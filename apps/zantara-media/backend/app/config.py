"""
ZANTARA MEDIA - Configuration
Centralized environment variables using pydantic-settings
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "ZANTARA MEDIA"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3002", "https://media.balizero.com"]

    # Database (shared with NUZANTARA)
    database_url: str = ""

    # Redis (shared with NUZANTARA)
    redis_url: str = "redis://localhost:6379"

    # NUZANTARA Integration
    nuzantara_api_url: str = "https://nuzantara-rag.fly.dev"
    nuzantara_api_key: str = ""

    # INTEL SCRAPING Integration
    intel_api_url: str = "http://localhost:3001"
    intel_api_key: str = ""

    # AI Providers
    openrouter_api_key: str = ""
    google_api_key: str = ""
    openai_api_key: str = ""

    # Media Generation
    imagineart_api_key: str = ""

    # Social Media APIs
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""

    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_access_token: str = ""

    telegram_bot_token: str = ""
    telegram_channel_id: str = ""

    # Newsletter
    newsletter_api_key: str = ""
    newsletter_list_id: str = ""

    # Storage
    storage_bucket: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
