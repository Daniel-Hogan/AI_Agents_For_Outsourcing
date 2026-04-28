from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel


class NotificationPreferencesPayload(BaseModel):
    email: bool = True
    in_app: bool = True
    meeting_reminders: bool = True
    group_activity: bool = True
    weekly_digest: bool = False
    digest_frequency: Literal["daily", "weekly"] = "weekly"
    quiet_hours_enabled: bool = False
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None


class NotificationItem(BaseModel):
    id: int
    meeting_id: int | None
    channel: Literal["email", "in_app"]
    type: Literal["invite", "cancel", "update", "rsvp_update", "reminder"]
    title: str
    message: str
    status: Literal["pending", "sent", "failed", "read", "skipped"]
    created_at: datetime
    sent_at: datetime | None
    read_at: datetime | None


class NotificationBellItem(NotificationItem):
    meeting_title: str | None = None
    meeting_status: Literal["proposed", "confirmed", "cancelled"] | str | None = None
    current_status: Literal["invited", "accepted", "declined", "maybe"] | None = None
    is_unread: bool
    can_rsvp: bool = False
    open_url: str | None = None


class NotificationBellPayload(BaseModel):
    unread_count: int
    items: list[NotificationBellItem]


class PendingInviteItem(BaseModel):
    meeting_id: int
    title: str
    organizer_name: str
    organizer_email: str
    start_time: datetime
    end_time: datetime
    location: str | None
    current_status: Literal["invited", "accepted", "declined", "maybe"]
