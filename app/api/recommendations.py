from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.recommendations import (
    MeetingRecommendationRequest,
    MeetingRecommendationResponse,
    MeetingTimeRecommendation,
    RecommendationAttendeeBreakdown,
)


router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _resolve_attendees(
    db: Session,
    *,
    payload: MeetingRecommendationRequest,
    current_user: User,
) -> tuple[list[User], list[int], list[str]]:
    resolved_by_id: dict[int, User] = {}
    unresolved_user_ids: list[int] = []
    unresolved_emails: list[str] = []

    requested_ids = sorted(set(payload.attendee_user_ids))
    if requested_ids:
        users_by_id = db.execute(
            select(User).where(User.id.in_(requested_ids), User.is_active.is_(True))
        ).scalars()
        for user in users_by_id:
            resolved_by_id[user.id] = user
        unresolved_user_ids = [uid for uid in requested_ids if uid not in resolved_by_id]

    requested_emails = sorted({_normalize_email(str(email)) for email in payload.attendee_emails})
    if requested_emails:
        users_by_email = db.execute(
            select(User).where(User.email.in_(requested_emails), User.is_active.is_(True))
        ).scalars()
        email_to_user: dict[str, User] = {}
        for user in users_by_email:
            email_to_user[_normalize_email(user.email)] = user
            resolved_by_id[user.id] = user

        unresolved_emails = [email for email in requested_emails if _normalize_email(email) not in email_to_user]

    if payload.include_current_user:
        resolved_by_id[current_user.id] = current_user

    attendees = sorted(resolved_by_id.values(), key=lambda user: user.id)
    if not attendees:
        raise HTTPException(
            status_code=422,
            detail="No valid attendees resolved. Provide attendee_user_ids and/or attendee_emails.",
        )

    return attendees, unresolved_user_ids, unresolved_emails


def _load_preferences_by_user(
    db: Session, user_ids: list[int]
) -> dict[int, list[tuple[int, time, time]]]:
    preferences: dict[int, list[tuple[int, time, time]]] = {user_id: [] for user_id in user_ids}
    if not user_ids:
        return preferences

    stmt = text(
        """
        SELECT user_id, day_of_week, start_time, end_time
        FROM time_slot_preferences
        WHERE user_id IN :user_ids
        ORDER BY user_id, day_of_week, start_time
        """
    ).bindparams(bindparam("user_ids", expanding=True))
    rows = db.execute(stmt, {"user_ids": user_ids}).mappings()

    for row in rows:
        preferences[int(row["user_id"])].append(
            (
                int(row["day_of_week"]),
                row["start_time"],
                row["end_time"],
            )
        )

    return preferences


def _load_busy_intervals_by_user(
    db: Session,
    *,
    user_ids: list[int],
    window_start: datetime,
    window_end: datetime,
) -> dict[int, list[tuple[datetime, datetime]]]:
    busy: dict[int, list[tuple[datetime, datetime]]] = {user_id: [] for user_id in user_ids}
    if not user_ids:
        return busy

    owner_stmt = text(
        """
        SELECT c.owner_id AS user_id, m.start_time, m.end_time
        FROM meetings m
        JOIN calendars c ON c.id = m.calendar_id
        WHERE c.owner_type = 'user'
          AND c.owner_id IN :user_ids
          AND m.start_time < :window_end
          AND m.end_time > :window_start
        """
    ).bindparams(bindparam("user_ids", expanding=True))
    owner_rows = db.execute(
        owner_stmt,
        {
            "user_ids": user_ids,
            "window_start": window_start,
            "window_end": window_end,
        },
    ).mappings()

    attendee_stmt = text(
        """
        SELECT ma.user_id, m.start_time, m.end_time
        FROM meeting_attendees ma
        JOIN meetings m ON m.id = ma.meeting_id
        WHERE ma.user_id IN :user_ids
          AND ma.status IN ('invited', 'accepted')
          AND m.start_time < :window_end
          AND m.end_time > :window_start
        """
    ).bindparams(bindparam("user_ids", expanding=True))
    attendee_rows = db.execute(
        attendee_stmt,
        {
            "user_ids": user_ids,
            "window_start": window_start,
            "window_end": window_end,
        },
    ).mappings()

    for row in owner_rows:
        user_id = int(row["user_id"])
        start_time = _as_utc(row["start_time"])
        end_time = _as_utc(row["end_time"])
        busy[user_id].append((start_time, end_time))

    for row in attendee_rows:
        user_id = int(row["user_id"])
        start_time = _as_utc(row["start_time"])
        end_time = _as_utc(row["end_time"])
        busy[user_id].append((start_time, end_time))

    return busy


def _overlaps(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> bool:
    return a_start < b_end and a_end > b_start


def _within_preference(
    *,
    slot_start: datetime,
    slot_end: datetime,
    preferences_for_user: list[tuple[int, time, time]],
) -> bool:
    day_of_week = slot_start.isoweekday() % 7  # Sunday=0 ... Saturday=6
    slot_start_time = slot_start.time().replace(tzinfo=None)
    slot_end_time = slot_end.time().replace(tzinfo=None)

    for pref_day, pref_start, pref_end in preferences_for_user:
        if pref_day != day_of_week:
            continue
        if pref_start <= slot_start_time and pref_end >= slot_end_time:
            return True
    return False


def _score_slot(
    *,
    slot_start: datetime,
    slot_end: datetime,
    attendees: list[User],
    preferences_by_user: dict[int, list[tuple[int, time, time]]],
    busy_by_user: dict[int, list[tuple[datetime, datetime]]],
) -> MeetingTimeRecommendation:
    attendee_breakdown: list[RecommendationAttendeeBreakdown] = []
    busy_count = 0
    available_count = 0
    preferred_count = 0
    outside_preference_count = 0

    for attendee in attendees:
        busy_intervals = busy_by_user.get(attendee.id, [])
        is_busy = any(
            _overlaps(slot_start, slot_end, busy_start, busy_end) for busy_start, busy_end in busy_intervals
        )

        if is_busy:
            busy_count += 1
            attendee_breakdown.append(
                RecommendationAttendeeBreakdown(
                    user_id=attendee.id,
                    email=attendee.email,
                    state="busy",
                )
            )
            continue

        available_count += 1
        preferences = preferences_by_user.get(attendee.id, [])
        if not preferences:
            attendee_breakdown.append(
                RecommendationAttendeeBreakdown(
                    user_id=attendee.id,
                    email=attendee.email,
                    state="available_no_preference",
                )
            )
            continue

        if _within_preference(slot_start=slot_start, slot_end=slot_end, preferences_for_user=preferences):
            preferred_count += 1
            attendee_breakdown.append(
                RecommendationAttendeeBreakdown(
                    user_id=attendee.id,
                    email=attendee.email,
                    state="available_preferred",
                )
            )
        else:
            outside_preference_count += 1
            attendee_breakdown.append(
                RecommendationAttendeeBreakdown(
                    user_id=attendee.id,
                    email=attendee.email,
                    state="available_outside_preference",
                )
            )

    attendee_count = len(attendees)
    # Heavily penalize conflicts first, then outside-preference slots.
    score = (
        (attendee_count - busy_count) * 100
        + preferred_count * 5
        - outside_preference_count * 20
        - busy_count * 1000
    )

    return MeetingTimeRecommendation(
        start_time=slot_start,
        end_time=slot_end,
        score=score,
        available_count=available_count,
        busy_count=busy_count,
        preferred_count=preferred_count,
        outside_preference_count=outside_preference_count,
        attendee_breakdown=attendee_breakdown,
    )


def _build_candidate_slots(
    *,
    window_start: datetime,
    window_end: datetime,
    duration_minutes: int,
    interval_minutes: int,
) -> list[tuple[datetime, datetime]]:
    duration = timedelta(minutes=duration_minutes)
    interval = timedelta(minutes=interval_minutes)
    latest_start = window_end - duration
    if latest_start < window_start:
        return []

    slots: list[tuple[datetime, datetime]] = []
    current = window_start
    while current <= latest_start:
        slots.append((current, current + duration))
        current += interval
    return slots


@router.post("/meeting-times", response_model=MeetingRecommendationResponse)
def recommend_meeting_times(
    payload: MeetingRecommendationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return generate_meeting_time_recommendations(payload=payload, db=db, current_user=current_user)


def generate_meeting_time_recommendations(
    *,
    payload: MeetingRecommendationRequest,
    db: Session,
    current_user: User,
) -> MeetingRecommendationResponse:
    window_start = _as_utc(payload.window_start)
    window_end = _as_utc(payload.window_end)
    if window_end <= window_start:
        raise HTTPException(status_code=422, detail="window_end must be after window_start")

    attendees, unresolved_user_ids, unresolved_emails = _resolve_attendees(
        db, payload=payload, current_user=current_user
    )
    attendee_ids = [user.id for user in attendees]

    slots = _build_candidate_slots(
        window_start=window_start,
        window_end=window_end,
        duration_minutes=payload.duration_minutes,
        interval_minutes=payload.slot_interval_minutes,
    )
    if not slots:
        raise HTTPException(
            status_code=422,
            detail="No candidate slots in window. Increase window or reduce duration_minutes.",
        )

    preferences_by_user = _load_preferences_by_user(db, attendee_ids)
    busy_by_user = _load_busy_intervals_by_user(
        db,
        user_ids=attendee_ids,
        window_start=window_start,
        window_end=window_end,
    )

    recommendations = [
        _score_slot(
            slot_start=slot_start,
            slot_end=slot_end,
            attendees=attendees,
            preferences_by_user=preferences_by_user,
            busy_by_user=busy_by_user,
        )
        for slot_start, slot_end in slots
    ]

    recommendations.sort(
        key=lambda rec: (
            -rec.score,
            rec.busy_count,
            rec.outside_preference_count,
            -rec.preferred_count,
            rec.start_time,
        )
    )

    top_recommendations = recommendations[: payload.max_results]
    return MeetingRecommendationResponse(
        attendee_count=len(attendees),
        window_start=window_start,
        window_end=window_end,
        duration_minutes=payload.duration_minutes,
        slot_interval_minutes=payload.slot_interval_minutes,
        unresolved_user_ids=unresolved_user_ids,
        unresolved_emails=unresolved_emails,
        recommendations=top_recommendations,
    )
