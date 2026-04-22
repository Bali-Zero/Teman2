"""HTTP control panel :1819 — pause/resume/health/stats.

Minimal FastAPI app for operator interaction. Token auth via
filesystem-readable file (ORGANISM_TOKEN_PATH env). No user database,
no session — one shared operator token.

Endpoints:
  GET  /health    — status + paused flag (no auth)
  POST /pause     — set blackout for N min (auth required)
  POST /resume    — clear blackout (auth required)
  GET  /stats     — organism metrics (W2 will populate)
"""
import logging
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from organism.blackout import BlackoutManager

logger = logging.getLogger(__name__)


def _verify_token(x_organism_token: str | None) -> None:
    """Check header token matches the secret read from filesystem."""
    token_path = os.getenv("ORGANISM_TOKEN_PATH", "/etc/organism/token")
    try:
        expected = Path(token_path).read_text().strip()
    except FileNotFoundError:
        logger.warning("Token file not found at %s", token_path)
        raise HTTPException(status_code=503, detail="token not configured")
    if not x_organism_token or x_organism_token != expected:
        logger.warning("Invalid token attempt")
        raise HTTPException(status_code=401, detail="invalid token")


def create_app(*, blackout: BlackoutManager) -> FastAPI:
    """Factory — pass in BlackoutManager so tests can inject tmp_path."""
    app = FastAPI(title="Nuzantara Organism Control Panel")

    @app.get("/health")
    async def health():
        paused = blackout.is_paused()
        logger.debug("Health check: paused=%s", paused)
        return {"status": "ok", "paused": paused}

    @app.post("/pause")
    async def pause(minutes: int = 30, x_organism_token: str | None = Header(None)):
        _verify_token(x_organism_token)
        if not 1 <= minutes <= 120:
            raise HTTPException(status_code=400, detail="minutes must be 1..120 (max 120)")
        blackout.pause(minutes=minutes)
        logger.info("Blackout started for %d minutes", minutes)
        return {"paused_for_minutes": minutes}

    @app.post("/resume")
    async def resume(x_organism_token: str | None = Header(None)):
        _verify_token(x_organism_token)
        blackout.resume()
        logger.info("Blackout cleared")
        return {"resumed": True}

    @app.get("/stats")
    async def stats():
        # Populated by Wave 2 when Supervisor runs.
        return {"events_processed": 0, "supervisor_alive": False}

    return app


def _default_app() -> FastAPI:
    """Module-level entrypoint for uvicorn --factory in the plist.

    Reads ORGANISM_BLACKOUT_FLAG env for flag path (default ~/tmp/organism-pause.flag).
    """
    flag_path = Path(os.getenv(
        "ORGANISM_BLACKOUT_FLAG",
        str(Path.home() / "tmp" / "organism-pause.flag"),
    ))
    logger.info("Starting control panel with flag_path=%s", flag_path)
    return create_app(blackout=BlackoutManager(flag_path=flag_path))
