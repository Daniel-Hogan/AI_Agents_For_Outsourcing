from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _minutes_to_time(total_minutes: int) -> time:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return time(hour=hours, minute=minutes)


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []

    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _subtract_intervals(
    base_intervals: list[tuple[int, int]], busy_intervals: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    if not base_intervals:
        return []
    if not busy_intervals:
        return base_intervals

    busy = _merge_intervals(busy_intervals)
    remaining: list[tuple[int, int]] = []

    for base_start, base_end in base_intervals:
        cursor = base_start
        for busy_start, busy_end in busy:
            if busy_end <= cursor:
                continue
            if busy_start >= base_end:
                break
            if busy_start > cursor:
                remaining.append((cursor, min(busy_start, base_end)))
            cursor = max(cursor, busy_end)
            if cursor >= base_end:
                break
        if cursor < base_end:
            remaining.append((cursor, base_end))

    return [(start, end) for start, end in remaining if end > start]


def _intersect_intervals(
    left: list[tuple[int, int]], right: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    intersections: list[tuple[int, int]] = []
    left_index = 0
    right_index = 0

    while left_index < len(left) and right_index < len(right):
        left_start, left_end = left[left_index]
        right_start, right_end = right[right_index]

        start = max(left_start, right_start)
        end = min(left_end, right_end)
        if start < end:
            intersections.append((start, end))

        if left_end < right_end:
            left_index += 1
        else:
            right_index += 1

    return intersections


def _round_up_to_increment(value: int, increment: int) -> int:
    remainder = value % increment
    if remainder == 0:
        return value
    return value + (increment - remainder)


def _date_to_day_index(value: date) -> int:
    return (value.weekday() + 1) % 7


def _daterange(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _load_weekly_availability(user_ids: list[int], db: Session) -> dict[int, dict[int, list[tuple[int, int]]]]:
    availability_by_user = {user_id: {} for user_id in user_ids}
    rows = db.execute(
        text(
            """
            SELECT user_id, day_of_week, start_time, end_time
            FROM time_slot_preferences
            WHERE user_id = ANY(:user_ids)
            ORDER BY user_id, day_of_week, start_time
            """
        ),
        {"user_ids": user_ids},
    ).mappings().all()

    for row in rows:
        user_day_intervals = availability_by_user[row["user_id"]].setdefault(row["day_of_week"], [])
        user_day_intervals.append((_time_to_minutes(row["start_time"]), _time_to_minutes(row["end_time"])))

    for user_id in availability_by_user:
        for day_of_week, intervals in availability_by_user[user_id].items():
            availability_by_user[user_id][day_of_week] = _merge_intervals(intervals)

    return availability_by_user


def _load_busy_meetings(
    user_ids: list[int], start_date: date, end_date: date, db: Session
) -> dict[int, list[dict]]:
    busy_by_user: dict[int, list[dict]] = {user_id: [] for user_id in user_ids}
    window_start = datetime.combine(start_date, time.min)
    window_end = datetime.combine(end_date + timedelta(days=1), time.min)

    for user_id in user_ids:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT m.id, m.start_time, m.end_time
                FROM meetings m
                LEFT JOIN meeting_attendees ma
                    ON ma.meeting_id = m.id AND ma.user_id = :user_id
                WHERE COALESCE(m.status, 'confirmed') <> 'cancelled'
                  AND m.end_time > :window_start
                  AND m.start_time < :window_end
                  AND (
                    m.created_by = :user_id
                    OR ma.status IN ('invited', 'accepted', 'maybe')
                  )
                ORDER BY m.start_time ASC
                """
            ),
            {"user_id": user_id, "window_start": window_start, "window_end": window_end},
        ).mappings().all()
        busy_by_user[user_id] = [dict(row) for row in rows]

    return busy_by_user


def _busy_intervals_for_day(meetings: list[dict], current_date: date) -> list[tuple[int, int]]:
    reference_tzinfo = None
    for meeting in meetings:
        if meeting["start_time"].tzinfo is not None:
            reference_tzinfo = meeting["start_time"].tzinfo
            break

    day_start = datetime.combine(current_date, time.min, tzinfo=reference_tzinfo)
    day_end = day_start + timedelta(days=1)
    intervals: list[tuple[int, int]] = []

    for meeting in meetings:
        overlap_start = max(meeting["start_time"], day_start)
        overlap_end = min(meeting["end_time"], day_end)
        if overlap_end <= overlap_start:
            continue
        start_minutes = int((overlap_start - day_start).total_seconds() // 60)
        end_minutes = int((overlap_end - day_start).total_seconds() // 60)
        intervals.append((start_minutes, end_minutes))

    return _merge_intervals(intervals)


def _build_day_candidates(
    current_date: date,
    participant_ids: list[int],
    availability_by_user: dict[int, dict[int, list[tuple[int, int]]]],
    busy_by_user: dict[int, list[dict]],
    duration_minutes: int,
    increment_minutes: int,
) -> list[dict]:
    day_index = _date_to_day_index(current_date)
    shared_intervals: list[tuple[int, int]] | None = None

    for user_id in participant_ids:
        daily_availability = availability_by_user.get(user_id, {}).get(day_index, [])
        if not daily_availability:
            return []

        busy_intervals = _busy_intervals_for_day(busy_by_user.get(user_id, []), current_date)
        free_intervals = _subtract_intervals(daily_availability, busy_intervals)
        if not free_intervals:
            return []

        shared_intervals = free_intervals if shared_intervals is None else _intersect_intervals(shared_intervals, free_intervals)
        if not shared_intervals:
            return []

    candidates: list[dict] = []
    for interval_start, interval_end in shared_intervals or []:
        candidate_start = _round_up_to_increment(interval_start, increment_minutes)
        while candidate_start + duration_minutes <= interval_end:
            start_time = datetime.combine(current_date, _minutes_to_time(candidate_start))
            end_time = datetime.combine(current_date, _minutes_to_time(candidate_start + duration_minutes))
            candidates.append(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "available_attendee_count": len(participant_ids),
                    "conflicted_attendee_count": 0,
                    "score": 100,
                    "reason": "All selected attendees are available and no existing meetings overlap.",
                }
            )
            candidate_start += increment_minutes

    return candidates


def recommend_common_slots(
    user_ids: list[int],
    start_date: date,
    end_date: date,
    duration_minutes: int,
    max_results: int,
    db: Session,
    increment_minutes: int = 30,
) -> list[dict]:
    availability_by_user = _load_weekly_availability(user_ids, db)
    busy_by_user = _load_busy_meetings(user_ids, start_date, end_date, db)

    all_candidates: list[dict] = []
    for current_date in _daterange(start_date, end_date):
        all_candidates.extend(
            _build_day_candidates(
                current_date=current_date,
                participant_ids=user_ids,
                availability_by_user=availability_by_user,
                busy_by_user=busy_by_user,
                duration_minutes=duration_minutes,
                increment_minutes=increment_minutes,
            )
        )

    all_candidates.sort(key=lambda candidate: candidate["start_time"])
    ranked_candidates = all_candidates[:max_results]
    for index, candidate in enumerate(ranked_candidates, start=1):
        candidate["rank"] = index

    return ranked_candidates
