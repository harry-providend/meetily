from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.meeting import MeetingEntity
from app.domain.transcript import TranscriptEntity
from app.repositories.sqlalchemy.sqlalchemy_meeting_repository import SqlAlchemyMeetingRepository
from app.repositories.sqlalchemy.sqlalchemy_transcript_repository import (
    SqlAlchemyTranscriptRepository,
)


def _meeting(meeting_id: str, user: str, tenant: str) -> MeetingEntity:
    now = datetime.now(UTC)
    return MeetingEntity(
        id=meeting_id,
        owner_user_id=user,
        owner_tenant_id=tenant,
        title=meeting_id,
        folder_path=None,
        created_at=now,
        updated_at=now,
    )


async def test_find_all_for_owner_excludes_other_users(session: AsyncSession) -> None:
    session.add_all([_meeting("m1", "u1", "t1"), _meeting("m2", "u2", "t1")])
    await session.commit()

    results = await SqlAlchemyMeetingRepository(session).find_all_for_owner("u1", "t1", 10, 0)

    assert [m.id for m in results] == ["m1"]


async def test_find_all_for_owner_excludes_other_tenants(session: AsyncSession) -> None:
    session.add_all([_meeting("m1", "u1", "t1"), _meeting("m2", "u1", "t2")])
    await session.commit()

    results = await SqlAlchemyMeetingRepository(session).find_all_for_owner("u1", "t1", 10, 0)

    assert [m.id for m in results] == ["m1"]


async def test_delete_for_owner_refuses_another_users_meeting(session: AsyncSession) -> None:
    session.add(_meeting("m1", "u2", "t1"))
    await session.commit()
    repository = SqlAlchemyMeetingRepository(session)

    assert await repository.delete_for_owner("m1", "u1", "t1") is False
    assert await repository.find_by_id_for_owner("m1", "u2", "t1") is not None


async def test_deleting_a_meeting_cascades_to_transcripts(session: AsyncSession) -> None:
    session.add(_meeting("m1", "u1", "t1"))
    await session.commit()
    await SqlAlchemyTranscriptRepository(session).save_all(
        [
            TranscriptEntity(id="s1", meeting_id="m1", transcript="hello", timestamp="00:00:00"),
            TranscriptEntity(id="s2", meeting_id="m1", transcript="world", timestamp="00:00:05"),
        ]
    )
    await session.commit()

    assert await SqlAlchemyMeetingRepository(session).delete_for_owner("m1", "u1", "t1") is True
    await session.commit()

    remaining = await session.execute(select(TranscriptEntity))
    assert list(remaining.scalars().all()) == []


async def test_transcript_sequence_number_preserves_insertion_order(
    session: AsyncSession,
) -> None:
    # Segments must return in write order even with audio_start_time null.
    session.add(_meeting("m1", "u1", "t1"))
    await session.commit()
    repository = SqlAlchemyTranscriptRepository(session)
    await repository.save_all(
        [
            TranscriptEntity(id=f"s{i}", meeting_id="m1", transcript=f"line {i}", timestamp="0")
            for i in range(5)
        ]
    )
    await session.commit()

    segments = await repository.find_all_for_meeting("m1")

    assert [s.id for s in segments] == ["s0", "s1", "s2", "s3", "s4"]
    assert [s.sequence_number for s in segments] == sorted(s.sequence_number for s in segments)
