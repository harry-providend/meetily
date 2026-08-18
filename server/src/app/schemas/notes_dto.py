from datetime import datetime

from pydantic import BaseModel, ConfigDict, JsonValue


class MeetingNotesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    notes_markdown: str | None
    notes_json: dict[str, JsonValue] | None
    created_at: datetime
    updated_at: datetime


class MeetingNotesUpsertRequest(BaseModel):
    notes_markdown: str | None = None
    notes_json: dict[str, JsonValue] | None = None
