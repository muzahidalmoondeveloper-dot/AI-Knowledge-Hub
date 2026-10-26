from datetime import timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import access_token, new_refresh, passwords, token_hash, utcnow
from app.models import RefreshToken, User


async def issue(db: AsyncSession, user: User, family=None) -> tuple[str, str]:
    raw = new_refresh()
    db.add(
        RefreshToken(
            user_id=user.id,
            digest=token_hash(raw),
            family=family or uuid4(),
            expires_at=utcnow() + timedelta(days=get_settings().refresh_days),
        )
    )
    await db.flush()
    return access_token(str(user.id)), raw


async def rotate(db: AsyncSession, raw: str) -> tuple[str, str]:
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.digest == token_hash(raw)).with_for_update()
    )
    if not token:
        raise AppError(401, "invalid_refresh", "Session expired; please sign in")
    expires = (
        token.expires_at.replace(tzinfo=timezone.utc)
        if token.expires_at.tzinfo is None
        else token.expires_at
    )
    if token.revoked or expires <= utcnow():
        await db.execute(
            update(RefreshToken).where(RefreshToken.family == token.family).values(revoked=True)
        )
        # Persist replay revocation even though the API will return an authentication error.
        await db.commit()
        raise AppError(401, "invalid_refresh", "Session expired; please sign in")
    token.revoked = True
    user = await db.get(User, token.user_id)
    return await issue(db, user, token.family)


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email.lower()))
    # A valid dummy hash keeps unknown-user checks on the same expensive code path.
    digest = user.password_hash if user else DUMMY_HASH
    if not passwords.verify(password, digest) or not user:
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    return user


DUMMY_HASH = passwords.hash("unused-dummy-authentication-password")
