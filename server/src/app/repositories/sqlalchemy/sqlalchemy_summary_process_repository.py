from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.summary_process import SummaryProcessEntity
from app.repositories.interfaces.summary_process_repository import SummaryProcessRepository
from app.repositories.sqlalchemy.execution import execute_rowcount


class SqlAlchemySummaryProcessRepository(SummaryProcessRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_for_meeting(self, meeting_id: str) -> SummaryProcessEntity | None:
        stmt = select(SummaryProcessEntity).where(SummaryProcessEntity.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, summary_process: SummaryProcessEntity) -> SummaryProcessEntity:
        merged = await self._session.merge(summary_process)
        await self._session.flush()
        return merged

    async def delete_for_meeting(self, meeting_id: str) -> bool:
        stmt = delete(SummaryProcessEntity).where(SummaryProcessEntity.meeting_id == meeting_id)
        return await execute_rowcount(self._session, stmt) > 0
