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


async def test_an_inverted_audio_window_is_rejected(client: AsyncClient) -> None:
    # The desktop app's VAD force-end path has produced these; no path may persist one.
    bad = {
        "id": "t0",
        "transcript": "SI or why you don't do this",
        "timestamp": "00:00:00",
        "audio_start_time": 78.93,
        "audio_end_time": 45.09,
        "duration": -33.84,
    }

    created = await client.post(
        "/api/v1/meetings", headers=AUTH_A, json={"id": "m1", "title": "Bad", "segments": [bad]}
    )
    assert created.status_code == 422
    assert "precedes" in created.text

    # And not through the replace path either.
    await client.post("/api/v1/meetings", headers=AUTH_A, json={"id": "m2", "title": "Bad"})
    replaced = await client.put(
        "/api/v1/meetings/m2/transcript",
        headers=AUTH_A,
        json={"reason": "retranscription", "segments": [bad]},
    )
    assert replaced.status_code == 422


async def test_duration_is_derived_not_trusted(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={
            "id": "m1",
            "title": "Timing",
            "segments": [
                {
                    "id": "t0",
                    "transcript": "hello",
                    "timestamp": "00:00:00",
                    "audio_start_time": 10.0,
                    "audio_end_time": 12.5,
                    # Wrong on purpose: it is redundant with the window, so the window wins.
                    "duration": 999.0,
                }
            ],
        },
    )

    segments = (await client.get("/api/v1/meetings/m1/transcript", headers=AUTH_A)).json()[
        "segments"
    ]
    assert segments[0]["duration"] == 2.5


async def test_a_zero_length_segment_is_allowed(client: AsyncClient) -> None:
    # Equal start and end is degenerate but not corrupt, and real VAD output contains them.
    created = await client.post(
        "/api/v1/meetings",
        headers=AUTH_A,
        json={
            "id": "m1",
            "title": "Zero",
            "segments": [
                {
                    "id": "t0",
                    "transcript": "hm",
                    "timestamp": "00:00:00",
                    "audio_start_time": 5.0,
                    "audio_end_time": 5.0,
                }
            ],
        },
    )
    assert created.status_code == 201
