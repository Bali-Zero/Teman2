"""
Shared OCR Dispatcher Service.

Routes documents to the correct OCR handler. Two-tier strategy:

  Tier 1 — filename keywords + folder hints (fast, free, no API call)
  Tier 2 — Gemini Vision content classifier (fallback when Tier 1 misses,
           1 cheap Vision call, kicks the right OCR handler if confidence
           is high enough)

After a successful OCR handler call, optionally links the document into
the CRM Knowledge Graph (Tier-A direct edges). Controlled by env var
CRM_KG_ENABLED — off by default during gradual rollout.

Used by both CRM uploads and Portal uploads.
"""

import os
from typing import Any

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Minimum content classifier confidence to trigger an OCR handler.
# Below this threshold the file is logged as 'unknown' and skipped — better
# than running the wrong handler and writing bad data to the client record.
_CONTENT_CONFIDENCE_THRESHOLD = 0.70


def _kg_enabled() -> bool:
    """Feature flag for CRM Knowledge Graph linking.

    Off by default. Set CRM_KG_ENABLED=true (or 1, yes, on) to activate.
    Allows progressive rollout: deploy the wiring first, observe metrics,
    flip the flag once the linker is verified safe in prod.
    """
    return os.environ.get("CRM_KG_ENABLED", "").lower() in ("true", "1", "yes", "on")


async def _kg_link_after_ocr(
    db_pool: Any,
    *,
    file_id: str,
    client_id: int,
    doc_type: str,
    handler_result: Any,
    doc_id: int | None = None,  # noqa: ARG001 — reserved for PR-B backfill via documents.id
    filename: str | None = None,
) -> None:
    """Best-effort fire-and-forget hook to crm_kg document_linker.

    Called from inside dispatch_ocr_by_folder after a handler succeeds.
    All exceptions are swallowed: KG linking is a derived view, never
    a blocker for the OCR caller. If this fails, a backfill cron will
    pick up the orphan documents on the next sweep.

    Extracts the OCR fields from the handler result envelope. Each
    handler returns a dict shaped like:
        {"success": bool, "extracted": {<fields>}, ...}

    """
    if not _kg_enabled():
        return

    try:
        # Lazy import — keeps dispatch_ocr_by_folder import-cheap
        from backend.services.knowledge_graph.document_linker import kg_link_document

        # Pull extracted_fields out of the handler envelope. Handlers vary
        # in shape: some put fields under 'extracted', some under
        # 'raw_response', some return a flat dict. Be defensive.
        extracted: dict[str, Any] = {}
        practice_id: int | None = None
        drive_url: str | None = None

        if isinstance(handler_result, dict):
            # Common envelope: {"success": True, "extracted": {...}}
            if isinstance(handler_result.get("extracted"), dict):
                extracted = handler_result["extracted"]
            # OCR data field used by passport/visa handlers
            elif isinstance(handler_result.get("raw_response"), dict):
                extracted = handler_result["raw_response"]
            # Fallback: top-level keys are the extraction
            elif "passport_number" in handler_result or "npwp" in handler_result:
                extracted = handler_result

            practice_id = handler_result.get("practice_id") or practice_id
            drive_url = handler_result.get("drive_url") or drive_url

        result = await kg_link_document(
            db_pool,
            file_id=file_id,
            client_id=client_id,
            document_type=doc_type,
            extracted_fields=extracted,
            practice_id=practice_id,
            drive_url=drive_url,
            filename=filename,
        )

        if result.get("ok"):
            logger.info(
                "kg_link_document OK for file %s (client %d, type %s): "
                "nodes=%d edges=%d",
                file_id, client_id, doc_type,
                result.get("nodes", 0), result.get("edges", 0),
            )
        else:
            # ok=False is logged by document_linker itself; just note here
            # that the dispatcher saw the failure so it shows up in trace.
            logger.warning(
                "kg_link_document returned ok=False for file %s: %s",
                file_id, result.get("error"),
            )

    except Exception as e:  # noqa: BLE001 — broad-except is the contract here
        # Total swallow: KG linking failures must NEVER cause an OCR caller
        # to think the upload failed. Document state of truth lives in the
        # documents table, populated by the handler before this hook fires.
        logger.error(
            "kg_link_document hook crashed for file %s (client %d): %s",
            file_id, client_id, e, exc_info=True,
        )


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

    On successful handler dispatch (Tier 1 or Tier 2), optionally fires the
    crm_kg document_linker hook (controlled by CRM_KG_ENABLED env var).

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
        ocr_result = await _auto_ocr_passport(db_pool, client_id, file_id)
        await _kg_link_after_ocr(
            db_pool, file_id=file_id, client_id=client_id,
            doc_type="passport", handler_result=ocr_result,
            doc_id=doc_id, filename=filename,
        )
        return {
            "dispatched": True,
            "handler": "passport",
            "tier": "filename",
            "result": ocr_result,
        }

    # Visa / KITAS / KITAP detection
    visa_keywords = [
        "kitas", "kitap", "visa", "voa", "b211", "c31",
        "itas", "itap", "telex", "evisa",
    ]
    if any(kw in fn_lower for kw in visa_keywords):
        if any(kw in fn_lower for kw in visa_keywords) or "permit" in fn_lower or "stay" in fn_lower:
            logger.info(f"OCR dispatch: visa detected for client {client_id}, file {filename}")
            ocr_result = await _auto_ocr_visa(db_pool, client_id, file_id, doc_id)
            await _kg_link_after_ocr(
                db_pool, file_id=file_id, client_id=client_id,
                doc_type="visa", handler_result=ocr_result,
                doc_id=doc_id, filename=filename,
            )
            return {
                "dispatched": True,
                "handler": "visa",
                "tier": "filename",
                "result": ocr_result,
            }

    # NIB detection
    if "nib" in fn_lower or "berusaha" in fn_lower or "oss" in fn_lower:
        logger.info(f"OCR dispatch: NIB detected for client {client_id}, file {filename}")
        ocr_result = await _auto_ocr_nib(db_pool, client_id, file_id, doc_id)
        await _kg_link_after_ocr(
            db_pool, file_id=file_id, client_id=client_id,
            doc_type="nib", handler_result=ocr_result,
            doc_id=doc_id, filename=filename,
        )
        return {
            "dispatched": True,
            "handler": "nib",
            "tier": "filename",
            "result": ocr_result,
        }

    # NPWP detection
    if "npwp" in fn_lower or ("tax" in fn_lower and "id" in fn_lower):
        logger.info(f"OCR dispatch: NPWP detected for client {client_id}, file {filename}")
        ocr_result = await _auto_ocr_npwp(db_pool, client_id, file_id, doc_id)
        await _kg_link_after_ocr(
            db_pool, file_id=file_id, client_id=client_id,
            doc_type="npwp", handler_result=ocr_result,
            doc_id=doc_id, filename=filename,
        )
        return {
            "dispatched": True,
            "handler": "npwp",
            "tier": "filename",
            "result": ocr_result,
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
        await _kg_link_after_ocr(
            db_pool, file_id=file_id, client_id=client_id,
            doc_type="company_profile", handler_result=result,
            doc_id=doc_id, filename=filename,
        )
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
        # Fire KG hook after content-tier dispatch too
        await _kg_link_after_ocr(
            db_pool, file_id=file_id, client_id=client_id,
            doc_type=handler_name, handler_result=result,
            doc_id=doc_id, filename=filename,
        )
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
