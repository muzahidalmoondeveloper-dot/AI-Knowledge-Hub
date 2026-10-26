# RAG pipeline

## Ingestion

1. Authenticate, verify KB ownership and lock its configuration.
2. Stream the upload in bounded blocks, cap size, hash for per-KB duplicates and save under a UUID filename.
3. Commit document metadata and a durable job; embedding does not happen during upload.
4. The worker claims a job with a lease/retry count and snapshots the KB generation and immutable embedding configuration.
5. PDF extraction preserves selectable-text page numbers. DOCX paragraphs/tables are extracted; TXT/Markdown require UTF-8. Empty/scanned PDFs report the OCR limitation. Normalize with Unicode NFKC and remove NULs.
6. LangChain `RecursiveCharacterTextSplitter` creates overlapping character chunks.
7. Embed in batches of 32. Every vector must be finite, nonzero and match configured dimensions.
8. Check lease token/generation, then replace all document chunks and mark ready in one transaction. IDs derive from UUID5(document ID, embedding/generation/chunk index).

Processing timeout is shorter than the lease. Jobs retry up to three times with increasing delay. Expired leases recover after crashes. Replacement/deletion/reindex invalidates an old worker's publication. Queued/failed documents are excluded, including old chunks retained during replacement.

## Retrieval and generation

The server loads the owned bot/conversation, acquires a conversation lease and writes the user plus pending assistant records. Context is bounded to 12 messages and 24000 characters by default. A bounded contextual query prepends the previous user question for follow-ups; there is no hidden paid rewriting call.

The KB embedding adapter embeds the query. Chat-time cloud embedding use requires both KB and bot consent. PostgreSQL returns top-k chunks from the current authorized `(KB, embedding configuration, generation)` with cosine similarity `1 - distance` above the threshold. A guarded CASE expression protects different dimensions. Switching chat models preserves the vector space; switching embedding models requires reindexing.

LangChain receives separate application security instructions, database-loaded bot instructions, bounded conversation messages, JSON evidence marked untrusted and the current question. Retrieved text is not a system instruction. No arbitrary-data or code-execution tools are exposed to the model.

Strict mode checks evidence first. Empty retrieval returns unavailable without a chat-model call. Otherwise the model selects at most five exact quotes with source IDs as JSON. Server validation rejects unknown IDs, short/empty extracts or text absent from the cited passage. Invalid output becomes unavailable with no sources. Valid output consists only of checked quotes and server-assigned citation numbers.

Strict mode buffers model selection JSON before display, then emits verified extracts in chunks. It cannot prove question relevance, document truth or benign quoted text. Domain evaluation and review remain necessary. Prompt instructions alone are not treated as a grounding guarantee.

General mode explicitly disables `strict_rag`, permits model knowledge with empty retrieval and streams model text when the registered capability supports it. Its source panel is labeled **retrieved context**, not verified citations. Free-form factual accuracy is not validated.

The final answer/sources and usage are persisted in a short transaction. Failed/cancelled streams retain non-success status and partial text where available. History excludes failed/interrupted assistant messages. Fallback runs only before any general text was emitted and respects the same privacy policy.

## Example and evaluation

PDF page 2 says `Employees receive twenty days of annual leave.` Query: `How much leave do employees receive?` Valid output quotes the sentence with `[1]`, retaining PDF name, document UUID and page 2. `Employees receive fifty days` is rejected even when attached to a real source ID. A valid quote with an invented ID is rejected too.

Tests cover unsupported text/IDs, malformed JSON, empty-evidence routing, metadata, graph routing, persistence and stream failures. The opt-in PostgreSQL test checks KB isolation with different dimensions. Before domain deployment, measure retrieval recall, false-positive evidence, quote relevance and refusal quality on a representative corpus.
