import os

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ["JWT_SECRET_KEY"] = "test-only-random-secret-" + "a" * 40
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://unused:unused@localhost/test"

from app.db.session import get_db
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def sessions(tmp_path):
    # Relational/API tests use SQLite, but vector SQL is tested separately against PostgreSQL.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(sessions, monkeypatch):
    async def db_override():
        async with sessions() as db:
            try:
                yield db
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr("app.services.chat.Session", sessions)
    monkeypatch.setattr("app.workers.ingestion.Session", sessions)
    from langgraph.checkpoint.memory import InMemorySaver

    app.state.checkpointer = InMemorySaver()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def sign_in(client, email="admin@example.com"):
    data = {"email": email, "password": "correct horse battery staple"}
    registered = await client.post("/api/v1/auth/register", json=data)
    assert registered.status_code == 201, registered.text
    response = await client.post("/api/v1/auth/login", json=data)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def setup_workspace(client):
    headers = await sign_in(client)
    provider = await client.post(
        "/api/v1/providers",
        headers=headers,
        json={
            "name": "Local Ollama",
            "kind": "ollama",
            "base_url": "http://localhost:11434",
            "is_local": True,
            "api_key": "super-secret-api-key",
        },
    )
    assert provider.status_code == 201, provider.text
    provider_id = provider.json()["id"]
    model = await client.post(
        "/api/v1/models", headers=headers, json={"provider_id": provider_id, "name": "llama3:8b"}
    )
    assert model.status_code == 201, model.text
    embedding = await client.post(
        "/api/v1/embedding-models",
        headers=headers,
        json={
            "provider_id": provider_id,
            "name": "nomic-embed-text",
            "kind": "ollama",
            "dimensions": 3,
            "version": "test-v1",
        },
    )
    assert embedding.status_code == 201, embedding.text
    kb = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "Policies", "embedding_id": embedding.json()["id"]},
    )
    assert kb.status_code == 201, kb.text
    bot = await client.post(
        "/api/v1/chatbots",
        headers=headers,
        json={
            "name": "Policy assistant",
            "model_id": model.json()["id"],
            "knowledge_base_id": kb.json()["id"],
        },
    )
    assert bot.status_code == 201, bot.text
    return {
        "headers": headers,
        "provider": provider.json(),
        "model": model.json(),
        "embedding": embedding.json(),
        "kb": kb.json(),
        "bot": bot.json(),
    }
