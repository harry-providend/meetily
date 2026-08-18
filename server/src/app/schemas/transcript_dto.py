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
    meeting_id: str
    segments: list[TranscriptSegmentResponse]


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
