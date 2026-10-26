"""Optional tests use a throwaway database and roll back fixture data. Never use a production DB."""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.rag.retrieval import retrieve
from app.core.security import passwords
from app.models import Chunk, Document, EmbeddingModel, KnowledgeBase, User


@pytest.mark.integration
async def test_pgvector_filters_knowledge_space_and_dimensions(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a migrated disposable PostgreSQL database")
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            user = User(
                email=f"{uuid.uuid4()}@test.example", password_hash=passwords.hash("test password")
            )
            e3 = EmbeddingModel(name="test-3", kind="huggingface", dimensions=3, version="test")
            e4 = EmbeddingModel(name="test-4", kind="huggingface", dimensions=4, version="test")
            db.add_all([user, e3, e4])
            await db.flush()
            kb = KnowledgeBase(name="Authorized", owner_id=user.id, embedding_id=e3.id)
            other = KnowledgeBase(name="Other space", owner_id=user.id, embedding_id=e4.id)
            db.add_all([kb, other])
            await db.flush()
            for target, embedding, vector, text in [
                (kb, e3, [1, 0, 0], "Authorized policy"),
                (other, e4, [1, 0, 0, 0], "Must not retrieve"),
            ]:
                document = Document(
                    knowledge_base_id=target.id,
                    filename="policy.txt",
                    storage_key=str(uuid.uuid4()),
                    sha256=str(uuid.uuid4()),
                    size=100,
                    status="ready",
                )
                db.add(document)
                await db.flush()
                db.add(
                    Chunk(
                        document_id=document.id,
                        knowledge_base_id=target.id,
                        embedding_id=embedding.id,
                        generation=1,
                        content=text,
                        chunk_index=0,
                        embedding=vector,
                    )
                )
            await db.flush()
            adapter = AsyncMock()
            adapter.aembed_query.return_value = [1, 0, 0]
            monkeypatch.setattr(
                "app.ai.rag.retrieval.create_embeddings", AsyncMock(return_value=adapter)
            )
            sources = await retrieve(db, kb, "policy", 5, 0.5)
            assert len(sources) == 1 and sources[0]["excerpt"] == "Authorized policy"
            await db.rollback()
    finally:
        await engine.dispose()


@pytest.mark.ollama
async def test_real_ollama_embeddings():
    if os.environ.get("RUN_OLLAMA_TESTS") != "1":
        pytest.skip("Set RUN_OLLAMA_TESTS=1 after downloading nomic-embed-text")
    from langchain_ollama import OllamaEmbeddings

    adapter = OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434",
        client_kwargs={"timeout": 120, "trust_env": False},
    )
    vector = await adapter.aembed_query("Employees receive twenty days of annual leave.")
    assert len(vector) == 768 and any(vector)


@pytest.mark.ollama
async def test_real_ollama_chat_factory():
    if os.environ.get("RUN_OLLAMA_CHAT_TESTS") != "1":
        pytest.skip("Set RUN_OLLAMA_CHAT_TESTS=1 and OLLAMA_TEST_CHAT_MODEL to an installed model")
    import asyncio

    from app.ai.factory import create_chat_model
    from app.models import AIModel, Chatbot, Provider

    provider = Provider(kind="ollama", base_url="http://localhost:11434", is_local=True)
    model = AIModel(
        name=os.environ.get("OLLAMA_TEST_CHAT_MODEL", "llama3.2:3b"),
        capabilities={"temperature": True, "max_tokens": True},
    )
    bot = Chatbot(allow_cloud=False, timeout=120, temperature=0, max_tokens=16)
    adapter = create_chat_model(provider, model, bot)
    result = await asyncio.wait_for(adapter.ainvoke("Reply only with the word OK."), 125)
    assert result.content.strip()
