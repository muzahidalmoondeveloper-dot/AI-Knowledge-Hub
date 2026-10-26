import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import jwt
from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import AppError

passwords = PasswordHash.recommended()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def access_token(user_id: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "iat": utcnow(),
            "exp": utcnow() + timedelta(minutes=settings.access_minutes),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_refresh() -> str:
    return secrets.token_urlsafe(48)


def encrypt(value: str) -> str:
    return Fernet(get_settings().encryption_key.get_secret_value()).encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str:
    return (
        Fernet(get_settings().encryption_key.get_secret_value()).decrypt(value.encode()).decode()
        if value
        else ""
    )


def validate_provider_url(url: str) -> str:
    """Exact administrator-controlled origins; clients disable redirects and environment proxies."""
    parsed = urlsplit(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in {"http", "https"}
        or origin not in get_settings().provider_origins
        or ".." in parsed.path.split("/")
    ):
        raise AppError(
            422, "unsafe_provider_url", "Provider origin is not allowed by server configuration"
        )
    return url.rstrip("/")
