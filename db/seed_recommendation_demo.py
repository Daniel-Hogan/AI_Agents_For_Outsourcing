from pathlib import Path

from sqlalchemy import create_engine

from app.core.config import settings


def main() -> None:
    sql_path = Path(__file__).with_name("seed_recommendation_demo.sql")
    sql_script = sql_path.read_text(encoding="utf-8")

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            cursor.execute(sql_script)
        raw_conn.commit()
        print(f"Seed complete: {sql_path}")
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()
        engine.dispose()


if __name__ == "__main__":
    main()
