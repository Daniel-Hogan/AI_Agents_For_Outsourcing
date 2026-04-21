from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.api.deps import get_current_user, get_db
from app.db.calendars import get_or_create_user_calendar
from app.models import User

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    color: Optional[str] = "#3498db"

class EventUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    color: Optional[str] = None


class AvailabilityCreate(BaseModel):
    day_of_week: int  # 0=Sunday, 6=Saturday
    start_time: str   # "HH:MM"
    end_time: str     # "HH:MM"

class AvailabilityUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events")
def get_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all events for the current user's calendar.
    Includes:
      1. Meetings the user owns (via calendar_id)
      2. Meetings the user accepted or marked maybe via meeting_attendees
    Excludes cancelled meetings from both sources.
    """
    calendar_id = get_or_create_user_calendar(current_user.id, db)

    events = db.execute(text("""
        SELECT
            m.id,
            m.title,
            m.location,
            CASE
                WHEN COUNT(ma_all.user_id) FILTER (WHERE ma_all.status = 'maybe') > 0
                    THEN '#facc15'
                WHEN COUNT(ma_all.user_id) FILTER (WHERE ma_all.status = 'declined') > 0
                    AND me.status = 'accepted'
                    THEN '#ef4444'
                ELSE COALESCE(m.color, '#3498db')
            END AS color,
            m.start_time,
            m.end_time,
            me.status AS current_user_status
        FROM meetings m
        LEFT JOIN meeting_attendees ma_all ON ma_all.meeting_id = m.id
        LEFT JOIN meeting_attendees me ON me.meeting_id = m.id AND me.user_id = :user_id
        WHERE
            COALESCE(m.status, 'confirmed') <> 'cancelled'
            AND (
                m.calendar_id = :calendar_id
                OR
                EXISTS (
                    SELECT 1 FROM meeting_attendees ma
                    WHERE ma.meeting_id = m.id
                      AND ma.user_id = :user_id
                      AND ma.status IN ('accepted', 'maybe')
                )
            )
        GROUP BY m.id, m.title, m.location, m.color, m.start_time, m.end_time, me.status
        ORDER BY m.start_time ASC
    """), {
        "calendar_id": calendar_id,
        "user_id": current_user.id,
    }).mappings().all()

    return [dict(e) for e in events]


@router.post("/events")
def create_event(
    payload: EventCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new event in the user's calendar."""
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    calendar_id = get_or_create_user_calendar(current_user.id, db)

    result = db.execute(text("""
        INSERT INTO meetings (calendar_id, title, location, color, start_time, end_time, status, created_by)
        VALUES (:calendar_id, :title, :location, :color, :start_time, :end_time, 'confirmed', :created_by)
        RETURNING id, title, location, COALESCE(color, '#3498db') AS color, start_time, end_time
    """), {
        "calendar_id": calendar_id,
        "title": payload.title,
        "location": payload.location,
        "color": payload.color,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "created_by": current_user.id,
    }).fetchone()

    db.commit()
    return dict(result._mapping)


@router.put("/events/{event_id}")
def update_event(
    event_id: int,
    payload: EventUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing event."""
    calendar_id = get_or_create_user_calendar(current_user.id, db)

    existing = db.execute(text("""
        SELECT id FROM meetings
        WHERE id = :event_id AND calendar_id = :calendar_id
    """), {"event_id": event_id, "calendar_id": calendar_id}).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    start_time = updates.get("start_time")
    end_time = updates.get("end_time")
    if start_time is not None or end_time is not None:
        existing_row = db.execute(text("""
            SELECT start_time, end_time FROM meetings WHERE id = :event_id
        """), {"event_id": event_id}).mappings().one()
        if start_time is None:
            start_time = existing_row["start_time"]
        if end_time is None:
            end_time = existing_row["end_time"]
        if end_time <= start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["event_id"] = event_id

    result = db.execute(text(f"""
        UPDATE meetings SET {set_clause}
        WHERE id = :event_id
        RETURNING id, title, location, COALESCE(color, '#3498db') AS color, start_time, end_time
    """), updates).fetchone()

    db.commit()
    return dict(result._mapping)


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an event."""
    calendar_id = get_or_create_user_calendar(current_user.id, db)

    existing = db.execute(text("""
        SELECT id FROM meetings
        WHERE id = :event_id AND calendar_id = :calendar_id
    """), {"event_id": event_id, "calendar_id": calendar_id}).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    db.execute(text("DELETE FROM meetings WHERE id = :event_id"), {"event_id": event_id})
    db.commit()
    return {"message": "Event deleted"}


# ── Availability ──────────────────────────────────────────────────────────────

@router.get("/availability")
def get_availability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the user's availability preferences."""
    slots = db.execute(text("""
        SELECT id, day_of_week, start_time, end_time
        FROM time_slot_preferences
        WHERE user_id = :user_id
        ORDER BY day_of_week, start_time
    """), {"user_id": current_user.id}).mappings().all()

    return [dict(s) for s in slots]


@router.post("/availability")
def create_availability(
    payload: AvailabilityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add an availability slot."""
    if not 0 <= payload.day_of_week <= 6:
        raise HTTPException(status_code=400, detail="day_of_week must be 0-6")

    result = db.execute(text("""
        INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
        VALUES (:user_id, :day_of_week, :start_time, :end_time)
        RETURNING id, day_of_week, start_time, end_time
    """), {
        "user_id": current_user.id,
        "day_of_week": payload.day_of_week,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
    }).fetchone()

    db.commit()
    return dict(result._mapping)


@router.delete("/availability/{slot_id}")
def delete_availability(
    slot_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an availability slot."""
    existing = db.execute(text("""
        SELECT id FROM time_slot_preferences
        WHERE id = :slot_id AND user_id = :user_id
    """), {"slot_id": slot_id, "user_id": current_user.id}).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Slot not found")

    db.execute(text("""
        DELETE FROM time_slot_preferences WHERE id = :slot_id
    """), {"slot_id": slot_id})

    db.commit()
    return {"message": "Availability slot deleted"}
