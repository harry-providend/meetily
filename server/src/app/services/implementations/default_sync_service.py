from datetime import UTC, datetime

from app.auth.current_user import AuthenticatedUser
from app.domain.meeting import MeetingEntity
from app.domain.outbox_entry import OutboxEntryEntity
from app.repositories.interfaces.meeting_repository import MeetingRepository
from app.repositories.interfaces.outbox_repository import OutboxRepository
from app.schemas.sync_dto import (
    AggregateType,
    SyncItemStatus,
    SyncOperation,
    SyncPullItem,
    SyncPullResponse,
    SyncPushItem,
    SyncPushItemResult,
    SyncPushRequest,
    SyncPushResponse,
)
from app.services.interfaces.sync_service import SyncService


class DefaultSyncService(SyncService):
    """Single-writer, last-writer-wins per meeting: one author per meeting, so the later
    client_updated_at wins outright. Meeting-level aggregates only."""

    def __init__(
        self,
        outbox_repository: OutboxRepository,
        meeting_repository: MeetingRepository,
    ) -> None:
        self._outbox_repository = outbox_repository
        self._meeting_repository = meeting_repository

    async def push(
        self, current_user: AuthenticatedUser, request: SyncPushRequest
    ) -> SyncPushResponse:
        results: list[SyncPushItemResult] = []
        for item in request.items:
            status = await self._apply_one(current_user, item)
            results.append(SyncPushItemResult(client_entry_id=item.client_entry_id, status=status))
        return SyncPushResponse(results=results)

    async def pull(
        self, current_user: AuthenticatedUser, since: datetime | None, limit: int
    ) -> SyncPullResponse:
        entries = await self._outbox_repository.find_applied_since(
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
            since=since,
            limit=limit,
        )
        items = [
            SyncPullItem(
                aggregate_type=entry.aggregate_type,
                aggregate_id=entry.aggregate_id,
                operation=entry.operation,
                payload=entry.payload_json,
                server_received_at=entry.server_received_at,
            )
            for entry in entries
        ]
        return SyncPullResponse(
            items=items,
            next_cursor=entries[-1].server_received_at if entries else since,
        )

    async def _apply_one(
        self, current_user: AuthenticatedUser, item: SyncPushItem
    ) -> SyncItemStatus:
        already = await self._outbox_repository.find_by_client_entry_id(
            current_user.oid, item.client_entry_id
        )
        if already is not None:
            # A retry after a dropped connection. The unique constraint on
            # (owner_user_id, client_entry_id) is what makes this safe to detect here.
            return SyncItemStatus.DUPLICATE

        applied = await self._apply_to_aggregate(current_user, item)

        # Server clock, not the client's: pull cursors need it monotonic. Set here, not by
        # column default, so the returned instance carries it without a refresh.
        received_at = datetime.now(UTC)

        await self._outbox_repository.save(
            OutboxEntryEntity(
                server_received_at=received_at,
                client_entry_id=item.client_entry_id,
                owner_user_id=current_user.oid,
                owner_tenant_id=current_user.tenant_id,
                aggregate_type=str(item.aggregate_type),
                aggregate_id=item.aggregate_id,
                operation=str(item.operation),
                payload_json=item.payload,
                client_updated_at=item.client_updated_at,
                # Stale pushes are still recorded, with applied_at left NULL -- an audit trail
                # of what the client tried, without it showing up in anyone's pull feed.
                applied_at=received_at if applied else None,
            )
        )
        return SyncItemStatus.APPLIED if applied else SyncItemStatus.SKIPPED_STALE

    async def _apply_to_aggregate(
        self, current_user: AuthenticatedUser, item: SyncPushItem
    ) -> bool:
        if item.aggregate_type is not AggregateType.MEETING:
            # Child aggregates have dedicated endpoints; the outbox only carries the meeting
            # itself for now. Recording without applying keeps the client's retry loop honest.
            return False

        existing = await self._meeting_repository.find_by_id_for_owner(
            meeting_id=item.aggregate_id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )

        if item.operation is SyncOperation.DELETE:
            if existing is None:
                return False
            return await self._meeting_repository.delete_for_owner(
                meeting_id=item.aggregate_id,
                owner_user_id=current_user.oid,
                owner_tenant_id=current_user.tenant_id,
            )

        if existing is not None and existing.updated_at >= item.client_updated_at:
            return False

        title = item.payload.get("title")
        folder_path = item.payload.get("folder_path")
        await self._meeting_repository.save(
            MeetingEntity(
                id=item.aggregate_id,
                owner_user_id=current_user.oid,
                owner_tenant_id=current_user.tenant_id,
                title=title if isinstance(title, str) else "",
                folder_path=folder_path if isinstance(folder_path, str) else None,
                updated_at=item.client_updated_at,
            )
        )
        return True
