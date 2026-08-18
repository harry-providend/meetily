from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MeetingNotesEntity(Base):
    __tablename__ = "meeting_notes"

    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    notes_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_json: Mapped[dict[str, JsonValue] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
