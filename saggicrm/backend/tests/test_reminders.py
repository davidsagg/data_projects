def _create_contact(client):
    return client.post("/api/contacts", json={"first_name": "Jane", "last_name": "Doe"}).json()


def test_create_and_mark_reminder_done(client):
    contact = _create_contact(client)
    reminder = client.post(
        f"/api/contacts/{contact['id']}/reminders",
        json={"due_date": "2026-08-01", "note": "Follow up"},
    ).json()
    assert reminder["is_done"] is False

    response = client.patch(f"/api/reminders/{reminder['id']}", json={"is_done": True})
    assert response.status_code == 200
    body = response.json()
    assert body["is_done"] is True
    assert body["completed_at"] is not None


def test_global_reminders_filters_pending(client):
    contact = _create_contact(client)
    r1 = client.post(
        f"/api/contacts/{contact['id']}/reminders", json={"due_date": "2026-08-01"}
    ).json()
    client.post(f"/api/contacts/{contact['id']}/reminders", json={"due_date": "2026-09-01"})
    client.patch(f"/api/reminders/{r1['id']}", json={"is_done": True})

    pending = client.get("/api/reminders", params={"status": "pending"}).json()
    assert len(pending) == 1
    done = client.get("/api/reminders", params={"status": "done"}).json()
    assert len(done) == 1


def test_delete_reminder(client):
    contact = _create_contact(client)
    reminder = client.post(
        f"/api/contacts/{contact['id']}/reminders", json={"due_date": "2026-08-01"}
    ).json()
    assert client.delete(f"/api/reminders/{reminder['id']}").status_code == 204
