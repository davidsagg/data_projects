from src.models.models import Company
from src.services.companies import get_or_create_company, normalize_company_name


def test_get_or_create_creates_new_company(db_session):
    company = get_or_create_company(db_session, "Acme Corp")
    db_session.commit()
    assert company.id is not None
    assert company.name == "Acme Corp"
    assert company.normalized_name == "acme corp"


def test_get_or_create_reuses_existing_by_normalized_name(db_session):
    first = get_or_create_company(db_session, "Acme Corp")
    db_session.commit()
    second = get_or_create_company(db_session, "  ACME   corp ")
    db_session.commit()
    assert first.id == second.id
    assert db_session.query(Company).count() == 1


def test_normalize_company_name_collapses_whitespace_and_case():
    assert normalize_company_name("  GE   HealthCare ") == "ge healthcare"
    assert normalize_company_name("GE Healthcare") == "ge healthcare"


def test_companies_api_list_and_sector_filter(client):
    client.post("/api/contacts", json={"first_name": "A", "last_name": "B", "company": "Acme"})
    client.post("/api/contacts", json={"first_name": "C", "last_name": "D", "company": "Acme"})
    client.post("/api/contacts", json={"first_name": "E", "last_name": "F", "company": "Globex"})

    companies = client.get("/api/companies").json()
    by_name = {c["name"]: c for c in companies}
    assert by_name["Acme"]["contact_count"] == 2
    assert by_name["Globex"]["contact_count"] == 1

    acme_id = by_name["Acme"]["id"]
    client.patch(f"/api/companies/{acme_id}", json={"sector": "Tecnologia"})

    filtered = client.get("/api/companies", params={"sector": "Tecnologia"}).json()
    assert [c["name"] for c in filtered] == ["Acme"]


def test_companies_bulk_sector_assignment(client):
    a = client.post("/api/contacts", json={"first_name": "A", "last_name": "B", "company": "Acme"}).json()
    g = client.post("/api/contacts", json={"first_name": "C", "last_name": "D", "company": "Globex"}).json()
    companies = {c["name"]: c["id"] for c in client.get("/api/companies").json()}

    resp = client.post(
        "/api/companies/bulk-sector",
        json={"company_ids": [companies["Acme"], companies["Globex"]], "sector": "Saúde"},
    )
    assert resp.status_code == 204

    companies_after = {c["name"]: c["sector"] for c in client.get("/api/companies").json()}
    assert companies_after["Acme"] == "Saúde"
    assert companies_after["Globex"] == "Saúde"


def test_company_detail_includes_contacts_and_seniority_breakdown(client):
    client.post(
        "/api/contacts",
        json={"first_name": "Ana", "last_name": "CEO", "company": "Acme", "position": "CEO"},
    )
    client.post(
        "/api/contacts",
        json={"first_name": "Bob", "last_name": "Eng", "company": "Acme", "position": "Software Engineer"},
    )
    company_id = client.get("/api/companies").json()[0]["id"]

    detail = client.get(f"/api/companies/{company_id}").json()
    assert detail["contact_count"] == 2
    assert len(detail["contacts"]) == 2
    levels = {row["value"] for row in detail["seniority_breakdown"]}
    assert "C-Level / Fundador" in levels
    assert "Especialista / Analista" in levels


def test_contact_company_id_and_seniority_set_on_create(client):
    contact = client.post(
        "/api/contacts",
        json={"first_name": "Jane", "last_name": "Doe", "company": "Acme", "position": "CEO"},
    ).json()
    assert contact["company_id"] is not None
    assert contact["seniority"] == "C-Level / Fundador"


def test_sort_companies_by_name(client):
    client.post("/api/contacts", json={"first_name": "A", "last_name": "B", "company": "Zeta Corp"})
    client.post("/api/contacts", json={"first_name": "C", "last_name": "D", "company": "Alpha Inc"})

    companies = client.get("/api/companies", params={"sort": "name", "sort_dir": "asc"}).json()
    assert [c["name"] for c in companies] == ["Alpha Inc", "Zeta Corp"]

    reversed_companies = client.get(
        "/api/companies", params={"sort": "name", "sort_dir": "desc"}
    ).json()
    assert [c["name"] for c in reversed_companies] == ["Zeta Corp", "Alpha Inc"]


def test_sort_companies_by_contacts_desc(client):
    client.post("/api/contacts", json={"first_name": "A", "last_name": "B", "company": "Small Co"})
    client.post("/api/contacts", json={"first_name": "C", "last_name": "D", "company": "Big Co"})
    client.post("/api/contacts", json={"first_name": "E", "last_name": "F", "company": "Big Co"})

    companies = client.get("/api/companies", params={"sort": "contacts", "sort_dir": "desc"}).json()
    assert [c["name"] for c in companies] == ["Big Co", "Small Co"]

    ascending = client.get("/api/companies", params={"sort": "contacts", "sort_dir": "asc"}).json()
    assert [c["name"] for c in ascending] == ["Small Co", "Big Co"]


def test_sort_companies_by_sector_puts_unclassified_last(client):
    a = client.post("/api/contacts", json={"first_name": "A", "last_name": "B", "company": "Acme"}).json()
    client.post("/api/contacts", json={"first_name": "C", "last_name": "D", "company": "NoSectorCo"})
    companies_by_name = {c["name"]: c["id"] for c in client.get("/api/companies").json()}
    client.patch(f"/api/companies/{companies_by_name['Acme']}", json={"sector": "Tecnologia"})

    companies = client.get("/api/companies", params={"sort": "sector", "sort_dir": "asc"}).json()
    assert [c["name"] for c in companies] == ["Acme", "NoSectorCo"]


def test_ge_healthcare_casing_variants_merge_into_one_company(client):
    client.post("/api/contacts", json={"first_name": "A", "last_name": "A", "company": "GE HealthCare"})
    client.post("/api/contacts", json={"first_name": "B", "last_name": "B", "company": "GE Healthcare"})

    companies = client.get("/api/companies").json()
    ge_companies = [c for c in companies if "healthcare" in c["name"].lower()]
    assert len(ge_companies) == 1
    assert ge_companies[0]["contact_count"] == 2
