def test_register_login_me_refresh_logout(client):
    r = client.post(
        "/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "password": "supersecret123",
        },
    )
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]
    assert access
    assert client.cookies.get("refresh_token")

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "ada@example.com"
    assert r.json()["avatar_color"] == "blue"

    old_refresh = client.cookies.get("refresh_token")
    r = client.post("/auth/refresh")
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    r = client.post("/auth/logout")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_login_invalid_password(client):
    client.post(
        "/auth/register",
        json={
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "grace@example.com",
            "password": "supersecret123",
        },
    )

    r = client.post("/auth/login", json={"email": "grace@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_update_profile_and_password(client):
    register_response = client.post(
        "/auth/register",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "password": "supersecret123",
        },
    )
    assert register_response.status_code == 200, register_response.text
    access = register_response.json()["access_token"]

    update_response = client.patch(
        "/auth/me",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "first_name": "Augusta",
            "last_name": "Byron",
            "email": "augusta@example.com",
            "avatar_color": "teal",
            "current_password": "supersecret123",
            "new_password": "newsupersecret123",
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["first_name"] == "Augusta"
    assert update_response.json()["email"] == "augusta@example.com"
    assert update_response.json()["avatar_color"] == "teal"

    old_login = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "supersecret123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": "augusta@example.com", "password": "newsupersecret123"},
    )
    assert new_login.status_code == 200, new_login.text


def test_web_signup_creates_account_and_redirects_to_meetings(client):
    r = client.get("/signup")
    assert r.status_code == 200
    assert "Create your account" in r.text

    r = client.post(
        "/signup",
        data={
            "first_name": "Linus",
            "last_name": "Torvalds",
            "email": "linus@example.com",
            "phone": "",
            "password": "supersecret123",
            "confirm_password": "supersecret123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/meetings"

    meetings_page = client.get("/meetings")
    assert meetings_page.status_code == 200
    assert "Signed in as <strong>linus@example.com</strong>" in meetings_page.text
