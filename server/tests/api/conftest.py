"""API-level wiring: real app, routers, DI graph, and Postgres. Only the token validator is
substituted, so header parsing and the 401 paths stay under test -- just not the JWKS call."""

import os
from collections.abc import AsyncGenerator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.current_user import AuthenticatedUser
from app.auth.entra_token_validator import TokenValidator
from app.auth.exceptions import InvalidTokenError
from app.db.session import get_db_session
from app.dependencies.providers import provide_token_validator
from app.domain.registry import Base
from app.main import create_app

ENV_URL = "MEETILY_TEST_DATABASE_URL"

USER_A = AuthenticatedUser(oid="oid-a", tenant_id="tenant-1", display_name="A", upn="a@x.test")
USER_B = AuthenticatedUser(oid="oid-b", tenant_id="tenant-1", display_name="B", upn="b@x.test")

# Opaque strings, not real JWTs: the fake validator maps them straight to identities.
TOKEN_FOR = {"token-a": USER_A, "token-b": USER_B}


class FakeTokenValidator(TokenValidator):
    async def validate(self, bearer_token: str) -> AuthenticatedUser:
        user = TOKEN_FOR.get(bearer_token)
        if user is None:
            raise InvalidTokenError("unknown test token")
        return user


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    preset = os.environ.get(ENV_URL)
    if preset:
        yield preset
        return
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed and no MEETILY_TEST_DATABASE_URL set")
    try:
        with PostgresContainer("postgres:18") as container:
            yield container.get_connection_url().replace("psycopg2", "asyncpg")
    except Exception as exc:  # noqa: BLE001  # pragma: no cover
        pytest.skip(f"could not start a Postgres container ({exc}); set {ENV_URL} instead")


@pytest.fixture
async def app(database_url: str) -> AsyncGenerator[FastAPI]:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncGenerator[AsyncSession]:
        # Mirrors the production per-request unit of work, against the test engine.
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app = create_app()
    fastapi_app.dependency_overrides[get_db_session] = override_session
    fastapi_app.dependency_overrides[provide_token_validator] = FakeTokenValidator

    yield fastapi_app

    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client
