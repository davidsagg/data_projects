from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.db.database import get_db
from src.models.models import Contact, Interaction
from src.models.schemas import (
    ContactCreate,
    ContactListItem,
    ContactOut,
    ContactPage,
    ContactUpdate,
    FacetItem,
)

router = APIRouter(prefix="/api", tags=["contacts"])


def _last_contacted_map(db: Session, contact_ids: list[int]) -> dict[int, object]:
    if not contact_ids:
        return {}
    rows = db.execute(
        select(Interaction.contact_id, func.max(Interaction.occurred_at))
        .where(Interaction.contact_id.in_(contact_ids))
        .group_by(Interaction.contact_id)
    ).all()
    return dict(rows)


@router.get("/contacts", response_model=ContactPage)
def list_contacts(
    q: str | None = None,
    group_id: int | None = None,
    company: str | None = None,
    position: str | None = None,
    city: str | None = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    query = select(Contact).options(selectinload(Contact.groups))

    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            func.lower(Contact.first_name + " " + Contact.last_name).like(like)
            | func.lower(func.coalesce(Contact.company, "")).like(like)
            | func.lower(func.coalesce(Contact.position, "")).like(like)
        )
    if group_id:
        query = query.where(Contact.groups.any(id=group_id))
    if company:
        query = query.where(func.lower(Contact.company) == company.lower())
    if position:
        query = query.where(func.lower(func.coalesce(Contact.position, "")).like(f"%{position.lower()}%"))
    if city:
        query = query.where(func.lower(Contact.city) == city.lower())

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    sort_map = {
        "name": (Contact.first_name, Contact.last_name),
        "company": (Contact.company,),
        "connected_on": (Contact.connected_on.desc(),),
        "recent": (Contact.created_at.desc(),),
    }
    for col in sort_map.get(sort, sort_map["name"]):
        query = query.order_by(col)

    query = query.offset((page - 1) * page_size).limit(page_size)
    contacts = db.scalars(query).unique().all()

    last_contacted = _last_contacted_map(db, [c.id for c in contacts])
    items = []
    for c in contacts:
        c.last_contacted_at = last_contacted.get(c.id)
        items.append(ContactListItem.model_validate(c))

    return ContactPage(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/companies", response_model=list[FacetItem])
def list_companies(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contact.company, func.count())
        .where(Contact.company.is_not(None))
        .group_by(Contact.company)
        .order_by(func.count().desc())
    ).all()
    return [FacetItem(value=v, count=c) for v, c in rows]


@router.get("/locations", response_model=list[FacetItem])
def list_locations(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contact.city, func.count())
        .where(Contact.city.is_not(None))
        .group_by(Contact.city)
        .order_by(func.count().desc())
    ).all()
    return [FacetItem(value=v, count=c) for v, c in rows]


@router.get("/contacts/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    contact.last_contacted_at = _last_contacted_map(db, [contact_id]).get(contact_id)
    return ContactOut.model_validate(contact)


@router.post("/contacts", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    contact = Contact(**payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    contact.last_contacted_at = None
    return ContactOut.model_validate(contact)


@router.put("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    contact.last_contacted_at = _last_contacted_map(db, [contact_id]).get(contact_id)
    return ContactOut.model_validate(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    db.delete(contact)
    db.commit()
