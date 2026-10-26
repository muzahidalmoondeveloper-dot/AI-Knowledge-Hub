import uuid

from tests.conftest import sign_in


async def test_crud_prompts_ownership_and_provider_secrets(client, setup_workspace):
    w = setup_workspace
    headers, bot_id = w["headers"], w["bot"]["id"]
    providers = await client.get("/api/v1/providers", headers=headers)
    assert "super-secret-api-key" not in providers.text
    assert '"secret"' not in providers.text
    assert providers.json()[0]["has_secret"]
    prompt = await client.put(
        f"/api/v1/chatbots/{bot_id}/prompt",
        headers=headers,
        json={"content": "Answer in Bengali with concise quotations."},
    )
    assert prompt.status_code == 200
    versions = await client.get(f"/api/v1/chatbots/{bot_id}/prompts", headers=headers)
    assert len(versions.json()) == 2
    oldest = versions.json()[-1]
    assert (
        await client.post(
            f"/api/v1/chatbots/{bot_id}/prompts/{oldest['id']}/restore", headers=headers
        )
    ).status_code == 200
    assert (
        len((await client.get(f"/api/v1/chatbots/{bot_id}/prompts", headers=headers)).json()) == 3
    )
    conversation = (
        await client.post("/api/v1/conversations", headers=headers, json={"chatbot_id": bot_id})
    ).json()
    other = await sign_in(client, "other@example.com")
    for path in [
        f"/chatbots/{bot_id}",
        f"/chatbots/{bot_id}/prompts",
        f"/knowledge-bases/{w['kb']['id']}",
        f"/conversations/{conversation['id']}/messages",
    ]:
        assert (await client.get("/api/v1" + path, headers=other)).status_code == 404
    assert (
        await client.post("/api/v1/conversations", headers=other, json={"chatbot_id": bot_id})
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/providers",
            headers=other,
            json={"name": "x", "kind": "ollama", "base_url": "http://localhost:11434"},
        )
    ).status_code == 403
    assert (await client.delete(f"/api/v1/chatbots/{bot_id}", headers=other)).status_code == 404
    assert (
        await client.delete(f"/api/v1/conversations/{conversation['id']}", headers=headers)
    ).status_code == 204
    assert (await client.delete(f"/api/v1/chatbots/{bot_id}", headers=headers)).status_code == 204
    assert (await client.get(f"/api/v1/chatbots/{bot_id}", headers=headers)).status_code == 404


async def test_embedding_changes_require_reindex(client, setup_workspace):
    w = setup_workspace
    kb = w["kb"]
    data = {
        key: kb[key]
        for key in ["name", "embedding_id", "chunk_size", "chunk_overlap", "allow_cloud"]
    }
    data["chunk_size"] = 500
    assert (
        await client.put(f"/api/v1/knowledge-bases/{kb['id']}", headers=w["headers"], json=data)
    ).status_code == 409
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/reindex", headers=w["headers"], json=data
    )
    assert response.status_code == 202
    assert response.json()["generation"] == 2


async def test_cloud_requires_explicit_consent_and_local_cannot_spoof(client, setup_workspace):
    h = setup_workspace["headers"]
    cloud = (
        await client.post(
            "/api/v1/providers",
            headers=h,
            json={"name": "Cloud", "kind": "openai", "base_url": "https://api.openai.com/v1"},
        )
    ).json()
    model = (
        await client.post(
            "/api/v1/models", headers=h, json={"provider_id": cloud["id"], "name": "example-model"}
        )
    ).json()
    response = await client.post(
        "/api/v1/chatbots", headers=h, json={"name": "Private", "model_id": model["id"]}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "cloud_processing_disabled"
    spoof = await client.post(
        "/api/v1/providers",
        headers=h,
        json={
            "name": "Spoof",
            "kind": "openai",
            "base_url": "https://api.openai.com/v1",
            "is_local": True,
        },
    )
    assert spoof.status_code == 422
    unsafe = await client.post(
        "/api/v1/providers",
        headers=h,
        json={
            "name": "SSRF",
            "kind": "openai_compatible",
            "base_url": "http://169.254.169.254/latest",
        },
    )
    assert unsafe.status_code == 422
    assert (await client.get(f"/api/v1/chatbots/{uuid.uuid4()}", headers=h)).status_code == 404
