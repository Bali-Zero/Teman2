"""CELL configuration — all settings from environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings


class CellSettings(BaseSettings):
    """CELL organism settings. All from env vars."""

    # Paths
    cell_root: Path = Path(__file__).parent.parent.parent
    dna_path: Path = Path(__file__).parent.parent / "config" / "dna.json"

    # Nuzantara endpoints
    backend_health_url: str = "https://nuzantara-rag.fly.dev/health"
    fly_app_name: str = "nuzantara-rag"

    # Fly.io API (for restart/scale effectors)
    fly_api_token: str = ""  # set FLY_API_TOKEN env var (not CELL_ prefix — shared)

    # Database (via fly proxy tunnel)
    database_url: str = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # Qdrant (local or Fly.io)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "cell_experiences"

    # Telegram alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Pulse
    pulse_interval_seconds: int = 60

    # DNA integrity
    dna_expected_hash: str = ""

    class Config:
        env_prefix = "CELL_"
        env_file = ".env"


settings = CellSettings()
