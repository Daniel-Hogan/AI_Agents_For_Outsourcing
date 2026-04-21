from pydantic import BaseModel
from datetime import time

class TimeSlotCreate(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time

class TimeSlotResponse(TimeSlotCreate):
    id: int

    class Config:
        from_attributes = True