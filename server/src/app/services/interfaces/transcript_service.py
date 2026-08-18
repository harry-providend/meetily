from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.summary_dto import TranscriptVersionDetailResponse, TranscriptVersionResponse
from app.schemas.transcript_dto import TranscriptReplaceRequest, TranscriptResponse


class TranscriptService(ABC):
    @abstractmethod
    async def get_transcript(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> TranscriptResponse: ...

    @abstractmethod
    async def replace_transcript(
        self, current_user: AuthenticatedUser, meeting_id: str, request: TranscriptReplaceRequest
    ) -> TranscriptResponse: ...

    @abstractmethod
    async def list_versions(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> list[TranscriptVersionResponse]: ...

    @abstractmethod
    async def get_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> TranscriptVersionDetailResponse: ...
