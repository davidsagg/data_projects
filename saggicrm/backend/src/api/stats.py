from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from src.db.database import get_db
from src.models.models import Contact, Group, Interaction, Reminder, contact_group
from src.models.schemas import ContactListItem, FacetItem, ReminderOut, StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    total_contacts = db.scalar(select(func.count()).select_from(Contact)) or 0
    total_groups = db.scalar(select(func.count()).select_from(Group)) or 0
    contacts_missing_city = (
        db.scalar(select(func.count()).where(Contact.city.is_(None))) or 0
    )

    top_companies = db.execute(
        select(Contact.company, func.count())
        .where(Contact.company.is_not(None))
        .group_by(Contact.company)
        .order_by(func.count().desc())
        .limit(10)
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
        .options(selectinload(Contact.groups))
        .order_by(Contact.created_at.desc())
        .limit(5)
    ).all()
    for c in recent_contacts:
        c.last_contacted_at = None

    return StatsOut(
        total_contacts=total_contacts,
        total_groups=total_groups,
        contacts_missing_city=contacts_missing_city,
        top_companies=[FacetItem(value=v, count=c) for v, c in top_companies],
        contacts_by_group=[FacetItem(value=v, count=c) for v, c in contacts_by_group],
        connections_by_year=[
            FacetItem(value=str(int(y)), count=c) for y, c in connections_by_year
        ],
        upcoming_reminders=[ReminderOut.model_validate(r) for r in upcoming_reminders],
        recent_contacts=[ContactListItem.model_validate(c) for c in recent_contacts],
    )
