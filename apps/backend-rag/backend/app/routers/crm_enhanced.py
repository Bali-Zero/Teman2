"""
CRM Enhanced Routes - Family Members, Documents, Expiry Alerts

Provides endpoints for:
- Client family members (spouse, children)
- Document management with categories
- Expiry alerts with color indicators
- Auto OCR for passport documents
"""

import base64
import logging
import re as regex
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import extract_json_from_llm_response
from backend.app.utils.json_utils import to_jsonb
from backend.services.crm.document_categorizer import CATEGORY_TO_FOLDER, auto_categorize_document
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logger = logging.getLogger(__name__)


# ============================================
# AUTO OCR HELPER
# ============================================


async def _download_drive_file(file_id: str) -> tuple[bytes, str]:
    """
    Download a file from Google Drive using Service Account credentials.
    Returns (file_content, mime_type).
    Raises RuntimeError on failure.
    """
    import google.auth.transport.requests as google_auth_requests
    import httpx

    drive_service = ServiceAccountDriveService()
    if not drive_service.credentials.token:
        drive_service.credentials.refresh(google_auth_requests.Request())
    access_token = drive_service.credentials.token
    if not access_token:
        raise RuntimeError("Drive not connected")

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        meta_response = await http_client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"fields": "mimeType,name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if meta_response.status_code != 200:
            raise RuntimeError(f"Metadata fetch failed: {meta_response.status_code}")

        mime_type = meta_response.json().get("mimeType", "image/jpeg")

        download_response = await http_client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if download_response.status_code != 200:
            raise RuntimeError(f"Download failed: {download_response.status_code}")

        return download_response.content, mime_type


async def _gemini_ocr(image_data: bytes, mime_type: str, prompt: str) -> str:
    """
    Run OCR on image data.
    Strategy:
      1. Ollama qwen2.5vl:7b (local, free, confirmed working for passports)
      2. Gemini CLI (free via Ultra subscription)
      3. Gemini API (paid, fast fallback)
    Returns raw text response from the model.
    """
    import asyncio
    import base64 as _base64
    import shutil
    import tempfile

    # --- Attempt 1: Ollama qwen2.5vl:7b (local, free) ---
    try:
        import httpx as _httpx

        from backend.llm.ollama_client import is_ollama_available

        _OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
        if await is_ollama_available(_OLLAMA_VISION_MODEL):
            image_b64 = _base64.b64encode(image_data).decode()
            ollama_prompt = f"{prompt} Return JSON only, null for missing fields."
            async with _httpx.AsyncClient(timeout=120.0) as _client:
                resp = await _client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": _OLLAMA_VISION_MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": ollama_prompt,
                                "images": [image_b64],
                            }
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "").strip()
                if content:
                    logger.info(
                        f"OCR via Ollama {_OLLAMA_VISION_MODEL} (local): {len(content)} chars"
                    )
                    return content
                logger.warning("Ollama vision returned empty, falling back to Gemini")
    except Exception as _e:
        logger.warning(f"Ollama vision error: {_e}, falling back to Gemini")

    # --- Attempt 2: Gemini CLI (free via Ultra subscription) ---
    gemini_path = shutil.which("gemini")
    if gemini_path:
        try:
            # Determine file extension from mime type
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
                "application/pdf": ".pdf",
            }
            ext = ext_map.get(mime_type, ".jpg")

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir="/tmp") as f:
                f.write(image_data)
                tmp_path = f.name

            try:
                cli_prompt = (
                    f"Use read_file to read the image at {tmp_path}. "
                    f"{prompt} Return JSON only, null for missing fields."
                )
                process = await asyncio.create_subprocess_exec(
                    gemini_path,
                    "-p",
                    cli_prompt,
                    "-o",
                    "text",
                    "--yolo",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd="/tmp",
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90)

                if process.returncode == 0 and stdout:
                    response_text = stdout.decode("utf-8", errors="replace").strip()
                    # Remove the "Shell cwd was reset" line if present
                    lines = [
                        line
                        for line in response_text.split("\n")
                        if not line.startswith("Shell cwd was reset")
                    ]
                    response_text = "\n".join(lines).strip()
                    if response_text:
                        logger.info(f"OCR via Gemini CLI (free): {len(response_text)} chars")
                        return response_text
                    logger.warning("Gemini CLI returned empty response, falling back to API")
                else:
                    stderr_text = stderr.decode("utf-8", errors="replace")[:200] if stderr else ""
                    logger.warning(f"Gemini CLI failed (rc={process.returncode}): {stderr_text}")
            finally:
                import os

                os.unlink(tmp_path)

        except asyncio.TimeoutError:
            logger.warning("Gemini CLI timed out (90s), falling back to API")
            try:
                import os

                os.unlink(tmp_path)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Gemini CLI error: {e}, falling back to API")

    # --- Attempt 2: Gemini API (paid, fast) ---
    from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

    if not GENAI_AVAILABLE:
        raise RuntimeError("Neither Gemini CLI nor Gemini API available")

    genai_client = GenAIClient()
    if not genai_client.is_available:
        raise RuntimeError("Gemini not configured")

    contents = [
        prompt,
        {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_data).decode(),
            }
        },
    ]

    result = await genai_client.generate_content(
        contents=contents,
        model="gemini-2.5-flash",
        max_output_tokens=4096,
    )

    response_text = result.get("text", "")
    logger.info(f"OCR via Gemini API (paid): {len(response_text)} chars")
    return response_text


async def _auto_ocr_passport(client_id: int, file_id: str) -> dict:
    """
    Automatically run OCR on passport image and update client record.
    Runs in background after document upload.
    Creates its own db connection to avoid pool lifecycle issues.
    """
    import os

    import asyncpg

    db_pool = None
    try:
        # Create own pool for background task
        db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)

        # Get client name for verification
        async with db_pool.acquire() as conn:
            client = await conn.fetchrow("SELECT full_name FROM clients WHERE id = $1", client_id)
            if not client:
                return {"success": False, "error": "Client not found"}
            existing_name = client["full_name"]

        # Download from Drive + OCR (CLI free → API fallback)
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = "Extract from this passport: passport_number, expiry_date (YYYY-MM-DD), full_name, gender (M/F), date_of_birth (YYYY-MM-DD), birthplace, nationality, confidence (0-1)."

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR response for client {client_id}: {response_text[:200]}...")

        # Parse JSON (handles code fences and chain-of-thought)
        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(
                f"Auto OCR JSON parsing failed for client {client_id}. Raw: {response_text[:300]}"
            )
            return {"success": False, "error": "Could not parse OCR response"}

        # Normalize date formats (DD-MM-YYYY → YYYY-MM-DD)
        for date_field in ["expiry_date", "date_of_birth"]:
            if extracted.get(date_field):
                date_str = extracted[date_field]
                if regex.match(r"\d{2}-\d{2}-\d{4}", date_str):
                    parts = date_str.split("-")
                    extracted[date_field] = f"{parts[2]}-{parts[1]}-{parts[0]}"

        # Normalize gender (MALE/FEMALE → M/F)
        if extracted.get("gender"):
            g = extracted["gender"].upper()
            if g in ["MALE", "M"]:
                extracted["gender"] = "M"
            elif g in ["FEMALE", "F"]:
                extracted["gender"] = "F"

        # Name match verification
        name_match_ratio = None
        if extracted.get("full_name") and existing_name:
            ratio = SequenceMatcher(
                None,
                existing_name.upper().replace(",", " ").split(),
                extracted["full_name"].upper().replace(",", " ").split(),
            ).ratio()
            name_match_ratio = ratio

        # Prepare OCR data
        ocr_data = {
            "extracted_at": datetime.utcnow().isoformat(),
            "auto_triggered": True,
            "raw_response": extracted,
            "file_id": file_id,
            "confidence": extracted.get("confidence", 0.0),
            "name_match_ratio": name_match_ratio,
        }

        # Update client record
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
                    expiry = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                    update_parts.append(f"passport_expiry = ${param_idx}")
                    params.append(expiry)
                    param_idx += 1
                except ValueError:
                    pass

            if extracted.get("gender"):
                update_parts.append(f"gender = ${param_idx}")
                params.append(extracted["gender"][0].upper())
                param_idx += 1

            if extracted.get("date_of_birth"):
                try:
                    dob = datetime.strptime(extracted["date_of_birth"], "%Y-%m-%d").date()
                    update_parts.append(f"date_of_birth = ${param_idx}")
                    params.append(dob)
                    param_idx += 1
                except ValueError:
                    pass

            if extracted.get("birthplace"):
                update_parts.append(f"birthplace = ${param_idx}")
                params.append(extracted["birthplace"])
                param_idx += 1

            if extracted.get("nationality"):
                update_parts.append(f"nationality = ${param_idx}")
                params.append(extracted["nationality"])
                param_idx += 1

            params.append(client_id)
            update_sql = f"""
                UPDATE clients SET {", ".join(update_parts)}, updated_at = NOW()
                WHERE id = ${param_idx}
            """
            await conn.execute(update_sql, *params)

        logger.info(
            f"Auto OCR completed for client {client_id}: {extracted.get('passport_number', 'N/A')}"
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if db_pool:
            await db_pool.close()


async def _auto_ocr_visa(client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on visa/KITAS/KITAP document → extract visa_type, expiry, number.
    Updates documents.expiry_date and documents.ocr_extracted_data.
    """
    import os

    import asyncpg

    db_pool = None
    try:
        db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)

        # Download from Drive + OCR (CLI free → API fallback)
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = "Extract from this visa/immigration document: visa_type (KITAS/KITAP/B211/C31/etc), visa_number, expiry_date (YYYY-MM-DD), issue_date (YYYY-MM-DD), full_name, sponsor, telex_number, confidence (0-1)."

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR visa response for client {client_id}: {response_text[:200]}...")

        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"Auto OCR visa JSON parsing failed for client {client_id}")
            return {"success": False, "error": "Could not parse OCR response"}

        # Normalize date
        for date_field in ["expiry_date", "issue_date"]:
            if extracted.get(date_field):
                date_str = extracted[date_field]
                if regex.match(r"\d{2}-\d{2}-\d{4}", date_str):
                    parts = date_str.split("-")
                    extracted[date_field] = f"{parts[2]}-{parts[1]}-{parts[0]}"

        ocr_data = {
            "extracted_at": datetime.utcnow().isoformat(),
            "auto_triggered": True,
            "raw_response": extracted,
            "file_id": file_id,
            "document_type": "visa",
        }

        async with db_pool.acquire() as conn:
            # Update document with OCR data and expiry
            update_parts = [
                "ocr_status = 'completed'",
                "ocr_completed_at = NOW()",
                "ocr_extracted_data = $1",
            ]
            params: list[Any] = [to_jsonb(ocr_data)]
            param_idx = 2

            if extracted.get("expiry_date"):
                try:
                    expiry = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                    update_parts.append(f"expiry_date = ${param_idx}")
                    params.append(expiry)
                    param_idx += 1
                except ValueError:
                    pass

            if extracted.get("issue_date"):
                try:
                    issue = datetime.strptime(extracted["issue_date"], "%Y-%m-%d").date()
                    update_parts.append(f"issue_date = ${param_idx}")
                    params.append(issue)
                    param_idx += 1
                except ValueError:
                    pass

            if doc_id:
                params.append(doc_id)
                await conn.execute(
                    f"UPDATE documents SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = ${param_idx}",
                    *params,
                )

        logger.info(
            f"Auto OCR visa completed for client {client_id}: {extracted.get('visa_type', 'N/A')}"
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR visa failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if db_pool:
            await db_pool.close()


async def _auto_ocr_nib(client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on NIB (Nomor Induk Berusaha) document → extract NIB number, company_name, KBLI codes.
    Updates companies table if client has a linked company.
    """
    import os

    import asyncpg

    db_pool = None
    try:
        db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)

        # Download from Drive + OCR (CLI free → API fallback)
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = "Extract from this NIB (Nomor Induk Berusaha) document: nib_number, company_name, kbli_codes (array of strings), address, issue_date (YYYY-MM-DD), capital_amount, confidence (0-1)."

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR NIB response for client {client_id}: {response_text[:200]}...")

        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"Auto OCR NIB JSON parsing failed for client {client_id}")
            return {"success": False, "error": "Could not parse OCR response"}

        ocr_data = {
            "extracted_at": datetime.utcnow().isoformat(),
            "auto_triggered": True,
            "raw_response": extracted,
            "file_id": file_id,
            "document_type": "nib",
        }

        async with db_pool.acquire() as conn:
            # Update document with OCR data
            if doc_id:
                await conn.execute(
                    """UPDATE documents
                    SET ocr_status = 'completed', ocr_completed_at = NOW(),
                        ocr_extracted_data = $1, updated_at = NOW()
                    WHERE id = $2""",
                    to_jsonb(ocr_data),
                    doc_id,
                )

            # Try to update linked company
            if extracted.get("nib_number") or extracted.get("company_name"):
                company = await conn.fetchrow(
                    """SELECT c.id FROM companies c
                    JOIN client_company_links ccl ON ccl.company_id = c.id
                    WHERE ccl.client_id = $1 LIMIT 1""",
                    client_id,
                )
                if company:
                    update_parts = []
                    params: list[Any] = []
                    param_idx = 1
                    if extracted.get("nib_number"):
                        update_parts.append(f"nib = ${param_idx}")
                        params.append(extracted["nib_number"])
                        param_idx += 1
                    if extracted.get("company_name"):
                        update_parts.append(f"company_name = ${param_idx}")
                        params.append(extracted["company_name"])
                        param_idx += 1
                    if update_parts:
                        params.append(company["id"])
                        await conn.execute(
                            f"UPDATE companies SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = ${param_idx}",
                            *params,
                        )

        logger.info(
            f"Auto OCR NIB completed for client {client_id}: {extracted.get('nib_number', 'N/A')}"
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR NIB failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if db_pool:
            await db_pool.close()


async def _auto_ocr_npwp(client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on NPWP (tax ID) document → extract NPWP number, address, KPP.
    Updates clients or companies table.
    """
    import os

    import asyncpg

    db_pool = None
    try:
        db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)

        # Download from Drive + OCR (CLI free → API fallback)
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = "Extract from this NPWP (Indonesian Tax ID) document: npwp_number, full_name, address, kpp_name (Kantor Pelayanan Pajak), registration_date (YYYY-MM-DD), confidence (0-1)."

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR NPWP response for client {client_id}: {response_text[:200]}...")

        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"Auto OCR NPWP JSON parsing failed for client {client_id}")
            return {"success": False, "error": "Could not parse OCR response"}

        ocr_data = {
            "extracted_at": datetime.utcnow().isoformat(),
            "auto_triggered": True,
            "raw_response": extracted,
            "file_id": file_id,
            "document_type": "npwp",
        }

        async with db_pool.acquire() as conn:
            # Update document with OCR data
            if doc_id:
                await conn.execute(
                    """UPDATE documents
                    SET ocr_status = 'completed', ocr_completed_at = NOW(),
                        ocr_extracted_data = $1, updated_at = NOW()
                    WHERE id = $2""",
                    to_jsonb(ocr_data),
                    doc_id,
                )

            # Update client NPWP fields
            if extracted.get("npwp_number"):
                # Check if this is a company NPWP (linked company exists)
                company = await conn.fetchrow(
                    """SELECT c.id FROM companies c
                    JOIN client_company_links ccl ON ccl.company_id = c.id
                    WHERE ccl.client_id = $1 LIMIT 1""",
                    client_id,
                )
                if company:
                    update_parts = ["npwp = $1"]
                    params: list[Any] = [extracted["npwp_number"]]
                    param_idx = 2
                    if extracted.get("kpp_name"):
                        update_parts.append(f"kpp = ${param_idx}")
                        params.append(extracted["kpp_name"])
                        param_idx += 1
                    params.append(company["id"])
                    await conn.execute(
                        f"UPDATE companies SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = ${param_idx}",
                        *params,
                    )
                else:
                    # Personal NPWP → update clients custom_fields
                    await conn.execute(
                        """UPDATE clients
                        SET custom_fields = COALESCE(custom_fields, '{}'::jsonb) || $1::jsonb,
                            updated_at = NOW()
                        WHERE id = $2""",
                        to_jsonb(
                            {"npwp": extracted["npwp_number"], "kpp": extracted.get("kpp_name")}
                        ),
                        client_id,
                    )

        logger.info(
            f"Auto OCR NPWP completed for client {client_id}: {extracted.get('npwp_number', 'N/A')}"
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR NPWP failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if db_pool:
            await db_pool.close()


async def _dispatch_ocr_by_folder(
    client_id: int,
    file_id: str,
    folder_name: str,
    filename: str,
    doc_id: int | None = None,
) -> dict:
    """
    Central OCR dispatcher. Routes to the correct OCR handler based on
    subfolder name and filename keywords.

    Returns:
        {"dispatched": True, "handler": "passport"} or {"dispatched": False}
    """
    fn_lower = filename.lower()
    folder_lower = folder_name.lower() if folder_name else ""

    # Passport detection
    if "passport" in fn_lower or (folder_lower.startswith("00_") and "passport" in fn_lower):
        logger.info(f"OCR dispatch: passport detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "passport",
            "result": await _auto_ocr_passport(client_id, file_id),
        }

    # Visa / KITAS / KITAP detection
    visa_keywords = [
        "kitas",
        "kitap",
        "visa",
        "voa",
        "b211",
        "c31",
        "itas",
        "itap",
        "telex",
        "evisa",
    ]
    if any(kw in fn_lower for kw in visa_keywords) or folder_lower.startswith("01_"):
        # Only auto-OCR if filename suggests a visa document (not random immigration files)
        if (
            any(kw in fn_lower for kw in visa_keywords)
            or "permit" in fn_lower
            or "stay" in fn_lower
        ):
            logger.info(f"OCR dispatch: visa detected for client {client_id}, file {filename}")
            return {
                "dispatched": True,
                "handler": "visa",
                "result": await _auto_ocr_visa(client_id, file_id, doc_id),
            }

    # NIB detection
    if "nib" in fn_lower or "berusaha" in fn_lower or "oss" in fn_lower:
        logger.info(f"OCR dispatch: NIB detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "nib",
            "result": await _auto_ocr_nib(client_id, file_id, doc_id),
        }

    # NPWP detection
    if "npwp" in fn_lower or "tax" in fn_lower and "id" in fn_lower:
        logger.info(f"OCR dispatch: NPWP detected for client {client_id}, file {filename}")
        return {
            "dispatched": True,
            "handler": "npwp",
            "result": await _auto_ocr_npwp(client_id, file_id, doc_id),
        }

    logger.debug(f"OCR dispatch: no handler matched for file {filename} in {folder_name}")
    return {"dispatched": False}


router = APIRouter(prefix="/api/crm", tags=["crm-enhanced"])


# ============================================
# MODELS
# ============================================


class FamilyMemberCreate(BaseModel):
    full_name: str
    relationship: str  # 'spouse', 'child', 'parent', 'sibling', 'other'
    date_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    current_visa_type: str | None = None
    visa_expiry: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class FamilyMemberUpdate(BaseModel):
    full_name: str | None = None
    relationship: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: str | None = None
    current_visa_type: str | None = None
    visa_expiry: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class DocumentCreate(BaseModel):
    document_type: str
    document_category: str | None = None  # 'immigration', 'pma', 'tax', 'personal'
    file_name: str | None = None
    file_id: str | None = None  # Google Drive file ID
    file_url: str | None = None
    google_drive_file_url: str | None = None
    expiry_date: str | None = None
    notes: str | None = None
    family_member_id: int | None = None  # If document belongs to family member
    practice_id: int | None = None


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    document_category: str | None = None
    file_name: str | None = None
    file_id: str | None = None
    file_url: str | None = None
    google_drive_file_url: str | None = None
    expiry_date: str | None = None
    status: str | None = None
    notes: str | None = None
    is_archived: bool | None = None


class ClientProfileUpdate(BaseModel):
    avatar_url: str | None = None
    google_drive_folder_id: str | None = None
    date_of_birth: str | None = None
    passport_expiry: str | None = None
    company_name: str | None = None


# ============================================
# CLIENT PROFILE ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/profile")
async def get_client_profile(
    client_id: int,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get enhanced client profile with family members, documents, and expiry alerts.
    RBAC REMOVED: All authenticated users can view all client profiles.
    """
    async with pool.acquire() as conn:
        # Get client with extended fields
        client = await conn.fetchrow(
            """
            SELECT
                id, uuid, full_name, email, phone, whatsapp,
                nationality, passport_number, passport_expiry,
                date_of_birth, gender, avatar_url, company_name,
                google_drive_folder_id, status, client_type,
                assigned_to, address, notes, tags, custom_fields,
                first_contact_date, last_interaction_date,
                created_at, updated_at
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get family members
        family_members = await conn.fetch(
            """
            SELECT
                id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes,
                created_at, updated_at
            FROM client_family_members
            WHERE client_id = $1
            ORDER BY
                CASE relationship
                    WHEN 'spouse' THEN 1
                    WHEN 'child' THEN 2
                    ELSE 3
                END,
                full_name
            """,
            client_id,
        )

        # Get documents grouped by category
        documents = await conn.fetch(
            """
            SELECT
                d.id, d.document_type, d.document_category,
                d.file_name, d.file_id, d.file_url, d.google_drive_file_url,
                d.status, d.expiry_date, d.notes, d.family_member_id,
                d.practice_id, d.created_at, d.updated_at,
                fm.full_name as family_member_name,
                CASE
                    WHEN d.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color
            FROM documents d
            LEFT JOIN client_family_members fm ON d.family_member_id = fm.id
            WHERE d.client_id = $1
              AND (d.is_archived IS NULL OR d.is_archived = false)
            ORDER BY d.document_category, d.document_type
            """,
            client_id,
        )

        # Get expiry alerts
        expiry_alerts = await conn.fetch(
            """
            SELECT
                entity_type, entity_id, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            WHERE client_id = $1
              AND alert_color IN ('expired', 'red', 'yellow')
            ORDER BY
                CASE alert_color
                    WHEN 'expired' THEN 1
                    WHEN 'red' THEN 2
                    WHEN 'yellow' THEN 3
                END,
                expiry_date
            """,
            client_id,
        )

        # Get practices with financial + assignment fields for frontend
        practices = await conn.fetch(
            """
            SELECT
                p.id, p.status, p.priority, p.expiry_date, p.start_date,
                p.completion_date, p.title,
                p.quoted_price, p.actual_price, p.payment_status,
                p.assigned_to,
                COALESCE(pt.code, p.practice_type_code) as practice_type_code,
                COALESCE(pt.name, p.title) as practice_type_name,
                CASE
                    WHEN p.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN p.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN p.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color
            FROM practices p
            LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.client_id = $1
            ORDER BY
                CASE p.status
                    WHEN 'on_process' THEN 1
                    WHEN 'sending_invoice' THEN 2
                    WHEN 'waiting_documents' THEN 3
                    ELSE 4
                END,
                p.created_at DESC
            """,
            client_id,
        )

        # Get company links
        company_links = await conn.fetch(
            """
            SELECT
                ccl.id, ccl.company_id, ccl.role, ccl.is_primary,
                ccl.ownership_percentage, ccl.status, ccl.notes,
                c.company_name, c.company_type, c.brand_name, c.kbli_code,
                c.kbli_description, c.nib, c.npwp_company,
                c.akta_pendirian_no, c.akta_pendirian_date,
                c.akta_perubahan_no, c.akta_perubahan_date,
                c.sk_menhumkam_no, c.sk_menhumkam_date,
                c.registered_address, c.office_address, c.city, c.province,
                c.company_phone, c.company_email,
                c.status as company_status, c.setup_progress,
                c.custom_fields
            FROM client_company_links ccl
            JOIN companies c ON ccl.company_id = c.id
            WHERE ccl.client_id = $1
            ORDER BY ccl.is_primary DESC, c.company_name
            """,
            client_id,
        )

        # Get company documents via company_links
        company_documents = await conn.fetch(
            """
            SELECT
                cd.id, cd.uuid, cd.company_id, cd.document_type, cd.document_subtype,
                cd.document_number, cd.document_title, cd.description,
                cd.issue_date, cd.expiry_date, cd.status,
                cd.google_drive_file_id, cd.google_drive_file_url,
                cd.file_name, cd.file_size_kb, cd.mime_type,
                cd.is_verified, cd.created_at, cd.updated_at,
                c.company_name
            FROM company_documents cd
            JOIN companies c ON cd.company_id = c.id
            WHERE cd.company_id IN (
                SELECT company_id FROM client_company_links WHERE client_id = $1
            )
            AND cd.status = 'active'
            ORDER BY c.company_name, cd.document_type, cd.created_at DESC
            """,
            client_id,
        )

        return {
            "client": dict(client),
            "family_members": [dict(fm) for fm in family_members],
            "documents": [dict(d) for d in documents],
            "expiry_alerts": [dict(a) for a in expiry_alerts],
            "practices": [dict(p) for p in practices],
            "company_links": [dict(cl) for cl in company_links],
            "company_documents": [dict(cd) for cd in company_documents],
            "stats": {
                "family_count": len(family_members),
                "documents_count": len(documents),
                "practices_count": len(practices),
                "company_count": len(company_links),
                "company_documents_count": len(company_documents),
                "expired_count": sum(1 for a in expiry_alerts if a["alert_color"] == "expired"),
                "red_alerts": sum(1 for a in expiry_alerts if a["alert_color"] == "red"),
                "yellow_alerts": sum(1 for a in expiry_alerts if a["alert_color"] == "yellow"),
            },
        }


@router.patch("/clients/{client_id}/profile")
async def update_client_profile(
    client_id: int,
    data: ClientProfileUpdate,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update client profile fields (avatar, Google Drive folder, etc.)
    RBAC REMOVED: All authenticated users can update client profiles.
    """
    update_fields = []
    values = []
    param_num = 1

    if data.avatar_url is not None:
        update_fields.append(f"avatar_url = ${param_num}")
        values.append(data.avatar_url)
        param_num += 1

    if data.google_drive_folder_id is not None:
        update_fields.append(f"google_drive_folder_id = ${param_num}")
        values.append(data.google_drive_folder_id)
        param_num += 1

    if data.date_of_birth is not None:
        update_fields.append(f"date_of_birth = ${param_num}")
        values.append(data.date_of_birth)
        param_num += 1

    if data.passport_expiry is not None:
        update_fields.append(f"passport_expiry = ${param_num}")
        values.append(data.passport_expiry)
        param_num += 1

    if data.company_name is not None:
        update_fields.append(f"company_name = ${param_num}")
        values.append(data.company_name)
        param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(client_id)

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE clients
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num}
            """,
            *values,
        )

    return {"success": True, "message": "Client profile updated"}


# ============================================
# COMPANY LINKS ENDPOINTS
# ============================================


@router.get("/companies/by-client/{client_id}")
async def get_client_companies(
    client_id: int,
    pool: Any = Depends(get_database_pool),
    _current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get all companies linked to a client."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ccl.id as link_id, ccl.company_id, ccl.role, ccl.is_primary,
                ccl.ownership_percentage, ccl.shares_count, ccl.start_date,
                ccl.status, ccl.notes,
                c.company_name, c.company_type, c.brand_name, c.kbli_code,
                c.kbli_description, c.nib, c.npwp_company,
                c.akta_pendirian_no, c.akta_pendirian_date,
                c.akta_perubahan_no, c.akta_perubahan_date,
                c.sk_menhumkam_no, c.sk_menhumkam_date,
                c.registered_address, c.office_address, c.city, c.province,
                c.company_phone, c.company_email,
                c.status as company_status, c.setup_progress,
                c.custom_fields
            FROM client_company_links ccl
            JOIN companies c ON ccl.company_id = c.id
            WHERE ccl.client_id = $1
            ORDER BY ccl.is_primary DESC, c.company_name
            """,
            client_id,
        )
        return [dict(r) for r in rows]


@router.get("/companies/{company_id}/documents")
async def get_company_documents(
    company_id: int,
    doc_type: str | None = Query(None),
    pool: Any = Depends(get_database_pool),
    _current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get all documents for a company."""
    async with pool.acquire() as conn:
        if doc_type:
            rows = await conn.fetch(
                """
                SELECT id, uuid, company_id, document_type, document_subtype,
                       document_number, document_title, description,
                       issue_date, expiry_date, status,
                       google_drive_file_id, google_drive_file_url,
                       file_name, file_size_kb, mime_type,
                       is_verified, verified_by, verified_at,
                       created_at, updated_at
                FROM company_documents
                WHERE company_id = $1 AND document_type = $2
                ORDER BY created_at DESC
                """,
                company_id,
                doc_type,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, uuid, company_id, document_type, document_subtype,
                       document_number, document_title, description,
                       issue_date, expiry_date, status,
                       google_drive_file_id, google_drive_file_url,
                       file_name, file_size_kb, mime_type,
                       is_verified, verified_by, verified_at,
                       created_at, updated_at
                FROM company_documents
                WHERE company_id = $1
                ORDER BY created_at DESC
                """,
                company_id,
            )
        return [dict(r) for r in rows]


# ============================================
# FAMILY MEMBERS ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/family")
async def get_family_members(
    client_id: int,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """
    Get all family members for a client.
    RBAC REMOVED: All authenticated users can view family members.
    """
    async with pool.acquire() as conn:
        members = await conn.fetch(
            """
            SELECT
                id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes,
                created_at, updated_at,
                CASE
                    WHEN passport_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN passport_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN passport_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as passport_alert,
                CASE
                    WHEN visa_expiry <= CURRENT_DATE THEN 'expired'
                    WHEN visa_expiry <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN visa_expiry <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as visa_alert
            FROM client_family_members
            WHERE client_id = $1
            ORDER BY
                CASE relationship
                    WHEN 'spouse' THEN 1
                    WHEN 'child' THEN 2
                    ELSE 3
                END,
                full_name
            """,
            client_id,
        )
        return [dict(m) for m in members]


@router.post("/clients/{client_id}/family")
async def create_family_member(
    client_id: int,
    data: FamilyMemberCreate,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Add a family member to a client.
    RBAC REMOVED: All authenticated users can create family members.
    """
    async with pool.acquire() as conn:
        # Verify client exists
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Sanitize date fields - convert strings to date objects for asyncpg
        date_of_birth = None
        if data.date_of_birth:
            try:
                date_of_birth = datetime.strptime(data.date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                date_of_birth = None

        passport_expiry = None
        if data.passport_expiry:
            try:
                passport_expiry = datetime.strptime(data.passport_expiry, "%Y-%m-%d").date()
            except ValueError:
                passport_expiry = None

        visa_expiry = None
        if data.visa_expiry:
            try:
                visa_expiry = datetime.strptime(data.visa_expiry, "%Y-%m-%d").date()
            except ValueError:
                visa_expiry = None

        member_id = await conn.fetchval(
            """
            INSERT INTO client_family_members (
                client_id, full_name, relationship, date_of_birth,
                nationality, passport_number, passport_expiry,
                current_visa_type, visa_expiry, email, phone, notes
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            """,
            client_id,
            data.full_name,
            data.relationship,
            date_of_birth,  # Sanitized
            data.nationality,
            data.passport_number,
            passport_expiry,  # Sanitized
            data.current_visa_type,
            visa_expiry,  # Sanitized
            data.email,
            data.phone,
            data.notes,
        )

        return {"id": member_id, "success": True}


@router.patch("/clients/{client_id}/family/{member_id}")
async def update_family_member(
    client_id: int,
    member_id: int,
    data: FamilyMemberUpdate,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update a family member.
    RBAC REMOVED: All authenticated users can update family members.
    """
    # Date fields that need string → date object conversion for asyncpg
    date_fields = {"date_of_birth", "passport_expiry", "visa_expiry"}

    update_fields = []
    values = []
    param_num = 1

    for field, value in data.model_dump(exclude_unset=True).items():
        # Convert date fields: empty string → None, valid string → date object
        if field in date_fields:
            if value == "" or value is None:
                value = None
            elif isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    value = None

        if value is not None:
            update_fields.append(f"{field} = ${param_num}")
            values.append(value)
            param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.extend([member_id, client_id])

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            UPDATE client_family_members
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num} AND client_id = ${param_num + 1}
            """,
            *values,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Family member not found")

    return {"success": True}


@router.delete("/clients/{client_id}/family/{member_id}")
async def delete_family_member(
    client_id: int,
    member_id: int,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Delete a family member.
    RBAC REMOVED: All authenticated users can delete family members.
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM client_family_members WHERE id = $1 AND client_id = $2",
            member_id,
            client_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Family member not found")

    return {"success": True}


# ============================================
# DOCUMENTS ENDPOINTS
# ============================================


@router.get("/clients/{client_id}/documents")
async def get_client_documents(
    client_id: int,
    category: str | None = Query(
        None, description="Filter by category: immigration, pma, tax, personal"
    ),
    include_archived: bool = Query(False, description="Include archived documents"),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """
    Get all documents for a client, optionally filtered by category.
    RBAC REMOVED: All authenticated users can view documents.
    """
    async with pool.acquire() as conn:
        query = """
            SELECT
                d.id, d.document_type, d.document_category,
                d.file_name, d.file_id, d.file_url, d.google_drive_file_url,
                d.status, d.expiry_date, d.notes, d.is_archived,
                d.family_member_id, d.practice_id,
                d.created_at, d.updated_at,
                fm.full_name as family_member_name,
                CASE
                    WHEN d.expiry_date <= CURRENT_DATE THEN 'expired'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '8 months' THEN 'red'
                    WHEN d.expiry_date <= CURRENT_DATE + INTERVAL '12 months' THEN 'yellow'
                    ELSE 'green'
                END as alert_color
            FROM documents d
            LEFT JOIN client_family_members fm ON d.family_member_id = fm.id
            WHERE d.client_id = $1
        """
        params = [client_id]
        param_num = 2

        if category:
            query += f" AND d.document_category = ${param_num}"
            params.append(category)
            param_num += 1

        if not include_archived:
            query += " AND (d.is_archived IS NULL OR d.is_archived = false)"

        query += " ORDER BY d.document_category, d.document_type"

        docs = await conn.fetch(query, *params)
        return [dict(d) for d in docs]


@router.post("/clients/{client_id}/documents")
async def create_document(
    client_id: int,
    data: DocumentCreate,
    background_tasks: BackgroundTasks,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Add a document to a client. Auto-triggers OCR for passport documents.
    RBAC REMOVED: All authenticated users can create documents.
    """
    async with pool.acquire() as conn:
        # Sanitize date field - convert string to date object for asyncpg
        expiry_date = None
        if data.expiry_date:
            try:
                expiry_date = datetime.strptime(data.expiry_date, "%Y-%m-%d").date()
            except ValueError:
                expiry_date = None

        doc_id = await conn.fetchval(
            """
            INSERT INTO documents (
                client_id, document_type, document_category,
                file_name, file_id, file_url, google_drive_file_url,
                expiry_date, notes, family_member_id, practice_id,
                status, storage_type
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'google_drive', 'google_drive')
            RETURNING id
            """,
            client_id,
            data.document_type,
            data.document_category,
            data.file_name,
            data.file_id,
            data.file_url,
            data.google_drive_file_url,
            expiry_date,  # Sanitized
            data.notes,
            data.family_member_id,
            data.practice_id,
        )

        # Auto-trigger OCR via dispatcher
        ocr_triggered = False
        if data.file_id and data.document_type:
            # Determine folder from category
            folder_hint = ""
            cat = (data.document_category or "").lower()
            if cat == "immigration":
                folder_hint = "01_Immigration"
            elif cat == "tax":
                folder_hint = "03_Tax"
            elif cat == "company":
                folder_hint = "02_Company"
            background_tasks.add_task(
                _dispatch_ocr_by_folder,
                client_id,
                data.file_id,
                folder_hint,
                data.file_name or data.document_type,
                doc_id,
            )
            # Mark document as pending OCR
            await conn.execute(
                "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                doc_id,
            )
            ocr_triggered = True

        return {
            "id": doc_id,
            "success": True,
            "ocr_triggered": ocr_triggered,
        }


@router.post("/clients/{client_id}/documents/bulk")
async def create_documents_bulk(
    client_id: int,
    documents: list[DocumentCreate],
    background_tasks: BackgroundTasks,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Bulk insert documents for a client - optimized for migration.
    RBAC REMOVED: All authenticated users can bulk create documents.

    This endpoint allows inserting multiple documents in a single transaction,
    significantly improving performance during large data migrations.

    Args:
        client_id: Client database ID
        documents: Array of documents to insert (max 100 per request)
        background_tasks: FastAPI background tasks for OCR
        pool: Database connection pool
        current_user: Authenticated user

    Returns:
        {
            "success": true,
            "inserted": 50,
            "document_ids": [123, 124, ...],
            "ocr_triggered": 2,
            "failed": 0
        }

    Raises:
        HTTPException: If max limit exceeded or client not found
    """
    user_email = current_user.get("email", "").lower()

    # Enforce maximum batch size
    MAX_BATCH_SIZE = 100
    if len(documents) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_SIZE} documents per request. You provided {len(documents)}.",
        )

    if len(documents) == 0:
        raise HTTPException(status_code=400, detail="No documents provided")

    async with pool.acquire() as conn:
        # Check client exists
        check = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
        if not check:
            raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

        inserted_ids = []
        ocr_count = 0
        failed_count = 0

        # Use transaction for atomic bulk insert
        async with conn.transaction():
            for doc in documents:
                try:
                    # Sanitize expiry_date: convert string to date object
                    expiry_date = None
                    if doc.expiry_date:
                        try:
                            expiry_date = datetime.strptime(doc.expiry_date, "%Y-%m-%d").date()
                        except ValueError:
                            logger.warning(
                                f"Invalid expiry_date format for {doc.file_name}: {doc.expiry_date}"
                            )
                            expiry_date = None

                    # Insert document
                    doc_id = await conn.fetchval(
                        """
                        INSERT INTO documents (
                            client_id, document_type, document_category,
                            file_name, file_id, file_url, google_drive_file_url,
                            expiry_date, notes, family_member_id, practice_id,
                            status, storage_type, uploaded_by
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'active', 'google_drive', $12)
                        RETURNING id
                        """,
                        client_id,
                        doc.document_type,
                        doc.document_category,
                        doc.file_name,
                        doc.file_id,
                        doc.file_url,
                        doc.google_drive_file_url,
                        expiry_date,
                        doc.notes,
                        doc.family_member_id,
                        doc.practice_id,
                        user_email,  # Track who uploaded
                    )

                    inserted_ids.append(doc_id)

                    # Queue OCR for passport documents
                    if doc.file_id and doc.document_type:
                        folder_hint = ""
                        cat = (doc.document_category or "").lower()
                        if cat == "immigration":
                            folder_hint = "01_Immigration"
                        elif cat == "tax":
                            folder_hint = "03_Tax"
                        elif cat == "company":
                            folder_hint = "02_Company"
                        background_tasks.add_task(
                            _dispatch_ocr_by_folder,
                            client_id,
                            doc.file_id,
                            folder_hint,
                            doc.file_name or doc.document_type,
                            doc_id,
                        )
                        await conn.execute(
                            "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                            doc_id,
                        )
                        ocr_count += 1

                except Exception as e:
                    logger.error(f"Failed to insert document {doc.file_name}: {e}")
                    failed_count += 1
                    # Continue with other documents

        logger.info(
            f"Bulk inserted {len(inserted_ids)} documents for client {client_id}. "
            f"OCR queued: {ocr_count}, Failed: {failed_count}"
        )

        return {
            "success": True,
            "inserted": len(inserted_ids),
            "document_ids": inserted_ids,
            "ocr_triggered": ocr_count,
            "failed": failed_count,
            "client_id": client_id,
        }


@router.patch("/clients/{client_id}/documents/{doc_id}")
async def update_document(
    client_id: int,
    doc_id: int,
    data: DocumentUpdate,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update a document.
    RBAC REMOVED: All authenticated users can update documents.
    """
    # Date field that needs string → date object conversion for asyncpg
    date_fields = {"expiry_date"}

    update_fields = []
    values = []
    param_num = 1

    for field, value in data.model_dump(exclude_unset=True).items():
        # Convert date fields: empty string → None, valid string → date object
        if field in date_fields:
            if value == "" or value is None:
                value = None
            elif isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    value = None

        if value is not None:
            update_fields.append(f"{field} = ${param_num}")
            values.append(value)
            param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.extend([doc_id, client_id])

    async with pool.acquire() as conn:
        result = await conn.execute(
            f"""
            UPDATE documents
            SET {", ".join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_num} AND client_id = ${param_num + 1}
            """,
            *values,
        )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    return {"success": True}


@router.delete("/clients/{client_id}/documents/{doc_id}")
async def archive_document(
    client_id: int,
    doc_id: int,
    permanent: bool = Query(False, description="Permanently delete instead of archive"),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Archive or delete a document.
    RBAC REMOVED: All authenticated users can archive/delete documents.
    """
    async with pool.acquire() as conn:
        if permanent:
            result = await conn.execute(
                "DELETE FROM documents WHERE id = $1 AND client_id = $2", doc_id, client_id
            )
            action = "deleted"
        else:
            result = await conn.execute(
                "UPDATE documents SET is_archived = true, updated_at = NOW() WHERE id = $1 AND client_id = $2",
                doc_id,
                client_id,
            )
            action = "archived"

        if result in ("DELETE 0", "UPDATE 0"):
            raise HTTPException(status_code=404, detail="Document not found")

    return {"success": True, "action": action}


# ============================================
# DOCUMENT CATEGORIES ENDPOINT
# ============================================


@router.get("/document-categories")
async def get_document_categories(pool: Any = Depends(get_database_pool)) -> list[Any]:
    """Get all document categories for dropdowns."""
    async with pool.acquire() as conn:
        categories = await conn.fetch(
            """
            SELECT code, name, category_group, description, has_expiry
            FROM document_categories
            WHERE active = true
            ORDER BY sort_order, name
            """
        )
        return [dict(c) for c in categories]


# ============================================
# OCR STATUS ENDPOINT
# ============================================


@router.get("/clients/{client_id}/ocr-status")
async def get_client_ocr_status(
    client_id: int,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get OCR processing status for a client's documents.
    Frontend polls this to know when OCR completes.
    """
    async with pool.acquire() as conn:
        docs = await conn.fetch(
            """
            SELECT id, document_type, file_name, ocr_status, ocr_completed_at,
                   ocr_extracted_data
            FROM documents
            WHERE client_id = $1
              AND ocr_status IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            client_id,
        )

        pending = sum(1 for d in docs if d["ocr_status"] in ("pending", "processing"))
        completed = sum(1 for d in docs if d["ocr_status"] == "completed")

        return {
            "client_id": client_id,
            "pending_ocr": pending,
            "completed_ocr": completed,
            "documents": [dict(d) for d in docs],
        }


@router.post("/clients/{client_id}/extract-visa")
async def extract_visa_data(
    client_id: int,
    body: dict = Body(...),
    pool: Any = Depends(get_database_pool),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Extract visa/KITAS data from a document using Gemini Vision OCR.
    Updates the document's issue_date and expiry_date.

    Body: {"file_id": "...", "doc_id": 123}
    """
    file_id = body.get("file_id")
    doc_id = body.get("doc_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id required")

    result = await _auto_ocr_visa(client_id, file_id, doc_id)
    return result


# ============================================
# EXPIRY ALERTS ENDPOINTS
# ============================================


@router.get("/expiry-alerts")
async def get_all_expiry_alerts(
    alert_color: str | None = Query(None, description="Filter by color: expired, red, yellow"),
    assigned_to: str | None = Query(None, description="Filter by team member email"),
    limit: int = Query(100, le=500),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[Any]:
    """
    Get all expiry alerts across all clients (for team dashboard).
    RBAC REMOVED: All authenticated users can view all expiry alerts.
    Optional filtering by assigned_to is available as a query parameter.
    """
    async with pool.acquire() as conn:
        query = """
            SELECT
                entity_type, entity_id, entity_name, client_id, client_name,
                document_type, expiry_date, days_until_expiry, alert_color, assigned_to
            FROM client_expiry_alerts_view
            WHERE 1=1
        """
        params = []
        param_num = 1

        # Optional filter by assigned_to (user choice, not RBAC enforcement)
        if assigned_to:
            query += f" AND assigned_to = ${param_num}"
            params.append(assigned_to)
            param_num += 1

        query += f"""
            ORDER BY
                CASE alert_color
                    WHEN 'expired' THEN 1
                    WHEN 'red' THEN 2
                    WHEN 'yellow' THEN 3
                END,
                expiry_date
            LIMIT ${param_num}
        """
        params.append(limit)

        alerts = await conn.fetch(query, *params)
        return [dict(a) for a in alerts]


@router.get("/expiry-alerts/summary")
async def get_expiry_alerts_summary(pool: Any = Depends(get_database_pool)) -> dict[str, Any]:
    """Get summary counts of expiry alerts for dashboard."""
    async with pool.acquire() as conn:
        summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE alert_color = 'expired') as expired,
                COUNT(*) FILTER (WHERE alert_color = 'red') as red,
                COUNT(*) FILTER (WHERE alert_color = 'yellow') as yellow,
                COUNT(*) FILTER (WHERE alert_color = 'green') as green
            FROM client_expiry_alerts_view
            """
        )

        # Get top 5 urgent alerts
        urgent = await conn.fetch(
            """
            SELECT
                client_name, entity_name, document_type,
                expiry_date, days_until_expiry, alert_color
            FROM client_expiry_alerts_view
            WHERE alert_color IN ('expired', 'red')
            ORDER BY expiry_date
            LIMIT 5
            """
        )

        return {"counts": dict(summary), "urgent_alerts": [dict(a) for a in urgent]}


# ============================================
# NEW ENDPOINTS (Frontend Integration)
# ============================================


class DocumentUploadBase64(BaseModel):
    file: str  # Base64
    file_name: str
    document_type: str
    mime_type: str | None = None
    notes: str | None = None


@router.post("/clients/{client_id}/documents/upload")
async def upload_document_base64(
    client_id: int,
    data: DocumentUploadBase64 = Body(...),
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> dict[str, Any]:
    """
    Upload a document via Base64 (for frontend integration).
    Handles Google Drive upload and document creation.
    """
    try:
        # Decode Base64
        try:
            file_content = base64.b64decode(data.file)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 file content")

        # Determine category and folder name using filename-based categorization
        cat_result = auto_categorize_document(data.file_name)
        category = cat_result["document_category"]
        folder_name = CATEGORY_TO_FOLDER.get(category, "99_Misc")

        async with pool.acquire() as conn:
            client = await conn.fetchrow(
                "SELECT id, full_name, google_drive_folder_id, client_type FROM clients WHERE id = $1",
                client_id,
            )

            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

            drive_service = ServiceAccountDriveService()

            # Ensure Root Folder Exists
            root_folder_id = client["google_drive_folder_id"]
            if not root_folder_id:
                # Create root folder logic
                parent_id = settings.google_drive_root_folder_id

                # If specific settings exist for types, use them (simplified from crm_drive_folders)
                # But to avoid circular imports or config issues, we fall back to root or simple logic
                if client["client_type"] == "individual" and hasattr(
                    settings, "gdrive_individuals_folder_id"
                ):
                    parent_id = settings.gdrive_individuals_folder_id or parent_id
                elif client["client_type"] == "company" and hasattr(
                    settings, "gdrive_companies_folder_id"
                ):
                    parent_id = settings.gdrive_companies_folder_id or parent_id

                try:
                    folder_data = await drive_service.create_folder(
                        name=f"{client['id']}_{client['full_name']}",
                        parent_id=parent_id,
                    )
                    root_folder_id = folder_data["id"]

                    # Update client
                    await conn.execute(
                        "UPDATE clients SET google_drive_folder_id = $1 WHERE id = $2",
                        root_folder_id,
                        client_id,
                    )
                except Exception as e:
                    logger.error(f"Failed to create root folder: {e}")
                    raise HTTPException(
                        status_code=500, detail=f"Failed to create root folder: {e}"
                    ) from e

            # Ensure Subfolder Exists (Find or Create)
            try:
                structure = await drive_service.get_folder_structure(
                    root_folder_id=root_folder_id,
                )
            except Exception as e:
                # If structure fetch fails, maybe root folder is missing/deleted?
                # We'll just fail for now, or could try to recreate
                raise HTTPException(
                    status_code=500, detail=f"Failed to access folder structure: {e}"
                ) from e

            subfolder = next((f for f in structure["folders"] if f["name"] == folder_name), None)
            if not subfolder:
                # Create subfolder
                try:
                    subfolder_data = await drive_service.create_folder(
                        name=folder_name,
                        parent_id=root_folder_id,
                    )
                    subfolder_id = subfolder_data["id"]
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to create subfolder: {e}")
            else:
                subfolder_id = subfolder["id"]

            # Upload File
            try:
                upload_result = await drive_service.upload_file_to_folder(
                    folder_id=subfolder_id,
                    file_content=file_content,
                    file_name=data.file_name,
                    mime_type=data.mime_type,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to upload to drive: {e}")

            # Create Document Record
            doc_id = await conn.fetchval(
                """
                INSERT INTO documents (
                    client_id, document_type, document_category,
                    file_name, file_id, file_url, google_drive_file_url,
                    status, storage_type, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', 'google_drive', $8)
                RETURNING id
                """,
                client_id,
                data.document_type,
                category,
                data.file_name,
                upload_result["id"],
                upload_result.get("webViewLink"),  # Use webViewLink as file_url
                upload_result.get("webViewLink"),
                data.notes,
            )

            # Trigger OCR via dispatcher
            background_tasks.add_task(
                _dispatch_ocr_by_folder,
                client_id,
                upload_result["id"],
                folder_name,
                data.file_name,
                doc_id,
            )
            await conn.execute(
                "UPDATE documents SET ocr_status = 'pending' WHERE id = $1",
                doc_id,
            )

            return {
                "success": True,
                "document_id": doc_id,
                "file_url": upload_result.get("webViewLink"),
                "ocr_triggered": True,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    permanent: bool = False,
    pool: Any = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Delete a document (Soft delete by default).
    """
    async with pool.acquire() as conn:
        if permanent:
            result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
        else:
            result = await conn.execute(
                "UPDATE documents SET is_archived = true, updated_at = NOW() WHERE id = $1",
                doc_id,
            )

        if result == "DELETE 0" or result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Document not found")

    return {"success": True, "action": "deleted" if permanent else "archived"}
