"""
Dashboard Router - KBLI-Zoning Integration for Streamlit dashboard.

Provides 5 endpoints for property validation, client geo data,
risk zones, analytics logging, and aggregate stats.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.kbli_eye import KBLIEye

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard/map", tags=["dashboard"])

# Singleton KBLIEye instance (CPU-only, deterministic — no async needed)
_kbli_eye: Optional[KBLIEye] = None


def _get_kbli_eye() -> KBLIEye:
    global _kbli_eye
    if _kbli_eye is None:
        _kbli_eye = KBLIEye()
        logger.info("KBLIEye singleton initialized for dashboard")
    return _kbli_eye


# ── Request Models ────────────────────────────────────────────────────


class ValidatePropertyRequest(BaseModel):
    kbli_code: str
    is_pma: bool = True
    location: str = "Bali"
    skala: Optional[str] = None


class LogLookupRequest(BaseModel):
    user_email: str
    property_code: Optional[str] = None
    kbli_code: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoint 1: Validate Property ─────────────────────────────────────


@router.post("/validate-property")
async def validate_property(req: ValidatePropertyRequest) -> dict[str, Any]:
    """
    KBLI compliance check for a property/business activity.
    Returns APPROVED / WARNING / REJECTED with structured audit data.
    """
    eye = _get_kbli_eye()
    result = eye.get_decision(
        code=req.kbli_code,
        is_pma=req.is_pma,
        location=req.location,
    )
    state = result.get("audit", {}).get("state", result.get("state", "UNKNOWN"))
    logger.info(
        "KBLI validation: code=%s is_pma=%s location=%s -> %s",
        req.kbli_code, req.is_pma, req.location, state,
    )
    return result


# ── Endpoint 2: Client Geo Data ────────────────────────────────────────


@router.get("/clients/geo")
async def get_clients_geo(request: Request) -> dict[str, Any]:
    """
    Returns active clients with address info for CRM map layer.
    Uses asyncpg pool from app state.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard clients/geo: db_pool not available")
        return {"clients": [], "error": "Database pool not available"}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, email, phone, status, address
                FROM clients
                WHERE status = 'active'
                ORDER BY full_name
                LIMIT 500
                """
            )
            clients: list[dict[str, Any]] = [
                {
                    "id": row["id"],
                    "full_name": row["full_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "status": row["status"],
                    "address": row["address"],
                }
                for row in rows
            ]
            logger.info("Dashboard clients/geo: returned %d clients", len(clients))
            return {"clients": clients, "total": len(clients)}
    except Exception as e:
        logger.error("Dashboard clients/geo failed: %s", e, exc_info=True)
        return {"clients": [], "error": str(e)}


# ── Endpoint 3: Risk Zones ─────────────────────────────────────────────


@router.get("/compliance/risk-zones")
async def get_risk_zones() -> dict[str, list[dict[str, Any]]]:
    """
    Static/deterministic risk zone definitions for map coloring.
    Based on KBLI PMA restrictions from PP 28/2025 and Perpres 10/2021.
    """
    return {
        "zones": [
            {
                "level": "HIGH",
                "color": "#dc3545",
                "description": "KBLI con restrizioni PMA — riservati UMKM o chiusi a investimento straniero",
                "example_kbli_codes": ["47111", "47191", "56101"],
                "criteria": "pma_status != TERBUKA (Perpres 10/2021 DNI list)",
            },
            {
                "level": "MEDIUM",
                "color": "#fd7e14",
                "description": "KBLI aperto PMA ma con warning — limiti investimento, approvazioni extra, restrizioni Bali 2026",
                "example_kbli_codes": ["55111", "56301", "68110"],
                "criteria": "Risiko Rendah/Menengah Rendah in Bali (Lettera Governatore 28 Gen 2026)",
            },
            {
                "level": "LOW",
                "color": "#198754",
                "description": "KBLI completamente aperto a PMA — nessuna restrizione speciale",
                "example_kbli_codes": ["55203", "62011", "70201"],
                "criteria": "pma_status == TERBUKA, no location-specific restrictions",
            },
        ]
    }


# ── Endpoint 4: Log Analytics Lookup ───────────────────────────────────


@router.post("/analytics/log-lookup")
async def log_lookup(req: LogLookupRequest, request: Request) -> dict[str, Any]:
    """
    Log a map lookup event for analytics tracking.
    Creates the analytics table on first use (idempotent).
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard analytics/log: db_pool not available")
        return {"logged": False, "error": "Database pool not available"}

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_map_lookups (
                    id SERIAL PRIMARY KEY,
                    user_email TEXT,
                    property_code TEXT,
                    kbli_code TEXT,
                    location TEXT,
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO analytics_map_lookups
                    (user_email, property_code, kbli_code, location, notes)
                VALUES ($1, $2, $3, $4, $5)
                """,
                req.user_email,
                req.property_code,
                req.kbli_code,
                req.location,
                req.notes,
            )
            logger.info(
                "Dashboard analytics logged: user=%s kbli=%s",
                req.user_email, req.kbli_code,
            )
            return {"logged": True}
    except Exception as e:
        logger.error("Dashboard analytics/log failed: %s", e, exc_info=True)
        return {"logged": False, "error": str(e)}


# ── Endpoint 5: Aggregate Stats ────────────────────────────────────────


@router.get("/stats")
async def get_stats(request: Request) -> dict[str, Any]:
    """Aggregate stats for the sidebar dashboard widgets."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        logger.warning("Dashboard stats: db_pool not available")
        return {
            "total_clients": 0,
            "total_practices": 0,
            "map_lookups_24h": 0,
            "error": "Database pool not available",
        }

    try:
        async with pool.acquire() as conn:
            total_clients: int = await conn.fetchval(
                "SELECT COUNT(*) FROM clients WHERE status = 'active'"
            ) or 0

            total_practices: int = await conn.fetchval(
                """
                SELECT COUNT(*) FROM practices
                WHERE status NOT IN ('cancelled', 'archived')
                """
            ) or 0

            # Map lookups in last 24h (graceful if table doesn't exist yet)
            map_lookups_24h: int = 0
            try:
                map_lookups_24h = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM analytics_map_lookups
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    """
                ) or 0
            except Exception:
                pass  # Table may not exist yet

            return {
                "total_clients": total_clients,
                "total_practices": total_practices,
                "map_lookups_24h": map_lookups_24h,
            }
    except Exception as e:
        logger.error("Dashboard stats failed: %s", e, exc_info=True)
        return {
            "total_clients": 0,
            "total_practices": 0,
            "map_lookups_24h": 0,
            "error": str(e),
        }
