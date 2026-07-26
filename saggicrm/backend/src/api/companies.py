from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.db.database import get_db
from src.models.models import Company, Contact
from src.models.schemas import (
    BulkSectorRequest,
    CompanyDetail,
    CompanyOut,
    CompanyUpdate,
    ContactListItem,
    FacetItem,
)

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _contact_counts(db: Session, company_ids: list[int] | None = None) -> dict[int, int]:
    query = select(Contact.company_id, func.count()).where(Contact.company_id.is_not(None))
    if company_ids is not None:
        query = query.where(Contact.company_id.in_(company_ids))
    rows = db.execute(query.group_by(Contact.company_id)).all()
    return dict(rows)


# "￿" keeps companies without a sector last in an ascending sort, without
# needing a separate (is_none, value) tuple that reverse=True would flip awkwardly.
_SORT_KEYS = {
    "contacts": lambda c: c.contact_count,
    "name": lambda c: c.name.lower(),
    "sector": lambda c: (c.sector or "￿").lower(),
}


@router.get("", response_model=list[CompanyOut])
def list_companies(
    sector: str | None = None,
    q: str | None = None,
    sort: str = "contacts",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
):
    query = select(Company)
    if sector:
        query = query.where(Company.sector == sector)
    if q:
        query = query.where(func.lower(Company.name).like(f"%{q.lower()}%"))
    companies = db.scalars(query).all()

    counts = _contact_counts(db)
    items = [
        CompanyOut(id=c.id, name=c.name, sector=c.sector, contact_count=counts.get(c.id, 0))
        for c in companies
    ]
    key_fn = _SORT_KEYS.get(sort, _SORT_KEYS["contacts"])
    items.sort(key=lambda c: (key_fn(c), c.name.lower()), reverse=(sort_dir == "desc"))
    return items


@router.get("/{company_id}", response_model=CompanyDetail)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    contacts = db.scalars(
        select(Contact)
        .options(selectinload(Contact.groups))
        .where(Contact.company_id == company_id)
        .order_by(Contact.first_name, Contact.last_name)
    ).all()
    for c in contacts:
        c.last_contacted_at = None
        c.sector = company.sector

    seniority_rows = db.execute(
        select(Contact.seniority, func.count())
        .where(Contact.company_id == company_id)
        .group_by(Contact.seniority)
        .order_by(func.count().desc())
    ).all()

    return CompanyDetail(
        id=company.id,
        name=company.name,
        sector=company.sector,
        contact_count=len(contacts),
        seniority_breakdown=[FacetItem(value=v or "Não classificado", count=c) for v, c in seniority_rows],
        contacts=[ContactListItem.model_validate(c) for c in contacts],
    )


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    count = _contact_counts(db, [company_id]).get(company_id, 0)
    return CompanyOut(id=company.id, name=company.name, sector=company.sector, contact_count=count)


@router.post("/bulk-sector", status_code=204)
def bulk_assign_sector(payload: BulkSectorRequest, db: Session = Depends(get_db)):
    db.query(Company).filter(Company.id.in_(payload.company_ids)).update(
        {"sector": payload.sector}, synchronize_session=False
    )
    db.commit()
