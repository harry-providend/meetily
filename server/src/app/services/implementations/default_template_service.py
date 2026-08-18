from datetime import UTC, datetime

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import ForbiddenException, NotFoundException
from app.domain.summary_template import SummaryTemplateEntity
from app.repositories.interfaces.summary_template_repository import SummaryTemplateRepository
from app.schemas.template_dto import (
    SummaryTemplateListResponse,
    SummaryTemplateResponse,
    SummaryTemplateUpsertRequest,
)
from app.services.interfaces.template_service import TemplateService


class DefaultTemplateService(TemplateService):
    def __init__(self, template_repository: SummaryTemplateRepository) -> None:
        self._template_repository = template_repository

    async def list_templates(self, current_user: AuthenticatedUser) -> SummaryTemplateListResponse:
        entities = await self._template_repository.find_all_visible_to_tenant(
            current_user.tenant_id
        )
        return SummaryTemplateListResponse(
            items=[SummaryTemplateResponse.model_validate(e) for e in entities]
        )

    async def get_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateResponse:
        entity = await self._require_visible_template(current_user, template_id)
        return SummaryTemplateResponse.model_validate(entity)

    async def upsert_template(
        self, current_user: AuthenticatedUser, request: SummaryTemplateUpsertRequest
    ) -> SummaryTemplateResponse:
        existing = await self._template_repository.find_by_id_visible_to_tenant(
            request.id, current_user.tenant_id
        )
        if existing is not None and existing.is_builtin:
            raise ForbiddenException("builtin templates cannot be modified")

        now = datetime.now(UTC)
        entity = SummaryTemplateEntity(
            id=request.id,
            owner_tenant_id=current_user.tenant_id,
            name=request.name,
            description=request.description,
            sections_json=request.sections_json,
            is_builtin=False,
            user_modified=True,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        saved = await self._template_repository.save(entity)
        return SummaryTemplateResponse.model_validate(saved)

    async def delete_template(self, current_user: AuthenticatedUser, template_id: str) -> None:
        deleted = await self._template_repository.delete_for_tenant(
            template_id, current_user.tenant_id
        )
        if not deleted:
            # Either absent, or a builtin -- delete_for_tenant matches only tenant-owned rows.
            raise NotFoundException(f"template {template_id} not found")

    async def _require_visible_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateEntity:
        entity = await self._template_repository.find_by_id_visible_to_tenant(
            template_id, current_user.tenant_id
        )
        if entity is None:
            raise NotFoundException(f"template {template_id} not found")
        return entity
