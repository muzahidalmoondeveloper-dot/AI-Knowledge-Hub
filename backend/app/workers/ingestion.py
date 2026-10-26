"""Run independently: python -m app.workers.ingestion. Jobs survive API/worker restarts."""

import asyncio
import logging
import uuid
from datetime import timedelta

from sqlalchemy import and_, delete, or_, select

from app.ai.factory import create_embeddings
from app.ai.rag.retrieval import validate_vector
from app.core.config import get_settings
from app.core.security import utcnow
from app.db.session import Session
from app.models import Chunk, Document, EmbeddingModel, KnowledgeBase, ProcessingJob
from app.services.documents import extract, split_documents, storage_path

logger = logging.getLogger("ingestion")


async def claim():
    async with Session.begin() as db:
        eligible = or_(
            and_(ProcessingJob.status == "queued", ProcessingJob.available_at <= utcnow()),
            and_(ProcessingJob.status == "processing", ProcessingJob.lease_until < utcnow()),
        )
        # Discover without locking, then use the same KB -> document -> job order
        # as API mutations. Never hold a job lock while waiting for its parent KB.
        job = await db.scalar(
            select(ProcessingJob).where(eligible).order_by(ProcessingJob.available_at).limit(1)
        )
        if not job:
            return None
        candidate_id = job.id
        document = await db.get(Document, job.document_id)
        if not document:
            return None
        kb = await db.scalar(
            select(KnowledgeBase)
            .where(KnowledgeBase.id == document.knowledge_base_id)
            .with_for_update(skip_locked=True)
        )
        if not kb:
            return None
        document = await db.scalar(
            select(Document).where(Document.id == document.id).with_for_update()
        )
        job = await db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.id == candidate_id, eligible)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
        if not job or not document:
            return None
        if job.attempts >= 3:
            job.status, job.error = "failed", "Maximum processing attempts exceeded"
            document.status, document.error = "failed", job.error
            return None
        job.status, job.attempts = "processing", job.attempts + 1
        job.lease_token = uuid.uuid4()
        job.lease_until = utcnow() + timedelta(seconds=get_settings().worker_lease_seconds)
        document.status, document.error = "processing", None
        return job.id, job.lease_token


async def process(job_id, lease_token):
    async with Session() as db:
        job = await db.get(ProcessingJob, job_id)
        if not job or job.lease_token != lease_token or job.status != "processing":
            return
        document = await db.get(Document, job.document_id)
        kb = await db.get(KnowledgeBase, document.knowledge_base_id)
        config = await db.get(EmbeddingModel, kb.embedding_id)
        generation, embedding_id, document_id = kb.generation, config.id, document.id
        adapter = await create_embeddings(db, config, kb.allow_cloud)
        path, filename = storage_path(document.storage_key), document.filename
        size, overlap, dimensions = kb.chunk_size, kb.chunk_overlap, config.dimensions
    pages = await asyncio.to_thread(extract, path, filename)
    chunks = await asyncio.to_thread(split_documents, pages, size, overlap)
    vectors = []
    for start in range(0, len(chunks), 32):
        vectors.extend(
            await adapter.aembed_documents(
                [chunk.page_content for chunk in chunks[start : start + 32]]
            )
        )
    if len(vectors) != len(chunks) or any(len(v) != dimensions or not any(v) for v in vectors):
        raise ValueError("Embedding dimensions mismatch or empty vectors")
    for vector in vectors:
        validate_vector(vector, dimensions)
    # Fence stale workers after replacement/reindex/lease recovery. All chunks publish atomically.
    async with Session.begin() as db:
        kb = await db.scalar(
            select(KnowledgeBase).where(KnowledgeBase.id == kb.id).with_for_update()
        )
        job = await db.scalar(
            select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
        )
        if not kb or not job or job.lease_token != lease_token or kb.generation != generation:
            return
        document = await db.get(Document, document_id)
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            db.add(
                Chunk(
                    id=uuid.uuid5(document_id, f"{embedding_id}:{generation}:{i}"),
                    document_id=document_id,
                    knowledge_base_id=kb.id,
                    embedding_id=embedding_id,
                    generation=generation,
                    content=chunk.page_content,
                    page=chunk.metadata.get("page"),
                    chunk_index=i,
                    embedding=vector,
                )
            )
        job.status, job.lease_until, job.error = "complete", None, None
        document.status, document.error = "ready", None


async def run_once() -> bool:
    claimed = await claim()
    if not claimed:
        return False
    job_id, token = claimed
    try:
        await asyncio.wait_for(
            process(job_id, token), timeout=get_settings().worker_lease_seconds - 30
        )
    except Exception as error:
        # Do not persist provider exception strings: they can contain credentials or source text.
        message = "Document processing failed. Check file text, model availability and embedding dimensions."
        if isinstance(error, ValueError) and str(error) in {
            "No selectable text found. Scanned PDFs require OCR before upload.",
            "Embedding dimensions mismatch or empty vectors",
            "File is not a PDF",
            "Expanded document exceeds 100 MB",
        }:
            message = str(error)
        logger.warning(
            "document_processing_failed",
            extra={"job_id": str(job_id), "error_type": type(error).__name__},
        )
        async with Session.begin() as db:
            snapshot = await db.get(ProcessingJob, job_id)
            document = await db.get(Document, snapshot.document_id) if snapshot else None
            if not document:
                return True
            kb = await db.scalar(
                select(KnowledgeBase)
                .where(KnowledgeBase.id == document.knowledge_base_id)
                .with_for_update()
            )
            if not kb:
                return True
            job = await db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job and job.lease_token == token:
                job.status = "queued" if job.attempts < 3 else "failed"
                job.error, job.lease_until = message, None
                job.available_at = utcnow() + timedelta(seconds=10 * job.attempts)
                document = await db.get(Document, job.document_id)
                if document:
                    document.status, document.error = job.status, message
    return True


async def main():
    logging.basicConfig(
        level=logging.INFO, format='{"level":"%(levelname)s","event":"%(message)s"}'
    )
    while True:
        try:
            if not await run_once():
                await asyncio.sleep(2)
        except Exception as error:
            logger.error("worker_database_failure", extra={"error_type": type(error).__name__})
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
