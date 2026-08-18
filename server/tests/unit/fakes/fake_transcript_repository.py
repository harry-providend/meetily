from app.domain.transcript import TranscriptEntity
from app.repositories.interfaces.transcript_repository import TranscriptMatch, TranscriptRepository


class FakeTranscriptRepository(TranscriptRepository):
    """In-memory TranscriptRepository. Insertion order stands in for sequence_number."""

    def __init__(self, seed: list[TranscriptEntity] | None = None) -> None:
        self.transcripts: list[TranscriptEntity] = list(seed or [])
        self.meeting_titles: dict[str, str] = {}
        self.meeting_owners: dict[str, tuple[str, str]] = {}

    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptEntity]:
        return [t for t in self.transcripts if t.meeting_id == meeting_id]

    async def find_page_for_meeting(
        self, meeting_id: str, limit: int, offset: int
    ) -> list[TranscriptEntity]:
        segments = await self.find_all_for_meeting(meeting_id)
        return segments[offset : offset + limit]

    async def count_for_meeting(self, meeting_id: str) -> int:
        return len(await self.find_all_for_meeting(meeting_id))

    async def search_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, query: str, limit: int
    ) -> list[TranscriptMatch]:
        needle = query.lower()
        hits = [
            TranscriptMatch(
                meeting_id=t.meeting_id,
                meeting_title=self.meeting_titles.get(t.meeting_id, ""),
                transcript=t.transcript,
                timestamp=t.timestamp,
            )
            for t in self.transcripts
            if needle in t.transcript.lower()
            and self.meeting_owners.get(t.meeting_id) == (owner_user_id, owner_tenant_id)
        ]
        return hits[:limit]

    async def save_all(self, transcripts: list[TranscriptEntity]) -> None:
        for transcript in transcripts:
            self.transcripts = [
                t
                for t in self.transcripts
                if not (t.id == transcript.id and t.meeting_id == transcript.meeting_id)
            ]
            self.transcripts.append(transcript)

    async def delete_all_for_meeting(self, meeting_id: str) -> int:
        before = len(self.transcripts)
        self.transcripts = [t for t in self.transcripts if t.meeting_id != meeting_id]
        return before - len(self.transcripts)
