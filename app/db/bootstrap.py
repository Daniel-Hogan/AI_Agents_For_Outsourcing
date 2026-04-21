from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.session import engine


SCHEMA_PATCHES = (
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type TEXT NOT NULL DEFAULT 'in_person'",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT '#3498db'",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'confirmed'",
    (
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS created_by "
        "INTEGER REFERENCES users(id) ON DELETE SET NULL"
    ),
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location_latitude DOUBLE PRECISION",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_location_longitude DOUBLE PRECISION",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_raw TEXT",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_latitude DOUBLE PRECISION",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_longitude DOUBLE PRECISION",
    "ALTER TABLE meeting_attendees ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
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
    """
    DO $$
    DECLARE constraint_name TEXT;
    BEGIN
        SELECT c.conname INTO constraint_name
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'meeting_attendees'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) LIKE '%status%'
        LIMIT 1;

        IF constraint_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE meeting_attendees DROP CONSTRAINT %I', constraint_name);
        END IF;

        ALTER TABLE meeting_attendees
        ADD CONSTRAINT meeting_attendees_status_check
        CHECK (status IN ('invited', 'accepted', 'declined', 'maybe'));
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END $$;
    """,
)


def ensure_runtime_schema(db_engine: Engine = engine) -> None:
    with db_engine.begin() as conn:
        for statement in SCHEMA_PATCHES:
            conn.execute(text(statement))
