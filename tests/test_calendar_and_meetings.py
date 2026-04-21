from datetime import date


def register_user(client, *, first_name: str, last_name: str, email: str, password: str = "supersecret123"):
    response = client.post(
        "/auth/register",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def day_index_for(date_string: str) -> int:
    return (date.fromisoformat(date_string).weekday() + 1) % 7


def test_calendar_event_crud(client):
    token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")

    create_response = client.post(
        "/api/calendar/events",
        headers=auth_headers(token),
        json={
            "title": "Design Review",
            "location": "Room 101",
            "color": "#112233",
            "start_time": "2026-03-30T14:00:00Z",
            "end_time": "2026-03-30T15:00:00Z",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["color"] == "#112233"

    list_response = client.get("/api/calendar/events", headers=auth_headers(token))
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Design Review"

    update_response = client.put(
        f"/api/calendar/events/{created['id']}",
        headers=auth_headers(token),
        json={"title": "Updated Review", "color": "#445566"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == "Updated Review"

    delete_response = client.delete(f"/api/calendar/events/{created['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 200, delete_response.text


def test_meeting_lifecycle_and_rsvp(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    attendee_token = register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Sprint Planning",
            "description": "Plan the next iteration",
            "location": "Lab A",
            "color": "#0088cc",
            "start_time": "2026-04-01T15:00:00Z",
            "end_time": "2026-04-01T16:00:00Z",
            "capacity": 5,
            "setup_minutes": 10,
            "cleanup_minutes": 5,
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["attendee_count"] == 2
    assert created["accepted_count"] == 1
    assert created["invited_count"] == 1

    attendee_list_response = client.get("/api/meetings/", headers=auth_headers(attendee_token))
    assert attendee_list_response.status_code == 200, attendee_list_response.text
    attendee_items = attendee_list_response.json()
    assert len(attendee_items) == 1
    assert attendee_items[0]["current_user_status"] == "invited"

    attendee_calendar_before_response = client.get("/api/calendar/events", headers=auth_headers(attendee_token))
    assert attendee_calendar_before_response.status_code == 200, attendee_calendar_before_response.text
    assert attendee_calendar_before_response.json() == []

    rsvp_response = client.post(
        f"/api/meetings/{created['id']}/rsvp",
        headers=auth_headers(attendee_token),
        json={"status": "maybe"},
    )
    assert rsvp_response.status_code == 200, rsvp_response.text
    assert rsvp_response.json()["maybe_count"] == 1

    attendee_calendar_after_response = client.get("/api/calendar/events", headers=auth_headers(attendee_token))
    assert attendee_calendar_after_response.status_code == 200, attendee_calendar_after_response.text
    attendee_calendar_events = attendee_calendar_after_response.json()
    assert len(attendee_calendar_events) == 1
    assert attendee_calendar_events[0]["title"] == "Sprint Planning"

    cancel_response = client.post(
        f"/api/meetings/{created['id']}/cancel",
        headers=auth_headers(organizer_token),
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["status"] == "cancelled"

    hidden_list_response = client.get("/api/meetings/", headers=auth_headers(attendee_token))
    assert hidden_list_response.status_code == 200, hidden_list_response.text
    assert hidden_list_response.json() == []

    visible_cancelled_response = client.get(
        "/api/meetings/?include_cancelled=true",
        headers=auth_headers(attendee_token),
    )
    assert visible_cancelled_response.status_code == 200, visible_cancelled_response.text
    assert len(visible_cancelled_response.json()) == 1


def test_meeting_recommendations_full_match_only(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    attendee_token = register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")
    recommendation_date = "2026-04-07"
    day_index = day_index_for(recommendation_date)

    organizer_availability = client.post(
        "/api/availability/",
        headers=auth_headers(organizer_token),
        json=[
            {"day_of_week": day_index, "start_time": "09:00:00", "end_time": "12:00:00"}
        ],
    )
    assert organizer_availability.status_code == 200, organizer_availability.text

    attendee_availability = client.post(
        "/api/availability/",
        headers=auth_headers(attendee_token),
        json=[
            {"day_of_week": day_index, "start_time": "09:00:00", "end_time": "12:00:00"}
        ],
    )
    assert attendee_availability.status_code == 200, attendee_availability.text

    blocking_meeting = client.post(
        "/api/meetings/",
        headers=auth_headers(attendee_token),
        json={
            "title": "Existing Conflict",
            "start_time": f"{recommendation_date}T10:00:00",
            "end_time": f"{recommendation_date}T11:00:00",
            "attendee_emails": [],
        },
    )
    assert blocking_meeting.status_code == 200, blocking_meeting.text

    recommendation_response = client.post(
        "/api/meetings/recommendations",
        headers=auth_headers(organizer_token),
        json={
            "attendee_emails": ["grace@example.com"],
            "start_date": recommendation_date,
            "end_date": recommendation_date,
            "duration_minutes": 60,
            "max_results": 3,
            "include_organizer": True,
        },
    )
    assert recommendation_response.status_code == 200, recommendation_response.text

    payload = recommendation_response.json()
    assert payload["duration_minutes"] == 60
    assert [recommendation["start_time"] for recommendation in payload["recommendations"]] == [
        f"{recommendation_date}T09:00:00",
        f"{recommendation_date}T11:00:00",
    ]
