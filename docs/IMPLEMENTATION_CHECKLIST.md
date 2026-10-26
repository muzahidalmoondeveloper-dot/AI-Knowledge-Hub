# Implementation checklist

Architecture: one asynchronous FastAPI service, PostgreSQL with pgvector, a durable database job worker, LangChain provider adapters, a checkpointed LangGraph workflow, and a React SPA. Provider credentials are administrator-managed. User resources are owner-scoped.

- [x] Foundation, configuration, migrations, authentication
- [x] Provider/model registry and independent embeddings
- [x] Knowledge bases, durable ingestion and vector retrieval
- [x] Checkpointed LangGraph, prompts, conversations and streaming
- [x] React management dashboard and chat
- [x] Automated verification, Windows setup and Bengali learning guide

Verification: 44 backend tests and 5 frontend tests pass; frontend build and pip compatibility checks pass. Actual Ollama chat and embeddings pass. PostgreSQL online migrations/vector retrieval/persistent checkpoints remain unverified without database credentials and the native pgvector extension. Paid providers and optional Hugging Face models need separate live tests. See VERIFICATION.md for precise limits.

Verification separates credential-free tests from optional PostgreSQL/Ollama integration tests. No Docker or alternate Python package manager is used.
