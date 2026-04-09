from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class MeetingAttendeeSummary(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str
    status: Literal["invited", "accepted", "declined", "maybe"]


class MeetingBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    color: str | None = "#3498db"
    start_time: datetime
    end_time: datetime
    capacity: int | None = Field(default=None, ge=1)
    setup_minutes: int = Field(default=0, ge=0)
    cleanup_minutes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class MeetingCreate(MeetingBase):
    attendee_emails: list[EmailStr] = Field(default_factory=list)


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    location: str | None = None
    color: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    capacity: int | None = Field(default=None, ge=1)
    setup_minutes: int | None = Field(default=None, ge=0)
    cleanup_minutes: int | None = Field(default=None, ge=0)
    attendee_emails: list[EmailStr] | None = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class MeetingRsvpUpdate(BaseModel):
    status: Literal["accepted", "declined", "maybe"]


class MeetingResponse(BaseModel):
    id: int
    calendar_id: int
    title: str
    description: str | None
    location: str | None
    color: str
    start_time: datetime
    end_time: datetime
    capacity: int | None
    setup_minutes: int
    cleanup_minutes: int
    status: Literal["proposed", "confirmed", "cancelled"] | str
    created_by: int | None
    created_at: datetime
    is_organizer: bool
    current_user_status: Literal["invited", "accepted", "declined", "maybe"] | None
    attendee_count: int
    accepted_count: int
    declined_count: int
    maybe_count: int
    invited_count: int
    attendees: list[MeetingAttendeeSummary]
