import asyncio
import json
from contextlib import aclosing
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.ai.graphs.workflow import build_graph
from app.api.deps import CurrentUser, Db
from app.core.errors import AppError
from app.schemas.requests import ChatInput
from app.services.chat import begin_chat

router = APIRouter(tags=["Chat"])


def sse(event: dict) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


async def events(service, question, checkpointer):
    graph = build_graph(service, checkpointer)
    config = {"configurable": {"thread_id": f"{service.user_id}:{service.conversation_id}"}}
    initial = {
        "conversation_id": str(service.conversation_id),
        "question": question,
        "answer": "",
        "sources": [],
        "message_id": "",
        "status": "starting",
        "evidence": False,
        "query": "",
    }
    completed = False
    try:
        yield {"type": "start", "message_id": str(service.run_id)}
        # Custom events stream validated strict extracts or general-mode model chunks.
        async for mode, item in graph.astream(initial, config, stream_mode=["custom", "updates"]):
            if mode == "custom":
                yield item
            elif "persist" in item:
                completed = True
        if completed:
            # The canonical message is already committed; read sources from the final graph state.
            snapshot = await graph.aget_state(config)
            yield {
                "type": "done",
                "message_id": str(service.run_id),
                "sources": snapshot.values.get("sources", []),
                "status": "complete",
            }
    except asyncio.CancelledError:
        await asyncio.shield(service.interrupt("interrupted"))
        raise
    except Exception as error:
        await service.interrupt()
        yield {
            "type": "error",
            "code": error.code if isinstance(error, AppError) else "generation_failed",
            "message": error.message
            if isinstance(error, AppError)
            else "Unable to complete this response",
            "status": "failed",
        }
    finally:
        if not completed:
            await asyncio.shield(service.interrupt("interrupted"))


@router.post("/conversations/{conversation_id}/stream")
async def stream(
    conversation_id: UUID, data: ChatInput, db: Db, user: CurrentUser, request: Request
):
    service = await begin_chat(db, user, conversation_id, data.content)

    async def body():
        async with aclosing(
            events(service, data.content, request.app.state.checkpointer)
        ) as stream:
            async for event in stream:
                if await request.is_disconnected():
                    await service.interrupt("interrupted")
                    break
                yield sse(event)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/chat")
async def chat(conversation_id: UUID, data: ChatInput, db: Db, user: CurrentUser, request: Request):
    service = await begin_chat(db, user, conversation_id, data.content)
    text, final = "", {}
    async for event in events(service, data.content, request.app.state.checkpointer):
        if event["type"] == "token":
            text += event["text"]
        elif event["type"] == "error":
            raise AppError(502, event["code"], event["message"])
        else:
            final = event
    return {"content": text, **final}
