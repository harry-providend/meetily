from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.meeting_notes import MeetingNotesEntity
from app.repositories.interfaces.meeting_notes_repository import MeetingNotesRepository
from app.repositories.sqlalchemy.execution import execute_rowcount


class SqlAlchemyMeetingNotesRepository(MeetingNotesRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_for_meeting(self, meeting_id: str) -> MeetingNotesEntity | None:
        stmt = select(MeetingNotesEntity).where(MeetingNotesEntity.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, notes: MeetingNotesEntity) -> MeetingNotesEntity:
        merged = await self._session.merge(notes)
        await self._session.flush()
        return merged

    async def delete_for_meeting(self, meeting_id: str) -> bool:
        stmt = delete(MeetingNotesEntity).where(MeetingNotesEntity.meeting_id == meeting_id)
        return await execute_rowcount(self._session, stmt) > 0
