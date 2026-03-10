import logging
import time
import uuid

from fastapi import FastAPI, APIRouter, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.models import User

from app.api.deps import get_current_user,get_db

router = APIRouter(prefix="/groups", tags=["groups"])


configure_logging(settings.log_level)
logger = logging.getLogger("app")

def create_app() -> FastAPI:
    api = FastAPI(title="AI Agents API")

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
        allow_origins=[settings.frontend_origin] if settings.frontend_origin else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api.include_router(auth_router)
    api.include_router(router)
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
app = create_app()
