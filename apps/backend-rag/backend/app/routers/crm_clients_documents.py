"""
CRM Clients - Document OCR & Metrics

Split from crm_clients.py for maintainability.
Provides: CRM metrics (summary, refresh), Passport OCR (basic + enhanced),
Document soft-delete, NPWP OCR, NIB OCR, Required documents for portal.
"""

from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

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


@router.post("/extract-passport", response_model=PassportExtractResponse)
async def extract_passport_data(
    request: PassportExtractRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PassportExtractResponse:
    """
    Extract passport number and expiry date from passport image using Gemini Vision.
    Updates the client record with extracted data.
    """
    import base64

    import httpx

    try:
        # RBAC: verify caller has access to this client before reading/writing
        async with db_pool.acquire() as conn:
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

        from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

        if not GENAI_AVAILABLE:
            return PassportExtractResponse(success=False, message="Vision service not available")

        # Initialize Gemini client
        genai_client = GenAIClient()
        if not genai_client.is_available:
            return PassportExtractResponse(success=False, message="Gemini Vision not configured")

        # Download image from Google Drive
        image_url = request.image_url
        if "/view" in image_url:
            # Convert view URL to direct download URL
            import re

            match = re.search(r"/d/([^/]+)", image_url)
            if match:
                file_id = match.group(1)
                image_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        logger.info(f"Downloading passport image from: {image_url[:50]}...")

        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            response = await http_client.get(image_url, timeout=30.0)
            if response.status_code != 200:
                return PassportExtractResponse(
                    success=False, message=f"Failed to download image: HTTP {response.status_code}",
                )
            image_data = response.content

        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode()

        # Determine MIME type
        mime_type = "image/jpeg"
        if image_data[:4] == b"\x89PNG":
            mime_type = "image/png"
        elif image_data[:4] == b"%PDF":
            mime_type = "application/pdf"

        # Build multimodal content for Gemini Vision
        ocr_prompt = """Analyze this passport image and extract the following information.
Return ONLY a JSON object with these fields:
{
  "passport_number": "the passport number or null if not found",
  "expiry_date": "expiry date in YYYY-MM-DD format or null if not found"
}

Look for:
- The passport number (usually alphanumeric, 8-9 characters)
- The expiry date or date of expiration field

IMPORTANT: Return ONLY the JSON object, no additional text."""

        contents = [
            {"text": ocr_prompt},
            {"inline_data": {"mime_type": mime_type, "data": image_base64}},
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-2.0-flash-lite",
            max_output_tokens=500,
        )

        response_text = result.get("text", "")
        logger.info(f"Gemini OCR response: {response_text[:200]}...")

        # Parse JSON response
        import json
        import re as regex

        # Extract JSON from response (handle markdown code blocks)
        json_match = regex.search(r"\{[^}]+\}", response_text, regex.DOTALL)
        if not json_match:
            return PassportExtractResponse(success=False, message="Could not parse OCR response")

        extracted_data = json.loads(json_match.group())
        passport_number = extracted_data.get("passport_number")
        expiry_date = extracted_data.get("expiry_date")

        if not passport_number and not expiry_date:
            return PassportExtractResponse(success=False, message="No passport data found in image")

        # Update client record
        async with db_pool.acquire() as conn:
            update_fields = []
            update_values = []
            param_num = 1

            if passport_number:
                update_fields.append(f"passport_number = ${param_num}")
                update_values.append(passport_number)
                param_num += 1

            if expiry_date:
                update_fields.append(f"passport_expiry = ${param_num}")
                update_values.append(expiry_date)
                param_num += 1

            if update_fields:
                update_values.append(request.client_id)
                await conn.execute(
                    f"UPDATE clients SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = ${param_num}",
                    *update_values,
                )
                logger.info(f"Updated client {request.client_id} with extracted passport data")

        return PassportExtractResponse(
            success=True,
            passport_number=passport_number,
            passport_expiry=expiry_date,
            message="Passport data extracted successfully",
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse OCR JSON: {e}")
        return PassportExtractResponse(success=False, message="Failed to parse extracted data")
    except Exception as e:
        logger.error(f"Passport OCR extraction failed: {e}")
        return PassportExtractResponse(success=False, message=str(e))


# ================================================
# ENHANCED PASSPORT OCR (Full Extraction)
# ================================================


class PassportEnhancedRequest(BaseModel):
    """Request model for enhanced passport OCR"""

    client_id: int
    file_id: str  # Google Drive file ID


class PassportEnhancedResponse(BaseModel):
    """Response model for enhanced passport OCR"""

    success: bool
    passport_number: str | None = None
    expiry_date: str | None = None
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    birthplace: str | None = None
    nationality: str | None = None
    mrz_line1: str | None = None
    mrz_line2: str | None = None
    confidence: float = 0.0
    name_match: bool | None = None
    message: str | None = None


@router.post("/extract-passport-enhanced", response_model=PassportEnhancedResponse)
async def extract_passport_enhanced(
    request: PassportEnhancedRequest,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PassportEnhancedResponse:
    """
    Enhanced passport OCR using Gemini Vision.
    Extracts all visible data from passport and updates client record.

    Returns:
        - passport_number
        - expiry_date (linked to alert)
        - full_name (with fuzzy match verification)
        - gender (M/F)
        - date_of_birth
        - birthplace (for enrichment)
        - nationality
        - MRZ lines (if visible)
        - confidence score
    """
    import base64
    import json
    from difflib import SequenceMatcher

    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient
    from backend.services.integrations.google_drive_service import GoogleDriveService

    try:
        if not GENAI_AVAILABLE:
            return PassportEnhancedResponse(success=False, message="Vision service not available")

        genai_client = GenAIClient()
        if not genai_client.is_available:
            return PassportEnhancedResponse(success=False, message="Gemini Vision not configured")

        # Get current client data for name verification
        async with db_pool.acquire() as conn:
            # RBAC: verify user has access to this specific client
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

            client = await conn.fetchrow(
                "SELECT full_name FROM clients WHERE id = $1", request.client_id,
            )
            if not client:
                return PassportEnhancedResponse(
                    success=False, message=f"Client {request.client_id} not found",
                )
            existing_name = client["full_name"]

        # Download image via Google Drive API (SYSTEM OAuth token)
        drive_service = GoogleDriveService(db_pool)
        access_token = await drive_service.get_valid_token(GoogleDriveService.SYSTEM_USER_ID)

        if not access_token:
            return PassportEnhancedResponse(
                success=False, message="Google Drive not connected. Please connect via Settings.",
            )

        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            # Get file metadata
            meta_response = await http_client.get(
                f"https://www.googleapis.com/drive/v3/files/{request.file_id}",
                params={"fields": "mimeType,name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if meta_response.status_code != 200:
                return PassportEnhancedResponse(
                    success=False,
                    message=f"Failed to get file metadata: {meta_response.status_code}",
                )
            metadata = meta_response.json()
            mime_type = metadata.get("mimeType", "image/jpeg")

            # Download file
            download_response = await http_client.get(
                f"https://www.googleapis.com/drive/v3/files/{request.file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if download_response.status_code != 200:
                return PassportEnhancedResponse(
                    success=False,
                    message=f"Failed to download file: {download_response.status_code}",
                )
            image_data = download_response.content

        # Build enhanced OCR prompt - simplified to avoid token truncation
        ocr_prompt = """Extract passport data. Return ONLY this JSON:

{
  "passport_number": "XX123456",
  "expiry_date": "YYYY-MM-DD",
  "full_name": "SURNAME GIVEN_NAMES",
  "surname": "SURNAME",
  "given_names": "GIVEN NAMES",
  "gender": "M or F",
  "date_of_birth": "YYYY-MM-DD",
  "birthplace": "city, country",
  "nationality": "country code",
  "confidence": 0.95
}

Use null for unclear fields. Return ONLY JSON."""

        # Call Gemini Vision
        contents = [
            ocr_prompt,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(image_data).decode(),
                },
            },
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-2.0-flash-lite",
            max_output_tokens=4000,  # Increased further to prevent JSON truncation
        )

        response_text = result.get("text", "")
        logger.info(f"Enhanced OCR response: {response_text[:300]}...")

        # Parse JSON response (handles code fences and chain-of-thought)
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"OCR JSON parsing failed. Raw response: {response_text[:500]}")
            return PassportEnhancedResponse(success=False, message="Could not parse OCR response")

        # Verify name match
        name_match = None
        ratio = None
        extracted_name = extracted.get("full_name")
        if extracted_name and existing_name:
            # Fuzzy match with 80% threshold
            ratio = SequenceMatcher(
                None,
                existing_name.upper().replace(",", " ").split(),
                extracted_name.upper().replace(",", " ").split(),
            ).ratio()
            name_match = ratio >= 0.8

        # Prepare OCR data for storage
        ocr_data = {
            "extracted_at": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
            "raw_response": extracted,
            "file_id": request.file_id,
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
                    logger.warning(f"Invalid expiry_date format: {extracted['expiry_date']}")

            if extracted.get("gender"):
                update_parts.append(f"gender = ${param_idx}")
                params.append(extracted["gender"][0].upper())  # M or F
                param_idx += 1

            if extracted.get("date_of_birth"):
                try:
                    dob = datetime.strptime(extracted["date_of_birth"], "%Y-%m-%d").date()
                    update_parts.append(f"date_of_birth = ${param_idx}")
                    params.append(dob)
                    param_idx += 1
                except ValueError:
                    logger.warning(f"Invalid date_of_birth format: {extracted['date_of_birth']}")

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

        return PassportEnhancedResponse(
            success=True,
            passport_number=extracted.get("passport_number"),
            expiry_date=extracted.get("expiry_date"),
            full_name=extracted.get("full_name"),
            gender=extracted.get("gender"),
            date_of_birth=extracted.get("date_of_birth"),
            birthplace=extracted.get("birthplace"),
            nationality=extracted.get("nationality"),
            mrz_line1=extracted.get("mrz_line1"),
            mrz_line2=extracted.get("mrz_line2"),
            confidence=extracted.get("confidence", 0.0),
            name_match=name_match,
            message="Passport data extracted and saved successfully",
        )

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.warning(f"Enhanced OCR JSON parse error: {e}")
        return PassportEnhancedResponse(success=False, message="Failed to parse OCR response")
    except Exception as e:
        logger.error(f"Enhanced passport OCR failed: {e}")
        return PassportEnhancedResponse(success=False, message=str(e))


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
    import re

    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

    try:
        # RBAC check: verify caller has access to this client
        async with db_pool.acquire() as conn:
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

        if not GENAI_AVAILABLE:
            return NpwpExtractResponse(success=False, message="Vision service not available")

        genai_client = GenAIClient()
        if not genai_client.is_available:
            return NpwpExtractResponse(success=False, message="Gemini Vision not configured")

        # Validate base64 before decoding
        raw = request.file.split(",")[-1] if "," in request.file else request.file
        try:
            base64.b64decode(raw, validate=True)
        except Exception:
            return NpwpExtractResponse(success=False, message="Invalid base64 data")

        # Decode base64 file
        try:
            file_data = base64.b64decode(raw)
        except Exception as e:
            logger.error(f"Failed to decode base64 file: {e}")
            return NpwpExtractResponse(success=False, message="Invalid file format")

        # Determine mime type from file extension
        file_ext = request.file_name.lower().split(".")[-1] if "." in request.file_name else "jpg"
        mime_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "pdf": "application/pdf",
        }
        mime_type = mime_type_map.get(file_ext, "image/jpeg")

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

        # Call Gemini Vision
        contents = [
            ocr_prompt,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(file_data).decode(),
                },
            },
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-2.0-flash-lite",
            max_output_tokens=2000,
        )

        response_text = result.get("text", "")
        logger.info(f"NPWP OCR response: {response_text[:300]}...")

        # Parse JSON response
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"NPWP OCR JSON parsing failed. Raw: {response_text[:500]}")
            return NpwpExtractResponse(success=False, message="Could not parse OCR response")

        # Clean NPWP (remove dots, keep only digits)
        npwp = extracted.get("npwp", "")
        if npwp:
            npwp_clean = re.sub(r"\D", "", npwp)
            # Validate 15 digits
            if len(npwp_clean) != 15:
                logger.warning(f"NPWP doesn't have 15 digits: {npwp_clean}")
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
    import re

    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

    try:
        # RBAC check: verify caller has access to this client
        async with db_pool.acquire() as conn:
            await verify_client_access(request.client_id, current_user, conn, allow_assigned=True)

        if not GENAI_AVAILABLE:
            return NibExtractResponse(success=False, message="Vision service not available")

        genai_client = GenAIClient()
        if not genai_client.is_available:
            return NibExtractResponse(success=False, message="Gemini Vision not configured")

        # Validate base64 before decoding
        raw = request.file.split(",")[-1] if "," in request.file else request.file
        try:
            base64.b64decode(raw, validate=True)
        except Exception:
            return NibExtractResponse(success=False, message="Invalid base64 data")

        # Decode base64 file
        try:
            file_data = base64.b64decode(raw)
        except Exception as e:
            logger.error(f"Failed to decode base64 file: {e}")
            return NibExtractResponse(success=False, message="Invalid file format")

        # Determine mime type from file extension
        file_ext = request.file_name.lower().split(".")[-1] if "." in request.file_name else "jpg"
        mime_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "pdf": "application/pdf",
        }
        mime_type = mime_type_map.get(file_ext, "image/jpeg")

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

        # Call Gemini Vision
        contents = [
            ocr_prompt,
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(file_data).decode(),
                },
            },
        ]

        result = await genai_client.generate_content(
            contents=contents,
            model="gemini-2.0-flash-lite",
            max_output_tokens=2000,
        )

        response_text = result.get("text", "")
        logger.info(f"NIB OCR response: {response_text[:300]}...")

        # Parse JSON response
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"NIB OCR JSON parsing failed. Raw: {response_text[:500]}")
            return NibExtractResponse(success=False, message="Could not parse OCR response")

        # Clean NIB (keep only digits)
        nib = extracted.get("nib", "")
        if nib:
            nib_clean = re.sub(r"\D", "", nib)
            # Validate 13 digits
            if len(nib_clean) != 13:
                logger.warning(f"NIB doesn't have 13 digits: {nib_clean}")
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
