from abc import ABC, abstractmethod

from app.domain.transcript_chunk import TranscriptChunkEntity


class TranscriptChunkRepository(ABC):
    @abstractmethod
    async def find_for_meeting(self, meeting_id: str) -> TranscriptChunkEntity | None: ...

    @abstractmethod
    async def save(self, chunk: TranscriptChunkEntity) -> TranscriptChunkEntity: ...
