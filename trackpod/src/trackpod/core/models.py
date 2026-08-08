"""SQLAlchemy ORM models for the Trackpod library (single source of truth)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    """A music source the user added (playlist URL or artist favorite)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # spotify|youtube|apple|artist
    external_ref: Mapped[str] = mapped_column(String, default="")  # url / artist permalink
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list[SourceItem]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class SourceItem(Base):
    """A raw playlist row from a source (lightweight; no download yet)."""

    __tablename__ = "source_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    external_id: Mapped[str] = mapped_column(String, default="")  # provider track/playlist id
    ref: Mapped[str] = mapped_column(String, default="")  # url or permalink
    title: Mapped[str] = mapped_column(String, default="")
    artist: Mapped[str] = mapped_column(String, default="")  # track_id (safe for sort)

    source: Mapped[Source] = relationship(back_populates="items")


class Track(Base):
    """A logical track in the library. In-library only when a file exists in track_files."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist: Mapped[str] = mapped_column(String, default="")
    album: Mapped[str] = mapped_column(String, default="")
    year: Mapped[str] = mapped_column(String, default="")
    duration: Mapped[int] = mapped_column(Integer, default=0)  # seconds
    artwork: Mapped[str] = mapped_column(String, default="")
    title_id: Mapped[str] = mapped_column(String, unique=True, index=True)  # dedup key
    resolved_from: Mapped[str | None] = mapped_column(String, nullable=True)  # saavn|youtube
    state: Mapped[str] = mapped_column(String, default="pending")  # pending|resolving|downloading|done|failed|mismatch

    files: Mapped[list[TrackFile]] = relationship(
        back_populates="track", cascade="all, delete-orphan"
    )


class TrackFile(Base):
    """A concrete file belonging to a track."""

    __tablename__ = "track_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    source_qual: Mapped[str] = mapped_column(String, default="HQ")  # HQ|PL
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    track: Mapped[Track] = relationship(back_populates="files")


class Artist(Base):
    """A favorited artist (from search)."""

    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    external_id: Mapped[str] = mapped_column(String, default="")
    image: Mapped[str] = mapped_column(String, default="")