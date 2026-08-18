"""Every authenticated route must actually be authenticated. Walks the OpenAPI schema, so a new
route is covered without a new test."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

UNAUTHENTICATED_PATHS = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _authenticated_operations(app: FastAPI) -> list[tuple[str, str]]:
    operations: list[tuple[str, str]] = []
    for path, methods in app.openapi()["paths"].items():
        if path in UNAUTHENTICATED_PATHS:
            continue
        for method in methods:
            operations.append((method.upper(), path))
    return sorted(operations)


async def test_health_needs_no_token(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "header",
    [
        None,
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "token-a"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer wrong-token"},
    ],
    ids=["missing", "wrong-scheme", "no-scheme", "empty-token", "unknown-token"],
)
async def test_every_route_rejects_bad_credentials(
    app: FastAPI, client: AsyncClient, header: dict[str, str] | None
) -> None:
    for method, path in _authenticated_operations(app):
        url = path.replace("{meeting_id}", "m1").replace("{template_id}", "t1")
        url = url.replace("{version}", "1")
        response = await client.request(method, url, headers=header, json={})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


async def test_valid_token_reaches_the_handler(client: AsyncClient) -> None:
    response = await client.get("/api/v1/meetings", headers={"Authorization": "Bearer token-a"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
