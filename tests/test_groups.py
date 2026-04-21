def _register(client, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "password": "supersecret123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_create_group_and_list_membership(client):
    access = _register(client, "owner@example.com")

    created = client.post(
        "/groups/",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Design Team", "description": "Product and design planning"},
    )
    assert created.status_code == 200, created.text
    created_json = created.json()
    assert created_json["name"] == "Design Team"
    assert created_json["role"] == "owner"

    listing = client.get("/groups/", headers={"Authorization": f"Bearer {access}"})
    assert listing.status_code == 200, listing.text
    groups = listing.json()
    assert len(groups) == 1
    assert groups[0]["name"] == "Design Team"
    assert groups[0]["role"] == "owner"


def test_join_group_by_id_and_prevent_duplicate_membership(client):
    owner_access = _register(client, "owner2@example.com")
    created = client.post(
        "/groups/",
        headers={"Authorization": f"Bearer {owner_access}"},
        json={"name": "Engineering"},
    )
    assert created.status_code == 200, created.text
    group_id = created.json()["id"]

    member_access = _register(client, "member@example.com")

    joined = client.post(
        "/groups/join",
        headers={"Authorization": f"Bearer {member_access}"},
        json={"groupId": group_id},
    )
    assert joined.status_code == 200, joined.text
    assert joined.json()["role"] == "member"

    duplicate = client.post(
        "/groups/join",
        headers={"Authorization": f"Bearer {member_access}"},
        json={"groupId": group_id},
    )
    assert duplicate.status_code == 409
