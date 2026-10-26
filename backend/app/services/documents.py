import asyncio
import hashlib
import unicodedata
import uuid
import zipfile
from pathlib import Path

from docx import Document as WordDocument
from fastapi import UploadFile
from langchain_core.documents import Document as TextDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.models import Document, KnowledgeBase, ProcessingJob

EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def storage_path(key: str) -> Path:
    root = get_settings().upload_directory.resolve()
    path = (root / key).resolve()
    if path.parent != root:
        raise AppError(400, "invalid_path", "Invalid storage path")
    return path


def extract(path: Path, filename: str) -> list[TextDocument]:
    """Extraction runs in a worker thread. PDF page metadata remains attached to chunks."""
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        if path.read_bytes()[:5] != b"%PDF-":
            raise ValueError("File is not a PDF")
        reader = PdfReader(path)
        pages = [
            TextDocument(page_content=page.extract_text() or "", metadata={"page": i + 1})
            for i, page in enumerate(reader.pages)
        ]
    elif extension == ".docx":
        with zipfile.ZipFile(path) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("Expanded document exceeds 100 MB")
        document = WordDocument(path)
        text = "\n".join(p.text for p in document.paragraphs)
        text += "\n" + "\n".join(
            " | ".join(c.text for c in row.cells) for t in document.tables for row in t.rows
        )
        pages = [TextDocument(page_content=text)]
    elif extension in {".txt", ".md"}:
        pages = [TextDocument(page_content=path.read_text(encoding="utf-8-sig"))]
    else:
        raise ValueError("Unsupported document type")
    for page in pages:
        page.page_content = (
            unicodedata.normalize("NFKC", page.page_content).replace("\x00", "").strip()
        )
    pages = [page for page in pages if page.page_content]
    if not pages:
        raise ValueError("No selectable text found. Scanned PDFs require OCR before upload.")
    return pages


def split_documents(pages: list[TextDocument], size: int, overlap: int) -> list[TextDocument]:
    if overlap < 0 or overlap >= size:
        raise ValueError("Invalid chunk overlap")
    return RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap).split_documents(
        pages
    )


async def queue_document(
    db, kb: KnowledgeBase, upload: UploadFile, existing: Document | None = None
):
    filename = Path((upload.filename or "").replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    if extension not in EXTENSIONS or len(filename) > 255:
        raise AppError(422, "invalid_document", "Upload a PDF, DOCX, UTF-8 TXT or Markdown file")
    key = f"{uuid.uuid4()}{extension}"
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("wb") as target:
            while block := await upload.read(1024 * 1024):
                size += len(block)
                if size > get_settings().max_upload_size_mb * 1024 * 1024:
                    raise AppError(413, "file_too_large", "Document exceeds upload size limit")
                digest.update(block)
                await asyncio.to_thread(target.write, block)
        if size == 0:
            raise AppError(422, "empty_document", "Document is empty")
        duplicate = await db.scalar(
            select(Document).where(
                Document.knowledge_base_id == kb.id, Document.sha256 == digest.hexdigest()
            )
        )
        if duplicate and (not existing or duplicate.id != existing.id):
            raise AppError(
                409, "duplicate_document", "This document already exists in the knowledge base"
            )
        old_path = storage_path(existing.storage_key) if existing else None
        row = existing or Document(knowledge_base_id=kb.id)
        row.filename, row.storage_key, row.sha256, row.size = (
            filename,
            key,
            digest.hexdigest(),
            size,
        )
        row.status, row.error = "queued", None
        db.add(row)
        await db.flush()
        await enqueue(db, row)
        await db.commit()
        if old_path:
            old_path.unlink(missing_ok=True)
        return row
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


async def enqueue(db, document: Document):
    from app.core.security import utcnow

    job = await db.scalar(
        select(ProcessingJob).where(ProcessingJob.document_id == document.id).with_for_update()
    )
    if not job:
        job = ProcessingJob(document_id=document.id)
        db.add(job)
    job.status, job.attempts, job.error = "queued", 0, None
    job.available_at, job.lease_until, job.lease_token = utcnow(), None, None
    document.status, document.error = "queued", None


async def document_for_user(db, document_id, user, *, lock=False):
    query = (
        select(Document)
        .join(KnowledgeBase)
        .where(Document.id == document_id, KnowledgeBase.owner_id == user.id)
    )
    if lock:
        query = query.with_for_update(of=Document)
    row = await db.scalar(query)
    if not row:
        raise not_found()
    return row


async def locked_document(db, document_id, user):
    """Always lock knowledge base before document/job, matching worker publication order."""
    from app.api.deps import owned

    document = await document_for_user(db, document_id, user)
    kb = await owned(db, KnowledgeBase, document.knowledge_base_id, user, lock=True)
    document = await document_for_user(db, document_id, user, lock=True)
    return document, kb
