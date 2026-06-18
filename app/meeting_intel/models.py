"""SQLAlchemy ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MeetingStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), default="Untitled meeting")
    # Where the recording came from: upload | watch | jitsi | meet | voip
    source: Mapped[str] = mapped_column(String(32), default="upload")
    status: Mapped[str] = mapped_column(String(16), default=MeetingStatus.QUEUED.value, index=True)

    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Results.  Stored as JSON so it works on both Postgres and SQLite.
    # segments: [{"start": float, "end": float, "speaker": str|None, "text": str}]
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # summary: structured dict (see engine/summarize.py for the schema)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self, *, include_results: bool = True) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "error": self.error,
            "progress": self.progress,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_results:
            data["segments"] = self.segments
            data["transcript_text"] = self.transcript_text
            data["summary"] = self.summary
        return data
