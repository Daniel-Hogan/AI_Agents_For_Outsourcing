from pydantic import BaseModel, Field


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class JoinGroupRequest(BaseModel):
    inviteCode: str | None = None
    groupId: int | None = Field(default=None, ge=1)


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    role: str
