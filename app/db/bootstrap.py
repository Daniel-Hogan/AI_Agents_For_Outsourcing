from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import engine


SCHEMA_PATCHES = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location_latitude DOUBLE PRECISION",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location_longitude DOUBLE PRECISION",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_raw TEXT",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_latitude DOUBLE PRECISION",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_longitude DOUBLE PRECISION",
    """
    CREATE TABLE IF NOT EXISTS location_cache (
      location_key TEXT PRIMARY KEY,
      location_label TEXT NOT NULL,
      latitude DOUBLE PRECISION NOT NULL,
      longitude DOUBLE PRECISION NOT NULL,
      provider TEXT NOT NULL DEFAULT 'openrouteservice',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
)


def ensure_runtime_schema(db_engine: Engine = engine) -> None:
    with db_engine.begin() as conn:
        for statement in SCHEMA_PATCHES:
            conn.execute(text(statement))
