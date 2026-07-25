from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.db.database import get_db
from src.models.models import Contact, Reminder
from src.models.schemas import ReminderCreate, ReminderOut, ReminderUpdate

router = APIRouter(prefix="/api", tags=["reminders"])


@router.get("/reminders", response_model=list[ReminderOut])
def list_all_reminders(status: str = "pending", db: Session = Depends(get_db)):
    query = select(Reminder).options(joinedload(Reminder.contact))
    today = date.today()
    if status == "pending":
        query = query.where(Reminder.is_done.is_(False))
    elif status == "overdue":
        query = query.where(Reminder.is_done.is_(False), Reminder.due_date < today)
    elif status == "done":
        query = query.where(Reminder.is_done.is_(True))
    query = query.order_by(Reminder.due_date)
    return db.scalars(query).all()


@router.get("/contacts/{contact_id}/reminders", response_model=list[ReminderOut])
def list_contact_reminders(contact_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Reminder).where(Reminder.contact_id == contact_id).order_by(Reminder.due_date)
    ).all()


@router.post("/contacts/{contact_id}/reminders", response_model=ReminderOut, status_code=201)
def create_reminder(contact_id: int, payload: ReminderCreate, db: Session = Depends(get_db)):
    if not db.get(Contact, contact_id):
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    reminder = Reminder(contact_id=contact_id, **payload.model_dump())
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(reminder_id: int, payload: ReminderUpdate, db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_done") and not reminder.is_done:
        reminder.completed_at = datetime.utcnow()
    elif data.get("is_done") is False:
        reminder.completed_at = None
    for field, value in data.items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: int, db: Session = Depends(get_db)):
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Lembrete não encontrado")
    db.delete(reminder)
    db.commit()
