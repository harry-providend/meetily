from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.summary_dto import TranscriptVersionDetailResponse, TranscriptVersionResponse
from app.schemas.transcript_dto import (
    TranscriptReplaceRequest,
    TranscriptResponse,
    TranscriptSearchResponse,
)


class TranscriptService(ABC):
    @abstractmethod
    async def get_transcript(
        self,
        current_user: AuthenticatedUser,
        meeting_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> TranscriptResponse:
        """Whole transcript when limit is None, otherwise one page of it."""

    @abstractmethod
    async def search(
        self, current_user: AuthenticatedUser, query: str, limit: int
    ) -> TranscriptSearchResponse: ...

    @abstractmethod
    async def replace_transcript(
        self, current_user: AuthenticatedUser, meeting_id: str, request: TranscriptReplaceRequest
    ) -> TranscriptResponse: ...

    @abstractmethod
    async def restore_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> TranscriptResponse:
        """Replaces the live transcript with an archived one, archiving what it replaces first so
        the restore is itself undoable."""

    @abstractmethod
    async def list_versions(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> list[TranscriptVersionResponse]: ...

    @abstractmethod
    async def get_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> TranscriptVersionDetailResponse: ...
