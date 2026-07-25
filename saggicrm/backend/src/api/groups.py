from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.models import Contact, Group
from src.models.schemas import GroupCreate, GroupOut, GroupUpdate

router = APIRouter(prefix="/api", tags=["groups"])


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db)):
    return db.scalars(select(Group).order_by(Group.name)).all()


@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Group).where(Group.name == payload.name)):
        raise HTTPException(status_code=409, detail="Já existe um grupo com esse nome")
    group = Group(**payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/groups/{group_id}", response_model=GroupOut)
def update_group(group_id: int, payload: GroupUpdate, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    db.delete(group)
    db.commit()


@router.post("/contacts/{contact_id}/groups/{group_id}", response_model=GroupOut)
def assign_group(contact_id: int, group_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    group = db.get(Group, group_id)
    if not contact or not group:
        raise HTTPException(status_code=404, detail="Contato ou grupo não encontrado")
    if group not in contact.groups:
        contact.groups.append(group)
        db.commit()
    return group


@router.delete("/contacts/{contact_id}/groups/{group_id}", status_code=204)
def remove_group(contact_id: int, group_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    group = db.get(Group, group_id)
    if not contact or not group:
        raise HTTPException(status_code=404, detail="Contato ou grupo não encontrado")
    if group in contact.groups:
        contact.groups.remove(group)
        db.commit()
