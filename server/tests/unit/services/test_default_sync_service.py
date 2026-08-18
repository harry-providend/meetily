from datetime import UTC, datetime, timedelta

from app.auth.current_user import AuthenticatedUser
from app.domain.meeting import MeetingEntity
from app.schemas.sync_dto import (
    AggregateType,
    SyncItemStatus,
    SyncOperation,
    SyncPushItem,
    SyncPushRequest,
)
from app.services.implementations.default_sync_service import DefaultSyncService
from tests.unit.fakes.fake_meeting_repository import FakeMeetingRepository
from tests.unit.fakes.fake_outbox_repository import FakeOutboxRepository

USER = AuthenticatedUser(oid="user-a", tenant_id="tenant-1", display_name="A", upn="a@x.test")
NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def _existing_meeting(updated_at: datetime) -> MeetingEntity:
    return MeetingEntity(
        id="m1",
        owner_user_id=USER.oid,
        owner_tenant_id=USER.tenant_id,
        title="server version",
        folder_path=None,
        created_at=updated_at,
        updated_at=updated_at,
    )


def _push(
    client_updated_at: datetime, entry_id: str = "e1", title: str = "client version"
) -> SyncPushRequest:
    return SyncPushRequest(
        items=[
            SyncPushItem(
                client_entry_id=entry_id,
                aggregate_type=AggregateType.MEETING,
                aggregate_id="m1",
                operation=SyncOperation.UPSERT,
                payload={"title": title},
                client_updated_at=client_updated_at,
            )
        ]
    )


def _service(
    seed: list[MeetingEntity],
) -> tuple[DefaultSyncService, FakeMeetingRepository, FakeOutboxRepository]:
    meetings = FakeMeetingRepository(seed)
    outbox = FakeOutboxRepository()
    return DefaultSyncService(outbox, meetings), meetings, outbox


async def test_newer_client_change_wins() -> None:
    service, meetings, _ = _service([_existing_meeting(NOW - timedelta(minutes=5))])

    response = await service.push(USER, _push(NOW))

    assert response.results[0].status is SyncItemStatus.APPLIED
    assert meetings.meetings[0].title == "client version"


async def test_older_client_change_is_rejected_as_stale() -> None:
    service, meetings, outbox = _service([_existing_meeting(NOW)])

    response = await service.push(USER, _push(NOW - timedelta(minutes=5)))

    assert response.results[0].status is SyncItemStatus.SKIPPED_STALE
    assert meetings.meetings[0].title == "server version"
    # Still recorded for audit, but with applied_at unset so it never shows up in a pull.
    assert outbox.entries[0].applied_at is None


async def test_replaying_the_same_client_entry_id_is_a_duplicate() -> None:
    service, meetings, outbox = _service([_existing_meeting(NOW - timedelta(minutes=5))])

    first = await service.push(USER, _push(NOW))
    second = await service.push(USER, _push(NOW, title="second attempt"))

    assert first.results[0].status is SyncItemStatus.APPLIED
    assert second.results[0].status is SyncItemStatus.DUPLICATE
    assert meetings.meetings[0].title == "client version"
    assert len(outbox.entries) == 1


async def test_upsert_creates_a_meeting_that_does_not_exist_yet() -> None:
    service, meetings, _ = _service([])

    response = await service.push(USER, _push(NOW))

    assert response.results[0].status is SyncItemStatus.APPLIED
    assert meetings.meetings[0].id == "m1"
    assert meetings.meetings[0].owner_user_id == USER.oid


async def test_delete_of_an_absent_meeting_is_not_applied() -> None:
    service, _, outbox = _service([])
    request = SyncPushRequest(
        items=[
            SyncPushItem(
                client_entry_id="e1",
                aggregate_type=AggregateType.MEETING,
                aggregate_id="missing",
                operation=SyncOperation.DELETE,
                payload={},
                client_updated_at=NOW,
            )
        ]
    )

    response = await service.push(USER, request)

    assert response.results[0].status is SyncItemStatus.SKIPPED_STALE
    assert outbox.entries[0].applied_at is None


async def test_pull_returns_only_applied_entries_for_the_caller() -> None:
    service, _, _ = _service([_existing_meeting(NOW - timedelta(minutes=5))])
    await service.push(USER, _push(NOW))
    await service.push(USER, _push(NOW - timedelta(days=1), entry_id="stale-entry"))

    result = await service.pull(USER, since=None, limit=100)

    assert len(result.items) == 1
    assert result.items[0].aggregate_id == "m1"
    assert result.next_cursor is not None
