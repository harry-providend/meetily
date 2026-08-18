from pydantic import BaseModel, ConfigDict, Field


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
    """`total` is the segment count for the whole meeting, not this page, so a caller reading
    incrementally knows when to stop."""

    meeting_id: str
    segments: list[TranscriptSegmentResponse]
    total: int


class TranscriptSegmentRequest(BaseModel):
    id: str = Field(min_length=1)
    transcript: str
    timestamp: str
    audio_start_time: float | None = None
    audio_end_time: float | None = None
    duration: float | None = None
    speaker: str | None = None


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
