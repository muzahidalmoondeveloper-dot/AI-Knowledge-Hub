# Database design

Application schema is versioned by `alembic/versions/0001_initial.py`. It creates pgvector and 14 tables using frozen explicit SQL. It does not import live ORM metadata at migration time. UUID keys, timestamps, foreign keys and indexes are declared in `app/models/entities.py`. JSON becomes PostgreSQL JSONB. Python ORM defaults populate fields; raw SQL callers must supply required values.

| Table | Responsibility |
|---|---|
| users | unique normalized email, Argon2 password hash, role |
| refresh_tokens | digest, user, family, expiry, revoked state |
| ai_providers | adapter, allowed URL, encrypted secret, local/enabled status |
| ai_models | provider/model unique pair, capabilities, default flag, optional prices |
| embedding_models | immutable model/version/dimension definition |
| knowledge_bases | owner, embedding configuration, chunk settings, consent, index generation |
| chatbots | owner, primary/fallback model, KB, prompt and typed RAG/model settings |
| chatbot_prompt_versions | append-only prompt snapshots, chatbot and timestamp |
| documents | KB, safe storage key, filename, SHA-256, status/error |
| document_chunks | stable UUID, document/KB/embedding/generation, text/page/index, vector |
| document_processing_jobs | one durable job per document, retries, availability, lease/token |
| conversations | owner, fixed chatbot, title, generation lease/token |
| messages | canonical role/content/status/sources per conversation |
| model_usage_logs | owner/model/bot, optional tokens/cost, latency |

Bot settings are columns on `chatbots`, avoiding an unnecessary one-to-one settings table. Prompt history is a separate table because it is one-to-many. A chatbot initially attaches one KB; a future join table can add multiple KBs.

User-owned records cascade on user deletion. Documents cascade to chunks/jobs. Conversations cascade to messages. Referenced providers/models/embedding definitions are restricted from deletion. Deleting a KB detaches it from chatbots. Deleting a bot preserves usage totals but nulls their bot reference. Graph checkpoint tables are maintained by LangGraph and do not have application foreign keys: conversation/bot deletion explicitly deletes their thread checkpoints.

`document_chunks.embedding` is `vector` without a fixed dimension. Retrieval matches `(knowledge_base_id, embedding_id, generation)` and `vector_dims(embedding)` before the guarded distance calculation. A CASE expression ensures incompatible vectors cannot reach cosine distance even if the planner reorders predicates. The composite B-tree index narrows the space. Exact search works without training or an ANN index. For large collections, introduce a separately reviewed partial HNSW expression index for each specific dimension/embedding space and adjust the query to match; an unconditional mixed-dimension HNSW index is unsafe.

Reindex changes the embedding association, increases KB generation and resets all jobs atomically. Old vectors are immediately excluded. Each successfully rebuilt document becomes visible independently; a failed document remains unavailable. This is a controlled rebuild with a temporary availability gap, not a zero-downtime index swap.

Run migrations from `backend`:

```powershell
.\env\Scripts\python.exe -m alembic upgrade head
.\env\Scripts\python.exe -m app.db.setup_checkpoints
.\env\Scripts\python.exe -m alembic current
.\env\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
```

Review generated revisions before applying them. Never regenerate an already-applied initial migration. `scripts/build_initial_migration.py` was the development helper used once to freeze its initial SQL and refuses overwrite. `alembic upgrade head --sql` previews migration SQL without connecting to the server. `alembic downgrade base` removes application data/tables and should only be used on disposable databases; it leaves the shared pgvector extension and separate graph checkpoint tables intact.

Back up PostgreSQL, upload files and the encryption key consistently. Database backups include sensitive text, prompts, messages and graph state, even though provider secrets are encrypted.
