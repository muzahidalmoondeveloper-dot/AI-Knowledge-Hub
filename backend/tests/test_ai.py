import json
import uuid

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.ai.factory import create_chat_model, enforce_privacy
from app.ai.graphs.workflow import build_graph
from app.ai.rag.grounding import UNAVAILABLE, verify_extracts
from app.ai.rag.retrieval import validate_vector
from app.core.errors import AppError
from app.core.security import encrypt, validate_provider_url
from app.models import AIModel, Chatbot, Provider

SOURCE = {
    "source_id": "chunk-a",
    "document_id": "doc-a",
    "title": "Policy",
    "page": 2,
    "excerpt": "Employees receive twenty days of paid leave each year.",
    "score": 0.9,
}


@pytest.mark.parametrize(
    "kind,url",
    [
        ("ollama", "http://localhost:11434"),
        ("openai", "https://api.openai.com/v1"),
        ("anthropic", "https://api.anthropic.com"),
        ("google", "https://generativelanguage.googleapis.com"),
        ("groq", "https://api.groq.com/openai/v1"),
        ("lmstudio", "http://localhost:1234/v1"),
        ("vllm", "http://localhost:8001/v1"),
        ("openai_compatible", "http://localhost:1234/v1"),
    ],
)
def test_provider_factory_constructs_supported_adapters(kind, url):
    provider = Provider(
        kind=kind,
        base_url=url,
        secret=encrypt("test-key"),
        is_local=kind in {"ollama", "lmstudio", "vllm", "openai_compatible"},
    )
    model = AIModel(
        name="test-model",
        capabilities={"temperature": False, "max_tokens": True, "streaming": True},
    )
    bot = Chatbot(allow_cloud=True, temperature=0.1, max_tokens=100, timeout=20)
    adapter = create_chat_model(provider, model, bot)
    assert adapter is not None


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest",
        "http://localhost:22",
        "https://api.openai.com.evil.test",
        "https://key@api.openai.com/v1",
        "https://api.openai.com/v1?key=secret",
        "http://localhost:11434/../api",
    ],
)
def test_ssrf_origin_validation(url):
    with pytest.raises(AppError):
        validate_provider_url(url)


def test_privacy_and_vector_dimensions():
    with pytest.raises(AppError, match="Explicitly allow"):
        enforce_privacy(Provider(is_local=False), False)
    for vector in [[1, 2], [0, 0, 0], [1, float("nan"), 2], [1, float("inf"), 2]]:
        with pytest.raises(AppError):
            validate_vector(vector, 3)
    validate_vector([1, 0, 0], 3)


@pytest.mark.parametrize(
    "raw",
    [
        json.dumps(
            {"quotes": [{"source_id": "invented", "quote": "Employees receive twenty days"}]}
        ),
        json.dumps({"quotes": [{"source_id": "chunk-a", "quote": "Employees receive fifty days"}]}),
        '{"quotes":[]}',
        "not json",
        '{"quotes": "bad"}',
    ],
)
def test_strict_rag_rejects_unsupported_evidence(raw):
    assert verify_extracts(raw, [SOURCE]) == (UNAVAILABLE, [])


def test_strict_rag_preserves_verbatim_source():
    text, sources = verify_extracts(
        json.dumps({"quotes": [{"source_id": "chunk-a", "quote": SOURCE["excerpt"]}]}), [SOURCE]
    )
    assert SOURCE["excerpt"] in text and sources[0]["page"] == 2
    assert sources[0]["document_id"] == "doc-a"


class FakeService:
    def __init__(self, strict=True, sources=None):
        self.bot = Chatbot(strict_rag=strict)
        self.sources = sources or []
        self.generated = False
        self.saved = None

    async def load_settings(self):
        pass

    async def load_history(self):
        pass

    def retrieval_query(self, q):
        return q

    async def retrieve(self, q):
        return self.sources

    async def generate(self, q, sources, writer):
        self.generated = True
        writer({"type": "token", "text": "Grounded answer"})
        return "Grounded answer", sources

    async def persist(self, text, sources):
        self.saved = (text, sources)
        return uuid.uuid4()


async def test_langgraph_insufficient_evidence_short_circuits_llm_and_checkpoints():
    service = FakeService()
    graph = build_graph(service, InMemorySaver())
    config = {"configurable": {"thread_id": "owner:conversation"}}
    state = await graph.ainvoke({"question": "How much leave?", "sources": []}, config)
    assert not service.generated
    assert state["answer"] == UNAVAILABLE and state["status"] == "complete"
    assert service.saved == (UNAVAILABLE, [])
    assert (await graph.aget_state(config)).values["status"] == "complete"


async def test_langgraph_routes_generation_and_custom_stream():
    service = FakeService(sources=[SOURCE])
    graph = build_graph(service, InMemorySaver())
    chunks = [
        event
        async for event in graph.astream(
            {"question": "Policy?"},
            {"configurable": {"thread_id": "owner:conversation"}},
            stream_mode="custom",
        )
    ]
    assert chunks == [{"type": "token", "text": "Grounded answer"}]
    assert service.generated and service.saved[1][0]["document_id"] == "doc-a"


async def test_general_mode_works_without_retrieval():
    service = FakeService(strict=False)
    state = await build_graph(service, InMemorySaver()).ainvoke(
        {"question": "Hello"}, {"configurable": {"thread_id": "owner:new"}}
    )
    assert service.generated and state["answer"] == "Grounded answer"
