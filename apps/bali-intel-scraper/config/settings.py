"""
Centralized configuration management for Bali Intel Scraper.

This module provides a centralized, type-safe configuration system
with environment-based overrides and validation.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Set


class Environment(str, Enum):
    """Application environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection configuration."""

    host: str = "localhost"
    port: int = 5432
    name: str = "bali_intel"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800

    @property
    def url(self) -> str:
        """Generate database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables."""
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgres"):
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            return cls(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                name=parsed.path.lstrip("/") if parsed.path else "bali_intel",
                user=parsed.username or "postgres",
                password=parsed.password or "",
                pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
                max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
                pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
                pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
            )
        
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            name=os.getenv("DB_NAME", "bali_intel"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
        )


@dataclass(frozen=True)
class RedisConfig:
    """Redis connection configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 5
    socket_connect_timeout: int = 5

    @property
    def url(self) -> str:
        """Generate Redis URL."""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            socket_connect_timeout=int(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
        )


@dataclass(frozen=True)
class ScrapingConfig:
    """Web scraping configuration."""

    # Concurrency
    max_concurrent_requests: int = 10
    max_concurrent_browsers: int = 5

    # Rate limiting
    requests_per_second: float = 2.0
    requests_per_minute: int = 60

    # Timeouts
    request_timeout: int = 30
    page_load_timeout: int = 30
    script_timeout: int = 10

    # Retries
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    max_retry_delay: float = 60.0

    # Browser settings
    headless: bool = True
    browser_type: str = "chromium"
    viewport_width: int = 1920
    viewport_height: int = 1080

    # Proxy settings
    proxy_rotation_enabled: bool = False
    proxy_list: List[str] = field(default_factory=list)

    # User agent rotation
    ua_rotation_enabled: bool = True

    # Content filtering
    min_content_length: int = 500
    max_content_length: int = 100_000

    @classmethod
    def from_env(cls) -> "ScrapingConfig":
        """Create config from environment variables."""
        return cls(
            max_concurrent_requests=int(os.getenv("SCRAPE_MAX_CONCURRENT", "10")),
            max_concurrent_browsers=int(os.getenv("SCRAPE_MAX_BROWSERS", "5")),
            requests_per_second=float(os.getenv("SCRAPE_RPS", "2.0")),
            requests_per_minute=int(os.getenv("SCRAPE_RPM", "60")),
            request_timeout=int(os.getenv("SCRAPE_TIMEOUT", "30")),
            max_retries=int(os.getenv("SCRAPE_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("SCRAPE_RETRY_DELAY", "1.0")),
            headless=os.getenv("SCRAPE_HEADLESS", "true").lower() == "true",
            proxy_rotation_enabled=os.getenv("PROXY_ROTATION", "false").lower()
            == "true",
            proxy_list=os.getenv("PROXY_LIST", "").split(",")
            if os.getenv("PROXY_LIST")
            else [],
        )


@dataclass(frozen=True)
class AIConfig:
    """AI/NLP service configuration."""

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_timeout: int = 60
    openai_max_retries: int = 3

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"
    anthropic_timeout: int = 60

    # Local models
    local_model_path: Optional[str] = None
    use_local_models: bool = False

    # Processing
    batch_size: int = 10
    max_tokens: int = 4000
    temperature: float = 0.1

    # Rate limiting
    ai_calls_per_minute: int = 100

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Create config from environment variables."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4"),
            openai_timeout=int(os.getenv("OPENAI_TIMEOUT", "60")),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
            local_model_path=os.getenv("LOCAL_MODEL_PATH"),
            use_local_models=os.getenv("USE_LOCAL_MODELS", "false").lower() == "true",
            batch_size=int(os.getenv("AI_BATCH_SIZE", "10")),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "4000")),
            temperature=float(os.getenv("AI_TEMPERATURE", "0.1")),
            ai_calls_per_minute=int(os.getenv("AI_RATE_LIMIT", "100")),
        )


@dataclass(frozen=True)
class MonitoringConfig:
    """Monitoring and observability configuration."""

    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "json"
    log_file: Optional[str] = None

    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Tracing
    tracing_enabled: bool = False
    jaeger_endpoint: Optional[str] = None

    # Alerting
    alert_webhook_url: Optional[str] = None
    alert_email: Optional[str] = None

    # Sentry
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Create config from environment variables."""
        return cls(
            log_level=LogLevel(os.getenv("LOG_LEVEL", "INFO")),
            log_format=os.getenv("LOG_FORMAT", "json"),
            log_file=os.getenv("LOG_FILE"),
            metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            metrics_port=int(os.getenv("METRICS_PORT", "9090")),
            tracing_enabled=os.getenv("TRACING_ENABLED", "false").lower() == "true",
            jaeger_endpoint=os.getenv("JAEGER_ENDPOINT"),
            alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            alert_email=os.getenv("ALERT_EMAIL"),
            sentry_dsn=os.getenv("SENTRY_DSN"),
            sentry_environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        )


@dataclass(frozen=True)
class SecurityConfig:
    """Security configuration."""

    # API
    api_key_header: str = "X-API-Key"
    allowed_hosts: Set[str] = field(default_factory=lambda: {"localhost", "127.0.0.1"})
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Create config from environment variables."""
        cors = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        return cls(
            api_key_header=os.getenv("API_KEY_HEADER", "X-API-Key"),
            allowed_hosts=set(
                os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
            ),
            cors_origins=cors.split(","),
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
        )


class Settings:
    """Main application settings container."""

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure single config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.env = Environment(os.getenv("APP_ENV", "development"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.app_name = "Bali Intel Scraper"
        self.app_version = os.getenv("APP_VERSION", "1.0.0")

        # Load all config sections
        self.database = DatabaseConfig.from_env()
        self.redis = RedisConfig.from_env()
        self.scraping = ScrapingConfig.from_env()
        self.ai = AIConfig.from_env()
        self.monitoring = MonitoringConfig.from_env()
        self.security = SecurityConfig.from_env()

        # Derived settings
        self.is_production = self.env == Environment.PRODUCTION
        self.is_test = self.env == Environment.TEST
        self.data_dir = Path(os.getenv("DATA_DIR", "./data"))

        self._initialized = True

    def to_dict(self) -> dict:
        """Convert settings to dictionary (for logging, excluding secrets)."""
        return {
            "env": self.env.value,
            "debug": self.debug,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "name": self.database.name,
                "pool_size": self.database.pool_size,
            },
            "redis": {
                "host": self.redis.host,
                "port": self.redis.port,
                "db": self.redis.db,
            },
            "scraping": {
                "max_concurrent_requests": self.scraping.max_concurrent_requests,
                "max_retries": self.scraping.max_retries,
                "headless": self.scraping.headless,
            },
            "ai": {
                "openai_model": self.ai.openai_model,
                "anthropic_model": self.ai.anthropic_model,
                "batch_size": self.ai.batch_size,
            },
            "monitoring": {
                "log_level": self.monitoring.log_level.value,
                "metrics_enabled": self.monitoring.metrics_enabled,
            },
        }


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
