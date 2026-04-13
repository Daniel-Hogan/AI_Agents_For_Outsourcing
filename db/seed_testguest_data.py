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


TEST_USER_EMAIL = "testguest@stevens.edu"
TEST_USER_PASSWORD = "testguest123"
PASSWORD_PROVIDER = "password"
MEETING_TITLES = ("Lunch", "Trip to disney")

# Uses the clarified date from the user: April 20, 2026.
LUNCH_START = datetime(2026, 4, 20, 12, 30, tzinfo=timezone.utc)
LUNCH_END = datetime(2026, 4, 20, 13, 30, tzinfo=timezone.utc)
DISNEY_START = datetime(2026, 4, 20, 14, 30, tzinfo=timezone.utc)
DISNEY_END = datetime(2026, 4, 20, 15, 30, tzinfo=timezone.utc)


def ensure_test_user(db) -> User:
    user = db.execute(select(User).where(User.email == TEST_USER_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(
            first_name="test",
            last_name="guest",
            email=TEST_USER_EMAIL,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.first_name = "test"
        user.last_name = "guest"
        user.is_active = True

    credential = db.get(PasswordCredential, user.id)
    password_hash = hash_password(TEST_USER_PASSWORD)
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
                provider_subject=TEST_USER_EMAIL,
                email=TEST_USER_EMAIL,
                email_verified=False,
            )
        )
    else:
        identity.provider_subject = TEST_USER_EMAIL
        identity.email = TEST_USER_EMAIL

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


def reset_seed_meetings(db, *, calendar_id: int) -> None:
    meeting_ids = db.execute(
        text(
            """
            SELECT id
            FROM meetings
            WHERE calendar_id = :calendar_id
              AND (title = :title_one OR title = :title_two)
            """
        ),
        {
            "calendar_id": calendar_id,
            "title_one": MEETING_TITLES[0],
            "title_two": MEETING_TITLES[1],
        },
    ).scalars().all()

    if meeting_ids:
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
    user_id: int,
    title: str,
    location: str,
    location_raw: str,
    latitude: float,
    longitude: float,
    start_time: datetime,
    end_time: datetime,
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
                "location_raw": location_raw,
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
        {"meeting_id": meeting_id, "user_id": user_id},
    )


def main() -> None:
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        user = ensure_test_user(db)
        calendar_id = get_or_create_personal_calendar(db, user=user)
        reset_seed_meetings(db, calendar_id=calendar_id)

        insert_meeting(
            db,
            calendar_id=calendar_id,
            user_id=user.id,
            title="Lunch",
            location="1 Castle Point on Hudson, Hoboken, NJ, USA",
            location_raw="1 Castle Point on Hudson, Hoboken, NJ, USA",
            latitude=40.745008,
            longitude=-74.024085,
            start_time=LUNCH_START,
            end_time=LUNCH_END,
        )
        insert_meeting(
            db,
            calendar_id=calendar_id,
            user_id=user.id,
            title="Trip to disney",
            location="Orlando, Florida",
            location_raw="Orlando, Florida",
            latitude=28.538336,
            longitude=-81.379234,
            start_time=DISNEY_START,
            end_time=DISNEY_END,
        )

        db.commit()
        print("Seed complete.")
        print(f"User: {TEST_USER_EMAIL}")
        print(f"Password: {TEST_USER_PASSWORD}")
        print("Meetings: Lunch, Trip to disney")
        print("Date: 2026-04-20")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
