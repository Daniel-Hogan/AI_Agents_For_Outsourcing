from sqlalchemy import text

from app.db.session import SessionLocal


BOOTSTRAP_STATEMENTS = [
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type TEXT NOT NULL DEFAULT 'in_person'",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT '#3498db'",
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'confirmed'",
    (
        "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS created_by "
        "INTEGER REFERENCES users(id) ON DELETE SET NULL"
    ),
    "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "ALTER TABLE meeting_attendees ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
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
    END $$
    """,
]


def ensure_runtime_schema() -> None:
    db = SessionLocal()
    try:
        for statement in BOOTSTRAP_STATEMENTS:
            db.execute(text(statement))
        db.commit()
    finally:
        db.close()
