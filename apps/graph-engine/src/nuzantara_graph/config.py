"""Application configuration via Pydantic BaseSettings."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NUZANTARA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "nuzantara-graph-engine"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development | staging | production

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # LLM
    openai_api_key: str = ""
    google_api_key: str = ""
    primary_model: str = "gemini-2.0-flash"
    fallback_model: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-3-small"  # FROZEN — never change

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/nuzantara_v6"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Graph
    max_corrections: int = 2
    retrieval_top_k: int = 10
    rerank_top_k: int = 5
    semantic_cache_ttl_seconds: int = 3600
    checkpointer_enabled: bool = Field(
        default=False,
        description="Enable LangGraph checkpoint persistence. Disabled by default to avoid DB writes.",
    )
    checkpointer_backend: Literal["postgres", "memory"] = Field(
        default="postgres",
        description="Checkpoint backend. 'memory' is explicit test/dev only.",
    )
    checkpointer_database_url: str = Field(
        default="",
        description="Dedicated PostgreSQL URL for LangGraph checkpoints.",
    )
    checkpointer_postgres_pipeline: bool = Field(
        default=True,
        description="Use psycopg pipeline mode for PostgresSaver writes.",
    )

    # Auth
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"

    # Observability
    otel_endpoint: str = ""
    log_level: str = "INFO"

    # Rate limiting
    rate_limit_rpm: int = Field(default=60, description="Requests per minute per user")


settings = Settings()
