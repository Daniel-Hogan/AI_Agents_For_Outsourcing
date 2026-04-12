from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class MeetingRecommendationRequest(BaseModel):
    attendee_user_ids: list[int] = Field(default_factory=list)
    attendee_emails: list[EmailStr] = Field(default_factory=list)
    window_start: datetime
    window_end: datetime
    duration_minutes: int = Field(gt=0, le=720)
    slot_interval_minutes: int = Field(default=30, gt=0, le=240)
    max_results: int = Field(default=5, gt=0, le=20)
    include_current_user: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        return self


class RecommendationAttendeeBreakdown(BaseModel):
    user_id: int
    email: EmailStr
    state: Literal[
        "busy",
        "available_preferred",
        "available_outside_preference",
        "available_no_preference",
    ]


class MeetingTimeRecommendation(BaseModel):
    start_time: datetime
    end_time: datetime
    score: int
    available_count: int
    busy_count: int
    preferred_count: int
    outside_preference_count: int
    attendee_breakdown: list[RecommendationAttendeeBreakdown]


class MeetingRecommendationResponse(BaseModel):
    attendee_count: int
    window_start: datetime
    window_end: datetime
    duration_minutes: int
    slot_interval_minutes: int
    unresolved_user_ids: list[int]
    unresolved_emails: list[str]
    recommendations: list[MeetingTimeRecommendation]
