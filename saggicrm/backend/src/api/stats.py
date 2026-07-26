from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from src.db.database import get_db
from src.models.models import Company, Contact, Group, Interaction, Reminder, contact_group
from src.models.schemas import ContactListItem, FacetItem, ReminderOut, StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    total_contacts = db.scalar(select(func.count()).select_from(Contact)) or 0
    total_groups = db.scalar(select(func.count()).select_from(Group)) or 0
    contacts_missing_city = (
        db.scalar(select(func.count()).where(Contact.city.is_(None))) or 0
    )
    total_favorites = db.scalar(select(func.count()).where(Contact.is_favorite.is_(True))) or 0

    top_companies = db.execute(
        select(Company.id, Company.name, func.count(Contact.id))
        .join(Contact, Contact.company_id == Company.id)
        .group_by(Company.id)
        .order_by(func.count(Contact.id).desc())
        .limit(10)
    ).all()

    top_sectors = db.execute(
        select(Company.sector, func.count(Contact.id))
        .join(Contact, Contact.company_id == Company.id)
        .where(Company.sector.is_not(None))
        .group_by(Company.sector)
        .order_by(func.count(Contact.id).desc())
        .limit(10)
    ).all()

    seniority_breakdown = db.execute(
        select(Contact.seniority, func.count())
        .where(Contact.seniority.is_not(None))
        .group_by(Contact.seniority)
        .order_by(func.count().desc())
    ).all()

    contacts_by_group = db.execute(
        select(Group.name, func.count(contact_group.c.contact_id))
        .join(contact_group, contact_group.c.group_id == Group.id)
        .group_by(Group.name)
        .order_by(func.count(contact_group.c.contact_id).desc())
    ).all()

    connections_by_year = db.execute(
        select(extract("year", Contact.connected_on), func.count())
        .where(Contact.connected_on.is_not(None))
        .group_by(extract("year", Contact.connected_on))
        .order_by(extract("year", Contact.connected_on))
    ).all()

    upcoming_reminders = db.scalars(
        select(Reminder)
        .where(Reminder.is_done.is_(False))
        .order_by(Reminder.due_date)
        .limit(5)
    ).all()

    recent_contacts = db.scalars(
        select(Contact)
        .options(selectinload(Contact.groups), selectinload(Contact.company_ref))
        .order_by(Contact.created_at.desc())
        .limit(5)
    ).all()
    for c in recent_contacts:
        c.last_contacted_at = None
        c.sector = c.company_ref.sector if c.company_ref else None

    favorite_contacts = db.scalars(
        select(Contact)
        .options(selectinload(Contact.groups), selectinload(Contact.company_ref))
        .where(Contact.is_favorite.is_(True))
        .order_by(Contact.first_name, Contact.last_name)
        .limit(8)
    ).all()
    for c in favorite_contacts:
        c.last_contacted_at = None
        c.sector = c.company_ref.sector if c.company_ref else None

    return StatsOut(
        total_contacts=total_contacts,
        total_groups=total_groups,
        contacts_missing_city=contacts_missing_city,
        total_favorites=total_favorites,
        top_companies=[FacetItem(id=i, value=v, count=c) for i, v, c in top_companies],
        contacts_by_group=[FacetItem(value=v, count=c) for v, c in contacts_by_group],
        connections_by_year=[
            FacetItem(value=str(int(y)), count=c) for y, c in connections_by_year
        ],
        top_sectors=[FacetItem(value=v, count=c) for v, c in top_sectors],
        seniority_breakdown=[FacetItem(value=v, count=c) for v, c in seniority_breakdown],
        upcoming_reminders=[ReminderOut.model_validate(r) for r in upcoming_reminders],
        recent_contacts=[ContactListItem.model_validate(c) for c in recent_contacts],
        favorite_contacts=[ContactListItem.model_validate(c) for c in favorite_contacts],
    )
