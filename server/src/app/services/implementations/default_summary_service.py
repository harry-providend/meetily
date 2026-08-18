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
    SummaryProcessResponse,
    SummaryProcessUpsertRequest,
    SummaryVersionResponse,
)
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.summary_service import SummaryService


class DefaultSummaryService(SummaryService):
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

    async def upsert_summary(
        self, current_user: AuthenticatedUser, meeting_id: str, request: SummaryProcessUpsertRequest
    ) -> SummaryProcessResponse:
        await self._ownership_guard.require_owned_meeting(current_user, meeting_id)

        existing = await self._summary_process_repository.find_for_meeting(meeting_id)
        now = datetime.now(UTC)

        # Archive before overwriting -- numbered history, replacing the old result_backup slot.
        if existing is not None and existing.result is not None:
            await self._archive(meeting_id, existing.result)

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

    async def _archive(self, meeting_id: str, previous_result: str) -> None:
        next_version = await self._version_repository.next_version_for_meeting(meeting_id)
        await self._version_repository.save(
            SummaryVersionEntity(
                meeting_id=meeting_id,
                version=next_version,
                reason="superseded",
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
