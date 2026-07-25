from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.models import Contact, Interaction
from src.models.schemas import InteractionCreate, InteractionOut

router = APIRouter(prefix="/api", tags=["interactions"])


@router.get("/contacts/{contact_id}/interactions", response_model=list[InteractionOut])
def list_interactions(contact_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Interaction)
        .where(Interaction.contact_id == contact_id)
        .order_by(Interaction.occurred_at.desc())
    ).all()


@router.post("/contacts/{contact_id}/interactions", response_model=InteractionOut, status_code=201)
def create_interaction(contact_id: int, payload: InteractionCreate, db: Session = Depends(get_db)):
    if not db.get(Contact, contact_id):
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    interaction = Interaction(
        contact_id=contact_id,
        type=payload.type,
        content=payload.content,
        occurred_at=payload.occurred_at or datetime.utcnow(),
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


@router.delete("/interactions/{interaction_id}", status_code=204)
def delete_interaction(interaction_id: int, db: Session = Depends(get_db)):
    interaction = db.get(Interaction, interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interação não encontrada")
    db.delete(interaction)
    db.commit()
