from abc import ABC, abstractmethod

from app.auth.current_user import AuthenticatedUser
from app.schemas.template_dto import (
    SummaryTemplateListResponse,
    SummaryTemplateResponse,
    SummaryTemplateUpsertRequest,
    TemplateImportResponse,
    TemplateSeedRequest,
    TemplateSeedResponse,
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
    async def save_template(
        self, current_user: AuthenticatedUser, request: SummaryTemplateUpsertRequest
    ) -> SummaryTemplateResponse:
        """Records a user edit. Keeps is_builtin as it was and marks the row modified."""

    @abstractmethod
    async def delete_template(self, current_user: AuthenticatedUser, template_id: str) -> None:
        """Refuses builtins: they are reset, not deleted."""

    @abstractmethod
    async def seed_templates(
        self, current_user: AuthenticatedUser, request: TemplateSeedRequest
    ) -> TemplateSeedResponse:
        """Applies the app's shipped templates, leaving user-edited rows alone."""

    @abstractmethod
    async def import_templates(
        self, current_user: AuthenticatedUser, request: TemplateSeedRequest
    ) -> TemplateImportResponse:
        """One-time legacy import: writes only ids that are absent, never overwrites."""

    @abstractmethod
    async def reset_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateResponse:
        """Clears the modified flag so the next seed restores the shipped content."""
