from fastapi import APIRouter

from app.dependencies.providers import CurrentUserDep, TranscriptServiceDep
from app.schemas.summary_dto import TranscriptVersionDetailResponse, TranscriptVersionResponse
from app.schemas.transcript_dto import TranscriptReplaceRequest, TranscriptResponse

router = APIRouter(prefix="/api/v1/meetings/{meeting_id}", tags=["transcripts"])


@router.get("/transcript")
async def get_transcript(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
) -> TranscriptResponse:
    return await transcript_service.get_transcript(current_user, meeting_id)


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


@router.get("/transcript/versions/{version}")
async def get_transcript_version(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    meeting_id: str,
    version: int,
) -> TranscriptVersionDetailResponse:
    return await transcript_service.get_version(current_user, meeting_id, version)
