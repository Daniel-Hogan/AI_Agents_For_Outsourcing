from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_db
from app.db.calendars import get_or_create_user_calendar
from app.models import User
from app.schemas.meetings import MeetingCreate, MeetingResponse, MeetingRsvpUpdate, MeetingUpdate
from app.schemas.recommendations import RecommendationRequest, RecommendationResponse
from app.services.recommendations import recommend_common_slots


router = APIRouter(prefix="/meetings", tags=["meetings"])


def _normalize_emails(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for email in emails:
        value = email.strip().lower()
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized


def _resolve_attendee_user_ids(db: Session, attendee_emails: list[str]) -> list[int]:
    emails = _normalize_emails(attendee_emails)
    if not emails:
        return []

    query = text(
        """
        SELECT id, email
        FROM users
        WHERE LOWER(email) IN :emails
        ORDER BY email
        """
    ).bindparams(bindparam("emails", expanding=True))
    rows = db.execute(query, {"emails": emails}).mappings().all()

    found_by_email = {row["email"].lower(): row["id"] for row in rows}
    missing = [email for email in emails if email not in found_by_email]
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some attendee emails do not belong to registered users",
                "missing_emails": missing,
            },
        )

    return [found_by_email[email] for email in emails]


def _load_users_by_ids(db: Session, user_ids: list[int]) -> list[dict]:
    if not user_ids:
        return []

    query = text(
        """
        SELECT id, email, first_name, last_name
        FROM users
        WHERE id IN :user_ids
        """
    ).bindparams(bindparam("user_ids", expanding=True))
    rows = db.execute(query, {"user_ids": user_ids}).mappings().all()
    users_by_id = {row["id"]: dict(row) for row in rows}
    return [users_by_id[user_id] for user_id in user_ids if user_id in users_by_id]


def _meeting_access_clause() -> str:
    return "(m.created_by = :user_id OR EXISTS (SELECT 1 FROM meeting_attendees ma2 WHERE ma2.meeting_id = m.id AND ma2.user_id = :user_id))"


def _fetch_meeting_row(meeting_id: int, user_id: int, db: Session):
    meeting = db.execute(
        text(
            f"""
            SELECT
                m.id,
                m.calendar_id,
                m.title,
                m.description,
                m.location,
                COALESCE(m.meeting_type, 'in_person') AS meeting_type,
                CASE 
                WHEN COUNT(ma.user_id) FILTER (WHERE ma.status = 'maybe') > 0
                    THEN '#facc15'
                ELSE COALESCE(m.color, '#3498db')
                END AS color,              
                m.start_time,
                m.end_time,
                m.capacity,
                COALESCE(m.setup_minutes, 0) AS setup_minutes,
                COALESCE(m.cleanup_minutes, 0) AS cleanup_minutes,
                COALESCE(m.status, 'confirmed') AS status,
                m.created_by,
                m.created_at,
                CASE WHEN m.created_by = :user_id THEN TRUE ELSE FALSE END AS is_organizer,
                me.status AS current_user_status,
                COUNT(ma.user_id) AS attendee_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'accepted') AS accepted_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'declined') AS declined_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'maybe') AS maybe_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'invited') AS invited_count
            FROM meetings m
            LEFT JOIN meeting_attendees ma ON ma.meeting_id = m.id
            LEFT JOIN meeting_attendees me ON me.meeting_id = m.id AND me.user_id = :user_id
            WHERE m.id = :meeting_id AND {_meeting_access_clause()}
            GROUP BY m.id, me.status
            """
        ),
        {"meeting_id": meeting_id, "user_id": user_id},
    ).mappings().first()

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return dict(meeting)


def _fetch_attendees(meeting_id: int, db: Session) -> list[dict]:
    attendees = db.execute(
        text(
            """
            SELECT
                ma.user_id,
                u.email,
                u.first_name,
                u.last_name,
                ma.status
            FROM meeting_attendees ma
            JOIN users u ON u.id = ma.user_id
            WHERE ma.meeting_id = :meeting_id
            ORDER BY
                CASE ma.status
                    WHEN 'accepted' THEN 0
                    WHEN 'maybe' THEN 1
                    WHEN 'invited' THEN 2
                    ELSE 3
                END,
                u.email ASC
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().all()
    return [dict(row) for row in attendees]


def _serialize_meeting(meeting_id: int, user_id: int, db: Session) -> dict:
    meeting = _fetch_meeting_row(meeting_id, user_id, db)
    meeting["attendees"] = _fetch_attendees(meeting_id, db)
    return meeting


def _replace_attendees(meeting_id: int, organizer_id: int, attendee_user_ids: list[int], db: Session) -> None:
    desired_ids = {organizer_id, *attendee_user_ids}
    existing_rows = db.execute(
        text(
            """
            SELECT user_id, status
            FROM meeting_attendees
            WHERE meeting_id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().all()
    existing = {row["user_id"]: row["status"] for row in existing_rows}

    for user_id in list(existing):
        if user_id not in desired_ids:
            db.execute(
                text(
                    "DELETE FROM meeting_attendees WHERE meeting_id = :meeting_id AND user_id = :user_id"
                ),
                {"meeting_id": meeting_id, "user_id": user_id},
            )

    for user_id in desired_ids:
        desired_status = "accepted" if user_id == organizer_id else existing.get(user_id, "invited")
        if user_id in existing:
            db.execute(
                text(
                    """
                    UPDATE meeting_attendees
                    SET status = :status
                    WHERE meeting_id = :meeting_id AND user_id = :user_id
                    """
                ),
                {"meeting_id": meeting_id, "user_id": user_id, "status": desired_status},
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO meeting_attendees (meeting_id, user_id, status)
                    VALUES (:meeting_id, :user_id, :status)
                    """
                ),
                {"meeting_id": meeting_id, "user_id": user_id, "status": desired_status},
            )


def _validate_meeting_window(start_time, end_time) -> None:
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")


@router.get("/", response_model=list[MeetingResponse])
def list_meetings(
    include_cancelled: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = ""
    if not include_cancelled:
        filters = " AND COALESCE(m.status, 'confirmed') <> 'cancelled'"

    meetings = db.execute(
        text(
            f"""
            SELECT
                m.id,
                m.calendar_id,
                m.title,
                m.description,
                m.location,
                COALESCE(m.meeting_type, 'in_person') AS meeting_type,
                CASE 
                WHEN COUNT(ma.user_id) FILTER (WHERE ma.status = 'maybe') > 0
                    THEN '#facc15'
                ELSE COALESCE(m.color, '#3498db')
                END AS color,
                m.start_time,
                m.end_time,
                m.capacity,
                COALESCE(m.setup_minutes, 0) AS setup_minutes,
                COALESCE(m.cleanup_minutes, 0) AS cleanup_minutes,
                COALESCE(m.status, 'confirmed') AS status,
                m.created_by,
                m.created_at,
                CASE WHEN m.created_by = :user_id THEN TRUE ELSE FALSE END AS is_organizer,
                me.status AS current_user_status,
                COUNT(ma.user_id) AS attendee_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'accepted') AS accepted_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'declined') AS declined_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'maybe') AS maybe_count,
                COUNT(ma.user_id) FILTER (WHERE ma.status = 'invited') AS invited_count
            FROM meetings m
            LEFT JOIN meeting_attendees ma ON ma.meeting_id = m.id
            LEFT JOIN meeting_attendees me ON me.meeting_id = m.id AND me.user_id = :user_id
            WHERE {_meeting_access_clause()}{filters}
            GROUP BY m.id, me.status
            ORDER BY m.start_time ASC, m.id ASC
            """
        ),
        {"user_id": current_user.id},
    ).mappings().all()

    items = []
    for meeting in meetings:
        item = dict(meeting)
        item["attendees"] = _fetch_attendees(item["id"], db)
        items.append(item)
    return items


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_meeting(meeting_id, current_user.id, db)


@router.post("/", response_model=MeetingResponse)
def create_meeting(
    payload: MeetingCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_meeting_window(payload.start_time, payload.end_time)
    calendar_id = get_or_create_user_calendar(current_user.id, db)
    attendee_user_ids = _resolve_attendee_user_ids(db, [str(email) for email in payload.attendee_emails])

    created = db.execute(
        text(
            """
            INSERT INTO meetings (
                calendar_id,
                title,
                description,
                location,
                meeting_type,
                color,
                start_time,
                end_time,
                capacity,
                setup_minutes,
                cleanup_minutes,
                status,
                created_by
            )
            VALUES (
                :calendar_id,
                :title,
                :description,
                :location,
                :meeting_type,
                :color,
                :start_time,
                :end_time,
                :capacity,
                :setup_minutes,
                :cleanup_minutes,
                'confirmed',
                :created_by
            )
            RETURNING id
            """
        ),
        {
            "calendar_id": calendar_id,
            "title": payload.title.strip(),
            "description": payload.description.strip() if payload.description else None,
            "location": payload.location.strip() if payload.location else None,
            "meeting_type": payload.meeting_type,
            "color": payload.color or "#3498db",
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "capacity": payload.capacity,
            "setup_minutes": payload.setup_minutes,
            "cleanup_minutes": payload.cleanup_minutes,
            "created_by": current_user.id,
        },
    ).fetchone()

    meeting_id = created[0]
    _replace_attendees(meeting_id, current_user.id, attendee_user_ids, db)
    db.commit()
    return _serialize_meeting(meeting_id, current_user.id, db)


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text("SELECT id, created_by, start_time, end_time FROM meetings WHERE id = :meeting_id"),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if existing["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can update this meeting")

    updates = payload.model_dump(exclude_unset=True)
    attendee_emails = updates.pop("attendee_emails", None)

    start_time = updates.get("start_time", existing["start_time"])
    end_time = updates.get("end_time", existing["end_time"])
    _validate_meeting_window(start_time, end_time)

    if updates:
        allowed_fields = {
            "title", "description", "location", "meeting_type", "color",
            "start_time", "end_time", "capacity", "setup_minutes", "cleanup_minutes",
        }
        filtered_updates = {
            key: (value.strip() if isinstance(value, str) and key in {"title", "description", "location"} else value)
            for key, value in updates.items()
            if key in allowed_fields
        }
        set_clause = ", ".join(f"{field} = :{field}" for field in filtered_updates)
        filtered_updates["meeting_id"] = meeting_id
        db.execute(
            text(f"UPDATE meetings SET {set_clause} WHERE id = :meeting_id"),
            filtered_updates,
        )

    if attendee_emails is not None:
        attendee_user_ids = _resolve_attendee_user_ids(db, [str(email) for email in attendee_emails])
        _replace_attendees(meeting_id, current_user.id, attendee_user_ids, db)

    db.commit()
    return _serialize_meeting(meeting_id, current_user.id, db)


@router.post("/{meeting_id}/cancel", response_model=MeetingResponse)
def cancel_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text("SELECT id, created_by FROM meetings WHERE id = :meeting_id"),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if existing["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can cancel this meeting")

    db.execute(
        text("UPDATE meetings SET status = 'cancelled' WHERE id = :meeting_id"),
        {"meeting_id": meeting_id},
    )
    db.commit()
    return _serialize_meeting(meeting_id, current_user.id, db)


@router.post("/recommendations", response_model=RecommendationResponse)
def get_meeting_recommendations(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participant_ids = _resolve_attendee_user_ids(db, [str(email) for email in payload.attendee_emails])
    if payload.include_organizer and current_user.id not in participant_ids:
        participant_ids = [current_user.id, *participant_ids]

    if not participant_ids:
        raise HTTPException(status_code=400, detail="At least one participant is required")

    participant_rows = _load_users_by_ids(db, participant_ids)
    recommendations = recommend_common_slots(
        user_ids=participant_ids,
        start_date=payload.start_date,
        end_date=payload.end_date,
        duration_minutes=payload.duration_minutes,
        max_results=payload.max_results,
        db=db,
    )

    return {
        "attendees": [
            {
                "user_id": row["id"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
            }
            for row in participant_rows
        ],
        "duration_minutes": payload.duration_minutes,
        "recommendations": recommendations,
    }


@router.post("/{meeting_id}/rsvp", response_model=MeetingResponse)
def update_rsvp(
    meeting_id: int,
    payload: MeetingRsvpUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.execute(
        text(
            "SELECT id, COALESCE(status, 'confirmed') AS status, created_by FROM meetings WHERE id = :meeting_id"
        ),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled meetings cannot be updated")

    attendee = db.execute(
        text(
            """
            SELECT meeting_id FROM meeting_attendees
            WHERE meeting_id = :meeting_id AND user_id = :user_id
            """
        ),
        {"meeting_id": meeting_id, "user_id": current_user.id},
    ).fetchone()
    if attendee is None:
        raise HTTPException(status_code=403, detail="You are not invited to this meeting")

    db.execute(
        text(
            """
            UPDATE meeting_attendees
            SET status = :status
            WHERE meeting_id = :meeting_id AND user_id = :user_id
            """
        ),
        {"meeting_id": meeting_id, "user_id": current_user.id, "status": payload.status},
    )

    db.commit()
    return _serialize_meeting(meeting_id, current_user.id, db)

@router.post("/{meeting_id}/reschedule-suggestions", response_model=RecommendationResponse)
def get_reschedule_suggestions(
    meeting_id: int,
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = db.execute(
        text("SELECT id, created_by, start_time, end_time FROM meetings WHERE id = :meeting_id"),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Only the organizer can get reschedule suggestions")

    participant_ids = _resolve_attendee_user_ids(db, [str(email) for email in payload.attendee_emails])
    if payload.include_organizer and current_user.id not in participant_ids:
        participant_ids = [current_user.id, *participant_ids]

    if not participant_ids:
        raise HTTPException(status_code=400, detail="At least one participant is required")

    participant_rows = _load_users_by_ids(db, participant_ids)
    recommendations = recommend_common_slots(
        user_ids=participant_ids,
        start_date=payload.start_date,
        end_date=payload.end_date,
        duration_minutes=payload.duration_minutes,
        max_results=payload.max_results,
        db=db,
        exclude_meeting_id=meeting_id,
    )

    return {
        "attendees": [
            {
                "user_id": row["id"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
            }
            for row in participant_rows
        ],
        "duration_minutes": payload.duration_minutes,
        "recommendations": recommendations,
    }

@router.get("/{meeting_id}/availability")
def get_availability(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meeting = _fetch_meeting_row(meeting_id, current_user.id, db)

    attendees = db.execute(
        text("""
            SELECT user_id, status
            FROM meeting_attendees
            WHERE meeting_id = :meeting_id
        """),
        {"meeting_id": meeting_id},
    ).mappings().all()

    return {
        "start_time": meeting["start_time"],
        "end_time": meeting["end_time"],
        "attendees": attendees,
    }
