from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.travel import LocationSuggestionData


class DummyTravelWarningService:
    def evaluate_meeting(self, db, *, user, meeting, persist=False):
        return []

    def enrich_meetings(self, db, *, user, meetings, persist=False):
        enriched = []
        for meeting in meetings:
            item = dict(meeting)
            item["travel_warnings"] = []
            enriched.append(item)
        return enriched


def _register_user(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
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


def test_locations_autocomplete_returns_suggestions(client, monkeypatch):
    _register_user(client)
    _web_login(client)

    monkeypatch.setattr(
        "app.web.routes.autocomplete_locations",
        lambda query, size=5: [
            LocationSuggestionData(
                label="Boston, Massachusetts, United States",
                latitude=42.3601,
                longitude=-71.0589,
            )
        ],
    )

    response = client.get("/locations/autocomplete?q=bos")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["suggestions"][0]["label"] == "Boston, Massachusetts, United States"
    assert payload["suggestions"][0]["latitude"] == 42.3601


def test_meetings_page_includes_enhanced_datetime_controls(client):
    _register_user(client)
    _web_login(client)

    response = client.get("/meetings")

    assert response.status_code == 200, response.text
    assert "data-datetime-picker" in response.text
    assert "15-minute increments" in response.text


def test_meeting_create_stores_selected_location_coordinates(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: DummyTravelWarningService())

    response = client.post(
        "/meetings/create",
        data={
            "title": "Site Visit",
            "location": "Boston, Massachusetts, United States",
            "location_raw": "bos",
            "location_latitude": "42.3601",
            "location_longitude": "-71.0589",
            "start_time": "2030-01-01T10:00",
            "end_time": "2030-01-01T11:00",
            "invitees": "",
            "q": "",
            "status": "",
            "mine": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text

    db = SessionLocal()
    try:
        meeting = db.execute(
            text(
                """
                SELECT location, location_raw, location_latitude, location_longitude
                FROM meetings
                WHERE title = 'Site Visit'
                """
            )
        ).mappings().one()
        assert meeting["location"] == "Boston, Massachusetts, United States"
        assert meeting["location_raw"] == "bos"
        assert float(meeting["location_latitude"]) == 42.3601
        assert float(meeting["location_longitude"]) == -71.0589
    finally:
        db.close()


def test_meeting_create_keeps_unresolved_optional_location_text(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: DummyTravelWarningService())

    response = client.post(
        "/meetings/create",
        data={
            "title": "Coffee Chat",
            "location": "Lobby maybe",
            "location_raw": "Lobby maybe",
            "location_latitude": "",
            "location_longitude": "",
            "start_time": "2030-01-01T12:00",
            "end_time": "2030-01-01T13:00",
            "invitees": "",
            "q": "",
            "status": "",
            "mine": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text

    db = SessionLocal()
    try:
        meeting = db.execute(
            text(
                """
                SELECT location, location_raw, location_latitude, location_longitude
                FROM meetings
                WHERE title = 'Coffee Chat'
                """
            )
        ).mappings().one()
        assert meeting["location"] == "Lobby maybe"
        assert meeting["location_raw"] == "Lobby maybe"
        assert meeting["location_latitude"] is None
        assert meeting["location_longitude"] is None
    finally:
        db.close()
