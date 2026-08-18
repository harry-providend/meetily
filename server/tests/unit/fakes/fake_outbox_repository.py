from datetime import datetime

from app.domain.outbox_entry import OutboxEntryEntity
from app.repositories.interfaces.outbox_repository import OutboxRepository


class FakeOutboxRepository(OutboxRepository):
    def __init__(self, seed: list[OutboxEntryEntity] | None = None) -> None:
        self.entries: list[OutboxEntryEntity] = list(seed or [])

    async def find_by_client_entry_id(
        self, owner_user_id: str, client_entry_id: str
    ) -> OutboxEntryEntity | None:
        return next(
            (
                e
                for e in self.entries
                if e.owner_user_id == owner_user_id and e.client_entry_id == client_entry_id
            ),
            None,
        )

    async def save(self, entry: OutboxEntryEntity) -> OutboxEntryEntity:
        self.entries.append(entry)
        return entry

    async def find_applied_since(
        self, owner_user_id: str, owner_tenant_id: str, since: datetime | None, limit: int
    ) -> list[OutboxEntryEntity]:
        matches = [
            e
            for e in self.entries
            if e.owner_user_id == owner_user_id
            and e.owner_tenant_id == owner_tenant_id
            and e.applied_at is not None
            and (since is None or e.server_received_at > since)
        ]
        matches.sort(key=lambda e: e.server_received_at)
        return matches[:limit]
