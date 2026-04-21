from sqlalchemy import text
from sqlalchemy.orm import Session


def get_or_create_user_calendar(user_id: int, db: Session) -> int:
    result = db.execute(
        text(
            """
            SELECT c.id
            FROM calendars c
            JOIN user_calendars uc ON c.id = uc.calendar_id
            WHERE uc.user_id = :user_id AND c.owner_type = 'user'
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).fetchone()

    if result:
        return result[0]

    new_calendar = db.execute(
        text(
            """
            INSERT INTO calendars (name, owner_type, owner_id)
            VALUES (:name, 'user', :owner_id)
            RETURNING id
            """
        ),
        {"name": "My Calendar", "owner_id": user_id},
    ).fetchone()

    calendar_id = new_calendar[0]
    db.execute(
        text(
            """
            INSERT INTO user_calendars (user_id, calendar_id)
            VALUES (:user_id, :calendar_id)
            """
        ),
        {"user_id": user_id, "calendar_id": calendar_id},
    )
    db.commit()
    return calendar_id
