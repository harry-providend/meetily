from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.template_dto import (
    SummaryTemplateListResponse,
    SummaryTemplateResponse,
    SummaryTemplateUpsertRequest,
)


class TemplateService(ABC):
    @abstractmethod
    async def list_templates(
        self, current_user: AuthenticatedUser
    ) -> SummaryTemplateListResponse: ...

    @abstractmethod
    async def get_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateResponse: ...

    @abstractmethod
    async def upsert_template(
        self, current_user: AuthenticatedUser, request: SummaryTemplateUpsertRequest
    ) -> SummaryTemplateResponse: ...

    @abstractmethod
    async def delete_template(self, current_user: AuthenticatedUser, template_id: str) -> None: ...
