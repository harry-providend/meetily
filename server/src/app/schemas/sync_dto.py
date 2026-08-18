from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, JsonValue


class AggregateType(StrEnum):
    MEETING = "meeting"
    TRANSCRIPT = "transcript"
    SUMMARY_PROCESS = "summary_process"
    MEETING_NOTES = "meeting_notes"


class SyncOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class SyncPushItem(BaseModel):
    client_entry_id: str = Field(min_length=1)
    aggregate_type: AggregateType
    aggregate_id: str = Field(min_length=1)
    operation: SyncOperation
    payload: dict[str, JsonValue]
    client_updated_at: datetime


class SyncPushRequest(BaseModel):
    items: list[SyncPushItem]


class SyncItemStatus(StrEnum):
    APPLIED = "applied"
    # Server's copy is newer, so the client should drop its outbox row: a retry can never win.
    SKIPPED_STALE = "skipped_stale"
    # Already applied on an earlier attempt; a retry after a dropped connection.
    DUPLICATE = "duplicate"


class SyncPushItemResult(BaseModel):
    client_entry_id: str
    status: SyncItemStatus


class SyncPushResponse(BaseModel):
    results: list[SyncPushItemResult]


class SyncPullItem(BaseModel):
    aggregate_type: str
    aggregate_id: str
    operation: str
    payload: dict[str, JsonValue]
    server_received_at: datetime


class SyncPullResponse(BaseModel):
    items: list[SyncPullItem]
    # Feed back as `since` on the next pull. None when nothing was returned.
    next_cursor: datetime | None
