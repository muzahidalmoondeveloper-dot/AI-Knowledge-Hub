from unittest.mock import AsyncMock

import pytest
from docx import Document as WordDocument
from langchain_core.documents import Document as TextDocument
from sqlalchemy import select

from app.core.config import get_settings
from app.models import Chunk, Document, ProcessingJob
from app.services.documents import extract, split_documents, storage_path
from app.workers.ingestion import claim, process, run_once
from tests.conftest import sign_in
from tests.pdf_fixture import policy_pdf


def test_selectable_pdf_preserves_page_metadata(tmp_path):
    path = tmp_path / "policy.pdf"
    path.write_bytes(policy_pdf())
    pages = extract(path, "policy.pdf")
    assert "Employees receive twenty days" in pages[0].page_content
    assert pages[0].metadata["page"] == 1


def test_chunking_normalization_and_metadata(tmp_path):
    pages = [TextDocument(page_content="A practical policy sentence. " * 50, metadata={"page": 3})]
    chunks = split_documents(pages, 120, 20)
    assert len(chunks) > 5
    assert all(len(c.page_content) <= 120 and c.metadata["page"] == 3 for c in chunks)
    with pytest.raises(ValueError):
        split_documents(pages, 100, 100)
    path = tmp_path / "unicode.txt"
    path.write_text("\ufeff\x00Ａ policy\n", encoding="utf-8")
    assert extract(path, "unicode.txt")[0].page_content == "A policy"


def test_extract_docx_and_empty_pdf(tmp_path):
    doc = WordDocument()
    doc.add_paragraph("Paid leave policy: employees receive twenty days.")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Dhaka"
    path = tmp_path / "policy.docx"
    doc.save(path)
    text = extract(path, "policy.docx")[0].page_content
    assert "twenty days" in text and "Dhaka" in text
    from pypdf import PdfWriter

    pdf = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as target:
        writer.write(target)
    with pytest.raises(ValueError, match="Scanned PDFs require OCR"):
        extract(pdf, "scan.pdf")


async def test_upload_duplicate_replace_reindex_and_owner_access(
    client, setup_workspace, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "upload_directory", tmp_path / "uploads")
    h = setup_workspace["headers"]
    kb = setup_workspace["kb"]["id"]
    response = await client.post(
        f"/api/v1/knowledge-bases/{kb}/documents",
        headers=h,
        files={"file": ("../policy.txt", b"Employees receive twenty days of leave.", "text/plain")},
    )
    assert response.status_code == 201, response.text
    d = response.json()
    assert d["filename"] == "policy.txt" and "storage_key" not in d
    duplicate = await client.post(
        f"/api/v1/knowledge-bases/{kb}/documents",
        headers=h,
        files={"file": ("again.txt", b"Employees receive twenty days of leave.", "text/plain")},
    )
    assert duplicate.status_code == 409
    bad = await client.post(
        f"/api/v1/knowledge-bases/{kb}/documents",
        headers=h,
        files={"file": ("bad.exe", b"malware")},
    )
    assert bad.status_code == 422
    empty = await client.post(
        f"/api/v1/knowledge-bases/{kb}/documents", headers=h, files={"file": ("empty.md", b"")}
    )
    assert empty.status_code == 422
    other = await sign_in(client, "other@example.com")
    for path in [f"/documents/{d['id']}/download", f"/documents/{d['id']}/job"]:
        assert (await client.get("/api/v1" + path, headers=other)).status_code == 404
    assert (
        await client.post(f"/api/v1/documents/{d['id']}/reindex", headers=other)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/documents/{d['id']}/download", headers=h)
    ).content == b"Employees receive twenty days of leave."
    replaced = await client.put(
        f"/api/v1/documents/{d['id']}",
        headers=h,
        files={"file": ("new.md", b"Updated policy: thirty days.")},
    )
    assert replaced.status_code == 200
    assert len(list((tmp_path / "uploads").iterdir())) == 1
    assert (await client.post(f"/api/v1/documents/{d['id']}/reindex", headers=h)).status_code == 202
    assert (await client.get(f"/api/v1/documents/{d['id']}/job", headers=h)).json()[
        "status"
    ] == "queued"
    assert (await client.delete(f"/api/v1/documents/{d['id']}", headers=h)).status_code == 204
    assert not list((tmp_path / "uploads").iterdir())
    with pytest.raises(Exception, match="Invalid storage path"):
        storage_path("../escape.txt")


async def test_worker_atomic_ingestion_and_stale_lease(
    client, setup_workspace, sessions, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "upload_directory", tmp_path / "uploads")
    response = await client.post(
        f"/api/v1/knowledge-bases/{setup_workspace['kb']['id']}/documents",
        headers=setup_workspace["headers"],
        files={"file": ("policy.txt", b"Employees receive twenty days of paid leave. " * 30)},
    )
    assert response.status_code == 201
    adapter = AsyncMock()

    async def embed(texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    adapter.aembed_documents.side_effect = embed
    monkeypatch.setattr("app.workers.ingestion.create_embeddings", AsyncMock(return_value=adapter))
    job_id, token = await claim()
    await process(job_id, token)
    async with sessions() as db:
        doc = await db.scalar(select(Document))
        chunks = (await db.scalars(select(Chunk))).all()
        assert doc.status == "ready" and len(chunks) > 1
        assert all(
            c.embedding_id == setup_workspace["embedding"]["id"]
            or str(c.embedding_id) == setup_workspace["embedding"]["id"]
            for c in chunks
        )
        original_ids = [c.id for c in chunks]
    await process(job_id, token)
    async with sessions() as db:
        assert [c.id for c in (await db.scalars(select(Chunk))).all()] == original_ids
    import uuid

    await process(job_id, uuid.uuid4())


async def test_worker_failure_is_retriable_and_hides_provider_secrets(
    client, setup_workspace, sessions, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "upload_directory", tmp_path / "uploads")
    await client.post(
        f"/api/v1/knowledge-bases/{setup_workspace['kb']['id']}/documents",
        headers=setup_workspace["headers"],
        files={"file": ("policy.txt", b"Some useful policy information.")},
    )
    adapter = AsyncMock()
    adapter.aembed_documents.side_effect = RuntimeError("SECRET_API_KEY should not leak")
    monkeypatch.setattr("app.workers.ingestion.create_embeddings", AsyncMock(return_value=adapter))
    assert await run_once()
    async with sessions() as db:
        job = await db.scalar(select(ProcessingJob))
        assert job.status == "queued" and job.attempts == 1
        assert "SECRET_API_KEY" not in job.error
        assert not (await db.scalars(select(Chunk))).all()
