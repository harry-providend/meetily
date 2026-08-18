from fastapi import APIRouter

from app.dependencies.providers import CurrentUserDep, NotesServiceDep
from app.schemas.notes_dto import MeetingNotesResponse, MeetingNotesUpsertRequest

router = APIRouter(prefix="/api/v1/meetings/{meeting_id}", tags=["notes"])


@router.get("/notes")
async def get_notes(
    current_user: CurrentUserDep,
    notes_service: NotesServiceDep,
    meeting_id: str,
) -> MeetingNotesResponse:
    return await notes_service.get_notes(current_user, meeting_id)


@router.put("/notes")
async def upsert_notes(
    current_user: CurrentUserDep,
    notes_service: NotesServiceDep,
    meeting_id: str,
    request: MeetingNotesUpsertRequest,
) -> MeetingNotesResponse:
    return await notes_service.upsert_notes(current_user, meeting_id, request)
