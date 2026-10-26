# Providers and embeddings

`app/ai/factory.py` receives stored provider/model/bot definitions, decrypts credentials and creates a LangChain adapter. Business logic uses `ainvoke`/`astream`; switching providers does not rewrite RAG.

| Provider | Integration | Typical base URL |
|---|---|---|
| ollama | ChatOllama | http://localhost:11434 |
| openai | ChatOpenAI | https://api.openai.com/v1 |
| anthropic | ChatAnthropic | https://api.anthropic.com |
| google | ChatGoogleGenerativeAI | https://generativelanguage.googleapis.com |
| groq | ChatOpenAI compatible protocol | https://api.groq.com/openai/v1 |
| lmstudio | ChatOpenAI | http://localhost:1234/v1 |
| vllm | ChatOpenAI | http://localhost:8001/v1 |
| openai_compatible | ChatOpenAI | administrator-allowlisted origin |

Register exact provider model names and supported temperature/output-limit/streaming capabilities. Unsupported optional parameters are suppressed. Ollama maps output limit to `num_predict`; other adapters handle native aliases. Maximum timeout is 300 seconds. Retries/fallbacks are controlled by the application. The default model pre-fills new bot forms; existing bots retain their explicit ID.

Optional per-million token prices enable approximate cost only when provider usage is also available. Missing usage is not invented. Provider tests perform a short actual generation and can incur cloud cost.

Only loopback servers may be marked local. Known Ollama `:cloud` tags are rejected under local providers. Administrators must not label a local forwarding proxy as private: the application cannot inspect a model server's internal network behavior. Cloud use and fallback require explicit consent. Fallback occurs only before general-mode text has been emitted.

API keys are encrypted at rest with Fernet and excluded from responses. Omitted key updates preserve it; empty string clears it. Ordinary logs omit raw provider exceptions, prompts and source text. Keep LangSmith tracing disabled for sensitive workloads unless you explicitly consent to that destination.

## Embeddings

Configurations are immutable. Register a new version for model/revision/dimension changes and reindex the KB. Test actual dimensions first.

- Ollama: `OllamaEmbeddings`, usually `nomic-embed-text`, 768 dimensions.
- OpenAI/compatible: `OpenAIEmbeddings`, using the model's default dimension. Arbitrary output dimensionality reduction is not configured in this version.
- Hugging Face: optional `HuggingFaceEmbeddings`, `local_files_only=True`, normalized vectors. Install optional requirements and pre-download a trusted pinned snapshot/local model path. Remote-code execution is not enabled. This optional torch stack was not installed in baseline verification.

Changing chat models does not require re-embedding. Changing embedding models always does. Ingestion/query validation checks finite nonzero vectors and dimensions. Equal dimensions do not make two model configurations compatible spaces.

Default tests construct every chat adapter without paid calls. Ollama embedding smoke testing is opt-in. Cloud account access and real response semantics need separate credentialed testing. To extend providers, add an adapter branch, URL/credential checks, capability definitions and mocked success/failure tests. Never put credentials in graph state. Installed versions are frozen in `requirements.lock.txt`; see [LangChain integration documentation](https://docs.langchain.com/oss/python/integrations/chat/ollama).
