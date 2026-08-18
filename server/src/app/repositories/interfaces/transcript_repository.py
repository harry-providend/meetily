from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.transcript import TranscriptEntity


@dataclass(frozen=True)
class TranscriptMatch:
    """A search hit joined to its meeting. A projection, not an entity."""

    meeting_id: str
    meeting_title: str
    transcript: str
    timestamp: str


class TranscriptRepository(ABC):
    """Scoped by meeting, not owner: the service authorizes the parent meeting first."""

    @abstractmethod
    async def find_all_for_meeting(self, meeting_id: str) -> list[TranscriptEntity]: ...

    @abstractmethod
    async def find_page_for_meeting(
        self, meeting_id: str, limit: int, offset: int
    ) -> list[TranscriptEntity]: ...

    @abstractmethod
    async def count_for_meeting(self, meeting_id: str) -> int: ...

    @abstractmethod
    async def search_for_owner(
        self, owner_user_id: str, owner_tenant_id: str, query: str, limit: int
    ) -> list[TranscriptMatch]:
        """Takes an owner because search spans every meeting, so there is no parent to authorize."""

    @abstractmethod
    async def save_all(self, transcripts: list[TranscriptEntity]) -> None: ...

    @abstractmethod
    async def delete_all_for_meeting(self, meeting_id: str) -> int: ...
