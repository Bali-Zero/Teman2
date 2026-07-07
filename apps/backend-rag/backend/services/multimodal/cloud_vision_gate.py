"""PII sovereignty gate for cloud OCR/Vision fallbacks.

SYMBIOSIS Law 2 (OSINT/PII sovereignty) + UU PDP Art. 56 (cross-border transfer):
OCR of client documents (passport / KTP / NPWP / akta / visa) must NOT send the
document image to Google's Gemini Vision when local Ollama is unavailable. Several
OCR paths historically did exactly that as a silent fallback.

This module is the single decision point both cloud OCR chokepoints consult
(`pdf_vision_service._analyze_via_gemini` and `crm_enhanced._gemini_ocr`):

  - `cloud_vision_allowed()` → bool : reads `settings.ocr_allow_cloud_vision`
    (default False = PII-safe). When False, the cloud path is skipped.
  - `note_cloud_ocr_blocked(context)` : logs a WARNING (the deterministic,
    deploy-safe signal) and best-effort Telegram-alerts the operator. NEVER
    raises — alerting failure must not break OCR degradation.

When the cloud path is blocked, callers degrade to local results (tesseract /
text-layer) per the crm_guardian pattern — never hard-fail, never send to cloud.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("backend.multimodal.cloud_vision_gate")


def cloud_vision_allowed() -> bool:
    """True only if cloud Vision fallback is explicitly enabled (default False).

    Reads the config flag lazily so an import-time config issue can't crash the
    OCR path; on any error it FAILS CLOSED (returns False = PII-safe).
    """
    try:
        from backend.app.core.config import settings

        return bool(getattr(settings, "ocr_allow_cloud_vision", False))
    except Exception as exc:  # config import/attr error → fail closed (no cloud)
        logger.warning("cloud_vision_gate: config unavailable (%s) — defaulting to PII-safe (no cloud)", exc)
        return False


def note_cloud_ocr_blocked(context: str) -> None:
    """Record that a cloud OCR fallback was blocked for PII sovereignty.

    Always logs WARNING (grep-able, survives in Fly logs). Best-effort Telegram
    alert so the operator knows local OCR is degraded and can restart Ollama.
    NEVER raises — this is called on the degradation path.
    """
    logger.warning(
        "🛡️ [PII-SOVEREIGNTY] Cloud OCR/Vision fallback BLOCKED (OCR_ALLOW_CLOUD_VISION=false). "
        "Local OCR unavailable — degrading locally, NOT sending document to Google. Context: %s",
        context,
    )
    try:
        # scripts/ is on PYTHONPATH in the app runtime; guard so a missing module
        # or a Telegram outage never breaks the OCR degradation path.
        from scripts.sentinel_lib.alerter import send_alert

        send_alert(
            f"OCR cloud fallback blocked (PII-safe): local Ollama OCR unavailable.\n"
            f"Context: {context}\n"
            f"Action: restart Ollama vision (qwen2.5vl) or set OCR_ALLOW_CLOUD_VISION=true "
            f"ONLY for non-PII flows.",
            level="WARNING",
        )
    except Exception as exc:  # alerter import error / network / anything
        logger.debug("cloud_vision_gate: Telegram alert unavailable (%s)", exc)
