"""LangChain adapters are selected here, never in chatbot business logic."""

import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decrypt, validate_provider_url
from app.models import AIModel, Chatbot, EmbeddingModel, Provider


async def provider_for(db: AsyncSession, provider_id) -> Provider:
    provider = await db.get(Provider, provider_id)
    if not provider or not provider.enabled:
        raise AppError(
            422, "provider_unavailable", "The selected provider is disabled or unavailable"
        )
    validate_provider_url(provider.base_url)
    return provider


def enforce_privacy(provider: Provider, allow_cloud: bool):
    if not provider.is_local and not allow_cloud:
        raise AppError(
            422,
            "cloud_processing_disabled",
            "Explicitly allow cloud processing before using this provider",
        )


def validate_model_locality(provider: Provider, name: str):
    if provider.kind == "ollama" and provider.is_local and name.endswith(":cloud"):
        raise AppError(
            422,
            "remote_ollama_model",
            "Ollama cloud models must be registered under a cloud-processing provider",
        )


def create_chat_model(provider: Provider, model: AIModel, bot: Chatbot) -> BaseChatModel:
    """Pass tunable parameters only when the administrator registered the capability."""
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI

    validate_provider_url(provider.base_url)
    enforce_privacy(provider, bot.allow_cloud)
    validate_model_locality(provider, model.name)
    options = {"model": model.name}
    if model.capabilities.get("temperature"):
        options["temperature"] = bot.temperature
    if model.capabilities.get("max_tokens"):
        options["max_tokens"] = bot.max_tokens
    secret = decrypt(provider.secret)
    if provider.kind == "ollama":
        maximum = options.pop("max_tokens", None)
        if maximum:
            options["num_predict"] = maximum
        return ChatOllama(
            **options,
            base_url=provider.base_url,
            client_kwargs={"timeout": bot.timeout, "follow_redirects": False, "trust_env": False},
        )
    if provider.kind == "anthropic":
        return ChatAnthropic(
            **options,
            api_key=secret,
            base_url=provider.base_url,
            timeout=bot.timeout,
            max_retries=0,
        )
    if provider.kind == "google":
        return ChatGoogleGenerativeAI(
            **options,
            api_key=secret,
            base_url=provider.base_url,
            client_args={"follow_redirects": False, "trust_env": False},
            timeout=bot.timeout,
            max_retries=0,
        )
    # Groq, LM Studio and vLLM expose the supported OpenAI chat completion protocol.
    return ChatOpenAI(
        **options,
        api_key=secret or "local-no-key",
        base_url=provider.base_url,
        timeout=bot.timeout,
        max_retries=0,
        http_async_client=httpx.AsyncClient(follow_redirects=False, trust_env=False),
        http_client=httpx.Client(follow_redirects=False, trust_env=False),
    )


async def create_embeddings(
    db: AsyncSession, config: EmbeddingModel, allow_cloud: bool
) -> Embeddings:
    if config.kind == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=config.name,
            model_kwargs={"local_files_only": True},
            encode_kwargs={"normalize_embeddings": True},
        )
    provider = await provider_for(db, config.provider_id)
    enforce_privacy(provider, allow_cloud)
    validate_model_locality(provider, config.name)
    if config.kind == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=config.name,
            base_url=provider.base_url,
            client_kwargs={"timeout": 120, "follow_redirects": False, "trust_env": False},
        )
    if config.kind == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=config.name,
            api_key=decrypt(provider.secret) or "local-no-key",
            base_url=provider.base_url,
            request_timeout=120,
            max_retries=0,
            http_async_client=httpx.AsyncClient(follow_redirects=False, trust_env=False),
            http_client=httpx.Client(follow_redirects=False, trust_env=False),
        )
    raise AppError(422, "unsupported_embeddings", "Unsupported embedding adapter")
