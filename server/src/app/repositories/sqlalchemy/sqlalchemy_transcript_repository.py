from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.transcript import TranscriptEntity
from app.repositories.interfaces.transcript_repository import TranscriptRepository
from app.repositories.sqlalchemy.execution import execute_rowcount


class SqlAlchemyTranscriptRepository(TranscriptRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptEntity]:
        # sequence_number, not rowid -- see TranscriptEntity.
        stmt = (
            select(TranscriptEntity)
            .where(TranscriptEntity.meeting_id == meeting_id)
            .order_by(TranscriptEntity.sequence_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def save_all(self, transcripts: list[TranscriptEntity]) -> None:
        for transcript in transcripts:
            await self._session.merge(transcript)
        await self._session.flush()

    async def delete_all_for_meeting(self, meeting_id: str) -> int:
        stmt = delete(TranscriptEntity).where(TranscriptEntity.meeting_id == meeting_id)
        return await execute_rowcount(self._session, stmt)
