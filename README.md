# AI Knowledge Hub

A local-first RAG chatbot workspace built with FastAPI, asynchronous SQLAlchemy, PostgreSQL/pgvector, LangChain, LangGraph and React. No Docker, Redis or paid API key is required for the Ollama workflow.

Implemented: registration/login, Argon2 passwords, JWT access tokens, rotating refresh cookies with family replay revocation, administrator provider management with encrypted secrets, independent immutable embedding configurations, owned chatbot/knowledge/conversation resources, prompt history and restoration, PDF/DOCX/TXT/Markdown ingestion, a durable database job worker, isolated cosine retrieval, PostgreSQL graph checkpoints, SSE chat, source references and usage analytics.

**Strict mode returns verified verbatim extracts for knowledge questions.** Recognized standalone greetings, thanks, farewells and casual check-ins use the configured model for natural replies in the user's language, with conversation history and without document retrieval or citations. Recognition uses a conservative phrase list; mixed greetings and questions still follow the evidence path. The model selects relevant quotes; the server rejects unknown source IDs and text absent from the retrieved passage. It refuses when retrieval is empty or validation fails. This reduces unsupported generated claims, but does not prove relevance or document truth. General mode permits free-form model knowledge and streams raw model text. Strict factual output is buffered until verified, then streamed as validated text chunks.

## Project layout

```text
backend/
  app/api/             versioned routes and access dependencies
  app/core/            validated settings, errors, encryption and tokens
  app/models/          14 SQLAlchemy application tables
  app/schemas/         request validation and public response contracts
  app/services/        authentication, resources, uploads and chat execution
  app/ai/              provider factory, retrieval and graph nodes/state
  app/workers/         leased database ingestion worker
  app/db/              async sessions and checkpoint installation
  alembic/             versioned PostgreSQL schema migration
  tests/               mocked unit/API tests and opt-in integration checks
frontend/              React, TypeScript, Vite and Tailwind
docs/                  architecture, API, Windows setup and Bengali lessons
scripts/               local configuration helpers
```

## Install and run on Windows

See [the complete Windows guide](docs/LOCAL_SETUP_WINDOWS.md) to install PostgreSQL, compile/install pgvector, create the database and install Ollama. Python 3.12 or 3.13 and Node 22 are supported by the selected dependency set; this workspace was checked with Python 3.13 and Node 22.

From the repository root:

```powershell
python -m venv backend/env
.\backend\env\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
.\backend\env\Scripts\python.exe scripts/init_env.py
# Edit backend/.env: database credentials and BOOTSTRAP_ADMIN_EMAIL.
cd backend
.\env\Scripts\python.exe -m alembic upgrade head
.\env\Scripts\python.exe -m app.db.setup_checkpoints
.\env\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --loop app.core.event_loop:selector_loop --no-access-log
```

In a second terminal, from `backend`:

```powershell
.\env\Scripts\python.exe -m app.workers.ingestion
```

In a third terminal, from the repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. Keep the browser host consistent for refresh cookies. Vite proxies `/api` to the backend. Swagger UI: **http://127.0.0.1:8000/docs**. The explicit selector loop in the startup command supports psycopg checkpoints on Windows.

`requirements.txt` declares compatibility ranges; `requirements.lock.txt` freezes the complete verified Windows environment. `package-lock.json` freezes frontend dependencies. Hugging Face local embeddings are optional: install `backend/requirements-local-embeddings.txt` and pre-download a model yourself.

## First complete workflow

1. Register the exact email configured in `BOOTSTRAP_ADMIN_EMAIL` to create the administrator account, then sign in. Other registrations are ordinary users. Reserve this email before exposing registration; clear the bootstrap setting after provisioning.
2. AI providers → add Ollama at `http://localhost:11434`, mark it local and enabled. Register a chat model such as `llama3.2:3b` using its exact installed tag. Test the connection.
3. Register `nomic-embed-text` as an Ollama embedding model, **768 dimensions**, version `v1`. Test dimensions.
4. Create a knowledge base, then create a chatbot linked to it and the chat model. Leave cloud processing off.
5. Open Instructions, save a system prompt, then upload a selectable-text PDF in Knowledge bases.
6. Keep the worker running until the document status becomes `ready`. Ask a question in Playground and inspect its source excerpts. Reopen the conversation from its sidebar.
7. Update the prompt, ask again, then restore a previous revision. For cloud models, configure the provider/model and explicitly allow cloud processing on both chatbot and knowledge base before switching.

Example document text: `Employees receive twenty days of annual leave.` Question: `How much annual leave do employees receive?` Strict output, when the model selects the passage: that exact sentence plus `[1]`, with document/page metadata. A question unsupported by retrieved evidence returns the unavailable-information response.

## Configuration

Required: `DATABASE_URL`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`. The initialization script generates strong secrets without printing them. Set `BOOTSTRAP_ADMIN_EMAIL` before registering your administrator. `.env.example` also documents CORS origins, exact allowed provider origins, upload limits, history limits, lease duration and secure-cookie mode. Provider keys are entered into the administrator dashboard and encrypted in PostgreSQL; they are never stored in frontend persistence or returned by the API.

Back up the encryption key separately from the database. Losing it loses access to stored provider credentials. Rotation requires decrypting with the old key and re-encrypting with the new one in a controlled maintenance process. Keep database/filesystem backups, prompts, messages and graph checkpoints private.

## Verification

```powershell
cd backend
.\env\Scripts\python.exe -m pytest -q
.\env\Scripts\python.exe -m pip check
.\env\Scripts\python.exe -m ruff check app tests
.\env\Scripts\python.exe -m alembic upgrade head --sql
cd ../frontend
npm.cmd test
npm.cmd run build
```

The default suite uses temporary SQLite databases for relational/API behavior, in-memory graph checkpoints, and mocked AI calls. SQLite is **only a test fixture**, never an application storage option. PostgreSQL vector operators, locking and durable checkpoints require separate integration verification. See [verification results and remaining limitations](docs/VERIFICATION.md).

## Design and next steps

The application uses 14 tables; chatbot settings are typed columns on `chatbots` rather than a separate one-to-one settings table. The worker publishes a document's vectors in one transaction. Re-indexing increments the knowledge-base generation, excludes old vectors immediately, and queues every document. Exact search safely supports different vector dimensions; no second vector database is used.

Before public deployment, add authentication throttling and account recovery, upload scanning/resource isolation, operational monitoring, checkpoint retention, load tests and TLS/reverse-proxy controls. Add embedding-specific approximate indexes only after measuring retrieval scale. Organization tenancy, billing, OCR, automatic model downloads and autonomous agents are intentionally outside this version. The platform has production-oriented boundaries, but has not been certified or load-tested for public production use.
