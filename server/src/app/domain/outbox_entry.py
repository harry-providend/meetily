from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OutboxEntryEntity(Base):
    """A change the desktop app pushed up. (owner_user_id, client_entry_id) uniqueness makes a
    retried push an idempotent no-op rather than a duplicate apply."""

    __tablename__ = "outbox_entries"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "client_entry_id", name="uq_outbox_owner_client_entry"),
        Index("ix_outbox_owner_received", "owner_tenant_id", "owner_user_id", "server_received_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_entry_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, nullable=False)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
