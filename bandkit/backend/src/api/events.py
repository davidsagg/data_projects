from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

from src.db.database import get_db
from src.models.models import Event, ExecutionMusician, MusicalExecution, Setlist, SetlistSong
from src.models.schemas import EventCreate, EventDuplicateRequest, EventOut

router = APIRouter(prefix="/api/events", tags=["events"])


def _load(event_id: int, db: Session) -> Event:
    ev = (
        db.query(Event)
        .options(selectinload(Event.setlist))
        .filter(Event.id == event_id)
        .first()
    )
    if not ev:
        raise HTTPException(404, "Event not found")
    return ev


@router.get("", response_model=List[EventOut])
def list_events(musician_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Event).options(selectinload(Event.setlist)).order_by(Event.date)
    if musician_id is not None:
        sq = (
            db.query(MusicalExecution.event_id)
            .join(ExecutionMusician)
            .filter(ExecutionMusician.musician_id == musician_id)
            .distinct()
            .subquery()
        )
        q = q.filter(Event.id.in_(sq))
    return q.all()


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    if data.setlist_id and not db.get(Setlist, data.setlist_id):
        raise HTTPException(404, "Setlist not found")
    ev = Event(**data.model_dump())
    db.add(ev)
    db.commit()

    # Auto-cria execuções para as músicas do setlist
    if ev.setlist_id:
        setlist = (
            db.query(Setlist)
            .options(selectinload(Setlist.songs))
            .filter(Setlist.id == ev.setlist_id)
            .first()
        )
        if setlist:
            for entry in setlist.songs:
                db.add(MusicalExecution(event_id=ev.id, song_id=entry.song_id))
            db.commit()

    return _load(ev.id, db)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return _load(event_id, db)


@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: int, data: EventCreate, db: Session = Depends(get_db)):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    if data.setlist_id and not db.get(Setlist, data.setlist_id):
        raise HTTPException(404, "Setlist not found")
    for k, v in data.model_dump().items():
        setattr(ev, k, v)
    db.commit()
    return _load(event_id, db)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(404, "Event not found")
    db.delete(ev)
    db.commit()


@router.post("/{event_id}/duplicate", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def duplicate_event(event_id: int, data: EventDuplicateRequest, db: Session = Depends(get_db)):
    """Cria uma cópia do evento com nova data. Copia execuções e, opcionalmente, músicos."""
    original = _load(event_id, db)

    if data.setlist_id is not None and not db.get(Setlist, data.setlist_id):
        raise HTTPException(404, "Setlist not found")

    new_setlist_id = data.setlist_id  # frontend envia o setlist_id resolvido

    new_ev = Event(
        title=data.title,
        date=data.date,
        event_type=original.event_type,
        status="tentative",
        venue=original.venue,
        venue_address=original.venue_address,
        notes=original.notes,
        duration_min=original.duration_min,
        setlist_id=new_setlist_id,
    )
    db.add(new_ev)
    db.commit()

    # Auto-cria execuções do setlist
    if new_setlist_id:
        setlist = (
            db.query(Setlist)
            .options(selectinload(Setlist.songs))
            .filter(Setlist.id == new_setlist_id)
            .first()
        )
        if setlist:
            for entry in setlist.songs:
                db.add(MusicalExecution(event_id=new_ev.id, song_id=entry.song_id))
            db.commit()

    # Copia músicos (e tonalidades) das execuções originais
    if data.copy_musicians:
        orig_execs = (
            db.query(MusicalExecution)
            .options(selectinload(MusicalExecution.musicians))
            .filter(MusicalExecution.event_id == event_id)
            .all()
        )
        new_execs = db.query(MusicalExecution).filter(MusicalExecution.event_id == new_ev.id).all()
        new_by_song = {ex.song_id: ex for ex in new_execs}

        for orig in orig_execs:
            new_ex = new_by_song.get(orig.song_id)
            if not new_ex:
                # Execução manual (não veio do setlist) — cria também
                new_ex = MusicalExecution(event_id=new_ev.id, song_id=orig.song_id)
                db.add(new_ex)
                db.flush()
                new_by_song[orig.song_id] = new_ex

            new_ex.key_override = orig.key_override

            for em in orig.musicians:
                db.add(ExecutionMusician(
                    execution_id=new_ex.id,
                    musician_id=em.musician_id,
                    instrument_override=em.instrument_override,
                ))

        db.commit()

    return _load(new_ev.id, db)
