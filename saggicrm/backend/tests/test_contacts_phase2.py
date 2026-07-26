def _create(client, **overrides):
    payload = {"first_name": "Jane", "last_name": "Doe", **overrides}
    return client.post("/api/contacts", json=payload).json()


def test_filter_contacts_by_company_id(client):
    _create(client, company="Acme")
    _create(client, first_name="Bob", company="Globex")
    companies = {c["name"]: c["id"] for c in client.get("/api/companies").json()}

    result = client.get("/api/contacts", params={"company_id": companies["Acme"]}).json()
    assert result["total"] == 1
    assert result["items"][0]["first_name"] == "Jane"


def test_filter_contacts_by_sector(client):
    _create(client, company="Acme", position="CEO")
    _create(client, first_name="Bob", company="Globex", position="Analyst")
    companies = {c["name"]: c["id"] for c in client.get("/api/companies").json()}
    client.patch(f"/api/companies/{companies['Acme']}", json={"sector": "Tecnologia"})

    result = client.get("/api/contacts", params={"sector": "Tecnologia"}).json()
    assert result["total"] == 1
    assert result["items"][0]["company"] == "Acme"


def test_filter_contacts_by_seniority(client):
    _create(client, position="CEO")
    _create(client, first_name="Bob", position="Analyst")

    result = client.get("/api/contacts", params={"seniority": "C-Level / Fundador"}).json()
    assert result["total"] == 1
    assert result["items"][0]["seniority"] == "C-Level / Fundador"


def test_toggle_favorite(client):
    contact = _create(client)
    assert contact["is_favorite"] is False

    toggled = client.patch(f"/api/contacts/{contact['id']}/favorite").json()
    assert toggled["is_favorite"] is True

    toggled_back = client.patch(f"/api/contacts/{contact['id']}/favorite").json()
    assert toggled_back["is_favorite"] is False


def test_filter_contacts_by_favorite_only(client):
    a = _create(client)
    _create(client, first_name="Bob")
    client.patch(f"/api/contacts/{a['id']}/favorite")

    result = client.get("/api/contacts", params={"favorite_only": True}).json()
    assert result["total"] == 1
    assert result["items"][0]["first_name"] == "Jane"


def test_seniority_recomputed_on_position_update(client):
    contact = _create(client, position="Analyst")
    assert contact["seniority"] == "Especialista / Analista"

    updated = client.put(f"/api/contacts/{contact['id']}", json={"position": "CEO"}).json()
    assert updated["seniority"] == "C-Level / Fundador"


def test_seniority_levels_facet(client):
    _create(client, position="CEO")
    _create(client, first_name="Bob", position="Analyst")

    facets = client.get("/api/seniority-levels").json()
    values = {f["value"] for f in facets}
    assert "C-Level / Fundador" in values
    assert "Especialista / Analista" in values


def test_sort_contacts_by_seniority_ranks_c_level_first(client):
    _create(client, first_name="Ana", position="Analyst")
    _create(client, first_name="Beto", position="Intern")
    _create(client, first_name="Caio", position="CEO")
    _create(client, first_name="Duda", position="Manager")

    result = client.get("/api/contacts", params={"sort": "seniority", "sort_dir": "asc"}).json()
    ordered_names = [c["first_name"] for c in result["items"]]
    assert ordered_names == ["Caio", "Duda", "Ana", "Beto"]

    reversed_result = client.get(
        "/api/contacts", params={"sort": "seniority", "sort_dir": "desc"}
    ).json()
    reversed_names = [c["first_name"] for c in reversed_result["items"]]
    assert reversed_names == ["Beto", "Ana", "Duda", "Caio"]


def test_sort_contacts_by_company(client):
    _create(client, first_name="Zed", company="Zeta Corp")
    _create(client, first_name="Ann", company="Alpha Inc")

    result = client.get("/api/contacts", params={"sort": "company", "sort_dir": "asc"}).json()
    ordered_names = [c["first_name"] for c in result["items"]]
    assert ordered_names == ["Ann", "Zed"]

    reversed_result = client.get(
        "/api/contacts", params={"sort": "company", "sort_dir": "desc"}
    ).json()
    reversed_names = [c["first_name"] for c in reversed_result["items"]]
    assert reversed_names == ["Zed", "Ann"]


def test_sort_contacts_by_company_pushes_blank_company_to_the_end(client):
    _create(client, first_name="NoCompany", company=None)
    _create(client, first_name="Zed", company="Zeta Corp")
    _create(client, first_name="Ann", company="Alpha Inc")

    ascending = client.get("/api/contacts", params={"sort": "company", "sort_dir": "asc"}).json()
    assert [c["first_name"] for c in ascending["items"]] == ["Ann", "Zed", "NoCompany"]

    descending = client.get("/api/contacts", params={"sort": "company", "sort_dir": "desc"}).json()
    assert [c["first_name"] for c in descending["items"]] == ["Zed", "Ann", "NoCompany"]
