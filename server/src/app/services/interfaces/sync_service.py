from abc import ABC, abstractmethod
from datetime import datetime

from app.auth.current_user import AuthenticatedUser
from app.schemas.sync_dto import SyncPullResponse, SyncPushRequest, SyncPushResponse


class SyncService(ABC):
    @abstractmethod
    async def push(
        self, current_user: AuthenticatedUser, request: SyncPushRequest
    ) -> SyncPushResponse: ...

    @abstractmethod
    async def pull(
        self, current_user: AuthenticatedUser, since: datetime | None, limit: int
    ) -> SyncPullResponse: ...
