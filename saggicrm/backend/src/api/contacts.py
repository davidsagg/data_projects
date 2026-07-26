from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, case, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.db.database import get_db
from src.models.models import Company, Contact, Interaction
from src.models.schemas import (
    ContactCreate,
    ContactListItem,
    ContactOut,
    ContactPage,
    ContactUpdate,
    FacetItem,
)
from src.services.companies import get_or_create_company
from src.services.seniority import SENIORITY_LEVELS, classify_seniority

router = APIRouter(prefix="/api", tags=["contacts"])

# Orders by actual seniority rank (C-Level first) rather than alphabetically —
# SENIORITY_LEVELS is already ranked most-senior-first in seniority.py.
_SENIORITY_RANK = case(
    {level: i for i, level in enumerate(SENIORITY_LEVELS)},
    value=Contact.seniority,
    else_=len(SENIORITY_LEVELS),
)


def _last_contacted_map(db: Session, contact_ids: list[int]) -> dict[int, object]:
    if not contact_ids:
        return {}
    rows = db.execute(
        select(Interaction.contact_id, func.max(Interaction.occurred_at))
        .where(Interaction.contact_id.in_(contact_ids))
        .group_by(Interaction.contact_id)
    ).all()
    return dict(rows)


def _apply_derived_fields(db: Session, contact: Contact) -> None:
    """Keeps company_id and seniority in sync with the free-text company/position."""
    contact.company_id = get_or_create_company(db, contact.company).id if contact.company else None
    contact.seniority = classify_seniority(contact.position)


def _to_list_item(contact: Contact) -> ContactListItem:
    contact.sector = contact.company_ref.sector if contact.company_ref else None
    return ContactListItem.model_validate(contact)


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Já existe outro contato com essa URL do LinkedIn"
        ) from exc


@router.get("/contacts", response_model=ContactPage)
def list_contacts(
    q: str | None = None,
    group_id: int | None = None,
    company_id: int | None = None,
    sector: str | None = None,
    seniority: str | None = None,
    position: str | None = None,
    city: str | None = None,
    favorite_only: bool = False,
    sort: str = "name",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    query = select(Contact).options(selectinload(Contact.groups), selectinload(Contact.company_ref))

    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            func.lower(Contact.first_name + " " + Contact.last_name).like(like)
            | func.lower(func.coalesce(Contact.company, "")).like(like)
            | func.lower(func.coalesce(Contact.position, "")).like(like)
        )
    if group_id:
        query = query.where(Contact.groups.any(id=group_id))
    if company_id:
        query = query.where(Contact.company_id == company_id)
    if sector:
        query = query.where(Contact.company_ref.has(Company.sector == sector))
    if seniority:
        query = query.where(Contact.seniority == seniority)
    if position:
        query = query.where(func.lower(func.coalesce(Contact.position, "")).like(f"%{position.lower()}%"))
    if city:
        query = query.where(func.lower(Contact.city) == city.lower())
    if favorite_only:
        query = query.where(Contact.is_favorite.is_(True))

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    sort_map = {
        "name": (Contact.first_name, Contact.last_name),
        "company": (Contact.company,),
        "seniority": (_SENIORITY_RANK,),
        "connected_on": (Contact.connected_on,),
        "recent": (Contact.created_at,),
    }
    # Contacts with no company/connection-date shouldn't flood the top of the list
    # just because SQL treats NULL as the smallest value in ASC order — always
    # push them to the bottom, independent of the chosen direction.
    nulls_last_fields = {"company", "connected_on"}

    direction = desc if sort_dir == "desc" else asc
    primary_cols = sort_map.get(sort, sort_map["name"])
    if sort in nulls_last_fields:
        query = query.order_by(primary_cols[0].is_(None))
    for col in primary_cols:
        query = query.order_by(direction(col))
    if sort != "name":
        # stable, readable tiebreaker so equal-rank rows aren't in arbitrary order
        query = query.order_by(Contact.first_name, Contact.last_name)

    query = query.offset((page - 1) * page_size).limit(page_size)
    contacts = db.scalars(query).unique().all()

    last_contacted = _last_contacted_map(db, [c.id for c in contacts])
    items = []
    for c in contacts:
        c.last_contacted_at = last_contacted.get(c.id)
        items.append(_to_list_item(c))

    return ContactPage(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/locations", response_model=list[FacetItem])
def list_locations(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contact.city, func.count())
        .where(Contact.city.is_not(None))
        .group_by(Contact.city)
        .order_by(func.count().desc())
    ).all()
    return [FacetItem(value=v, count=c) for v, c in rows]


@router.get("/seniority-levels", response_model=list[FacetItem])
def list_seniority_levels(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contact.seniority, func.count())
        .where(Contact.seniority.is_not(None))
        .group_by(Contact.seniority)
        .order_by(func.count().desc())
    ).all()
    return [FacetItem(value=v, count=c) for v, c in rows]


@router.get("/contacts/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    contact.last_contacted_at = _last_contacted_map(db, [contact_id]).get(contact_id)
    contact.sector = contact.company_ref.sector if contact.company_ref else None
    return ContactOut.model_validate(contact)


@router.post("/contacts", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    contact = Contact(**payload.model_dump())
    _apply_derived_fields(db, contact)
    db.add(contact)
    _commit_or_conflict(db)
    db.refresh(contact)
    contact.last_contacted_at = None
    contact.sector = contact.company_ref.sector if contact.company_ref else None
    return ContactOut.model_validate(contact)


@router.put("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    _apply_derived_fields(db, contact)
    _commit_or_conflict(db)
    db.refresh(contact)
    contact.last_contacted_at = _last_contacted_map(db, [contact_id]).get(contact_id)
    contact.sector = contact.company_ref.sector if contact.company_ref else None
    return ContactOut.model_validate(contact)


@router.patch("/contacts/{contact_id}/favorite", response_model=ContactOut)
def toggle_favorite(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    contact.is_favorite = not contact.is_favorite
    db.commit()
    db.refresh(contact)
    contact.last_contacted_at = _last_contacted_map(db, [contact_id]).get(contact_id)
    contact.sector = contact.company_ref.sector if contact.company_ref else None
    return ContactOut.model_validate(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    db.delete(contact)
    db.commit()
