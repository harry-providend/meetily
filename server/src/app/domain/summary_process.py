from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SummaryProcessEntity(Base):
    """1:1 with a meeting -- the PK *is* the meeting id.

    result_backup is not history (summary_versions is): it is the rollback slot for one
    in-flight regeneration. Starting a run copies result into it, a failed or cancelled run
    restores from it, and only a successful run turns it into a numbered version. Dropping it
    would make a failed regeneration destroy the summary it was replacing.
    """

    __tablename__ = "summary_processes"

    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_backup: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_backup_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    process_metadata: Mapped[dict[str, JsonValue] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
