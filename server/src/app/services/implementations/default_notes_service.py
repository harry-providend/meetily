from datetime import UTC, datetime

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import NotFoundException
from app.domain.meeting_notes import MeetingNotesEntity
from app.repositories.interfaces.meeting_notes_repository import MeetingNotesRepository
from app.schemas.notes_dto import MeetingNotesResponse, MeetingNotesUpsertRequest
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.notes_service import NotesService


class DefaultNotesService(NotesService):
    def __init__(
        self,
        notes_repository: MeetingNotesRepository,
        ownership_guard: MeetingOwnershipGuard,
    ) -> None:
        self._notes_repository = notes_repository
        self._ownership_guard = ownership_guard

    async def get_notes(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> MeetingNotesResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity = await self._notes_repository.find_for_meeting(meeting_id)
        if entity is None:
            raise NotFoundException(f"no notes for meeting {meeting_id}")
        return MeetingNotesResponse.model_validate(entity)

    async def upsert_notes(
        self, current_user: AuthenticatedUser, meeting_id: str, request: MeetingNotesUpsertRequest
    ) -> MeetingNotesResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        existing = await self._notes_repository.find_for_meeting(meeting_id)
        now = datetime.now(UTC)
        entity = MeetingNotesEntity(
            meeting_id=meeting_id,
            notes_markdown=request.notes_markdown,
            notes_json=request.notes_json,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        saved = await self._notes_repository.save(entity)
        return MeetingNotesResponse.model_validate(saved)
