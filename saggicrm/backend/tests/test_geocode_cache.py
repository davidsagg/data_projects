from src.services import geocode as geocode_service


def test_geocode_uses_cache_and_avoids_second_network_call(db_session, monkeypatch):
    calls = []

    def fake_query(company_name):
        calls.append(company_name)
        return {"city": "São Paulo", "country": "Brazil", "latitude": -23.5, "longitude": -46.6}

    monkeypatch.setattr(geocode_service, "_query_nominatim", fake_query)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    first = geocode_service.get_or_geocode_company(db_session, "Acme Corp")
    second = geocode_service.get_or_geocode_company(db_session, "Acme Corp")

    assert first.found is True
    assert first.city == "São Paulo"
    assert second.city == "São Paulo"
    assert len(calls) == 1


def test_geocode_caches_negative_result_without_retry_by_default(db_session, monkeypatch):
    calls = []

    def fake_query(company_name):
        calls.append(company_name)
        return None

    monkeypatch.setattr(geocode_service, "_query_nominatim", fake_query)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    first = geocode_service.get_or_geocode_company(db_session, "Unknown Ltda")
    second = geocode_service.get_or_geocode_company(db_session, "Unknown Ltda")

    assert first.found is False
    assert second.found is False
    assert len(calls) == 1


def test_geocode_force_retry_calls_network_again(db_session, monkeypatch):
    calls = []

    def fake_query(company_name):
        calls.append(company_name)
        return None

    monkeypatch.setattr(geocode_service, "_query_nominatim", fake_query)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    geocode_service.get_or_geocode_company(db_session, "Unknown Ltda")
    geocode_service.get_or_geocode_company(db_session, "Unknown Ltda", force_retry=True)

    assert len(calls) == 2


def test_normalize_is_case_and_whitespace_insensitive(db_session, monkeypatch):
    calls = []

    def fake_query(company_name):
        calls.append(company_name)
        return {"city": "Lisboa", "country": "Portugal", "latitude": 1.0, "longitude": 2.0}

    monkeypatch.setattr(geocode_service, "_query_nominatim", fake_query)
    monkeypatch.setattr(geocode_service, "_throttle", lambda: None)

    geocode_service.get_or_geocode_company(db_session, "  Acme  Corp ")
    geocode_service.get_or_geocode_company(db_session, "ACME CORP")

    assert len(calls) == 1
