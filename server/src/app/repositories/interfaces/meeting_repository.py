from abc import ABC, abstractmethod

from app.domain.meeting import MeetingEntity


class MeetingRepository(ABC):
    """Owner is a required parameter on every method: there is deliberately no unfiltered
    variant, so adding one would be a visible diff rather than a forgotten WHERE clause."""

    @abstractmethod
    async def find_all_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, limit: int, offset: int
    ) -> list[MeetingEntity]: ...

    @abstractmethod
    async def count_for_owner(self, owner_user_id: str, owner_tenant_id: str) -> int: ...

    @abstractmethod
    async def find_by_id_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> MeetingEntity | None: ...

    @abstractmethod
    async def save(self, meeting: MeetingEntity) -> MeetingEntity: ...

    @abstractmethod
    async def delete_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> bool: ...
