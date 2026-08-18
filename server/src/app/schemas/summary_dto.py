from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class SummaryProcessResponse(BaseModel):
    """result_backup is not exposed: a client that could set it could corrupt the rollback."""

    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    status: str
    result: str | None
    english_cache: dict[str, JsonValue] | None
    error: str | None
    chunk_count: int
    processing_time: float
    start_time: datetime | None
    end_time: datetime | None
    created_at: datetime
    updated_at: datetime


class SummaryCompleteRequest(BaseModel):
    """The cache travels beside the document, never inside it."""

    result: str = Field(min_length=1)
    chunk_count: int = Field(ge=0, default=0)
    processing_time: float = Field(ge=0.0, default=0.0)
    english_cache: dict[str, JsonValue] | None = None


class SummaryFailRequest(BaseModel):
    error: str = Field(min_length=1)


class SummaryProcessUpsertRequest(BaseModel):
    status: str = Field(min_length=1)
    result: str | None = None
    error: str | None = None
    chunk_count: int = 0
    processing_time: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None


class SummaryVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    version: int
    reason: str
    result_json: dict[str, JsonValue]
    created_at: datetime


class TranscriptVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    version: int
    reason: str
    segment_count: int
    created_at: datetime


class TranscriptVersionDetailResponse(TranscriptVersionResponse):
    segments_json: list[JsonValue]
