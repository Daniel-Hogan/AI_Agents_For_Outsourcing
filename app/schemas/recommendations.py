from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class RecommendationRequest(BaseModel):
    attendee_emails: list[EmailStr] = Field(default_factory=list)
    start_date: date
    end_date: date
    duration_minutes: int = Field(ge=15, le=480)
    max_results: int = Field(default=3, ge=1, le=10)
    include_organizer: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 31:
            raise ValueError("date range cannot exceed 31 days")
        if not self.include_organizer and not self.attendee_emails:
            raise ValueError("at least one attendee is required when include_organizer is false")
        return self


class RecommendationParticipant(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str


class RecommendationSlot(BaseModel):
    rank: int
    start_time: datetime
    end_time: datetime
    available_attendee_count: int
    conflicted_attendee_count: int
    score: int
    reason: str


class RecommendationResponse(BaseModel):
    attendees: list[RecommendationParticipant]
    duration_minutes: int
    recommendations: list[RecommendationSlot]
