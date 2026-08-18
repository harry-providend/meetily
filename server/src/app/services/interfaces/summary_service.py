from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.summary_dto import (
    SummaryCompleteRequest,
    SummaryFailRequest,
    SummaryProcessResponse,
    SummaryProcessUpsertRequest,
    SummaryVersionResponse,
)


class SummaryService(ABC):
    @abstractmethod
    async def get_summary(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse: ...

    @abstractmethod
    async def start_generation(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse:
        """Moves to PENDING and stashes the current result for rollback."""

    @abstractmethod
    async def complete_generation(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryCompleteRequest
    ) -> SummaryProcessResponse:
        """Stores the new result and turns the stashed one into a numbered version."""

    @abstractmethod
    async def fail_generation(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryFailRequest
    ) -> SummaryProcessResponse:
        """Records the failure and restores the stashed result, leaving no version behind."""

    @abstractmethod
    async def cancel_generation(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse:
        """As fail_generation, for a user-initiated stop."""

    @abstractmethod
    async def upsert_summary(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryProcessUpsertRequest
    ) -> SummaryProcessResponse: ...

    @abstractmethod
    async def list_versions(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> list[SummaryVersionResponse]: ...

    @abstractmethod
    async def get_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> SummaryVersionResponse: ...
