from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.providers import CurrentUserDep, TranscriptServiceDep
from app.schemas.transcript_dto import TranscriptSearchResponse

# Outside the per-meeting prefix: search spans every meeting the caller owns.
router = APIRouter(prefix="/api/v1/transcripts", tags=["transcripts"])


@router.get("/search")
async def search_transcripts(
    current_user: CurrentUserDep,
    transcript_service: TranscriptServiceDep,
    query: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TranscriptSearchResponse:
    return await transcript_service.search(current_user, query, limit)
