from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.summary_dto import (
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
