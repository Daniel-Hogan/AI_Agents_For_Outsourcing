import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.notifications import (
    REMINDER_LOCK_ID,
    create_due_reminder_notifications,
    start_notification_scheduler,
    stop_notification_scheduler,
    _send_email_notification,
)


class NoopTravelWarningService:
    def evaluate_meeting(self, db, *, user, meeting, persist=False):
        return []


@pytest.fixture(autouse=True)
def _deterministic_email_settings(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", None)
    monkeypatch.setattr(settings, "email_from_address", None)
    monkeypatch.setattr(settings, "app_base_url", "http://127.0.0.1:8000")


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


def web_login(client, *, email: str, password: str = "supersecret123") -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_web_meeting_create_notifies_invited_user(client, monkeypatch):
    register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")
    register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    web_login(client, email="ada@example.com")
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: NoopTravelWarningService())

    response = client.post(
        "/meetings/create",
        data={
            "title": "Python UI Invite",
            "meeting_type": "virtual",
            "location": "https://zoom.example.com/python-ui-invite",
            "location_raw": "https://zoom.example.com/python-ui-invite",
            "location_latitude": "",
            "location_longitude": "",
            "start_time": "2030-05-01T09:00",
            "end_time": "2030-05-01T10:00",
            "invitees": "grace@example.com",
            "q": "",
            "status": "",
            "mine": "",
            "day": "2030-05-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT channel, type, status, title, message
                FROM notifications
                WHERE user_id = 1
                ORDER BY id ASC
                """
            )
        ).fetchall()
    finally:
        db.close()

    assert [(row.channel, row.type, row.status) for row in rows] == [
        ("in_app", "invite", "sent"),
        ("email", "invite", "skipped"),
    ]
    assert rows[1].title == "Meeting invite: Python UI Invite"
    assert "Meeting link: https://zoom.example.com/python-ui-invite" in rows[1].message
    assert "Manage your RSVP" not in rows[1].message


def test_notification_preferences_round_trip(client):
    token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")

    get_response = client.get("/notifications/preferences", headers=auth_headers(token))
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["email"] is True
    assert get_response.json()["in_app"] is True

    update_response = client.put(
        "/notifications/preferences",
        headers=auth_headers(token),
        json={
            "email": False,
            "in_app": True,
            "meeting_reminders": False,
            "group_activity": False,
            "weekly_digest": True,
            "digest_frequency": "daily",
            "quiet_hours_enabled": True,
            "quiet_hours_start": "21:00:00",
            "quiet_hours_end": "07:00:00",
        },
    )
    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["email"] is False
    assert payload["weekly_digest"] is True
    assert payload["digest_frequency"] == "daily"


def test_notifications_created_for_invite_update_cancel(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    attendee_token = register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Sprint Planning",
            "description": "Plan the next sprint",
            "location": "Lab A",
            "meeting_type": "in_person",
            "start_time": "2026-04-21T14:00:00Z",
            "end_time": "2026-04-21T15:00:00Z",
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert create_response.status_code == 200, create_response.text
    meeting_id = create_response.json()["id"]

    pending_invites = client.get("/notifications/pending-invites", headers=auth_headers(attendee_token))
    assert pending_invites.status_code == 200, pending_invites.text
    assert len(pending_invites.json()) == 1
    assert pending_invites.json()[0]["meeting_id"] == meeting_id

    in_app_notifications = client.get("/notifications/", headers=auth_headers(attendee_token))
    assert in_app_notifications.status_code == 200, in_app_notifications.text
    notifications = in_app_notifications.json()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "invite"
    assert notifications[0]["status"] == "sent"

    mark_read_response = client.post(
        f"/notifications/{notifications[0]['id']}/read",
        headers=auth_headers(attendee_token),
    )
    assert mark_read_response.status_code == 200, mark_read_response.text
    assert mark_read_response.json()["status"] == "read"

    update_response = client.put(
        f"/api/meetings/{meeting_id}",
        headers=auth_headers(organizer_token),
        json={
            "location": "Lab B",
            "start_time": "2026-04-21T16:00:00Z",
            "end_time": "2026-04-21T17:00:00Z",
        },
    )
    assert update_response.status_code == 200, update_response.text

    cancel_response = client.post(
        f"/api/meetings/{meeting_id}/cancel",
        headers=auth_headers(organizer_token),
    )
    assert cancel_response.status_code == 200, cancel_response.text

    refreshed_notifications = client.get("/notifications/", headers=auth_headers(attendee_token))
    assert refreshed_notifications.status_code == 200, refreshed_notifications.text
    refreshed_payload = refreshed_notifications.json()
    assert [item["type"] for item in refreshed_payload[:3]] == ["cancel", "update", "invite"]

    pending_after_cancel = client.get("/notifications/pending-invites", headers=auth_headers(attendee_token))
    assert pending_after_cancel.status_code == 200, pending_after_cancel.text
    assert pending_after_cancel.json() == []

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT channel, type, status
                FROM notifications
                WHERE user_id = 2
                ORDER BY id ASC
                """
            )
        ).fetchall()
    finally:
        db.close()

    assert rows == [
        ("in_app", "invite", "read"),
        ("email", "invite", "skipped"),
        ("in_app", "update", "sent"),
        ("email", "update", "skipped"),
        ("in_app", "cancel", "sent"),
        ("email", "cancel", "skipped"),
    ]


def test_email_invite_message_uses_location_or_meeting_link(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    in_person_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "SD Meeting",
            "location": "Scott Hall",
            "meeting_type": "in_person",
            "start_time": "2030-04-23T11:00:00Z",
            "end_time": "2030-04-23T12:00:00Z",
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert in_person_response.status_code == 200, in_person_response.text

    db = SessionLocal()
    try:
        in_person_message = db.execute(
            text(
                """
                SELECT message
                FROM notifications
                WHERE user_id = 2 AND channel = 'email' AND type = 'invite'
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).scalar_one()
    finally:
        db.close()

    assert "Location: Scott Hall" in in_person_message
    assert "Meeting link:" not in in_person_message
    assert "Manage your RSVP" not in in_person_message

    virtual_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Remote SD Meeting",
            "location": "https://zoom.example.com/meeting-123",
            "meeting_type": "virtual",
            "start_time": "2030-04-24T11:00:00Z",
            "end_time": "2030-04-24T12:00:00Z",
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert virtual_response.status_code == 200, virtual_response.text

    db = SessionLocal()
    try:
        virtual_message = db.execute(
            text(
                """
                SELECT message
                FROM notifications
                WHERE user_id = 2 AND channel = 'email' AND type = 'invite'
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).scalar_one()
    finally:
        db.close()

    assert "Meeting link: https://zoom.example.com/meeting-123" in virtual_message
    assert "Location:" not in virtual_message
    assert "Manage your RSVP" not in virtual_message


def test_email_provider_payload_preserves_line_breaks_and_single_app_link(client, monkeypatch):
    register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    monkeypatch.setattr(settings, "resend_api_key", "test-api-key")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(settings, "email_from_name", "Scheduler AI")

    sent_payloads = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "email_123"}

    def fake_post(url, *, headers, json, timeout):
        sent_payloads.append(json)
        return FakeResponse()

    monkeypatch.setattr("app.services.notifications.requests.post", fake_post)

    db = SessionLocal()
    try:
        _send_email_notification(
            user_id=1,
            recipient_email="grace@example.com",
            meeting_id=None,
            notification_type="invite",
            title="Meeting invite: Senior D Meeting",
            message=(
                "swagger lagger invited you to 'senior d meetnig'.\n"
                "When: May 09, 2026 09:00 AM to 10:00 AM UTC\n"
                "Meeting link: zoom"
            ),
            db=db,
        )
        db.commit()
    finally:
        db.close()

    payload = sent_payloads[0]
    assert payload["html"] == (
        "<p>swagger lagger invited you to &#x27;senior d meetnig&#x27;.<br>"
        "When: May 09, 2026 09:00 AM to 10:00 AM UTC<br>"
        "Meeting link: zoom</p>"
        '<p><a href="http://127.0.0.1:8000/meetings">Open Scheduler AI</a></p>'
    )
    assert payload["html"].count("Open Scheduler AI") == 1
    assert "Manage your RSVP" not in payload["html"]
    assert payload["text"] == (
        "swagger lagger invited you to 'senior d meetnig'.\n"
        "When: May 09, 2026 09:00 AM to 10:00 AM UTC\n"
        "Meeting link: zoom\n\n"
        "Open Scheduler AI: http://127.0.0.1:8000/meetings"
    )


def test_notification_bell_supports_session_auth_and_open_marks_visible_items_read(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Bell Review",
            "description": "Review recent notifications",
            "location": "Library",
            "meeting_type": "in_person",
            "start_time": "2030-04-21T14:00:00Z",
            "end_time": "2030-04-21T15:00:00Z",
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert create_response.status_code == 200, create_response.text
    meeting_id = create_response.json()["id"]

    web_login(client, email="grace@example.com")

    bell_response = client.get("/notifications/bell")
    assert bell_response.status_code == 200, bell_response.text
    bell_payload = bell_response.json()
    assert bell_payload["unread_count"] == 1
    assert bell_payload["items"][0]["meeting_id"] == meeting_id
    assert bell_payload["items"][0]["type"] == "invite"
    assert bell_payload["items"][0]["can_rsvp"] is True

    open_response = client.post("/notifications/bell/open")
    assert open_response.status_code == 200, open_response.text
    open_payload = open_response.json()
    assert open_payload["unread_count"] == 0
    assert open_payload["items"][0]["read_at"] is not None

    rsvp_response = client.post(
        f"/api/meetings/{meeting_id}/rsvp",
        json={"status": "accepted"},
    )
    assert rsvp_response.status_code == 200, rsvp_response.text
    assert rsvp_response.json()["current_user_status"] == "accepted"


def test_notification_read_all_marks_recent_bell_items_read(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    attendee_token = register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")

    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Mark All Review",
            "description": "Review read-all behavior",
            "location": "Room 101",
            "meeting_type": "in_person",
            "start_time": "2030-04-21T14:00:00Z",
            "end_time": "2030-04-21T15:00:00Z",
            "attendee_emails": ["grace@example.com"],
        },
    )
    assert create_response.status_code == 200, create_response.text
    meeting_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/meetings/{meeting_id}",
        headers=auth_headers(organizer_token),
        json={
            "location": "Room 202",
            "start_time": "2030-04-21T16:00:00Z",
            "end_time": "2030-04-21T17:00:00Z",
        },
    )
    assert update_response.status_code == 200, update_response.text

    bell_response = client.get("/notifications/bell", headers=auth_headers(attendee_token))
    assert bell_response.status_code == 200, bell_response.text
    assert bell_response.json()["unread_count"] == 2

    read_all_response = client.post("/notifications/read-all", headers=auth_headers(attendee_token))
    assert read_all_response.status_code == 200, read_all_response.text
    assert read_all_response.json()["unread_count"] == 0


def test_reminder_notifications_created_once_and_skip_declined_attendees(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    accepted_token = register_user(client, first_name="Grace", last_name="Hopper", email="grace@example.com")
    maybe_token = register_user(client, first_name="Linus", last_name="Torvalds", email="linus@example.com")
    declined_token = register_user(client, first_name="Dennis", last_name="Ritchie", email="dennis@example.com")
    register_user(client, first_name="Barbara", last_name="Liskov", email="barbara@example.com")

    fixed_now = datetime(2030, 4, 21, 14, 0, tzinfo=timezone.utc)
    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Reminder Review",
            "description": "Review reminder generation",
            "location": "North Lab",
            "meeting_type": "in_person",
            "start_time": (fixed_now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "end_time": (fixed_now + timedelta(minutes=40)).isoformat().replace("+00:00", "Z"),
            "attendee_emails": [
                "grace@example.com",
                "linus@example.com",
                "dennis@example.com",
                "barbara@example.com",
            ],
        },
    )
    assert create_response.status_code == 200, create_response.text
    meeting_id = create_response.json()["id"]

    accepted_rsvp = client.post(
        f"/api/meetings/{meeting_id}/rsvp",
        headers=auth_headers(accepted_token),
        json={"status": "accepted"},
    )
    assert accepted_rsvp.status_code == 200, accepted_rsvp.text

    maybe_rsvp = client.post(
        f"/api/meetings/{meeting_id}/rsvp",
        headers=auth_headers(maybe_token),
        json={"status": "maybe"},
    )
    assert maybe_rsvp.status_code == 200, maybe_rsvp.text

    declined_rsvp = client.post(
        f"/api/meetings/{meeting_id}/rsvp",
        headers=auth_headers(declined_token),
        json={"status": "declined"},
    )
    assert declined_rsvp.status_code == 200, declined_rsvp.text

    db = SessionLocal()
    try:
        created_count = create_due_reminder_notifications(db, now=fixed_now)
        assert created_count == 4
    finally:
        db.close()

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT u.email
                FROM notifications n
                JOIN users u ON u.id = n.user_id
                WHERE n.type = 'reminder'
                ORDER BY u.email
                """
            )
        ).fetchall()
    finally:
        db.close()

    assert [row[0] for row in rows] == [
        "ada@example.com",
        "barbara@example.com",
        "grace@example.com",
        "linus@example.com",
    ]

    db = SessionLocal()
    try:
        duplicate_count = create_due_reminder_notifications(db, now=fixed_now)
        assert duplicate_count == 0
    finally:
        db.close()


def test_reminder_generation_skips_when_advisory_lock_is_unavailable(client):
    organizer_token = register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    fixed_now = datetime(2030, 4, 21, 14, 0, tzinfo=timezone.utc)

    create_response = client.post(
        "/api/meetings/",
        headers=auth_headers(organizer_token),
        json={
            "title": "Lock Review",
            "description": "Review advisory lock behavior",
            "location": "South Lab",
            "meeting_type": "in_person",
            "start_time": (fixed_now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "end_time": (fixed_now + timedelta(minutes=35)).isoformat().replace("+00:00", "Z"),
            "attendee_emails": [],
        },
    )
    assert create_response.status_code == 200, create_response.text

    lock_db = SessionLocal()
    worker_db = SessionLocal()
    try:
        lock_db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": REMINDER_LOCK_ID})
        worker_result = create_due_reminder_notifications(worker_db, now=fixed_now)
        assert worker_result == 0
    finally:
        lock_db.rollback()
        lock_db.close()
        worker_db.close()

    db = SessionLocal()
    try:
        reminder_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM notifications
                    WHERE type = 'reminder'
                    """
                )
            ).scalar_one()
        )
    finally:
        db.close()

    assert reminder_count == 0


def test_notification_scheduler_starts_only_once(monkeypatch):
    async def fake_scheduler_loop(stop_event, *, poll_seconds):
        await stop_event.wait()

    async def scenario():
        app = SimpleNamespace(state=SimpleNamespace())
        monkeypatch.setattr("app.services.notifications._notification_scheduler_loop", fake_scheduler_loop)

        first_task = start_notification_scheduler(app, poll_seconds=999)
        second_task = start_notification_scheduler(app, poll_seconds=999)

        assert first_task is second_task

        await stop_notification_scheduler(app)
        assert first_task.done() is True

    asyncio.run(scenario())
