import io

from src.models.models import Contact
from src.services.linkedin_import import import_linkedin_csv

NOTES_PREAMBLE = (
    "Notes:\n"
    '"Some preamble text that should be skipped."\n'
    "\n"
)

HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"


def _csv(rows: str) -> bytes:
    return (NOTES_PREAMBLE + HEADER + rows).encode("utf-8")


def test_skips_fully_blank_rows(db_session):
    csv_bytes = _csv(
        "Jane,Doe,https://linkedin.com/in/janedoe,,Acme,Engineer,23 Jul 2026\n"
        ",,,,,,20 Jun 2025\n"
    )
    summary = import_linkedin_csv(db_session, csv_bytes)
    assert summary.total_rows == 2
    assert summary.skipped_blank == 1
    assert summary.created == 1


def test_parses_connected_on_date(db_session):
    csv_bytes = _csv("Jane,Doe,https://linkedin.com/in/janedoe,,Acme,Engineer,23 Jul 2026\n")
    import_linkedin_csv(db_session, csv_bytes)
    contact = db_session.query(Contact).one()
    assert contact.connected_on.isoformat() == "2026-07-23"


def test_upsert_by_linkedin_url_does_not_duplicate(db_session):
    csv_bytes = _csv("Jane,Doe,https://linkedin.com/in/janedoe,,Acme,Engineer,23 Jul 2026\n")
    import_linkedin_csv(db_session, csv_bytes)
    csv_bytes_v2 = _csv(
        "Jane,Doe,https://linkedin.com/in/janedoe,jane@acme.com,Acme,Senior Engineer,23 Jul 2026\n"
    )
    summary = import_linkedin_csv(db_session, csv_bytes_v2)
    assert summary.created == 0
    assert summary.updated == 1
    contact = db_session.query(Contact).one()
    assert contact.position == "Senior Engineer"
    assert contact.email == "jane@acme.com"


def test_reimport_never_overwrites_user_curated_city(db_session):
    csv_bytes = _csv("Jane,Doe,https://linkedin.com/in/janedoe,,Acme,Engineer,23 Jul 2026\n")
    import_linkedin_csv(db_session, csv_bytes)
    contact = db_session.query(Contact).one()
    contact.city = "São Paulo"
    db_session.commit()

    import_linkedin_csv(db_session, csv_bytes)
    contact = db_session.query(Contact).one()
    assert contact.city == "São Paulo"


def test_fallback_match_by_name_and_company_when_url_blank(db_session):
    csv_bytes = _csv("Jane,Doe,,,Acme,Engineer,23 Jul 2026\n")
    import_linkedin_csv(db_session, csv_bytes)
    summary = import_linkedin_csv(db_session, csv_bytes)
    assert summary.created == 0
    assert summary.updated == 1
    assert db_session.query(Contact).count() == 1


def test_import_via_api_with_real_export(client):
    with open(
        "../Basic_LinkedInDataExport_07-24-2026.zip/Connections.csv", "rb"
    ) as f:
        response = client.post(
            "/api/import/linkedin", files={"file": ("Connections.csv", f, "text/csv")}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 3204
    assert body["skipped_blank"] == 101
    assert body["total_rows"] == 3305


def test_rejects_non_csv_upload(client):
    response = client.post(
        "/api/import/linkedin",
        files={"file": ("Connections.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert response.status_code == 400
