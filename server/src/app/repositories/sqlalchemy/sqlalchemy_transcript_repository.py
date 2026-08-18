from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.meeting import MeetingEntity
from app.domain.transcript import TranscriptEntity
from app.repositories.interfaces.transcript_repository import TranscriptMatch, TranscriptRepository
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

    async def find_page_for_meeting(
        self, meeting_id: str, limit: int, offset: int
    ) -> list[TranscriptEntity]:
        stmt = (
            select(TranscriptEntity)
            .where(TranscriptEntity.meeting_id == meeting_id)
            .order_by(TranscriptEntity.sequence_number)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_meeting(self, meeting_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(TranscriptEntity)
            .where(TranscriptEntity.meeting_id == meeting_id)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def search_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, query: str, limit: int
    ) -> list[TranscriptMatch]:
        # The join to meetings enforces tenancy and supplies the title.
        stmt = (
            select(
                MeetingEntity.id,
                MeetingEntity.title,
                TranscriptEntity.transcript,
                TranscriptEntity.timestamp,
            )
            .join(TranscriptEntity, TranscriptEntity.meeting_id == MeetingEntity.id)
            .where(
                MeetingEntity.owner_user_id == owner_user_id,
                MeetingEntity.owner_tenant_id == owner_tenant_id,
                TranscriptEntity.transcript.ilike(f"%{query}%"),
            )
            .order_by(MeetingEntity.updated_at.desc(), TranscriptEntity.sequence_number)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            TranscriptMatch(
                meeting_id=row[0], meeting_title=row[1], transcript=row[2], timestamp=row[3]
            )
            for row in result.all()
        ]

    async def save_all(self, transcripts: list[TranscriptEntity]) -> None:
        for transcript in transcripts:
            await self._session.merge(transcript)
        await self._session.flush()

    async def delete_all_for_meeting(self, meeting_id: str) -> int:
        stmt = delete(TranscriptEntity).where(TranscriptEntity.meeting_id == meeting_id)
        return await execute_rowcount(self._session, stmt)
