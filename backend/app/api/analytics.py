from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Db, public
from app.models import Chatbot, Conversation, Document, KnowledgeBase, UsageLog

router = APIRouter(tags=["Analytics"])


@router.get("/analytics")
async def analytics(db: Db, user: CurrentUser):
    bots = await db.scalar(
        select(func.count()).select_from(Chatbot).where(Chatbot.owner_id == user.id)
    )
    conversations = await db.scalar(
        select(func.count()).select_from(Conversation).where(Conversation.owner_id == user.id)
    )
    documents = await db.scalar(
        select(func.count())
        .select_from(Document)
        .join(KnowledgeBase)
        .where(KnowledgeBase.owner_id == user.id)
    )
    totals = (
        await db.execute(
            select(
                func.count(UsageLog.id),
                func.sum(UsageLog.input_tokens),
                func.sum(UsageLog.output_tokens),
                func.avg(UsageLog.latency_ms),
                func.sum(UsageLog.cost),
            ).where(UsageLog.owner_id == user.id)
        )
    ).one()
    usage = (
        await db.scalars(
            select(UsageLog)
            .where(UsageLog.owner_id == user.id)
            .order_by(UsageLog.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "chatbots": bots,
        "documents": documents,
        "conversations": conversations,
        "responses": totals[0],
        "input_tokens": totals[1],
        "output_tokens": totals[2],
        "average_latency_ms": totals[3],
        "approximate_cost": totals[4],
        "recent_usage": [public(u) for u in usage],
    }
