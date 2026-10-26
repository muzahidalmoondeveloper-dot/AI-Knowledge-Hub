"""Initial application schema with mixed-dimension pgvector storage."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
CREATE TABLE ai_providers (
	name VARCHAR(100) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	base_url VARCHAR(500) NOT NULL, 
	secret TEXT, 
	enabled BOOLEAN NOT NULL, 
	is_local BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)
""")
    op.execute("""
CREATE TABLE users (
	email VARCHAR(320) NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)
""")
    op.execute("""
CREATE TABLE ai_models (
	provider_id UUID NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	capabilities JSONB NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	input_cost_per_million FLOAT, 
	output_cost_per_million FLOAT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (provider_id, name), 
	FOREIGN KEY(provider_id) REFERENCES ai_providers (id) ON DELETE RESTRICT
)
""")
    op.execute("CREATE INDEX ix_ai_models_provider_id ON ai_models (provider_id)")
    op.execute("""
CREATE TABLE embedding_models (
	provider_id UUID, 
	name VARCHAR(150) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	dimensions INTEGER NOT NULL, 
	version VARCHAR(80) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (dimensions > 0 AND dimensions <= 16000), 
	FOREIGN KEY(provider_id) REFERENCES ai_providers (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE refresh_tokens (
	user_id UUID NOT NULL, 
	digest VARCHAR(64) NOT NULL, 
	family UUID NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (digest)
)
""")
    op.execute("CREATE INDEX ix_refresh_tokens_family ON refresh_tokens (family)")
    op.execute("CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("""
CREATE TABLE knowledge_bases (
	owner_id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	embedding_id UUID NOT NULL, 
	chunk_size INTEGER NOT NULL, 
	chunk_overlap INTEGER NOT NULL, 
	allow_cloud BOOLEAN NOT NULL, 
	generation INTEGER NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(embedding_id) REFERENCES embedding_models (id) ON DELETE RESTRICT
)
""")
    op.execute("CREATE INDEX ix_knowledge_bases_owner_id ON knowledge_bases (owner_id)")
    op.execute("""
CREATE TABLE chatbots (
	owner_id UUID NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	model_id UUID NOT NULL, 
	fallback_model_id UUID, 
	knowledge_base_id UUID, 
	enabled BOOLEAN NOT NULL, 
	system_prompt TEXT NOT NULL, 
	strict_rag BOOLEAN NOT NULL, 
	allow_cloud BOOLEAN NOT NULL, 
	streaming BOOLEAN NOT NULL, 
	top_k INTEGER NOT NULL, 
	score_threshold FLOAT NOT NULL, 
	temperature FLOAT NOT NULL, 
	max_tokens INTEGER NOT NULL, 
	timeout INTEGER NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_id) REFERENCES ai_models (id) ON DELETE RESTRICT, 
	FOREIGN KEY(fallback_model_id) REFERENCES ai_models (id) ON DELETE RESTRICT, 
	FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases (id) ON DELETE SET NULL
)
""")
    op.execute("CREATE INDEX ix_chatbots_owner_id ON chatbots (owner_id)")
    op.execute("""
CREATE TABLE documents (
	knowledge_base_id UUID NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	storage_key VARCHAR(100) NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	size INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	error VARCHAR(300), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (knowledge_base_id, sha256), 
	FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	UNIQUE (storage_key)
)
""")
    op.execute("CREATE INDEX ix_documents_knowledge_base_id ON documents (knowledge_base_id)")
    op.execute("""
CREATE TABLE chatbot_prompt_versions (
	chatbot_id UUID NOT NULL, 
	content TEXT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE
)
""")
    op.execute(
        "CREATE INDEX ix_chatbot_prompt_versions_chatbot_id ON chatbot_prompt_versions (chatbot_id)"
    )
    op.execute("""
CREATE TABLE conversations (
	owner_id UUID NOT NULL, 
	chatbot_id UUID NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	busy_until TIMESTAMP WITH TIME ZONE, 
	run_token UUID, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE CASCADE
)
""")
    op.execute("CREATE INDEX ix_conversations_chatbot_id ON conversations (chatbot_id)")
    op.execute("CREATE INDEX ix_conversations_owner_id ON conversations (owner_id)")
    op.execute("""
CREATE TABLE document_chunks (
	document_id UUID NOT NULL, 
	knowledge_base_id UUID NOT NULL, 
	embedding_id UUID NOT NULL, 
	generation INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	page INTEGER, 
	chunk_index INTEGER NOT NULL, 
	embedding VECTOR NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id, chunk_index), 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	FOREIGN KEY(embedding_id) REFERENCES embedding_models (id) ON DELETE RESTRICT
)
""")
    op.execute(
        "CREATE INDEX ix_chunks_space ON document_chunks (knowledge_base_id, embedding_id, generation)"
    )
    op.execute("CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id)")
    op.execute(
        "CREATE INDEX ix_document_chunks_knowledge_base_id ON document_chunks (knowledge_base_id)"
    )
    op.execute("""
CREATE TABLE document_processing_jobs (
	document_id UUID NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	attempts INTEGER NOT NULL, 
	available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	lease_until TIMESTAMP WITH TIME ZONE, 
	lease_token UUID, 
	error VARCHAR(300), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (document_id), 
	FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
)
""")
    op.execute(
        "CREATE INDEX ix_document_processing_jobs_status ON document_processing_jobs (status)"
    )
    op.execute("""
CREATE TABLE model_usage_logs (
	owner_id UUID NOT NULL, 
	chatbot_id UUID, 
	model_id UUID, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	latency_ms INTEGER NOT NULL, 
	cost FLOAT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(chatbot_id) REFERENCES chatbots (id) ON DELETE SET NULL, 
	FOREIGN KEY(model_id) REFERENCES ai_models (id) ON DELETE SET NULL
)
""")
    op.execute("CREATE INDEX ix_model_usage_logs_owner_id ON model_usage_logs (owner_id)")
    op.execute("""
CREATE TABLE messages (
	conversation_id UUID NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	content TEXT NOT NULL, 
	sources JSONB NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
)
""")
    op.execute("CREATE INDEX ix_messages_conversation_id ON messages (conversation_id)")


def downgrade():
    op.execute("DROP TABLE messages")
    op.execute("DROP TABLE model_usage_logs")
    op.execute("DROP TABLE document_processing_jobs")
    op.execute("DROP TABLE document_chunks")
    op.execute("DROP TABLE conversations")
    op.execute("DROP TABLE chatbot_prompt_versions")
    op.execute("DROP TABLE documents")
    op.execute("DROP TABLE chatbots")
    op.execute("DROP TABLE knowledge_bases")
    op.execute("DROP TABLE refresh_tokens")
    op.execute("DROP TABLE embedding_models")
    op.execute("DROP TABLE ai_models")
    op.execute("DROP TABLE users")
    op.execute("DROP TABLE ai_providers")
