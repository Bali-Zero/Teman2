"""
NUZANTARA PRIME - Centralized Configuration
All environment variables centralized using pydantic-settings
"""

import logging
import os
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables - Prime Standard"""

    # ========================================
    # PROJECT CONFIGURATION
    # ========================================
    PROJECT_NAME: str = "Nuzantara Prime"
    COMPANY_NAME: str = "Bali Zero"
    COMPANY_LOCATION: str = "Jalan Semer, Kerobokan, Bali"
    COMPANY_SERVICE_DOMAIN: str = "Visas, Business Setup, Tax, Legal matters in Indonesia"
    SUPPORT_EMAIL: str = "info@balizero.com"
    SUPPORT_WHATSAPP: str = "+62 813 3805 1876"
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
    google_credentials_json: str | None = Field(
        default=None,
        description="Google Service Account JSON credentials. Set via GOOGLE_CREDENTIALS_JSON, GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SERVICE_ACCOUNT, or GEMINI_SA_TOKEN env var",
    )
    gemini_sa_token: str | None = None  # Alias for GEMINI_SA_TOKEN env var

    @field_validator("google_credentials_json", mode="before")
    @classmethod
    def resolve_google_credentials(cls, v: Any) -> Any:
        """Resolve Google credentials from multiple env vars."""
        import os

        if v:
            return v
        # Check alternative env var names (in priority order)
        google_sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if google_sa_json:
            return google_sa_json
        google_sa = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
        if google_sa:
            return google_sa
        gemini_token = os.environ.get("GEMINI_SA_TOKEN")
        if gemini_token:
            return gemini_token
        return None

    google_imagen_api_key: str | None = (
        None  # Set via GOOGLE_IMAGEN_API_KEY env var (for Imagen image generation)
    )
    google_ai_studio_key: str | None = (
        None  # Set via GOOGLE_AI_STUDIO_KEY env var (Google AI Studio with Ultra tier)
    )
    imagineart_api_key: str | None = None  # Set via IMAGINEART_API_KEY env var (for ImagineArt)
    stability_api_key: str | None = None  # Set via STABILITY_API_KEY env var (for Stability AI)
    brave_api_key: str | None = None  # Set via BRAVE_API_KEY env var (for Brave Web Search)
    tavily_api_key: str | None = (
        None  # Set via TAVILY_API_KEY env var (for Tavily AI Search - preferred)
    )
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536  # Matches migrated collections

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def validate_openai_api_key(cls, v: Any) -> Any:
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
    def set_dimensions_from_provider(cls, _v: Any, info: Any) -> Any:
        """Automatically set embedding dimensions based on provider"""
        provider = info.data.get("embedding_provider", "openai")
        if provider == "openai":
            return 1536  # OpenAI text-embedding-3-small
        return 384  # sentence-transformers fallback

    # ========================================
    # ZANTARA AI CONFIGURATION (PRIMARY)
    # ========================================
    zantara_ai_model: str = "gemini-2.5-flash"  # Set via ZANTARA_AI_MODEL
    zantara_ai_cost_input: float = 0.00  # Preview is free? Or check updated pricing.
    zantara_ai_cost_output: float = 0.00  # Preview is free? Or check updated pricing.
    openrouter_api_key: str | None = None  # Set via OPENROUTER_API_KEY env var (free AI fallback)
    deepseek_api_key: str | None = Field(default=None, description="DeepSeek API Key")
    ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API URL - Set via OLLAMA_URL env var (default: localhost for local Ollama)",
    )
    ollama_model: str = Field(
        default="deepseek-r1",
        description="Ollama model name - Set via OLLAMA_MODEL env var (default: deepseek-r1)",
    )

    # ========================================
    # QDRANT VECTOR DATABASE
    # ========================================
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant URL - Set via QDRANT_URL env var (default: localhost for development)",
    )

    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, v: Any) -> Any:
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
    api_host: str = "::"
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
    latency_alert_threshold_ms: float = (
        8000.0  # Alert if request takes longer than 8s (RAG target: <3s)
    )
    memory_alert_threshold_percent: float = 80.0  # Alert if memory usage exceeds 80% of available
    cpu_alert_threshold_percent: float = 90.0  # Alert if CPU exceeds 90% sustained

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

    # ZeroEntropy Re-ranker Configuration (External API)
    zerank_api_key: str | None = Field(
        default=None, description="ZeroEntropy API Key - Set via ZERANK_API_KEY env var"
    )
    zerank_api_url: str = Field(
        default="https://api.zeroentropy.dev/v1/models/rerank",
        description="ZeroEntropy Re-ranker API URL - Set via ZERANK_API_URL env var",
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
    # BM25 HYBRID SEARCH CONFIGURATION
    # ========================================
    enable_hybrid_search: bool = Field(
        default=False,
        description="Enable hybrid search (BM25+dense+RRF+reranking) in the agentic VectorSearchTool pipeline. "
        "Set via ENABLE_HYBRID_SEARCH env var. When False, uses dense-only search with legacy reranker.",
    )
    enable_query_expansion: bool = Field(
        default=False,
        description="Enable LLM-based multi-query expansion for complex queries (>5 words). "
        "Uses Gemini Flash to generate 2-3 alternative queries, then RRF-fuses results. "
        "Set via ENABLE_QUERY_EXPANSION env var. Adds ~200ms latency but improves recall.",
    )
    enable_bm25: bool = Field(
        default=True,
        description="Enable BM25 sparse vectors for hybrid search. Set via ENABLE_BM25 env var.",
    )
    bm25_vocab_size: int = Field(
        default=30000,
        description="Hash space size for BM25 token IDs. Set via BM25_VOCAB_SIZE env var.",
    )
    bm25_k1: float = Field(
        default=1.5,
        description="BM25 term frequency saturation parameter. Set via BM25_K1 env var.",
    )
    bm25_b: float = Field(
        default=0.75,
        description="BM25 document length normalization parameter. Set via BM25_B env var.",
    )
    hybrid_dense_weight: float = Field(
        default=0.7,
        description="Weight for dense vectors in hybrid search (0-1). Set via HYBRID_DENSE_WEIGHT env var.",
    )
    hybrid_sparse_weight: float = Field(
        default=0.3,
        description="Weight for sparse vectors in hybrid search (0-1). Set via HYBRID_SPARSE_WEIGHT env var.",
    )

    # ========================================
    # QUERY EXPANSION CONFIGURATION
    # ========================================
    query_expansion_enabled: bool = Field(
        default=True,
        description="Enable multilingual query expansion for better RAG matching. Set via QUERY_EXPANSION_ENABLED env var.",
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
    def validate_debug_mode(cls, v: Any) -> Any:
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
    # OPENTELEMETRY / JAEGER TRACING
    # ========================================
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing. Set via OTEL_ENABLED env var.",
    )
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317",
        description=(
            "OTLP exporter endpoint for Jaeger. Set via OTEL_EXPORTER_ENDPOINT env var. "
            "Use http://localhost:4317 for local dev, http://jaeger:4317 for Docker."
        ),
    )
    otel_service_name: str = Field(
        default="nuzantara-backend",
        description="Service name for tracing. Set via OTEL_SERVICE_NAME env var.",
    )
    otel_exporter_headers: str | None = Field(
        default=None,
        description=(
            "OTLP exporter headers for authentication. Set via OTEL_EXPORTER_HEADERS env var. "
            "Format: 'Authorization=Basic <token>' for Grafana Cloud."
        ),
    )

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
    def validate_database_url(cls, v: Any) -> Any:
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
    def validate_jwt_secret(cls, v: Any) -> Any:
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
    intel_scraper_api_key: str = Field(
        default="dev_scraper_key",
        description="API key for internal scraper poller. Set via INTEL_SCRAPER_API_KEY env var.",
    )

    @field_validator("api_keys", mode="before")
    @classmethod
    def validate_api_keys(cls, v: Any) -> Any:
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
    # GITHUB PUBLISHING CONFIGURATION
    # ========================================
    github_token: str | None = Field(
        default=None,
        description="GitHub Personal Access Token for publishing articles. Set via GITHUB_TOKEN env var.",
    )
    github_owner: str = Field(
        default="Balizero1987",
        description="GitHub repository owner. Set via GITHUB_OWNER env var.",
    )
    github_repo: str = Field(
        default="Teman2",
        description="GitHub repository name. Set via GITHUB_REPO env var.",
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
    def validate_whatsapp_token(cls, v: Any) -> Any:
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

    whatsapp_api_token: str | None = Field(
        default=None,
        description="WhatsApp Cloud API access token from Meta Business. Set via WHATSAPP_API_TOKEN env var.",
    )
    whatsapp_phone_number_id: str | None = Field(
        default=None,
        description="WhatsApp Business Phone Number ID from Meta. Set via WHATSAPP_PHONE_NUMBER_ID env var.",
    )
    whatsapp_business_account_id: str | None = Field(
        default=None,
        description="WhatsApp Business Account ID from Meta. Set via WHATSAPP_BUSINESS_ACCOUNT_ID env var.",
    )
    whatsapp_personal_contacts: str | None = Field(
        default=None,
        description=(
            "Comma-separated list of personal contact phone numbers (no + prefix). "
            "Messages from these numbers will always escalate to human. "
            "Set via WHATSAPP_PERSONAL_CONTACTS env var. "
            "Example: '393471234567,628123456789'"
        ),
    )
    whatsapp_allowed_numbers: str | None = Field(
        default=None,
        description=(
            "Comma-separated whitelist of phone numbers allowed to interact with WhatsApp bot (no + prefix). "
            "If set, messages from numbers NOT in this list are silently ignored (no response sent). "
            "Set via WHATSAPP_ALLOWED_NUMBERS env var. "
            "Example: '628213107363' — leave empty to allow everyone."
        ),
    )

    # ========================================
    # TELEGRAM BOT CONFIGURATION
    # ========================================
    telegram_bot_token: str | None = Field(
        default=None,
        description="Telegram bot token for sending notifications. Set via TELEGRAM_BOT_TOKEN env var.",
    )
    admin_telegram_chat_id: str | None = Field(
        default=None,
        description="Admin Telegram chat ID for WhatsApp escalation notifications. Set via ADMIN_TELEGRAM_CHAT_ID env var.",
    )

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
    def validate_instagram_token(cls, v: Any) -> Any:
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
    # X/TWITTER INTEGRATION
    # ========================================
    x_consumer_key: str | None = None  # Set via X_CONSUMER_KEY env var
    x_consumer_secret: str | None = None  # Set via X_CONSUMER_SECRET env var
    x_access_token: str | None = None  # Set via X_ACCESS_TOKEN env var
    x_access_token_secret: str | None = None  # Set via X_ACCESS_TOKEN_SECRET env var
    x_bearer_token: str | None = None  # Set via X_BEARER_TOKEN env var
    x_client_id: str | None = None  # Set via X_CLIENT_ID env var
    x_client_secret: str | None = None  # Set via X_CLIENT_SECRET env var
    x_webhook_secret: str | None = None  # Set via X_WEBHOOK_SECRET env var (CRC token)

    # X/Twitter Social Listening Monitor
    x_monitor_enabled: bool = False  # Set via X_MONITOR_ENABLED env var
    x_monitor_interval_seconds: int = 300  # 5 minutes, set via X_MONITOR_INTERVAL_SECONDS
    x_monitor_keywords: str = "PT PMA Bali,KITAS Bali,KITAS Indonesia,KITAP Indonesia,business in Bali,Bali visa,move to Bali,living in Bali,invest in Bali,open company Bali,company in Bali,work permit Bali,digital nomad Bali"
    x_monitor_digest_interval_hours: int = 3  # Send Telegram digest every N hours
    x_monitor_digest_enabled: bool = True  # Enable/disable digest on Telegram

    # ========================================
    # ZOHO EMAIL INTEGRATION
    # ========================================
    zoho_client_id: str | None = None  # Set via ZOHO_CLIENT_ID env var
    zoho_client_secret: str | None = None  # Set via ZOHO_CLIENT_SECRET env var
    zoho_redirect_uri: str = Field(
        default="https://nuzantara-rag.fly.dev/api/integrations/zoho/callback",
        description="Zoho OAuth redirect URI (set via ZOHO_REDIRECT_URI env var)",
    )
    frontend_url: str = Field(
        default="https://kita.balizero.com",
        description="Frontend URL for OAuth redirects (set via FRONTEND_URL env var)",
    )
    zoho_api_domain: str = Field(
        default="https://mail.zoho.com",
        description="Zoho Mail API domain - regional (set via ZOHO_API_DOMAIN env var)",
    )
    zoho_accounts_url: str = Field(
        default="https://accounts.zoho.com",
        description="Zoho Accounts URL for OAuth (set via ZOHO_ACCOUNTS_URL env var)",
    )

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
    # google_api_key: str | None = None  # Already defined in EMBEDDINGS CONFIGURATION

    # ========================================
    # GOOGLE DRIVE OAUTH CONFIGURATION
    # ========================================
    google_drive_client_id: str | None = None  # Set via GOOGLE_DRIVE_CLIENT_ID env var
    google_drive_client_secret: str | None = None  # Set via GOOGLE_DRIVE_CLIENT_SECRET env var
    google_drive_redirect_uri: str = (
        "https://nuzantara-rag.fly.dev/api/integrations/google-drive/callback"
    )
    google_drive_root_folder_id: str | None = (
        None  # Set via GOOGLE_DRIVE_ROOT_FOLDER_ID env var (team root folder)
    )
    gdrive_individuals_folder_id: str | None = (
        None  # Set via GDRIVE_INDIVIDUALS_FOLDER_ID env var (parent for individual clients)
    )
    gdrive_companies_folder_id: str | None = (
        None  # Set via GDRIVE_COMPANIES_FOLDER_ID env var (parent for company clients)
    )
    hf_api_key: str | None = None  # Set via HF_API_KEY env var

    # ========================================
    # JAKSEL AI PERSONALITY SYSTEM
    # ========================================
    jaksel_oracle_url: str | None = None  # Set via JAKSEL_ORACLE_URL env var
    jaksel_tunnel_url: str | None = None  # Set via JAKSEL_TUNNEL_URL env var
    jaksel_enabled: bool = True  # Feature flag (set via JAKSEL_ENABLED env var)
    jaksel_local_url: str = "http://127.0.0.1:11434"  # Local development only

    # ========================================
    # JURNAL.ID INTEGRATION (LKPM)
    # ========================================
    jurnal_api_key: str | None = None  # Set via JURNAL_API_KEY env var
    jurnal_api_url: str = Field(
        default="https://api.jurnal.id/core/api/v1",
        description="Jurnal.id API base URL. Set via JURNAL_API_URL env var",
    )

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

    # ========================================
    # EXTERNAL SERVICE URLS
    # ========================================
    indexnow_api_url: str = Field(
        default="https://api.indexnow.org/indexnow",
        description="IndexNow API URL for search engine indexing. Set via INDEXNOW_API_URL env var",
    )
    google_indexing_api_url: str = Field(
        default="https://indexing.googleapis.com/v3/urlNotifications:publish",
        description="Google Indexing API URL for search console notifications. Set via GOOGLE_INDEXING_API_URL env var",
    )
    backend_url: str = Field(
        default="https://nuzantara-rag.fly.dev",
        description="Backend API base URL. Set via BACKEND_URL env var (default: production Fly.io URL)",
    )
    frontend_portal_url: str = Field(
        default="https://nuzantara-mouth.vercel.app",
        description="Frontend portal base URL for client invitations. Set via FRONTEND_PORTAL_URL env var",
    )
    balizero_website_url: str = Field(
        default="https://balizero.com",
        description="Bali Zero public website URL for article publishing. Set via BALIZERO_WEBSITE_URL env var",
    )
    qdrant_default_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant fallback URL when QDRANT_URL is not set. Set via QDRANT_DEFAULT_URL env var",
    )

    # ========================================
    # FILE SYSTEM PATHS
    # ========================================
    # Intel staging directories
    # In production (Fly.io), use /data/staging (mounted volume)
    # In local dev, use /tmp/staging
    intel_staging_base_dir: str | None = Field(
        default=None,
        description="Base directory for Intel staging files. Defaults to /data/staging in production, /tmp/staging locally. Set via INTEL_STAGING_BASE_DIR env var",
    )
    intel_pending_path: str | None = Field(
        default=None,
        description="Path for pending Intel approval storage. Defaults to /tmp/pending_intel. Set via INTEL_PENDING_PATH env var",
    )

    # Allowed directories for VisionTool file access (security sandbox)
    vision_allowed_dirs: str = Field(
        default="/app/uploads,/tmp,/app/data",
        description="Comma-separated list of directories the VisionTool may access. Set via VISION_ALLOWED_DIRS env var",
    )

    @property
    def get_vision_allowed_dirs(self) -> list[str]:
        """Get list of allowed directories for VisionTool file access."""
        return [d.strip() for d in self.vision_allowed_dirs.split(",") if d.strip()]

    @property
    def get_intel_staging_base_dir(self) -> str:
        """Get Intel staging base directory with fallback logic."""
        if self.intel_staging_base_dir:
            return self.intel_staging_base_dir
        # Check if /data exists (production Fly.io volume)
        from pathlib import Path

        if Path("/data").exists():
            return "/data/staging"
        return "/tmp/staging"

    @property
    def get_intel_pending_path(self) -> str:
        """Get Intel pending path with fallback logic."""
        if self.intel_pending_path:
            return self.intel_pending_path
        return "/tmp/pending_intel"

    class Config:
        # Load .env file for local development, but allow env vars to override
        # In production (Fly.io), use environment variables/secrets only
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields


# Global settings instance
settings = Settings()
