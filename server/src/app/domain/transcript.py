from sqlalchemy import BigInteger, Float, ForeignKey, Identity, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TranscriptEntity(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_meeting_id", "meeting_id"),
        Index("ix_transcripts_meeting_sequence", "meeting_id", "sequence_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    # Replaces SQLite's implicit rowid, which version.rs orders by; Postgres has no stable
    # equivalent. Only meaningful within a meeting. Identity because autoincrement is honoured
    # on primary keys only, BY DEFAULT so the backfill can insert explicit values.
    sequence_number: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    # Opaque on purpose: mixed elapsed-time ("00:00:00") and wall-clock values, so casting
    # to a timestamp type would be lossy.
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaker: Mapped[str | None] = mapped_column(String, nullable=True)
