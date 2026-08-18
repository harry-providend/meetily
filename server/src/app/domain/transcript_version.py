from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TranscriptVersionEntity(Base):
    """Surrogate BIGSERIAL PK replaces SQLite's derived-string id ("tsver-{meeting_id}-{version}"),
    which was redundant with the real uniqueness constraint below."""

    __tablename__ = "transcript_versions"
    __table_args__ = (
        UniqueConstraint("meeting_id", "version", name="uq_transcript_versions_meeting_version"),
        Index("ix_transcript_versions_meeting_version", "meeting_id", "version"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    segments_json: Mapped[list[JsonValue]] = mapped_column(JSONB, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
