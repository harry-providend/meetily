from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.providers import CurrentUserDep, SyncServiceDep
from app.schemas.sync_dto import SyncPullResponse, SyncPushRequest, SyncPushResponse

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/push")
async def push(
    current_user: CurrentUserDep,
    sync_service: SyncServiceDep,
    request: SyncPushRequest,
) -> SyncPushResponse:
    return await sync_service.push(current_user, request)


@router.get("/pull")
async def pull(
    current_user: CurrentUserDep,
    sync_service: SyncServiceDep,
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SyncPullResponse:
    return await sync_service.pull(current_user, since, limit)
