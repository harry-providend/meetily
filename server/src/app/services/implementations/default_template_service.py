from datetime import UTC, datetime

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import ConflictException, NotFoundException
from app.domain.summary_template import SummaryTemplateEntity
from app.repositories.interfaces.summary_template_repository import SummaryTemplateRepository
from app.schemas.template_dto import (
    ShippedTemplate,
    SummaryTemplateListResponse,
    SummaryTemplateResponse,
    SummaryTemplateUpsertRequest,
    TemplateImportResponse,
    TemplateSeedRequest,
    TemplateSeedResponse,
)
from app.services.interfaces.template_service import TemplateService


class DefaultTemplateService(TemplateService):
    """Holds the two flags the desktop app's seeding depends on.

    is_builtin says the app ships this template; user_modified says the user has edited it. Seeding
    re-applies shipped content to builtins but never over an edit, so a user's changes survive
    every update, and resetting is just clearing the flag and seeding again.
    """

    def __init__(self, template_repository: SummaryTemplateRepository) -> None:
        self._template_repository = template_repository

    async def list_templates(self, current_user: AuthenticatedUser) -> SummaryTemplateListResponse:
        entities = await self._template_repository.find_all_for_owner(
            owner_user_id=current_user.oid, owner_tenant_id=current_user.tenant_id
        )
        return SummaryTemplateListResponse(
            items=[SummaryTemplateResponse.model_validate(e) for e in entities]
        )

    async def get_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateResponse:
        return SummaryTemplateResponse.model_validate(
            await self._require_template(current_user, template_id)
        )

    async def save_template(
        self, current_user: AuthenticatedUser, request: SummaryTemplateUpsertRequest
    ) -> SummaryTemplateResponse:
        existing = await self._find(current_user, request.id)
        now = datetime.now(UTC)

        entity = SummaryTemplateEntity(
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
            id=request.id,
            name=request.name,
            description=request.description,
            sections_json=request.sections_json,
            # Editing a shipped template leaves it shipped, so a later reset can still restore it.
            is_builtin=existing.is_builtin if existing is not None else False,
            user_modified=True,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        return SummaryTemplateResponse.model_validate(await self._template_repository.save(entity))

    async def delete_template(self, current_user: AuthenticatedUser, template_id: str) -> None:
        entity = await self._require_template(current_user, template_id)
        if entity.is_builtin:
            raise ConflictException(
                "Built-in templates cannot be deleted. Reset them to the shipped version instead."
            )
        await self._template_repository.delete_for_owner(
            template_id=template_id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )

    async def seed_templates(
        self, current_user: AuthenticatedUser, request: TemplateSeedRequest
    ) -> TemplateSeedResponse:
        written = 0
        skipped = 0
        for shipped in request.templates:
            existing = await self._find(current_user, shipped.id)
            if existing is not None and existing.user_modified:
                skipped += 1
                continue
            await self._write_shipped(current_user, shipped, existing)
            written += 1
        return TemplateSeedResponse(written=written, skipped_user_modified=skipped)

    async def import_templates(
        self, current_user: AuthenticatedUser, request: TemplateSeedRequest
    ) -> TemplateImportResponse:
        imported: list[str] = []
        already_present: list[str] = []
        now = datetime.now(UTC)

        for candidate in request.templates:
            if await self._find(current_user, candidate.id) is not None:
                already_present.append(candidate.id)
                continue
            await self._template_repository.save(
                SummaryTemplateEntity(
                    owner_user_id=current_user.oid,
                    owner_tenant_id=current_user.tenant_id,
                    id=candidate.id,
                    name=candidate.name,
                    description=candidate.description,
                    sections_json=candidate.sections_json,
                    is_builtin=False,
                    user_modified=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            imported.append(candidate.id)

        return TemplateImportResponse(imported=imported, already_present=already_present)

    async def reset_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateResponse:
        entity = await self._require_template(current_user, template_id)
        if not entity.is_builtin:
            raise ConflictException("Only built-in templates can be reset to the shipped version")

        # Only the flag changes here. The content comes back when the app seeds, because the
        # shipped definitions live in the app bundle, not on the server.
        entity.user_modified = False
        entity.updated_at = datetime.now(UTC)
        return SummaryTemplateResponse.model_validate(await self._template_repository.save(entity))

    async def _write_shipped(
        self,
        current_user: AuthenticatedUser,
        shipped: ShippedTemplate,
        existing: SummaryTemplateEntity | None,
    ) -> None:
        now = datetime.now(UTC)
        await self._template_repository.save(
            SummaryTemplateEntity(
                owner_user_id=current_user.oid,
                owner_tenant_id=current_user.tenant_id,
                id=shipped.id,
                name=shipped.name,
                description=shipped.description,
                sections_json=shipped.sections_json,
                is_builtin=True,
                user_modified=False,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
        )

    async def _find(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateEntity | None:
        return await self._template_repository.find_by_id_for_owner(
            template_id=template_id,
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
        )

    async def _require_template(
        self, current_user: AuthenticatedUser, template_id: str
    ) -> SummaryTemplateEntity:
        entity = await self._find(current_user, template_id)
        if entity is None:
            raise NotFoundException(f"template {template_id} not found")
        return entity
