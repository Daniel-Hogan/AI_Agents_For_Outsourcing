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


def _create_meeting(client, *, title: str, start_time: str, end_time: str, location: str = "") -> int:
    response = client.post(
        "/meetings/create",
        data={
            "title": title,
            "location": location,
            "location_raw": location,
            "location_latitude": "",
            "location_longitude": "",
            "start_time": start_time,
            "end_time": end_time,
            "invitees": "",
            "q": "",
            "status": "",
            "mine": "",
            "day": "2030-01-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db = SessionLocal()
    try:
        meeting_id = db.execute(
            text(
                """
                SELECT id
                FROM meetings
                WHERE title = :title
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"title": title},
        ).scalar_one()
        return int(meeting_id)
    finally:
        db.close()


def _assert_theme_hooks(response_text: str) -> None:
    assert 'data-theme="light"' in response_text
    assert "planner-theme" in response_text
    assert "theme.js" in response_text
    assert "app-shell.js" in response_text
    assert "data-theme-toggle" in response_text


def _assert_app_header(response_text: str) -> None:
    assert "app-header" in response_text
    assert "Scheduler AI" in response_text
    assert "/dashboard" in response_text
    assert "/settings" in response_text
    assert "data-notification-bell-button" in response_text


def test_auth_pages_include_theme_bootstrap_and_toggle(client):
    index_response = client.get("/")
    assert index_response.status_code == 200, index_response.text
    _assert_theme_hooks(index_response.text)

    signup_response = client.get("/signup")
    assert signup_response.status_code == 200, signup_response.text
    _assert_theme_hooks(signup_response.text)


def test_signed_in_pages_include_theme_bootstrap_and_toggle(client):
    _register_user(client)
    _web_login(client)

    for path in ("/dashboard", "/meetings", "/meetings/overview", "/calendar", "/availability", "/settings", "/groups"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        _assert_theme_hooks(response.text)
        _assert_app_header(response.text)


def test_meeting_detail_page_includes_theme_bootstrap_and_toggle(client):
    _register_user(client)
    _web_login(client)
    meeting_id = _create_meeting(
        client,
        title="Theme Detail Review",
        location="Campus Center",
        start_time="2030-01-08T09:00",
        end_time="2030-01-08T10:00",
    )

    response = client.get(f"/meetings/{meeting_id}")

    assert response.status_code == 200, response.text
    _assert_theme_hooks(response.text)
    _assert_app_header(response.text)


def test_group_detail_page_includes_theme_bootstrap_and_toggle(client):
    _register_user(client, email="groupowner@example.com")
    _web_login(client, email="groupowner@example.com")

    create_response = client.post(
        "/groups/create",
        data={"name": "Theme Group", "description": "UI coverage"},
        follow_redirects=False,
    )
    assert create_response.status_code == 303, create_response.text

    db = SessionLocal()
    try:
        group_id = int(
            db.execute(
                text(
                    """
                    SELECT id
                    FROM groups
                    WHERE name = :name
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"name": "Theme Group"},
            ).scalar_one()
        )
    finally:
        db.close()

    response = client.get(f"/groups/{group_id}")

    assert response.status_code == 200, response.text
    _assert_theme_hooks(response.text)
    _assert_app_header(response.text)
