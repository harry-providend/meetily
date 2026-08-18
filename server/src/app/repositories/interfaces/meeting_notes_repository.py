from abc import ABC, abstractmethod

from app.domain.meeting_notes import MeetingNotesEntity


class MeetingNotesRepository(ABC):
    @abstractmethod
    async def find_for_meeting(self, meeting_id: str) -> MeetingNotesEntity | None: ...

    @abstractmethod
    async def save(self, notes: MeetingNotesEntity) -> MeetingNotesEntity: ...

    @abstractmethod
    async def delete_for_meeting(self, meeting_id: str) -> bool: ...
