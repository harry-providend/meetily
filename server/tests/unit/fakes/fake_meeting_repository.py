from app.domain.meeting import MeetingEntity
from app.repositories.interfaces.meeting_repository import MeetingRepository


class FakeMeetingRepository(MeetingRepository):
    """In-memory MeetingRepository, so services are testable with no database."""

    def __init__(self, seed: list[MeetingEntity] | None = None) -> None:
        self.meetings: list[MeetingEntity] = list(seed or [])

    async def find_all_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, limit: int, offset: int
    ) -> list[MeetingEntity]:
        return self._owned(owner_user_id, owner_tenant_id)[offset : offset + limit]

    async def count_for_owner(self, owner_user_id: str, owner_tenant_id: str) -> int:
        return len(self._owned(owner_user_id, owner_tenant_id))

    async def find_by_id_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> MeetingEntity | None:
        return next(
            (m for m in self._owned(owner_user_id, owner_tenant_id) if m.id == meeting_id),
            None,
        )

    async def save(self, meeting: MeetingEntity) -> MeetingEntity:
        self.meetings = [m for m in self.meetings if m.id != meeting.id]
        self.meetings.append(meeting)
        return meeting

    async def delete_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> bool:
        target = await self.find_by_id_for_owner(meeting_id, owner_user_id, owner_tenant_id)
        if target is None:
            return False
        self.meetings.remove(target)
        return True

    def _owned(self, owner_user_id: str, owner_tenant_id: str) -> list[MeetingEntity]:
        return [
            m
            for m in self.meetings
            if m.owner_user_id == owner_user_id and m.owner_tenant_id == owner_tenant_id
        ]
