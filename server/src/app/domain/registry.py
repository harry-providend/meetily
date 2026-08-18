"""Imports every entity so Base.metadata is complete. Alembic autogenerate and create_all()
both read it, and an unimported entity module is silently omitted from migrations."""

from app.db.base import Base
from app.domain.meeting import MeetingEntity
from app.domain.summary_process import SummaryProcessEntity
from app.domain.summary_template import SummaryTemplateEntity
from app.domain.summary_version import SummaryVersionEntity
from app.domain.transcript import TranscriptEntity
from app.domain.transcript_version import TranscriptVersionEntity

__all__ = [
    "Base",
    "MeetingEntity",
    "SummaryProcessEntity",
    "SummaryTemplateEntity",
    "SummaryVersionEntity",
    "TranscriptEntity",
    "TranscriptVersionEntity",
]
