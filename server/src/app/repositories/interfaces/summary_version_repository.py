from abc import ABC, abstractmethod

from app.domain.summary_version import SummaryVersionEntity


class SummaryVersionRepository(ABC):
    @abstractmethod
    async def find_all_for_meeting(self, meeting_id: str) -> list[SummaryVersionEntity]: ...

    @abstractmethod
    async def find_version_for_meeting(
        self, meeting_id: str, version: int
    ) -> SummaryVersionEntity | None: ...

    @abstractmethod
    async def next_version_for_meeting(self, meeting_id: str) -> int: ...

    @abstractmethod
    async def save(self, version: SummaryVersionEntity) -> SummaryVersionEntity: ...
