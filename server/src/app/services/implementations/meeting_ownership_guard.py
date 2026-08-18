from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import NotFoundException
from app.domain.meeting import MeetingEntity
from app.repositories.interfaces.meeting_repository import MeetingRepository


class MeetingOwnershipGuard:
    """Resolves a meeting the caller owns, or raises. Composed into every child service."""

    def __init__(self, meeting_repository: MeetingRepository) -> None:
        self._meeting_repository = meeting_repository

    async def require_owned_meeting(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> MeetingEntity:
        entity = await self._meeting_repository.find_by_id_for_owner(
            meeting_id=meeting_id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )
        if entity is None:
            # Identical to truly-absent: "exists, but not yours" confirms another user's id.
            raise NotFoundException(f"meeting {meeting_id} not found")
        return entity
