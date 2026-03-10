from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.api.deps import get_current_user, get_db
from app.models import User

router = APIRouter(prefix="/calendar", tags=["calendar"])


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_user_calendar(user_id: int, db: Session) -> int:
    """Get the user's personal calendar id, creating one if it doesn't exist."""
    result = db.execute(text("""
        SELECT c.id FROM calendars c
        JOIN user_calendars uc ON c.id = uc.calendar_id
        WHERE uc.user_id = :user_id AND c.owner_type = 'user'
        LIMIT 1
    """), {"user_id": user_id}).fetchone()

    if result:
        return result[0]

    # Create a new calendar for the user
    new_cal = db.execute(text("""
        INSERT INTO calendars (name, owner_type, owner_id)
        VALUES (:name, 'user', :owner_id)
        RETURNING id
    """), {"name": "My Calendar", "owner_id": user_id}).fetchone()

    db.execute(text("""
        INSERT INTO user_calendars (user_id, calendar_id)
        VALUES (:user_id, :calendar_id)
    """), {"user_id": user_id, "calendar_id": new_cal[0]})

    db.commit()
    return new_cal[0]


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events")
def get_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all events for the current user's calendar."""
    calendar_id = get_or_create_user_calendar(current_user.id, db)

    events = db.execute(text("""
        SELECT id, title, location, color, start_time, end_time
        FROM meetings
        WHERE calendar_id = :calendar_id
        ORDER BY start_time ASC
    """), {"calendar_id": calendar_id}).mappings().all()

    return [dict(e) for e in events]


@router.post("/events")
def create_event(
    payload: EventCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new event in the user's calendar."""
    calendar_id = get_or_create_user_calendar(current_user.id, db)

    result = db.execute(text("""
        INSERT INTO meetings (calendar_id, title, location, color, start_time, end_time)
        VALUES (:calendar_id, :title, :location, :color, :start_time, :end_time)
        RETURNING id, title, location, color, start_time, end_time
    """), {
        "calendar_id": calendar_id,
        "title": payload.title,
        "location": payload.location,
        "color": payload.color,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
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

    # Make sure this event belongs to the user
    existing = db.execute(text("""
        SELECT id FROM meetings
        WHERE id = :event_id AND calendar_id = :calendar_id
    """), {"event_id": event_id, "calendar_id": calendar_id}).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["event_id"] = event_id

    result = db.execute(text(f"""
        UPDATE meetings SET {set_clause}
        WHERE id = :event_id
        RETURNING id, title, location, color, start_time, end_time
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