from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SummaryTemplateEntity(Base):
    """Not meeting-scoped. owner_tenant_id is nullable: NULL means a global/builtin template,
    a value means a tenant authored it -- so per-tenant templates need no schema change later."""

    __tablename__ = "summary_templates"
    __table_args__ = (Index("ix_summary_templates_updated_at", "updated_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_tenant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sections_json: Mapped[dict[str, JsonValue] | list[JsonValue]] = mapped_column(
        JSONB, nullable=False
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_modified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
