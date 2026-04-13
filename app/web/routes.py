import calendar as month_calendar
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.api.auth import create_password_user_account
from app.api.recommendations import generate_meeting_time_recommendations
from app.api.deps import get_db
from app.core.security import verify_password
from app.models import PasswordCredential, User
from app.schemas.auth import RegisterRequest
from app.schemas.travel import LocationSuggestion
from app.schemas.recommendations import MeetingRecommendationRequest
from app.services.travel import autocomplete_locations, get_travel_warning_service


router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DAY_OPTIONS = [
    (0, "Sunday"),
    (1, "Monday"),
    (2, "Tuesday"),
    (3, "Wednesday"),
    (4, "Thursday"),
    (5, "Friday"),
    (6, "Saturday"),
]
DAY_NAME_BY_INDEX = {day: name for day, name in DAY_OPTIONS}
WARNING_SEVERITY_ORDER = {"critical": 0, "caution": 1, "info": 2}
ORIGIN_SOURCE_LABELS = {
    "previous_meeting": "From previous meeting",
    "user_default": "From your default location",
    "org_default": "From organization default",
    "unknown": "Origin unresolved",
}
CALENDAR_COLOR_TOKENS = ("sky", "amber", "lime", "coral", "violet")


def _push_flash(request: Request, category: str, msg: str) -> None:
    flashes = request.session.get("_flashes", [])
    flashes.append({"category": category, "message": msg})
    request.session["_flashes"] = flashes


def _pop_flashes(request: Request) -> list[dict[str, str]]:
    flashes = request.session.get("_flashes", [])
    request.session["_flashes"] = []
    return flashes


def _current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        return None
    return user


def _parse_datetime_local(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_optional_float(raw: str) -> float | None:
    value = raw.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_optional_date(raw: str) -> date | None:
    value = raw.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_optional_month(raw: str) -> date | None:
    value = raw.strip()
    if not value:
        return None
    try:
        return datetime.strptime(f"{value}-01", "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_location_form_state(
    *,
    location: str,
    location_raw: str,
    location_latitude: str,
    location_longitude: str,
) -> dict[str, str]:
    return {
        "location": location.strip(),
        "location_raw": location_raw.strip(),
        "location_latitude": location_latitude.strip(),
        "location_longitude": location_longitude.strip(),
    }


def _resolve_submitted_location(
    *,
    location: str,
    location_raw: str,
    location_latitude: str,
    location_longitude: str,
) -> dict[str, object]:
    display_text = location.strip()
    raw_text = location_raw.strip() or display_text
    latitude = _parse_optional_float(location_latitude)
    longitude = _parse_optional_float(location_longitude)
    coordinates_present = latitude is not None and longitude is not None

    return {
        "location": display_text or raw_text or None,
        "location_raw": raw_text or display_text or None,
        "location_latitude": latitude if coordinates_present else None,
        "location_longitude": longitude if coordinates_present else None,
        "location_is_resolved": coordinates_present,
    }


def _parse_invitee_emails(raw: str) -> tuple[list[str], list[str]]:
    parts = [p.strip().lower() for p in re.split(r"[,;\n]+", raw) if p.strip()]
    seen: set[str] = set()
    valid: list[str] = []
    invalid: list[str] = []

    for email in parts:
        if email in seen:
            continue
        seen.add(email)
        if EMAIL_RE.match(email):
            valid.append(email)
        else:
            invalid.append(email)
    return valid, invalid


def _get_or_create_personal_calendar(db: Session, user: User) -> int:
    existing_id = db.execute(
        text(
            """
            SELECT id
            FROM calendars
            WHERE owner_type = 'user' AND owner_id = :user_id
            ORDER BY id
            LIMIT 1
            """
        ),
        {"user_id": user.id},
    ).scalar_one_or_none()
    if existing_id is not None:
        return int(existing_id)

    return int(
        db.execute(
            text(
                """
                INSERT INTO calendars (name, owner_type, owner_id)
                VALUES (:name, 'user', :user_id)
                RETURNING id
                """
            ),
            {"name": f"{user.email} calendar", "user_id": user.id},
        ).scalar_one()
    )


def _list_meetings(db: Session, *, user: User, q: str, status: str, mine: bool):
    sql = """
        SELECT
            m.id,
            m.title,
            COALESCE(u.email, 'group-calendar') AS organizer_email,
            m.start_time,
            m.end_time,
            m.location,
            m.location_latitude,
            m.location_longitude,
            CASE
                WHEN m.end_time < NOW() THEN 'completed'
                ELSE 'scheduled'
            END AS status,
            (
                EXISTS (
                    SELECT 1
                    FROM calendars own_c
                    WHERE own_c.id = m.calendar_id
                      AND own_c.owner_type = 'user'
                      AND own_c.owner_id = :current_user_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM meeting_attendees own_ma
                    WHERE own_ma.meeting_id = m.id
                      AND own_ma.user_id = :current_user_id
                      AND own_ma.status IN ('invited', 'accepted')
                )
            ) AS is_relevant_to_user
        FROM meetings m
        JOIN calendars c ON c.id = m.calendar_id
        LEFT JOIN users u ON c.owner_type = 'user' AND c.owner_id = u.id
        WHERE 1=1
    """
    params: dict[str, object] = {"current_user_id": user.id}

    if q:
        sql += " AND (m.title ILIKE :q OR COALESCE(m.location, '') ILIKE :q OR COALESCE(u.email, '') ILIKE :q)"
        params["q"] = f"%{q}%"

    if status in {"scheduled", "completed"}:
        if status == "completed":
            sql += " AND m.end_time < NOW()"
        if status == "scheduled":
            sql += " AND m.end_time >= NOW()"

    if mine:
        sql += " AND COALESCE(u.email, '') = :email"
        params["email"] = user.email

    sql += " ORDER BY m.start_time ASC"
    return db.execute(text(sql), params).mappings().all()


def _coerce_datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _format_time_label(value: datetime | None) -> str:
    if value is None:
        return "--"
    return value.strftime("%I:%M %p").lstrip("0")


def _format_day_label(value: date) -> str:
    return value.strftime("%A, %B ") + str(value.day) + value.strftime(", %Y")


def _pluralize(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"


def _build_meetings_query_string(*, q: str, status: str, mine: bool, day_value: str) -> str:
    params: dict[str, str] = {}
    if q:
        params["q"] = q
    if status:
        params["status"] = status
    if mine:
        params["mine"] = "1"
    if day_value:
        params["day"] = day_value
    return urlencode(params)


def _shift_month(month_value: date, offset: int) -> date:
    shifted = month_value.replace(day=1)
    month_index = shifted.month - 1 + offset
    year = shifted.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _pick_calendar_color_token(meeting: dict[str, Any]) -> str:
    severity = str(meeting.get("primary_severity") or "none")
    if severity == "critical":
        return "rose"
    if severity == "caution":
        return "amber"
    if severity == "info":
        return "sky"

    meeting_id = int(meeting.get("id") or 0)
    return CALENDAR_COLOR_TOKENS[meeting_id % len(CALENDAR_COLOR_TOKENS)]


def _build_agenda_item(meeting: dict[str, Any]) -> dict[str, Any]:
    start_dt = _coerce_datetime_value(meeting.get("start_time"))
    end_dt = _coerce_datetime_value(meeting.get("end_time"))
    warnings = [dict(item) for item in meeting.get("travel_warnings") or []]
    primary_warning = min(
        warnings,
        key=lambda warning: WARNING_SEVERITY_ORDER.get(str(warning.get("severity")), 99),
        default=None,
    )

    travel_snapshot = next(
        (
            warning
            for warning in warnings
            if warning.get("travel_minutes") is not None
            or warning.get("distance_miles") is not None
            or warning.get("distance_km") is not None
            or warning.get("origin_source") not in {None, "", "unknown"}
        ),
        None,
    )

    if travel_snapshot:
        travel_badges: list[str] = []
        if travel_snapshot.get("travel_minutes") is not None:
            travel_badges.append(f"{travel_snapshot['travel_minutes']} min travel")
        if travel_snapshot.get("distance_miles") is not None:
            travel_badges.append(f"{travel_snapshot['distance_miles']:.1f} mi")
        elif travel_snapshot.get("distance_km") is not None:
            travel_badges.append(f"{travel_snapshot['distance_km']:.1f} km")
        origin_source = str(travel_snapshot.get("origin_source") or "unknown")
        if origin_source in ORIGIN_SOURCE_LABELS:
            travel_badges.append(ORIGIN_SOURCE_LABELS[origin_source])
        travel_summary = " · ".join(travel_badges)
    elif meeting.get("location"):
        travel_summary = "No travel warning recorded."
        travel_badges = []
    else:
        travel_summary = "Travel info unavailable without a location."
        travel_badges = []

    has_actionable_warning = any(
        warning.get("severity") in {"critical", "caution"} for warning in warnings
    )

    return {
        **meeting,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "day_iso": start_dt.date().isoformat() if start_dt else "",
        "time_range_label": f"{_format_time_label(start_dt)} - {_format_time_label(end_dt)}",
        "start_time_label": _format_time_label(start_dt),
        "end_time_label": _format_time_label(end_dt),
        "location_label": meeting.get("location") or "No location provided",
        "primary_warning": primary_warning,
        "primary_severity": primary_warning.get("severity", "none") if primary_warning else "none",
        "travel_summary": travel_summary,
        "travel_badges": travel_badges,
        "has_actionable_warning": has_actionable_warning,
        "status_label": str(meeting.get("status") or "scheduled").capitalize(),
    }


def _build_agenda_context(
    meetings: list[dict[str, Any]],
    *,
    selected_day_raw: str,
    q: str,
    status: str,
    mine: bool,
) -> dict[str, Any]:
    agenda_items = [_build_agenda_item(dict(meeting)) for meeting in meetings]
    requested_day = _parse_optional_date(selected_day_raw)
    if requested_day is None:
        requested_day = next(
            (item["start_dt"].date() for item in agenda_items if item.get("start_dt") is not None),
            datetime.now(timezone.utc).date(),
        )

    selected_day_iso = requested_day.isoformat()
    selected_meetings = [item for item in agenda_items if item.get("day_iso") == selected_day_iso]
    warning_count = sum(1 for item in selected_meetings if item["has_actionable_warning"])
    info_count = sum(
        1
        for item in selected_meetings
        if any(warning.get("severity") == "info" for warning in item.get("travel_warnings") or [])
    )

    return {
        "selected_day": selected_day_iso,
        "selected_day_label": _format_day_label(requested_day),
        "meeting_count": len(selected_meetings),
        "warning_count": warning_count,
        "info_count": info_count,
        "meeting_count_label": _pluralize(len(selected_meetings), "meeting"),
        "warning_count_label": _pluralize(warning_count, "travel warning"),
        "info_count_label": _pluralize(info_count, "routing note"),
        "meetings": selected_meetings,
        "is_empty": len(selected_meetings) == 0,
        "prev_query": _build_meetings_query_string(
            q=q,
            status=status,
            mine=mine,
            day_value=(requested_day - timedelta(days=1)).isoformat(),
        ),
        "next_query": _build_meetings_query_string(
            q=q,
            status=status,
            mine=mine,
            day_value=(requested_day + timedelta(days=1)).isoformat(),
        ),
        "today_query": _build_meetings_query_string(
            q=q,
            status=status,
            mine=mine,
            day_value=datetime.now(timezone.utc).date().isoformat(),
        ),
    }


def _build_calendar_context(meetings: list[dict[str, Any]], *, selected_month_raw: str) -> dict[str, Any]:
    agenda_items = [_build_agenda_item(dict(meeting)) for meeting in meetings]
    requested_month = _parse_optional_month(selected_month_raw)
    if requested_month is None:
        requested_month = next(
            (
                item["start_dt"].date().replace(day=1)
                for item in agenda_items
                if item.get("start_dt") is not None
            ),
            datetime.now(timezone.utc).date().replace(day=1),
        )

    month_start = requested_month.replace(day=1)
    month_grid = month_calendar.Calendar(firstweekday=6).monthdatescalendar(month_start.year, month_start.month)
    visible_start = month_grid[0][0]
    visible_end = month_grid[-1][-1]
    today = datetime.now(timezone.utc).date()

    meetings_by_day: dict[str, list[dict[str, Any]]] = {}
    month_groups: dict[str, list[dict[str, Any]]] = {}

    for item in agenda_items:
        start_dt = item.get("start_dt")
        if start_dt is None:
            continue

        meeting_day = start_dt.date()
        if not (visible_start <= meeting_day <= visible_end):
            continue

        calendar_item = {
            **item,
            "color_token": _pick_calendar_color_token(item),
            "detail_url": f"/meetings/{item['id']}",
            "date_label": _format_day_label(meeting_day),
            "warning_message": item["primary_warning"]["message"]
            if item.get("primary_warning")
            else "No active travel warning for this meeting.",
        }
        meetings_by_day.setdefault(meeting_day.isoformat(), []).append(calendar_item)

        if meeting_day.month == month_start.month and meeting_day.year == month_start.year:
            month_groups.setdefault(meeting_day.isoformat(), []).append(calendar_item)

    for day_items in meetings_by_day.values():
        day_items.sort(key=lambda item: item["start_dt"] or datetime.max.replace(tzinfo=timezone.utc))
    for day_items in month_groups.values():
        day_items.sort(key=lambda item: item["start_dt"] or datetime.max.replace(tzinfo=timezone.utc))

    weeks: list[list[dict[str, Any]]] = []
    for week in month_grid:
        week_cells: list[dict[str, Any]] = []
        for day_value in week:
            day_iso = day_value.isoformat()
            day_meetings = meetings_by_day.get(day_iso, [])
            week_cells.append(
                {
                    "date_iso": day_iso,
                    "day_number": day_value.day,
                    "is_current_month": day_value.month == month_start.month,
                    "is_today": day_value == today,
                    "meetings": day_meetings[:3],
                    "meeting_count": len(day_meetings),
                    "more_count": max(0, len(day_meetings) - 3),
                }
            )
        weeks.append(week_cells)

    grouped_meetings = [
        {"label": _format_day_label(_parse_optional_date(day_iso) or month_start), "meetings": month_groups[day_iso]}
        for day_iso in sorted(month_groups.keys())
    ]

    month_meeting_count = sum(len(items) for items in month_groups.values())
    return {
        "selected_month": month_start.strftime("%Y-%m"),
        "month_label": month_start.strftime("%B %Y"),
        "meeting_count_label": _pluralize(month_meeting_count, "meeting"),
        "weeks": weeks,
        "grouped_meetings": grouped_meetings,
        "is_empty": month_meeting_count == 0,
        "prev_query": urlencode({"month": _shift_month(month_start, -1).strftime("%Y-%m")}),
        "next_query": urlencode({"month": _shift_month(month_start, 1).strftime("%Y-%m")}),
        "today_query": urlencode({"month": datetime.now(timezone.utc).date().replace(day=1).strftime("%Y-%m")}),
    }


def _format_travel_warning_flash(warning: dict[str, Any]) -> str:
    origin = warning.get("origin_location") or "origin"
    destination = warning.get("destination_location") or "meeting"
    travel_minutes = warning.get("travel_minutes")
    available_minutes = warning.get("available_minutes")

    detail = f"{warning['message']} {origin} -> {destination}."
    if travel_minutes is not None and available_minutes is not None:
        detail += f" Estimated travel: {travel_minutes} min; available gap: {available_minutes} min."
    return detail


def _load_meetings_with_travel_context(db: Session, *, user: User, q: str, status: str, mine: bool) -> list[dict[str, Any]]:
    rows = _list_meetings(db, user=user, q=q, status=status, mine=mine)
    fallback_rows: list[dict[str, Any]] = []
    for row in rows:
        meeting = dict(row)
        meeting["travel_warnings"] = []
        fallback_rows.append(meeting)

    try:
        meetings = get_travel_warning_service().enrich_meetings(db, user=user, meetings=rows, persist=True)
        db.commit()
        return meetings
    except Exception:
        db.rollback()
        return fallback_rows


def _invitable_users(db: Session, current_user_id: int) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT email
            FROM users
            WHERE is_active = true AND id <> :current_user_id
            ORDER BY email
            """
        ),
        {"current_user_id": current_user_id},
    ).mappings()
    return [str(row["email"]) for row in rows]


def _overlap_conflict_count(
    db: Session,
    *,
    user_id: int,
    slot_start: datetime,
    slot_end: datetime,
    exclude_meeting_id: int | None = None,
) -> int:
    return int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM meetings m
                WHERE m.start_time < :slot_end
                  AND m.end_time > :slot_start
                  AND (:exclude_meeting_id IS NULL OR m.id <> :exclude_meeting_id)
                  AND (
                    EXISTS (
                        SELECT 1
                        FROM calendars c
                        WHERE c.id = m.calendar_id
                          AND c.owner_type = 'user'
                          AND c.owner_id = :user_id
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM meeting_attendees ma
                        WHERE ma.meeting_id = m.id
                          AND ma.user_id = :user_id
                          AND ma.status IN ('invited', 'accepted')
                    )
                  )
                """
            ),
            {
                "slot_start": slot_start,
                "slot_end": slot_end,
                "user_id": user_id,
                "exclude_meeting_id": exclude_meeting_id,
            },
        ).scalar_one()
    )


def _preferred_slot_info(db: Session, *, user_id: int, slot_start: datetime, slot_end: datetime) -> tuple[bool, bool]:
    has_preferences = bool(
        db.execute(
            text("SELECT EXISTS (SELECT 1 FROM time_slot_preferences WHERE user_id = :user_id)"),
            {"user_id": user_id},
        ).scalar_one()
    )
    if not has_preferences:
        return False, False

    day_of_week = slot_start.isoweekday() % 7  # Sunday=0 ... Saturday=6
    start_time = slot_start.time().replace(tzinfo=None)
    end_time = slot_end.time().replace(tzinfo=None)
    within_preference = bool(
        db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM time_slot_preferences
                    WHERE user_id = :user_id
                      AND day_of_week = :day_of_week
                      AND start_time <= :slot_start_time
                      AND end_time >= :slot_end_time
                )
                """
            ),
            {
                "user_id": user_id,
                "day_of_week": day_of_week,
                "slot_start_time": start_time,
                "slot_end_time": end_time,
            },
        ).scalar_one()
    )
    return True, within_preference


def _availability_summary(
    db: Session,
    *,
    user_id: int,
    slot_start: datetime,
    slot_end: datetime,
    exclude_meeting_id: int | None = None,
) -> tuple[str, int]:
    conflict_count = _overlap_conflict_count(
        db,
        user_id=user_id,
        slot_start=slot_start,
        slot_end=slot_end,
        exclude_meeting_id=exclude_meeting_id,
    )
    if conflict_count > 0:
        return "Busy (has overlapping meetings)", conflict_count

    has_preferences, within_preference = _preferred_slot_info(
        db, user_id=user_id, slot_start=slot_start, slot_end=slot_end
    )
    if has_preferences and not within_preference:
        return "Outside preferred availability", 0
    if has_preferences and within_preference:
        return "Available (within preferred slot)", 0
    return "Available (no preferences set)", 0


def _build_availability_preview(
    db: Session, *, emails: list[str], slot_start: datetime, slot_end: datetime
) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for email in emails:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            preview.append(
                {
                    "email": email,
                    "status": "User not found",
                    "conflicts": 0,
                    "exists": False,
                }
            )
            continue

        status, conflicts = _availability_summary(
            db,
            user_id=user.id,
            slot_start=slot_start,
            slot_end=slot_end,
        )
        preview.append(
            {
                "email": email,
                "status": status,
                "conflicts": conflicts,
                "exists": True,
            }
        )
    return preview


def _load_user_preferences(db: Session, user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT id, day_of_week, start_time, end_time
            FROM time_slot_preferences
            WHERE user_id = :user_id
            ORDER BY day_of_week ASC, start_time ASC
            """
        ),
        {"user_id": user_id},
    ).mappings()
    preferences: list[dict[str, Any]] = []
    for row in rows:
        day_idx = int(row["day_of_week"])
        start_time = row["start_time"]
        end_time = row["end_time"]
        preferences.append(
            {
                "id": int(row["id"]),
                "day_of_week": day_idx,
                "day_name": DAY_NAME_BY_INDEX.get(day_idx, f"Day {day_idx}"),
                "start_time": start_time.strftime("%H:%M"),
                "end_time": end_time.strftime("%H:%M"),
            }
        )
    return preferences


def _parse_time_value(raw: str) -> time:
    return time.fromisoformat(raw.strip())


def _render_availability_page(
    request: Request,
    *,
    db: Session,
    user: User,
    form_data: dict[str, str] | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="availability.html",
        context={
            "email": user.email,
            "messages": _pop_flashes(request),
            "preferences": _load_user_preferences(db, user.id),
            "day_options": DAY_OPTIONS,
            "form_data": form_data or {"day_of_week": "1", "start_time": "", "end_time": ""},
        },
    )


def _render_signup_page(
    request: Request,
    *,
    form_data: dict[str, str] | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={
            "messages": _pop_flashes(request),
            "form_data": form_data
            or {
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
            },
        },
    )


def _render_meetings_page(
    request: Request,
    *,
    db: Session,
    user: User,
    q: str,
    status: str,
    mine: bool,
    selected_day: str = "",
    create_form: dict[str, str] | None = None,
    availability_preview: list[dict[str, Any]] | None = None,
    recommendation_form: dict[str, str] | None = None,
    meeting_recommendations: list[dict[str, Any]] | None = None,
    unresolved_recommendation_emails: list[str] | None = None,
    unresolved_recommendation_user_ids: list[int] | None = None,
):
    create_form_value = create_form or {
        "title": "",
        "location": "",
        "location_raw": "",
        "location_latitude": "",
        "location_longitude": "",
        "start_time": "",
        "end_time": "",
        "invitees": "",
    }
    recommendation_form_value = {
        "window_start": create_form_value["start_time"],
        "window_end": create_form_value["end_time"],
        "duration_minutes": "60",
        "slot_interval_minutes": "30",
        "max_results": "5",
    }
    if recommendation_form:
        recommendation_form_value.update(recommendation_form)
    meetings = _load_meetings_with_travel_context(db, user=user, q=q, status=status, mine=mine)

    return templates.TemplateResponse(
        request=request,
        name="meetings.html",
        context={
            "meetings": meetings,
            "agenda": _build_agenda_context(
                meetings,
                selected_day_raw=selected_day,
                q=q,
                status=status,
                mine=mine,
            ),
            "q": q,
            "status": status,
            "mine": mine,
            "selected_day": selected_day,
            "email": user.email,
            "messages": _pop_flashes(request),
            "create_form": create_form_value,
            "availability_preview": availability_preview or [],
            "recommendation_form": recommendation_form_value,
            "meeting_recommendations": meeting_recommendations or [],
            "unresolved_recommendation_emails": unresolved_recommendation_emails or [],
            "unresolved_recommendation_user_ids": unresolved_recommendation_user_ids or [],
            "invitable_users": _invitable_users(db, user.id),
        },
    )


def _render_calendar_page(
    request: Request,
    *,
    db: Session,
    user: User,
    selected_month: str = "",
):
    meetings = _load_meetings_with_travel_context(db, user=user, q="", status="", mine=False)
    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={
            "email": user.email,
            "messages": _pop_flashes(request),
            "calendar_view": _build_calendar_context(meetings, selected_month_raw=selected_month),
        },
    )


@router.get("/", name="web_index")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"messages": _pop_flashes(request)},
    )


@router.get("/signup", name="web_signup_page")
def signup_page(request: Request):
    return _render_signup_page(request)


@router.post("/signup", name="web_signup")
def signup(
    request: Request,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    form_data = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
    }

    if password != confirm_password:
        _push_flash(request, "error", "Passwords do not match.")
        return _render_signup_page(request, form_data=form_data)

    try:
        payload = RegisterRequest(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.strip().lower(),
            phone=phone.strip() or None,
            password=password,
        )
    except ValidationError as exc:
        first_error = exc.errors()[0]["msg"] if exc.errors() else "Use valid signup details."
        _push_flash(request, "error", str(first_error))
        return _render_signup_page(request, form_data=form_data)

    try:
        user = create_password_user_account(db, payload=payload)
    except HTTPException as exc:
        _push_flash(request, "error", str(exc.detail))
        return _render_signup_page(request, form_data=form_data)

    request.session["user_id"] = user.id
    _push_flash(request, "success", f"Account created. Signed in as {user.email}")
    return RedirectResponse(url="/meetings", status_code=303)


@router.post("/login", name="web_login")
def web_login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()

    if user is None or not user.is_active:
        _push_flash(request, "error", "Invalid credentials.")
        return RedirectResponse(url="/", status_code=303)

    cred = db.get(PasswordCredential, user.id)
    if cred is None or not verify_password(password, cred.password_hash):
        _push_flash(request, "error", "Invalid credentials.")
        return RedirectResponse(url="/", status_code=303)

    request.session["user_id"] = user.id
    _push_flash(request, "success", f"Signed in as {user.email}")
    return RedirectResponse(url="/meetings", status_code=303)


@router.get("/locations/autocomplete", name="web_locations_autocomplete")
def locations_autocomplete(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        return JSONResponse(status_code=401, content={"suggestions": [], "status": "unauthorized"})

    query = q.strip()
    if len(query) < 3:
        return {"suggestions": [], "status": "idle"}

    suggestions = [
        LocationSuggestion(label=item.label, latitude=item.latitude, longitude=item.longitude).model_dump(mode="python")
        for item in autocomplete_locations(query, size=5)
    ]
    return {"suggestions": suggestions, "status": "ok"}


@router.get("/dashboard", name="web_dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"email": user.email, "messages": _pop_flashes(request)},
    )


@router.get("/availability", name="web_availability")
def availability_page(request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)
    return _render_availability_page(request, db=db, user=user)


@router.get("/calendar", name="web_calendar")
def calendar_page(request: Request, db: Session = Depends(get_db), month: str = ""):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)
    return _render_calendar_page(request, db=db, user=user, selected_month=month.strip())


@router.post("/availability/add", name="web_availability_add")
def availability_add(
    request: Request,
    day_of_week: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    form_data = {
        "day_of_week": day_of_week.strip(),
        "start_time": start_time.strip(),
        "end_time": end_time.strip(),
    }

    try:
        day_value = int(day_of_week)
        start_value = _parse_time_value(start_time)
        end_value = _parse_time_value(end_time)
    except Exception:
        _push_flash(request, "error", "Use valid day/start/end values.")
        return _render_availability_page(request, db=db, user=user, form_data=form_data)

    if day_value < 0 or day_value > 6:
        _push_flash(request, "error", "Day of week must be between 0 and 6.")
        return _render_availability_page(request, db=db, user=user, form_data=form_data)

    if end_value <= start_value:
        _push_flash(request, "error", "End time must be after start time.")
        return _render_availability_page(request, db=db, user=user, form_data=form_data)

    overlaps_existing = bool(
        db.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM time_slot_preferences
                    WHERE user_id = :user_id
                      AND day_of_week = :day_of_week
                      AND start_time < :end_time
                      AND end_time > :start_time
                )
                """
            ),
            {
                "user_id": user.id,
                "day_of_week": day_value,
                "start_time": start_value,
                "end_time": end_value,
            },
        ).scalar_one()
    )
    if overlaps_existing:
        _push_flash(request, "error", "This slot overlaps an existing preference.")
        return _render_availability_page(request, db=db, user=user, form_data=form_data)

    db.execute(
        text(
            """
            INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
            VALUES (:user_id, :day_of_week, :start_time, :end_time)
            """
        ),
        {
            "user_id": user.id,
            "day_of_week": day_value,
            "start_time": start_value,
            "end_time": end_value,
        },
    )
    db.commit()

    _push_flash(request, "success", "Availability preference added.")
    return RedirectResponse(url="/availability", status_code=303)


@router.post("/availability/delete", name="web_availability_delete")
def availability_delete(request: Request, preference_id: int = Form(...), db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    deleted = db.execute(
        text(
            """
            DELETE FROM time_slot_preferences
            WHERE id = :preference_id
              AND user_id = :user_id
            """
        ),
        {"preference_id": preference_id, "user_id": user.id},
    ).rowcount
    db.commit()

    if deleted:
        _push_flash(request, "success", "Availability preference removed.")
    else:
        _push_flash(request, "error", "Preference not found.")
    return RedirectResponse(url="/availability", status_code=303)


@router.get("/meetings", name="web_meetings")
def meetings(
    request: Request,
    db: Session = Depends(get_db),
    q: str = "",
    status: str = "",
    mine: str = "",
    day: str = "",
):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    return _render_meetings_page(
        request,
        db=db,
        user=user,
        q=q.strip(),
        status=status.strip().lower(),
        mine=mine.strip() == "1",
        selected_day=day.strip(),
    )


@router.post("/meetings/availability", name="web_meetings_availability")
def meetings_availability(
    request: Request,
    title: str = Form(""),
    location: str = Form(""),
    location_raw: str = Form(""),
    location_latitude: str = Form(""),
    location_longitude: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    invitees: str = Form(""),
    recommendation_window_start: str = Form(""),
    recommendation_window_end: str = Form(""),
    recommendation_duration_minutes: str = Form("60"),
    recommendation_slot_interval_minutes: str = Form("30"),
    recommendation_max_results: str = Form("5"),
    q: str = Form(""),
    status: str = Form(""),
    mine: str = Form(""),
    day: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    q_norm = q.strip()
    status_norm = status.strip().lower()
    mine_enabled = mine.strip() == "1"
    selected_day = day.strip()
    create_form = {
        "title": title.strip(),
        **_build_location_form_state(
            location=location,
            location_raw=location_raw,
            location_latitude=location_latitude,
            location_longitude=location_longitude,
        ),
        "start_time": start_time.strip(),
        "end_time": end_time.strip(),
        "invitees": invitees.strip(),
    }
    recommendation_form = {
        "window_start": recommendation_window_start.strip() or start_time.strip(),
        "window_end": recommendation_window_end.strip() or end_time.strip(),
        "duration_minutes": recommendation_duration_minutes.strip() or "60",
        "slot_interval_minutes": recommendation_slot_interval_minutes.strip() or "30",
        "max_results": recommendation_max_results.strip() or "5",
    }

    try:
        start_dt = _parse_datetime_local(start_time)
        end_dt = _parse_datetime_local(end_time)
    except Exception:
        _push_flash(request, "error", "Use valid start/end date-time values to check availability.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
            recommendation_form=recommendation_form,
        )

    if end_dt <= start_dt:
        _push_flash(request, "error", "End time must be after start time.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
            recommendation_form=recommendation_form,
        )

    emails, invalid_emails = _parse_invitee_emails(invitees)
    if invalid_emails:
        _push_flash(request, "error", f"Ignored invalid emails: {', '.join(invalid_emails)}")
    if not emails:
        _push_flash(request, "error", "Add at least one invitee email.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
            recommendation_form=recommendation_form,
        )

    preview = _build_availability_preview(db, emails=emails, slot_start=start_dt, slot_end=end_dt)

    recommendations: list[dict[str, Any]] = []
    unresolved_user_ids: list[int] = []
    unresolved_emails: list[str] = []
    try:
        recommendation_payload = MeetingRecommendationRequest(
            attendee_emails=emails,
            window_start=_parse_datetime_local(recommendation_form["window_start"]),
            window_end=_parse_datetime_local(recommendation_form["window_end"]),
            duration_minutes=int(recommendation_form["duration_minutes"]),
            slot_interval_minutes=int(recommendation_form["slot_interval_minutes"]),
            max_results=int(recommendation_form["max_results"]),
            include_current_user=True,
        )
        recommendation_response = generate_meeting_time_recommendations(
            payload=recommendation_payload,
            db=db,
            current_user=user,
        )
        recommendations = [rec.model_dump(mode="python") for rec in recommendation_response.recommendations]
        unresolved_user_ids = recommendation_response.unresolved_user_ids
        unresolved_emails = recommendation_response.unresolved_emails
        _push_flash(request, "success", "Availability preview and recommendations updated.")
    except HTTPException as exc:
        _push_flash(request, "error", f"Recommendations unavailable: {exc.detail}")
    except Exception:
        _push_flash(request, "error", "Recommendations unavailable due to invalid recommendation settings.")

    return _render_meetings_page(
        request,
        db=db,
        user=user,
        q=q_norm,
        status=status_norm,
        mine=mine_enabled,
        selected_day=selected_day,
        create_form=create_form,
        availability_preview=preview,
        recommendation_form=recommendation_form,
        meeting_recommendations=recommendations,
        unresolved_recommendation_emails=unresolved_emails,
        unresolved_recommendation_user_ids=unresolved_user_ids,
    )


@router.post("/meetings/create", name="web_meetings_create")
def meetings_create(
    request: Request,
    title: str = Form(""),
    location: str = Form(""),
    location_raw: str = Form(""),
    location_latitude: str = Form(""),
    location_longitude: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    invitees: str = Form(""),
    q: str = Form(""),
    status: str = Form(""),
    mine: str = Form(""),
    day: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    q_norm = q.strip()
    status_norm = status.strip().lower()
    mine_enabled = mine.strip() == "1"
    selected_day = day.strip()
    create_form = {
        "title": title.strip(),
        **_build_location_form_state(
            location=location,
            location_raw=location_raw,
            location_latitude=location_latitude,
            location_longitude=location_longitude,
        ),
        "start_time": start_time.strip(),
        "end_time": end_time.strip(),
        "invitees": invitees.strip(),
    }

    if not title.strip():
        _push_flash(request, "error", "Meeting title is required.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
        )

    try:
        start_dt = _parse_datetime_local(start_time)
        end_dt = _parse_datetime_local(end_time)
    except Exception:
        _push_flash(request, "error", "Use valid start/end date-time values.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
        )

    if end_dt <= start_dt:
        _push_flash(request, "error", "End time must be after start time.")
        return _render_meetings_page(
            request,
            db=db,
            user=user,
            q=q_norm,
            status=status_norm,
            mine=mine_enabled,
            selected_day=selected_day,
            create_form=create_form,
        )

    emails, invalid_emails = _parse_invitee_emails(invitees)
    if invalid_emails:
        _push_flash(request, "error", f"Ignored invalid emails: {', '.join(invalid_emails)}")

    resolved_location = _resolve_submitted_location(
        location=location,
        location_raw=location_raw,
        location_latitude=location_latitude,
        location_longitude=location_longitude,
    )
    calendar_id = _get_or_create_personal_calendar(db, user)
    meeting_id = int(
        db.execute(
            text(
                """
                INSERT INTO meetings (
                    calendar_id,
                    title,
                    location,
                    location_raw,
                    location_latitude,
                    location_longitude,
                    start_time,
                    end_time,
                    capacity,
                    setup_minutes,
                    cleanup_minutes
                )
                VALUES (
                    :calendar_id,
                    :title,
                    :location,
                    :location_raw,
                    :location_latitude,
                    :location_longitude,
                    :start_time,
                    :end_time,
                    NULL,
                    0,
                    0
                )
                RETURNING id
                """
            ),
            {
                "calendar_id": calendar_id,
                "title": title.strip(),
                "location": resolved_location["location"],
                "location_raw": resolved_location["location_raw"],
                "location_latitude": resolved_location["location_latitude"],
                "location_longitude": resolved_location["location_longitude"],
                "start_time": start_dt,
                "end_time": end_dt,
            },
        ).scalar_one()
    )

    db.execute(
        text(
            """
            INSERT INTO meeting_attendees (meeting_id, user_id, status)
            VALUES (:meeting_id, :user_id, 'accepted')
            ON CONFLICT (meeting_id, user_id) DO NOTHING
            """
        ),
        {"meeting_id": meeting_id, "user_id": user.id},
    )

    invited_count = 0
    missing_users: list[str] = []
    for email in emails:
        invitee = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if invitee is None:
            missing_users.append(email)
            continue

        status_value = "accepted" if invitee.id == user.id else "invited"
        db.execute(
            text(
                """
                INSERT INTO meeting_attendees (meeting_id, user_id, status)
                VALUES (:meeting_id, :user_id, :status)
                ON CONFLICT (meeting_id, user_id) DO NOTHING
                """
            ),
            {"meeting_id": meeting_id, "user_id": invitee.id, "status": status_value},
        )
        if invitee.id != user.id:
            invited_count += 1

    travel_warnings = get_travel_warning_service().evaluate_meeting(
        db,
        user=user,
        meeting={
            "id": meeting_id,
            "title": title.strip(),
            "start_time": start_dt,
            "end_time": end_dt,
            "location": resolved_location["location"],
            "location_latitude": resolved_location["location_latitude"],
            "location_longitude": resolved_location["location_longitude"],
            "is_relevant_to_user": True,
        },
        persist=True,
    )
    db.commit()

    summary = f"Meeting created. Invited {invited_count} user(s)."
    if missing_users:
        summary += f" Not found: {', '.join(missing_users)}."
    _push_flash(request, "success", summary)
    first_actionable_warning = next(
        (warning for warning in travel_warnings if warning.severity in {"critical", "caution"}),
        None,
    )
    if first_actionable_warning is not None:
        _push_flash(
            request,
            "error" if first_actionable_warning.severity == "critical" else "warning",
            _format_travel_warning_flash(first_actionable_warning.model_dump(mode="python")),
        )
    return RedirectResponse(url=f"/meetings/{meeting_id}", status_code=303)


@router.get("/meetings/{meeting_id}", name="web_meeting_detail")
def meeting_detail(meeting_id: int, request: Request, db: Session = Depends(get_db)):
    user = _current_user(request, db)
    if user is None:
        _push_flash(request, "error", "Please sign in first.")
        return RedirectResponse(url="/", status_code=303)

    row = db.execute(
        text(
            """
            SELECT
                m.id,
                m.title,
                COALESCE(u.email, 'group-calendar') AS organizer_email,
                m.start_time,
                m.end_time,
                m.location,
                CASE
                    WHEN m.end_time < NOW() THEN 'completed'
                    ELSE 'scheduled'
                END AS status
            FROM meetings m
            JOIN calendars c ON c.id = m.calendar_id
            LEFT JOIN users u ON c.owner_type = 'user' AND c.owner_id = u.id
            WHERE m.id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().one_or_none()

    if row is None:
        _push_flash(request, "error", "Meeting not found.")
        return RedirectResponse(url="/meetings", status_code=303)

    start_dt = row["start_time"]
    end_dt = row["end_time"]
    if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
        _push_flash(request, "error", "Meeting date data is invalid.")
        return RedirectResponse(url="/meetings", status_code=303)

    attendees_raw = db.execute(
        text(
            """
            SELECT u.id, u.email, ma.status
            FROM meeting_attendees ma
            JOIN users u ON u.id = ma.user_id
            WHERE ma.meeting_id = :meeting_id
            ORDER BY u.email
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings()

    attendees: list[dict[str, Any]] = []
    for attendee in attendees_raw:
        availability_status, conflicts = _availability_summary(
            db,
            user_id=int(attendee["id"]),
            slot_start=start_dt,
            slot_end=end_dt,
            exclude_meeting_id=meeting_id,
        )
        attendees.append(
            {
                "email": attendee["email"],
                "invite_status": attendee["status"],
                "availability_status": availability_status,
                "conflicts": conflicts,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="meeting_detail.html",
        context={"meeting": row, "attendees": attendees, "messages": _pop_flashes(request)},
    )


@router.post("/logout", name="web_logout")
def logout(request: Request):
    request.session.clear()
    _push_flash(request, "success", "Signed out.")
    return RedirectResponse(url="/", status_code=303)


@router.get("/web/auth/google", name="web_auth_google")
def auth_google(request: Request):
    _push_flash(request, "error", "Google OAuth UI flow is not wired in this page yet.")
    return RedirectResponse(url="/", status_code=303)


@router.get("/web/auth/microsoft", name="web_auth_microsoft")
def auth_microsoft(request: Request):
    _push_flash(request, "error", "Microsoft OAuth flow is not wired yet.")
    return RedirectResponse(url="/", status_code=303)
