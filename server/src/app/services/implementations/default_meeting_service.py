from datetime import UTC, datetime

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import NotFoundException
from app.domain.meeting import MeetingEntity
from app.repositories.interfaces.meeting_repository import MeetingRepository
from app.schemas.meeting_dto import (
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdateRequest,
)
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.meeting_service import MeetingService


class DefaultMeetingService(MeetingService):
    def __init__(
        self, meeting_repository: MeetingRepository, ownership_guard: MeetingOwnershipGuard
    ) -> None:
        self._meeting_repository = meeting_repository
        self._ownership_guard = ownership_guard

    async def list_meetings(
        self, current_user: AuthenticatedUser, page: int, page_size: int
    ) -> MeetingListResponse:
        offset = (page - 1) * page_size
        entities = await self._meeting_repository.find_all_for_owner(
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
            limit=page_size,
            offset=offset,
        )
        total = await self._meeting_repository.count_for_owner(
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )
        return MeetingListResponse(
            items=[MeetingResponse.model_validate(entity) for entity in entities],
            total=total,
        )

    async def get_meeting(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> MeetingResponse:
        entity = await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        return MeetingResponse.model_validate(entity)

    async def create_meeting(
        self, current_user: AuthenticatedUser, request: MeetingCreateRequest
    ) -> MeetingResponse:
        # Set here, not by server_default: a flushed-but-unrefreshed instance still carries
        # None, and the response is built from it.
        now = datetime.now(UTC)
        entity = MeetingEntity(
            id=request.id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
            title=request.title,
            folder_path=request.folder_path,
            created_at=now,
            updated_at=now,
        )
        saved = await self._meeting_repository.save(entity)
        return MeetingResponse.model_validate(saved)

    async def update_meeting(
        self, current_user: AuthenticatedUser, meeting_id: str, request: MeetingUpdateRequest
    ) -> MeetingResponse:
        entity = await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity.title = request.title
        entity.updated_at = datetime.now(UTC)
        saved = await self._meeting_repository.save(entity)
        return MeetingResponse.model_validate(saved)

    async def delete_meeting(self, current_user: AuthenticatedUser, meeting_id: str) -> None:
        deleted = await self._meeting_repository.delete_for_owner(
            meeting_id=meeting_id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )
        if not deleted:
            raise NotFoundException(f"meeting {meeting_id} not found")
