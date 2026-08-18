from abc import ABC, abstractmethod

from app.domain.summary_process import SummaryProcessEntity


class SummaryProcessRepository(ABC):
    @abstractmethod
    async def find_for_meeting(self, meeting_id: str) -> SummaryProcessEntity | None: ...

    @abstractmethod
    async def save(self, summary_process: SummaryProcessEntity) -> SummaryProcessEntity: ...

    @abstractmethod
    async def delete_for_meeting(self, meeting_id: str) -> bool: ...
