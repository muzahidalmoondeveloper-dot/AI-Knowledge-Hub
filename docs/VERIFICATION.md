# Verification record

Verified on 26 October 2026 using Windows, Python 3.13.5 and Node 22.17.1. No paid API credentials were used. The environment is frozen in `backend/requirements.lock.txt` and `frontend/package-lock.json`.

| Check | Result |
|---|---|
| Backend default pytest suite | 44 passed, 3 optional integration tests skipped |
| Frontend Vitest | 5 passed across 2 files |
| TypeScript and Vite production build | passed |
| Python dependency resolver / `pip check` | no broken requirements |
| Ruff backend checks | passed after formatting/import cleanup |
| Initial migration offline SQL | generated; test confirms pgvector, tables, cascades and indexes |
| FastAPI OpenAPI schema | generated/imported successfully |
| Real Ollama embedding smoke test | passed, nomic-embed-text produced 768 dimensions |
| Real Ollama chat factory smoke test | passed, installed llama3:8b generated nonempty text |
| Browser visual check | authentication page renders in Chrome at 127.0.0.1:5173 |
| Full PostgreSQL/pgvector acceptance workflow | not run: database password unavailable and native pgvector extension not found |
| Paid cloud calls | not run: credentials not supplied |
| Hugging Face local model | not run: optional packages/model snapshot not installed |

The default suite covers registration/login, Argon2/encryption, refresh rotation/replay/logout, response redaction, administrator permissions, owner isolation, CRUD, prompt revisions/restoration, cloud consent, URL allowlists, adapter construction, dimension checks, chunk metadata, DOCX/text/PDF extraction failures, upload replacement/deletion/duplicates, job fencing/atomic publication, worker failures/retries, graph conditional routing/checkpoint state, strict evidence validation, canonical messages, streaming failures/cancellation, fallback and usage.

Frontend tests cover UTF-8/SSE framing, authenticated requests, refresh retry, safe errors, incomplete streams, and preserving the first streamed response across new-conversation navigation. They are mocked behavior tests, not a complete browser automation suite. Authenticated dashboard forms and the complete PDF conversation workflow still require a configured real database for interactive acceptance.

The PostgreSQL integration test is opt-in with `TEST_DATABASE_URL` pointing to a disposable migrated database. It exercises actual pgvector operators and filters across KBs with different vector dimensions. SQLite relational tests do not establish PostgreSQL locking, extension availability, foreign-key DDL execution or durable checkpoint correctness. Offline SQL generation does not prove online migrations have succeeded.

Actual smoke commands used:

```powershell
cd backend
$env:RUN_OLLAMA_TESTS='1'
.\env\Scripts\python.exe -m pytest tests/test_postgres.py -m ollama -q
$env:RUN_OLLAMA_CHAT_TESTS='1'
$env:OLLAMA_TEST_CHAT_MODEL='llama3:8b'
.\env\Scripts\python.exe -m pytest tests/test_postgres.py::test_real_ollama_chat_factory -q
```

Set the chat model to one installed on your own machine. Normal tests skip these network/model calls.

## Material limitations and next verification

1. Install the native pgvector extension and put a dedicated PostgreSQL connection URL in `backend/.env`. Run Alembic plus checkpoint setup, then execute the README acceptance workflow with a selectable-text PDF. No existing database role, password or server configuration was changed during development.
2. Strict mode is extractive and buffers selection until validation. It does not provide free-form grounded synthesis or prove quote relevance. General mode is free-form and unverified. There is no OCR requirement.
3. The local worker is durable but not a general distributed task platform. Restart recovery uses leases; interrupted token streams do not resume automatically. File/database operations can leave orphan files after process crashes; checkpoint deletion and application deletion also need periodic reconciliation after failures.
4. Exact vector search favors correctness over large-corpus performance. Add dimension-specific ANN indexes after profiling. Retain the authorization and embedding/generation filters.
5. Only recent usage is tabulated; token/cost information is nullable and approximate. Chat model names/prices/capabilities are administrator-maintained; model discovery/download is manual.
6. Upload parsing runs in a thread within the worker process, not an operating-system isolation boundary. Add malware scanning, parser subprocess memory/time limits and reverse-proxy body/rate limits before accepting hostile public uploads.
7. Add login throttling, email verification/recovery, production TLS/cookie configuration, monitoring, backup/restore tests and load testing before public deployment. Access JWTs remain valid until expiry after logout; refresh sessions are revoked immediately.
8. Provider origins and local server behavior are trusted administrator configuration. A malicious approved endpoint or a local proxy forwarding externally is outside what origin validation can guarantee. Cloud SDK calls and optional local Hugging Face dependencies need separate live verification.

This is an implemented application with passing isolated checks and verified local model adapters; full end-to-end PostgreSQL acceptance is still pending the listed local infrastructure setup.
