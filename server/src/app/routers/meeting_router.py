from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencies.providers import CurrentUserDep, MeetingServiceDep
from app.schemas.meeting_dto import (
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdateRequest,
)

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.get("")
async def list_meetings(
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MeetingListResponse:
    return await meeting_service.list_meetings(current_user, page, page_size)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_meeting(
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    request: MeetingCreateRequest,
) -> MeetingResponse:
    return await meeting_service.create_meeting(current_user, request)


@router.get("/{meeting_id}")
async def get_meeting(
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    meeting_id: str,
) -> MeetingResponse:
    return await meeting_service.get_meeting(current_user, meeting_id)


@router.patch("/{meeting_id}")
async def update_meeting(
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    meeting_id: str,
    request: MeetingUpdateRequest,
) -> MeetingResponse:
    return await meeting_service.update_meeting(current_user, meeting_id, request)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    current_user: CurrentUserDep,
    meeting_service: MeetingServiceDep,
    meeting_id: str,
) -> None:
    await meeting_service.delete_meeting(current_user, meeting_id)
