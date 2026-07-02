from datetime import datetime
from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, ConfigDict
from pydantic.functional_serializers import PlainSerializer

# Serializa datetime como ISO UTC com 'Z' — evita ambiguidade de fuso no frontend.
# Sem isso, o JS interpreta strings sem 'Z' como horário local, causando desvio de 3h no Brasil.
UtcDt = Annotated[datetime, PlainSerializer(lambda v: v.isoformat() + "Z", return_type=str)]


# ── Músicos ───────────────────────────────────────────────────────

class MusicianCreate(BaseModel):
    name: str
    instrument: Optional[str] = None
    role: Literal["admin", "musician"] = "musician"
    email: Optional[str] = None
    photo_url: Optional[str] = None


class MusicianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    instrument: Optional[str] = None
    role: str
    email: Optional[str] = None
    photo_url: Optional[str] = None


# ── Músicas ───────────────────────────────────────────────────────

class SongCreate(BaseModel):
    title: str
    artist: Optional[str] = None
    key_original: Optional[str] = None
    bkcp_content: Optional[str] = None
    genre_tags: Optional[str] = None
    tempo_bpm: Optional[int] = None
    duration_sec: Optional[int] = None


class SongPatch(BaseModel):
    """Campos opcionais para edição manual da música."""
    title: Optional[str] = None
    artist: Optional[str] = None
    key_original: Optional[str] = None
    bkcp_content: Optional[str] = None
    genre_tags: Optional[str] = None


class SongOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    artist: Optional[str] = None
    key_original: Optional[str] = None
    bkcp_content: Optional[str] = None
    genre_tags: Optional[str] = None
    tempo_bpm: Optional[int] = None
    duration_sec: Optional[int] = None
    parse_status: str


class SongBrief(BaseModel):
    """Versão resumida da música (sem bkcp_content) para listas."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    artist: Optional[str] = None
    key_original: Optional[str] = None
    parse_status: str


# ── Setlists ──────────────────────────────────────────────────────

class SetlistCreate(BaseModel):
    name: str
    notes: Optional[str] = None


class SetlistSongCreate(BaseModel):
    song_id: int
    order_position: int
    notes: Optional[str] = None


class SetlistSongOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    song_id: int
    order_position: int
    notes: Optional[str] = None
    song: Optional[SongBrief] = None


class SetlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    notes: Optional[str] = None
    created_at: UtcDt
    songs: List[SetlistSongOut] = []


class SetlistBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    notes: Optional[str] = None


class ReorderItem(BaseModel):
    id: int
    order_position: int


# ── Eventos ───────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    date: datetime          # entrada: aceita qualquer datetime
    event_type: str
    status: str = "tentative"
    venue: Optional[str] = None
    venue_address: Optional[str] = None
    notes: Optional[str] = None
    duration_min: Optional[int] = None
    setlist_id: Optional[int] = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    date: UtcDt             # saída: sempre com 'Z' para o frontend interpretar como UTC
    event_type: str
    status: str
    venue: Optional[str] = None
    venue_address: Optional[str] = None
    notes: Optional[str] = None
    duration_min: Optional[int] = None
    setlist_id: Optional[int] = None
    setlist: Optional[SetlistBrief] = None


# ── Execuções musicais ────────────────────────────────────────────

class ExecutionMusicianCreate(BaseModel):
    musician_id: int
    instrument_override: Optional[str] = None


class ExecutionMusicianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    musician_id: int
    instrument_override: Optional[str] = None


class ExecutionCreate(BaseModel):
    song_id: int
    key_override: Optional[str] = None
    notes: Optional[str] = None


class ExecutionPatch(BaseModel):
    key_override: Optional[str] = None
    notes: Optional[str] = None


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    song_id: int
    order_position: Optional[int] = None
    key_override: Optional[str] = None
    notes: Optional[str] = None
    musicians: List[ExecutionMusicianOut] = []


# ── Duplicação ────────────────────────────────────────────────────

class EventDuplicateRequest(BaseModel):
    title: str
    date: datetime
    setlist_id: Optional[int] = None   # None = sem setlist; valor = setlist específico
    copy_musicians: bool = True         # copia músicos e tonalidades das execuções


class SetlistDuplicateRequest(BaseModel):
    name: Optional[str] = None         # None = nome original + " (cópia)"


# ── Transposição ──────────────────────────────────────────────────

class TransposeResponse(BaseModel):
    song_id: int
    semitones: int
    bkcp_transposed: str
    key_result: str
