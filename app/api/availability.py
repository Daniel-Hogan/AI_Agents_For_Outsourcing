from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from app.api.deps import get_current_user, get_db
from app.models import User, TimeSlotPreference
from app.schemas.availability import TimeSlotCreate, TimeSlotResponse

router = APIRouter(prefix="/api/availability", tags=["availability"])

@router.get("/", response_model=List[TimeSlotResponse])
def get_availability(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the current user's weekly availability."""
    return db.execute(
        select(TimeSlotPreference).where(TimeSlotPreference.user_id == current_user.id)
    ).scalars().all()

@router.post("/", response_model=List[TimeSlotResponse])
def update_availability(
    slots: List[TimeSlotCreate],
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    
    #
    db.execute(
        TimeSlotPreference.__table__.delete().where(TimeSlotPreference.user_id == current_user.id)
    )
    

    new_slots = [
        TimeSlotPreference(
            user_id=current_user.id,
            day_of_week=slot.day_of_week,
            start_time=slot.start_time,
            end_time=slot.end_time
        )
        for slot in slots
    ]
    
    if new_slots:
        db.add_all(new_slots)
        
    db.commit()
    
    return db.execute(
        select(TimeSlotPreference).where(TimeSlotPreference.user_id == current_user.id)
    ).scalars().all()
