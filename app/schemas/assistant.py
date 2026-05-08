from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AssistantRole = Literal["user", "assistant", "tool"]
AssistantActionType = Literal["create_meeting", "update_meeting", "cancel_meeting"]
AssistantDraftStatus = Literal["pending", "confirmed", "discarded", "failed"]


class AssistantThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class AssistantMessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    selected_user_ids: list[int] = Field(default_factory=list)


class AssistantMessageItem(BaseModel):
    role: AssistantRole
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssistantDraftAction(BaseModel):
    id: int
    thread_id: int
    action_type: AssistantActionType
    status: AssistantDraftStatus
    payload: dict[str, Any]
    target_meeting_id: int | None = None
    created_at: datetime
    updated_at: datetime


class AssistantThreadSummary(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    pending_draft: AssistantDraftAction | None = None


class AssistantThreadDetail(AssistantThreadSummary):
    messages: list[AssistantMessageItem]


class AssistantInviteeCandidate(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str
    display_name: str
    shared_group_ids: list[int]


class AssistantToolResult(BaseModel):
    name: str
    ok: bool
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class AssistantResponse(BaseModel):
    thread: AssistantThreadSummary
    assistant_message: AssistantMessageItem
    pending_questions: list[str] = Field(default_factory=list)
    candidate_invitees: list[AssistantInviteeCandidate] = Field(default_factory=list)
    pending_draft: AssistantDraftAction | None = None
    completed_action: dict[str, Any] | None = None
    tool_results: list[AssistantToolResult] = Field(default_factory=list)


class AssistantConfirmRequest(BaseModel):
    draft_action_id: int | None = None


class AssistantDiscardRequest(BaseModel):
    draft_action_id: int | None = None
