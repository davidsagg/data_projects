from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.db.database import get_db
from src.models.models import Musician
from src.models.schemas import MusicianCreate, MusicianOut

router = APIRouter(prefix="/api/musicians", tags=["musicians"])


@router.get("", response_model=List[MusicianOut])
def list_musicians(db: Session = Depends(get_db)):
    return db.query(Musician).all()


@router.post("", response_model=MusicianOut, status_code=status.HTTP_201_CREATED)
def create_musician(data: MusicianCreate, db: Session = Depends(get_db)):
    m = Musician(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.get("/{musician_id}", response_model=MusicianOut)
def get_musician(musician_id: int, db: Session = Depends(get_db)):
    m = db.get(Musician, musician_id)
    if not m:
        raise HTTPException(status_code=404, detail="Musician not found")
    return m


@router.put("/{musician_id}", response_model=MusicianOut)
def update_musician(musician_id: int, data: MusicianCreate, db: Session = Depends(get_db)):
    m = db.get(Musician, musician_id)
    if not m:
        raise HTTPException(status_code=404, detail="Musician not found")
    for key, value in data.model_dump().items():
        setattr(m, key, value)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{musician_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_musician(musician_id: int, db: Session = Depends(get_db)):
    m = db.get(Musician, musician_id)
    if not m:
        raise HTTPException(status_code=404, detail="Musician not found")
    db.delete(m)
    db.commit()
