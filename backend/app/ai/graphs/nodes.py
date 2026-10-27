from langgraph.config import get_stream_writer


def build_nodes(service):
    """Execution services are ephemeral; credentials, ORM sessions and history never enter checkpoints."""

    async def load_settings(state):
        await service.load_settings()
        return {"status": "loading"}

    async def load_context(state):
        await service.load_history()
        return {}

    async def greeting(state):
        answer, sources = await service.generate(
            state["question"], [], get_stream_writer(), social=True
        )
        return {"answer": answer, "sources": sources}

    async def prepare_query(state):
        return {"query": service.retrieval_query(state["question"])}

    async def retrieve_knowledge(state):
        return {"sources": await service.retrieve(state["query"])}

    async def check_evidence(state):
        return {"evidence": bool(state["sources"]) or not service.bot.strict_rag}

    async def generate(state):
        writer = get_stream_writer()
        answer, sources = await service.generate(state["question"], state["sources"], writer)
        return {"answer": answer, "sources": sources}

    async def insufficient(state):
        from app.ai.rag.grounding import UNAVAILABLE

        get_stream_writer()({"type": "token", "text": UNAVAILABLE})
        return {"answer": UNAVAILABLE, "sources": []}

    async def prepare_sources(state):
        return {"sources": state["sources"], "status": "generated"}

    async def persist(state):
        message_id = await service.persist(state["answer"], state["sources"])
        return {"message_id": str(message_id), "status": "complete"}

    return {
        "load_settings": load_settings,
        "load_context": load_context,
        "greeting": greeting,
        "prepare_query": prepare_query,
        "retrieve": retrieve_knowledge,
        "check_evidence": check_evidence,
        "generate": generate,
        "insufficient": insufficient,
        "prepare_sources": prepare_sources,
        "persist": persist,
    }
