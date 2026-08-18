from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.summary_version import SummaryVersionEntity
from app.repositories.interfaces.summary_version_repository import SummaryVersionRepository


class SqlAlchemySummaryVersionRepository(SummaryVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all_for_meeting(self, meeting_id: str) -> list[SummaryVersionEntity]:
        stmt = (
            select(SummaryVersionEntity)
            .where(SummaryVersionEntity.meeting_id == meeting_id)
            .order_by(SummaryVersionEntity.version.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_version_for_meeting(
        self, meeting_id: str, version: int
    ) -> SummaryVersionEntity | None:
        stmt = select(SummaryVersionEntity).where(
            SummaryVersionEntity.meeting_id == meeting_id,
            SummaryVersionEntity.version == version,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def next_version_for_meeting(self, meeting_id: str) -> int:
        stmt = select(func.max(SummaryVersionEntity.version)).where(
            SummaryVersionEntity.meeting_id == meeting_id
        )
        result = await self._session.execute(stmt)
        current_max: int | None = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def save(self, version: SummaryVersionEntity) -> SummaryVersionEntity:
        merged = await self._session.merge(version)
        await self._session.flush()
        return merged
