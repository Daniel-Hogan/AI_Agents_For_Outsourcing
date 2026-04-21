from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import hash_password
from app.db.bootstrap import ensure_runtime_schema
from app.db.session import SessionLocal
from app.models import AuthIdentity, PasswordCredential, User


PASSWORD_PROVIDER = "password"
DEFAULT_PASSWORD = "demo12345"
TEST_USER_EMAIL = "testguest@stevens.edu"
TEST_USER_PASSWORD = "testguest123"
WEEK_START = datetime(2026, 4, 13, 0, 0, tzinfo=timezone.utc)
WEEK_END = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)

USER_PROFILES = [
    {
        "first_name": "test",
        "last_name": "guest",
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "default_location": "1 Castle Point on Hudson, Hoboken, NJ, USA",
        "default_location_latitude": 40.745008,
        "default_location_longitude": -74.024085,
    },
    {"first_name": "Alex", "last_name": "Rivera", "email": "alex.rivera@stevens.edu", "password": DEFAULT_PASSWORD},
    {"first_name": "Maya", "last_name": "Patel", "email": "maya.patel@stevens.edu", "password": DEFAULT_PASSWORD},
    {"first_name": "Jordan", "last_name": "Lee", "email": "jordan.lee@stevens.edu", "password": DEFAULT_PASSWORD},
    {"first_name": "Priya", "last_name": "Shah", "email": "priya.shah@stevens.edu", "password": DEFAULT_PASSWORD},
    {"first_name": "Sam", "last_name": "Chen", "email": "sam.chen@stevens.edu", "password": DEFAULT_PASSWORD},
    {"first_name": "Olivia", "last_name": "Brooks", "email": "olivia.brooks@stevens.edu", "password": DEFAULT_PASSWORD},
]

WEEK_MEETINGS = [
    {
        "title": "Campus Planning Standup",
        "location": "1 Castle Point on Hudson, Hoboken, NJ, USA",
        "latitude": 40.745008,
        "longitude": -74.024085,
        "start_time": datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc),
        "attendees": ["alex.rivera@stevens.edu", "maya.patel@stevens.edu"],
        "alert_hint": "info",
    },
    {
        "title": "Airport Vendor Review",
        "location": "John F. Kennedy International Airport, Queens, NY, USA",
        "latitude": 40.641311,
        "longitude": -73.778139,
        "start_time": datetime(2026, 4, 13, 10, 45, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 13, 11, 45, tzinfo=timezone.utc),
        "attendees": ["jordan.lee@stevens.edu", "priya.shah@stevens.edu", "sam.chen@stevens.edu"],
        "alert_hint": "critical",
    },
    {
        "title": "Roadmap Check-In",
        "location": "Hoboken Terminal, Hoboken, NJ, USA",
        "latitude": 40.735657,
        "longitude": -74.027464,
        "start_time": datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
        "attendees": ["alex.rivera@stevens.edu", "olivia.brooks@stevens.edu"],
        "alert_hint": "info",
    },
    {
        "title": "Terminal Ops Briefing",
        "location": "Newark Liberty International Airport, Newark, NJ, USA",
        "latitude": 40.689531,
        "longitude": -74.174462,
        "start_time": datetime(2026, 4, 14, 10, 35, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 14, 11, 20, tzinfo=timezone.utc),
        "attendees": ["maya.patel@stevens.edu", "priya.shah@stevens.edu"],
        "alert_hint": "caution",
    },
    {
        "title": "Candidate Interview Loop",
        "location": "Babbio Center, Hoboken, NJ, USA",
        "latitude": 40.744489,
        "longitude": -74.025694,
        "start_time": datetime(2026, 4, 15, 9, 30, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 15, 10, 15, tzinfo=timezone.utc),
        "attendees": ["jordan.lee@stevens.edu", "sam.chen@stevens.edu"],
        "alert_hint": "info",
    },
    {
        "title": "Design Review",
        "location": "Harborside Plaza, Jersey City, NJ, USA",
        "latitude": 40.719486,
        "longitude": -74.034878,
        "start_time": datetime(2026, 4, 15, 13, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 15, 14, 0, tzinfo=timezone.utc),
        "attendees": ["alex.rivera@stevens.edu", "maya.patel@stevens.edu", "olivia.brooks@stevens.edu"],
        "alert_hint": "none",
    },
    {
        "title": "Client Workshop",
        "location": "Bryant Park, Manhattan, NY, USA",
        "latitude": 40.753597,
        "longitude": -73.983233,
        "start_time": datetime(2026, 4, 16, 11, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
        "attendees": ["priya.shah@stevens.edu", "olivia.brooks@stevens.edu"],
        "alert_hint": "info",
    },
    {
        "title": "Investor Debrief",
        "location": "Newark Penn Station, Newark, NJ, USA",
        "latitude": 40.734722,
        "longitude": -74.164167,
        "start_time": datetime(2026, 4, 16, 12, 35, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 16, 13, 20, tzinfo=timezone.utc),
        "attendees": ["alex.rivera@stevens.edu", "sam.chen@stevens.edu"],
        "alert_hint": "caution",
    },
    {
        "title": "Sprint Retro",
        "location": "Pier A Park, Hoboken, NJ, USA",
        "latitude": 40.737894,
        "longitude": -74.025455,
        "start_time": datetime(2026, 4, 17, 9, 15, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        "attendees": ["maya.patel@stevens.edu", "jordan.lee@stevens.edu"],
        "alert_hint": "info",
    },
    {
        "title": "Regional Offsite",
        "location": "30th Street Station, Philadelphia, PA, USA",
        "latitude": 39.955686,
        "longitude": -75.182037,
        "start_time": datetime(2026, 4, 17, 10, 50, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 17, 11, 50, tzinfo=timezone.utc),
        "attendees": ["priya.shah@stevens.edu", "sam.chen@stevens.edu", "olivia.brooks@stevens.edu"],
        "alert_hint": "critical",
    },
]


def ensure_user(db, *, profile: dict[str, object]) -> User:
    email = str(profile["email"]).strip().lower()
    password = str(profile["password"])
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(
            first_name=str(profile["first_name"]),
            last_name=str(profile["last_name"]),
            email=email,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.first_name = str(profile["first_name"])
        user.last_name = str(profile["last_name"])
        user.email = email
        user.is_active = True

    user.default_location = profile.get("default_location")
    user.default_location_latitude = profile.get("default_location_latitude")
    user.default_location_longitude = profile.get("default_location_longitude")

    password_hash = hash_password(password)
    credential = db.get(PasswordCredential, user.id)
    if credential is None:
        db.add(PasswordCredential(user_id=user.id, password_hash=password_hash))
    else:
        credential.password_hash = password_hash

    identity = db.execute(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == PASSWORD_PROVIDER,
        )
    ).scalar_one_or_none()
    if identity is None:
        db.add(
            AuthIdentity(
                user_id=user.id,
                provider=PASSWORD_PROVIDER,
                provider_subject=email,
                email=email,
                email_verified=False,
            )
        )
    else:
        identity.provider_subject = email
        identity.email = email

    db.flush()
    return user


def get_or_create_personal_calendar(db, *, user: User) -> int:
    existing_id = db.execute(
        text(
            """
            SELECT id
            FROM calendars
            WHERE owner_type = 'user' AND owner_id = :user_id
            ORDER BY id
            LIMIT 1
            """
        ),
        {"user_id": user.id},
    ).scalar_one_or_none()
    if existing_id is not None:
        return int(existing_id)

    return int(
        db.execute(
            text(
                """
                INSERT INTO calendars (name, owner_type, owner_id)
                VALUES (:name, 'user', :user_id)
                RETURNING id
                """
            ),
            {"name": f"{user.email} calendar", "user_id": user.id},
        ).scalar_one()
    )


def reset_week_seed_meetings(db, *, calendar_id: int) -> None:
    meeting_ids = db.execute(
        text(
            """
            SELECT id
            FROM meetings
            WHERE calendar_id = :calendar_id
              AND start_time >= :week_start
              AND start_time < :week_end
            """
        ),
        {
            "calendar_id": calendar_id,
            "week_start": WEEK_START,
            "week_end": WEEK_END,
        },
    ).scalars().all()

    if not meeting_ids:
        return

    db.execute(
        text("DELETE FROM meeting_attendees WHERE meeting_id = ANY(:meeting_ids)"),
        {"meeting_ids": list(meeting_ids)},
    )
    db.execute(
        text("DELETE FROM meetings WHERE id = ANY(:meeting_ids)"),
        {"meeting_ids": list(meeting_ids)},
    )


def insert_meeting(
    db,
    *,
    calendar_id: int,
    organizer_id: int,
    title: str,
    location: str,
    latitude: float,
    longitude: float,
    start_time: datetime,
    end_time: datetime,
    attendee_ids: list[int],
) -> None:
    meeting_id = int(
        db.execute(
            text(
                """
                INSERT INTO meetings (
                    calendar_id,
                    title,
                    location,
                    location_raw,
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
                    :location_raw,
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
                "location_raw": location,
                "latitude": latitude,
                "longitude": longitude,
                "start_time": start_time,
                "end_time": end_time,
            },
        ).scalar_one()
    )

    db.execute(
        text(
            """
            INSERT INTO meeting_attendees (meeting_id, user_id, status)
            VALUES (:meeting_id, :user_id, 'accepted')
            ON CONFLICT (meeting_id, user_id) DO UPDATE SET status = EXCLUDED.status
            """
        ),
        {"meeting_id": meeting_id, "user_id": organizer_id},
    )

    for attendee_id in attendee_ids:
        if attendee_id == organizer_id:
            continue
        db.execute(
            text(
                """
                INSERT INTO meeting_attendees (meeting_id, user_id, status)
                VALUES (:meeting_id, :user_id, 'invited')
                ON CONFLICT (meeting_id, user_id) DO UPDATE SET status = EXCLUDED.status
                """
            ),
            {"meeting_id": meeting_id, "user_id": attendee_id},
        )


def main() -> None:
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        users_by_email = {
            str(profile["email"]).strip().lower(): ensure_user(db, profile=profile) for profile in USER_PROFILES
        }
        testguest = users_by_email[TEST_USER_EMAIL]
        calendar_id = get_or_create_personal_calendar(db, user=testguest)
        reset_week_seed_meetings(db, calendar_id=calendar_id)

        for meeting in WEEK_MEETINGS:
            attendee_ids = [users_by_email[email].id for email in meeting["attendees"]]
            insert_meeting(
                db,
                calendar_id=calendar_id,
                organizer_id=testguest.id,
                title=str(meeting["title"]),
                location=str(meeting["location"]),
                latitude=float(meeting["latitude"]),
                longitude=float(meeting["longitude"]),
                start_time=meeting["start_time"],
                end_time=meeting["end_time"],
                attendee_ids=attendee_ids,
            )

        db.commit()

        print("Weekly demo seed complete.")
        print(f"Primary user: {TEST_USER_EMAIL}")
        print(f"Primary password: {TEST_USER_PASSWORD}")
        print("Guest accounts:")
        for profile in USER_PROFILES[1:]:
            print(f"  - {profile['email']} / {profile['password']}")
        print("Seeded meetings for week: 2026-04-13 through 2026-04-17")
        print("Alert demo hints:")
        for meeting in WEEK_MEETINGS:
            start_label = meeting["start_time"].strftime("%Y-%m-%d %H:%M")
            print(f"  - {start_label} | {meeting['title']} -> expected {meeting['alert_hint']}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
