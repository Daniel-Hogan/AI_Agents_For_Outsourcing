from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal


logger = logging.getLogger("app.notifications")

DEFAULT_NOTIFICATION_PREFERENCES = {
    "email": True,
    "in_app": True,
    "meeting_reminders": True,
    "group_activity": True,
    "weekly_digest": False,
    "digest_frequency": "weekly",
    "quiet_hours_enabled": False,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
}

BELL_LOOKBACK_HOURS = 24
BELL_DEFAULT_LIMIT = 20
REMINDER_LOOKAHEAD_MINUTES = 15
REMINDER_LOCK_ID = 2147483021


def get_or_create_notification_preferences(user_id: int, db: Session, *, commit: bool = True) -> dict:
    row = db.execute(
        text(
            """
            SELECT
                email_enabled,
                in_app_enabled,
                meeting_reminders_enabled,
                group_activity_enabled,
                weekly_digest_enabled,
                digest_frequency,
                quiet_hours_enabled,
                quiet_hours_start,
                quiet_hours_end
            FROM notification_preferences
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if row is None:
        db.execute(
            text(
                """
                INSERT INTO notification_preferences (
                    user_id,
                    email_enabled,
                    in_app_enabled,
                    meeting_reminders_enabled,
                    group_activity_enabled,
                    weekly_digest_enabled,
                    digest_frequency,
                    quiet_hours_enabled,
                    quiet_hours_start,
                    quiet_hours_end
                )
                VALUES (
                    :user_id,
                    :email_enabled,
                    :in_app_enabled,
                    :meeting_reminders_enabled,
                    :group_activity_enabled,
                    :weekly_digest_enabled,
                    :digest_frequency,
                    :quiet_hours_enabled,
                    :quiet_hours_start,
                    :quiet_hours_end
                )
                """
            ),
            {
                "user_id": user_id,
                "email_enabled": DEFAULT_NOTIFICATION_PREFERENCES["email"],
                "in_app_enabled": DEFAULT_NOTIFICATION_PREFERENCES["in_app"],
                "meeting_reminders_enabled": DEFAULT_NOTIFICATION_PREFERENCES["meeting_reminders"],
                "group_activity_enabled": DEFAULT_NOTIFICATION_PREFERENCES["group_activity"],
                "weekly_digest_enabled": DEFAULT_NOTIFICATION_PREFERENCES["weekly_digest"],
                "digest_frequency": DEFAULT_NOTIFICATION_PREFERENCES["digest_frequency"],
                "quiet_hours_enabled": DEFAULT_NOTIFICATION_PREFERENCES["quiet_hours_enabled"],
                "quiet_hours_start": DEFAULT_NOTIFICATION_PREFERENCES["quiet_hours_start"],
                "quiet_hours_end": DEFAULT_NOTIFICATION_PREFERENCES["quiet_hours_end"],
            },
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return DEFAULT_NOTIFICATION_PREFERENCES.copy()

    return {
        "email": row["email_enabled"],
        "in_app": row["in_app_enabled"],
        "meeting_reminders": row["meeting_reminders_enabled"],
        "group_activity": row["group_activity_enabled"],
        "weekly_digest": row["weekly_digest_enabled"],
        "digest_frequency": row["digest_frequency"],
        "quiet_hours_enabled": row["quiet_hours_enabled"],
        "quiet_hours_start": row["quiet_hours_start"],
        "quiet_hours_end": row["quiet_hours_end"],
    }


def update_notification_preferences(user_id: int, payload: dict, db: Session) -> dict:
    get_or_create_notification_preferences(user_id, db)
    db.execute(
        text(
            """
            UPDATE notification_preferences
            SET
                email_enabled = :email_enabled,
                in_app_enabled = :in_app_enabled,
                meeting_reminders_enabled = :meeting_reminders_enabled,
                group_activity_enabled = :group_activity_enabled,
                weekly_digest_enabled = :weekly_digest_enabled,
                digest_frequency = :digest_frequency,
                quiet_hours_enabled = :quiet_hours_enabled,
                quiet_hours_start = :quiet_hours_start,
                quiet_hours_end = :quiet_hours_end,
                updated_at = NOW()
            WHERE user_id = :user_id
            """
        ),
        {
            "user_id": user_id,
            "email_enabled": payload["email"],
            "in_app_enabled": payload["in_app"],
            "meeting_reminders_enabled": payload["meeting_reminders"],
            "group_activity_enabled": payload["group_activity"],
            "weekly_digest_enabled": payload["weekly_digest"],
            "digest_frequency": payload["digest_frequency"],
            "quiet_hours_enabled": payload["quiet_hours_enabled"],
            "quiet_hours_start": payload["quiet_hours_start"],
            "quiet_hours_end": payload["quiet_hours_end"],
        },
    )
    db.commit()
    return get_or_create_notification_preferences(user_id, db)


def _insert_notification(
    *,
    user_id: int,
    meeting_id: int | None,
    channel: str,
    notification_type: str,
    title: str,
    message: str,
    status: str,
    db: Session,
    provider_message_id: str | None = None,
    error_message: str | None = None,
    sent_at: datetime | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO notifications (
                user_id,
                meeting_id,
                channel,
                type,
                title,
                message,
                status,
                provider_message_id,
                error_message,
                sent_at
            )
            VALUES (
                :user_id,
                :meeting_id,
                :channel,
                :type,
                :title,
                :message,
                :status,
                :provider_message_id,
                :error_message,
                :sent_at
            )
            """
        ),
        {
            "user_id": user_id,
            "meeting_id": meeting_id,
            "channel": channel,
            "type": notification_type,
            "title": title,
            "message": message,
            "status": status,
            "provider_message_id": provider_message_id,
            "error_message": error_message,
            "sent_at": sent_at,
        },
    )


def _notification_window_start(now: datetime | None = None) -> datetime:
    reference_time = now or datetime.now(timezone.utc)
    return reference_time - timedelta(hours=BELL_LOOKBACK_HOURS)


def _notification_open_url(meeting_id: int | None) -> str | None:
    if meeting_id is None:
        return None
    return f"/meetings/{meeting_id}"


def _serialize_bell_item(row: dict[str, Any]) -> dict[str, Any]:
    current_status = row.get("current_status")
    meeting_status = row.get("meeting_status") or "confirmed"
    notification_type = row["type"]
    can_rsvp = notification_type == "invite" and current_status == "invited" and meeting_status != "cancelled"

    return {
        "id": int(row["id"]),
        "meeting_id": int(row["meeting_id"]) if row.get("meeting_id") is not None else None,
        "channel": row["channel"],
        "type": notification_type,
        "title": row["title"],
        "message": row["message"],
        "status": row["status"],
        "created_at": row["created_at"],
        "sent_at": row["sent_at"],
        "read_at": row["read_at"],
        "meeting_title": row.get("meeting_title"),
        "meeting_status": meeting_status,
        "current_status": current_status,
        "is_unread": row.get("read_at") is None,
        "can_rsvp": can_rsvp,
        "open_url": _notification_open_url(
            int(row["meeting_id"]) if row.get("meeting_id") is not None else None
        ),
    }


def get_notification_bell(user_id: int, db: Session, *, limit: int = BELL_DEFAULT_LIMIT, now: datetime | None = None) -> dict:
    window_start = _notification_window_start(now)
    params = {
        "user_id": user_id,
        "window_start": window_start,
        "limit": limit,
    }

    unread_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM notifications
                WHERE user_id = :user_id
                  AND channel = 'in_app'
                  AND read_at IS NULL
                  AND created_at >= :window_start
                """
            ),
            params,
        ).scalar_one()
    )

    rows = db.execute(
        text(
            """
            SELECT
                n.id,
                n.meeting_id,
                n.channel,
                n.type,
                n.title,
                n.message,
                n.status,
                n.created_at,
                n.sent_at,
                n.read_at,
                m.title AS meeting_title,
                COALESCE(m.status, 'confirmed') AS meeting_status,
                ma.status AS current_status
            FROM notifications n
            LEFT JOIN meetings m ON m.id = n.meeting_id
            LEFT JOIN meeting_attendees ma
              ON ma.meeting_id = n.meeting_id
             AND ma.user_id = :user_id
            WHERE n.user_id = :user_id
              AND n.channel = 'in_app'
              AND n.created_at >= :window_start
            ORDER BY n.created_at DESC, n.id DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()

    return {
        "unread_count": unread_count,
        "items": [_serialize_bell_item(dict(row)) for row in rows],
    }


def mark_notification_read(notification_id: int, user_id: int, db: Session) -> dict | None:
    row = db.execute(
        text(
            """
            UPDATE notifications
            SET status = 'read', read_at = NOW()
            WHERE id = :notification_id
              AND user_id = :user_id
              AND channel = 'in_app'
            RETURNING id, meeting_id, channel, type, title, message, status, created_at, sent_at, read_at
            """
        ),
        {"notification_id": notification_id, "user_id": user_id},
    ).mappings().first()
    if row is None:
        return None
    db.commit()
    return dict(row)


def mark_recent_notifications_read(
    user_id: int,
    db: Session,
    *,
    notification_ids: list[int] | None = None,
    now: datetime | None = None,
) -> int:
    window_start = _notification_window_start(now)

    if notification_ids:
        result = db.execute(
            text(
                """
                UPDATE notifications
                SET status = 'read', read_at = NOW()
                WHERE user_id = :user_id
                  AND channel = 'in_app'
                  AND created_at >= :window_start
                  AND read_at IS NULL
                  AND id = ANY(:notification_ids)
                """
            ),
            {
                "user_id": user_id,
                "window_start": window_start,
                "notification_ids": notification_ids,
            },
        )
    else:
        result = db.execute(
            text(
                """
                UPDATE notifications
                SET status = 'read', read_at = NOW()
                WHERE user_id = :user_id
                  AND channel = 'in_app'
                  AND created_at >= :window_start
                  AND read_at IS NULL
                """
            ),
            {"user_id": user_id, "window_start": window_start},
        )

    db.commit()
    return int(result.rowcount or 0)


def open_notification_bell(user_id: int, db: Session, *, limit: int = BELL_DEFAULT_LIMIT, now: datetime | None = None) -> dict:
    bell = get_notification_bell(user_id, db, limit=limit, now=now)
    unread_ids = [int(item["id"]) for item in bell["items"] if item["is_unread"]]
    if unread_ids:
        mark_recent_notifications_read(user_id, db, notification_ids=unread_ids, now=now)
    return get_notification_bell(user_id, db, limit=limit, now=now)


def _format_person_name(first_name: str | None, last_name: str | None, email: str | None, fallback: str) -> str:
    name = " ".join(part.strip() for part in [first_name or "", last_name or ""] if part and part.strip()).strip()
    return name or email or fallback


def _format_meeting_window(start_time: datetime, end_time: datetime) -> str:
    start_utc = start_time.astimezone(timezone.utc)
    end_utc = end_time.astimezone(timezone.utc)
    if start_utc.date() == end_utc.date():
        return f"{start_utc:%b %d, %Y %I:%M %p} to {end_utc:%I:%M %p} UTC"
    return f"{start_utc:%b %d, %Y %I:%M %p} to {end_utc:%b %d, %Y %I:%M %p} UTC"


def _load_meeting_context(meeting_id: int, db: Session) -> tuple[dict, list[dict]]:
    meeting = db.execute(
        text(
            """
            SELECT
                m.id,
                m.title,
                m.location,
                COALESCE(m.meeting_type, 'in_person') AS meeting_type,
                COALESCE(m.status, 'confirmed') AS status,
                m.start_time,
                m.end_time,
                m.created_by,
                creator.first_name AS organizer_first_name,
                creator.last_name AS organizer_last_name,
                creator.email AS organizer_email
            FROM meetings m
            LEFT JOIN users creator ON creator.id = m.created_by
            WHERE m.id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if meeting is None:
        raise ValueError(f"Meeting {meeting_id} not found")

    attendees = db.execute(
        text(
            """
            SELECT
                ma.user_id,
                ma.status,
                u.email,
                u.first_name,
                u.last_name
            FROM meeting_attendees ma
            JOIN users u ON u.id = ma.user_id
            WHERE ma.meeting_id = :meeting_id
            ORDER BY ma.user_id ASC
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().all()
    return dict(meeting), [dict(row) for row in attendees]


def _notification_copy(notification_type: str, meeting: dict) -> tuple[str, str]:
    organizer_name = _format_person_name(
        meeting.get("organizer_first_name"),
        meeting.get("organizer_last_name"),
        meeting.get("organizer_email"),
        "Organizer",
    )
    meeting_window = _format_meeting_window(meeting["start_time"], meeting["end_time"])
    location_label = (
        meeting["location"]
        or ("Virtual meeting" if meeting["meeting_type"] == "virtual" else "Location TBD")
    )

    if notification_type == "invite":
        title = f"Invitation: {meeting['title']}"
        message = f"{organizer_name} invited you to {meeting['title']} on {meeting_window}. {location_label}."
    elif notification_type == "update":
        title = f"Updated: {meeting['title']}"
        message = f"{meeting['title']} was updated by {organizer_name}. New time: {meeting_window}. {location_label}."
    elif notification_type == "cancel":
        title = f"Cancelled: {meeting['title']}"
        message = f"{organizer_name} cancelled {meeting['title']} that was scheduled for {meeting_window}."
    elif notification_type == "reminder":
        title = f"Starting soon: {meeting['title']}"
        message = (
            f"{meeting['title']} starts in about {REMINDER_LOOKAHEAD_MINUTES} minutes on {meeting_window}. "
            f"{location_label}."
        )
    else:
        raise ValueError(f"Unsupported notification type: {notification_type}")

    return title, message


def _send_email_notification(
    *,
    user_id: int,
    recipient_email: str,
    meeting_id: int | None,
    notification_type: str,
    title: str,
    message: str,
    db: Session,
) -> None:
    now = datetime.now(timezone.utc)
    if not settings.resend_api_key or not settings.email_from_address:
        _insert_notification(
            user_id=user_id,
            meeting_id=meeting_id,
            channel="email",
            notification_type=notification_type,
            title=title,
            message=message,
            status="skipped",
            db=db,
            error_message="Email provider not configured",
            sent_at=now,
        )
        return

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{settings.email_from_name} <{settings.email_from_address}>",
                "to": [recipient_email],
                "subject": title,
                "html": (
                    f"<p>{message}</p>"
                    f"<p><a href=\"{settings.app_base_url}/meetings\">Open Scheduler AI</a></p>"
                ),
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        _insert_notification(
            user_id=user_id,
            meeting_id=meeting_id,
            channel="email",
            notification_type=notification_type,
            title=title,
            message=message,
            status="sent",
            db=db,
            provider_message_id=payload.get("id"),
            sent_at=now,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to send email notification for user_id=%s meeting_id=%s: %s", user_id, meeting_id, exc)
        _insert_notification(
            user_id=user_id,
            meeting_id=meeting_id,
            channel="email",
            notification_type=notification_type,
            title=title,
            message=message,
            status="failed",
            db=db,
            error_message=str(exc),
        )


def _notify_attendees(
    meeting_id: int,
    notification_type: str,
    db: Session,
    attendee_user_ids: list[int] | None = None,
) -> None:
    meeting, attendees = _load_meeting_context(meeting_id, db)
    title, message = _notification_copy(notification_type, meeting)
    allowed_user_ids = set(attendee_user_ids or [])

    for attendee in attendees:
        if attendee["user_id"] == meeting["created_by"]:
            continue
        if allowed_user_ids and attendee["user_id"] not in allowed_user_ids:
            continue

        preferences = get_or_create_notification_preferences(attendee["user_id"], db, commit=False)
        if preferences["in_app"]:
            _insert_notification(
                user_id=attendee["user_id"],
                meeting_id=meeting_id,
                channel="in_app",
                notification_type=notification_type,
                title=title,
                message=message,
                status="sent",
                db=db,
                sent_at=datetime.now(timezone.utc),
            )

        if preferences["email"]:
            _send_email_notification(
                user_id=attendee["user_id"],
                recipient_email=attendee["email"],
                meeting_id=meeting_id,
                notification_type=notification_type,
                title=title,
                message=message,
                db=db,
            )

    db.commit()


def notify_meeting_invite(meeting_id: int, db: Session, attendee_user_ids: list[int] | None = None) -> None:
    _notify_attendees(meeting_id, "invite", db, attendee_user_ids=attendee_user_ids)


def notify_meeting_updated(meeting_id: int, db: Session) -> None:
    _notify_attendees(meeting_id, "update", db)


def notify_meeting_cancelled(meeting_id: int, db: Session) -> None:
    _notify_attendees(meeting_id, "cancel", db)


def _load_due_meeting_ids(db: Session, *, now: datetime) -> list[int]:
    rows = db.execute(
        text(
            """
            SELECT id
            FROM meetings
            WHERE COALESCE(status, 'confirmed') <> 'cancelled'
              AND start_time > :now
              AND start_time <= :deadline
            ORDER BY start_time ASC, id ASC
            """
        ),
        {
            "now": now,
            "deadline": now + timedelta(minutes=REMINDER_LOOKAHEAD_MINUTES),
        },
    ).scalars().all()
    return [int(meeting_id) for meeting_id in rows]


def _build_reminder_recipients(meeting: dict, attendees: list[dict]) -> list[dict]:
    recipients: dict[int, dict[str, Any]] = {}

    organizer_id = meeting.get("created_by")
    if organizer_id is not None:
        recipients[int(organizer_id)] = {
            "user_id": int(organizer_id),
            "status": "accepted",
            "email": meeting.get("organizer_email"),
            "first_name": meeting.get("organizer_first_name"),
            "last_name": meeting.get("organizer_last_name"),
        }

    for attendee in attendees:
        if attendee["status"] not in {"invited", "accepted", "maybe"}:
            continue
        recipients[int(attendee["user_id"])] = dict(attendee)

    return list(recipients.values())


def _reminder_exists(*, user_id: int, meeting_id: int, db: Session) -> bool:
    return bool(
        db.execute(
            text(
                """
                SELECT 1
                FROM notifications
                WHERE user_id = :user_id
                  AND meeting_id = :meeting_id
                  AND channel = 'in_app'
                  AND type = 'reminder'
                LIMIT 1
                """
            ),
            {"user_id": user_id, "meeting_id": meeting_id},
        ).scalar_one_or_none()
    )


def create_due_reminder_notifications(db: Session, *, now: datetime | None = None) -> int:
    now_value = now or datetime.now(timezone.utc)
    acquired_lock = bool(
        db.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
            {"lock_id": REMINDER_LOCK_ID},
        ).scalar_one()
    )
    if not acquired_lock:
        db.rollback()
        return 0

    try:
        created_count = 0
        for meeting_id in _load_due_meeting_ids(db, now=now_value):
            meeting, attendees = _load_meeting_context(meeting_id, db)
            title, message = _notification_copy("reminder", meeting)

            for recipient in _build_reminder_recipients(meeting, attendees):
                user_id = int(recipient["user_id"])
                preferences = get_or_create_notification_preferences(user_id, db, commit=False)
                if not preferences["in_app"] or not preferences["meeting_reminders"]:
                    continue
                if _reminder_exists(user_id=user_id, meeting_id=meeting_id, db=db):
                    continue

                _insert_notification(
                    user_id=user_id,
                    meeting_id=meeting_id,
                    channel="in_app",
                    notification_type="reminder",
                    title=title,
                    message=message,
                    status="sent",
                    db=db,
                    sent_at=now_value,
                )
                created_count += 1

        db.commit()
        return created_count
    except Exception:
        db.rollback()
        raise


async def _notification_scheduler_loop(stop_event: asyncio.Event, *, poll_seconds: int) -> None:
    try:
        while not stop_event.is_set():
            db = SessionLocal()
            try:
                create_due_reminder_notifications(db)
            except Exception:
                logger.exception("Notification reminder scheduler tick failed")
            finally:
                db.close()

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise


def start_notification_scheduler(app: Any, *, poll_seconds: int = 60) -> asyncio.Task[Any]:
    existing_task = getattr(app.state, "notification_scheduler_task", None)
    if existing_task is not None and not existing_task.done():
        return existing_task

    stop_event = asyncio.Event()
    task = asyncio.create_task(_notification_scheduler_loop(stop_event, poll_seconds=poll_seconds))
    app.state.notification_scheduler_stop_event = stop_event
    app.state.notification_scheduler_task = task
    return task


async def stop_notification_scheduler(app: Any) -> None:
    stop_event = getattr(app.state, "notification_scheduler_stop_event", None)
    task = getattr(app.state, "notification_scheduler_task", None)

    if stop_event is not None:
        stop_event.set()

    if task is None:
        return

    try:
        await asyncio.wait_for(task, timeout=2)
    except asyncio.TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
