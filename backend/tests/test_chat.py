import asyncio
import json
from unittest.mock import AsyncMock

from app.ai.rag.grounding import UNAVAILABLE
from app.core.errors import AppError
from tests.conftest import sign_in


async def new_conversation(client, w):
    response = await client.post(
        "/api/v1/conversations", headers=w["headers"], json={"chatbot_id": w["bot"]["id"]}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_strict_empty_retrieval_stream_and_persistence(client, setup_workspace, monkeypatch):
    w = setup_workspace
    monkeypatch.setattr("app.services.chat.retrieve", AsyncMock(return_value=[]))
    cid = await new_conversation(client, w)
    response = await client.post(
        f"/api/v1/conversations/{cid}/stream",
        headers=w["headers"],
        json={"content": "What is the leave policy?"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")]
    assert [e["type"] for e in events] == ["start", "token", "done"]
    assert events[1]["text"] == UNAVAILABLE and events[-1]["sources"] == []
    messages = (
        await client.get(f"/api/v1/conversations/{cid}/messages", headers=w["headers"])
    ).json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user" and messages[1]["content"] == UNAVAILABLE
    assert messages[1]["status"] == "complete"
    conversations = (await client.get("/api/v1/conversations", headers=w["headers"])).json()
    assert conversations[0]["title"] == "What is the leave policy?"
    assert (await client.get("/api/v1/analytics", headers=w["headers"])).json()["responses"] == 1
    again = await client.post(
        f"/api/v1/conversations/{cid}/chat", headers=w["headers"], json={"content": "And weekends?"}
    )
    assert again.json()["content"] == UNAVAILABLE
    assert (
        len(
            (await client.get(f"/api/v1/conversations/{cid}/messages", headers=w["headers"])).json()
        )
        == 4
    )


async def test_stream_failure_never_marks_partial_success(client, setup_workspace, monkeypatch):
    from app.services.chat import ChatService

    source = {
        "source_id": "a",
        "document_id": "b",
        "title": "Policy",
        "page": 1,
        "excerpt": "The policy applies to all employees.",
        "score": 0.9,
    }
    monkeypatch.setattr("app.services.chat.retrieve", AsyncMock(return_value=[source]))

    async def broken(self, question, sources, writer):
        self.partial = "Partial response"
        writer({"type": "token", "text": "Partial response"})
        raise AppError(502, "provider_offline", "Provider unavailable")

    monkeypatch.setattr(ChatService, "generate", broken)
    cid = await new_conversation(client, setup_workspace)
    response = await client.post(
        f"/api/v1/conversations/{cid}/stream",
        headers=setup_workspace["headers"],
        json={"content": "Explain the policy"},
    )
    events = [json.loads(frame[6:]) for frame in response.text.strip().split("\n\n")]
    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in events)
    messages = (
        await client.get(
            f"/api/v1/conversations/{cid}/messages", headers=setup_workspace["headers"]
        )
    ).json()
    assert messages[-1]["content"] == "Partial response"
    assert messages[-1]["status"] in {"failed", "interrupted"}


async def test_chat_ownership_and_concurrent_generation_guard(client, setup_workspace, sessions):
    from datetime import timedelta
    from uuid import UUID

    from app.core.security import utcnow
    from app.models import Conversation

    cid = await new_conversation(client, setup_workspace)
    other = await sign_in(client, "intruder@example.com")
    assert (
        await client.post(
            f"/api/v1/conversations/{cid}/stream",
            headers=other,
            json={"content": "Steal private knowledge"},
        )
    ).status_code == 404
    async with sessions.begin() as db:
        conversation = await db.get(Conversation, UUID(cid))
        conversation.busy_until = utcnow() + timedelta(minutes=5)
    conflict = await client.post(
        f"/api/v1/conversations/{cid}/chat",
        headers=setup_workspace["headers"],
        json={"content": "Concurrent request"},
    )
    assert conflict.status_code == 409


async def test_model_stream_verifies_quotes_persists_sources_and_dynamic_prompt(
    client, setup_workspace, monkeypatch
):
    from langchain_core.messages import AIMessageChunk

    source = {
        "source_id": "chunk-policy",
        "document_id": "document-policy",
        "title": "policy.pdf",
        "page": 2,
        "excerpt": "Employees receive twenty days of annual leave.",
        "score": 0.94,
        "chunk_index": 0,
    }
    calls = []

    class Model:
        async def astream(self, messages):
            calls.append(messages)
            raw = json.dumps(
                {"quotes": [{"source_id": source["source_id"], "quote": source["excerpt"]}]}
            )
            yield AIMessageChunk(content=raw[:20])
            yield AIMessageChunk(
                content=raw[20:],
                usage_metadata={"input_tokens": 20, "output_tokens": 30, "total_tokens": 50},
            )

    monkeypatch.setattr("app.services.chat.retrieve", AsyncMock(return_value=[source]))
    monkeypatch.setattr("app.services.chat.create_chat_model", lambda *args: Model())
    w = setup_workspace
    await client.put(
        f"/api/v1/chatbots/{w['bot']['id']}/prompt",
        headers=w["headers"],
        json={"content": "Use a calm and clear tone."},
    )
    cid = await new_conversation(client, w)
    result = await client.post(
        f"/api/v1/conversations/{cid}/chat",
        headers=w["headers"],
        json={"content": "How much leave?"},
    )
    assert result.status_code == 200, result.text
    assert source["excerpt"] in result.json()["content"]
    assert result.json()["sources"][0]["page"] == 2
    assert any(message.content == "Use a calm and clear tone." for message in calls[0])
    messages = (
        await client.get(f"/api/v1/conversations/{cid}/messages", headers=w["headers"])
    ).json()
    assert messages[-1]["status"] == "complete"
    assert messages[-1]["sources"][0]["document_id"] == "document-policy"
    analytics = (await client.get("/api/v1/analytics", headers=w["headers"])).json()
    assert analytics["input_tokens"] == 20 and analytics["output_tokens"] == 30


async def test_general_model_fallback_before_tokens(client, setup_workspace, monkeypatch):

    from langchain_core.messages import AIMessageChunk

    # Configure fallback through the real API, preserving ownership and model validation.
    w = setup_workspace
    fallback = (
        await client.post(
            "/api/v1/models",
            headers=w["headers"],
            json={"provider_id": w["provider"]["id"], "name": "fallback-local"},
        )
    ).json()
    fields = [
        "name",
        "description",
        "model_id",
        "fallback_model_id",
        "knowledge_base_id",
        "enabled",
        "strict_rag",
        "allow_cloud",
        "streaming",
        "top_k",
        "score_threshold",
        "temperature",
        "max_tokens",
        "timeout",
    ]
    payload = {key: w["bot"][key] for key in fields}
    payload.update(strict_rag=False, fallback_model_id=fallback["id"])
    assert (
        await client.put(f"/api/v1/chatbots/{w['bot']['id']}", headers=w["headers"], json=payload)
    ).status_code == 200
    attempts = []

    class Model:
        def __init__(self, name):
            self.name = name

        async def astream(self, messages):
            attempts.append(self.name)
            if self.name != "fallback-local":
                raise ConnectionError("private provider diagnostic")
            yield AIMessageChunk(content="Hello from the fallback.")

    monkeypatch.setattr("app.services.chat.retrieve", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.services.chat.create_chat_model", lambda p, m, b: Model(m.name))
    cid = await new_conversation(client, w)
    result = await client.post(
        f"/api/v1/conversations/{cid}/chat", headers=w["headers"], json={"content": "Hello"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["content"] == "Hello from the fallback."
    assert attempts == [w["model"]["name"], "fallback-local"]


async def test_cancellation_marks_interrupted(monkeypatch):
    import uuid

    from langgraph.checkpoint.memory import InMemorySaver

    from app.api.chat import events

    class Service:
        user_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        run_id = uuid.uuid4()
        bot = type("Bot", (), {"strict_rag": False})()
        interrupt = AsyncMock()

        async def load_settings(self):
            pass

        async def load_history(self):
            pass

        def retrieval_query(self, q):
            return q

        async def retrieve(self, q):
            return []

        async def generate(self, *args):
            await asyncio.sleep(100)

        async def persist(self, *args):
            raise AssertionError("Cancelled generation must not persist")

    service = Service()
    generator = events(service, "question", InMemorySaver())
    assert (await anext(generator))["type"] == "start"
    import pytest

    task = asyncio.create_task(anext(generator))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    service.interrupt.assert_called_with("interrupted")
