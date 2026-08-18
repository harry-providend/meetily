"""The DI graph. Every provider returns an interface type, so this is the only place
interface-to-implementation binding happens."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.current_user import AuthenticatedUser
from app.auth.entra_token_validator import TokenValidator
from app.auth.exceptions import InvalidTokenError
from app.composition_root import get_token_validator
from app.db.session import get_db_session
from app.repositories.interfaces.meeting_notes_repository import MeetingNotesRepository
from app.repositories.interfaces.meeting_repository import MeetingRepository
from app.repositories.interfaces.outbox_repository import OutboxRepository
from app.repositories.interfaces.summary_process_repository import SummaryProcessRepository
from app.repositories.interfaces.summary_template_repository import SummaryTemplateRepository
from app.repositories.interfaces.summary_version_repository import SummaryVersionRepository
from app.repositories.interfaces.transcript_repository import TranscriptRepository
from app.repositories.interfaces.transcript_version_repository import TranscriptVersionRepository
from app.repositories.sqlalchemy.sqlalchemy_meeting_notes_repository import (
    SqlAlchemyMeetingNotesRepository,
)
from app.repositories.sqlalchemy.sqlalchemy_meeting_repository import SqlAlchemyMeetingRepository
from app.repositories.sqlalchemy.sqlalchemy_outbox_repository import SqlAlchemyOutboxRepository
from app.repositories.sqlalchemy.sqlalchemy_summary_process_repository import (
    SqlAlchemySummaryProcessRepository,
)
from app.repositories.sqlalchemy.sqlalchemy_summary_template_repository import (
    SqlAlchemySummaryTemplateRepository,
)
from app.repositories.sqlalchemy.sqlalchemy_summary_version_repository import (
    SqlAlchemySummaryVersionRepository,
)
from app.repositories.sqlalchemy.sqlalchemy_transcript_repository import (
    SqlAlchemyTranscriptRepository,
)
from app.repositories.sqlalchemy.sqlalchemy_transcript_version_repository import (
    SqlAlchemyTranscriptVersionRepository,
)
from app.services.implementations.default_meeting_service import DefaultMeetingService
from app.services.implementations.default_notes_service import DefaultNotesService
from app.services.implementations.default_summary_service import DefaultSummaryService
from app.services.implementations.default_sync_service import DefaultSyncService
from app.services.implementations.default_template_service import DefaultTemplateService
from app.services.implementations.default_transcript_service import DefaultTranscriptService
from app.services.implementations.match_context_extractor import MatchContextExtractor
from app.services.implementations.meeting_ownership_guard import MeetingOwnershipGuard
from app.services.interfaces.meeting_service import MeetingService
from app.services.interfaces.notes_service import NotesService
from app.services.interfaces.summary_service import SummaryService
from app.services.interfaces.sync_service import SyncService
from app.services.interfaces.template_service import TemplateService
from app.services.interfaces.transcript_service import TranscriptService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# -- Repositories -------------------------------------------------------------------------


def provide_meeting_repository(session: SessionDep) -> MeetingRepository:
    return SqlAlchemyMeetingRepository(session)


def provide_transcript_repository(session: SessionDep) -> TranscriptRepository:
    return SqlAlchemyTranscriptRepository(session)


def provide_summary_process_repository(session: SessionDep) -> SummaryProcessRepository:
    return SqlAlchemySummaryProcessRepository(session)


def provide_meeting_notes_repository(session: SessionDep) -> MeetingNotesRepository:
    return SqlAlchemyMeetingNotesRepository(session)


def provide_summary_template_repository(session: SessionDep) -> SummaryTemplateRepository:
    return SqlAlchemySummaryTemplateRepository(session)


def provide_transcript_version_repository(session: SessionDep) -> TranscriptVersionRepository:
    return SqlAlchemyTranscriptVersionRepository(session)


def provide_summary_version_repository(session: SessionDep) -> SummaryVersionRepository:
    return SqlAlchemySummaryVersionRepository(session)


def provide_outbox_repository(session: SessionDep) -> OutboxRepository:
    return SqlAlchemyOutboxRepository(session)


MeetingRepositoryDep = Annotated[MeetingRepository, Depends(provide_meeting_repository)]


# -- Policy helpers -----------------------------------------------------------------------


def provide_ownership_guard(meeting_repository: MeetingRepositoryDep) -> MeetingOwnershipGuard:
    return MeetingOwnershipGuard(meeting_repository)


OwnershipGuardDep = Annotated[MeetingOwnershipGuard, Depends(provide_ownership_guard)]


# -- Services -----------------------------------------------------------------------------


def provide_meeting_service(
    meeting_repository: MeetingRepositoryDep,
    transcript_repository: Annotated[TranscriptRepository, Depends(provide_transcript_repository)],
    ownership_guard: OwnershipGuardDep,
) -> MeetingService:
    return DefaultMeetingService(meeting_repository, transcript_repository, ownership_guard)


def provide_transcript_service(
    transcript_repository: Annotated[TranscriptRepository, Depends(provide_transcript_repository)],
    version_repository: Annotated[
        TranscriptVersionRepository, Depends(provide_transcript_version_repository)
    ],
    ownership_guard: OwnershipGuardDep,
) -> TranscriptService:
    return DefaultTranscriptService(
        transcript_repository, version_repository, ownership_guard, MatchContextExtractor()
    )


def provide_summary_service(
    summary_process_repository: Annotated[
        SummaryProcessRepository, Depends(provide_summary_process_repository)
    ],
    version_repository: Annotated[
        SummaryVersionRepository, Depends(provide_summary_version_repository)
    ],
    ownership_guard: OwnershipGuardDep,
) -> SummaryService:
    return DefaultSummaryService(summary_process_repository, version_repository, ownership_guard)


def provide_notes_service(
    notes_repository: Annotated[MeetingNotesRepository, Depends(provide_meeting_notes_repository)],
    ownership_guard: OwnershipGuardDep,
) -> NotesService:
    return DefaultNotesService(notes_repository, ownership_guard)


def provide_template_service(
    template_repository: Annotated[
        SummaryTemplateRepository, Depends(provide_summary_template_repository)
    ],
) -> TemplateService:
    return DefaultTemplateService(template_repository)


def provide_sync_service(
    outbox_repository: Annotated[OutboxRepository, Depends(provide_outbox_repository)],
    meeting_repository: MeetingRepositoryDep,
) -> SyncService:
    return DefaultSyncService(outbox_repository, meeting_repository)


# -- Authentication -----------------------------------------------------------------------


def provide_token_validator() -> TokenValidator:
    """Exposes the app-lifetime validator as a dependency rather than a global lookup, so tests
    can substitute one without reaching past the header parsing and 401 handling below."""
    return get_token_validator()


async def provide_current_user(
    validator: Annotated[TokenValidator, Depends(provide_token_validator)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """The single entry point for identity, and how oid/tid reach the repository layer."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise InvalidTokenError("missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise InvalidTokenError("empty bearer token")
    return await validator.validate(token)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(provide_current_user)]
MeetingServiceDep = Annotated[MeetingService, Depends(provide_meeting_service)]
TranscriptServiceDep = Annotated[TranscriptService, Depends(provide_transcript_service)]
SummaryServiceDep = Annotated[SummaryService, Depends(provide_summary_service)]
NotesServiceDep = Annotated[NotesService, Depends(provide_notes_service)]
TemplateServiceDep = Annotated[TemplateService, Depends(provide_template_service)]
SyncServiceDep = Annotated[SyncService, Depends(provide_sync_service)]
