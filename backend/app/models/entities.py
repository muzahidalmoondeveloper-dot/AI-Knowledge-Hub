"""Relational models; JSONB on PostgreSQL, JSON in isolated unit tests."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.security import utcnow

Json = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="user")


class RefreshToken(Entity, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    family: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Provider(Entity, Base):
    __tablename__ = "ai_providers"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    base_url: Mapped[str] = mapped_column(String(500))
    secret: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)


class AIModel(Entity, Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider_id", "name"),)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    capabilities: Mapped[dict[str, Any]] = mapped_column(
        Json, default=lambda: {"temperature": True, "max_tokens": True, "streaming": True}
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    input_cost_per_million: Mapped[float | None] = mapped_column(Float)
    output_cost_per_million: Mapped[float | None] = mapped_column(Float)


class EmbeddingModel(Entity, Base):
    __tablename__ = "embedding_models"
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_providers.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(30))
    dimensions: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(80))
    __table_args__ = (CheckConstraint("dimensions > 0 AND dimensions <= 16000"),)


class KnowledgeBase(Entity, Base):
    __tablename__ = "knowledge_bases"
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    embedding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("embedding_models.id", ondelete="RESTRICT")
    )
    chunk_size: Mapped[int] = mapped_column(Integer, default=1000)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=150)
    allow_cloud: Mapped[bool] = mapped_column(Boolean, default=False)
    generation: Mapped[int] = mapped_column(Integer, default=1)


class Chatbot(Entity, Base):
    __tablename__ = "chatbots"
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_models.id", ondelete="RESTRICT"))
    fallback_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="RESTRICT")
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    system_prompt: Mapped[str] = mapped_column(
        Text,
        default="You are a helpful knowledge assistant. Answer clearly in the user's language.",
    )
    strict_rag: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_cloud: Mapped[bool] = mapped_column(Boolean, default=False)
    streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    score_threshold: Mapped[float] = mapped_column(Float, default=0.35)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    timeout: Mapped[int] = mapped_column(Integer, default=90)


class PromptVersion(Entity, Base):
    __tablename__ = "chatbot_prompt_versions"
    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)


class Document(Entity, Base):
    __tablename__ = "documents"
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (UniqueConstraint("knowledge_base_id", "sha256"),)


class Chunk(Entity, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True
    )
    embedding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("embedding_models.id", ondelete="RESTRICT")
    )
    generation: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[Any] = mapped_column(Vector())
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_chunks_space", "knowledge_base_id", "embedding_id", "generation"),
    )


class ProcessingJob(Entity, Base):
    __tablename__ = "document_processing_jobs"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    error: Mapped[str | None] = mapped_column(String(300))


class Conversation(Entity, Base):
    __tablename__ = "conversations"
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chatbot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chatbots.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150), default="New conversation")
    busy_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class Message(Entity, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(Json, default=list)
    status: Mapped[str] = mapped_column(String(20), default="complete")


class UsageLog(Entity, Base):
    __tablename__ = "model_usage_logs"
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chatbot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chatbots.id", ondelete="SET NULL")
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
