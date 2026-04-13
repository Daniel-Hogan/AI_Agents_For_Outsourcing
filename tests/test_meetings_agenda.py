from sqlalchemy import text

from app.db.session import SessionLocal


class AgendaTravelWarningService:
    def evaluate_meeting(self, db, *, user, meeting, persist=False):
        return []

    def enrich_meetings(self, db, *, user, meetings, persist=False):
        enriched = []
        for meeting in meetings:
            item = dict(meeting)
            if item["title"] == "Site Visit":
                item["travel_warnings"] = [
                    {
                        "severity": "caution",
                        "message": "Tight travel window before this meeting.",
                        "travel_minutes": 45,
                        "distance_miles": 23.4,
                        "available_minutes": 50,
                        "origin_source": "previous_meeting",
                        "origin_location": "Morning Sync",
                        "destination_location": item.get("location"),
                    }
                ]
            else:
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


def _create_meeting(client, *, title: str, start_time: str, end_time: str, location: str = "") -> None:
    response = client.post(
        "/meetings/create",
        data={
            "title": title,
            "location": location,
            "location_raw": location,
            "location_latitude": "",
            "location_longitude": "",
            "start_time": start_time,
            "end_time": end_time,
            "invitees": "",
            "q": "",
            "status": "",
            "mine": "",
            "day": "2030-01-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_meetings_page_renders_agenda_cards_for_selected_day(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: AgendaTravelWarningService())

    _create_meeting(
        client,
        title="Morning Sync",
        location="Campus Center",
        start_time="2030-01-01T09:00",
        end_time="2030-01-01T10:00",
    )
    _create_meeting(
        client,
        title="Site Visit",
        location="Boston Office",
        start_time="2030-01-01T13:00",
        end_time="2030-01-01T14:00",
    )

    response = client.get("/meetings?day=2030-01-01")

    assert response.status_code == 200, response.text
    assert "Agenda View" in response.text
    assert "Tuesday, January 1, 2030" in response.text
    assert "2 meetings" in response.text
    assert "1 travel warning" in response.text
    assert "No location provided" not in response.text
    assert "45 min travel" in response.text
    assert "Site Visit" in response.text
    assert "Morning Sync" in response.text
    assert response.text.index("Morning Sync") < response.text.index("Site Visit")
    assert 'name="day" value="2030-01-01"' in response.text


def test_meetings_page_shows_agenda_empty_state_for_day_without_meetings(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: AgendaTravelWarningService())

    response = client.get("/meetings?day=2030-01-02")

    assert response.status_code == 200, response.text
    assert "No meetings scheduled for Wednesday, January 2, 2030" in response.text
    assert "create a meeting above to start filling this agenda" in response.text


def test_meetings_page_uses_selected_day_for_seeded_render_context(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: AgendaTravelWarningService())

    _create_meeting(
        client,
        title="Coffee Chat",
        location="",
        start_time="2030-01-01T11:00",
        end_time="2030-01-01T11:30",
    )

    response = client.get("/meetings?day=2030-01-01")

    assert response.status_code == 200, response.text
    assert "No location provided" in response.text
    assert "No travel warning for this meeting." in response.text

    db = SessionLocal()
    try:
        stored = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM meetings
                WHERE title = 'Coffee Chat'
                """
            )
        ).scalar_one()
        assert stored == 1
    finally:
        db.close()
