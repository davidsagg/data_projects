import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.models import CompanyGeocodeCache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "saggicrm-personal-crm/1.0 (local personal use)"
MIN_INTERVAL_SECONDS = 1.1

_last_request_at = 0.0


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_SECONDS:
        time.sleep(MIN_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def _normalize(company_name: str) -> str:
    return " ".join(company_name.split()).strip().lower()


def _query_nominatim(company_name: str) -> dict | None:
    _throttle()
    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={"q": company_name, "format": "jsonv2", "addressdetails": 1, "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10.0,
        )
        response.raise_for_status()
        results = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not results:
        return None
    address = results[0].get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
    )
    return {
        "city": city,
        "country": address.get("country"),
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
    }


def get_or_geocode_company(
    db: Session, company_name: str, force_retry: bool = False
) -> CompanyGeocodeCache:
    normalized = _normalize(company_name)
    cached = db.scalar(
        select(CompanyGeocodeCache).where(CompanyGeocodeCache.company_name == normalized)
    )
    if cached and (cached.found or not force_retry):
        return cached

    result = _query_nominatim(company_name)
    if cached is None:
        cached = CompanyGeocodeCache(company_name=normalized)
        db.add(cached)

    if result:
        cached.city = result["city"]
        cached.country = result["country"]
        cached.latitude = result["latitude"]
        cached.longitude = result["longitude"]
        cached.found = True
    else:
        cached.found = False

    db.commit()
    db.refresh(cached)
    return cached
