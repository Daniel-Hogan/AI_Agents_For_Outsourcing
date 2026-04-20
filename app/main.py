import logging
import time
import uuid

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.availability import router as availability_router
from app.api.calendar import router as calendar_router
from app.api.meetings import router as meetings_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.bootstrap import ensure_runtime_schema
from app.models import User
from app.schemas.groups import CreateGroupRequest, GroupResponse, JoinGroupRequest

from app.api.deps import get_current_user,get_db

router = APIRouter(prefix="/groups", tags=["groups"])


configure_logging(settings.log_level)
logger = logging.getLogger("app")


def _allowed_origins() -> list[str]:
    origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    if settings.frontend_origin:
        origins.add(settings.frontend_origin)
    return sorted(origins)

def create_app() -> FastAPI:
    api = FastAPI(title="AI Agents API")

    @api.on_event("startup")
    def bootstrap_runtime_schema() -> None:
        ensure_runtime_schema()

    @api.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s %.1fms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response

    @api.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
        logger.exception(
            "Unhandled error on %s %s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    api.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api.include_router(auth_router)
    api.include_router(router)
    api.include_router(availability_router)

    api.include_router(calendar_router)
    api.include_router(meetings_router)
    return api

@router.get("/")
def get_user_groups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch all groups the current logged-in user belongs to."""
    
    query = text("""
        SELECT g.id, g.name, g.description, gm.role 
        FROM groups g
        JOIN group_memberships gm ON g.id = gm.group_id
        WHERE gm.user_id = :user_id
    """)
    
    
    result = db.execute(query, {"user_id": current_user.id}).mappings().all()
    
    return [dict(row) for row in result]


def _group_id_from_invite_code(invite_code: str) -> int | None:
    token = invite_code.strip()
    if not token:
        return None

    # Minimal invite format support backed by current schema:
    # numeric code ("12") or prefixed code ("GRP-12").
    token_upper = token.upper()
    if token_upper.startswith("GRP-"):
        token = token[4:]

    if token.isdigit():
        return int(token)

    return None


@router.post("/", response_model=GroupResponse)
def create_group(payload: CreateGroupRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group_name = payload.name.strip()
    if not group_name:
        raise HTTPException(status_code=422, detail="Group name cannot be empty")

    description = payload.description.strip() if payload.description else None
    if description == "":
        description = None

    group_row = db.execute(
        text(
            """
            INSERT INTO groups (name, description)
            VALUES (:name, :description)
            RETURNING id, name, description
            """
        ),
        {"name": group_name, "description": description},
    ).mappings().one()

    db.execute(
        text(
            """
            INSERT INTO group_memberships (user_id, group_id, role)
            VALUES (:user_id, :group_id, 'owner')
            """
        ),
        {"user_id": current_user.id, "group_id": group_row["id"]},
    )
    db.commit()

    return GroupResponse(
        id=group_row["id"],
        name=group_row["name"],
        description=group_row["description"],
        role="owner",
    )


@router.post("/join", response_model=GroupResponse)
def join_group(payload: JoinGroupRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    group_id = payload.groupId
    if group_id is None and payload.inviteCode:
        group_id = _group_id_from_invite_code(payload.inviteCode)

    if group_id is None:
        raise HTTPException(status_code=422, detail="Provide a valid groupId or inviteCode")

    existing_group = db.execute(
        text("SELECT id, name, description FROM groups WHERE id = :group_id"),
        {"group_id": group_id},
    ).mappings().one_or_none()

    if existing_group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    try:
        db.execute(
            text(
                """
                INSERT INTO group_memberships (user_id, group_id, role)
                VALUES (:user_id, :group_id, 'member')
                """
            ),
            {"user_id": current_user.id, "group_id": group_id},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You are already a member of this group")

    return GroupResponse(
        id=existing_group["id"],
        name=existing_group["name"],
        description=existing_group["description"],
        role="member",
    )
app = create_app()
