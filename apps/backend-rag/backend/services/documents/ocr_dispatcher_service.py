"""
Shared OCR Dispatcher Service.

Routes documents to the correct OCR handler based on filename keywords.
Used by both CRM uploads and Portal uploads.
"""

from typing import Any

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)


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
    Central OCR dispatcher. Routes to the correct OCR handler based on
    subfolder name, filename keywords, and document_type.

    Returns:
        {"dispatched": True, "handler": "<type>", "result": <ocr_result>}
        or {"dispatched": False}
    """
    # Lazy import to avoid circular dependencies — handlers live in the router module
    from backend.app.routers.crm_enhanced import (
        _auto_ocr_company_profile,
        _auto_ocr_nib,
        _auto_ocr_npwp,
        _auto_ocr_passport,
        _auto_ocr_visa,
    )

    fn_lower = filename.lower()
    folder_lower = folder_name.lower() if folder_name else ""
    dtype_lower = (document_type or "").lower().replace("_", " ")

    # Passport detection
    if "passport" in fn_lower or (folder_lower.startswith("00_") and "passport" in fn_lower):
        logger.info(f"OCR dispatch: passport detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "passport",
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
                "result": await _auto_ocr_visa(db_pool, client_id, file_id, doc_id),
            }

    # NIB detection
    if "nib" in fn_lower or "berusaha" in fn_lower or "oss" in fn_lower:
        logger.info(f"OCR dispatch: NIB detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "nib",
            "result": await _auto_ocr_nib(db_pool, client_id, file_id, doc_id),
        }

    # NPWP detection
    if "npwp" in fn_lower or ("tax" in fn_lower and "id" in fn_lower):
        logger.info(f"OCR dispatch: NPWP detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "npwp",
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
        return await _auto_ocr_company_profile(db_pool, client_id, file_id, doc_id)

    logger.debug(f"OCR dispatch: no handler matched for file {filename} in {folder_name}")
    return {"dispatched": False}
