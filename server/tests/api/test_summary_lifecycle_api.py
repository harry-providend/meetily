"""The generation run: start -> complete | fail | cancel, and what each does to the stashed result.

The rollback behaviour is the point of these tests. A failed or cancelled run must leave both the
previous summary and the version history untouched, and only a successful one may add a version.
"""

from httpx import AsyncClient

AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}

FIRST = '{"markdown": "first summary"}'
SECOND = '{"markdown": "second summary"}'


async def _meeting_with_summary(client: AsyncClient, result: str = FIRST) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Standup"})
    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post(
        "/api/v1/meetings/m1/summary/generation/complete",
        headers=AUTH_A,
        json={"result": result, "chunk_count": 3, "processing_time": 1.5},
    )


async def test_a_first_run_completes_without_creating_a_version(client: AsyncClient) -> None:
    await _meeting_with_summary(client)

    summary = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    assert summary["status"] == "completed"
    assert summary["result"] == FIRST
    assert summary["chunk_count"] == 3

    # Nothing was replaced, so there is nothing to archive.
    versions = await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)
    assert versions.json() == []


async def test_regenerating_archives_the_summary_it_replaced(client: AsyncClient) -> None:
    await _meeting_with_summary(client)

    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post(
        "/api/v1/meetings/m1/summary/generation/complete",
        headers=AUTH_A,
        json={"result": SECOND},
    )

    current = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    assert current["result"] == SECOND

    versions = (await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)).json()
    assert [v["version"] for v in versions] == [1]
    assert versions[0]["reason"] == "regeneration"

    archived = await client.get("/api/v1/meetings/m1/summary/versions/1", headers=AUTH_A)
    assert archived.json()["result_json"] == {"markdown": "first summary"}


async def test_a_failed_regeneration_restores_the_previous_summary(client: AsyncClient) -> None:
    await _meeting_with_summary(client)

    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    failed = await client.post(
        "/api/v1/meetings/m1/summary/generation/fail",
        headers=AUTH_A,
        json={"error": "provider timed out"},
    )
    assert failed.status_code == 200

    summary = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    assert summary["status"] == "failed"
    assert summary["error"] == "provider timed out"
    # The summary the user already had must survive a failed attempt to replace it.
    assert summary["result"] == FIRST

    # And a run that never produced anything must not leave a version behind.
    assert (await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)).json() == []


async def test_a_cancelled_regeneration_restores_the_previous_summary(client: AsyncClient) -> None:
    await _meeting_with_summary(client)

    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post("/api/v1/meetings/m1/summary/generation/cancel", headers=AUTH_A)

    summary = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    assert summary["status"] == "cancelled"
    assert summary["result"] == FIRST
    assert "cancelled" in summary["error"].lower()
    assert (await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)).json() == []


async def test_a_failed_first_run_leaves_no_summary_rather_than_inventing_one(
    client: AsyncClient,
) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Standup"})
    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post(
        "/api/v1/meetings/m1/summary/generation/fail",
        headers=AUTH_A,
        json={"error": "no api key configured"},
    )

    summary = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    assert summary["status"] == "failed"
    assert summary["result"] is None


async def test_rollback_state_is_never_exposed(client: AsyncClient) -> None:
    await _meeting_with_summary(client)
    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)

    body = (await client.get("/api/v1/meetings/m1/summary", headers=AUTH_A)).json()
    # Server-side rollback state: a client that could read or set it could corrupt the rollback.
    assert "result_backup" not in body
    assert "result_backup_timestamp" not in body


async def test_completing_a_run_that_was_never_started_is_not_found(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Standup"})

    completing = await client.post(
        "/api/v1/meetings/m1/summary/generation/complete",
        headers=AUTH_A,
        json={"result": FIRST},
    )
    assert completing.status_code == 404


async def test_another_user_cannot_drive_the_generation(client: AsyncClient) -> None:
    await _meeting_with_summary(client)

    for path, body in [
        ("/api/v1/meetings/m1/summary/generation", None),
        ("/api/v1/meetings/m1/summary/generation/complete", {"result": SECOND}),
        ("/api/v1/meetings/m1/summary/generation/fail", {"error": "x"}),
        ("/api/v1/meetings/m1/summary/generation/cancel", None),
    ]:
        response = await client.post(path, headers=AUTH_B, json=body)
        assert response.status_code == 404, path
