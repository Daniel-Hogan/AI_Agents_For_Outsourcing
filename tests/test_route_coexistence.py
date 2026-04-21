def _register_user(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> str:
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
    return response.json()["access_token"]


def _web_login(client, *, email: str = "ada@example.com", password: str = "supersecret123") -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_meetings_page_and_api_can_coexist(client):
    token = _register_user(client)
    _web_login(client)

    page_response = client.get("/meetings")
    assert page_response.status_code == 200, page_response.text
    assert page_response.headers["content-type"].startswith("text/html")

    api_response = client.get("/api/meetings/", headers=_auth_headers(token))
    assert api_response.status_code == 200, api_response.text
    assert api_response.headers["content-type"].startswith("application/json")
    assert api_response.json() == []


def test_availability_page_and_api_can_coexist(client):
    token = _register_user(client, email="grace@example.com")
    _web_login(client, email="grace@example.com")

    page_response = client.get("/availability")
    assert page_response.status_code == 200, page_response.text
    assert page_response.headers["content-type"].startswith("text/html")

    api_get_response = client.get("/api/availability/", headers=_auth_headers(token))
    assert api_get_response.status_code == 200, api_get_response.text
    assert api_get_response.headers["content-type"].startswith("application/json")
    assert api_get_response.json() == []

    api_post_response = client.post(
        "/api/availability/",
        headers=_auth_headers(token),
        json=[{"day_of_week": 1, "start_time": "09:00:00", "end_time": "17:00:00"}],
    )
    assert api_post_response.status_code == 200, api_post_response.text
    assert len(api_post_response.json()) == 1
