from datetime import UTC, datetime

import pytest

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import NotFoundException
from app.domain.meeting import MeetingEntity
from app.schemas.meeting_dto import MeetingCreateRequest, MeetingUpdateRequest
from app.services.implementations.default_meeting_service import DefaultMeetingService
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from tests.unit.fakes.fake_meeting_repository import FakeMeetingRepository

USER_A = AuthenticatedUser(oid="user-a", tenant_id="tenant-1", display_name="A", upn="a@x.test")
USER_B = AuthenticatedUser(oid="user-b", tenant_id="tenant-1", display_name="B", upn="b@x.test")
OTHER_TENANT = AuthenticatedUser(
    oid="user-a", tenant_id="tenant-2", display_name="A", upn="a@y.test"
)


def _meeting(meeting_id: str, owner: AuthenticatedUser, title: str = "m") -> MeetingEntity:
    now = datetime.now(UTC)
    return MeetingEntity(
        id=meeting_id,
        owner_user_id=owner.oid,
        owner_tenant_id=owner.tenant_id,
        title=title,
        folder_path=None,
        created_at=now,
        updated_at=now,
    )


def _service(seed: list[MeetingEntity]) -> tuple[DefaultMeetingService, FakeMeetingRepository]:
    repository = FakeMeetingRepository(seed)
    return DefaultMeetingService(repository, MeetingOwnershipGuard(repository)), repository


async def test_list_meetings_returns_only_the_callers_meetings() -> None:
    service, _ = _service([_meeting("m1", USER_A), _meeting("m2", USER_B)])

    result = await service.list_meetings(USER_A, page=1, page_size=10)

    assert [m.id for m in result.items] == ["m1"]
    assert result.total == 1


async def test_list_meetings_isolates_tenants_even_for_the_same_oid() -> None:
    # Same oid in two tenants must not see across the boundary -- oid alone is not the key.
    service, _ = _service([_meeting("m1", USER_A), _meeting("m2", OTHER_TENANT)])

    result = await service.list_meetings(USER_A, page=1, page_size=10)

    assert [m.id for m in result.items] == ["m1"]


async def test_list_meetings_paginates() -> None:
    service, _ = _service([_meeting(f"m{i}", USER_A) for i in range(5)])

    page_two = await service.list_meetings(USER_A, page=2, page_size=2)

    assert [m.id for m in page_two.items] == ["m2", "m3"]
    assert page_two.total == 5


async def test_get_meeting_owned_by_another_user_is_reported_as_not_found() -> None:
    # Not Forbidden: a distinguishable error would confirm the id exists for someone else.
    service, _ = _service([_meeting("m1", USER_B)])

    with pytest.raises(NotFoundException):
        await service.get_meeting(USER_A, "m1")


async def test_create_meeting_stamps_the_caller_as_owner() -> None:
    service, repository = _service([])

    created = await service.create_meeting(
        USER_A, MeetingCreateRequest(id="m1", title="Standup", folder_path=None)
    )

    assert created.id == "m1"
    assert repository.meetings[0].owner_user_id == USER_A.oid
    assert repository.meetings[0].owner_tenant_id == USER_A.tenant_id


async def test_update_meeting_rejects_another_users_meeting() -> None:
    service, repository = _service([_meeting("m1", USER_B, title="original")])

    with pytest.raises(NotFoundException):
        await service.update_meeting(USER_A, "m1", MeetingUpdateRequest(title="hijacked"))

    assert repository.meetings[0].title == "original"


async def test_delete_meeting_rejects_another_users_meeting() -> None:
    service, repository = _service([_meeting("m1", USER_B)])

    with pytest.raises(NotFoundException):
        await service.delete_meeting(USER_A, "m1")

    assert len(repository.meetings) == 1


async def test_delete_meeting_removes_own_meeting() -> None:
    service, repository = _service([_meeting("m1", USER_A)])

    await service.delete_meeting(USER_A, "m1")

    assert repository.meetings == []
