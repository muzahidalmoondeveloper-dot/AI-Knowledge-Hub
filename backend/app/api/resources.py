from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, Db, owned, public
from app.core.errors import AppError, not_found
from app.models import Chatbot, Conversation, KnowledgeBase, Message, PromptVersion
from app.schemas.requests import BotInput, ConversationInput, KnowledgeInput, PromptInput
from app.schemas.responses import BotOut, ConversationOut, KnowledgeOut, MessageOut, PromptOut
from app.services.resources import paged, save_bot, save_prompt, validate_knowledge

router = APIRouter(tags=["Workspace"])


@router.get("/chatbots", response_model=list[BotOut])
async def list_bots(
    db: Db, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    return [public(row) for row in await paged(db, Chatbot, user, offset, limit)]


@router.post("/chatbots", status_code=201, response_model=BotOut)
async def create_bot(data: BotInput, db: Db, user: CurrentUser):
    return public(await save_bot(db, user, data))


@router.get("/chatbots/{bot_id}", response_model=BotOut)
async def get_bot(bot_id: UUID, db: Db, user: CurrentUser):
    return public(await owned(db, Chatbot, bot_id, user))


@router.put("/chatbots/{bot_id}", response_model=BotOut)
async def update_bot(bot_id: UUID, data: BotInput, db: Db, user: CurrentUser):
    bot = await owned(db, Chatbot, bot_id, user, lock=True)
    return public(await save_bot(db, user, data, bot))


@router.delete("/chatbots/{bot_id}", status_code=204)
async def delete_bot(bot_id: UUID, db: Db, user: CurrentUser, request: Request):
    bot = await owned(db, Chatbot, bot_id, user, lock=True)
    conversations = (
        await db.scalars(
            select(Conversation).where(Conversation.chatbot_id == bot.id).with_for_update()
        )
    ).all()
    for conversation in conversations:
        await delete_checkpoint(request, conversation)
    await db.delete(bot)


@router.get("/chatbots/{bot_id}/prompts", response_model=list[PromptOut])
async def prompt_versions(bot_id: UUID, db: Db, user: CurrentUser):
    await owned(db, Chatbot, bot_id, user)
    return [
        public(p)
        for p in (
            await db.scalars(
                select(PromptVersion)
                .where(PromptVersion.chatbot_id == bot_id)
                .order_by(PromptVersion.created_at.desc())
            )
        ).all()
    ]


@router.put("/chatbots/{bot_id}/prompt", response_model=PromptOut)
async def update_prompt(bot_id: UUID, data: PromptInput, db: Db, user: CurrentUser):
    bot = await owned(db, Chatbot, bot_id, user, lock=True)
    return public(await save_prompt(db, bot, data.content))


@router.post("/chatbots/{bot_id}/prompts/{version_id}/restore", response_model=PromptOut)
async def restore_prompt(bot_id: UUID, version_id: UUID, db: Db, user: CurrentUser):
    bot = await owned(db, Chatbot, bot_id, user, lock=True)
    version = await db.get(PromptVersion, version_id)
    if not version or version.chatbot_id != bot.id:
        raise not_found()
    return public(await save_prompt(db, bot, version.content))


@router.get("/knowledge-bases", response_model=list[KnowledgeOut])
async def list_knowledge(
    db: Db, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)
):
    return [public(row) for row in await paged(db, KnowledgeBase, user, offset, limit)]


@router.post("/knowledge-bases", status_code=201, response_model=KnowledgeOut)
async def create_knowledge(data: KnowledgeInput, db: Db, user: CurrentUser):
    await validate_knowledge(db, data)
    row = KnowledgeBase(owner_id=user.id, **data.model_dump())
    db.add(row)
    await db.flush()
    return public(row)


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeOut)
async def get_knowledge(kb_id: UUID, db: Db, user: CurrentUser):
    return public(await owned(db, KnowledgeBase, kb_id, user))


@router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeOut)
async def update_knowledge(kb_id: UUID, data: KnowledgeInput, db: Db, user: CurrentUser):
    kb = await owned(db, KnowledgeBase, kb_id, user, lock=True)
    await validate_knowledge(db, data)
    if (
        data.embedding_id != kb.embedding_id
        or data.chunk_size != kb.chunk_size
        or data.chunk_overlap != kb.chunk_overlap
    ):
        raise AppError(
            409,
            "reindex_required",
            "Use the reindex endpoint to change embedding or chunk settings",
        )
    kb.name, kb.allow_cloud = data.name, data.allow_cloud
    return public(kb)


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge(kb_id: UUID, db: Db, user: CurrentUser):
    from app.models import Document
    from app.services.documents import storage_path

    kb = await owned(db, KnowledgeBase, kb_id, user, lock=True)
    paths = [
        storage_path(d.storage_key)
        for d in (
            await db.scalars(select(Document).where(Document.knowledge_base_id == kb_id))
        ).all()
    ]
    await db.delete(kb)
    await db.commit()
    for path in paths:
        path.unlink(missing_ok=True)


@router.post("/conversations", status_code=201, response_model=ConversationOut)
async def create_conversation(data: ConversationInput, db: Db, user: CurrentUser):
    bot = await owned(db, Chatbot, data.chatbot_id, user)
    if not bot.enabled:
        raise AppError(409, "bot_disabled", "This chatbot is disabled")
    row = Conversation(owner_id=user.id, **data.model_dump())
    db.add(row)
    await db.flush()
    return public(row)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: Db,
    user: CurrentUser,
    chatbot_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = select(Conversation).where(Conversation.owner_id == user.id)
    if chatbot_id:
        query = query.where(Conversation.chatbot_id == chatbot_id)
    return [
        public(c)
        for c in (
            await db.scalars(
                query.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
            )
        ).all()
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: UUID, db: Db, user: CurrentUser):
    return public(await owned(db, Conversation, conversation_id, user))


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def messages(
    conversation_id: UUID,
    db: Db,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    latest: bool = False,
):
    await owned(db, Conversation, conversation_id, user)
    rows = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc() if latest else Message.created_at)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    if latest:
        rows = list(reversed(rows))
    return [public(row) for row in rows]


async def delete_checkpoint(request: Request, conversation):
    from datetime import timezone

    from app.core.security import utcnow

    until = conversation.busy_until
    if until and (until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until) > utcnow():
        raise AppError(
            409, "conversation_busy", "Cancel generation before deleting this conversation"
        )
    saver = getattr(request.app.state, "checkpointer", None)
    if saver:
        await saver.adelete_thread(f"{conversation.owner_id}:{conversation.id}")


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: UUID, db: Db, user: CurrentUser, request: Request):
    row = await owned(db, Conversation, conversation_id, user, lock=True)
    await delete_checkpoint(request, row)
    await db.delete(row)
