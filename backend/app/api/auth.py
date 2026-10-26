from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update

from app.api.deps import CurrentUser, Db, public
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import passwords, token_hash
from app.models import RefreshToken, User
from app.schemas.requests import Credentials
from app.schemas.responses import LoginOut, TokenOut, UserOut
from app.services.auth import authenticate, issue, rotate

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_refresh(response: Response, raw: str):
    settings = get_settings()
    response.set_cookie(
        "akh_refresh",
        raw,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.refresh_days * 86400,
    )


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise AppError(403, "origin_denied", "Request origin is not allowed")


@router.post("/register", status_code=201, response_model=UserOut)
async def register(data: Credentials, db: Db):
    email = str(data.email).lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise AppError(409, "registration_failed", "Unable to register this account")
    role = "admin" if email == get_settings().bootstrap_admin_email.lower() else "user"
    user = User(email=email, password_hash=passwords.hash(data.password), role=role)
    db.add(user)
    await db.flush()
    return public(user)


@router.post("/login", response_model=LoginOut)
async def login(data: Credentials, db: Db, request: Request, response: Response):
    check_origin(request)
    user = await authenticate(db, str(data.email), data.password)
    access, refresh = await issue(db, user)
    set_refresh(response, refresh)
    return {"access_token": access, "token_type": "bearer", "user": public(user)}


@router.post("/refresh", response_model=TokenOut)
async def refresh(db: Db, request: Request, response: Response):
    check_origin(request)
    access, refresh = await rotate(db, request.cookies.get("akh_refresh", ""))
    set_refresh(response, refresh)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout", status_code=204)
async def logout(db: Db, request: Request, response: Response):
    check_origin(request)
    token = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.digest == token_hash(request.cookies.get("akh_refresh", ""))
        )
    )
    if token:
        await db.execute(
            update(RefreshToken).where(RefreshToken.family == token.family).values(revoked=True)
        )
    response.delete_cookie("akh_refresh", path="/api/v1/auth")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return public(user)
