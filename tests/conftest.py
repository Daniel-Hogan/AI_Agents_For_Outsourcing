import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.bootstrap import ensure_runtime_schema
from app.main import create_app
from app.db.session import SessionLocal


@pytest.fixture(scope="session", autouse=True)
def _require_db():
    try:
        ensure_runtime_schema()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Postgres not running / DATABASE_URL not reachable")
    finally:
        try:
            db.close()
        except Exception:
            pass


@pytest.fixture(scope="session")
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def _db_cleanup():
    # Truncate auth-related tables between tests.
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                TRUNCATE TABLE
                    refresh_tokens,
                    password_credentials,
                    auth_identities,
                    time_slot_preferences,
                    meeting_attendees,
                    meetings,
                    user_calendars,
                    calendars,
                    group_memberships,
                    groups,
                    location_cache,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )
        db.commit()
    except Exception:
        # If DB isn't up / schema isn't applied, let individual tests fail with clearer errors.
        db.rollback()
    finally:
        db.close()
