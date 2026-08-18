"""Templates, and the rule that seeding must never overwrite a user's edit."""

from httpx import AsyncClient

AUTH_A = {"Authorization": "Bearer token-a"}
AUTH_B = {"Authorization": "Bearer token-b"}

SHIPPED = {
    "templates": [
        {
            "id": "daily_standup",
            "name": "Daily Standup",
            "description": "Shipped with the app",
            "sections_json": {"blockers": {"title": "Blockers"}},
        }
    ]
}


async def test_seeding_writes_shipped_templates(client: AsyncClient) -> None:
    seeded = await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    assert seeded.status_code == 200
    assert seeded.json() == {"written": 1, "skipped_user_modified": 0}

    listed = (await client.get("/api/v1/templates", headers=AUTH_A)).json()["items"]
    assert [t["id"] for t in listed] == ["daily_standup"]
    assert listed[0]["is_builtin"] is True
    assert listed[0]["user_modified"] is False


async def test_reseeding_updates_an_untouched_builtin(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)

    updated = {"templates": [{**SHIPPED["templates"][0], "name": "Daily Standup v2"}]}
    again = await client.post("/api/v1/templates/seed", headers=AUTH_A, json=updated)
    assert again.json() == {"written": 1, "skipped_user_modified": 0}

    template = (await client.get("/api/v1/templates/daily_standup", headers=AUTH_A)).json()
    assert template["name"] == "Daily Standup v2"


async def test_seeding_never_overwrites_a_user_edit(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    await client.put(
        "/api/v1/templates",
        headers=AUTH_A,
        json={
            "id": "daily_standup",
            "name": "My Standup",
            "description": "mine",
            "sections_json": {"mine": {"title": "Mine"}},
        },
    )

    again = await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    assert again.json() == {"written": 0, "skipped_user_modified": 1}

    template = (await client.get("/api/v1/templates/daily_standup", headers=AUTH_A)).json()
    assert template["name"] == "My Standup"
    # Still shipped, so it can be reset later, but now flagged as edited.
    assert template["is_builtin"] is True
    assert template["user_modified"] is True


async def test_resetting_makes_a_builtin_eligible_for_seeding_again(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    await client.put(
        "/api/v1/templates",
        headers=AUTH_A,
        json={"id": "daily_standup", "name": "My Standup", "sections_json": {}},
    )

    reset = await client.post("/api/v1/templates/daily_standup/reset", headers=AUTH_A)
    assert reset.status_code == 200
    assert reset.json()["user_modified"] is False

    # The content itself returns on the next seed, because the app holds the shipped definitions.
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    template = (await client.get("/api/v1/templates/daily_standup", headers=AUTH_A)).json()
    assert template["name"] == "Daily Standup"


async def test_a_builtin_cannot_be_deleted(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)

    refused = await client.delete("/api/v1/templates/daily_standup", headers=AUTH_A)
    assert refused.status_code == 409
    assert "reset" in refused.json()["detail"].lower()


async def test_a_user_template_can_be_deleted_but_not_reset(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/templates",
        headers=AUTH_A,
        json={"id": "my_own", "name": "My Own", "sections_json": {}},
    )

    assert (await client.post("/api/v1/templates/my_own/reset", headers=AUTH_A)).status_code == 409
    assert (await client.delete("/api/v1/templates/my_own", headers=AUTH_A)).status_code == 204
    assert (await client.get("/api/v1/templates/my_own", headers=AUTH_A)).status_code == 404


async def test_importing_never_overwrites_an_existing_id(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)

    imported = await client.post(
        "/api/v1/templates/import",
        headers=AUTH_A,
        json={
            "templates": [
                {"id": "daily_standup", "name": "Legacy Clash", "sections_json": {}},
                {"id": "legacy_one", "name": "Legacy One", "sections_json": {}},
            ]
        },
    )
    assert imported.json() == {"imported": ["legacy_one"], "already_present": ["daily_standup"]}

    template = (await client.get("/api/v1/templates/daily_standup", headers=AUTH_A)).json()
    assert template["name"] == "Daily Standup"


async def test_builtins_sort_above_user_templates(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    # A name that would sort first alphabetically, to prove is_builtin dominates.
    await client.put(
        "/api/v1/templates",
        headers=AUTH_A,
        json={"id": "aaa", "name": "AAA Mine", "sections_json": {}},
    )

    listed = (await client.get("/api/v1/templates", headers=AUTH_A)).json()["items"]
    assert [t["id"] for t in listed] == ["daily_standup", "aaa"]


async def test_templates_are_per_user(client: AsyncClient) -> None:
    await client.post("/api/v1/templates/seed", headers=AUTH_A, json=SHIPPED)
    await client.put(
        "/api/v1/templates",
        headers=AUTH_A,
        json={"id": "mine", "name": "Mine", "sections_json": {}},
    )

    assert (await client.get("/api/v1/templates", headers=AUTH_B)).json() == {"items": []}
    assert (await client.get("/api/v1/templates/mine", headers=AUTH_B)).status_code == 404
    assert (await client.delete("/api/v1/templates/mine", headers=AUTH_B)).status_code == 404
