from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.providers import CurrentUserDep, TranscriptServiceDep
from app.schemas.transcript_dto import (
    TranscriptReplaceRequest,
    TranscriptResponse,
    TranscriptVersionDetailResponse,
    TranscriptVersionResponse,
)

router = APIRouter(prefix="/api/v1/meetings/{meeting_id}", tags=["transcripts"])


@router.get("/transcript")
async def get_transcript(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TranscriptResponse:
    """Omitting limit returns the whole transcript; `total` is the full count either way."""
    return await transcript_service.get_transcript(current_user, meeting_id, limit, offset)


@router.put("/transcript")
async def replace_transcript(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
    request: TranscriptReplaceRequest,
) -> TranscriptResponse:
    return await transcript_service.replace_transcript(current_user, meeting_id, request)


@router.get("/transcript/versions")
async def list_transcript_versions(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
) -> list[TranscriptVersionResponse]:
    return await transcript_service.list_versions(current_user, meeting_id)


@router.post("/transcript/versions/{version}/restore")
async def restore_transcript_version(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
    version: int,
) -> TranscriptResponse:
    """Archives the current transcript, then swaps in the requested version."""
    return await transcript_service.restore_version(current_user, meeting_id, version)


@router.get("/transcript/versions/{version}")
async def get_transcript_version(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
    version: int,
) -> TranscriptVersionDetailResponse:
    return await transcript_service.get_version(current_user, meeting_id, version)
