from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.api import meetings as meetings_api
from app.core.config import settings
from app.models import User
from app.schemas.assistant import (
    AssistantDraftAction,
    AssistantInviteeCandidate,
    AssistantMessageItem,
    AssistantResponse,
    AssistantThreadDetail,
    AssistantThreadSummary,
    AssistantToolResult,
)
from app.schemas.meetings import MeetingCreate, MeetingUpdate
from app.services.notifications import get_or_create_notification_preferences
from app.services.recommendations import recommend_common_slots


logger = logging.getLogger("app.assistant")

MAX_STORED_MESSAGES = 80
APP_LOCAL_TIMEZONE = ZoneInfo("America/New_York")


ASSISTANT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_user_profile",
            "description": "Get the authenticated scheduler user's profile.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_preferences",
            "description": "Get the authenticated user's notification and scheduling preferences.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_availability",
            "description": "Get weekly availability for the current user or a same-group user.",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_group_availability",
            "description": "Get member availability for a group the requester belongs to.",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_invitees",
            "description": "Search inviteable same-group users by name or email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "selected_user_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_meetings",
            "description": "List meetings visible to the requester.",
            "parameters": {
                "type": "object",
                "properties": {"include_cancelled": {"type": "boolean"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_meeting_details",
            "description": "Get details for a meeting visible to the requester.",
            "parameters": {
                "type": "object",
                "properties": {"meeting_id": {"type": "integer"}},
                "required": ["meeting_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_meeting_draft",
            "description": "Create a pending meeting draft. This never writes the real meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_type": {"type": "string", "enum": ["in_person", "virtual"]},
                    "start_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "end_time": {"type": "string", "description": "ISO 8601 datetime"},
                    "attendee_emails": {"type": "array", "items": {"type": "string"}},
                    "attendee_user_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["title", "start_time", "end_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_meeting_draft",
            "description": "Create a pending draft to update an existing meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_type": {"type": "string", "enum": ["in_person", "virtual"]},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "attendee_emails": {"type": "array", "items": {"type": "string"}},
                    "attendee_user_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["meeting_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_meeting_draft",
            "description": "Create a pending draft to cancel a meeting.",
            "parameters": {
                "type": "object",
                "properties": {"meeting_id": {"type": "integer"}},
                "required": ["meeting_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_meeting_times",
            "description": "Recommend common available meeting slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attendee_emails": {"type": "array", "items": {"type": "string"}},
                    "attendee_user_ids": {"type": "array", "items": {"type": "integer"}},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "duration_minutes": {"type": "integer", "minimum": 15, "maximum": 480},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["start_date", "end_date", "duration_minutes"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_draft_action",
            "description": "Confirm a draft action. Only available through the confirm endpoint.",
            "parameters": {
                "type": "object",
                "properties": {"draft_action_id": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _coerce_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


def _display_name(row: dict[str, Any]) -> str:
    first = str(row.get("first_name") or "").strip()
    last = str(row.get("last_name") or "").strip()
    name = " ".join(part for part in (first, last) if part)
    return name or str(row.get("email") or "")


def _message(role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "role": role,
        "content": content,
        "created_at": _utc_now().isoformat(),
        "metadata": metadata or {},
    }


def _message_item(payload: dict[str, Any]) -> AssistantMessageItem:
    return AssistantMessageItem(
        role=payload.get("role", "assistant"),
        content=payload.get("content", ""),
        created_at=payload.get("created_at", _utc_now().isoformat()),
        metadata=payload.get("metadata") or {},
    )


def _assistant_system_prompt() -> str:
    return (
        "You are Scheduler AI, a backend scheduling assistant. "
        "You help authenticated users schedule, update, and cancel meetings. "
        "Use tools for all scheduling facts. Do not claim that a meeting was created, updated, or cancelled "
        "unless a confirm endpoint result is present. Create draft actions when enough details are known. "
        "Ask concise follow-up questions when attendees, date, time, or permissions are ambiguous. "
        "Current UTC date is "
        f"{_utc_now().date().isoformat()}."
    )


def _load_messages(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_coerce_json(row.get("messages_json"), []))[-MAX_STORED_MESSAGES:]


def _write_messages(db: Session, *, thread_id: int, user_id: int, messages: list[dict[str, Any]]) -> None:
    db.execute(
        text(
            """
            UPDATE assistant_threads
            SET messages_json = CAST(:messages_json AS JSONB),
                updated_at = NOW()
            WHERE id = :thread_id AND user_id = :user_id
            """
        ),
        {
            "thread_id": thread_id,
            "user_id": user_id,
            "messages_json": json.dumps(_json_safe(messages[-MAX_STORED_MESSAGES:])),
        },
    )


def _thread_row(db: Session, *, thread_id: int, user_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT id, user_id, title, messages_json, openai_thread_id, created_at, updated_at
            FROM assistant_threads
            WHERE id = :thread_id AND user_id = :user_id
            """
        ),
        {"thread_id": thread_id, "user_id": user_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    return dict(row)


def _pending_draft_row(db: Session, *, thread_id: int, user_id: int, draft_action_id: int | None = None) -> dict[str, Any] | None:
    extra = ""
    params: dict[str, Any] = {"thread_id": thread_id, "user_id": user_id}
    if draft_action_id is not None:
        extra = " AND id = :draft_action_id"
        params["draft_action_id"] = draft_action_id

    return db.execute(
        text(
            f"""
            SELECT id, thread_id, user_id, action_type, status, target_meeting_id,
                   payload_json, result_json, created_at, updated_at
            FROM assistant_draft_actions
            WHERE thread_id = :thread_id
              AND user_id = :user_id
              AND status = 'pending'
              {extra}
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        params,
    ).mappings().first()


def _draft_model(row: dict[str, Any] | None) -> AssistantDraftAction | None:
    if row is None:
        return None
    row_dict = dict(row)
    return AssistantDraftAction(
        id=int(row_dict["id"]),
        thread_id=int(row_dict["thread_id"]),
        action_type=row_dict["action_type"],
        status=row_dict["status"],
        payload=_coerce_json(row_dict.get("payload_json"), {}),
        target_meeting_id=row_dict.get("target_meeting_id"),
        created_at=row_dict["created_at"],
        updated_at=row_dict["updated_at"],
    )


def _thread_summary(row: dict[str, Any], db: Session) -> AssistantThreadSummary:
    return AssistantThreadSummary(
        id=int(row["id"]),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        pending_draft=_draft_model(
            _pending_draft_row(db, thread_id=int(row["id"]), user_id=int(row["user_id"]))
        ),
    )


def create_thread(db: Session, *, user: User, title: str | None = None) -> AssistantThreadSummary:
    row = db.execute(
        text(
            """
            INSERT INTO assistant_threads (user_id, title)
            VALUES (:user_id, :title)
            RETURNING id, user_id, title, messages_json, created_at, updated_at
            """
        ),
        {"user_id": user.id, "title": (title or "New scheduling chat").strip()[:120]},
    ).mappings().one()
    db.commit()
    return _thread_summary(dict(row), db)


def list_threads(db: Session, *, user: User) -> list[AssistantThreadSummary]:
    rows = db.execute(
        text(
            """
            SELECT id, user_id, title, messages_json, created_at, updated_at
            FROM assistant_threads
            WHERE user_id = :user_id
            ORDER BY updated_at DESC, id DESC
            """
        ),
        {"user_id": user.id},
    ).mappings().all()
    return [_thread_summary(dict(row), db) for row in rows]


def get_thread_detail(db: Session, *, user: User, thread_id: int) -> AssistantThreadDetail:
    row = _thread_row(db, thread_id=thread_id, user_id=user.id)
    summary = _thread_summary(row, db)
    return AssistantThreadDetail(
        **summary.model_dump(),
        messages=[_message_item(message) for message in _load_messages(row)],
    )


def _user_group_ids(db: Session, *, user_id: int) -> list[int]:
    return [
        int(group_id)
        for group_id in db.execute(
            text("SELECT group_id FROM group_memberships WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).scalars().all()
    ]


def _shared_group_ids(db: Session, *, left_user_id: int, right_user_id: int) -> list[int]:
    rows = db.execute(
        text(
            """
            SELECT left_gm.group_id
            FROM group_memberships left_gm
            JOIN group_memberships right_gm ON right_gm.group_id = left_gm.group_id
            WHERE left_gm.user_id = :left_user_id
              AND right_gm.user_id = :right_user_id
            ORDER BY left_gm.group_id
            """
        ),
        {"left_user_id": left_user_id, "right_user_id": right_user_id},
    ).scalars().all()
    return [int(group_id) for group_id in rows]


def _common_group_ids(db: Session, *, user_ids: list[int]) -> list[int]:
    unique_ids = sorted(set(int(user_id) for user_id in user_ids))
    if len(unique_ids) < 2:
        return []
    rows = db.execute(
        text(
            """
            SELECT group_id
            FROM group_memberships
            WHERE user_id IN :user_ids
            GROUP BY group_id
            HAVING COUNT(DISTINCT user_id) = :user_count
            ORDER BY group_id
            """
        ).bindparams(bindparam("user_ids", expanding=True)),
        {"user_ids": unique_ids, "user_count": len(unique_ids)},
    ).scalars().all()
    return [int(group_id) for group_id in rows]


def _load_users(db: Session, *, user_ids: list[int]) -> list[dict[str, Any]]:
    unique_ids = sorted(set(int(user_id) for user_id in user_ids))
    if not unique_ids:
        return []
    rows = db.execute(
        text(
            """
            SELECT id, email, first_name, last_name
            FROM users
            WHERE id IN :user_ids
            ORDER BY LOWER(email)
            """
        ).bindparams(bindparam("user_ids", expanding=True)),
        {"user_ids": unique_ids},
    ).mappings().all()
    return [dict(row) for row in rows]


def _resolve_user_ids_from_emails(db: Session, emails: list[str]) -> tuple[list[int], list[str]]:
    normalized = sorted({email.strip().lower() for email in emails if email and email.strip()})
    if not normalized:
        return [], []
    rows = db.execute(
        text(
            """
            SELECT id, LOWER(email) AS email
            FROM users
            WHERE LOWER(email) IN :emails
            """
        ).bindparams(bindparam("emails", expanding=True)),
        {"emails": normalized},
    ).mappings().all()
    found = {row["email"]: int(row["id"]) for row in rows}
    missing = [email for email in normalized if email not in found]
    return [found[email] for email in normalized if email in found], missing


def _validate_common_group_scope(db: Session, *, requester_id: int, attendee_user_ids: list[int]) -> list[int]:
    attendee_ids = sorted(set(int(user_id) for user_id in attendee_user_ids if int(user_id) != requester_id))
    if not attendee_ids:
        return []
    common_groups = _common_group_ids(db, user_ids=[requester_id, *attendee_ids])
    if not common_groups:
        raise HTTPException(
            status_code=403,
            detail="Invitees must all share at least one group with you and each other.",
        )
    return common_groups


def _candidate_from_row(db: Session, *, requester_id: int, row: dict[str, Any]) -> AssistantInviteeCandidate:
    shared_group_ids = _shared_group_ids(db, left_user_id=requester_id, right_user_id=int(row["id"]))
    return AssistantInviteeCandidate(
        user_id=int(row["id"]),
        email=row["email"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        display_name=_display_name(row),
        shared_group_ids=shared_group_ids,
    )


def search_invitees_tool(db: Session, *, user: User, query: str = "", selected_user_ids: list[int] | None = None) -> list[AssistantInviteeCandidate]:
    selected_ids = sorted(set(selected_user_ids or []))
    if selected_ids:
        _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=selected_ids)
        return [
            _candidate_from_row(db, requester_id=user.id, row=row)
            for row in _load_users(db, user_ids=selected_ids)
            if int(row["id"]) != user.id
        ]

    group_ids = _user_group_ids(db, user_id=user.id)
    if not group_ids:
        return []

    query_value = query.strip()
    params = {"user_id": user.id, "group_ids": group_ids, "query": f"%{query_value}%"}
    query_filter = ""
    if query_value:
        query_filter = """
          AND (
            u.email ILIKE :query
            OR u.first_name ILIKE :query
            OR u.last_name ILIKE :query
            OR CONCAT(u.first_name, ' ', u.last_name) ILIKE :query
          )
        """
    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT u.id, u.email, u.first_name, u.last_name, LOWER(u.email) AS email_sort
            FROM users u
            JOIN group_memberships gm ON gm.user_id = u.id
            WHERE gm.group_id IN :group_ids
              AND u.id <> :user_id
              AND u.is_active = TRUE
              {query_filter}
            ORDER BY email_sort
            LIMIT 10
            """
        ).bindparams(bindparam("group_ids", expanding=True)),
        params,
    ).mappings().all()
    return [_candidate_from_row(db, requester_id=user.id, row=dict(row)) for row in rows]


def _availability_for_user(db: Session, *, requester_id: int, user_id: int) -> list[dict[str, Any]]:
    if user_id != requester_id and not _shared_group_ids(db, left_user_id=requester_id, right_user_id=user_id):
        raise HTTPException(status_code=403, detail="Availability is only visible for same-group users.")
    rows = db.execute(
        text(
            """
            SELECT id, user_id, day_of_week, start_time::text AS start_time, end_time::text AS end_time
            FROM time_slot_preferences
            WHERE user_id = :user_id
            ORDER BY day_of_week ASC, start_time ASC
            """
        ),
        {"user_id": user_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_group_availability_tool(db: Session, *, user: User, group_id: int) -> dict[str, Any]:
    role = db.execute(
        text(
            """
            SELECT role
            FROM group_memberships
            WHERE user_id = :user_id AND group_id = :group_id
            """
        ),
        {"user_id": user.id, "group_id": group_id},
    ).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    rows = db.execute(
        text(
            """
            SELECT
                u.id AS user_id,
                u.email,
                u.first_name,
                u.last_name,
                gm.role,
                tsp.id AS preference_id,
                tsp.day_of_week,
                tsp.start_time::text AS start_time,
                tsp.end_time::text AS end_time
            FROM group_memberships gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN time_slot_preferences tsp ON tsp.user_id = u.id
            WHERE gm.group_id = :group_id
            ORDER BY LOWER(u.email), tsp.day_of_week, tsp.start_time
            """
        ),
        {"group_id": group_id},
    ).mappings().all()

    members: dict[int, dict[str, Any]] = {}
    for row in rows:
        user_id = int(row["user_id"])
        member = members.setdefault(
            user_id,
            {
                "user_id": user_id,
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "role": row["role"],
                "availability": [],
            },
        )
        if row["preference_id"] is not None:
            member["availability"].append(
                {
                    "id": int(row["preference_id"]),
                    "day_of_week": int(row["day_of_week"]),
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                }
            )
    return {"group_id": group_id, "requester_role": role, "members": list(members.values())}


def _active_pending_draft(db: Session, *, thread_id: int, user_id: int) -> AssistantDraftAction | None:
    return _draft_model(_pending_draft_row(db, thread_id=thread_id, user_id=user_id))


def _store_draft(
    db: Session,
    *,
    thread_id: int,
    user_id: int,
    action_type: str,
    payload: dict[str, Any],
    target_meeting_id: int | None = None,
) -> AssistantDraftAction:
    db.execute(
        text(
            """
            UPDATE assistant_draft_actions
            SET status = 'discarded', updated_at = NOW()
            WHERE thread_id = :thread_id
              AND user_id = :user_id
              AND status = 'pending'
            """
        ),
        {"thread_id": thread_id, "user_id": user_id},
    )
    row = db.execute(
        text(
            """
            INSERT INTO assistant_draft_actions (
                thread_id, user_id, action_type, target_meeting_id, payload_json
            )
            VALUES (
                :thread_id, :user_id, :action_type, :target_meeting_id, CAST(:payload_json AS JSONB)
            )
            RETURNING id, thread_id, user_id, action_type, status, target_meeting_id,
                      payload_json, result_json, created_at, updated_at
            """
        ),
        {
            "thread_id": thread_id,
            "user_id": user_id,
            "action_type": action_type,
            "target_meeting_id": target_meeting_id,
            "payload_json": json.dumps(_json_safe(payload)),
        },
    ).mappings().one()
    db.flush()
    return _draft_model(dict(row))  # type: ignore[return-value]


def _draft_summary(draft: AssistantDraftAction) -> str:
    payload = draft.payload
    if draft.action_type == "create_meeting":
        attendees = payload.get("attendee_emails") or []
        attendee_copy = f" with {', '.join(attendees)}" if attendees else ""
        start_copy = _format_assistant_datetime(payload.get("start_time"))
        end_copy = _format_assistant_datetime(payload.get("end_time"))
        return (
            f"I drafted {payload.get('title', 'the meeting')}{attendee_copy} from "
            f"{start_copy} to {end_copy}. Confirm it when you are ready."
        )
    if draft.action_type == "update_meeting":
        return f"I drafted updates for meeting #{draft.target_meeting_id}. Confirm to apply them."
    return f"I drafted a cancellation for meeting #{draft.target_meeting_id}. Confirm to cancel it."


def _format_assistant_datetime(value: Any) -> str:
    if not value:
        return "the selected time"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local_value = parsed.astimezone(APP_LOCAL_TIMEZONE)
    return f"{local_value:%b} {local_value.day}, {local_value.year} at {local_value.strftime('%I:%M %p').lstrip('0')}"


def _normalize_draft_payload(
    db: Session,
    *,
    user: User,
    payload: dict[str, Any],
    require_window: bool,
) -> dict[str, Any]:
    attendee_ids = [int(value) for value in payload.get("attendee_user_ids") or []]
    email_ids, missing_emails = _resolve_user_ids_from_emails(db, [str(value) for value in payload.get("attendee_emails") or []])
    if missing_emails:
        raise HTTPException(status_code=400, detail={"message": "Some invitees are not registered.", "missing_emails": missing_emails})

    attendee_ids = sorted(set([*attendee_ids, *email_ids]))
    _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=attendee_ids)
    attendee_users = _load_users(db, user_ids=attendee_ids)
    attendee_emails = [row["email"] for row in attendee_users if int(row["id"]) != user.id]

    normalized = {
        "title": str(payload.get("title") or "Meeting").strip(),
        "description": (str(payload.get("description")).strip() if payload.get("description") is not None else None),
        "location": (str(payload.get("location")).strip() if payload.get("location") is not None else None),
        "meeting_type": payload.get("meeting_type") if payload.get("meeting_type") in {"in_person", "virtual"} else "in_person",
        "attendee_user_ids": [int(row["id"]) for row in attendee_users if int(row["id"]) != user.id],
        "attendee_emails": attendee_emails,
    }
    if payload.get("start_time") is not None:
        normalized["start_time"] = str(payload["start_time"])
    if payload.get("end_time") is not None:
        normalized["end_time"] = str(payload["end_time"])

    if require_window and (not normalized.get("start_time") or not normalized.get("end_time")):
        raise HTTPException(status_code=400, detail="Start and end time are required.")
    return normalized


def create_meeting_draft_tool(db: Session, *, user: User, thread_id: int, **payload: Any) -> AssistantDraftAction:
    normalized = _normalize_draft_payload(db, user=user, payload=payload, require_window=True)
    try:
        MeetingCreate(
            title=normalized["title"],
            description=normalized.get("description"),
            location=normalized.get("location"),
            meeting_type=normalized["meeting_type"],
            start_time=normalized["start_time"],
            end_time=normalized["end_time"],
            attendee_emails=normalized["attendee_emails"],
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return _store_draft(db, thread_id=thread_id, user_id=user.id, action_type="create_meeting", payload=normalized)


def _require_editable_meeting(db: Session, *, user_id: int, meeting_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT m.id, m.created_by, COALESCE(m.status, 'confirmed') AS status,
                   c.owner_type, c.owner_id
            FROM meetings m
            JOIN calendars c ON c.id = m.calendar_id
            WHERE m.id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if row["created_by"] != user_id and not (row["owner_type"] == "user" and row["owner_id"] == user_id):
        raise HTTPException(status_code=403, detail="Only the organizer can change this meeting.")
    return dict(row)


def update_meeting_draft_tool(db: Session, *, user: User, thread_id: int, meeting_id: int, **payload: Any) -> AssistantDraftAction:
    _require_editable_meeting(db, user_id=user.id, meeting_id=meeting_id)
    normalized: dict[str, Any] = {"meeting_id": meeting_id}
    for key in ("title", "description", "location", "meeting_type", "start_time", "end_time"):
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        normalized[key] = value

    if "attendee_user_ids" in payload or "attendee_emails" in payload:
        attendee_ids = [int(value) for value in payload.get("attendee_user_ids") or []]
        email_ids, missing_emails = _resolve_user_ids_from_emails(db, [str(value) for value in payload.get("attendee_emails") or []])
        if missing_emails:
            raise HTTPException(
                status_code=400,
                detail={"message": "Some invitees are not registered.", "missing_emails": missing_emails},
            )
        attendee_ids = sorted(set([*attendee_ids, *email_ids]))
        _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=attendee_ids)
        attendee_users = _load_users(db, user_ids=attendee_ids)
        normalized["attendee_user_ids"] = [int(row["id"]) for row in attendee_users if int(row["id"]) != user.id]
        normalized["attendee_emails"] = [row["email"] for row in attendee_users if int(row["id"]) != user.id]

    try:
        MeetingUpdate(
            title=normalized.get("title"),
            description=normalized.get("description"),
            location=normalized.get("location"),
            meeting_type=normalized.get("meeting_type"),
            start_time=normalized.get("start_time"),
            end_time=normalized.get("end_time"),
            attendee_emails=normalized.get("attendee_emails"),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    normalized["meeting_id"] = meeting_id
    return _store_draft(
        db,
        thread_id=thread_id,
        user_id=user.id,
        action_type="update_meeting",
        payload=normalized,
        target_meeting_id=meeting_id,
    )


def cancel_meeting_draft_tool(db: Session, *, user: User, thread_id: int, meeting_id: int) -> AssistantDraftAction:
    _require_editable_meeting(db, user_id=user.id, meeting_id=meeting_id)
    return _store_draft(
        db,
        thread_id=thread_id,
        user_id=user.id,
        action_type="cancel_meeting",
        payload={"meeting_id": meeting_id},
        target_meeting_id=meeting_id,
    )


def _tool_result(name: str, ok: bool, data: Any = None, error: str | None = None) -> AssistantToolResult:
    return AssistantToolResult(name=name, ok=ok, data=_json_safe(data), error=error)


def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    db: Session,
    user: User,
    thread_id: int,
) -> AssistantToolResult:
    try:
        if name == "get_current_user_profile":
            return _tool_result(
                name,
                True,
                {
                    "user_id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "default_location": user.default_location,
                },
            )
        if name == "get_user_preferences":
            return _tool_result(
                name,
                True,
                {
                    "notification_preferences": get_or_create_notification_preferences(user.id, db),
                    "default_location": user.default_location,
                    "default_location_latitude": user.default_location_latitude,
                    "default_location_longitude": user.default_location_longitude,
                },
            )
        if name == "get_user_availability":
            target_user_id = int(arguments.get("user_id") or user.id)
            return _tool_result(name, True, _availability_for_user(db, requester_id=user.id, user_id=target_user_id))
        if name == "get_group_availability":
            return _tool_result(name, True, get_group_availability_tool(db, user=user, group_id=int(arguments["group_id"])))
        if name == "search_invitees":
            candidates = search_invitees_tool(
                db,
                user=user,
                query=str(arguments.get("query") or ""),
                selected_user_ids=[int(value) for value in arguments.get("selected_user_ids") or []],
            )
            return _tool_result(name, True, [candidate.model_dump() for candidate in candidates])
        if name == "list_user_meetings":
            meetings = meetings_api.list_meetings(
                include_cancelled=bool(arguments.get("include_cancelled") or False),
                current_user=user,
                db=db,
            )
            return _tool_result(name, True, meetings)
        if name == "get_meeting_details":
            return _tool_result(name, True, meetings_api.get_meeting(int(arguments["meeting_id"]), current_user=user, db=db))
        if name == "create_meeting_draft":
            draft = create_meeting_draft_tool(db, user=user, thread_id=thread_id, **arguments)
            return _tool_result(name, True, draft.model_dump())
        if name == "update_meeting_draft":
            meeting_id = int(arguments.pop("meeting_id"))
            draft = update_meeting_draft_tool(db, user=user, thread_id=thread_id, meeting_id=meeting_id, **arguments)
            return _tool_result(name, True, draft.model_dump())
        if name == "cancel_meeting_draft":
            draft = cancel_meeting_draft_tool(db, user=user, thread_id=thread_id, meeting_id=int(arguments["meeting_id"]))
            return _tool_result(name, True, draft.model_dump())
        if name == "recommend_meeting_times":
            attendee_ids = [int(value) for value in arguments.get("attendee_user_ids") or []]
            email_ids, missing = _resolve_user_ids_from_emails(db, [str(value) for value in arguments.get("attendee_emails") or []])
            if missing:
                raise HTTPException(status_code=400, detail={"missing_emails": missing})
            participant_ids = sorted(set([user.id, *attendee_ids, *email_ids]))
            _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=participant_ids)
            slots = recommend_common_slots(
                user_ids=participant_ids,
                start_date=date.fromisoformat(str(arguments["start_date"])),
                end_date=date.fromisoformat(str(arguments["end_date"])),
                duration_minutes=int(arguments["duration_minutes"]),
                max_results=int(arguments.get("max_results") or 5),
                db=db,
            )
            return _tool_result(name, True, {"recommendations": slots})
        if name == "confirm_draft_action":
            raise HTTPException(status_code=400, detail="Use POST /api/assistant/threads/{thread_id}/confirm to confirm drafts.")
        raise HTTPException(status_code=400, detail=f"Unknown assistant tool: {name}")
    except HTTPException as exc:
        return _tool_result(name, False, error=str(exc.detail))
    except Exception as exc:  # pragma: no cover - defensive boundary around model-chosen tools
        logger.exception("Assistant tool %s failed", name)
        return _tool_result(name, False, error=str(exc))


def _chat_messages_for_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": _assistant_system_prompt()},
        *[
            {"role": message["role"], "content": message["content"]}
            for message in messages[-20:]
            if message.get("role") in {"user", "assistant"}
        ],
    ]


def _call_openai_with_tools(
    *,
    messages: list[dict[str, Any]],
    db: Session,
    user: User,
    thread_id: int,
) -> tuple[str, list[AssistantToolResult]]:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - covered by package install, not unit tests
        raise RuntimeError("The openai package is not installed") from exc

    client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    client = OpenAI(**client_kwargs)

    openai_messages = _chat_messages_for_openai(messages)
    tool_results: list[AssistantToolResult] = []

    for _ in range(3):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=openai_messages,
            tools=ASSISTANT_TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []
        if not tool_calls:
            return assistant_message.content or "I am ready to help schedule that.", tool_results

        openai_messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            }
        )
        for call in tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = _execute_tool(call.function.name, arguments, db=db, user=user, thread_id=thread_id)
            tool_results.append(result)
            openai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result.model_dump(mode="json"), default=str),
                }
            )

    return "I gathered the scheduling details, but I need one more pass to finish that request.", tool_results


WEEKDAY_INDEXES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def _parse_time_parts(message: str) -> tuple[int, int] | None:
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", message, re.IGNORECASE)
    if not time_match:
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    meridiem = time_match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return hour, minute


def _future_date_for_month_day(month: int, day: int, year: int | None = None) -> date:
    today = _utc_now().astimezone(APP_LOCAL_TIMEZONE).date()
    resolved_year = year or today.year
    resolved = date(resolved_year, month, day)
    if year is None and resolved < today:
        resolved = date(resolved_year + 1, month, day)
    return resolved


def _future_date_for_day_number(day: int, year: int | None = None) -> date:
    today = _utc_now().astimezone(APP_LOCAL_TIMEZONE).date()
    resolved_year = year or today.year
    resolved_month = today.month
    resolved = date(resolved_year, resolved_month, day)
    if year is None and resolved < today:
        next_month = resolved_month + 1
        next_year = resolved_year
        if next_month > 12:
            next_month = 1
            next_year += 1
        resolved = date(next_year, next_month, day)
    return resolved


def _future_date_for_weekday(weekday_name: str) -> date:
    today = _utc_now().astimezone(APP_LOCAL_TIMEZONE).date()
    target_index = WEEKDAY_INDEXES[weekday_name.lower()]
    days_ahead = (target_index - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _local_datetime_to_utc(resolved: date, hour: int, minute: int, second: int = 0) -> datetime:
    local_value = datetime(resolved.year, resolved.month, resolved.day, hour, minute, second, tzinfo=APP_LOCAL_TIMEZONE)
    return local_value.astimezone(timezone.utc)


def _parse_start_time(message: str) -> datetime | None:
    iso_match = re.search(
        r"\b(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:?\d{2})?)?\b",
        message,
    )
    if iso_match:
        resolved = date.fromisoformat(iso_match.group(1))
        hour = int(iso_match.group(2) or "09")
        minute = int(iso_match.group(3) or "00")
        second = int(iso_match.group(4) or "00")
        tz_suffix = iso_match.group(5)
        if tz_suffix:
            normalized_tz = "+00:00" if tz_suffix == "Z" else tz_suffix
            if re.fullmatch(r"[+-]\d{4}", normalized_tz):
                normalized_tz = f"{normalized_tz[:3]}:{normalized_tz[3:]}"
            parsed = datetime.fromisoformat(
                f"{resolved.isoformat()}T{hour:02d}:{minute:02d}:{second:02d}{normalized_tz}"
            )
            return parsed.astimezone(timezone.utc)
        return _local_datetime_to_utc(resolved, hour, minute, second)

    time_parts = _parse_time_parts(message)
    if not time_parts:
        return None
    hour, minute = time_parts

    date_match = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
        message,
        re.IGNORECASE,
    )
    month_names = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    if date_match:
        month = month_names[date_match.group(1)[:3].lower()]
        day = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else None
        resolved = _future_date_for_month_day(month, day, year)
        return _local_datetime_to_utc(resolved, hour, minute)

    weekday_day_match = re.search(
        r"\b(?:next\s+)?(mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b(?:,?\s+(?:the\s+)?)?(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
        message,
        re.IGNORECASE,
    )
    if weekday_day_match:
        day = int(weekday_day_match.group(2))
        year = int(weekday_day_match.group(3)) if weekday_day_match.group(3) else None
        resolved = _future_date_for_day_number(day, year)
        return _local_datetime_to_utc(resolved, hour, minute)

    weekday_match = re.search(
        r"\b(?:next\s+)?(mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
        message,
        re.IGNORECASE,
    )
    if weekday_match:
        weekday_key = weekday_match.group(1).lower()
        resolved = _future_date_for_weekday(weekday_key)
        return _local_datetime_to_utc(resolved, hour, minute)

    day_year_match = re.search(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))\b", message, re.IGNORECASE)
    if day_year_match:
        day = int(day_year_match.group(1))
        year = int(day_year_match.group(2))
        resolved = _future_date_for_day_number(day, year)
        return _local_datetime_to_utc(resolved, hour, minute)

    return None


def _parse_title(message: str) -> str:
    titled = re.search(r"(?:called|titled|named)\s+(.+?)(?:\s+(?:on|at|with)\b|$)", message, re.IGNORECASE)
    if titled:
        return titled.group(1).strip().strip("\"'")[:200] or "Meeting"
    return "Meeting"


def _name_queries(message: str) -> list[str]:
    match = re.search(r"\bwith\s+(.+?)(?:\s+(?:on|at|for)\b|$)", message, re.IGNORECASE)
    if not match:
        return []
    raw = match.group(1)
    raw = re.split(r"\s+\b(?:in|near)\b\s+", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    raw = re.sub(r"\s*(?:,|\band\b)\s*", ",", raw, flags=re.IGNORECASE)
    return [part.strip() for part in raw.split(",") if part.strip() and "@" not in part]


def _parse_location(message: str) -> str | None:
    virtual_match = re.search(r"\b(?:on|via)\s+(zoom|teams|google meet|meet)\b", message, re.IGNORECASE)
    if virtual_match:
        return virtual_match.group(1).strip()

    location_match = re.search(
        r"\b(?:in|near)\s+(.+?)(?:\s+\b(?:with|on|from|for)\b|$)",
        message,
        re.IGNORECASE,
    )
    if not location_match:
        return None

    location = re.sub(r"[.!?]+$", "", location_match.group(1).strip())
    location = re.split(
        r"\s+\b(?:mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
        location,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    location = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b.*$", "", location, flags=re.IGNORECASE).strip()
    return location[:240] or None


def _fallback_context_text(messages: list[dict[str, Any]]) -> str:
    recent_user_messages: list[str] = []
    for stored_message in reversed(messages):
        metadata = stored_message.get("metadata") or {}
        if stored_message.get("role") == "assistant" and (
            metadata.get("completed_action") or metadata.get("discarded_draft_id")
        ):
            break
        if stored_message.get("role") == "user":
            content = str(stored_message.get("content") or "").strip()
            if content:
                recent_user_messages.append(content)
        if len(recent_user_messages) >= 6:
            break
    return " ".join(reversed(recent_user_messages)).strip()


def _local_fallback_response(
    *,
    message: str,
    messages: list[dict[str, Any]],
    selected_user_ids: list[int],
    db: Session,
    user: User,
    thread_id: int,
) -> tuple[str, list[str], list[AssistantInviteeCandidate], AssistantDraftAction | None, list[AssistantToolResult]]:
    context_message = _fallback_context_text(messages) or message
    lowered = context_message.lower()
    if not any(word in lowered for word in {"schedule", "create", "book", "set up", "cancel", "update", "reschedule"}):
        return (
            "I can help schedule, update, or cancel meetings. Tell me the time and who should attend.",
            [],
            [],
            None,
            [],
        )

    candidates: list[AssistantInviteeCandidate] = []
    unresolved_names: list[str] = []
    if selected_user_ids:
        candidates = search_invitees_tool(db, user=user, selected_user_ids=selected_user_ids)

    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", context_message, flags=re.IGNORECASE)
    email_ids, missing_emails = _resolve_user_ids_from_emails(db, emails)
    if missing_emails:
        return (
            f"I could not find registered users for: {', '.join(missing_emails)}.",
            ["Choose registered same-group users before confirming the meeting."],
            [],
            None,
            [],
        )

    attendee_ids = sorted(set([*selected_user_ids, *email_ids]))
    if not attendee_ids:
        for query in _name_queries(context_message):
            matches = search_invitees_tool(db, user=user, query=query)
            if len(matches) == 1:
                attendee_ids.append(matches[0].user_id)
                candidates.extend(matches)
            elif len(matches) > 1:
                return (
                    f"I found more than one match for {query}.",
                    [f"Which {query} should I invite?"],
                    matches,
                    None,
                    [],
                )
            else:
                unresolved_names.append(query)

    if unresolved_names:
        return (
            f"I could not find same-group users for: {', '.join(unresolved_names)}.",
            ["Try the person's full name or Stevens email address."],
            candidates,
            None,
            [],
        )

    if not attendee_ids:
        return (
            "I know the timing, but I still need at least one invitee.",
            ["Who should I invite?"],
            candidates,
            None,
            [],
        )

    start_time = _parse_start_time(context_message)
    if start_time is None:
        return (
            "I need a specific date and time before I can draft the meeting.",
            ["What date and time should I use?"],
            candidates,
            None,
            [],
        )
    end_time = start_time + timedelta(hours=1)
    meeting_type = "virtual" if any(word in lowered for word in {"remote", "virtual", "zoom", "teams", "video"}) else "in_person"
    location = _parse_location(context_message)

    try:
        draft = create_meeting_draft_tool(
            db,
            user=user,
            thread_id=thread_id,
            title=_parse_title(context_message),
            meeting_type=meeting_type,
            location=location,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            attendee_user_ids=attendee_ids,
            attendee_emails=[],
        )
    except HTTPException as exc:
        return (str(exc.detail), [str(exc.detail)], candidates, None, [])

    return (_draft_summary(draft), [], [], draft, [_tool_result("create_meeting_draft", True, draft.model_dump())])


def process_user_message(
    db: Session,
    *,
    user: User,
    thread_id: int,
    message: str,
    selected_user_ids: list[int] | None = None,
) -> AssistantResponse:
    thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    messages = _load_messages(thread)
    messages.append(_message("user", message, {"selected_user_ids": selected_user_ids or []}))

    pending_questions: list[str] = []
    candidates: list[AssistantInviteeCandidate] = []
    tool_results: list[AssistantToolResult] = []

    if settings.openai_api_key:
        try:
            assistant_text, tool_results = _call_openai_with_tools(
                messages=messages,
                db=db,
                user=user,
                thread_id=thread_id,
            )
        except Exception as exc:
            logger.warning("OpenAI assistant call failed, using local fallback: %s", exc)
            assistant_text, pending_questions, candidates, pending_draft, tool_results = _local_fallback_response(
                message=message,
                messages=messages,
                selected_user_ids=selected_user_ids or [],
                db=db,
                user=user,
                thread_id=thread_id,
            )
        else:
            pending_draft = _active_pending_draft(db, thread_id=thread_id, user_id=user.id)
    else:
        assistant_text, pending_questions, candidates, pending_draft, tool_results = _local_fallback_response(
            message=message,
            messages=messages,
            selected_user_ids=selected_user_ids or [],
            db=db,
            user=user,
            thread_id=thread_id,
        )

    if not pending_questions and pending_draft is not None and "confirm" not in assistant_text.lower():
        assistant_text = _draft_summary(pending_draft)

    assistant_message = _message(
        "assistant",
        assistant_text,
        {
            "pending_questions": pending_questions,
            "candidate_invitees": [candidate.model_dump() for candidate in candidates],
            "pending_draft_id": pending_draft.id if pending_draft else None,
        },
    )
    messages.append(assistant_message)
    _write_messages(db, thread_id=thread_id, user_id=user.id, messages=messages)
    db.commit()

    updated_thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    pending_draft = _active_pending_draft(db, thread_id=thread_id, user_id=user.id)
    return AssistantResponse(
        thread=_thread_summary(updated_thread, db),
        assistant_message=_message_item(assistant_message),
        pending_questions=pending_questions,
        candidate_invitees=candidates,
        pending_draft=pending_draft,
        completed_action=None,
        tool_results=tool_results,
    )


def confirm_draft_action(
    db: Session,
    *,
    user: User,
    thread_id: int,
    draft_action_id: int | None = None,
) -> AssistantResponse:
    _thread_row(db, thread_id=thread_id, user_id=user.id)
    draft_row = _pending_draft_row(db, thread_id=thread_id, user_id=user.id, draft_action_id=draft_action_id)
    draft = _draft_model(draft_row)
    if draft is None:
        raise HTTPException(status_code=404, detail="No pending assistant draft found")

    payload = dict(draft.payload)
    try:
        if draft.action_type == "create_meeting":
            _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=payload.get("attendee_user_ids") or [])
            result = meetings_api.create_meeting(
                payload=MeetingCreate(
                    title=payload["title"],
                    description=payload.get("description"),
                    location=payload.get("location"),
                    meeting_type=payload.get("meeting_type", "in_person"),
                    start_time=payload["start_time"],
                    end_time=payload["end_time"],
                    attendee_emails=payload.get("attendee_emails") or [],
                ),
                current_user=user,
                db=db,
            )
            completed_text = f"Created {result['title']} and sent RSVP notifications."
        elif draft.action_type == "update_meeting":
            meeting_id = int(draft.target_meeting_id or payload["meeting_id"])
            _validate_common_group_scope(db, requester_id=user.id, attendee_user_ids=payload.get("attendee_user_ids") or [])
            update_payload = {
                key: payload[key]
                for key in (
                    "title",
                    "description",
                    "location",
                    "meeting_type",
                    "start_time",
                    "end_time",
                    "attendee_emails",
                )
                if key in payload
            }
            result = meetings_api.update_meeting(
                meeting_id,
                MeetingUpdate(**update_payload),
                current_user=user,
                db=db,
            )
            completed_text = f"Updated {result['title']} and asked attendees to reconfirm if needed."
        else:
            meeting_id = int(draft.target_meeting_id or payload["meeting_id"])
            result = meetings_api.cancel_meeting(meeting_id, current_user=user, db=db)
            completed_text = f"Cancelled {result['title']} and notified attendees."
    except Exception:
        db.rollback()
        raise

    db.execute(
        text(
            """
            UPDATE assistant_draft_actions
            SET status = 'confirmed',
                result_json = CAST(:result_json AS JSONB),
                updated_at = NOW()
            WHERE id = :draft_id AND user_id = :user_id
            """
        ),
        {
            "draft_id": draft.id,
            "user_id": user.id,
            "result_json": json.dumps(_json_safe(result)),
        },
    )
    thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    messages = _load_messages(thread)
    assistant_message = _message("assistant", completed_text, {"completed_action": _json_safe(result), "draft_action_id": draft.id})
    messages.append(assistant_message)
    _write_messages(db, thread_id=thread_id, user_id=user.id, messages=messages)
    db.commit()

    updated_thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    return AssistantResponse(
        thread=_thread_summary(updated_thread, db),
        assistant_message=_message_item(assistant_message),
        pending_questions=[],
        candidate_invitees=[],
        pending_draft=None,
        completed_action=_json_safe(result),
        tool_results=[_tool_result("confirm_draft_action", True, result)],
    )


def discard_draft_action(
    db: Session,
    *,
    user: User,
    thread_id: int,
    draft_action_id: int | None = None,
) -> AssistantResponse:
    _thread_row(db, thread_id=thread_id, user_id=user.id)
    draft_row = _pending_draft_row(db, thread_id=thread_id, user_id=user.id, draft_action_id=draft_action_id)
    draft = _draft_model(draft_row)
    if draft is None:
        raise HTTPException(status_code=404, detail="No pending assistant draft found")
    db.execute(
        text(
            """
            UPDATE assistant_draft_actions
            SET status = 'discarded', updated_at = NOW()
            WHERE id = :draft_id AND user_id = :user_id
            """
        ),
        {"draft_id": draft.id, "user_id": user.id},
    )
    thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    messages = _load_messages(thread)
    assistant_message = _message("assistant", "I discarded that draft.", {"discarded_draft_id": draft.id})
    messages.append(assistant_message)
    _write_messages(db, thread_id=thread_id, user_id=user.id, messages=messages)
    db.commit()

    updated_thread = _thread_row(db, thread_id=thread_id, user_id=user.id)
    return AssistantResponse(
        thread=_thread_summary(updated_thread, db),
        assistant_message=_message_item(assistant_message),
        pending_questions=[],
        candidate_invitees=[],
        pending_draft=None,
        completed_action=None,
        tool_results=[_tool_result("discard_draft_action", True, draft.model_dump())],
    )
