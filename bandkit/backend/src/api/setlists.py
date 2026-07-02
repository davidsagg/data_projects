from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from typing import List

from src.db.database import get_db
from src.models.models import Setlist, SetlistSong, Song
from src.models.schemas import (
    ReorderItem, SetlistCreate, SetlistDuplicateRequest, SetlistOut, SetlistSongCreate, SetlistSongOut,
)

router = APIRouter(prefix="/api/setlists", tags=["setlists"])


def _load(setlist_id: int, db: Session) -> Setlist:
    sl = (
        db.query(Setlist)
        .options(selectinload(Setlist.songs).selectinload(SetlistSong.song))
        .filter(Setlist.id == setlist_id)
        .first()
    )
    if not sl:
        raise HTTPException(404, "Setlist not found")
    return sl


@router.get("", response_model=List[SetlistOut])
def list_setlists(db: Session = Depends(get_db)):
    return (
        db.query(Setlist)
        .options(selectinload(Setlist.songs).selectinload(SetlistSong.song))
        .all()
    )


@router.post("", response_model=SetlistOut, status_code=status.HTTP_201_CREATED)
def create_setlist(data: SetlistCreate, db: Session = Depends(get_db)):
    sl = Setlist(**data.model_dump())
    db.add(sl)
    db.commit()
    return _load(sl.id, db)


@router.get("/{setlist_id}", response_model=SetlistOut)
def get_setlist(setlist_id: int, db: Session = Depends(get_db)):
    return _load(setlist_id, db)


@router.put("/{setlist_id}", response_model=SetlistOut)
def update_setlist(setlist_id: int, data: SetlistCreate, db: Session = Depends(get_db)):
    sl = db.get(Setlist, setlist_id)
    if not sl:
        raise HTTPException(404, "Setlist not found")
    for k, v in data.model_dump().items():
        setattr(sl, k, v)
    db.commit()
    return _load(setlist_id, db)


@router.delete("/{setlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setlist(setlist_id: int, db: Session = Depends(get_db)):
    sl = db.get(Setlist, setlist_id)
    if not sl:
        raise HTTPException(404, "Setlist not found")
    db.delete(sl)
    db.commit()


@router.post("/{setlist_id}/songs", response_model=SetlistSongOut, status_code=status.HTTP_201_CREATED)
def add_song(setlist_id: int, data: SetlistSongCreate, db: Session = Depends(get_db)):
    if not db.get(Setlist, setlist_id):
        raise HTTPException(404, "Setlist not found")
    if not db.get(Song, data.song_id):
        raise HTTPException(404, "Song not found")
    entry = SetlistSong(setlist_id=setlist_id, **data.model_dump())
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Position already taken in setlist")
    db.refresh(entry)
    # reload with song relationship
    return (
        db.query(SetlistSong)
        .options(selectinload(SetlistSong.song))
        .filter(SetlistSong.id == entry.id)
        .first()
    )


@router.delete("/{setlist_id}/songs/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_song(setlist_id: int, entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(SetlistSong, entry_id)
    if not entry or entry.setlist_id != setlist_id:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    db.commit()


@router.post("/{setlist_id}/duplicate", response_model=SetlistOut, status_code=status.HTTP_201_CREATED)
def duplicate_setlist(setlist_id: int, data: SetlistDuplicateRequest, db: Session = Depends(get_db)):
    """Cria uma cópia do setlist com as mesmas músicas na mesma ordem."""
    original = _load(setlist_id, db)
    new_name = data.name or (original.name + " (cópia)")
    new_sl = Setlist(name=new_name, notes=original.notes)
    db.add(new_sl)
    db.commit()
    for entry in original.songs:
        db.add(SetlistSong(
            setlist_id=new_sl.id,
            song_id=entry.song_id,
            order_position=entry.order_position,
            notes=entry.notes,
        ))
    db.commit()
    return _load(new_sl.id, db)


@router.put("/{setlist_id}/reorder")
def reorder_songs(setlist_id: int, items: List[ReorderItem], db: Session = Depends(get_db)):
    if not db.get(Setlist, setlist_id):
        raise HTTPException(404, "Setlist not found")

    # Duas fases para evitar colisão na constraint UNIQUE(setlist_id, order_position).
    # Fase 1: move para posições temporárias altas (ex: 100001, 100002…)
    # Fase 2: aplica as posições finais (sem conflito, pois as antigas já sumiram)
    OFFSET = 100_000
    entries = {r.id: db.get(SetlistSong, r.id) for r in items}

    for r in items:
        entry = entries[r.id]
        if entry and entry.setlist_id == setlist_id:
            entry.order_position = r.order_position + OFFSET
    db.flush()

    for r in items:
        entry = entries[r.id]
        if entry and entry.setlist_id == setlist_id:
            entry.order_position = r.order_position
    db.commit()

    return {"ok": True}
