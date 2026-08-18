import json
from datetime import UTC, datetime

from pydantic import JsonValue

from app.auth.current_user import AuthenticatedUser
from app.core.exceptions import NotFoundException
from app.domain.summary_process import SummaryProcessEntity
from app.domain.summary_version import SummaryVersionEntity
from app.repositories.interfaces.summary_process_repository import SummaryProcessRepository
from app.repositories.interfaces.summary_version_repository import SummaryVersionRepository
from app.schemas.summary_dto import (
    SummaryCompleteRequest,
    SummaryFailRequest,
    SummaryProcessResponse,
    SummaryProcessUpsertRequest,
    SummaryVersionResponse,
)
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.summary_service import SummaryService

# Set by the server rather than the caller: the reason a run stopped is ours to state.
CANCELLED_MESSAGE = "Generation was cancelled by user"


class DefaultSummaryService(SummaryService):
    """Generation is a run: start -> complete | fail | cancel. start stashes the current result,
    complete archives the stash as a version, and fail and cancel restore from it."""

    def __init__(
        self,
        summary_process_repository: SummaryProcessRepository,
        version_repository: SummaryVersionRepository,
        ownership_guard: MeetingOwnershipGuard,
    ) -> None:
        self._summary_process_repository = summary_process_repository
        self._version_repository = version_repository
        self._ownership_guard = ownership_guard

    async def get_summary(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity = await self._summary_process_repository.find_for_meeting(meeting_id)
        if entity is None:
            raise NotFoundException(f"no summary for meeting {meeting_id}")
        return SummaryProcessResponse.model_validate(entity)

    async def start_generation(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        now = datetime.now(UTC)
        entity = await self._summary_process_repository.find_for_meeting(meeting_id)

        if entity is None:
            entity = SummaryProcessEntity(
                meeting_id=meeting_id,
                status="PENDING",
                created_at=now,
                updated_at=now,
                start_time=now,
                chunk_count=0,
                processing_time=0.0,
            )
        else:
            # The result stays visible while the new one is generated; the copy is what makes a
            # failure recoverable.
            entity.result_backup = entity.result
            entity.result_backup_timestamp = now
            entity.status = "PENDING"
            entity.error = None
            entity.start_time = now
            entity.end_time = None
            entity.updated_at = now

        return SummaryProcessResponse.model_validate(
            await self._summary_process_repository.save(entity)
        )

    async def complete_generation(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryCompleteRequest
    ) -> SummaryProcessResponse:
        entity = await self._require_process(current_user, meeting_id)
        now = datetime.now(UTC)

        # Archived here, not at start: a run that never finished must not leave a version behind.
        if entity.result_backup is not None:
            await self._archive(meeting_id, entity.result_backup, reason="regeneration")

        entity.status = "completed"
        entity.result = request.result
        entity.english_cache = request.english_cache
        entity.error = None
        entity.chunk_count = request.chunk_count
        entity.processing_time = request.processing_time
        entity.end_time = now
        entity.updated_at = now
        entity.result_backup = None
        entity.result_backup_timestamp = None

        return SummaryProcessResponse.model_validate(
            await self._summary_process_repository.save(entity)
        )

    async def fail_generation(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryFailRequest
    ) -> SummaryProcessResponse:
        return await self._stop_generation(current_user, meeting_id, "failed", request.error)

    async def cancel_generation(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessResponse:
        return await self._stop_generation(current_user, meeting_id, "cancelled", CANCELLED_MESSAGE)

    async def _stop_generation(
        self, current_user: AuthenticatedUser, meeting_id: str, status: str, error: str
    ) -> SummaryProcessResponse:
        entity = await self._require_process(current_user, meeting_id)
        now = datetime.now(UTC)

        entity.status = status
        entity.error = error
        entity.end_time = now
        entity.updated_at = now
        # Roll back to whatever was showing before this run, if anything was.
        if entity.result_backup is not None:
            entity.result = entity.result_backup
        entity.result_backup = None
        entity.result_backup_timestamp = None

        return SummaryProcessResponse.model_validate(
            await self._summary_process_repository.save(entity)
        )

    async def _require_process(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> SummaryProcessEntity:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity = await self._summary_process_repository.find_for_meeting(meeting_id)
        if entity is None:
            raise NotFoundException(f"no summary generation in progress for meeting {meeting_id}")
        return entity

    async def upsert_summary(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryProcessUpsertRequest
    ) -> SummaryProcessResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)

        existing = await self._summary_process_repository.find_for_meeting(meeting_id)
        now = datetime.now(UTC)

        # A direct save, not part of a generation run: archive whatever it replaces.
        if existing is not None and existing.result is not None:
            await self._archive(meeting_id, existing.result, reason="superseded")

        entity = SummaryProcessEntity(
            meeting_id=meeting_id,
            status=request.status,
            result=request.result,
            error=request.error,
            chunk_count=request.chunk_count,
            processing_time=request.processing_time,
            start_time=request.start_time,
            end_time=request.end_time,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        saved = await self._summary_process_repository.save(entity)
        return SummaryProcessResponse.model_validate(saved)

    async def restore_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> SummaryProcessResponse:
        entity = await self._require_process(current_user, meeting_id)

        target = await self._version_repository.find_version_for_meeting(meeting_id, version)
        if target is None:
            raise NotFoundException(f"version {version} not found for meeting {meeting_id}")

        # Archive what the restore displaces, so restoring is undoable too.
        if entity.result is not None:
            await self._archive(meeting_id, entity.result, reason="restore")

        entity.result = json.dumps(target.result_json)
        entity.status = "completed"
        entity.error = None
        entity.updated_at = datetime.now(UTC)
        # A restore is not a generation run, so in-flight state is meaningless -- and the cache
        # belonged to whichever run produced the summary being displaced, not this one.
        entity.result_backup = None
        entity.result_backup_timestamp = None
        entity.english_cache = None

        return SummaryProcessResponse.model_validate(
            await self._summary_process_repository.save(entity)
        )

    async def list_versions(
        self, current_user: AuthenticatedUser, meeting_id: str
    ) -> list[SummaryVersionResponse]:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        versions = await self._version_repository.find_all_for_meeting(meeting_id)
        return [SummaryVersionResponse.model_validate(v) for v in versions]

    async def get_version(
        self, current_user: AuthenticatedUser, meeting_id: str, version: int
    ) -> SummaryVersionResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)
        entity = await self._version_repository.find_version_for_meeting(meeting_id, version)
        if entity is None:
            raise NotFoundException(f"version {version} not found for meeting {meeting_id}")
        return SummaryVersionResponse.model_validate(entity)

    async def _archive(self, meeting_id: str, previous_result: str, reason: str) -> None:
        next_version = await self._version_repository.next_version_for_meeting(meeting_id)
        await self._version_repository.save(
            SummaryVersionEntity(
                meeting_id=meeting_id,
                version=next_version,
                reason=reason,
                result_json=self._as_json_object(previous_result),
                created_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _as_json_object(result: str) -> dict[str, JsonValue]:
        """Summaries are stored as a JSON string by the desktop app, but older rows may hold
        plain text. Keep unparseable content rather than dropping it."""
        try:
            parsed: JsonValue = json.loads(result)
        except json.JSONDecodeError:
            return {"raw": result}
        if isinstance(parsed, dict):
            return parsed
        return {"raw": parsed}
