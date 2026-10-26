from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class ProviderInput(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "ollama", "openai", "anthropic", "google", "groq", "openai_compatible", "lmstudio", "vllm"
    ]
    base_url: str = Field(max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    enabled: bool = True
    is_local: bool = False


class Capabilities(Input):
    temperature: bool = True
    max_tokens: bool = True
    streaming: bool = True


class ModelInput(Input):
    provider_id: UUID
    name: str = Field(min_length=1, max_length=150)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    is_default: bool = False
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)


class EmbeddingInput(Input):
    provider_id: UUID | None = None
    name: str = Field(min_length=1, max_length=150)
    kind: Literal["ollama", "openai", "huggingface"]
    dimensions: int = Field(ge=1, le=16000)
    version: str = Field(min_length=1, max_length=80)


class KnowledgeInput(Input):
    name: str = Field(min_length=1, max_length=100)
    embedding_id: UUID
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    chunk_overlap: int = Field(default=150, ge=0)
    allow_cloud: bool = False

    @model_validator(mode="after")
    def valid_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class BotInput(Input):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    model_id: UUID
    fallback_model_id: UUID | None = None
    knowledge_base_id: UUID | None = None
    enabled: bool = True
    strict_rag: bool = True
    allow_cloud: bool = False
    streaming: bool = True
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.35, ge=0, le=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=32, le=32768)
    timeout: int = Field(default=90, ge=5, le=300)


class PromptInput(Input):
    content: str = Field(min_length=1, max_length=16000)


class ConversationInput(Input):
    chatbot_id: UUID
    title: str = Field(default="New conversation", min_length=1, max_length=150)


class ChatInput(Input):
    content: str = Field(min_length=1, max_length=12000)
