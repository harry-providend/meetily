from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.outbox_entry import OutboxEntryEntity


class OutboxRepository(ABC):
    @abstractmethod
    async def find_by_client_entry_id(
        self, owner_user_id: str, client_entry_id: str
    ) -> OutboxEntryEntity | None: ...

    @abstractmethod
    async def save(self, entry: OutboxEntryEntity) -> OutboxEntryEntity: ...

    @abstractmethod
    async def find_applied_since(
        self, owner_user_id: str, owner_tenant_id: str, since: datetime | None, limit: int
    ) -> list[OutboxEntryEntity]: ...
