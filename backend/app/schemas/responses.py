"""Public API contracts deliberately omit every credential and internal storage key."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class UserOut(Record):
    email: str
    role: str


class ProviderOut(Record):
    name: str
    kind: str
    base_url: str
    enabled: bool
    is_local: bool
    has_secret: bool


class ModelOut(Record):
    name: str
    provider_id: UUID
    capabilities: dict[str, bool]
    is_default: bool
    input_cost_per_million: float | None
    output_cost_per_million: float | None


class EmbeddingOut(Record):
    name: str
    provider_id: UUID | None
    kind: str
    dimensions: int
    version: str


class KnowledgeOut(Record):
    name: str
    owner_id: UUID
    embedding_id: UUID
    chunk_size: int
    chunk_overlap: int
    allow_cloud: bool
    generation: int


class BotOut(Record):
    owner_id: UUID
    name: str
    description: str
    model_id: UUID
    fallback_model_id: UUID | None
    knowledge_base_id: UUID | None
    enabled: bool
    system_prompt: str
    strict_rag: bool
    allow_cloud: bool
    streaming: bool
    top_k: int
    score_threshold: float
    temperature: float
    max_tokens: int
    timeout: int


class PromptOut(Record):
    chatbot_id: UUID
    content: str


class DocumentOut(Record):
    knowledge_base_id: UUID
    filename: str
    sha256: str
    size: int
    status: str
    error: str | None


class ConversationOut(Record):
    owner_id: UUID
    chatbot_id: UUID
    title: str


class SourceOut(BaseModel):
    source_id: str
    document_id: str
    title: str
    page: int | None
    excerpt: str
    score: float
    chunk_index: int = 0


class MessageOut(Record):
    conversation_id: UUID
    role: str
    content: str
    sources: list[SourceOut]
    status: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str


class LoginOut(TokenOut):
    user: UserOut
