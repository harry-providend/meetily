from datetime import UTC, datetime

from pydantic import JsonValue, ValidationError

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import ConflictException, NotFoundException
from app.domain.transcript import TranscriptEntity
from app.domain.transcript_version import TranscriptVersionEntity
from app.repositories.interfaces.transcript_repository import TranscriptRepository
from app.repositories.interfaces.transcript_version_repository import TranscriptVersionRepository
from app.schemas.transcript_dto import (
    TranscriptReplaceRequest,
    TranscriptResponse,
    TranscriptSearchHit,
    TranscriptSearchResponse,
    TranscriptSegmentRequest,
    TranscriptSegmentResponse,
    TranscriptVersionDetailResponse,
    TranscriptVersionResponse,
)
from app.services.implementations.match_context_extractor import MatchContextExtractor
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.transcript_service import TranscriptService


class DefaultTranscriptService(TranscriptService):
    def __init__(
        self,
        transcript_repository: TranscriptRepository,
        version_repository: TranscriptVersionRepository,
        ownership_guard: MeetingOwnershipGuard,
        match_context_extractor: MatchContextExtractor,
    ) -> None:
        self._transcript_repository = transcript_repository
        self._version_repository = version_repository
        self._ownership_guard = ownership_guard
        self._match_context_extractor = match_context_extractor

    async def get_transcript(
        self,
        current_user: AuthenticatedUser,
        meeting_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> TranscriptResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        if limit is None:
            segments = await self._transcript_repository.find_all_for_meeting(meeting_id)
            total = len(segments)
        else:
            segments = await self._transcript_repository.find_page_for_meeting(
                meeting_id, limit=limit, offset=offset
            )
            total = await self._transcript_repository.count_for_meeting(meeting_id)
        return TranscriptResponse(
            meeting_id=meeting_id,
            segments=[TranscriptSegmentResponse.model_validate(s) for s in segments],
            total=total,
        )

    async def search(
        self, current_user: AuthenticatedUser, query: str, limit: int
    ) -> TranscriptSearchResponse:
        if not query.strip():
            return TranscriptSearchResponse(hits=[])
        matches = await self._transcript_repository.search_for_owner(
            owner_user_id=current_user.oid,
            owner_tenant_id=current_user.tenant_id,
            query=query,
            limit=limit,
        )
        return TranscriptSearchResponse(
            hits=[
                TranscriptSearchHit(
                    meeting_id=match.meeting_id,
                    meeting_title=match.meeting_title,
                    match_context=self._match_context_extractor.extract(match.transcript, query),
                    timestamp=match.timestamp,
                )
                for match in matches
            ]
        )

    async def replace_transcript(
        self, current_user: AuthenticatedUser, meeting_id: str, request: TranscriptReplaceRequest
    ) -> TranscriptResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)

        # Archive before overwriting, mirroring the app's retranscription flow.
        existing = await self._transcript_repository.find_all_for_meeting(meeting_id)
        if existing:
            await self._archive(meeting_id, request.reason, existing)

        await self._transcript_repository.delete_all_for_meeting(meeting_id)
        await self._transcript_repository.save_all(
            [
                TranscriptEntity(
                    id=segment.id,
                    meeting_id=meeting_id,
                    transcript=segment.transcript,
                    timestamp=segment.timestamp,
                    audio_start_time=segment.audio_start_time,
                    audio_end_time=segment.audio_end_time,
                    duration=segment.duration,
                    speaker=segment.speaker,
                )
                for segment in request.segments
            ]
        )
        return await self.get_transcript(current_user, meeting_id)

    async def restore_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> TranscriptResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)

        target = await self._version_repository.find_version_for_meeting(meeting_id, version)
        if target is None:
            raise NotFoundException(f"version {version} not found for meeting {meeting_id}")

        # Validated through the same DTO as an ordinary write, so a malformed archive is a clear
        # 422 rather than an integrity error deeper down.
        try:
            segments = [
                TranscriptSegmentRequest.model_validate(segment) for segment in target.segments_json
            ]
        except ValidationError as exc:
            raise ConflictException(f"version {version} is not readable: {exc}") from exc

        return await self.replace_transcript(
            current_user,
            meeting_id,
            TranscriptReplaceRequest(reason="restore", segments=segments),
        )

    async def list_versions(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> list[TranscriptVersionResponse]:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        versions = await self._version_repository.find_all_for_meeting(meeting_id)
        return [TranscriptVersionResponse.model_validate(v) for v in versions]

    async def get_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> TranscriptVersionDetailResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity = await self._version_repository.find_version_for_meeting(meeting_id, version)
        if entity is None:
            raise NotFoundException(f"version {version} not found for meeting {meeting_id}")
        return TranscriptVersionDetailResponse.model_validate(entity)

    async def _archive(
        self, meeting_id: str, reason: str, segments: list[TranscriptEntity]
    ) -> None:
        next_version = await self._version_repository.next_version_for_meeting(meeting_id)
        segments_json: list[JsonValue] = [
            {
                "id": s.id,
                "transcript": s.transcript,
                "timestamp": s.timestamp,
                "audio_start_time": s.audio_start_time,
                "audio_end_time": s.audio_end_time,
                "duration": s.duration,
                "speaker": s.speaker,
            }
            for s in segments
        ]
        await self._version_repository.save(
            TranscriptVersionEntity(
                meeting_id=meeting_id,
                version=next_version,
                reason=reason,
                segments_json=segments_json,
                segment_count=len(segments),
                created_at=datetime.now(UTC),
            )
        )
