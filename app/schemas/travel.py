from typing import Literal

from pydantic import BaseModel


OriginSource = Literal["previous_meeting", "user_default", "org_default", "unknown"]
TravelWarningSeverity = Literal["info", "caution", "critical"]


class TravelWarning(BaseModel):
    severity: TravelWarningSeverity
    message: str
    travel_minutes: int | None = None
    distance_km: float | None = None
    distance_miles: float | None = None
    available_minutes: int | None = None
    buffer_minutes: int | None = None
    origin_source: OriginSource = "unknown"
    origin_location: str | None = None
    destination_location: str | None = None


class LocationSuggestion(BaseModel):
    label: str
    latitude: float
    longitude: float
