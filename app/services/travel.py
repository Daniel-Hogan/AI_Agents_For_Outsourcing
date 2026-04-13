from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User
from app.schemas.travel import OriginSource, TravelWarning


logger = logging.getLogger(__name__)
FALLBACK_TRAVEL_SPEED_KMH = 80.0
FALLBACK_DISTANCE_MULTIPLIER = 1.2


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    label: str
    coordinates: Coordinates


@dataclass(frozen=True, slots=True)
class TravelEstimate:
    distance_meters: float
    duration_seconds: float

    @property
    def distance_km(self) -> float:
        return self.distance_meters / 1000.0

    @property
    def distance_miles(self) -> float:
        return meters_to_miles(self.distance_meters)

    @property
    def travel_minutes(self) -> int:
        return max(1, math.ceil(self.duration_seconds / 60.0))


@dataclass(frozen=True, slots=True)
class ResolvedOrigin:
    source: OriginSource
    location: str
    coordinates: Coordinates
    previous_meeting_end_time: datetime | None = None
    previous_meeting_id: int | None = None


class TravelProvider(Protocol):
    def geocode_location(self, location: str) -> GeocodedLocation | None: ...

    def get_travel_estimate(self, origin: Coordinates, destination: Coordinates) -> TravelEstimate | None: ...

    def autocomplete_locations(self, query: str, *, size: int = 5) -> list["LocationSuggestionData"]: ...


@dataclass(frozen=True, slots=True)
class LocationSuggestionData:
    label: str
    latitude: float
    longitude: float


class OpenRouteServiceProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
        profile: str,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.profile = profile
        self.session = session or requests.Session()

    def geocode_location(self, location: str) -> GeocodedLocation | None:
        try:
            response = self.session.get(
                f"{self.base_url}/geocode/search",
                params={"api_key": self.api_key, "text": location, "size": 1},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            features = payload.get("features") or []
            if not features:
                return None
            feature = features[0]
            coords = ((feature.get("geometry") or {}).get("coordinates")) or []
            if len(coords) < 2:
                return None
            lon = float(coords[0])
            lat = float(coords[1])
            properties = feature.get("properties") or {}
            label = str(properties.get("label") or location).strip() or location.strip()
            return GeocodedLocation(label=label, coordinates=Coordinates(latitude=lat, longitude=lon))
        except (requests.RequestException, TypeError, ValueError) as exc:
            logger.warning("openrouteservice geocoding failed for %s: %s", location, exc)
            return None

    def autocomplete_locations(self, query: str, *, size: int = 5) -> list[LocationSuggestionData]:
        try:
            response = self.session.get(
                f"{self.base_url}/geocode/autocomplete",
                params={
                    "api_key": self.api_key,
                    "text": query,
                    "size": size,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            features = payload.get("features") or []
            suggestions: list[LocationSuggestionData] = []
            for feature in features:
                coords = ((feature.get("geometry") or {}).get("coordinates")) or []
                if len(coords) < 2:
                    continue
                properties = feature.get("properties") or {}
                label = str(properties.get("label") or "").strip()
                if not label:
                    continue
                suggestions.append(
                    LocationSuggestionData(
                        label=label,
                        latitude=float(coords[1]),
                        longitude=float(coords[0]),
                    )
                )
            return suggestions
        except (requests.RequestException, TypeError, ValueError) as exc:
            logger.warning("openrouteservice autocomplete failed for %s: %s", query, exc)
            return []

    def get_travel_estimate(self, origin: Coordinates, destination: Coordinates) -> TravelEstimate | None:
        try:
            response = self.session.post(
                f"{self.base_url}/v2/directions/{self.profile}/json",
                headers={"Authorization": self.api_key},
                json={
                    "coordinates": [
                        [origin.longitude, origin.latitude],
                        [destination.longitude, destination.latitude],
                    ]
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            routes = payload.get("routes") or []
            if not routes:
                return None
            summary = (routes[0] or {}).get("summary") or {}
            distance = float(summary["distance"])
            duration = float(summary["duration"])
            return TravelEstimate(distance_meters=distance, duration_seconds=duration)
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            logger.warning("openrouteservice routing failed: %s", exc)
            return None


class TravelWarningService:
    def __init__(
        self,
        *,
        provider: TravelProvider | None,
        buffer_minutes: int,
        tight_window_minutes: int,
    ) -> None:
        self.provider = provider
        self.buffer_minutes = max(0, buffer_minutes)
        self.tight_window_minutes = max(0, tight_window_minutes)

    def enrich_meetings(
        self,
        db: Session,
        *,
        user: User,
        meetings: list[Mapping[str, Any]],
        persist: bool = False,
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for raw_meeting in meetings:
            meeting = dict(raw_meeting)
            warnings = self.evaluate_meeting(db, user=user, meeting=meeting, persist=persist)
            meeting["travel_warnings"] = [warning.model_dump(mode="python") for warning in warnings]
            enriched.append(meeting)
        return enriched

    def evaluate_meeting(
        self,
        db: Session,
        *,
        user: User,
        meeting: Mapping[str, Any],
        persist: bool = False,
    ) -> list[TravelWarning]:
        if not bool(meeting.get("is_relevant_to_user", False)):
            return []

        start_time = meeting.get("start_time")
        if not isinstance(start_time, datetime):
            return []

        if start_time <= datetime.now(timezone.utc):
            return []

        destination = self._resolve_meeting_destination(db, meeting=meeting, persist=persist)
        if destination is None:
            return []

        origin = resolve_origin_location(
            db,
            user=user,
            meeting=meeting,
            provider=self.provider,
            persist=persist,
        )
        if origin is None:
            return []

        estimate = get_travel_estimate(origin.coordinates, destination.coordinates, provider=self.provider)
        used_fallback_estimate = False
        if estimate is None:
            estimate = get_fallback_travel_estimate(origin.coordinates, destination.coordinates)
            used_fallback_estimate = estimate is not None

        available_minutes = None
        warnings: list[TravelWarning] = []

        if origin.source != "previous_meeting":
            info_message = f"Origin resolved from {origin.source.replace('_', ' ')}."
            if origin.previous_meeting_end_time is None:
                info_message = f"No earlier meeting found that day, so {origin.source.replace('_', ' ')} was used."
            warnings.append(
                build_warning(
                    severity="info",
                    message=info_message,
                    estimate=estimate,
                    available_minutes=None,
                    origin=origin,
                    destination=destination,
                    buffer_minutes=self.buffer_minutes,
                )
            )

        if used_fallback_estimate:
            warnings.append(
                build_warning(
                    severity="info",
                    message="Live routing was unavailable, so this uses an approximate travel estimate.",
                    estimate=estimate,
                    available_minutes=None,
                    origin=origin,
                    destination=destination,
                    buffer_minutes=self.buffer_minutes,
                )
            )

        if origin.previous_meeting_end_time is None or estimate is None:
            return warnings

        available_minutes = max(
            0,
            math.floor((start_time - origin.previous_meeting_end_time).total_seconds() / 60.0),
        )
        required_minutes = estimate.travel_minutes + self.buffer_minutes
        margin_minutes = available_minutes - required_minutes

        if margin_minutes < 0:
            warnings.append(
                build_warning(
                    severity="critical",
                    message="Travel time from the previous stop likely makes this meeting late.",
                    estimate=estimate,
                    available_minutes=available_minutes,
                    origin=origin,
                    destination=destination,
                    buffer_minutes=self.buffer_minutes,
                )
            )
        elif margin_minutes <= self.tight_window_minutes:
            warnings.append(
                build_warning(
                    severity="caution",
                    message="Travel looks possible, but the window is tight.",
                    estimate=estimate,
                    available_minutes=available_minutes,
                    origin=origin,
                    destination=destination,
                    buffer_minutes=self.buffer_minutes,
                )
            )

        return warnings

    def _resolve_meeting_destination(
        self,
        db: Session,
        *,
        meeting: Mapping[str, Any],
        persist: bool,
    ) -> GeocodedLocation | None:
        return _resolve_location_record(
            db,
            location=meeting.get("location"),
            latitude=meeting.get("location_latitude"),
            longitude=meeting.get("location_longitude"),
            provider=self.provider,
            persist=persist,
            persist_target=("meeting", int(meeting["id"])) if meeting.get("id") is not None else None,
        )


def build_warning(
    *,
    severity: str,
    message: str,
    estimate: TravelEstimate | None,
    available_minutes: int | None,
    origin: ResolvedOrigin,
    destination: GeocodedLocation,
    buffer_minutes: int,
) -> TravelWarning:
    return TravelWarning(
        severity=severity,
        message=message,
        travel_minutes=estimate.travel_minutes if estimate else None,
        distance_km=round(estimate.distance_km, 2) if estimate else None,
        distance_miles=round(estimate.distance_miles, 2) if estimate else None,
        available_minutes=available_minutes,
        buffer_minutes=buffer_minutes,
        origin_source=origin.source,
        origin_location=origin.location,
        destination_location=destination.label,
    )


def get_travel_warning_service(provider: TravelProvider | None = None) -> TravelWarningService:
    return TravelWarningService(
        provider=provider if provider is not None else get_travel_provider(),
        buffer_minutes=settings.travel_warning_buffer_minutes,
        tight_window_minutes=settings.travel_warning_tight_window_minutes,
    )


def get_travel_provider() -> TravelProvider | None:
    if not settings.openrouteservice_api_key:
        return None
    return OpenRouteServiceProvider(
        api_key=settings.openrouteservice_api_key,
        base_url=settings.openrouteservice_base_url,
        timeout_seconds=settings.openrouteservice_timeout_seconds,
        profile=settings.openrouteservice_profile,
    )


def geocode_location(location: str, provider: TravelProvider | None = None) -> GeocodedLocation | None:
    location_value = normalize_location_text(location)
    if not location_value:
        return None

    provider_value = provider if provider is not None else get_travel_provider()
    if provider_value is None:
        return None
    return provider_value.geocode_location(location_value)


def calculate_distance_km(origin: Coordinates, destination: Coordinates) -> float:
    radius_km = 6371.0
    lat1 = math.radians(origin.latitude)
    lat2 = math.radians(destination.latitude)
    delta_lat = math.radians(destination.latitude - origin.latitude)
    delta_lon = math.radians(destination.longitude - origin.longitude)

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    arc = 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))
    return radius_km * arc


def get_fallback_travel_estimate(origin: Coordinates, destination: Coordinates) -> TravelEstimate:
    distance_km = calculate_distance_km(origin, destination) * FALLBACK_DISTANCE_MULTIPLIER
    duration_hours = distance_km / FALLBACK_TRAVEL_SPEED_KMH
    duration_seconds = max(60.0, duration_hours * 3600.0)
    return TravelEstimate(distance_meters=distance_km * 1000.0, duration_seconds=duration_seconds)


def get_travel_estimate(
    origin: Coordinates,
    destination: Coordinates,
    *,
    provider: TravelProvider | None = None,
) -> TravelEstimate | None:
    provider_value = provider if provider is not None else get_travel_provider()
    if provider_value is None:
        return None
    return provider_value.get_travel_estimate(origin, destination)


def autocomplete_locations(
    query: str,
    *,
    size: int = 5,
    provider: TravelProvider | None = None,
) -> list[LocationSuggestionData]:
    query_value = normalize_location_text(query)
    if len(query_value) < 3:
        return []

    provider_value = provider if provider is not None else get_travel_provider()
    if provider_value is None:
        return []
    return provider_value.autocomplete_locations(query_value, size=size)


def resolve_origin_location(
    db: Session,
    *,
    user: User,
    meeting: Mapping[str, Any],
    provider: TravelProvider | None = None,
    persist: bool = False,
) -> ResolvedOrigin | None:
    provider_value = provider if provider is not None else get_travel_provider()
    previous_meeting = _load_previous_meeting(db, user_id=user.id, meeting=meeting)
    previous_end_time = None

    if previous_meeting is not None:
        previous_end_time = previous_meeting["end_time"]
        previous_location = _resolve_location_record(
            db,
            location=previous_meeting.get("location"),
            latitude=previous_meeting.get("location_latitude"),
            longitude=previous_meeting.get("location_longitude"),
            provider=provider_value,
            persist=persist,
            persist_target=("meeting", int(previous_meeting["id"])),
        )
        if previous_location is not None:
            return ResolvedOrigin(
                source="previous_meeting",
                location=previous_location.label,
                coordinates=previous_location.coordinates,
                previous_meeting_end_time=previous_end_time,
                previous_meeting_id=int(previous_meeting["id"]),
            )

    user_location = _resolve_location_record(
        db,
        location=user.default_location,
        latitude=user.default_location_latitude,
        longitude=user.default_location_longitude,
        provider=provider_value,
        persist=persist,
        persist_target=("user", user.id),
    )
    if user_location is not None:
        return ResolvedOrigin(
            source="user_default",
            location=user_location.label,
            coordinates=user_location.coordinates,
            previous_meeting_end_time=previous_end_time,
            previous_meeting_id=int(previous_meeting["id"]) if previous_meeting is not None else None,
        )

    org_location = _resolve_org_default_location(db, provider=provider_value, persist=persist)
    if org_location is not None:
        return ResolvedOrigin(
            source="org_default",
            location=org_location.label,
            coordinates=org_location.coordinates,
            previous_meeting_end_time=previous_end_time,
            previous_meeting_id=int(previous_meeting["id"]) if previous_meeting is not None else None,
        )

    return None


def evaluate_travel_warning(
    db: Session,
    *,
    user: User,
    meeting: Mapping[str, Any],
    provider: TravelProvider | None = None,
    persist: bool = False,
) -> list[TravelWarning]:
    service = TravelWarningService(
        provider=provider if provider is not None else get_travel_provider(),
        buffer_minutes=settings.travel_warning_buffer_minutes,
        tight_window_minutes=settings.travel_warning_tight_window_minutes,
    )
    return service.evaluate_meeting(db, user=user, meeting=meeting, persist=persist)


def meters_to_miles(meters: float) -> float:
    return meters * 0.000621371


def normalize_location_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _load_previous_meeting(db: Session, *, user_id: int, meeting: Mapping[str, Any]) -> dict[str, Any] | None:
    meeting_id = meeting.get("id")
    start_time = meeting.get("start_time")
    if meeting_id is None or not isinstance(start_time, datetime):
        return None

    row = db.execute(
        text(
            """
            SELECT
                m.id,
                m.location,
                m.location_latitude,
                m.location_longitude,
                m.start_time,
                m.end_time
            FROM meetings m
            WHERE m.id <> :meeting_id
              AND m.end_time <= :meeting_start
              AND DATE(m.end_time AT TIME ZONE 'UTC') = DATE(:meeting_start AT TIME ZONE 'UTC')
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
            ORDER BY m.end_time DESC, m.id DESC
            LIMIT 1
            """
        ),
        {
            "meeting_id": meeting_id,
            "meeting_start": start_time,
            "user_id": user_id,
        },
    ).mappings().one_or_none()
    return dict(row) if row is not None else None


def _resolve_location_record(
    db: Session,
    *,
    location: Any,
    latitude: Any,
    longitude: Any,
    provider: TravelProvider | None,
    persist: bool,
    persist_target: tuple[str, int] | None,
) -> GeocodedLocation | None:
    location_text = normalize_location_text(location)
    direct_coordinates = _coerce_coordinates(latitude, longitude)
    if direct_coordinates is not None and location_text:
        if persist:
            _upsert_location_cache(db, location_text=location_text, coordinates=direct_coordinates)
        return GeocodedLocation(label=location_text, coordinates=direct_coordinates)

    if not location_text:
        return None

    cached_coordinates = _load_cached_coordinates(db, location_text)
    if cached_coordinates is not None:
        if persist and persist_target is not None:
            _persist_target_coordinates(db, persist_target, location_text, cached_coordinates)
        return GeocodedLocation(label=location_text, coordinates=cached_coordinates)

    geocoded = geocode_location(location_text, provider=provider)
    if geocoded is None:
        return None

    resolved = GeocodedLocation(label=location_text, coordinates=geocoded.coordinates)
    if persist:
        _upsert_location_cache(db, location_text=location_text, coordinates=geocoded.coordinates)
        if persist_target is not None:
            _persist_target_coordinates(db, persist_target, location_text, geocoded.coordinates)

    return resolved


def _resolve_org_default_location(
    db: Session,
    *,
    provider: TravelProvider | None,
    persist: bool,
) -> GeocodedLocation | None:
    coordinates = _coerce_coordinates(
        settings.organization_default_location_latitude,
        settings.organization_default_location_longitude,
    )
    location_text = normalize_location_text(settings.organization_default_location)
    if coordinates is not None and location_text:
        return GeocodedLocation(label=location_text, coordinates=coordinates)
    return _resolve_location_record(
        db,
        location=location_text,
        latitude=None,
        longitude=None,
        provider=provider,
        persist=persist,
        persist_target=None,
    )


def _coerce_coordinates(latitude: Any, longitude: Any) -> Coordinates | None:
    try:
        if latitude is None or longitude is None:
            return None
        return Coordinates(latitude=float(latitude), longitude=float(longitude))
    except (TypeError, ValueError):
        return None


def _cache_key(location_text: str) -> str:
    return normalize_location_text(location_text).lower()


def _load_cached_coordinates(db: Session, location_text: str) -> Coordinates | None:
    row = db.execute(
        text(
            """
            SELECT latitude, longitude
            FROM location_cache
            WHERE location_key = :location_key
            """
        ),
        {"location_key": _cache_key(location_text)},
    ).mappings().one_or_none()
    if row is None:
        return None
    return _coerce_coordinates(row["latitude"], row["longitude"])


def _upsert_location_cache(db: Session, *, location_text: str, coordinates: Coordinates) -> None:
    db.execute(
        text(
            """
            INSERT INTO location_cache (location_key, location_label, latitude, longitude, provider, updated_at)
            VALUES (:location_key, :location_label, :latitude, :longitude, 'openrouteservice', NOW())
            ON CONFLICT (location_key)
            DO UPDATE SET
                location_label = EXCLUDED.location_label,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                provider = EXCLUDED.provider,
                updated_at = NOW()
            """
        ),
        {
            "location_key": _cache_key(location_text),
            "location_label": location_text,
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
        },
    )


def _persist_target_coordinates(
    db: Session,
    persist_target: tuple[str, int],
    location_text: str,
    coordinates: Coordinates,
) -> None:
    target_type, target_id = persist_target
    if target_type == "meeting":
        db.execute(
            text(
                """
                UPDATE meetings
                SET location = :location,
                    location_latitude = :latitude,
                    location_longitude = :longitude
                WHERE id = :target_id
                """
            ),
            {
                "location": location_text,
                "latitude": coordinates.latitude,
                "longitude": coordinates.longitude,
                "target_id": target_id,
            },
        )
        return

    if target_type == "user":
        db.execute(
            text(
                """
                UPDATE users
                SET default_location = :location,
                    default_location_latitude = :latitude,
                    default_location_longitude = :longitude
                WHERE id = :target_id
                """
            ),
            {
                "location": location_text,
                "latitude": coordinates.latitude,
                "longitude": coordinates.longitude,
                "target_id": target_id,
            },
        )
