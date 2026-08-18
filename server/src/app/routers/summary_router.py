from fastapi import APIRouter

from app.dependencies.providers import CurrentUserDep, SummaryServiceDep
from app.schemas.summary_dto import (
    SummaryCompleteRequest,
    SummaryFailRequest,
    SummaryProcessResponse,
    SummaryProcessUpsertRequest,
    SummaryVersionResponse,
)

router = APIRouter(prefix="/api/v1/meetings/{meeting_id}", tags=["summaries"])


@router.get("/summary")
async def get_summary(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
) -> SummaryProcessResponse:
    return await summary_service.get_summary(current_user, meeting_id)


@router.put("/summary")
async def upsert_summary(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
    request: SummaryProcessUpsertRequest,
) -> SummaryProcessResponse:
    return await summary_service.upsert_summary(current_user, meeting_id, request)


@router.post("/summary/generation")
async def start_generation(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
) -> SummaryProcessResponse:
    """Begins a run. The existing summary is stashed so a failure can restore it."""
    return await summary_service.start_generation(current_user, meeting_id)


@router.post("/summary/generation/complete")
async def complete_generation(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
    request: SummaryCompleteRequest,
) -> SummaryProcessResponse:
    return await summary_service.complete_generation(current_user, meeting_id, request)


@router.post("/summary/generation/fail")
async def fail_generation(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
    request: SummaryFailRequest,
) -> SummaryProcessResponse:
    return await summary_service.fail_generation(current_user, meeting_id, request)


@router.post("/summary/generation/cancel")
async def cancel_generation(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
) -> SummaryProcessResponse:
    return await summary_service.cancel_generation(current_user, meeting_id)


@router.get("/summary/versions")
async def list_summary_versions(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
) -> list[SummaryVersionResponse]:
    return await summary_service.list_versions(current_user, meeting_id)


@router.get("/summary/versions/{version}")
async def get_summary_version(
    current_user: CurrentUserDep,
    summary_service: SummaryServiceDep,
    meeting_id: str,
    version: int,
) -> SummaryVersionResponse:
    return await summary_service.get_version(current_user, meeting_id, version)
