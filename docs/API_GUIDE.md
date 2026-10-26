# API guide

All business endpoints use `/api/v1`. OpenAPI/Swagger is at `/docs`. Request and public response schemas are in `app/schemas`; validation rejects unknown fields. Failures use `{"error":{"code":"not_found","message":"Resource not found"}}`. Validation errors include field names/messages, never submitted values. Unauthorized ownership access returns 404; administrator actions return 403 for ordinary users. Conflicts use 409, invalid configuration 422, upload too large 413, model failure 502 and database failure 503.

## Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | /auth/register | `{email,password}`; at least 10 password characters |
| POST | /auth/login | same body; access token + public user; HttpOnly refresh cookie |
| POST | /auth/refresh | rotate cookie; return access token |
| POST | /auth/logout | revoke refresh family; clear cookie |
| GET | /auth/me | current authenticated user |

Use `Authorization: Bearer <access_token>` for protected endpoints. Browser requests include credentials for refresh cookies. Tokens are never URL parameters. Refresh/logout check Origin when provided; SameSite Strict adds browser protection. Password whitespace is significant.

```powershell
$login = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/login -Method Post -ContentType application/json -Body (@{email='admin@example.com';password='your long password'} | ConvertTo-Json) -SessionVariable session
$headers = @{Authorization=('Bearer ' + $login.access_token)}
Invoke-RestMethod http://127.0.0.1:8000/api/v1/chatbots -Headers $headers
# Do not print or commit $login, $headers or cookies.
```

## Provider and model management

Authenticated users read safe global configuration. Only administrators may mutate or test it.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | /providers | list/create |
| PUT/DELETE | /providers/{id} | update/delete |
| POST | /providers/{id}/test | short invocation using a registered chat model |
| GET/POST | /models | list/register chat model |
| PUT/DELETE | /models/{id} | update/delete model definition |
| GET/POST | /embedding-models | list/register immutable configuration |
| POST | /embedding-models/{id}/test | verify dimensions |

Create provider:

```json
{"name":"Local Ollama","kind":"ollama","base_url":"http://localhost:11434","enabled":true,"is_local":true}
```

Create chat model:

```json
{"provider_id":"PROVIDER_UUID","name":"llama3.2:3b","capabilities":{"temperature":true,"max_tokens":true,"streaming":true},"is_default":true}
```

Create embedding configuration:

```json
{"provider_id":"PROVIDER_UUID","name":"nomic-embed-text","kind":"ollama","dimensions":768,"version":"v1"}
```

Provider input accepts `api_key`. Responses only contain `has_secret`; encrypted bytes are also omitted. On provider PUT omit the key to preserve it; an empty string clears it. Names are explicitly registered rather than fetched from a cross-provider discovery API. Connection tests can consume paid tokens and require administrator action.

## Workspace resources

| Method | Path | Purpose |
|---|---|---|
| GET/POST | /chatbots | list/create owned bots |
| GET/PUT/DELETE | /chatbots/{id} | retrieve/update/delete |
| GET | /chatbots/{id}/prompts | revisions, newest first |
| PUT | /chatbots/{id}/prompt | `{content}`, 1–16000 characters |
| POST | /chatbots/{id}/prompts/{version}/restore | append restored revision |
| GET/POST | /knowledge-bases | list/create owned KBs |
| GET/PUT/DELETE | /knowledge-bases/{id} | read/update metadata/delete |
| POST | /knowledge-bases/{id}/reindex | full KB input, advance generation and queue all docs |
| GET/POST | /knowledge-bases/{id}/documents | list/upload multipart `file` |
| PUT/DELETE | /documents/{id} | replace multipart file/delete |
| GET | /documents/{id}/download | authorized original file |
| GET | /documents/{id}/job | durable job status and attempts |
| POST | /documents/{id}/reindex | retry/rebuild one document |
| GET/POST | /conversations | list/create |
| GET | /conversations/{id} | owned conversation metadata |
| GET | /conversations/{id}/messages | messages/status/sources |
| DELETE | /conversations/{id} | remove messages/checkpoints |
| POST | /conversations/{id}/chat | non-SSE graph wrapper |
| POST | /conversations/{id}/stream | SSE graph response |
| GET | /analytics | counts, token/cost totals and recent usage |

Creation returns 201, queued reindex 202, deletion 204. PUT uses full objects rather than JSON Merge Patch. Changing embedding/chunk settings with ordinary KB PUT returns 409 and directs clients to reindex. Change a bot prompt only through its prompt endpoint; creation records a default revision.

User-resource lists accept bounded `offset`/`limit`. Defaults: bots/KBs/conversations 50, documents/messages 100; maxima 100 and 200 respectively. Message queries accept `latest=true` to page backwards from recent messages while returning each page in chronological order. Conversation list accepts `chatbot_id`. Analytics uses aggregates and last 100 usage records. Registries and prompt history are small administrative lists in this version.

## Streaming

POST `{"content":"How many leave days?"}`. Consume `text/event-stream` over fetch with an Authorization header:

```text
data: {"type":"start","message_id":"UUID"}

data: {"type":"token","text":"Employees receive…"}

data: {"type":"done","message_id":"UUID","sources":[{"source_id":"CHUNK_UUID","document_id":"DOC_UUID","title":"policy.pdf","page":2,"chunk_index":0,"excerpt":"…","score":0.87}],"status":"complete"}

```

On failure the terminal event is `error` with a safe code/message and failed status, without `done`. Disconnects and AbortController cancellation mark unfinished messages interrupted. Once HTTP starts, generation failures appear as SSE events rather than changed HTTP status. Completion follows persistence. A stream ending without `done` is incomplete.
