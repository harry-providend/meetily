from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.meeting import MeetingEntity
from app.repositories.interfaces.meeting_repository import MeetingRepository
from app.repositories.sqlalchemy.execution import execute_rowcount


class SqlAlchemyMeetingRepository(MeetingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, limit: int, offset: int
    ) -> list[MeetingEntity]:
        stmt = (
            select(MeetingEntity)
            .where(
                MeetingEntity.owner_user_id == owner_user_id,
                MeetingEntity.owner_tenant_id == owner_tenant_id,
            )
            .order_by(MeetingEntity.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_owner(self, owner_user_id: str, owner_tenant_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(MeetingEntity)
            .where(
                MeetingEntity.owner_user_id == owner_user_id,
                MeetingEntity.owner_tenant_id == owner_tenant_id,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def find_by_id_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> MeetingEntity | None:
        stmt = select(MeetingEntity).where(
            MeetingEntity.id == meeting_id,
            MeetingEntity.owner_user_id == owner_user_id,
            MeetingEntity.owner_tenant_id == owner_tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, meeting: MeetingEntity) -> MeetingEntity:
        merged = await self._session.merge(meeting)
        await self._session.flush()
        return merged

    async def delete_for_owner(
        self, meeting_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> bool:
        stmt = delete(MeetingEntity).where(
            MeetingEntity.id == meeting_id,
            MeetingEntity.owner_user_id == owner_user_id,
            MeetingEntity.owner_tenant_id == owner_tenant_id,
        )
        return await execute_rowcount(self._session, stmt) > 0
