from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "AI Knowledge Hub"
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/ai_knowledge_hub"
    jwt_secret_key: SecretStr
    encryption_key: SecretStr
    access_minutes: int = Field(default=15, ge=1, le=60)
    refresh_days: int = Field(default=14, ge=1, le=90)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    provider_origins: list[str] = [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://localhost:1234",
        "http://localhost:8001",
        "https://api.openai.com",
        "https://api.anthropic.com",
        "https://generativelanguage.googleapis.com",
        "https://api.groq.com",
    ]
    upload_directory: Path = Path("uploads")
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)
    history_messages: int = Field(default=12, ge=1, le=100)
    history_characters: int = Field(default=24000, ge=1000, le=100000)
    worker_lease_seconds: int = Field(default=900, ge=120, le=3600)
    cookie_secure: bool = False
    bootstrap_admin_email: str = ""

    @field_validator("jwt_secret_key")
    @classmethod
    def strong_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32 or "replace" in value.get_secret_value().lower():
            raise ValueError("JWT_SECRET_KEY must contain at least 32 random characters")
        return value

    @field_validator("encryption_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        Fernet(value.get_secret_value().encode())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
