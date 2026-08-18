from abc import ABC, abstractmethod

from app.domain.summary_template import SummaryTemplateEntity


class SummaryTemplateRepository(ABC):
    """Templates are either global (owner_tenant_id IS NULL) or tenant-authored. Reads return
    both for the caller's tenant; writes always carry a tenant so nobody can edit a builtin."""

    @abstractmethod
    async def find_all_visible_to_tenant(
        self, owner_tenant_id: str
    ) -> list[SummaryTemplateEntity]: ...

    @abstractmethod
    async def find_by_id_visible_to_tenant(
        self, template_id: str, owner_tenant_id: str
    ) -> SummaryTemplateEntity | None: ...

    @abstractmethod
    async def save(self, template: SummaryTemplateEntity) -> SummaryTemplateEntity: ...

    @abstractmethod
    async def delete_for_tenant(self, template_id: str, owner_tenant_id: str) -> bool: ...
