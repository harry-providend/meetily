from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.transcript_chunk import TranscriptChunkEntity
from app.repositories.interfaces.transcript_chunk_repository import TranscriptChunkRepository


class SqlAlchemyTranscriptChunkRepository(TranscriptChunkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_for_meeting(self, meeting_id: str) -> TranscriptChunkEntity | None:
        stmt = select(TranscriptChunkEntity).where(TranscriptChunkEntity.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, chunk: TranscriptChunkEntity) -> TranscriptChunkEntity:
        merged = await self._session.merge(chunk)
        await self._session.flush()
        return merged
