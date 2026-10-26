import asyncio
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select, update

from app.ai.factory import create_chat_model, create_embeddings, provider_for
from app.api.deps import Admin, CurrentUser, Db, public
from app.core.errors import AppError, not_found
from app.core.security import encrypt, validate_provider_url
from app.models import AIModel, Chatbot, EmbeddingModel, Provider
from app.schemas.requests import EmbeddingInput, ModelInput, ProviderInput
from app.schemas.responses import EmbeddingOut, ModelOut, ProviderOut

router = APIRouter(tags=["AI configuration"])


def provider_public(provider):
    return {**public(provider), "has_secret": bool(provider.secret)}


def validate_provider(data: ProviderInput):
    from urllib.parse import urlsplit

    validate_provider_url(data.base_url)
    if data.is_local and (
        data.kind not in {"ollama", "lmstudio", "vllm", "openai_compatible"}
        or urlsplit(data.base_url).hostname not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise AppError(
            422, "invalid_local_provider", "Local processing must use a loopback model server"
        )


@router.get("/providers", response_model=list[ProviderOut])
async def providers(db: Db, user: CurrentUser):
    return [
        provider_public(p)
        for p in (await db.scalars(select(Provider).order_by(Provider.name))).all()
    ]


@router.post("/providers", status_code=201, response_model=ProviderOut)
async def add_provider(data: ProviderInput, db: Db, user: Admin):
    validate_provider(data)
    values = data.model_dump(exclude={"api_key"})
    row = Provider(**values, secret=encrypt(data.api_key) if data.api_key else None)
    db.add(row)
    await db.flush()
    return provider_public(row)


@router.put("/providers/{provider_id}", response_model=ProviderOut)
async def edit_provider(provider_id: UUID, data: ProviderInput, db: Db, user: Admin):
    validate_provider(data)
    row = await db.get(Provider, provider_id)
    if not row:
        raise not_found()
    for key, value in data.model_dump(exclude={"api_key"}).items():
        setattr(row, key, value)
    if data.api_key is not None:
        row.secret = encrypt(data.api_key) if data.api_key else None
    await db.flush()
    return provider_public(row)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: UUID, db: Db, user: Admin):
    row = await db.get(Provider, provider_id)
    if not row:
        raise not_found()
    await db.delete(row)


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: UUID, db: Db, user: Admin):
    provider = await provider_for(db, provider_id)
    model = await db.scalar(select(AIModel).where(AIModel.provider_id == provider_id).limit(1))
    if not model:
        raise AppError(422, "model_required", "Register a chat model before testing")
    bot = Chatbot(temperature=0, max_tokens=16, timeout=20, allow_cloud=True)
    try:
        result = await asyncio.wait_for(
            create_chat_model(provider, model, bot).ainvoke("Reply with OK."), timeout=25
        )
        return {"ok": bool(result.content), "model": model.name}
    except Exception:
        raise AppError(
            502,
            "provider_test_failed",
            "Connection test failed. Check server, credentials and model name.",
        ) from None


@router.get("/models", response_model=list[ModelOut])
async def models(db: Db, user: CurrentUser):
    return [public(m) for m in (await db.scalars(select(AIModel).order_by(AIModel.name))).all()]


async def apply_model(data, db, row):
    await provider_for(db, data.provider_id)
    if data.is_default:
        await db.execute(update(AIModel).values(is_default=False))
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    await db.flush()
    return public(row)


@router.post("/models", status_code=201, response_model=ModelOut)
async def add_model(data: ModelInput, db: Db, user: Admin):
    return await apply_model(data, db, AIModel())


@router.put("/models/{model_id}", response_model=ModelOut)
async def edit_model(model_id: UUID, data: ModelInput, db: Db, user: Admin):
    row = await db.get(AIModel, model_id)
    if not row:
        raise not_found()
    return await apply_model(data, db, row)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(model_id: UUID, db: Db, user: Admin):
    row = await db.get(AIModel, model_id)
    if not row:
        raise not_found()
    await db.delete(row)


@router.get("/embedding-models", response_model=list[EmbeddingOut])
async def embeddings(db: Db, user: CurrentUser):
    return [public(e) for e in (await db.scalars(select(EmbeddingModel))).all()]


@router.post("/embedding-models", status_code=201, response_model=EmbeddingOut)
async def add_embedding(data: EmbeddingInput, db: Db, user: Admin):
    if data.kind != "huggingface":
        p = await provider_for(db, data.provider_id)
        if (data.kind == "ollama") != (p.kind == "ollama"):
            raise AppError(422, "adapter_mismatch", "Embedding adapter does not match provider")
    row = EmbeddingModel(**data.model_dump())
    db.add(row)
    await db.flush()
    return public(row)


@router.post("/embedding-models/{embedding_id}/test")
async def test_embedding(embedding_id: UUID, db: Db, user: Admin):
    config = await db.get(EmbeddingModel, embedding_id)
    if not config:
        raise not_found()
    try:
        adapter = await create_embeddings(db, config, True)
        vector = await asyncio.wait_for(adapter.aembed_query("Connection test"), 120)
        if len(vector) != config.dimensions:
            raise AppError(
                422,
                "dimension_mismatch",
                f"Model returned {len(vector)} dimensions; configuration expects {config.dimensions}",
            )
        return {"ok": True, "dimensions": len(vector)}
    except AppError:
        raise
    except Exception:
        raise AppError(502, "embedding_test_failed", "Embedding model test failed") from None
