from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    """Rejects a segment whose audio window runs backwards, and derives duration rather than
    trusting it.

    The desktop app has produced inverted segments (the VAD's force-end path can report an end
    before the start), and duration is redundant with the other two, so a client-supplied value
    can only ever disagree with them. Enforced here because this is the single writer for every
    path: live recording, recovery, retranscription and import.
    """

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
