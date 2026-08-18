from typing import cast

from sqlalchemy import CursorResult, Delete, Update
from sqlalchemy.ext.asyncio import AsyncSession


async def execute_rowcount(session: AsyncSession, statement: Delete | Update) -> int:
    """Runs DML and returns rows affected. execute() is typed Result[Any] with no rowcount;
    for DML the runtime object is always a CursorResult, hence the cast."""
    result = cast(CursorResult[tuple[()]], await session.execute(statement))
    await session.flush()
    return result.rowcount
