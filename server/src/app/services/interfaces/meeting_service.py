from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.meeting_dto import (
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdateRequest,
)


class MeetingService(ABC):
    @abstractmethod
    async def list_meetings(
        self, current_user: AuthenticatedUser, page: int, page_size: int
    ) -> MeetingListResponse: ...

    @abstractmethod
    async def get_meeting(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> MeetingResponse: ...

    @abstractmethod
    async def create_meeting(
        self, current_user: AuthenticatedUser, request: MeetingCreateRequest
    ) -> MeetingResponse: ...

    @abstractmethod
    async def update_meeting(
        self, current_user: AuthenticatedUser, meeting_id: str, request: MeetingUpdateRequest
    ) -> MeetingResponse: ...

    @abstractmethod
    async def delete_meeting(self, current_user: AuthenticatedUser, meeting_id: str) -> None: ...
