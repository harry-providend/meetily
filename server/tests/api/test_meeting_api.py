"""Full-stack meeting flows: HTTP -> router -> service -> repository -> Postgres. Catches a
mis-wired DI graph, an unserialisable DTO, or a wrong status code."""

from httpx import AsyncClient

AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}


async def test_create_then_read_back(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Standup", "folder_path": "/tmp/m1"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == "m1"
    assert body["title"] == "Standup"
    # Ownership is internal: it must not appear in the response body.
    assert "owner_user_id" not in body
    assert body["created_at"] is not None

    listed = await client.get("/api/v1/meetings", headers=AUTH_A)
    assert listed.status_code == 200
    assert [m["id"] for m in listed.json()["items"]] == ["m1"]


async def test_one_users_meeting_is_invisible_to_another(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Private"})

    listed = await client.get("/api/v1/meetings", headers=AUTH_B)
    assert listed.json() == {"items": [], "total": 0}

    # 404, not 403 -- B must not be able to tell that m1 exists.
    assert (await client.get("/api/v1/meetings/m1", headers=AUTH_B)).status_code == 404
    assert (
        await client.patch("/api/v1/meetings/m1", headers=AUTH_B, json={"title": "hijacked"})
    ).status_code == 404
    assert (await client.delete("/api/v1/meetings/m1", headers=AUTH_B)).status_code == 404

    still_there = await client.get("/api/v1/meetings/m1", headers=AUTH_A)
    assert still_there.json()["title"] == "Private"


async def test_delete_returns_no_content_and_removes_the_meeting(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Temp"})

    assert (await client.delete("/api/v1/meetings/m1", headers=AUTH_A)).status_code == 204
    assert (await client.get("/api/v1/meetings/m1", headers=AUTH_A)).status_code == 404


async def test_transcript_round_trip_preserves_segment_order(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Call"})

    # Ids deliberately out of alphabetical order: the response must follow submission order.
    put = await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={
            "reason": "initial",
            "segments": [
                {"id": "sC", "transcript": "third", "timestamp": "00:00:10"},
                {"id": "sA", "transcript": "first", "timestamp": "00:00:00"},
                {"id": "sB", "transcript": "second", "timestamp": "00:00:05"},
            ],
        },
    )
    assert put.status_code == 200
    assert [s["id"] for s in put.json()["segments"]] == ["sC", "sA", "sB"]

    fetched = await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_A)
    assert [s["transcript"] for s in fetched.json()["segments"]] == ["third", "first", "second"]


async def test_replacing_a_transcript_archives_the_previous_version(
    client: AsyncClient,
) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Call"})
    await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={
            "reason": "initial",
            "segments": [{"id": "s1", "transcript": "original", "timestamp": "0"}],
        },
    )
    await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={
            "reason": "retranscribed with a better model",
            "segments": [{"id": "s1", "transcript": "corrected", "timestamp": "0"}],
        },
    )

    versions = await client.get("/api/v1/meetings/m1/transcript/versions", headers=AUTH_A)
    assert versions.status_code == 200
    assert [v["version"] for v in versions.json()] == [1]
    assert versions.json()[0]["reason"] == "retranscribed with a better model"

    detail = await client.get("/api/v1/meetings/m1/transcript/versions/1", headers=AUTH_A)
    assert detail.json()["segments_json"][0]["transcript"] == "original"

    live = await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_A)
    assert live.json()["segments"][0]["transcript"] == "corrected"


async def test_transcript_of_another_users_meeting_is_not_found(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Private"})

    assert (await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_B)).status_code == 404
    assert (
        await client.put(
            "/api/v1/meetings/m1/transcript",
            headers=AUTH_B,
            json={"reason": "x", "segments": []},
        )
    ).status_code == 404


async def test_directly_authored_summary_round_trip(client: AsyncClient) -> None:
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Call"})

    summary = await client.put(
        "/api/v1/meetings/m1/summary",
        headers=AUTH_A,
        json={"status": "completed", "result": '{"summary":"all good"}', "chunk_count": 2},
    )
    assert summary.status_code == 200
    assert summary.json()["status"] == "completed"

    # Overwriting the summary should archive the previous result as version 1.
    await client.put(
        "/api/v1/meetings/m1/summary",
        headers=AUTH_A,
        json={"status": "completed", "result": '{"summary":"revised"}'},
    )
    versions = await client.get("/api/v1/meetings/m1/summary/versions", headers=AUTH_A)
    assert [v["version"] for v in versions.json()] == [1]
    assert versions.json()[0]["result_json"] == {"summary": "all good"}


async def test_pagination_bounds_are_enforced(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/meetings?page=0", headers=AUTH_A)).status_code == 422
    assert (await client.get("/api/v1/meetings?page_size=10000", headers=AUTH_A)).status_code == 422
