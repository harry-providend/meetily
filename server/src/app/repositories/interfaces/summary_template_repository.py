from abc import ABC, abstractmethod

from app.domain.summary_template import SummaryTemplateEntity


class SummaryTemplateRepository(ABC):
    """Owned per user, like meetings: every method takes the owner, and there is no unfiltered
    read. Builtin-ness is a property of the row, not of who can see it."""

    @abstractmethod
    async def find_all_for_owner(
        self, owner_user_id: str, owner_tenant_id: str
    ) -> list[SummaryTemplateEntity]:
        """Builtins first, then by name, so the shipped defaults stay at the top of the picker."""

    @abstractmethod
    async def find_by_id_for_owner(
        self, template_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> SummaryTemplateEntity | None: ...

    @abstractmethod
    async def save(self, template: SummaryTemplateEntity) -> SummaryTemplateEntity: ...

    @abstractmethod
    async def delete_for_owner(
        self, template_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> bool: ...
