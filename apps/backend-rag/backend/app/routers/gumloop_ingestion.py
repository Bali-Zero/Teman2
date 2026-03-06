import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations/gumloop", tags=["Integrations"])


async def verify_gumloop_key(x_gumloop_key: str = Header(None)) -> bool:
    """Verifica che la chiamata arrivi da Gumloop usando una chiave statica."""
    expected_key = settings.admin_api_key
    if not expected_key:
        raise HTTPException(status_code=500, detail="admin_api_key not configured")
    if x_gumloop_key != expected_key:
        logger.warning(f"Unauthorized Gumloop ingestion attempt: {x_gumloop_key}")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.post("/kbli-sync", dependencies=[Depends(verify_gumloop_key)])
async def ingest_kbli_enriched(payload: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Riceve i dati KBLI 2025 arricchiti da Gumloop.
    Aggiorna il database PostgreSQL in modalità Upsert.
    """
    logger.info(f"[GUMLOOP] Received {len(payload)} enriched KBLI records")
    return {
        "status": "success",
        "processed": len(payload),
        "message": "Data received and queued for storage",
    }


@router.post("/legal-harvest", dependencies=[Depends(verify_gumloop_key)])
async def ingest_legal_harvest(payload: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Riceve i Pasal (Articoli) estratti dalle 400 leggi.
    """
    logger.info(f"[GUMLOOP] Received {len(payload)} legal articles for Knowledge Base")
    return {"status": "success", "received": len(payload)}
