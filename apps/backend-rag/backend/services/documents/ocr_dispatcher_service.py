"""
Shared OCR Dispatcher Service.

Routes documents to the correct OCR handler. Two-tier strategy:

  Tier 1 — filename keywords + folder hints (fast, free, no API call)
  Tier 2 — Gemini Vision content classifier (fallback when Tier 1 misses,
           1 cheap Vision call, kicks the right OCR handler if confidence
           is high enough)

Used by both CRM uploads and Portal uploads.
"""

from typing import Any

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Minimum content classifier confidence to trigger an OCR handler.
# Below this threshold the file is logged as 'unknown' and skipped — better
# than running the wrong handler and writing bad data to the client record.
_CONTENT_CONFIDENCE_THRESHOLD = 0.70


async def dispatch_ocr_by_folder(
    db_pool: Any,
    client_id: int,
    file_id: str,
    folder_name: str,
    filename: str,
    doc_id: int | None = None,
    document_type: str | None = None,
) -> dict:
    """
    Central OCR dispatcher. Routes to the correct OCR handler based on:
      1. Subfolder name + filename keywords + explicit document_type (Tier 1)
      2. Gemini Vision content classifier as fallback (Tier 2)

    Returns:
        {"dispatched": True, "handler": "<type>", "tier": "filename"|"content",
         "result": <ocr_result>}
        or {"dispatched": False, "tier": "content", "classifier": <class_result>}
        or {"dispatched": False}
    """
    # Lazy import to avoid circular dependencies — handlers live in the router module
    from backend.app.routers.crm_enhanced import (
        _auto_classify_content,
        _auto_ocr_company_profile,
        _auto_ocr_nib,
        _auto_ocr_npwp,
        _auto_ocr_passport,
        _auto_ocr_visa,
    )

    fn_lower = filename.lower()
    folder_lower = folder_name.lower() if folder_name else ""
    dtype_lower = (document_type or "").lower().replace("_", " ")

    # ─── Tier 1: filename / folder keyword match ─────────────────────────

    # Passport detection
    if "passport" in fn_lower or (folder_lower.startswith("00_") and "passport" in fn_lower):
        logger.info(f"OCR dispatch: passport detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "passport",
            "tier": "filename",
            "result": await _auto_ocr_passport(db_pool, client_id, file_id),
        }

    # Visa / KITAS / KITAP detection
    visa_keywords = [
        "kitas", "kitap", "visa", "voa", "b211", "c31",
        "itas", "itap", "telex", "evisa",
    ]
    if any(kw in fn_lower for kw in visa_keywords):
        if any(kw in fn_lower for kw in visa_keywords) or "permit" in fn_lower or "stay" in fn_lower:
            logger.info(f"OCR dispatch: visa detected for client {client_id}, file {filename}")
            return {
                "dispatched": True,
                "handler": "visa",
                "tier": "filename",
                "result": await _auto_ocr_visa(db_pool, client_id, file_id, doc_id),
            }

    # NIB detection
    if "nib" in fn_lower or "berusaha" in fn_lower or "oss" in fn_lower:
        logger.info(f"OCR dispatch: NIB detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "nib",
            "tier": "filename",
            "result": await _auto_ocr_nib(db_pool, client_id, file_id, doc_id),
        }

    # NPWP detection
    if "npwp" in fn_lower or ("tax" in fn_lower and "id" in fn_lower):
        logger.info(f"OCR dispatch: NPWP detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "npwp",
            "tier": "filename",
            "result": await _auto_ocr_npwp(db_pool, client_id, file_id, doc_id),
        }

    # Company Profile / Profil Perseroan
    profile_keywords = [
        "company profile", "profil perseroan", "profil pt",
        "profil perusahaan", "profile perseroan",
    ]
    if any(kw in fn_lower for kw in profile_keywords) or dtype_lower in (
        "company profile", "profile perseroan", "company_profile",
    ):
        logger.info(f"OCR dispatch: company_profile for client {client_id}")
        result = await _auto_ocr_company_profile(db_pool, client_id, file_id, doc_id)
        # Existing handler returns its own dict; preserve it as-is for
        # backward compatibility but enrich with tier metadata.
        if isinstance(result, dict):
            result.setdefault("dispatched", True)
            result.setdefault("handler", "company_profile")
            result.setdefault("tier", "filename")
        return result

    # ─── Tier 2: Gemini Vision content classifier (fallback) ─────────────
    #
    # If filename gave us no signal, ask Gemini to look at the actual
    # content. One cheap Vision call (Ollama qwen2.5vl:7b → Gemini CLI →
    # Gemini API). The classifier is robust against filename obfuscation
    # ("IMG_2847.pdf", "scan_001.jpeg", clienti che caricano dal cellulare).
    logger.info(
        f"OCR dispatch: filename '{filename}' did not match Tier 1 keywords — "
        f"trying content classifier for client {client_id}",
    )
    classification = await _auto_classify_content(file_id)

    if "error" in classification:
        logger.warning(
            f"OCR dispatch: content classifier failed for file {filename}: "
            f"{classification['error']}",
        )
        return {"dispatched": False, "tier": "content", "classifier": classification}

    detected_type = classification.get("document_type", "unknown")
    confidence = float(classification.get("confidence", 0.0))

    if confidence < _CONTENT_CONFIDENCE_THRESHOLD or detected_type == "unknown":
        logger.info(
            f"OCR dispatch: content classifier returned {detected_type} "
            f"(confidence {confidence:.2f} < {_CONTENT_CONFIDENCE_THRESHOLD}) — "
            f"no handler triggered for client {client_id}, file {filename}",
        )
        return {"dispatched": False, "tier": "content", "classifier": classification}

    # Confidence high enough → re-route to the matching OCR handler.
    # Only types that already have a handler are listed here. Akta / SPT /
    # Faktur / bukti_potong / contract / family_doc are recognized by the
    # classifier but produce {"dispatched": False, "classifier": ...} until
    # their handlers ship in Phase 2.
    handler_map = {
        "passport": ("passport", lambda: _auto_ocr_passport(db_pool, client_id, file_id)),
        "visa": ("visa", lambda: _auto_ocr_visa(db_pool, client_id, file_id, doc_id)),
        "nib": ("nib", lambda: _auto_ocr_nib(db_pool, client_id, file_id, doc_id)),
        "npwp": ("npwp", lambda: _auto_ocr_npwp(db_pool, client_id, file_id, doc_id)),
        "company_profile": (
            "company_profile",
            lambda: _auto_ocr_company_profile(db_pool, client_id, file_id, doc_id),
        ),
    }
    if detected_type in handler_map:
        handler_name, handler_call = handler_map[detected_type]
        logger.info(
            f"OCR dispatch: content classifier matched {detected_type} "
            f"(confidence {confidence:.2f}) for client {client_id}, file {filename} — "
            f"running {handler_name} handler",
        )
        try:
            result = await handler_call()
        except Exception as e:
            logger.error(
                f"OCR dispatch: handler {handler_name} failed after content "
                f"classification for file {filename}: {e}",
            )
            return {
                "dispatched": False,
                "tier": "content",
                "classifier": classification,
                "handler_error": str(e),
            }
        # Normalize handler return shape (some handlers return raw dicts,
        # others return the already-wrapped {dispatched, handler, result}).
        if isinstance(result, dict) and "dispatched" in result:
            result.setdefault("tier", "content")
            result.setdefault("classifier", classification)
            return result
        return {
            "dispatched": True,
            "handler": handler_name,
            "tier": "content",
            "classifier": classification,
            "result": result,
        }

    # Recognized type but no handler yet (akta/spt/faktur/etc — Phase 2).
    logger.info(
        f"OCR dispatch: content classifier matched {detected_type} "
        f"(confidence {confidence:.2f}) but no handler implemented yet — "
        f"file {filename} cataloged as classified but unprocessed",
    )
    return {"dispatched": False, "tier": "content", "classifier": classification}
