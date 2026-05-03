"""
CRM Clients - Document OCR & Metrics

Split from crm_clients.py for maintainability.
Provides: CRM metrics (summary, refresh), Passport OCR (basic + enhanced),
Document soft-delete, NPWP OCR, NIB OCR, Required documents for portal.
"""

import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.services.crm.metrics import metrics_collector
from backend.app.utils.crm_utils import (
    extract_json_from_llm_response,
    is_crm_admin,
    verify_client_access,
)
from backend.app.utils.error_handlers import handle_database_error
from backend.app.utils.json_utils import to_jsonb
from backend.app.utils.logging_utils import get_logger
from backend.core.cache import invalidate_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/clients", tags=["crm-clients-documents"])

@router.get("/metrics/summary")
async def get_crm_metrics_summary(
    current_user: dict = Depends(get_current_user),
    _db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """
    Get CRM metrics summary for dashboard
    """
    try:
        user_email = current_user.get("email", "")
        if not user_email:
            raise HTTPException(status_code=401, detail="Authentication required")

        return await metrics_collector.get_metrics_summary()

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


@router.post("/metrics/refresh")
async def refresh_crm_metrics(
    current_user: dict = Depends(get_current_user),
    _db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """
    Force refresh of CRM metrics (Admin only)
    """
    try:
        if not is_crm_admin(current_user):
            raise HTTPException(status_code=403, detail="Admin access required")

        results = await metrics_collector.update_all_metrics()

        await invalidate_cache("zantara:crm_clients_documents:*")
        return {
            "message": "CRM metrics refreshed successfully",
            "timestamp": results.get("timestamp"),
            "metrics_updated": results.get("metrics_updated", []),
            "errors": results.get("errors", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e) from e


# ================================================
# PASSPORT OCR EXTRACTION
# ================================================


class PassportExtractRequest(BaseModel):
    """Request model for passport data extraction"""

    client_id: int
    image_url: str


class PassportExtractResponse(BaseModel):
    """Response model for extracted passport data"""

    success: bool
    passport_number: str | None = None
    passport_expiry: str | None = None
    message: str | None = None


@router.post("/extract-passport", response_model=PassportExtractResponse, deprecated=True)
async def extract_passport_data(
    request: PassportExtractRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PassportExtractResponse:
    """
    DEPRECATED — Use /extract-passport-enhanced instead.
    This endpoint only extracts 2 fields and requires a Drive URL.
    Kept for backward compatibility with existing callers.
    """
    return PassportExtractResponse(
        success=False,
        message="This endpoint is deprecated. Use /extract-passport-enhanced with base64 image instead.",
    )


# ================================================
# ENHANCED PASSPORT OCR (Full Extraction)
# ================================================


class PassportPreviewRequest(BaseModel):
    """Passport OCR — preview mode (client_id=None) or persist mode (client_id=int).

    Preview: stateless OCR, returns extracted fields, no DB write.
    Persist: OCR + DB update (existing behavior).
    """

    image_base64: str = Field(..., max_length=14_000_000)  # ~10MB after base64 overhead
    mime_type: str = "image/jpeg"
    client_id: int | None = None


class PassportPreviewResponse(BaseModel):
    """Response model for passport OCR (preview + persist modes)"""

    success: bool
    confidence: float = 0.0
    full_name: str | None = None
    surname: str | None = None
    given_names: str | None = None
    nationality: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    issuing_country: str | None = None
    birthplace: str | None = None
    mrz_line1: str | None = None
    mrz_line2: str | None = None
    name_match: bool | None = None
    warnings: list[str] = []
    message: str | None = None


@router.post("/extract-passport-enhanced", response_model=PassportPreviewResponse)
async def extract_passport_enhanced(
    request: PassportPreviewRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PassportPreviewResponse:
    """
    Passport OCR using Gemini Vision — preview or persist mode.

    Preview mode (client_id=None): stateless OCR, returns extracted fields, no DB write.
    Persist mode (client_id=int): OCR + DB update + name match verification.

    Accepts base64 image data directly (no Drive download).
    """
    import base64
    import json
    from difflib import SequenceMatcher

    import httpx

    from backend.utils.passport_normalize import normalize_date, normalize_nationality, title_case_name

    # Ollama URL: local Pro (H24) or configurable via env
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

    try:
        # Persist mode: RBAC check + client lookup
        existing_name: str | None = None
        if request.client_id is not None:
            async with db_pool.acquire() as conn:
                # RBAC: verify user has access to this specific client
                await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

                client = await conn.fetchrow(
                    "SELECT full_name FROM clients WHERE id = $1", request.client_id,
                )
                if not client:
                    return PassportPreviewResponse(
                        success=False, message=f"Client {request.client_id} not found",
                    )
                existing_name = client["full_name"]

        # Decode base64 image
        raw_b64 = request.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]  # Strip data URI prefix
        try:
            image_data = base64.b64decode(raw_b64, validate=True)
        except Exception:
            return PassportPreviewResponse(success=False, message="Invalid base64 image data")

        # Build OCR prompt
        ocr_prompt = """Extract passport data. Return ONLY this JSON:

{
  "passport_number": "XX123456",
  "expiry_date": "YYYY-MM-DD",
  "full_name": "GIVEN_NAMES SURNAME",
  "surname": "SURNAME",
  "given_names": "GIVEN NAMES",
  "gender": "M or F",
  "date_of_birth": "YYYY-MM-DD",
  "birthplace": "city, country",
  "nationality": "country code",
  "confidence": 0.95
}

The "surname" field MUST contain ONLY the family name (Surname/Apellidos/Nom),
and "given_names" MUST contain ONLY the first/middle names (Given names/Prenoms/Nombres).
"full_name" MUST be given names FIRST, then surname (Western reading order).

Use null for unclear fields. Return ONLY JSON."""

        # Try Ollama Vision first (local, zero API cost), fallback to Gemini API
        response_text = ""
        ollama_ok = False

        try:
            ollama_payload = {
                "model": OLLAMA_VISION_MODEL,
                "prompt": ocr_prompt,
                "images": [base64.b64encode(image_data).decode()],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2000},
            }

            async with httpx.AsyncClient(timeout=30.0) as http:
                ollama_response = await http.post(
                    f"{OLLAMA_URL}/api/generate",
                    json=ollama_payload,
                )

            if ollama_response.status_code == 200:
                response_text = ollama_response.json().get("response", "")
                if response_text:
                    ollama_ok = True
                    logger.info(f"Passport OCR via Ollama: len={len(response_text)}")
                else:
                    logger.warning("Ollama returned empty response, falling back to Gemini")
            else:
                logger.warning(f"Ollama OCR failed: HTTP {ollama_response.status_code}, falling back to Gemini")
        except Exception as e:
            logger.warning(f"Ollama unreachable ({e}), falling back to Gemini Vision")

        # Fallback: Gemini API Vision
        if not ollama_ok:
            from backend.llm.genai_client import GENAI_AVAILABLE, get_genai_client

            if not GENAI_AVAILABLE:
                return PassportPreviewResponse(
                    success=False,
                    message="Vision OCR service unavailable (no Ollama or Gemini configured)",
                )

            genai_client = get_genai_client()
            if not genai_client.is_available:
                return PassportPreviewResponse(
                    success=False,
                    message="Vision OCR service unavailable (Gemini not configured)",
                )

            contents = [
                ocr_prompt,
                {
                    "inline_data": {
                        "mime_type": request.mime_type,
                        "data": base64.b64encode(image_data).decode(),
                    },
                },
            ]

            result = await genai_client.generate_content(
                contents=contents,
                model="gemini-2.5-flash",
                max_output_tokens=4096,
            )
            response_text = result.get("text", "")
            logger.info(f"Passport OCR via Gemini API: len={len(response_text)}")

        if not response_text:
            return PassportPreviewResponse(
                success=False,
                message="Vision OCR returned empty response",
            )

        # Parse JSON response (handles code fences and chain-of-thought)
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error("Passport OCR: JSON parsing failed")
            return PassportPreviewResponse(success=False, message="Could not parse OCR response")

        # Normalize extracted fields
        extracted["full_name"] = title_case_name(extracted.get("full_name"))
        extracted["surname"] = title_case_name(extracted.get("surname"))
        extracted["given_names"] = title_case_name(extracted.get("given_names"))
        extracted["nationality"] = normalize_nationality(extracted.get("nationality"))
        extracted["date_of_birth"] = normalize_date(extracted.get("date_of_birth"))
        extracted["expiry_date"] = normalize_date(extracted.get("expiry_date"))
        gender_raw = extracted.get("gender", "")
        if gender_raw and len(gender_raw) > 0:
            extracted["gender"] = gender_raw[0].upper()
        else:
            extracted["gender"] = None

        # Build warnings
        warnings: list[str] = []
        confidence = extracted.get("confidence", 0.0)
        if isinstance(confidence, (int, float)) and confidence < 0.7:
            warnings.append("Low image quality — verify extracted fields")
        expiry = extracted.get("expiry_date")
        if expiry:
            try:
                from datetime import date

                if datetime.strptime(expiry, "%Y-%m-%d").date() < date.today():
                    warnings.append("Passport is expired")
            except ValueError:
                # UU PDP audit: document OCR returned a non-ISO expiry date.
                # Surfacing the mis-parse as a warning preserves traceability
                # without rejecting the whole extraction.
                warnings.append(
                    "Passport expiry date format unrecognised — manual review required"
                )
                logger.info(
                    "crm.passport_ocr.invalid_expiry_format",
                    extra={"raw_expiry": str(expiry)[:32]},
                )

        # Preview mode — return without persisting
        if request.client_id is None:
            return PassportPreviewResponse(
                success=bool(extracted),
                confidence=extracted.get("confidence", 0.0) if extracted else 0.0,
                full_name=extracted.get("full_name") if extracted else None,
                surname=extracted.get("surname") if extracted else None,
                given_names=extracted.get("given_names") if extracted else None,
                nationality=extracted.get("nationality") if extracted else None,
                date_of_birth=extracted.get("date_of_birth") if extracted else None,
                gender=extracted.get("gender") if extracted else None,
                passport_number=extracted.get("passport_number") if extracted else None,
                passport_expiry=extracted.get("expiry_date") if extracted else None,
                issuing_country=extracted.get("issuing_country") or extracted.get("nationality") if extracted else None,
                birthplace=extracted.get("birthplace") if extracted else None,
                mrz_line1=extracted.get("mrz_line1") if extracted else None,
                mrz_line2=extracted.get("mrz_line2") if extracted else None,
                warnings=warnings if extracted else ["OCR extraction failed"],
                message="Preview — fields extracted but not saved" if extracted else "Could not extract passport data",
            )

        # --- Persist mode (client_id is not None) ---

        # Verify name match (order-insensitive: "Rewis Bishop" must match "Bishop Rewis")
        name_match = None
        ratio = None
        extracted_name = extracted.get("full_name")
        if extracted_name and existing_name:
            existing_tokens = sorted(existing_name.upper().replace(",", " ").split())
            extracted_tokens = sorted(extracted_name.upper().replace(",", " ").split())
            ratio = SequenceMatcher(None, existing_tokens, extracted_tokens).ratio()
            name_match = ratio >= 0.8

        # Prepare OCR data for storage
        ocr_data = {
            "extracted_at": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
            "fields_extracted": [k for k, v in extracted.items() if v is not None],
            "confidence": extracted.get("confidence", 0.0),
            "name_match_ratio": ratio if name_match is not None else None,
        }

        # Update client record with extracted data
        async with db_pool.acquire() as conn:
            update_parts = ["passport_ocr_data = $1"]
            # Use to_jsonb for asyncpg JSONB compatibility (handles Decimal, datetime, UUID)
            params = [to_jsonb(ocr_data)]
            param_idx = 2

            if extracted.get("passport_number"):
                update_parts.append(f"passport_number = ${param_idx}")
                params.append(extracted["passport_number"])
                param_idx += 1

            if extracted.get("expiry_date"):
                try:
                    expiry_date = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                    update_parts.append(f"passport_expiry = ${param_idx}")
                    params.append(expiry_date)
                    param_idx += 1
                except ValueError:
                    logger.warning("Passport OCR: invalid expiry_date format in persist mode")

            if extracted.get("gender"):
                update_parts.append(f"gender = ${param_idx}")
                params.append(extracted["gender"])  # Already normalized to M or F
                param_idx += 1

            if extracted.get("date_of_birth"):
                try:
                    dob = datetime.strptime(extracted["date_of_birth"], "%Y-%m-%d").date()
                    update_parts.append(f"date_of_birth = ${param_idx}")
                    params.append(dob)
                    param_idx += 1
                except ValueError:
                    logger.warning("Passport OCR: invalid date_of_birth format in persist mode")

            if extracted.get("birthplace"):
                update_parts.append(f"birthplace = ${param_idx}")
                params.append(extracted["birthplace"])
                param_idx += 1

            if extracted.get("nationality"):
                update_parts.append(f"nationality = ${param_idx}")
                params.append(extracted["nationality"])
                param_idx += 1

            params.append(request.client_id)
            update_sql = f"""
                UPDATE clients SET {", ".join(update_parts)}, updated_at = NOW()
                WHERE id = ${param_idx}
            """
            await conn.execute(update_sql, *params)
            logger.info(f"Updated client {request.client_id} with enhanced OCR data")

        await invalidate_cache("zantara:crm_clients_documents:*")
        return PassportPreviewResponse(
            success=True,
            confidence=extracted.get("confidence", 0.0),
            full_name=extracted.get("full_name"),
            surname=extracted.get("surname"),
            given_names=extracted.get("given_names"),
            nationality=extracted.get("nationality"),
            date_of_birth=extracted.get("date_of_birth"),
            gender=extracted.get("gender"),
            passport_number=extracted.get("passport_number"),
            passport_expiry=extracted.get("expiry_date"),
            issuing_country=extracted.get("nationality"),
            birthplace=extracted.get("birthplace"),
            mrz_line1=extracted.get("mrz_line1"),
            mrz_line2=extracted.get("mrz_line2"),
            name_match=name_match,
            warnings=warnings,
            message="Passport data extracted and saved successfully",
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.warning(f"Enhanced OCR JSON parse error: {e}")
        return PassportPreviewResponse(success=False, message="Failed to parse OCR response")
    except Exception as e:
        logger.error(f"Enhanced passport OCR failed: {e}")
        return PassportPreviewResponse(success=False, message=str(e))


# ================================================
# MANUAL DOCUMENT UPLOAD & DELETE
# ================================================


# NOTE: Document upload endpoint moved to crm_enhanced.py
# Path: POST /api/crm/clients/{client_id}/documents/upload
# Uses DocumentUploadBase64 model with proper Pydantic validation


@router.delete("/documents/{document_id}")
async def delete_client_document(
    document_id: int = Path(..., gt=0, description="Document ID"),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Delete a client document (soft delete).

    Sets the document status to 'deleted'. The file remains in Google Drive
    but is hidden from the UI.

    Args:
        document_id: Document ID to delete

    Returns:
        Success message
    """
    try:
        user_email = current_user.get("email", "").lower()

        async with db_pool.acquire() as conn:
            # Get document info
            doc = await conn.fetchrow(
                """
                SELECT id, client_id, document_type, file_name, status
                FROM documents
                WHERE id = $1
                """,
                document_id,
            )

            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            # RBAC: verify caller has access to the client this document belongs to
            await verify_client_access(doc["client_id"], current_user, conn, allow_assigned=True)

            if doc["status"] == "deleted":
                return {
                    "success": True,
                    "message": f"Document {doc['file_name']} is already deleted",
                }

            # Soft delete (mark as deleted)
            await conn.execute(
                """
                UPDATE documents
                SET status = 'deleted', updated_at = NOW()
                WHERE id = $1
                """,
                document_id,
            )

            logger.info(
                f"Soft deleted document {document_id} (client {doc['client_id']}, type: {doc['document_type']}) by {user_email}",
            )
            await invalidate_cache("zantara:crm_clients_documents:*")
            return {
                "success": True,
                "message": f"Document {doc['file_name']} marked as deleted",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}") from e


# ================================================
# NPWP OCR ENDPOINT
# ================================================


class NpwpExtractRequest(BaseModel):
    client_id: int
    file: str  # base64 encoded file
    file_name: str


class NpwpExtractResponse(BaseModel):
    success: bool
    npwp: str | None = None
    address: str | None = None
    city: str | None = None
    message: str | None = None


@router.post("/extract-npwp", response_model=NpwpExtractResponse)
async def extract_npwp(
    request: NpwpExtractRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> NpwpExtractResponse:
    """
    Extract NPWP data from uploaded NPWP card image using Gemini Vision.

    Extracts:
    - NPWP number (15 digits)
    - Registered address
    - City
    """
    import base64
    import os
    import re

    import httpx

    try:
        # RBAC check: verify caller has access to this client
        async with db_pool.acquire() as conn:
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

        # Validate base64 before decoding
        raw = request.file.split(",")[-1] if "," in request.file else request.file
        try:
            file_data = base64.b64decode(raw, validate=True)
        except Exception:
            return NpwpExtractResponse(success=False, message="Invalid base64 data")

        # OCR Prompt for NPWP
        ocr_prompt = """Extract NPWP (Indonesian Tax ID) information from this image.

Return ONLY this JSON format:
{
  "npwp": "12.345.678.9-012.345" or "123456789012345",
  "address": "Full street address",
  "city": "City name",
  "confidence": 0.95
}

Rules:
- NPWP is a 15-digit number, usually formatted as XX.XXX.XXX.X-XXX.XXX
- Address should be the complete registered address
- City should be just the city name (e.g., "Denpasar", "Jakarta", "Surabaya")
- Use null for fields that are not visible or unclear
- Return ONLY valid JSON, no markdown, no explanations"""

        # Call Ollama Vision (local, zero API cost)
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        vision_model = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{ollama_url}/api/generate", json={
                "model": vision_model,
                "prompt": ocr_prompt,
                "images": [base64.b64encode(file_data).decode()],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2000},
            })

        if resp.status_code != 200:
            logger.error("NPWP OCR: Ollama HTTP %d", resp.status_code)
            return NpwpExtractResponse(success=False, message="Vision OCR service unavailable")

        response_text = resp.json().get("response", "")
        logger.info("NPWP OCR: response_len=%d", len(response_text))

        # Parse JSON response
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error("NPWP OCR: JSON parsing failed")
            return NpwpExtractResponse(success=False, message="Could not parse OCR response")

        # Clean NPWP (remove dots, keep only digits)
        npwp = extracted.get("npwp", "")
        if npwp:
            npwp_clean = re.sub(r"\D", "", npwp)
            # Validate 15 digits
            if len(npwp_clean) != 15:
                logger.warning("NPWP OCR: extracted value doesn't have 15 digits")
                npwp = npwp_clean  # Keep original but cleaned
            else:
                npwp = npwp_clean

        # Save to DB if extracted successfully
        if npwp:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE clients SET npwp = $1, updated_at = NOW() WHERE id = $2",
                    npwp,
                    request.client_id,
                )
                logger.info(f"Saved NPWP for client {request.client_id}")

        await invalidate_cache("zantara:crm_clients_documents:*")
        return NpwpExtractResponse(
            success=True,
            npwp=npwp if npwp else None,
            address=extracted.get("address"),
            city=extracted.get("city"),
            message=f"OCR completed with confidence {extracted.get('confidence', 'unknown')}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NPWP extraction failed: {e}", exc_info=True)
        return NpwpExtractResponse(success=False, message=f"Extraction failed: {str(e)}")


# ================================================
# NIB OCR ENDPOINT
# ================================================


class NibExtractRequest(BaseModel):
    client_id: int
    file: str  # base64 encoded file
    file_name: str


class NibExtractResponse(BaseModel):
    success: bool
    nib: str | None = None
    company_name: str | None = None
    kbli_code: str | None = None
    message: str | None = None


@router.post("/extract-nib", response_model=NibExtractResponse)
async def extract_nib(
    request: NibExtractRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> NibExtractResponse:
    """
    Extract NIB (Nomor Induk Berusaha) data from uploaded NIB document using Gemini Vision.

    Extracts:
    - NIB number (13 digits)
    - Company name
    - KBLI code
    """
    import base64
    import os
    import re

    import httpx

    try:
        # RBAC check: verify caller has access to this client
        async with db_pool.acquire() as conn:
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

        # Validate base64 before decoding
        raw = request.file.split(",")[-1] if "," in request.file else request.file
        try:
            file_data = base64.b64decode(raw, validate=True)
        except Exception:
            return NibExtractResponse(success=False, message="Invalid base64 data")

        # OCR Prompt for NIB
        ocr_prompt = """Extract NIB (Nomor Induk Berusaha) information from this Indonesian business document.

Return ONLY this JSON format:
{
  "nib": "13 digit NIB number",
  "company_name": "Full company name as written",
  "kbli_code": "5 digit KBLI code",
  "confidence": 0.95
}

Rules:
- NIB is a 13-digit number
- Company name should be the full legal name
- KBLI code is usually a 5-digit number representing business classification
- Use null for fields that are not visible or unclear
- Return ONLY valid JSON, no markdown, no explanations"""

        # Call Ollama Vision (local, zero API cost)
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        vision_model = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl:7b")

        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(f"{ollama_url}/api/generate", json={
                "model": vision_model,
                "prompt": ocr_prompt,
                "images": [base64.b64encode(file_data).decode()],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 2000},
            })

        if resp.status_code != 200:
            logger.error("NIB OCR: Ollama HTTP %d", resp.status_code)
            return NibExtractResponse(success=False, message="Vision OCR service unavailable")

        response_text = resp.json().get("response", "")
        logger.info("NIB OCR: response_len=%d", len(response_text))

        # Parse JSON response
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error("NIB OCR: JSON parsing failed")
            return NibExtractResponse(success=False, message="Could not parse OCR response")

        # Clean NIB (keep only digits)
        nib = extracted.get("nib", "")
        if nib:
            nib_clean = re.sub(r"\D", "", nib)
            # Validate 13 digits
            if len(nib_clean) != 13:
                logger.warning("NIB OCR: extracted value doesn't have 13 digits")
                nib = nib_clean
            else:
                nib = nib_clean

        # Save to DB if extracted successfully
        if nib:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE clients SET nib = $1, updated_at = NOW() WHERE id = $2",
                    nib,
                    request.client_id,
                )
                logger.info(f"Saved NIB for client {request.client_id}")

        await invalidate_cache("zantara:crm_clients_documents:*")
        return NibExtractResponse(
            success=True,
            nib=nib if nib else None,
            company_name=extracted.get("company_name"),
            kbli_code=extracted.get("kbli_code"),
            message=f"OCR completed with confidence {extracted.get('confidence', 'unknown')}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"NIB extraction failed: {e}", exc_info=True)
        return NibExtractResponse(success=False, message=f"Extraction failed: {str(e)}")


# ================================================
@router.get("/client/{client_id}/required-documents")
async def get_client_required_documents(
    client_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> list[Any]:
    """Get all required documents for a client across all their practices (for Portal)."""
    try:
        async with db_pool.acquire() as conn:
            # RBAC: verify user has access to this specific client
            await verify_client_access(client_id, current_user, conn, allow_assigned=True)

            rows = await conn.fetch(
                """
                SELECT
                    prd.id, prd.practice_id, prd.document_type, prd.document_label,
                    prd.description, prd.is_required, prd.uploaded_by_client,
                    prd.status, prd.client_notes, prd.team_member_notes,
                    COALESCE(pt.name, p.practice_type_code) as process_name,
                    p.status as process_status
                FROM practice_required_documents prd
                JOIN practices p ON prd.practice_id = p.id
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE p.client_id = $1 AND p.status NOT IN ('completed', 'cancelled')
                ORDER BY prd.is_required DESC, prd.created_at DESC
                """,
                client_id,
            )

            return [
                {
                    "id": row["id"],
                    "practice_id": row["practice_id"],
                    "process_name": row["process_name"],
                    "process_status": row["process_status"],
                    "document_type": row["document_type"],
                    "document_label": row["document_label"],
                    "description": row["description"],
                    "is_required": row["is_required"],
                    "uploaded_by_client": row["uploaded_by_client"],
                    "status": row["status"],
                    "client_notes": row["client_notes"],
                    "team_member_notes": row["team_member_notes"],
                }
                for row in rows
            ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get client required documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}") from e
