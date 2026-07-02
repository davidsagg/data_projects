import os
import shutil
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional

from src.db.database import get_db
from src.models.models import ExecutionMusician, MusicalExecution, SetlistSong, Song
from src.models.schemas import SongCreate, SongOut, SongPatch, TransposeResponse
from src.chord_engine.transposer import transpose_bkcp, get_key_name


@lru_cache(maxsize=256)
def _cached_transpose(bkcp_content: str, semitones: int) -> str:
    return transpose_bkcp(bkcp_content, semitones)

router = APIRouter(prefix="/api/songs", tags=["songs"])


@router.get("", response_model=List[SongOut])
def list_songs(db: Session = Depends(get_db)):
    return db.query(Song).all()


@router.post("", response_model=SongOut, status_code=status.HTTP_201_CREATED)
def create_song(data: SongCreate, db: Session = Depends(get_db)):
    s = Song(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/upload", response_model=SongOut, status_code=status.HTTP_201_CREATED)
async def upload_song_pdf(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    artist: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDFs são aceitos")

    data_dir = os.environ.get("BANDKIT_DATA", "../bandkit-data")
    songs_dir = os.path.join(data_dir, "songs")
    os.makedirs(songs_dir, exist_ok=True)
    pdf_path = os.path.join(songs_dir, file.filename)

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from src.chord_engine.parser import pdf_to_bkcp
        bkcp_content, metadata = pdf_to_bkcp(pdf_path)
        parse_status = "parsed"
    except Exception:
        bkcp_content, metadata, parse_status = "", {}, "failed"

    song = Song(
        title=title or metadata.get("title") or file.filename,
        artist=artist or metadata.get("artist", ""),
        key_original=metadata.get("key", ""),
        bkcp_content=bkcp_content,
        pdf_original_path=pdf_path,
        parse_status=parse_status,
    )
    db.add(song)
    db.commit()
    db.refresh(song)
    return song


@router.patch("/{song_id}", response_model=SongOut)
def patch_song(song_id: int, data: SongPatch, db: Session = Depends(get_db)):
    """Edição manual de campos da música (bkcp_content, key_original, etc.)."""
    s = db.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404, detail="Song not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    s.parse_status = "manual"   # marca que o conteúdo foi editado manualmente
    _cached_transpose.cache_clear()
    db.commit()
    db.refresh(s)
    return s


@router.get("/{song_id}", response_model=SongOut)
def get_song(song_id: int, db: Session = Depends(get_db)):
    s = db.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404, detail="Song not found")
    return s


@router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_song(song_id: int, db: Session = Depends(get_db)):
    s = db.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404, detail="Song not found")

    # Remove PDF do disco
    if s.pdf_original_path and os.path.exists(s.pdf_original_path):
        os.remove(s.pdf_original_path)

    # Invalida cache de transposição para esta música
    _cached_transpose.cache_clear()

    # Deleta dependências em cascata (FK sem ondelete=CASCADE no schema)
    # 1. ExecutionMusician de todas as execuções desta música
    exec_ids = [
        row[0] for row in
        db.query(MusicalExecution.id).filter(MusicalExecution.song_id == song_id)
    ]
    if exec_ids:
        db.query(ExecutionMusician).filter(
            ExecutionMusician.execution_id.in_(exec_ids)
        ).delete(synchronize_session=False)

    # 2. Execuções musicais (evento + música)
    db.query(MusicalExecution).filter(
        MusicalExecution.song_id == song_id
    ).delete(synchronize_session=False)

    # 3. Entradas em todos os setlists que referenciam esta música
    db.query(SetlistSong).filter(
        SetlistSong.song_id == song_id
    ).delete(synchronize_session=False)

    # 4. Deleta a música
    db.delete(s)
    db.commit()


@router.post("/{song_id}/transpose", response_model=TransposeResponse)
def transpose_song(song_id: int, semitones: int = 0, db: Session = Depends(get_db)):
    s = db.get(Song, song_id)
    if not s:
        raise HTTPException(status_code=404, detail="Song not found")
    bkcp_transposed = _cached_transpose(s.bkcp_content or "", semitones)
    key_result = get_key_name(s.key_original or "", semitones)
    return TransposeResponse(
        song_id=song_id,
        semitones=semitones,
        bkcp_transposed=bkcp_transposed,
        key_result=key_result,
    )
