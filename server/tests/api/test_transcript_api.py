"""Transcript reads, pagination, and cross-meeting search over the full HTTP stack."""

from httpx import AsyncClient

AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}


def _segment(index: int, text: str) -> dict[str, object]:
    return {
        "id": f"t{index}",
        "transcript": text,
        "timestamp": f"00:00:{index:02d}",
        "audio_start_time": float(index),
        "audio_end_time": float(index) + 1.0,
        "duration": 1.0,
    }


async def test_a_meeting_can_be_created_with_its_transcript_in_one_request(
    client: AsyncClient,
) -> None:
    created = await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={
            "id": "m1",
            "title": "Standup",
            "segments": [_segment(0, "first thing"), _segment(1, "second thing")],
        },
    )
    assert created.status_code == 201

    transcript = await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_A)
    assert transcript.status_code == 200
    body = transcript.json()
    assert body["total"] == 2
    assert [s["transcript"] for s in body["segments"]] == ["first thing", "second thing"]


async def test_transcript_reads_paginate_while_total_stays_the_full_count(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={
            "id": "m1",
            "title": "Long",
            "segments": [_segment(i, f"line {i}") for i in range(5)],
        },
    )

    page = await client.get(
        "/api/v1/meetings/m1/transcript", headers=AUTH_A, params={"limit": 2, "offset": 2}
    )
    body = page.json()
    assert [s["transcript"] for s in body["segments"]] == ["line 2", "line 3"]
    assert body["total"] == 5


async def test_search_returns_context_around_the_match(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={
            "id": "m1",
            "title": "Planning",
            "segments": [_segment(0, "we should ship the migration next week")],
        },
    )

    found = await client.get(
        "/api/v1/transcripts/search", headers=AUTH_A, params={"query": "migration"}
    )
    assert found.status_code == 200
    hits = found.json()["hits"]
    assert len(hits) == 1
    assert hits[0]["meeting_id"] == "m1"
    assert hits[0]["meeting_title"] == "Planning"
    assert "migration" in hits[0]["match_context"]


async def test_search_never_crosses_owners(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Private", "segments": [_segment(0, "confidential salary")]},
    )

    assert (
        await client.get("/api/v1/transcripts/search", headers=AUTH_B, params={"query": "salary"})
    ).json() == {"hits": []}


async def test_replacing_a_transcript_archives_the_previous_one(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={"id": "m1", "title": "Retranscribed", "segments": [_segment(0, "original")]},
    )

    replaced = await client.put(
        "/api/v1/meetings/m1/transcript",
        headers=AUTH_A,
        json={"reason": "retranscribed with a larger model", "segments": [_segment(0, "improved")]},
    )
    assert replaced.status_code == 200
    assert [s["transcript"] for s in replaced.json()["segments"]] == ["improved"]

    versions = await client.get("/api/v1/meetings/m1/transcript/versions", headers=AUTH_A)
    assert [v["version"] for v in versions.json()] == [1]

    archived = await client.get("/api/v1/meetings/m1/transcript/versions/1", headers=AUTH_A)
    assert [s["transcript"] for s in archived.json()["segments_json"]] == ["original"]
