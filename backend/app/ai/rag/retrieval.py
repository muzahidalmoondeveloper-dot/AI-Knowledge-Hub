import math

from sqlalchemy import case, func, select

from app.ai.factory import create_embeddings
from app.core.errors import AppError
from app.models import Chunk, Document, EmbeddingModel, KnowledgeBase


def validate_vector(vector: list[float], dimensions: int):
    if len(vector) != dimensions or not all(math.isfinite(v) for v in vector) or not any(vector):
        raise AppError(502, "invalid_embedding", "Embedding model returned an incompatible vector")


async def retrieve(
    db, kb: KnowledgeBase, question: str, top_k: int, threshold: float, allow_cloud: bool = False
):
    config = await db.get(EmbeddingModel, kb.embedding_id)
    adapter = await create_embeddings(db, config, kb.allow_cloud and allow_cloud)
    vector = await adapter.aembed_query(question)
    validate_vector(vector, config.dimensions)
    # CASE prevents pgvector from comparing dimensions/spaces even if PostgreSQL reorders filters.
    compatible = (
        (Chunk.knowledge_base_id == kb.id)
        & (Chunk.embedding_id == config.id)
        & (Chunk.generation == kb.generation)
        & (func.vector_dims(Chunk.embedding) == config.dimensions)
    )
    distance = case((compatible, Chunk.embedding.cosine_distance(vector)), else_=None).label(
        "distance"
    )
    query = (
        select(Chunk, Document.filename, distance)
        .join(Document)
        .where(compatible, Document.status == "ready")
        .order_by(distance)
        .limit(top_k)
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "source_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "title": name,
            "page": chunk.page,
            "chunk_index": chunk.chunk_index,
            "excerpt": chunk.content,
            "score": round(1 - float(distance), 5),
        }
        for chunk, name, distance in rows
        if distance is not None and 1 - float(distance) >= threshold
    ]
