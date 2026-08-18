from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.transcript_dto import TranscriptSegmentRequest


class MeetingResponse(BaseModel):
    """Note the absence of owner_user_id/owner_tenant_id: ownership is an internal concern and
    every response is already scoped to the caller, so echoing it back adds nothing."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    folder_path: str | None
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    items: list[MeetingResponse]
    total: int


class MeetingCreateRequest(BaseModel):
    """Segments may be supplied with the meeting, so finalisation is one transaction."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    folder_path: str | None = None
    segments: list[TranscriptSegmentRequest] = Field(default_factory=list)


class MeetingUpdateRequest(BaseModel):
    title: str = Field(min_length=1)
