"""Restoring an archived transcript or summary. A restore must itself be undoable."""

from httpx import AsyncClient

AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}


def _segment(index: int, text: str) -> dict[str, object]:
    return {"id": f"t{index}", "transcript": text, "timestamp": f"00:00:{index:02d}"}


async def test_restoring_a_transcript_version_swaps_it_back_in(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Talk", "segments": [_segment(0, "original wording")]},
    )
    await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={"reason": "retranscription", "segments": [_segment(0, "revised wording")]},
    )

    restored = await client.post(
        "/api/v1/meetings/m1/transcript/versions/1/restore", headers=AUTH_A
    )
    assert restored.status_code == 200
    assert [s["transcript"] for s in restored.json()["segments"]] == ["original wording"]

    live = await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_A)
    assert [s["transcript"] for s in live.json()["segments"]] == ["original wording"]


async def test_a_restore_is_itself_undoable(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Talk", "segments": [_segment(0, "v0")]},
    )
    await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={"reason": "retranscription", "segments": [_segment(0, "v1")]},
    )
    await client.post("/api/v1/meetings/m1/transcript/versions/1/restore", headers=AUTH_A)

    # The restore archived what it displaced, so v1 is recoverable. Newest version first, as the
    # picker shows them.
    versions = (await client.get("/api/v1/meetings/m1/transcript/versions", headers=AUTH_A)).json()
    assert [(v["version"], v["reason"]) for v in versions] == [
        (2, "restore"),
        (1, "retranscription"),
    ]

    back = await client.post("/api/v1/meetings/m1/transcript/versions/2/restore", headers=AUTH_A)
    assert [s["transcript"] for s in back.json()["segments"]] == ["v1"]


async def test_restoring_a_missing_transcript_version_is_not_found(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Talk"})
    response = await client.post(
        "/api/v1/meetings/m1/transcript/versions/9/restore", headers=AUTH_A
    )
    assert response.status_code == 404


async def test_restoring_a_summary_version_swaps_it_back_in(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Talk"})
    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post(
        "/api/v1/meetings/m1/summary/generation/complete",
        headers=AUTH_A,
        json={"result": '{"markdown": "first"}'},
    )
    await client.post("/api/v1/meetings/m1/summary/generation", headers=AUTH_A)
    await client.post(
        "/api/v1/meetings/m1/summary/generation/complete",
        headers=AUTH_A,
        json={"result": '{"markdown": "second"}'},
    )

    restored = await client.post("/api/v1/meetings/m1/summary/versions/1/restore", headers=AUTH_A)
    assert restored.status_code == 200
    assert restored.json()["result"] == '{"markdown": "first"}'
    assert restored.json()["status"] == "completed"

    # And the second summary was archived on the way out.
    versions = (await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)).json()
    assert [(v["version"], v["reason"]) for v in versions] == [
        (2, "restore"),
        (1, "regeneration"),
    ]


async def test_another_user_cannot_restore(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Talk", "segments": [_segment(0, "private")]},
    )
    await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={"reason": "retranscription", "segments": [_segment(0, "private 2")]},
    )

    assert (
        await client.post("/api/v1/meetings/m1/transcript/versions/1/restore", headers=AUTH_B)
    ).status_code == 404
    assert (
        await client.post("/api/v1/meetings/m1/summary/versions/1/restore", headers=AUTH_B)
    ).status_code == 404
