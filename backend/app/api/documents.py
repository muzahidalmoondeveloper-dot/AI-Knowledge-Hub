from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, Db, owned, public
from app.models import Document, KnowledgeBase, ProcessingJob
from app.schemas.requests import KnowledgeInput
from app.schemas.responses import DocumentOut
from app.services.documents import (
    document_for_user,
    enqueue,
    locked_document,
    queue_document,
    storage_path,
)
from app.services.resources import validate_knowledge

router = APIRouter(tags=["Documents"])


@router.post("/knowledge-bases/{kb_id}/documents", status_code=201, response_model=DocumentOut)
async def upload_document(kb_id: UUID, db: Db, user: CurrentUser, file: UploadFile = File(...)):
    kb = await owned(db, KnowledgeBase, kb_id, user, lock=True)
    return public(await queue_document(db, kb, file))


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    kb_id: UUID,
    db: Db,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    await owned(db, KnowledgeBase, kb_id, user)
    return [
        public(d)
        for d in (
            await db.scalars(
                select(Document)
                .where(Document.knowledge_base_id == kb_id)
                .order_by(Document.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    ]


@router.put("/documents/{document_id}", response_model=DocumentOut)
async def replace_document(
    document_id: UUID, db: Db, user: CurrentUser, file: UploadFile = File(...)
):
    document, kb = await locked_document(db, document_id, user)
    return public(await queue_document(db, kb, file, document))


@router.get("/documents/{document_id}/download")
async def download_document(document_id: UUID, db: Db, user: CurrentUser):
    document = await document_for_user(db, document_id, user)
    return FileResponse(storage_path(document.storage_key), filename=document.filename)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: UUID, db: Db, user: CurrentUser):
    document, _ = await locked_document(db, document_id, user)
    path = storage_path(document.storage_key)
    await db.delete(document)
    await db.commit()
    path.unlink(missing_ok=True)


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex_document(document_id: UUID, db: Db, user: CurrentUser):
    document, _ = await locked_document(db, document_id, user)
    await enqueue(db, document)
    return {"status": "queued"}


@router.get("/documents/{document_id}/job")
async def document_job(document_id: UUID, db: Db, user: CurrentUser):
    await document_for_user(db, document_id, user)
    job = await db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == document_id))
    return public(job) if job else None


@router.post("/knowledge-bases/{kb_id}/reindex", status_code=202)
async def reindex_knowledge(kb_id: UUID, data: KnowledgeInput, db: Db, user: CurrentUser):
    kb = await owned(db, KnowledgeBase, kb_id, user, lock=True)
    await validate_knowledge(db, data)
    for key, value in data.model_dump().items():
        setattr(kb, key, value)
    kb.generation += 1
    for document in (
        await db.scalars(
            select(Document).where(Document.knowledge_base_id == kb_id).with_for_update()
        )
    ).all():
        await enqueue(db, document)
    return {"status": "queued", "generation": kb.generation}
