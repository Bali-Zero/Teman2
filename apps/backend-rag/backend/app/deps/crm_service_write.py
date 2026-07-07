"""Scoped service-write auth for WA Mirror CRM mutations."""

from __future__ import annotations

from fastapi import HTTPException, Request


async def verify_crm_write_key(request: Request) -> str:
    """Validate the WA Mirror CRM service-write key.

    The key is deliberately narrower than ``WA_MIRROR_INTERNAL_KEY``. It is for
    WA Mirror CRM write-backs that are already gate-checked locally on Pro:
    phone-keyed lead upsert and intake document delivery to the canonical Kita
    CRM upload path. The feature remains hard-gated by
    ``WA_MIRROR_CRM_WRITE_ENABLED``.
    """
    from backend.app.core.config import settings as _settings

    if not getattr(_settings, "wa_mirror_crm_write_enabled", False):
        raise HTTPException(status_code=503, detail="crm service-write disabled")
    provided = (request.headers.get("X-CRM-Write-Key") or "").strip()
    configured = (getattr(_settings, "wa_mirror_crm_write_key", None) or "").strip()
    if not configured or not provided or provided != configured:
        raise HTTPException(status_code=401, detail="invalid or missing X-CRM-Write-Key")
    return "wa-mirror-crm-writer@balizero.com"
