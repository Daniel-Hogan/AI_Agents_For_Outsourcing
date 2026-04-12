from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware





from sqlalchemy import text
from sqlalchemy.orm import Session

from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.models import User

from app.api.deps import get_current_user,get_db

from app.web.routes import router as web_router



from app.api.auth import router as auth_router
from app.api.recommendations import router as recommendations_router
from app.core.config import settings

router = APIRouter(prefix="/groups", tags=["groups"])

def create_app() -> FastAPI:
    api = FastAPI(title="AI Agents API")

    api.add_middleware(
        SessionMiddleware,
        secret_key=settings.jwt_secret,
        same_site=settings.cookie_samesite,
        https_only=settings.cookie_secure,
    )

    api.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin] if settings.frontend_origin else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api.mount("/static", StaticFiles(directory="app/static"), name="static")
    api.include_router(web_router)
    api.include_router(auth_router)
    api.include_router(recommendations_router)
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
