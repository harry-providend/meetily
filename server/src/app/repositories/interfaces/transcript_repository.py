from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.transcript import TranscriptEntity


@dataclass(frozen=True)
class TranscriptMatch:
    """A search hit joined to its meeting. A projection, not an entity: search spans meetings, so
    there is no single parent to read the title from."""

    meeting_id: str
    meeting_title: str
    transcript: str
    timestamp: str


class TranscriptRepository(ABC):
    """Scoped by meeting, not owner: the service layer authorizes the parent meeting first, so
    ownership is already settled here. Duplicating owner columns onto children would drift."""

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
        """The one method here that takes an owner: search spans every meeting, so there is no
        parent for the guard to authorize first."""

    @abstractmethod
    async def save_all(self, transcripts: list[TranscriptEntity]) -> None: ...

    @abstractmethod
    async def delete_all_for_meeting(self, meeting_id: str) -> int: ...
