from fastapi import APIRouter, status

from app.dependencies.providers import CurrentUserDep, TemplateServiceDep
from app.schemas.template_dto import (
    SummaryTemplateListResponse,
    SummaryTemplateResponse,
    SummaryTemplateUpsertRequest,
)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("")
async def list_templates(
    current_user: CurrentUserDep,
    template_service: TemplateServiceDep,
) -> SummaryTemplateListResponse:
    return await template_service.list_templates(current_user)


@router.put("")
async def upsert_template(
    current_user: CurrentUserDep,
    template_service: TemplateServiceDep,
    request: SummaryTemplateUpsertRequest,
) -> SummaryTemplateResponse:
    return await template_service.upsert_template(current_user, request)


@router.get("/{template_id}")
async def get_template(
    current_user: CurrentUserDep,
    template_service: TemplateServiceDep,
    template_id: str,
) -> SummaryTemplateResponse:
    return await template_service.get_template(current_user, template_id)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    current_user: CurrentUserDep,
    template_service: TemplateServiceDep,
    template_id: str,
) -> None:
    await template_service.delete_template(current_user, template_id)
