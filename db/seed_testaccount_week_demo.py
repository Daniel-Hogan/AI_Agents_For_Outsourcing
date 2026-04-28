from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import hash_password
from app.db.bootstrap import ensure_runtime_schema
from app.db.calendars import get_or_create_user_calendar
from app.db.session import SessionLocal
from app.models import AuthIdentity, PasswordCredential, User


PASSWORD_PROVIDER = "password"
PRIMARY_EMAIL = "testaccount@stevens.edu"
PRIMARY_PASSWORD = "testaccount123"
GUEST_EMAIL = "testguest@stevens.edu"
GUEST_PASSWORD = "testguest123"
DEFAULT_INVITEE_PASSWORD = "stevensdemo123"
DEFAULT_INVITEE_COUNT = 36
PRIMARY_SEED_MARKER = "[seed:testaccount-week-2026-04-20]"
PRIMARY_RANDOM_SEED = 20260420
PRIMARY_WEEK_START = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)
PRIMARY_WEEK_END = datetime(2026, 4, 26, 0, 0, tzinfo=timezone.utc)
GUEST_SEED_MARKER = "[seed:testguest-week-2026-05-18]"
GUEST_RANDOM_SEED = 20260518
GUEST_WEEK_START = datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc)
GUEST_WEEK_END = datetime(2026, 5, 23, 0, 0, tzinfo=timezone.utc)

FIRST_NAMES = [
    "Avery",
    "Morgan",
    "Jordan",
    "Taylor",
    "Riley",
    "Casey",
    "Quinn",
    "Parker",
    "Skyler",
    "Cameron",
    "Drew",
    "Alex",
    "Hayden",
    "Rowan",
    "Blake",
    "Logan",
    "Reese",
    "Sydney",
    "Kendall",
    "Emerson",
]

LAST_NAMES = [
    "Parker",
    "Bennett",
    "Sullivan",
    "Ramirez",
    "Kim",
    "Patel",
    "Nguyen",
    "Rivera",
    "Brooks",
    "Shah",
    "Chen",
    "Flores",
    "Davis",
    "Morris",
    "Campbell",
    "Diaz",
    "Kelly",
    "Cruz",
    "Long",
    "Ward",
]

LOCATIONS = {
    "stevens": {
        "label": "1 Castle Point on Hudson, Hoboken, NJ, USA",
        "latitude": 40.745008,
        "longitude": -74.024085,
    },
    "babbio": {
        "label": "Babbio Center, Hoboken, NJ, USA",
        "latitude": 40.744489,
        "longitude": -74.025694,
    },
    "terminal": {
        "label": "Hoboken Terminal, Hoboken, NJ, USA",
        "latitude": 40.735657,
        "longitude": -74.027464,
    },
    "pier_a": {
        "label": "Pier A Park, Hoboken, NJ, USA",
        "latitude": 40.737894,
        "longitude": -74.025455,
    },
    "harborside": {
        "label": "Harborside Plaza, Jersey City, NJ, USA",
        "latitude": 40.719486,
        "longitude": -74.034878,
    },
    "bryant_park": {
        "label": "Bryant Park, Manhattan, NY, USA",
        "latitude": 40.753597,
        "longitude": -73.983233,
    },
    "newark_penn": {
        "label": "Newark Penn Station, Newark, NJ, USA",
        "latitude": 40.734722,
        "longitude": -74.164167,
    },
    "ny_penn": {
        "label": "Penn Station, New York, NY, USA",
        "latitude": 40.750568,
        "longitude": -73.993519,
    },
}

PRIMARY_MEETING_BLUEPRINTS = [
    {
        "title": "Weekly Planning Kickoff",
        "description": "Seeded weekly kickoff for client review demos.",
        "location_key": "stevens",
        "start_time": datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        "attendee_count": 6,
    },
    {
        "title": "Manhattan Client Check-In",
        "description": "Seeded cross-city client sync.",
        "location_key": "bryant_park",
        "start_time": datetime(2026, 4, 20, 10, 45, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 20, 11, 30, tzinfo=timezone.utc),
        "attendee_count": 5,
    },
    {
        "title": "Invitees Review",
        "description": "Seeded invitee coordination meeting.",
        "location_key": "babbio",
        "start_time": datetime(2026, 4, 21, 13, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 21, 14, 0, tzinfo=timezone.utc),
        "attendee_count": 7,
    },
    {
        "title": "Operations Sync",
        "description": "Seeded operations follow-up.",
        "location_key": "terminal",
        "start_time": datetime(2026, 4, 21, 15, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc),
        "attendee_count": 4,
    },
    {
        "title": "Design Review",
        "description": "Seeded design review for weekly calendar demos.",
        "location_key": "harborside",
        "start_time": datetime(2026, 4, 22, 9, 30, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc),
        "attendee_count": 8,
    },
    {
        "title": "Product Demo",
        "description": "Seeded product demo with student invitees.",
        "location_key": "stevens",
        "start_time": datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 22, 13, 0, tzinfo=timezone.utc),
        "attendee_count": 6,
    },
    {
        "title": "Stakeholder Workshop",
        "description": "Seeded workshop for the requested week.",
        "location_key": "ny_penn",
        "start_time": datetime(2026, 4, 23, 11, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 23, 12, 30, tzinfo=timezone.utc),
        "attendee_count": 9,
    },
    {
        "title": "Travel Follow-Up",
        "description": "Seeded short travel follow-up meeting.",
        "location_key": "stevens",
        "start_time": datetime(2026, 4, 23, 14, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 23, 14, 45, tzinfo=timezone.utc),
        "attendee_count": 4,
    },
    {
        "title": "Sprint Retro",
        "description": "Seeded retrospective for UI walkthroughs.",
        "location_key": "pier_a",
        "start_time": datetime(2026, 4, 24, 9, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
        "attendee_count": 6,
    },
    {
        "title": "Executive Debrief",
        "description": "Seeded end-of-week debrief.",
        "location_key": "newark_penn",
        "start_time": datetime(2026, 4, 24, 13, 30, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 24, 14, 30, tzinfo=timezone.utc),
        "attendee_count": 5,
    },
    {
        "title": "Weekend Planning Session",
        "description": "Seeded Saturday planning block.",
        "location_key": "stevens",
        "start_time": datetime(2026, 4, 25, 11, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc),
        "attendee_count": 5,
    },
]

GUEST_MEETING_BLUEPRINTS = [
    {
        "title": "Campus Ops Check-In",
        "description": "Seeded guest meeting that should surface an info travel warning from the default origin.",
        "location_key": "babbio",
        "start_time": datetime(2026, 5, 18, 13, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 18, 13, 45, tzinfo=timezone.utc),
        "attendee_count": 3,
    },
    {
        "title": "Harborside Partner Handoff",
        "description": "Seeded guest meeting with a tight travel window intended to show a caution warning.",
        "location_key": "harborside",
        "start_time": datetime(2026, 5, 18, 14, 10, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 18, 14, 45, tzinfo=timezone.utc),
        "attendee_count": 2,
    },
    {
        "title": "Newark Vendor Pickup",
        "description": "Seeded guest meeting intended to produce a critical travel warning.",
        "location_key": "newark_penn",
        "start_time": datetime(2026, 5, 18, 14, 55, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 18, 15, 35, tzinfo=timezone.utc),
        "attendee_count": 3,
    },
    {
        "title": "Terminal Planning Sync",
        "description": "Seeded guest meeting that starts a second travel-warning sequence later in the week.",
        "location_key": "terminal",
        "start_time": datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 20, 14, 45, tzinfo=timezone.utc),
        "attendee_count": 2,
    },
    {
        "title": "Midtown Design Review",
        "description": "Seeded guest meeting with a second caution-level travel window.",
        "location_key": "ny_penn",
        "start_time": datetime(2026, 5, 20, 15, 15, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 20, 16, 0, tzinfo=timezone.utc),
        "attendee_count": 3,
    },
    {
        "title": "Campus Wrap-Up",
        "description": "Seeded guest meeting that should force another critical travel warning before the day ends.",
        "location_key": "stevens",
        "start_time": datetime(2026, 5, 20, 16, 10, tzinfo=timezone.utc),
        "end_time": datetime(2026, 5, 20, 17, 0, tzinfo=timezone.utc),
        "attendee_count": 2,
    },
]

COLOR_PALETTE = [
    "#1d4ed8",
    "#0f766e",
    "#b45309",
    "#9333ea",
    "#dc2626",
    "#2563eb",
]

ATTENDEE_STATUS_CHOICES = ("invited", "accepted", "invited", "maybe", "declined")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed testaccount@stevens.edu, testguest@stevens.edu, a pool of @stevens.edu users, "
            "and demo meetings for the weeks of 2026-04-20 and 2026-05-18."
        )
    )
    parser.add_argument(
        "--user-count",
        type=int,
        default=DEFAULT_INVITEE_COUNT,
        help=f"Number of inviteable @stevens.edu users to generate (default: {DEFAULT_INVITEE_COUNT}).",
    )
    return parser.parse_args()


def ensure_user(
    db,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    default_location: str | None = None,
    default_location_latitude: float | None = None,
    default_location_longitude: float | None = None,
) -> User:
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email_norm,
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.first_name = first_name
        user.last_name = last_name
        user.email = email_norm
        user.is_active = True

    user.default_location = default_location
    user.default_location_latitude = default_location_latitude
    user.default_location_longitude = default_location_longitude

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
                provider_subject=email_norm,
                email=email_norm,
                email_verified=False,
            )
        )
    else:
        identity.provider_subject = email_norm
        identity.email = email_norm

    db.flush()
    return user


def build_invitee_profiles(user_count: int) -> list[dict[str, str]]:
    if user_count < 1:
        raise ValueError("user_count must be at least 1")

    rng = random.Random(PRIMARY_RANDOM_SEED)
    profiles: list[dict[str, str]] = []
    used_emails = {PRIMARY_EMAIL, GUEST_EMAIL}
    suffix = 1

    while len(profiles) < user_count:
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        email = f"{first_name}.{last_name}{suffix:02d}@stevens.edu".lower()
        suffix += 1

        if email in used_emails:
            continue

        used_emails.add(email)
        profiles.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": DEFAULT_INVITEE_PASSWORD,
            }
        )

    return profiles


def reset_seeded_week_meetings(
    db,
    *,
    calendar_id: int,
    organizer_id: int,
    week_start: datetime,
    week_end: datetime,
    seed_marker: str,
) -> None:
    meeting_ids = db.execute(
        text(
            """
            SELECT id
            FROM meetings
            WHERE calendar_id = :calendar_id
              AND created_by = :organizer_id
              AND start_time >= :week_start
              AND start_time < :week_end
              AND description LIKE :seed_marker
            """
        ),
        {
            "calendar_id": calendar_id,
            "organizer_id": organizer_id,
            "week_start": week_start,
            "week_end": week_end,
            "seed_marker": f"{seed_marker}%",
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


def choose_attendee_rows(
    rng: random.Random,
    *,
    invitee_ids: list[int],
    organizer_id: int,
    attendee_count: int,
) -> list[tuple[int, str]]:
    chosen_ids = rng.sample(invitee_ids, k=min(attendee_count, len(invitee_ids)))
    rows: list[tuple[int, str]] = [(organizer_id, "accepted")]
    for attendee_id in chosen_ids:
        status = rng.choice(ATTENDEE_STATUS_CHOICES)
        rows.append((attendee_id, status))
    return rows


def insert_meeting(
    db,
    *,
    calendar_id: int,
    organizer_id: int,
    seed_marker: str,
    title: str,
    description: str,
    location: dict[str, float | str],
    color: str,
    start_time: datetime,
    end_time: datetime,
    attendee_rows: list[tuple[int, str]],
) -> None:
    meeting_id = int(
        db.execute(
            text(
                """
                INSERT INTO meetings (
                    calendar_id,
                    title,
                    description,
                    location,
                    location_raw,
                    location_latitude,
                    location_longitude,
                    meeting_type,
                    color,
                    start_time,
                    end_time,
                    capacity,
                    setup_minutes,
                    cleanup_minutes,
                    status,
                    created_by
                )
                VALUES (
                    :calendar_id,
                    :title,
                    :description,
                    :location,
                    :location_raw,
                    :latitude,
                    :longitude,
                    'in_person',
                    :color,
                    :start_time,
                    :end_time,
                    NULL,
                    0,
                    0,
                    'confirmed',
                    :created_by
                )
                RETURNING id
                """
            ),
            {
                "calendar_id": calendar_id,
                "title": title,
                "description": f"{seed_marker} {description}",
                "location": location["label"],
                "location_raw": location["label"],
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "color": color,
                "start_time": start_time,
                "end_time": end_time,
                "created_by": organizer_id,
            },
        ).scalar_one()
    )

    for attendee_id, status in attendee_rows:
        db.execute(
            text(
                """
                INSERT INTO meeting_attendees (meeting_id, user_id, status)
                VALUES (:meeting_id, :user_id, :status)
                ON CONFLICT (meeting_id, user_id) DO UPDATE SET status = EXCLUDED.status
                """
            ),
            {
                "meeting_id": meeting_id,
                "user_id": attendee_id,
                "status": status,
            },
        )


def seed_week_for_user(
    db,
    *,
    user: User,
    meeting_blueprints: list[dict[str, object]],
    invitee_ids: list[int],
    seed_marker: str,
    random_seed: int,
    week_start: datetime,
    week_end: datetime,
) -> None:
    calendar_id = get_or_create_user_calendar(user.id, db)
    reset_seeded_week_meetings(
        db,
        calendar_id=calendar_id,
        organizer_id=user.id,
        week_start=week_start,
        week_end=week_end,
        seed_marker=seed_marker,
    )

    rng = random.Random(random_seed)
    for index, blueprint in enumerate(meeting_blueprints):
        location = LOCATIONS[str(blueprint["location_key"])]
        attendee_rows = choose_attendee_rows(
            rng,
            invitee_ids=invitee_ids,
            organizer_id=user.id,
            attendee_count=int(blueprint["attendee_count"]),
        )
        insert_meeting(
            db,
            calendar_id=calendar_id,
            organizer_id=user.id,
            seed_marker=seed_marker,
            title=str(blueprint["title"]),
            description=str(blueprint["description"]),
            location=location,
            color=COLOR_PALETTE[index % len(COLOR_PALETTE)],
            start_time=blueprint["start_time"],
            end_time=blueprint["end_time"],
            attendee_rows=attendee_rows,
        )


def main() -> None:
    args = parse_args()
    ensure_runtime_schema()

    db = SessionLocal()
    try:
        primary_location = LOCATIONS["stevens"]
        primary_user = ensure_user(
            db,
            first_name="Test",
            last_name="Account",
            email=PRIMARY_EMAIL,
            password=PRIMARY_PASSWORD,
            default_location=str(primary_location["label"]),
            default_location_latitude=float(primary_location["latitude"]),
            default_location_longitude=float(primary_location["longitude"]),
        )
        guest_user = ensure_user(
            db,
            first_name="Test",
            last_name="Guest",
            email=GUEST_EMAIL,
            password=GUEST_PASSWORD,
            default_location=str(primary_location["label"]),
            default_location_latitude=float(primary_location["latitude"]),
            default_location_longitude=float(primary_location["longitude"]),
        )

        invitee_profiles = build_invitee_profiles(args.user_count)
        invitees = [
            ensure_user(
                db,
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                email=profile["email"],
                password=profile["password"],
            )
            for profile in invitee_profiles
        ]

        invitee_ids = [invitee.id for invitee in invitees]
        seed_week_for_user(
            db,
            user=primary_user,
            meeting_blueprints=PRIMARY_MEETING_BLUEPRINTS,
            invitee_ids=invitee_ids,
            seed_marker=PRIMARY_SEED_MARKER,
            random_seed=PRIMARY_RANDOM_SEED,
            week_start=PRIMARY_WEEK_START,
            week_end=PRIMARY_WEEK_END,
        )
        seed_week_for_user(
            db,
            user=guest_user,
            meeting_blueprints=GUEST_MEETING_BLUEPRINTS,
            invitee_ids=invitee_ids,
            seed_marker=GUEST_SEED_MARKER,
            random_seed=GUEST_RANDOM_SEED,
            week_start=GUEST_WEEK_START,
            week_end=GUEST_WEEK_END,
        )

        db.commit()

        print("Seed complete.")
        print(f"Primary user: {PRIMARY_EMAIL}")
        print(f"Primary password: {PRIMARY_PASSWORD}")
        print(f"Guest user: {GUEST_EMAIL}")
        print(f"Guest password: {GUEST_PASSWORD}")
        print(f"Generated inviteable @stevens.edu users: {len(invitees)}")
        print(f"Invitee password: {DEFAULT_INVITEE_PASSWORD}")
        print("Primary week seeded: 2026-04-20 through 2026-04-25")
        print("Guest week seeded: 2026-05-18 through 2026-05-22")
        print("Sample invitees:")
        for invitee in invitees[:10]:
            print(f"  - {invitee.email}")
        if len(invitees) > 10:
            print(f"  ... and {len(invitees) - 10} more")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
