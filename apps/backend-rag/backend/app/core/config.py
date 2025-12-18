"""
NUZANTARA PRIME - Centralized Configuration
All environment variables centralized using pydantic-settings
"""

import logging
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables - Prime Standard"""

    # ========================================
    # PROJECT CONFIGURATION
    # ========================================
    PROJECT_NAME: str = "Nuzantara Prime"
    API_V1_STR: str = "/api/v1"
    environment: str = "development"  # Set via ENVIRONMENT env var (production/development)

    # ========================================
    # EMBEDDINGS CONFIGURATION
    # ========================================
    embedding_provider: str = "openai"  # OpenAI for production (1536-dim)
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key - REQUIRED for embeddings. Set via OPENAI_API_KEY env var",
    )
    google_api_key: str | None = None  # Set via GOOGLE_API_KEY env var (for Gemini AI)
    google_imagen_api_key: str | None = (
        None  # Set via GOOGLE_IMAGEN_API_KEY env var (for Imagen image generation)
    )
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536  # Matches migrated collections

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def validate_openai_api_key(cls, v):
        """Validate OpenAI API key - warn if missing in production"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                import warnings

                warnings.warn(
                    "OPENAI_API_KEY not set in production. Embeddings will fail.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
                logger = logging.getLogger(__name__)
                logger.warning(
                    "⚠️ OPENAI_API_KEY not set - embeddings may fail. "
                    "Set OPENAI_API_KEY env var for production."
                )
        elif v and not v.startswith("sk-"):
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ OPENAI_API_KEY format may be invalid (should start with 'sk-')")

        return v

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def set_dimensions_from_provider(cls, _v, info):
        """Automatically set embedding dimensions based on provider"""
        provider = info.data.get("embedding_provider", "openai")
        if provider == "openai":
            return 1536  # OpenAI text-embedding-3-small
        return 384  # sentence-transformers fallback

    # ========================================
    # ZANTARA AI CONFIGURATION (PRIMARY)
    # ========================================
    zantara_ai_model: str = "gpt-4o-mini"  # Set via ZANTARA_AI_MODEL
    zantara_ai_cost_input: float = 0.15  # Cost per 1M input tokens (GPT-4o-mini)
    zantara_ai_cost_output: float = 0.60  # Cost per 1M output tokens (GPT-4o-mini)
    openrouter_api_key: str | None = None  # Set via OPENROUTER_API_KEY env var (free AI fallback)
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API Key")

    # ========================================
    # QDRANT VECTOR DATABASE
    # ========================================
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant URL - Set via QDRANT_URL env var (default: localhost for development)",
    )

    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, v):
        """Validate Qdrant URL format - fail in production if invalid"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                raise ValueError(
                    "QDRANT_URL must be set in production. "
                    "Set QDRANT_URL env var to your Qdrant instance URL."
                )
            logger = logging.getLogger(__name__)
            logger.warning(
                "⚠️ QDRANT_URL not set - using default localhost. "
                "Set QDRANT_URL env var for production."
            )
            return "http://localhost:6333"

        if not v.startswith(("http://", "https://")):
            raise ValueError("QDRANT_URL must be a valid HTTP(S) URL")

        return v

    qdrant_api_key: str | None = None  # Set via QDRANT_API_KEY env var
    qdrant_collection_name: str = "knowledge_base"

    # ========================================
    # CHUNKING CONFIGURATION
    # ========================================
    chunk_size: int = 500
    chunk_overlap: int = 50
    max_chunks_per_book: int = 1000

    # ========================================
    # API CONFIGURATION
    # ========================================
    api_host: str = "0.0.0.0"
    api_port: int = 8080  # Use PORT env var (default 8080 for Fly.io)
    api_reload: bool = True

    # ========================================
    # TIMEOUT CONFIGURATION (Centralized)
    # ========================================
    timeout_default: float = 30.0  # Default timeout for API calls
    timeout_ai_response: float = 60.0  # AI response timeout
    timeout_rag_query: float = 10.0  # RAG query timeout
    timeout_tool_execution: float = 30.0  # Tool execution timeout
    timeout_streaming: float = 120.0  # Streaming timeout
    timeout_internal_api: float = 5.0  # Internal API calls timeout
    latency_alert_threshold_ms: float = 20000.0  # Alert if request takes longer than 20s

    # ========================================
    # RERANKER CONFIGURATION
    # ========================================
    enable_reranker: bool = False  # DISABLED: Saves ~5GB Docker image size
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_k: int = 5
    reranker_latency_target_ms: float = 50.0
    reranker_cache_enabled: bool = True
    reranker_cache_size: int = 1000
    reranker_batch_enabled: bool = True
    reranker_audit_enabled: bool = True
    reranker_rate_limit_per_minute: int = 100
    reranker_rate_limit_per_hour: int = 1000
    reranker_overfetch_count: int = 20
    reranker_return_count: int = 5

    # Ze-Rank 2 Configuration (External API)
    zerank_api_key: str | None = Field(
        default=None, description="Ze-Rank 2 API Key - Set via ZERANK_API_KEY env var"
    )
    zerank_api_url: str = Field(
        default="https://api.zerank.com/v2/rerank",
        description="Ze-Rank 2 API URL - Set via ZERANK_API_URL env var",
    )

    # ========================================
    # SEARCH CONFIGURATION
    # ========================================
    search_enable_filters: bool = Field(
        default=False,
        description="Enable tier/exclude_repealed filters in SearchService.search() by default. "
        "Set via SEARCH_ENABLE_FILTERS env var. When False (default), filters are disabled "
        "for backward compatibility with chat path. Individual calls can override via apply_filters parameter.",
    )

    # ========================================
    # LOGGING CONFIGURATION
    # ========================================
    log_level: str = "INFO"
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode (set via DEBUG_MODE env var). Disables in production.",
    )

    @field_validator("debug_mode", mode="before")
    @classmethod
    def validate_debug_mode(cls, v):
        """Validate debug mode - disable in production"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if is_production and v:
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ DEBUG_MODE cannot be enabled in production. Forcing to False.")
            return False

        return bool(v) if v is not None else False
    log_file: str = "./data/zantara_rag.log"

    # ========================================
    # DATA DIRECTORIES
    # ========================================
    raw_books_dir: str = "./data/raw_books"
    processed_dir: str = "./data/processed"
    batch_size: int = 10

    # ========================================
    # TIER OVERRIDES (Optional)
    # ========================================
    tier_overrides: str | None = None

    # ========================================
    # DATABASE CONFIGURATION
    # ========================================
    database_url: str | None = None  # Set via DATABASE_URL env var

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        """Validate database URL - warn if missing in production"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v and is_production:
            # In production, database is usually required but some services might work without it
            # So we warn but don't fail
            import warnings

            warnings.warn(
                "DATABASE_URL not set in production. Some features may be unavailable.",
                UserWarning,
                stacklevel=2,
            )

        # Fix for SQLAlchemy: replace postgres:// with postgresql://
        # Fly.io/Heroku often use postgres:// which is deprecated/unsupported in SQLAlchemy 1.4+
        if v and v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)

        return v

    # ========================================
    # REDIS CONFIGURATION
    # ========================================
    redis_url: str | None = None  # Set via REDIS_URL env var

    # ========================================
    # AUTHENTICATION CONFIGURATION
    # ========================================
    jwt_secret_key: str | None = Field(
        default=None,
        description=(
            "JWT secret key - REQUIRED: Set via JWT_SECRET_KEY env var. "
            "SECURITY: Default dev key only allowed in development mode. "
            "Production will fail if not explicitly set."
        ),
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v):
        """
        Validate JWT secret key - fail in production if not set

        SECURITY: Default dev key is only provided in development mode.
        Production requires explicit JWT_SECRET_KEY environment variable.
        """
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                raise ValueError(
                    "SECURITY ERROR: JWT_SECRET_KEY must be set in production environment. "
                    "Set ENVIRONMENT=production and provide JWT_SECRET_KEY secret."
                )
            # SECURITY: Only allow default dev key in development/testing
            # This prevents accidental use of weak keys in production
            logger = logging.getLogger(__name__)
            logger.warning(
                "⚠️ Using default JWT secret key for development. "
                "Set JWT_SECRET_KEY env var for production."
            )
            return "zantara_dev_secret_key_change_in_production_min_32_chars"

        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")

        if is_production and v == "zantara_dev_secret_key_change_in_production_min_32_chars":
            raise ValueError(
                "SECURITY ERROR: Cannot use default JWT secret key in production. "
                "Set JWT_SECRET_KEY to a secure random string (min 32 chars)."
            )

        return v

    # ========================================
    # API KEY AUTHENTICATION CONFIGURATION
    # ========================================
    api_keys: str | None = Field(
        default=None,
        description=(
            "API keys - REQUIRED: Set via API_KEYS env var (comma-separated). "
            "SECURITY: Default dev key only allowed in development mode. "
            "Production will fail if not explicitly set."
        ),
    )

    @field_validator("api_keys", mode="before")
    @classmethod
    def validate_api_keys(cls, v):
        """
        Validate API keys - fail in production if using default

        SECURITY: Default dev key is only provided in development mode.
        Production requires explicit API_KEYS environment variable.
        """
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                raise ValueError(
                    "SECURITY ERROR: API_KEYS must be set in production environment. "
                    "Provide comma-separated list of secure API keys."
                )
            # SECURITY: Only allow default dev key in development/testing
            logger = logging.getLogger(__name__)
            logger.warning(
                "⚠️ Using default API key for development. Set API_KEYS env var for production."
            )
            return "dev_api_key_for_testing_only"

        if is_production and v == "dev_api_key_for_testing_only":
            raise ValueError(
                "SECURITY ERROR: Cannot use default API key in production. "
                "Set API_KEYS to secure comma-separated keys."
            )

        return v

    api_auth_enabled: bool = True
    api_auth_bypass_db: bool = False  # Must be False to enable JWT auth

    # ========================================
    # COOKIE AUTHENTICATION CONFIGURATION
    # ========================================
    cookie_domain: str | None = Field(
        default=None,
        description=(
            "Cookie domain for cross-subdomain auth (e.g., '.balizero.com'). "
            "Set via COOKIE_DOMAIN env var. None for localhost."
        ),
    )
    cookie_secure: bool = Field(
        default=True,
        description="Use Secure flag for cookies (HTTPS only). Set via COOKIE_SECURE env var.",
    )
    csrf_enabled: bool = Field(
        default=True,
        description="Enable CSRF protection for state-changing requests. Set via CSRF_ENABLED env var.",
    )

    # ========================================
    # LEGACY REMOVED: TypeScript Backend Integration
    # All handlers migrated to Python services (GmailService, CalendarService, etc.)
    # ========================================

    # ========================================
    # CORS CONFIGURATION
    # ========================================
    zantara_allowed_origins: str | None = (
        None  # Comma-separated list, set via ZANTARA_ALLOWED_ORIGINS
    )

    # ========================================
    # FEATURE FLAGS
    # ========================================
    enable_skill_detection: bool = False  # Set via ENABLE_SKILL_DETECTION env var
    enable_collective_memory: bool = False  # Set via ENABLE_COLLECTIVE_MEMORY env var
    enable_advanced_analytics: bool = False  # Set via ENABLE_ADVANCED_ANALYTICS env var
    enable_tool_execution: bool = False  # Set via ENABLE_TOOL_EXECUTION env var

    # ========================================
    # NOTIFICATION SERVICES
    # ========================================
    sendgrid_api_key: str | None = None  # Set via SENDGRID_API_KEY env var
    smtp_host: str | None = None  # Set via SMTP_HOST env var
    smtp_port: int = Field(default=587, description="SMTP port (default: 587)")
    smtp_user: str | None = None  # Set via SMTP_USER env var
    smtp_password: str | None = None  # Set via SMTP_PASSWORD env var
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP (default: True)")
    smtp_from: str | None = None  # Set via SMTP_FROM env var (sender email address)
    twilio_account_sid: str | None = None  # Set via TWILIO_ACCOUNT_SID env var
    twilio_auth_token: str | None = None  # Set via TWILIO_AUTH_TOKEN env var
    twilio_whatsapp_number: str | None = None  # Set via TWILIO_WHATSAPP_NUMBER env var
    twilio_phone_number: str | None = None  # Set via TWILIO_PHONE_NUMBER env var (for SMS)
    slack_webhook_url: str | None = None  # Set via SLACK_WEBHOOK_URL env var
    discord_webhook_url: str | None = None  # Set via DISCORD_WEBHOOK_URL env var

    # ========================================
    # META WHATSAPP CONFIGURATION
    # ========================================
    whatsapp_verify_token: str = Field(
        default="dev_whatsapp_token_for_testing",
        description=(
            "WhatsApp webhook verify token - Set via WHATSAPP_VERIFY_TOKEN env var "
            "(default: dev token for testing only)"
        ),
    )

    @field_validator("whatsapp_verify_token", mode="before")
    @classmethod
    def validate_whatsapp_token(cls, v):
        """Validate WhatsApp token - warn in production if using default"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                raise ValueError(
                    "WHATSAPP_VERIFY_TOKEN must be set in production. "
                    "Provide a secure random token."
                )
            return "dev_whatsapp_token_for_testing"

        if is_production and v == "dev_whatsapp_token_for_testing":
            raise ValueError(
                "Cannot use default WhatsApp verify token in production. "
                "Set WHATSAPP_VERIFY_TOKEN to a secure random string."
            )

        return v

    whatsapp_access_token: str | None = None  # Set via WHATSAPP_ACCESS_TOKEN env var
    whatsapp_phone_number_id: str | None = None  # Set via WHATSAPP_PHONE_NUMBER_ID env var
    whatsapp_business_account_id: str | None = None  # Set via WHATSAPP_BUSINESS_ACCOUNT_ID env var

    # ========================================
    # META INSTAGRAM CONFIGURATION
    # ========================================
    instagram_verify_token: str = Field(
        default="dev_instagram_token_for_testing",
        description=(
            "Instagram webhook verify token - Set via INSTAGRAM_VERIFY_TOKEN env var "
            "(default: dev token for testing only)"
        ),
    )

    @field_validator("instagram_verify_token", mode="before")
    @classmethod
    def validate_instagram_token(cls, v):
        """Validate Instagram token - warn in production if using default"""
        env = os.getenv("ENVIRONMENT", "development")
        is_production = env.lower() == "production"

        if not v:
            if is_production:
                raise ValueError(
                    "INSTAGRAM_VERIFY_TOKEN must be set in production. "
                    "Provide a secure random token."
                )
            return "dev_instagram_token_for_testing"

        if is_production and v == "dev_instagram_token_for_testing":
            raise ValueError(
                "Cannot use default Instagram verify token in production. "
                "Set INSTAGRAM_VERIFY_TOKEN to a secure random string."
            )

        return v

    instagram_access_token: str | None = None  # Set via INSTAGRAM_ACCESS_TOKEN env var
    instagram_account_id: str | None = None  # Set via INSTAGRAM_ACCOUNT_ID env var

    # ========================================
    # ORACLE CONFIGURATION
    # ========================================
    zantara_oracle_url: str = Field(
        default="http://localhost:11434/api/generate",
        description="ZANTARA Oracle API URL (set via ZANTARA_ORACLE_URL env var)",
    )

    # Development origins (for local testing)
    dev_origins: str = Field(
        default=(
            "http://localhost:4173,http://127.0.0.1:4173,"
            "http://localhost:3000,http://127.0.0.1:3000"
        ),
        description=(
            "Comma-separated list of development origins for CORS (set via DEV_ORIGINS env var)"
        ),
    )
    oracle_api_key: str | None = None  # Set via ORACLE_API_KEY env var

    # ========================================
    # ADMIN CONFIGURATION
    # ========================================
    admin_api_key: str | None = Field(
        None,
        description="Admin API key for plugin reload and admin endpoints (set via ADMIN_API_KEY env var)",
    )

    # ========================================
    # GOOGLE SERVICES CONFIGURATION
    # ========================================
    google_api_key: str | None = None  # Set via GOOGLE_API_KEY env var
    google_credentials_json: str | None = None  # Set via GOOGLE_CREDENTIALS_JSON env var
    hf_api_key: str | None = None  # Set via HF_API_KEY env var

    # ========================================
    # JAKSEL AI PERSONALITY SYSTEM
    # ========================================
    jaksel_oracle_url: str | None = None  # Set via JAKSEL_ORACLE_URL env var
    jaksel_tunnel_url: str | None = None  # Set via JAKSEL_TUNNEL_URL env var
    jaksel_enabled: bool = True  # Feature flag (set via JAKSEL_ENABLED env var)
    jaksel_local_url: str = "http://127.0.0.1:11434"  # Local development only

    # ========================================
    # FLY.IO DEPLOYMENT
    # ========================================
    fly_app_name: str | None = None  # Set via FLY_APP_NAME env var
    fly_region: str | None = None  # Set via FLY_REGION env var
    hostname: str | None = None  # Set via HOSTNAME env var
    port: int = 8080  # Set via PORT env var (Fly.io default)

    # ========================================
    # SERVICE CONFIGURATION
    # ========================================
    service_name: str = "nuzantara-rag"  # Set via SERVICE_NAME env var

    class Config:
        # Load .env file for local development, but allow env vars to override
        # In production (Fly.io), use environment variables/secrets only
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields


# Global settings instance
settings = Settings()
