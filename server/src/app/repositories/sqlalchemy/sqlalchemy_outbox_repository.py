from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.outbox_entry import OutboxEntryEntity
from app.repositories.interfaces.outbox_repository import OutboxRepository


class SqlAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_client_entry_id(
        self, owner_user_id: str, client_entry_id: str
    ) -> OutboxEntryEntity | None:
        stmt = select(OutboxEntryEntity).where(
            OutboxEntryEntity.owner_user_id == owner_user_id,
            OutboxEntryEntity.client_entry_id == client_entry_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, entry: OutboxEntryEntity) -> OutboxEntryEntity:
        merged = await self._session.merge(entry)
        await self._session.flush()
        return merged

    async def find_applied_since(
        self, owner_user_id: str, owner_tenant_id: str, since: datetime | None, limit: int
    ) -> list[OutboxEntryEntity]:
        stmt = select(OutboxEntryEntity).where(
            OutboxEntryEntity.owner_user_id == owner_user_id,
            OutboxEntryEntity.owner_tenant_id == owner_tenant_id,
            OutboxEntryEntity.applied_at.is_not(None),
        )
        if since is not None:
            stmt = stmt.where(OutboxEntryEntity.server_received_at > since)
        stmt = stmt.order_by(OutboxEntryEntity.server_received_at).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
