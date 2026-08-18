from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.transcript_version import TranscriptVersionEntity
from app.repositories.interfaces.transcript_version_repository import TranscriptVersionRepository


class SqlAlchemyTranscriptVersionRepository(TranscriptVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptVersionEntity]:
        stmt = (
            select(TranscriptVersionEntity)
            .where(TranscriptVersionEntity.meeting_id == meeting_id)
            .order_by(TranscriptVersionEntity.version.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_version_for_meeting(
        self, meeting_id: str, version: int
    ) -> TranscriptVersionEntity | None:
        stmt = select(TranscriptVersionEntity).where(
            TranscriptVersionEntity.meeting_id == meeting_id,
            TranscriptVersionEntity.version == version,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def next_version_for_meeting(self, meeting_id: str) -> int:
        stmt = select(func.max(TranscriptVersionEntity.version)).where(
            TranscriptVersionEntity.meeting_id == meeting_id
        )
        result = await self._session.execute(stmt)
        current_max: int | None = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def save(self, version: TranscriptVersionEntity) -> TranscriptVersionEntity:
        merged = await self._session.merge(version)
        await self._session.flush()
        return merged
