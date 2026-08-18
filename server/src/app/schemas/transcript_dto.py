from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript: str
    timestamp: str
    audio_start_time: float | None
    audio_end_time: float | None
    duration: float | None
    speaker: str | None


class TranscriptResponse(BaseModel):
    """`total` counts the whole meeting, not this page."""

    meeting_id: str
    segments: list[TranscriptSegmentResponse]
    total: int


class TranscriptSegmentRequest(BaseModel):
    """Rejects a backwards audio window and derives duration, which is redundant with it. Enforced
    here because this is the single writer for every path."""

    id: str = Field(min_length=1)
    transcript: str
    timestamp: str
    audio_start_time: float | None = None
    audio_end_time: float | None = None
    duration: float | None = None
    speaker: str | None = None

    @model_validator(mode="after")
    def _check_audio_window(self) -> Self:
        start, end = self.audio_start_time, self.audio_end_time
        if start is not None and end is not None:
            if end < start:
                raise ValueError(f"audio_end_time ({end}) precedes audio_start_time ({start})")
            self.duration = end - start
        return self


class TranscriptReplaceRequest(BaseModel):
    """Replaces a meeting's whole transcript, matching the app's retranscription flow. Segment
    order is this list's order."""

    reason: str = Field(min_length=1)
    segments: list[TranscriptSegmentRequest]


class TranscriptSearchHit(BaseModel):
    """One matching segment, with the surrounding text needed to render a result row."""

    meeting_id: str
    meeting_title: str
    match_context: str
    timestamp: str


class TranscriptSearchResponse(BaseModel):
    hits: list[TranscriptSearchHit]


class TranscriptVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: str
    version: int
    reason: str
    segment_count: int
    created_at: datetime


class TranscriptVersionDetailResponse(TranscriptVersionResponse):
    segments_json: list[JsonValue]
