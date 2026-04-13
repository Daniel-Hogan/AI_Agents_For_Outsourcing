class CalendarTravelWarningService:
    def evaluate_meeting(self, db, *, user, meeting, persist=False):
        return []

    def enrich_meetings(self, db, *, user, meetings, persist=False):
        enriched = []
        for meeting in meetings:
            item = dict(meeting)
            if item["title"] == "Client Review":
                item["travel_warnings"] = [
                    {
                        "severity": "critical",
                        "message": "You likely cannot arrive on time.",
                        "travel_minutes": 90,
                        "distance_miles": 48.2,
                        "available_minutes": 30,
                        "origin_source": "previous_meeting",
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


def test_calendar_page_renders_monthly_grid_and_modal_markup(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: CalendarTravelWarningService())

    _create_meeting(
        client,
        title="Morning Sync",
        location="Campus Center",
        start_time="2030-01-08T09:00",
        end_time="2030-01-08T10:00",
    )
    _create_meeting(
        client,
        title="Client Review",
        location="Boston Office",
        start_time="2030-01-15T13:00",
        end_time="2030-01-15T14:00",
    )

    response = client.get("/calendar?month=2030-01")

    assert response.status_code == 200, response.text
    assert "January 2030" in response.text
    assert "Morning Sync" in response.text
    assert "Client Review" in response.text
    assert "data-calendar-open" in response.text
    assert "data-calendar-modal" in response.text
    assert "data-warning-severity=\"critical\"" in response.text
    assert "Campus Center" in response.text


def test_calendar_page_shows_empty_month_state(client, monkeypatch):
    _register_user(client)
    _web_login(client)
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: CalendarTravelWarningService())

    response = client.get("/calendar?month=2031-02")

    assert response.status_code == 200, response.text
    assert "No meetings scheduled" in response.text
    assert "This month is open." in response.text
