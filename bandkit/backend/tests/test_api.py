import io
import pytest


# ── Health ───────────────────────────────────────────────────────

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Upload / Songs ───────────────────────────────────────────────

def test_upload_pdf_non_pdf_rejected(client):
    resp = client.post("/api/songs/upload", files={"file": ("song.txt", io.BytesIO(b"not a pdf"), "text/plain")})
    assert resp.status_code == 400


SAMPLE_PDF = "/workspaces/bandkit/bandkit-data/songs/ze_ramalho_sinonimos.pdf"

@pytest.mark.skipif(not __import__("os").path.exists(SAMPLE_PDF), reason="PDF de amostra ausente")
def test_upload_pdf_real_file(client):
    pdf = open(SAMPLE_PDF, "rb")
    resp = client.post(
        "/api/songs/upload",
        files={"file": ("ze_ramalho_sinonimos.pdf", pdf, "application/pdf")},
        data={"title": "Sinônimos", "artist": "Zé Ramalho"},
    )
    pdf.close()
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Sinônimos"
    assert body["parse_status"] in ("parsed", "failed")


# ── Musicians ────────────────────────────────────────────────────

def test_list_musicians_empty(client):
    assert client.get("/api/musicians").status_code == 200
    assert client.get("/api/musicians").json() == []


def test_create_musician(client):
    resp = client.post("/api/musicians", json={"name": "Dave", "instrument": "guitarra", "role": "admin"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Dave"
    assert "id" in resp.json()


def test_create_musician_missing_name_422(client):
    assert client.post("/api/musicians", json={"instrument": "bateria"}).status_code == 422


# ── Setlists ─────────────────────────────────────────────────────

def test_create_setlist(client):
    resp = client.post("/api/setlists", json={"name": "Setlist Rock"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Setlist Rock"
    assert "id" in resp.json()


def test_list_setlists(client):
    client.post("/api/setlists", json={"name": "Set A"})
    resp = client.get("/api/setlists")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_add_song_to_setlist(client, sample_song):
    sl = client.post("/api/setlists", json={"name": "My Set"}).json()
    resp = client.post(f"/api/setlists/{sl['id']}/songs", json={"song_id": sample_song.id, "order_position": 1})
    assert resp.status_code == 201
    assert resp.json()["song_id"] == sample_song.id


# ── Events ───────────────────────────────────────────────────────

def test_list_songs_empty(client):
    assert client.get("/api/songs").status_code == 200


def test_song_not_found_404(client):
    assert client.get("/api/songs/99999").status_code == 404


def test_create_event(client):
    payload = {"title": "Show Clube X", "date": "2026-05-01T21:00:00", "event_type": "show", "status": "confirmed"}
    resp = client.post("/api/events", json=payload)
    assert resp.status_code == 201
    assert resp.json()["title"] == "Show Clube X"


def test_create_event_with_setlist_auto_creates_executions(client, sample_song):
    sl = client.post("/api/setlists", json={"name": "Set"}).json()
    client.post(f"/api/setlists/{sl['id']}/songs", json={"song_id": sample_song.id, "order_position": 1})
    ev = client.post("/api/events", json={
        "title": "Show", "date": "2026-05-01T21:00:00", "event_type": "show", "setlist_id": sl["id"],
    }).json()
    execs = client.get(f"/api/events/{ev['id']}/executions").json()
    assert len(execs) == 1
    assert execs[0]["song_id"] == sample_song.id


def test_list_events(client):
    assert client.get("/api/events").status_code == 200


# ── Execuções ─────────────────────────────────────────────────────

def test_create_execution(client, sample_song):
    ev = client.post("/api/events", json={"title": "Show", "date": "2026-05-01T21:00:00", "event_type": "show"}).json()
    resp = client.post(f"/api/events/{ev['id']}/executions", json={"song_id": sample_song.id})
    assert resp.status_code == 201
    assert resp.json()["song_id"] == sample_song.id


def test_duplicate_execution_409(client, sample_song):
    ev = client.post("/api/events", json={"title": "Show", "date": "2026-05-01T21:00:00", "event_type": "show"}).json()
    client.post(f"/api/events/{ev['id']}/executions", json={"song_id": sample_song.id})
    resp = client.post(f"/api/events/{ev['id']}/executions", json={"song_id": sample_song.id})
    assert resp.status_code == 409


def test_patch_execution_key_override(client, sample_song):
    ev = client.post("/api/events", json={"title": "Show", "date": "2026-05-01T21:00:00", "event_type": "show"}).json()
    ex = client.post(f"/api/events/{ev['id']}/executions", json={"song_id": sample_song.id}).json()
    resp = client.patch(f"/api/events/{ev['id']}/executions/{ex['id']}", json={"key_override": "G"})
    assert resp.status_code == 200
    assert resp.json()["key_override"] == "G"


def test_add_musician_to_execution(client, sample_song, sample_musician):
    ev = client.post("/api/events", json={"title": "Show", "date": "2026-05-01T21:00:00", "event_type": "show"}).json()
    ex = client.post(f"/api/events/{ev['id']}/executions", json={"song_id": sample_song.id}).json()
    resp = client.post(
        f"/api/events/{ev['id']}/executions/{ex['id']}/musicians",
        json={"musician_id": sample_musician.id, "instrument_override": "guitarra"},
    )
    assert resp.status_code == 201
    assert resp.json()["musician_id"] == sample_musician.id


def test_transpose_endpoint(client, sample_song):
    resp = client.post(f"/api/songs/{sample_song.id}/transpose?semitones=3")
    assert resp.status_code == 200
    assert "bkcp_transposed" in resp.json()
