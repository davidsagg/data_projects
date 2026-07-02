from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

from src.db.database import get_db
from src.models.models import Event, ExecutionMusician, Musician, MusicalExecution, Setlist, SetlistSong
from src.models.schemas import (
    ExecutionCreate, ExecutionMusicianCreate, ExecutionMusicianOut,
    ExecutionOut, ExecutionPatch, ReorderItem,
)

router = APIRouter(prefix="/api/events", tags=["executions"])


# ── Helpers ────────────────────────────────────────────────────────

def _load_execution(event_id: int, exec_id: int, db: Session) -> MusicalExecution:
    ex = (
        db.query(MusicalExecution)
        .options(selectinload(MusicalExecution.musicians))
        .filter(MusicalExecution.id == exec_id, MusicalExecution.event_id == event_id)
        .first()
    )
    if not ex:
        raise HTTPException(404, "Execution not found")
    return ex


def _next_position(event_id: int, db: Session) -> int:
    """Retorna a próxima order_position disponível para o evento."""
    max_pos = (
        db.query(func.max(MusicalExecution.order_position))
        .filter(MusicalExecution.event_id == event_id)
        .scalar()
    )
    return (max_pos or 0) + 1


def _list_executions(event_id: int, musician_id: Optional[int], db: Session):
    """Lista execuções ordenadas pela order_position do próprio evento."""
    q = (
        db.query(MusicalExecution)
        .options(selectinload(MusicalExecution.musicians))
        .filter(MusicalExecution.event_id == event_id)
        .order_by(
            func.coalesce(MusicalExecution.order_position, 99_999),
            MusicalExecution.id,
        )
    )
    if musician_id is not None:
        q = q.join(ExecutionMusician).filter(ExecutionMusician.musician_id == musician_id)
    return q.all()


# ── Execuções ──────────────────────────────────────────────────────

@router.get("/{event_id}/executions", response_model=List[ExecutionOut])
def get_executions(
    event_id: int,
    musician_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    if not db.get(Event, event_id):
        raise HTTPException(404, "Event not found")
    return _list_executions(event_id, musician_id, db)


@router.post("/{event_id}/executions", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
def create_execution(event_id: int, data: ExecutionCreate, db: Session = Depends(get_db)):
    if not db.get(Event, event_id):
        raise HTTPException(404, "Event not found")
    pos = _next_position(event_id, db)
    ex = MusicalExecution(event_id=event_id, order_position=pos, **data.model_dump())
    db.add(ex)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Song already has an execution in this event")
    return _load_execution(event_id, ex.id, db)


@router.patch("/{event_id}/executions/{exec_id}", response_model=ExecutionOut)
def update_execution(
    event_id: int, exec_id: int, data: ExecutionPatch, db: Session = Depends(get_db)
):
    ex = _load_execution(event_id, exec_id, db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ex, k, v)
    db.commit()
    return _load_execution(event_id, exec_id, db)


@router.delete("/{event_id}/executions/{exec_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution(event_id: int, exec_id: int, db: Session = Depends(get_db)):
    ex = _load_execution(event_id, exec_id, db)
    db.delete(ex)
    db.commit()


@router.put("/{event_id}/executions/reorder")
def reorder_executions(event_id: int, items: List[ReorderItem], db: Session = Depends(get_db)):
    """Reordena as execuções de um evento. A ordem é independente do setlist."""
    if not db.get(Event, event_id):
        raise HTTPException(404, "Event not found")
    for r in items:
        ex = db.get(MusicalExecution, r.id)
        if ex and ex.event_id == event_id:
            ex.order_position = r.order_position
    db.commit()
    return {"ok": True}


# ── Músicos por execução ───────────────────────────────────────────

@router.post(
    "/{event_id}/executions/{exec_id}/musicians",
    response_model=ExecutionMusicianOut,
    status_code=status.HTTP_201_CREATED,
)
def add_musician(
    event_id: int, exec_id: int, data: ExecutionMusicianCreate, db: Session = Depends(get_db)
):
    _load_execution(event_id, exec_id, db)
    if not db.get(Musician, data.musician_id):
        raise HTTPException(404, "Musician not found")
    em = ExecutionMusician(execution_id=exec_id, **data.model_dump())
    db.add(em)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Musician already in this execution")
    db.refresh(em)
    return em


@router.delete(
    "/{event_id}/executions/{exec_id}/musicians/{musician_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_musician(
    event_id: int, exec_id: int, musician_id: int, db: Session = Depends(get_db)
):
    em = (
        db.query(ExecutionMusician)
        .filter(
            ExecutionMusician.execution_id == exec_id,
            ExecutionMusician.musician_id == musician_id,
        )
        .first()
    )
    if not em:
        raise HTTPException(404, "Assignment not found")
    db.delete(em)
    db.commit()


# ── Sincronização com setlist ──────────────────────────────────────

@router.post("/{event_id}/sync-setlist", response_model=List[ExecutionOut])
def sync_setlist(event_id: int, db: Session = Depends(get_db)):
    """
    Adiciona ao evento as músicas do setlist que ainda não têm execução.
    NÃO altera a ordem das execuções existentes.
    Novas execuções recebem posições após as já existentes, na ordem do setlist.
    """
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if not event.setlist_id:
        raise HTTPException(400, "Event has no setlist")

    setlist = (
        db.query(Setlist)
        .options(selectinload(Setlist.songs))
        .filter(Setlist.id == event.setlist_id)
        .first()
    )
    if not setlist:
        raise HTTPException(404, "Setlist not found")

    existing_song_ids = {ex.song_id for ex in event.executions}
    next_pos = _next_position(event_id, db)

    for entry in setlist.songs:          # já ordenado por order_position
        if entry.song_id not in existing_song_ids:
            db.add(MusicalExecution(
                event_id=event_id,
                song_id=entry.song_id,
                order_position=next_pos,
            ))
            next_pos += 1

    db.commit()
    return _list_executions(event_id, None, db)


@router.post("/{event_id}/reimport-setlist", response_model=List[ExecutionOut])
def reimport_setlist(event_id: int, db: Session = Depends(get_db)):
    """
    Sincronização completa com o setlist:
    - Remove execuções de músicas que saíram do setlist
    - Adiciona execuções para músicas novas (sem key_override)
    - Reordena todas as execuções para seguir a ordem atual do setlist
    - Preserva key_override e atribuições de músicos das execuções que permanecem
    """
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if not event.setlist_id:
        raise HTTPException(400, "Event has no setlist")

    setlist = (
        db.query(Setlist)
        .options(selectinload(Setlist.songs))
        .filter(Setlist.id == event.setlist_id)
        .first()
    )
    if not setlist:
        raise HTTPException(404, "Setlist not found")

    setlist_song_ids = {entry.song_id for entry in setlist.songs}
    existing_by_song = {ex.song_id: ex for ex in event.executions}

    # Remove execuções de músicas que saíram do setlist
    for song_id, ex in existing_by_song.items():
        if song_id not in setlist_song_ids:
            db.delete(ex)
    db.flush()

    # Atualiza order_position e adiciona músicas novas, seguindo a ordem do setlist
    for idx, entry in enumerate(setlist.songs, start=1):
        if entry.song_id in existing_by_song:
            existing_by_song[entry.song_id].order_position = idx
        else:
            db.add(MusicalExecution(
                event_id=event_id,
                song_id=entry.song_id,
                order_position=idx,
            ))

    db.commit()
    return _list_executions(event_id, None, db)
