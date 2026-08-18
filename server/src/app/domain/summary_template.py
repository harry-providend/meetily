from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SummaryTemplateEntity(Base):
    """Not meeting-scoped, but owned: each user gets their own copies, which is what the desktop
    app's device-local table amounted to. Sharing a template across a tenant later means widening
    the read filter, not changing this shape.

    is_builtin marks a template shipped with the app; user_modified marks one the user has edited.
    Together they drive seeding: startup re-applies shipped content to builtins, but never over an
    edit, and clearing user_modified is what "reset to the shipped version" means.
    """

    __tablename__ = "summary_templates"
    __table_args__ = (Index("ix_summary_templates_updated_at", "updated_at"),)

    # Owner first, so "every template for this owner" is a prefix scan of the primary key.
    owner_tenant_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sections_json: Mapped[dict[str, JsonValue] | list[JsonValue]] = mapped_column(
        JSONB, nullable=False
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_modified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
