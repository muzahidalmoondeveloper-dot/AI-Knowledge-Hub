import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api import analytics, auth, chat, documents, providers, resources
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import engine

settings = get_settings()
logger = logging.getLogger("akh")
logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","event":"%(message)s"}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # setup() is an explicit installation step, not a schema mutation on every API boot.
    uri = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    async with AsyncPostgresSaver.from_conn_string(uri) as saver:
        app.state.checkpointer = saver
        yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
for module in (auth, providers, resources, documents, chat, analytics):
    app.include_router(module.router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error(request, error):
    return JSONResponse(
        status_code=error.status, content={"error": {"code": error.code, "message": error.message}}
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Pydantic's default errors include raw input, which can expose passwords/API keys.
    details = [
        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Check the submitted fields",
                "details": details,
            }
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, error):
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "resource_conflict",
                "message": "This resource already exists or is still in use",
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    logger.error("database_operation_failed")
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "database_unavailable", "message": "Database operation failed"}},
    )


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    logger.error("unexpected_request_failure")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Unable to complete this request"}},
    )


@app.middleware("http")
async def observe(request: Request, call_next):
    started, request_id = time.monotonic(), str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    # No URLs, request bodies, credentials, model exceptions or source content in logs.
    logger.info(
        "request_completed id=%s status=%s latency_ms=%s",
        request_id,
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    return response


@app.get("/health")
async def health():
    from sqlalchemy import text

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok"}
