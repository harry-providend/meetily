import os
from collections.abc import AsyncGenerator, Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.registry import Base
from tests.database_guard import require_disposable_database

# Real Postgres, never SQLite: JSONB, TIMESTAMPTZ, IDENTITY and CASCADE are what these tests
# check. Set MEETILY_TEST_DATABASE_URL to reuse a running instance, else testcontainers.
ENV_URL = "MEETILY_TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    preset = os.environ.get(ENV_URL)
    if preset:
        yield require_disposable_database(preset)
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed and no MEETILY_TEST_DATABASE_URL set")

    try:
        with PostgresContainer("postgres:18") as container:
            yield container.get_connection_url().replace("psycopg2", "asyncpg")
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        # Any startup failure (no daemon, no image, no network) should skip, not fail the suite.
        pytest.skip(f"could not start a Postgres container ({exc}); set {ENV_URL} instead")


@pytest.fixture
async def session(database_url: str) -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        # Drop first so each test starts from a known schema even if a previous run left rows.
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()
