def _create_contact(client, **overrides):
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "company": "Acme",
        "position": "Engineer",
        "city": "São Paulo",
        **overrides,
    }
    response = client.post("/api/contacts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_and_get_contact(client):
    created = _create_contact(client)
    response = client.get(f"/api/contacts/{created['id']}")
    assert response.status_code == 200
    assert response.json()["first_name"] == "Jane"


def test_list_contacts_filters_by_company(client):
    _create_contact(client, first_name="Jane", company="Acme")
    _create_contact(client, first_name="Bob", company="Globex")

    response = client.get("/api/contacts", params={"company": "Acme"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["first_name"] == "Jane"


def test_list_contacts_search_matches_name(client):
    _create_contact(client, first_name="Jane", last_name="Doe")
    _create_contact(client, first_name="Bob", last_name="Smith")

    response = client.get("/api/contacts", params={"q": "doe"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["last_name"] == "Doe"


def test_update_contact(client):
    created = _create_contact(client)
    response = client.put(f"/api/contacts/{created['id']}", json={"city": "Rio de Janeiro"})
    assert response.status_code == 200
    assert response.json()["city"] == "Rio de Janeiro"


def test_delete_contact(client):
    created = _create_contact(client)
    assert client.delete(f"/api/contacts/{created['id']}").status_code == 204
    assert client.get(f"/api/contacts/{created['id']}").status_code == 404


def test_last_contacted_at_reflects_latest_interaction(client):
    created = _create_contact(client)
    contact_id = created["id"]
    client.post(
        f"/api/contacts/{contact_id}/interactions",
        json={"type": "note", "content": "primeiro contato", "occurred_at": "2026-01-01T10:00:00"},
    )
    client.post(
        f"/api/contacts/{contact_id}/interactions",
        json={"type": "call", "content": "call de follow up", "occurred_at": "2026-06-01T10:00:00"},
    )
    response = client.get("/api/contacts", params={"q": "jane"})
    item = response.json()["items"][0]
    assert item["last_contacted_at"].startswith("2026-06-01")


def test_group_assignment_and_filter(client):
    created = _create_contact(client)
    group = client.post("/api/groups", json={"name": "Board", "color": "#111111"}).json()
    client.post(f"/api/contacts/{created['id']}/groups/{group['id']}")

    response = client.get("/api/contacts", params={"group_id": group["id"]})
    assert response.json()["total"] == 1

    client.delete(f"/api/contacts/{created['id']}/groups/{group['id']}")
    response = client.get("/api/contacts", params={"group_id": group["id"]})
    assert response.json()["total"] == 0
