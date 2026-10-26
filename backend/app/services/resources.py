from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import enforce_privacy, provider_for
from app.api.deps import owned
from app.core.errors import AppError, not_found
from app.models import AIModel, Chatbot, EmbeddingModel, KnowledgeBase, PromptVersion, User
from app.schemas.requests import BotInput, KnowledgeInput


async def validate_knowledge(db: AsyncSession, data: KnowledgeInput):
    config = await db.get(EmbeddingModel, data.embedding_id)
    if not config:
        raise not_found()
    if config.provider_id:
        enforce_privacy(await provider_for(db, config.provider_id), data.allow_cloud)


async def save_bot(db: AsyncSession, user: User, data: BotInput, bot: Chatbot | None = None):
    if data.knowledge_base_id:
        kb = await owned(db, KnowledgeBase, data.knowledge_base_id, user)
        if data.allow_cloud and not kb.allow_cloud:
            raise AppError(
                422, "knowledge_privacy", "This knowledge base does not allow cloud processing"
            )
    for model_id in [data.model_id, data.fallback_model_id]:
        if model_id:
            model = await db.get(AIModel, model_id)
            if not model:
                raise not_found()
            enforce_privacy(await provider_for(db, model.provider_id), data.allow_cloud)
    is_new = bot is None
    bot = bot or Chatbot(owner_id=user.id)
    for key, value in data.model_dump().items():
        setattr(bot, key, value)
    db.add(bot)
    await db.flush()
    if is_new:
        db.add(PromptVersion(chatbot_id=bot.id, content=bot.system_prompt))
    return bot


async def save_prompt(db: AsyncSession, bot: Chatbot, content: str):
    # The caller locks the chatbot row, serializing prompt revisions.
    bot.system_prompt = content
    version = PromptVersion(chatbot_id=bot.id, content=content)
    db.add(version)
    await db.flush()
    return version


async def paged(db: AsyncSession, model, user: User, offset: int, limit: int):
    return (
        await db.scalars(
            select(model)
            .where(model.owner_id == user.id)
            .order_by(model.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
