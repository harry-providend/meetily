from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.summary_template import SummaryTemplateEntity
from app.repositories.interfaces.summary_template_repository import SummaryTemplateRepository
from app.repositories.sqlalchemy.execution import execute_rowcount


class SqlAlchemySummaryTemplateRepository(SummaryTemplateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all_for_owner(
        self, owner_user_id: str, owner_tenant_id: str
    ) -> list[SummaryTemplateEntity]:
        stmt = (
            select(SummaryTemplateEntity)
            .where(
                SummaryTemplateEntity.owner_user_id == owner_user_id,
                SummaryTemplateEntity.owner_tenant_id == owner_tenant_id,
            )
            .order_by(
                SummaryTemplateEntity.is_builtin.desc(),
                SummaryTemplateEntity.name.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_id_for_owner(
        self, template_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> SummaryTemplateEntity | None:
        stmt = select(SummaryTemplateEntity).where(
            SummaryTemplateEntity.id == template_id,
            SummaryTemplateEntity.owner_user_id == owner_user_id,
            SummaryTemplateEntity.owner_tenant_id == owner_tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().one_or_none()

    async def save(self, template: SummaryTemplateEntity) -> SummaryTemplateEntity:
        merged = await self._session.merge(template)
        await self._session.flush()
        return merged

    async def delete_for_owner(
        self, template_id: str, owner_user_id: str, owner_tenant_id: str
    ) -> bool:
        stmt = delete(SummaryTemplateEntity).where(
            SummaryTemplateEntity.id == template_id,
            SummaryTemplateEntity.owner_user_id == owner_user_id,
            SummaryTemplateEntity.owner_tenant_id == owner_tenant_id,
        )
        return await execute_rowcount(self._session, stmt) > 0
