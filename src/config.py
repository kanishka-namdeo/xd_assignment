"""Global configuration (pydantic-settings BaseSettings)."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres123@localhost:5432/social_support"
    STATEMENT_TIMEOUT: int = 30000  # milliseconds

    # LLM Provider
    LLM_PROVIDER: str = "streamlake"  # "ollama" or "streamlake"
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_API_KEY: str = "ollama"
    OLLAMA_MODEL: str = "qwen3.5:14b"
    STREAMLAKE_BASE_URL: str = "https://vanchin.streamlake.ai/api/gateway/coding/v1"
    STREAMLAKE_API_KEY: SecretStr = SecretStr("")
    STREAMLAKE_MODEL: str = "kat-coder-pro-v2.5"

    # LLM Behavior
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int | None = None
    LLM_TIMEOUT: int = 30  # seconds
    LLM_MAX_RETRIES: int = 3

    # Embeddings
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text:v1.5"
    EMBEDDING_DIMENSION: int = 768

    # Langfuse
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_PUBLIC_KEY: SecretStr = SecretStr("")
    LANGFUSE_SECRET_KEY: SecretStr = SecretStr("")
    LANGFUSE_HOST: str = "http://localhost:4000"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "change_me_to_strong_password"
    NEO4J_DATABASE: str = "neo4j"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_PREFER_GRPC: bool = True
    QDRANT_GRPC_PORT: int = 6334


settings = Settings()
