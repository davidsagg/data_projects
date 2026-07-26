from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.models import CompanyGeocodeCache, Contact
from src.models.schemas import BulkGeocodeResult, GeocodeResult
from src.services.geocode import _normalize, get_or_geocode_company

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

DEFAULT_BULK_CHUNK = 15


class CompanyGeocodeRequest(BaseModel):
    company_name: str
    force_retry: bool = False


def _to_result(company_name: str, cache_row) -> GeocodeResult:
    return GeocodeResult(
        company_name=company_name,
        found=cache_row.found,
        city=cache_row.city,
        country=cache_row.country,
        latitude=cache_row.latitude,
        longitude=cache_row.longitude,
    )


@router.post("/company", response_model=GeocodeResult)
def geocode_company(payload: CompanyGeocodeRequest, db: Session = Depends(get_db)):
    cache_row = get_or_geocode_company(db, payload.company_name, force_retry=payload.force_retry)
    return _to_result(payload.company_name, cache_row)


@router.post("/bulk", response_model=BulkGeocodeResult)
def geocode_bulk(chunk_size: int = DEFAULT_BULK_CHUNK, db: Session = Depends(get_db)):
    companies = db.scalars(
        select(Contact.company)
        .where(Contact.company.is_not(None), Contact.city.is_(None))
        .distinct()
    ).all()

    # Companies already attempted (found or not) are skipped here — a failed lookup
    # never disappears from the "missing city" query above, so without this filter
    # the same unresolved companies would be retried forever and `remaining` would
    # never reach 0. Retrying a specific failure is what `force_retry` is for.
    already_tried = set(db.scalars(select(CompanyGeocodeCache.company_name)).all())
    pending = [c for c in companies if _normalize(c) not in already_tried]

    to_process = pending[:chunk_size]
    results = []
    for company_name in to_process:
        cache_row = get_or_geocode_company(db, company_name)
        results.append(_to_result(company_name, cache_row))
        if cache_row.found:
            db.query(Contact).filter(
                Contact.company == company_name, Contact.city.is_(None)
            ).update(
                {
                    "city": cache_row.city,
                    "country": cache_row.country,
                    "latitude": cache_row.latitude,
                    "longitude": cache_row.longitude,
                },
                synchronize_session=False,
            )
            db.commit()

    remaining = max(0, len(pending) - len(to_process))
    return BulkGeocodeResult(processed=len(to_process), remaining=remaining, results=results)
