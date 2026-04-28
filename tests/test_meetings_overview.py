from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db.session import SessionLocal


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


def _register_user(
    client,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str = "supersecret123",
) -> None:
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


def _web_login(client, *, email: str, password: str = "supersecret123") -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _seed_calendar_meeting(
    *,
    organizer_email: str,
    title: str,
    attendees: list[tuple[str, str]],
    start_time: datetime,
    end_time: datetime,
    meeting_type: str = "in_person",
    location: str | None = None,
) -> int:
    db = SessionLocal()
    try:
        organizer_id = int(
            db.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": organizer_email},
            ).scalar_one()
        )
        calendar_id = int(
            db.execute(
                text(
                    """
                    INSERT INTO calendars (name, owner_type, owner_id)
                    VALUES (:name, 'user', :owner_id)
                    RETURNING id
                    """
                ),
                {"name": f"{organizer_email} calendar", "owner_id": organizer_id},
            ).scalar_one()
        )
        meeting_id = int(
            db.execute(
                text(
                    """
                    INSERT INTO meetings (
                        calendar_id,
                        title,
                        meeting_type,
                        location,
                        start_time,
                        end_time,
                        status,
                        created_by
                    )
                    VALUES (
                        :calendar_id,
                        :title,
                        :meeting_type,
                        :location,
                        :start_time,
                        :end_time,
                        'confirmed',
                        :created_by
                    )
                    RETURNING id
                    """
                ),
                {
                    "calendar_id": calendar_id,
                    "title": title,
                    "meeting_type": meeting_type,
                    "location": location,
                    "start_time": start_time,
                    "end_time": end_time,
                    "created_by": organizer_id,
                },
            ).scalar_one()
        )

        db.execute(
            text(
                """
                INSERT INTO meeting_attendees (meeting_id, user_id, status)
                VALUES (:meeting_id, :user_id, 'accepted')
                """
            ),
            {"meeting_id": meeting_id, "user_id": organizer_id},
        )

        for attendee_email, status in attendees:
            attendee_id = int(
                db.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": attendee_email},
                ).scalar_one()
            )
            db.execute(
                text(
                    """
                    INSERT INTO meeting_attendees (meeting_id, user_id, status)
                    VALUES (:meeting_id, :user_id, :status)
                    """
                ),
                {"meeting_id": meeting_id, "user_id": attendee_id, "status": status},
            )

        db.commit()
        return meeting_id
    finally:
        db.close()


def _seed_group_membership(*, owner_email: str, member_email: str, group_name: str = "Capstone Crew") -> int:
    db = SessionLocal()
    try:
        owner_id = int(
            db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": owner_email}).scalar_one()
        )
        member_id = int(
            db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": member_email}).scalar_one()
        )
        group_id = int(
            db.execute(
                text(
                    """
                    INSERT INTO groups (name, description)
                    VALUES (:name, 'Seeded test group')
                    RETURNING id
                    """
                ),
                {"name": group_name},
            ).scalar_one()
        )
        db.execute(
            text(
                """
                INSERT INTO group_memberships (user_id, group_id, role)
                VALUES (:owner_id, :group_id, 'owner'),
                       (:member_id, :group_id, 'member')
                """
            ),
            {"owner_id": owner_id, "member_id": member_id, "group_id": group_id},
        )
        db.commit()
        return group_id
    finally:
        db.close()


def test_meeting_scheduler_supports_meeting_type_toggle_and_virtual_create(client, monkeypatch):
    _register_user(client, first_name="Ada", last_name="Lovelace", email="ada@example.com")
    _web_login(client, email="ada@example.com")
    monkeypatch.setattr("app.web.routes.get_travel_warning_service", lambda: DummyTravelWarningService())

    response = client.get("/meetings")

    assert response.status_code == 200, response.text
    assert "Meeting Scheduler" in response.text
    assert 'name="meeting_type"' in response.text
    assert "Remote" in response.text

    create_response = client.post(
        "/meetings/create",
        data={
            "title": "Virtual Design Review",
            "meeting_type": "virtual",
            "location": "https://zoom.example.com/virtual-design-review",
            "location_raw": "https://zoom.example.com/virtual-design-review",
            "location_latitude": "",
            "location_longitude": "",
            "start_time": "2099-01-01T10:00",
            "end_time": "2099-01-01T11:00",
            "invitees": "",
            "q": "",
            "status": "",
            "mine": "",
            "day": "2099-01-01",
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303, create_response.text

    db = SessionLocal()
    try:
        meeting = db.execute(
            text(
                """
                SELECT meeting_type, location
                FROM meetings
                WHERE title = 'Virtual Design Review'
                """
            )
        ).mappings().one()
    finally:
        db.close()

    assert meeting["meeting_type"] == "virtual"
    assert meeting["location"] == "https://zoom.example.com/virtual-design-review"


def test_meetings_overview_group_scope_lets_owner_manage_member_meeting(client):
    _register_user(client, first_name="Olive", last_name="Owner", email="owner@example.com")
    _register_user(client, first_name="Milo", last_name="Member", email="member@example.com")
    _register_user(client, first_name="Gina", last_name="Guest", email="guest@example.com")
    _web_login(client, email="owner@example.com")

    _seed_group_membership(owner_email="owner@example.com", member_email="member@example.com")
    meeting_id = _seed_calendar_meeting(
        organizer_email="member@example.com",
        title="Group Roadmap Review",
        attendees=[("guest@example.com", "accepted")],
        start_time=datetime(2099, 1, 2, 15, 0, tzinfo=timezone.utc),
        end_time=datetime(2099, 1, 2, 16, 0, tzinfo=timezone.utc),
        location="Babbio 122",
    )

    mine_response = client.get("/meetings/overview")
    assert mine_response.status_code == 200, mine_response.text
    assert "Group Roadmap Review" not in mine_response.text

    group_response = client.get("/meetings/overview?scope=group")
    assert group_response.status_code == 200, group_response.text
    assert "Group Roadmap Review" in group_response.text
    assert "Visible here because someone from one of your owned groups is on this meeting." in group_response.text
    assert "Can manage" in group_response.text

    reschedule_response = client.post(
        "/meetings/overview/reschedule",
        data={
            "meeting_id": meeting_id,
            "scope": "group",
            "start_time": "2099-01-03T09:00",
            "end_time": "2099-01-03T10:00",
        },
        follow_redirects=False,
    )
    assert reschedule_response.status_code == 303, reschedule_response.text
    assert reschedule_response.headers["location"] == "/meetings/overview?scope=group"

    db = SessionLocal()
    try:
        meeting_row = db.execute(
            text(
                """
                SELECT start_time, end_time, status
                FROM meetings
                WHERE id = :meeting_id
                """
            ),
            {"meeting_id": meeting_id},
        ).mappings().one()
        attendee_rows = db.execute(
            text(
                """
                SELECT u.email, ma.status
                FROM meeting_attendees ma
                JOIN users u ON u.id = ma.user_id
                WHERE ma.meeting_id = :meeting_id
                ORDER BY u.email
                """
            ),
            {"meeting_id": meeting_id},
        ).mappings().all()
    finally:
        db.close()

    assert meeting_row["start_time"] == datetime(2099, 1, 3, 9, 0, tzinfo=timezone.utc)
    assert meeting_row["end_time"] == datetime(2099, 1, 3, 10, 0, tzinfo=timezone.utc)
    attendee_statuses = {row["email"]: row["status"] for row in attendee_rows}
    assert attendee_statuses["member@example.com"] == "accepted"
    assert attendee_statuses["guest@example.com"] == "invited"

    cancel_response = client.post(
        "/meetings/overview/cancel",
        data={"meeting_id": meeting_id, "scope": "group"},
        follow_redirects=False,
    )
    assert cancel_response.status_code == 303, cancel_response.text

    db = SessionLocal()
    try:
        cancelled_status = db.execute(
            text("SELECT status FROM meetings WHERE id = :meeting_id"),
            {"meeting_id": meeting_id},
        ).scalar_one()
    finally:
        db.close()

    assert cancelled_status == "cancelled"


def test_meetings_overview_allows_participant_to_add_people(client):
    _register_user(client, first_name="Ava", last_name="Organizer", email="organizer@example.com")
    _register_user(client, first_name="Ben", last_name="Participant", email="participant@example.com")
    _register_user(client, first_name="Cara", last_name="New", email="newperson@example.com")

    meeting_id = _seed_calendar_meeting(
        organizer_email="organizer@example.com",
        title="Invite Expansion",
        attendees=[("participant@example.com", "accepted")],
        start_time=datetime.now(timezone.utc) + timedelta(days=30),
        end_time=datetime.now(timezone.utc) + timedelta(days=30, hours=1),
        meeting_type="virtual",
        location="https://teams.example.com/invite-expansion",
    )

    _web_login(client, email="participant@example.com")

    response = client.post(
        "/meetings/overview/invitees",
        data={
            "meeting_id": meeting_id,
            "scope": "mine",
            "invitees": "newperson@example.com",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/meetings/overview"

    db = SessionLocal()
    try:
        attendee_rows = db.execute(
            text(
                """
                SELECT u.email, ma.status
                FROM meeting_attendees ma
                JOIN users u ON u.id = ma.user_id
                WHERE ma.meeting_id = :meeting_id
                ORDER BY u.email
                """
            ),
            {"meeting_id": meeting_id},
        ).mappings().all()
    finally:
        db.close()

    attendee_statuses = {row["email"]: row["status"] for row in attendee_rows}
    assert attendee_statuses["newperson@example.com"] == "invited"
