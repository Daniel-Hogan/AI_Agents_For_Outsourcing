from sqlalchemy import text

from app.db.session import SessionLocal


def _register_user(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
    response = client.post(
        "/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text


def _web_login(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_availability_page_includes_clickable_time_cards(client):
    _register_user(client)
    _web_login(client)

    response = client.get("/availability")

    assert response.status_code == 200, response.text
    assert "availability-card" in response.text
    assert "data-time-picker" in response.text
    assert "data-time-native" in response.text
    assert "data-time-hour" in response.text
    assert "data-time-minute" in response.text
    assert "data-time-period" in response.text
    assert 'step="900"' in response.text
    assert 'type="checkbox"' in response.text
    assert "availability-day-toggle" in response.text
    assert "availability.js" in response.text


def test_availability_add_supports_multiple_days(client):
    _register_user(client)
    _web_login(client)

    response = client.post(
        "/availability/add",
        data={
            "day_of_week": ["1", "3", "5"],
            "start_time": "09:00",
            "end_time": "10:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT day_of_week, start_time, end_time
                FROM time_slot_preferences
                ORDER BY day_of_week
                """
            )
        ).mappings().all()
    finally:
        db.close()

    assert [int(row["day_of_week"]) for row in rows] == [1, 3, 5]
    assert all(str(row["start_time"]) == "09:00:00" for row in rows)
    assert all(str(row["end_time"]) == "10:00:00" for row in rows)
