from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.database import Base


class Musician(Base):
    __tablename__ = "musicians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    instrument: Mapped[Optional[str]] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="musician")
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    pin_hash: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    execution_musicians: Mapped[List["ExecutionMusician"]] = relationship(
        back_populates="musician"
    )


class Song(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    artist: Mapped[Optional[str]] = mapped_column(String(200))
    key_original: Mapped[Optional[str]] = mapped_column(String(10))
    tempo_bpm: Mapped[Optional[int]] = mapped_column(Integer)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    genre_tags: Mapped[Optional[str]] = mapped_column(String(300))
    bkcp_content: Mapped[Optional[str]] = mapped_column(Text)
    pdf_original_path: Mapped[Optional[str]] = mapped_column(String(500))
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    parse_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    setlist_songs: Mapped[List["SetlistSong"]] = relationship(back_populates="song")
    executions: Mapped[List["MusicalExecution"]] = relationship(back_populates="song")


class Setlist(Base):
    __tablename__ = "setlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    songs: Mapped[List["SetlistSong"]] = relationship(
        back_populates="setlist",
        cascade="all, delete-orphan",
        order_by="SetlistSong.order_position",
    )
    events: Mapped[List["Event"]] = relationship(back_populates="setlist")


class SetlistSong(Base):
    """Associação ordenada entre Setlist e Song."""
    __tablename__ = "setlist_songs"
    __table_args__ = (UniqueConstraint("setlist_id", "order_position", name="uq_setlist_song_pos"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setlist_id: Mapped[int] = mapped_column(
        ForeignKey("setlists.id", ondelete="CASCADE"), nullable=False
    )
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), nullable=False)
    order_position: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    setlist: Mapped["Setlist"] = relationship(back_populates="songs")
    song: Mapped["Song"] = relationship(back_populates="setlist_songs")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    venue: Mapped[Optional[str]] = mapped_column(String(200))
    venue_address: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="tentative")
    checklist_json: Mapped[Optional[str]] = mapped_column(Text)
    setlist_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("setlists.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    setlist: Mapped[Optional["Setlist"]] = relationship(back_populates="events")
    executions: Mapped[List["MusicalExecution"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="MusicalExecution.order_position",
    )


class MusicalExecution(Base):
    """Execução de uma música em um evento específico."""
    __tablename__ = "musical_executions"
    __table_args__ = (UniqueConstraint("event_id", "song_id", name="uq_execution"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id"), nullable=False)
    order_position: Mapped[Optional[int]] = mapped_column(Integer)
    key_override: Mapped[Optional[str]] = mapped_column(String(10))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    event: Mapped["Event"] = relationship(back_populates="executions")
    song: Mapped["Song"] = relationship(back_populates="executions")
    musicians: Mapped[List["ExecutionMusician"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionMusician(Base):
    """Músico em uma execução específica (evento + música)."""
    __tablename__ = "execution_musicians"
    __table_args__ = (UniqueConstraint("execution_id", "musician_id", name="uq_exec_musician"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("musical_executions.id", ondelete="CASCADE"), nullable=False
    )
    musician_id: Mapped[int] = mapped_column(ForeignKey("musicians.id"), nullable=False)
    instrument_override: Mapped[Optional[str]] = mapped_column(String(80))

    execution: Mapped["MusicalExecution"] = relationship(back_populates="musicians")
    musician: Mapped["Musician"] = relationship(back_populates="execution_musicians")
