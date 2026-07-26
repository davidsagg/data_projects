from src.services import geocode as geocode_service


def _create_contact(client, company):
    return client.post(
        "/api/contacts", json={"first_name": "Jane", "last_name": "Doe", "company": company}
    ).json()


def test_bulk_drains_to_zero_even_when_every_company_fails_to_geocode(client, monkeypatch):
    monkeypatch.setattr(geocode_service, "_query_nominatim", lambda name: None)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    for i in range(5):
        _create_contact(client, f"Unresolvable Corp {i}")

    seen_remaining = []
    for _ in range(20):
        result = client.post("/api/geocode/bulk", params={"chunk_size": 2}).json()
        seen_remaining.append(result["remaining"])
        if result["remaining"] == 0:
            break
    else:
        raise AssertionError("bulk geocode never drained to zero — infinite loop regression")

    assert seen_remaining[-1] == 0


def test_bulk_does_not_reprocess_same_failed_company_twice(client, monkeypatch):
    calls = []

    def fake_query(name):
        calls.append(name)
        return None

    monkeypatch.setattr(geocode_service, "_query_nominatim", fake_query)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    _create_contact(client, "Acme Corp")

    first = client.post("/api/geocode/bulk", params={"chunk_size": 10}).json()
    second = client.post("/api/geocode/bulk", params={"chunk_size": 10}).json()

    assert first["processed"] == 1
    assert first["remaining"] == 0
    assert second["processed"] == 0
    assert second["remaining"] == 0
    assert len(calls) == 1
