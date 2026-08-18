from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.notes_dto import MeetingNotesResponse, MeetingNotesUpsertRequest


class NotesService(ABC):
    @abstractmethod
    async def get_notes(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> MeetingNotesResponse: ...

    @abstractmethod
    async def upsert_notes(
        self, current_user: AuthenticatedUser, meeting_id: str, request: MeetingNotesUpsertRequest
    ) -> MeetingNotesResponse: ...
