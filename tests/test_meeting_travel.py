from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import User
from app.services.travel import (
    Coordinates,
    GeocodedLocation,
    TravelEstimate,
    TravelWarningService,
    evaluate_travel_warning,
    resolve_origin_location,
)


class FakeTravelProvider:
    def __init__(
        self,
        *,
        geocodes: dict[str, Coordinates] | None = None,
        estimate: TravelEstimate | None = None,
    ) -> None:
        self.geocodes = geocodes or {}
        self.estimate = estimate

    def geocode_location(self, location: str) -> GeocodedLocation | None:
        coordinates = self.geocodes.get(location)
        if coordinates is None:
            return None
        return GeocodedLocation(label=location, coordinates=coordinates)

    def get_travel_estimate(self, origin: Coordinates, destination: Coordinates) -> TravelEstimate | None:
        return self.estimate


def _register_user(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
    client.cookies.clear()
    response = client.post(
        "/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text


def _web_login(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _load_user(db, email: str = "ada@example.com") -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    return user


def _create_calendar(db, *, user_id: int) -> int:
    return int(
        db.execute(
            text(
                """
                INSERT INTO calendars (name, owner_type, owner_id)
                VALUES (:name, 'user', :owner_id)
                RETURNING id
                """
            ),
            {"name": f"user-{user_id}-calendar", "owner_id": user_id},
        ).scalar_one()
    )


def _create_meeting(
    db,
    *,
    calendar_id: int,
    title: str,
    start_time: datetime,
    end_time: datetime,
    location: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> int:
    return int(
        db.execute(
            text(
                """
                INSERT INTO meetings (
                    calendar_id,
                    title,
                    location,
                    location_latitude,
                    location_longitude,
                    start_time,
                    end_time,
                    capacity,
                    setup_minutes,
                    cleanup_minutes
                )
                VALUES (
                    :calendar_id,
                    :title,
                    :location,
                    :latitude,
                    :longitude,
                    :start_time,
                    :end_time,
                    NULL,
                    0,
                    0
                )
                RETURNING id
                """
            ),
            {
                "calendar_id": calendar_id,
                "title": title,
                "location": location,
                "latitude": latitude,
                "longitude": longitude,
                "start_time": start_time,
                "end_time": end_time,
            },
        ).scalar_one()
    )


def _meeting_payload(db, meeting_id: int) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                id,
                title,
                location,
                location_latitude,
                location_longitude,
                start_time,
                end_time
            FROM meetings
            WHERE id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().one()
    meeting = dict(row)
    meeting["is_relevant_to_user"] = True
    return meeting


def test_resolve_origin_uses_previous_meeting_location(client):
    _register_user(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Morning standup",
            start_time=base_day + timedelta(hours=9),
            end_time=base_day + timedelta(hours=10),
            location="Boston Office",
            latitude=42.3601,
            longitude=-71.0589,
        )
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Customer visit",
            start_time=base_day + timedelta(hours=11),
            end_time=base_day + timedelta(hours=12),
            location="New York Office",
            latitude=40.7128,
            longitude=-74.0060,
        )
        db.commit()

        origin = resolve_origin_location(db, user=user, meeting=_meeting_payload(db, current_meeting_id))

        assert origin is not None
        assert origin.source == "previous_meeting"
        assert origin.location == "Boston Office"
    finally:
        db.close()


def test_resolve_origin_falls_back_to_user_then_org_default(client, monkeypatch):
    _register_user(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Field visit",
            start_time=base_day + timedelta(hours=13),
            end_time=base_day + timedelta(hours=14),
            location="Client Site",
            latitude=39.9526,
            longitude=-75.1652,
        )
        user.default_location = "Home Office"
        user.default_location_latitude = 41.8781
        user.default_location_longitude = -87.6298
        db.commit()
        db.refresh(user)

        meeting = _meeting_payload(db, current_meeting_id)
        user_origin = resolve_origin_location(db, user=user, meeting=meeting)
        assert user_origin is not None
        assert user_origin.source == "user_default"
        assert user_origin.location == "Home Office"

        user.default_location = None
        user.default_location_latitude = None
        user.default_location_longitude = None
        db.commit()
        db.refresh(user)

        monkeypatch.setattr(settings, "organization_default_location", "HQ")
        monkeypatch.setattr(settings, "organization_default_location_latitude", 34.0522)
        monkeypatch.setattr(settings, "organization_default_location_longitude", -118.2437)

        org_origin = resolve_origin_location(db, user=user, meeting=meeting)
        assert org_origin is not None
        assert org_origin.source == "org_default"
        assert org_origin.location == "HQ"
    finally:
        db.close()


def test_critical_warning_when_travel_exceeds_gap(client):
    _register_user(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Warehouse",
            start_time=base_day + timedelta(hours=9),
            end_time=base_day + timedelta(hours=10),
            location="Warehouse",
            latitude=42.0,
            longitude=-71.0,
        )
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Airport pickup",
            start_time=base_day + timedelta(hours=10, minutes=20),
            end_time=base_day + timedelta(hours=11),
            location="Airport",
            latitude=40.0,
            longitude=-73.0,
        )
        db.commit()

        warnings = evaluate_travel_warning(
            db,
            user=user,
            meeting=_meeting_payload(db, current_meeting_id),
            provider=FakeTravelProvider(
                estimate=TravelEstimate(distance_meters=80467.0, duration_seconds=35 * 60),
            ),
        )

        critical = next(w for w in warnings if w.severity == "critical")
        assert critical.travel_minutes == 35
        assert critical.available_minutes == 20
        assert critical.origin_source == "previous_meeting"
    finally:
        db.close()


def test_no_warning_when_enough_time_exists(client):
    _register_user(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Town Hall",
            start_time=base_day + timedelta(hours=8),
            end_time=base_day + timedelta(hours=9),
            location="Town Hall",
            latitude=41.0,
            longitude=-72.0,
        )
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Partner Lunch",
            start_time=base_day + timedelta(hours=11),
            end_time=base_day + timedelta(hours=12),
            location="Partner HQ",
            latitude=41.5,
            longitude=-72.5,
        )
        db.commit()

        warnings = evaluate_travel_warning(
            db,
            user=user,
            meeting=_meeting_payload(db, current_meeting_id),
            provider=FakeTravelProvider(
                estimate=TravelEstimate(distance_meters=16093.0, duration_seconds=20 * 60),
            ),
        )

        assert warnings == []
    finally:
        db.close()


def test_missing_location_data_is_handled_gracefully(client, monkeypatch):
    _register_user(client)
    monkeypatch.setattr(settings, "organization_default_location", None)
    monkeypatch.setattr(settings, "organization_default_location_latitude", None)
    monkeypatch.setattr(settings, "organization_default_location_longitude", None)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Desk time",
            start_time=base_day + timedelta(hours=9),
            end_time=base_day + timedelta(hours=10),
            location=None,
        )
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Undisclosed meeting",
            start_time=base_day + timedelta(hours=11),
            end_time=base_day + timedelta(hours=12),
            location=None,
        )
        db.commit()

        warnings = evaluate_travel_warning(
            db,
            user=user,
            meeting=_meeting_payload(db, current_meeting_id),
            provider=FakeTravelProvider(),
        )

        assert warnings == []
    finally:
        db.close()


def test_fallback_estimate_generates_warning_when_live_routing_is_unavailable(client):
    _register_user(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Lunch",
            start_time=base_day + timedelta(hours=12, minutes=30),
            end_time=base_day + timedelta(hours=13, minutes=30),
            location="1 Castle Point on Hudson, Hoboken, NJ, USA",
            latitude=40.745008,
            longitude=-74.024085,
        )
        current_meeting_id = _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Trip to disney",
            start_time=base_day + timedelta(hours=14, minutes=30),
            end_time=base_day + timedelta(hours=15, minutes=30),
            location="Orlando, FL, USA",
            latitude=28.41959,
            longitude=-81.293691,
        )
        db.commit()

        warnings = evaluate_travel_warning(
            db,
            user=user,
            meeting=_meeting_payload(db, current_meeting_id),
            provider=FakeTravelProvider(estimate=None),
        )

        severities = [warning.severity for warning in warnings]
        assert "info" in severities
        assert "critical" in severities
        critical = next(w for w in warnings if w.severity == "critical")
        assert critical.available_minutes == 60
        assert critical.travel_minutes is not None
        assert critical.travel_minutes > 60
    finally:
        db.close()


def test_meetings_page_renders_travel_warning(client, monkeypatch):
    _register_user(client)
    _web_login(client)

    db = SessionLocal()
    try:
        user = _load_user(db)
        calendar_id = _create_calendar(db, user_id=user.id)
        base_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Factory visit",
            start_time=base_day + timedelta(hours=9),
            end_time=base_day + timedelta(hours=10),
            location="Factory",
            latitude=42.0,
            longitude=-71.0,
        )
        _create_meeting(
            db,
            calendar_id=calendar_id,
            title="Board review",
            start_time=base_day + timedelta(hours=10, minutes=25),
            end_time=base_day + timedelta(hours=11, minutes=10),
            location="Board Room",
            latitude=40.0,
            longitude=-73.0,
        )
        db.commit()

        monkeypatch.setattr(
            "app.web.routes.get_travel_warning_service",
            lambda: TravelWarningService(
                provider=FakeTravelProvider(
                    estimate=TravelEstimate(distance_meters=64373.0, duration_seconds=30 * 60),
                ),
                buffer_minutes=settings.travel_warning_buffer_minutes,
                tight_window_minutes=settings.travel_warning_tight_window_minutes,
            ),
        )

        response = client.get("/meetings")

        assert response.status_code == 200, response.text
        assert "Board review" in response.text
        assert "Travel time from the previous stop likely makes this meeting late." in response.text
        assert "30 min travel" in response.text
    finally:
        db.close()
