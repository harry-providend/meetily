from abc import ABC, abstractmethod

from app.domain.transcript_version import TranscriptVersionEntity


class TranscriptVersionRepository(ABC):
    @abstractmethod
    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptVersionEntity]: ...

    @abstractmethod
    async def find_version_for_meeting(
        self, meeting_id: str, version: int
    ) -> TranscriptVersionEntity | None: ...

    @abstractmethod
    async def next_version_for_meeting(self, meeting_id: str) -> int: ...

    @abstractmethod
    async def save(self, version: TranscriptVersionEntity) -> TranscriptVersionEntity: ...
