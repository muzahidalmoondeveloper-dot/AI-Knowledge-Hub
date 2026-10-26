from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.db.session import get_db
from app.models import User

Db = Annotated[AsyncSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


async def current_user(
    db: Db, credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    try:
        data = jwt.decode(
            credential.credentials if credential else "",
            get_settings().jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "type"]},
        )
        if data["type"] != "access":
            raise ValueError()
        user = await db.get(User, UUID(data["sub"]))
        if user:
            return user
    except (jwt.PyJWTError, ValueError, KeyError):
        pass
    raise AppError(401, "unauthenticated", "Authentication required")


CurrentUser = Annotated[User, Depends(current_user)]


async def admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, "forbidden", "Administrator permission required")
    return user


Admin = Annotated[User, Depends(admin)]


async def owned(db: AsyncSession, model, resource_id: UUID, user: User, *, lock=False):
    from sqlalchemy import select

    query = select(model).where(model.id == resource_id, model.owner_id == user.id)
    if lock:
        query = query.with_for_update()
    value = await db.scalar(query)
    if value is None:
        raise not_found()
    return value


def public(row) -> dict:
    """Only explicitly safe ORM columns; secrets/storage/passwords never leave the API."""
    hidden = {"secret", "password_hash", "storage_key", "digest", "lease_token", "run_token"}
    return {
        column.key: getattr(row, column.key)
        for column in row.__table__.columns
        if column.key not in hidden
    }
