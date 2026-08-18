from abc import ABC, abstractmethod

from app.domain.transcript import TranscriptEntity


class TranscriptRepository(ABC):
    """Scoped by meeting, not owner: the service layer authorizes the parent meeting first, so
    ownership is already settled here. Duplicating owner columns onto children would drift."""

    @abstractmethod
    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptEntity]: ...

    @abstractmethod
    async def save_all(self, transcripts: list[TranscriptEntity]) -> None: ...

    @abstractmethod
    async def delete_all_for_meeting(self, meeting_id: str) -> int: ...
