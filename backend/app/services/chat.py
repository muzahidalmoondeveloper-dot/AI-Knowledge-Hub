import asyncio
import json
import time
import uuid
from datetime import timedelta, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select

from app.ai.factory import create_chat_model, enforce_privacy, provider_for
from app.ai.rag.grounding import SECURITY, STRICT, verify_extracts
from app.ai.rag.retrieval import retrieve
from app.api.deps import owned
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.db.session import Session
from app.models import AIModel, Chatbot, Conversation, KnowledgeBase, Message, UsageLog, User


async def begin_chat(db, user: User, conversation_id, question: str):
    conversation = await owned(db, Conversation, conversation_id, user, lock=True)
    bot = await owned(db, Chatbot, conversation.chatbot_id, user)
    if not bot.enabled:
        raise AppError(409, "bot_disabled", "This chatbot is disabled")
    until = conversation.busy_until
    if until and (until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until) > utcnow():
        raise AppError(409, "conversation_busy", "A response is already being generated")
    # Recover abandoned response records when a previous API process died.
    pending = (
        await db.scalars(
            select(Message).where(
                Message.conversation_id == conversation_id, Message.status == "generating"
            )
        )
    ).all()
    for message in pending:
        message.status = "interrupted"
    run_id = uuid.uuid4()
    conversation.run_token = run_id
    conversation.busy_until = utcnow() + timedelta(seconds=bot.timeout * 2 + 120)
    conversation.updated_at = utcnow()
    if conversation.title == "New conversation":
        conversation.title = question[:100]
    db.add(Message(conversation_id=conversation_id, role="user", content=question))
    assistant = Message(
        id=run_id,
        conversation_id=conversation_id,
        role="assistant",
        content="",
        status="generating",
    )
    db.add(assistant)
    await db.commit()
    return ChatService(user.id, conversation_id, bot.id, run_id)


class ChatService:
    def __init__(self, user_id, conversation_id, bot_id, run_id):
        self.user_id, self.conversation_id, self.bot_id, self.run_id = (
            user_id,
            conversation_id,
            bot_id,
            run_id,
        )
        self.bot = None
        self.history = []
        self.partial = ""
        self.usage = {}
        self.model_id = None
        self.started = time.monotonic()

    async def load_settings(self):
        async with Session() as db:
            self.bot = await db.get(Chatbot, self.bot_id)
            if not self.bot or self.bot.owner_id != self.user_id or not self.bot.enabled:
                raise AppError(404, "bot_unavailable", "Chatbot is unavailable")

    async def load_history(self):
        settings = get_settings()
        async with Session() as db:
            rows = (
                await db.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == self.conversation_id,
                        Message.status == "complete",
                    )
                    .order_by(Message.created_at.desc())
                    .limit(settings.history_messages)
                )
            ).all()
        total = 0
        recent = []
        for row in rows:
            if total + len(row.content) > settings.history_characters:
                break
            total += len(row.content)
            recent.append(row)
        self.history = list(reversed(recent))

    def retrieval_query(self, question):
        # Follow-up questions benefit from the previous user question, within a bounded window.
        previous = [m.content for m in self.history if m.role == "user" and m.content != question]
        return (previous[-1][:1000] + "\n" if previous else "") + question

    async def retrieve(self, query):
        if not self.bot.knowledge_base_id:
            return []
        async with Session() as db:
            kb = await db.get(KnowledgeBase, self.bot.knowledge_base_id)
            if not kb or kb.owner_id != self.user_id:
                raise AppError(404, "knowledge_unavailable", "Knowledge base is unavailable")
            if self.bot.allow_cloud and not kb.allow_cloud:
                raise AppError(
                    422, "knowledge_privacy", "Knowledge base cloud processing is disabled"
                )
            return await retrieve(
                db, kb, query, self.bot.top_k, self.bot.score_threshold, self.bot.allow_cloud
            )

    async def generate(self, question, sources, writer):
        messages = [SystemMessage(content=SECURITY), SystemMessage(content=self.bot.system_prompt)]
        if self.bot.strict_rag:
            messages.append(SystemMessage(content=STRICT))
        else:
            messages.append(
                SystemMessage(
                    content="General mode is enabled. Distinguish general knowledge from supplied evidence. Do not invent citations. Sources are displayed separately by the application."
                )
            )
        for row in self.history[:-1]:
            messages.append(
                HumanMessage(content=row.content)
                if row.role == "user"
                else AIMessage(content=row.content)
            )
        messages.append(
            HumanMessage(
                content="UNTRUSTED RETRIEVED EVIDENCE (JSON data):\n"
                + json.dumps(sources, ensure_ascii=False)
            )
        )
        messages.append(HumanMessage(content=question))
        raw = ""
        candidates = [self.bot.model_id] + (
            [self.bot.fallback_model_id] if self.bot.fallback_model_id else []
        )
        for i, model_id in enumerate(candidates):
            async with Session() as db:
                definition = await db.get(AIModel, model_id)
                provider = await provider_for(db, definition.provider_id)
                enforce_privacy(provider, self.bot.allow_cloud)
                adapter = create_chat_model(provider, definition, self.bot)
                self.model_id = model_id
            try:
                async with asyncio.timeout(self.bot.timeout):
                    if self.bot.streaming and definition.capabilities.get("streaming", False):
                        async for chunk in adapter.astream(messages):
                            text = (
                                chunk.content
                                if isinstance(chunk.content, str)
                                else "".join(
                                    block.get("text", "")
                                    for block in chunk.content
                                    if isinstance(block, dict)
                                )
                            )
                            raw += text
                            if getattr(chunk, "usage_metadata", None):
                                self.usage = chunk.usage_metadata
                            if not self.bot.strict_rag and text:
                                self.partial += text
                                writer({"type": "token", "text": text})
                    else:
                        result = await adapter.ainvoke(messages)
                        raw = (
                            result.content
                            if isinstance(result.content, str)
                            else "".join(
                                b.get("text", "") for b in result.content if isinstance(b, dict)
                            )
                        )
                        self.usage = result.usage_metadata or {}
                break
            except Exception:
                # Never repeat a partial streamed answer using a different model.
                if i + 1 == len(candidates) or self.partial:
                    raise AppError(
                        502,
                        "generation_failed",
                        "Model generation failed or timed out. Check provider availability.",
                    ) from None
                raw = ""
        if self.bot.strict_rag:
            answer, sources = verify_extracts(raw, sources)
            self.partial = answer
            for start in range(0, len(answer), 80):
                writer({"type": "token", "text": answer[start : start + 80]})
                await asyncio.sleep(0)
        else:
            answer = raw
            if not self.partial:
                self.partial = answer
                writer({"type": "token", "text": answer})
        if not answer.strip():
            raise AppError(502, "empty_generation", "The model returned an empty response")
        return answer, sources

    async def persist(self, answer, sources):
        async with Session.begin() as db:
            conversation = await db.scalar(
                select(Conversation)
                .where(Conversation.id == self.conversation_id)
                .with_for_update()
            )
            if not conversation or conversation.run_token != self.run_id:
                raise AppError(409, "generation_expired", "This generation has expired")
            message = await db.get(Message, self.run_id)
            message.content, message.sources, message.status = answer, sources, "complete"
            conversation.busy_until, conversation.run_token = None, None
            conversation.updated_at = utcnow()
            model = await db.get(AIModel, self.model_id) if self.model_id else None
            input_tokens, output_tokens = (
                self.usage.get("input_tokens"),
                self.usage.get("output_tokens"),
            )
            cost = None
            if (
                model
                and input_tokens is not None
                and output_tokens is not None
                and model.input_cost_per_million is not None
                and model.output_cost_per_million is not None
            ):
                cost = (
                    input_tokens * model.input_cost_per_million
                    + output_tokens * model.output_cost_per_million
                ) / 1000000
            db.add(
                UsageLog(
                    owner_id=self.user_id,
                    chatbot_id=self.bot_id,
                    model_id=self.model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    latency_ms=int((time.monotonic() - self.started) * 1000),
                )
            )
        return self.run_id

    async def interrupt(self, status="failed"):
        async with Session.begin() as db:
            conversation = await db.scalar(
                select(Conversation)
                .where(Conversation.id == self.conversation_id)
                .with_for_update()
            )
            message = await db.get(Message, self.run_id)
            if message and message.status != "complete":
                message.content, message.status = self.partial, status
            if conversation and conversation.run_token == self.run_id:
                conversation.busy_until, conversation.run_token = None, None
