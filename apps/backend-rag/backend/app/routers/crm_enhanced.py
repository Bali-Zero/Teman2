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
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import extract_json_from_llm_response
from backend.app.utils.json_utils import to_jsonb
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
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": _OLLAMA_VISION_MODEL,
                        "messages": [
                            {
                                "role": "user",
                                "content": ollama_prompt,
                                "images": [image_b64],
                            },
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                content = resp.json().get("message", {}).get("content", "").strip()
                if content:
                    logger.info(
                        f"OCR via Ollama {_OLLAMA_VISION_MODEL} (local): {len(content)} chars",
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
            except Exception as e:
                logger.debug(f"Could not remove temp file {tmp_path}: {e}")
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
            },
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


async def _auto_ocr_passport(db_pool: Any, client_id: int, file_id: str) -> dict:
    """
    Automatically run OCR on passport image and update client record.
    Runs in background after document upload.
    Uses the shared app-level pool passed in to avoid connection churn.
    """
    try:
        # Get client name for verification
        async with db_pool.acquire() as conn:
            client = await conn.fetchrow("SELECT full_name FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id)
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
                f"Auto OCR JSON parsing failed for client {client_id}. Raw: {response_text[:300]}",
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
            "extracted_at": datetime.now(timezone.utc).isoformat(),
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
                except ValueError as e:
                    logger.debug(f"Skipping invalid date format: {e}")

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
                except ValueError as e:
                    logger.debug(f"Skipping invalid date format: {e}")

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
            f"Auto OCR completed for client {client_id}: {extracted.get('passport_number', 'N/A')}",
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}


async def _auto_ocr_visa(db_pool: Any, client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on visa/KITAS/KITAP document → extract visa_type, expiry, number.
    Updates documents.expiry_date and documents.ocr_extracted_data.
    Uses the shared app-level pool passed in to avoid connection churn.
    """
    try:
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
            "extracted_at": datetime.now(timezone.utc).isoformat(),
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
                except ValueError as e:
                    logger.debug(f"Skipping invalid date format: {e}")

            if extracted.get("issue_date"):
                try:
                    issue = datetime.strptime(extracted["issue_date"], "%Y-%m-%d").date()
                    update_parts.append(f"issue_date = ${param_idx}")
                    params.append(issue)
                    param_idx += 1
                except ValueError as e:
                    logger.debug(f"Skipping invalid date format: {e}")

            if doc_id:
                params.append(doc_id)
                await conn.execute(
                    f"UPDATE documents SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = ${param_idx}",
                    *params,
                )

            # Sync visa data to clients table for notifications and CRM display
            visa_type = extracted.get("visa_type")
            sponsor = extracted.get("sponsor")
            expiry_date_parsed = None
            if extracted.get("expiry_date"):
                try:
                    expiry_date_parsed = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            sync_parts: list[str] = []
            sync_params: list[Any] = []
            sync_idx = 1

            if expiry_date_parsed:
                sync_parts.append(f"visa_expiry_date = ${sync_idx}")
                sync_params.append(expiry_date_parsed)
                sync_idx += 1

            if visa_type:
                sync_parts.append(f"current_visa_type = ${sync_idx}")
                sync_params.append(visa_type[:50])
                sync_idx += 1

            if sponsor:
                sync_parts.append(f"current_visa_sponsor = ${sync_idx}")
                sync_params.append(sponsor[:255])
                sync_idx += 1

            if sync_parts:
                sync_params.append(client_id)
                await conn.execute(
                    f"UPDATE clients SET {', '.join(sync_parts)}, updated_at = NOW() WHERE id = ${sync_idx}",
                    *sync_params,
                )
                logger.info(
                    f"Synced visa OCR to client {client_id}: type={visa_type}, expiry={expiry_date_parsed}, sponsor={sponsor}"
                )

        logger.info(
            f"Auto OCR visa completed for client {client_id}: {extracted.get('visa_type', 'N/A')}",
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR visa failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}


async def _auto_ocr_nib(db_pool: Any, client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on NIB (Nomor Induk Berusaha) document → extract NIB number, company_name, KBLI codes.
    Updates companies table if client has a linked company.
    Uses the shared app-level pool passed in to avoid connection churn.
    """
    try:
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
            "extracted_at": datetime.now(timezone.utc).isoformat(),
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
            f"Auto OCR NIB completed for client {client_id}: {extracted.get('nib_number', 'N/A')}",
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR NIB failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}


async def _auto_ocr_npwp(db_pool: Any, client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on NPWP (tax ID) document → extract NPWP number, address, KPP.
    Updates clients or companies table.
    Uses the shared app-level pool passed in to avoid connection churn.
    """
    try:
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
            "extracted_at": datetime.now(timezone.utc).isoformat(),
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
                    update_parts = ["npwp_company = $1"]
                    params: list[Any] = [extracted["npwp_number"]]
                    param_idx = 2
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
                            {"npwp": extracted["npwp_number"], "kpp": extracted.get("kpp_name")},
                        ),
                        client_id,
                    )

        logger.info(
            f"Auto OCR NPWP completed for client {client_id}: {extracted.get('npwp_number', 'N/A')}",
        )
        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR NPWP failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}


async def _auto_ocr_company_profile(db_pool: Any, client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on Profil Perseroan / Company Profile document.
    Extracts: shareholders, capital, akta, SK, notaris, address, KBLI.
    Saves to companies.custom_fields via client → company link.
    """
    try:
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = (
            "Extract from this Indonesian company profile (Profil Perseroan) document. "
            "Return JSON with these fields: "
            "company_name, authorized_capital (number in IDR), paid_up_capital (number in IDR), "
            "shareholders (array of objects with: name, passport, nationality, role, shares, value), "
            "akta_no (string), akta_date (YYYY-MM-DD), "
            "sk_no (string, AHU number), sk_date (YYYY-MM-DD), "
            "notaris (string, full name with title), notaris_kedudukan (string, city), "
            "registered_address (string, full address), "
            "company_status (TERTUTUP/TERBUKA), jangka_waktu (string), "
            "kbli_codes (array of strings if present), risk_status (string if present), "
            "share_price (number per share), total_shares (number), "
            "confidence (0-1)."
        )

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR company profile for client {client_id}: {response_text[:200]}...")

        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"Auto OCR company profile JSON parsing failed for client {client_id}")
            return {"success": False, "error": "Could not parse OCR response"}

        # Build custom_fields update
        custom_fields: dict[str, str] = {}
        for key in [
            "authorized_capital", "paid_up_capital", "shareholders",
            "akta_no", "akta_date", "sk_no", "sk_date",
            "notaris", "notaris_kedudukan", "company_status",
            "jangka_waktu", "kbli_codes", "risk_status",
            "share_price", "total_shares",
        ]:
            val = extracted.get(key)
            if val is not None:
                if isinstance(val, (list, dict)):
                    import json as json_module
                    custom_fields[key] = json_module.dumps(val)
                else:
                    custom_fields[key] = str(val)

        async with db_pool.acquire() as conn:
            # Update document OCR status
            if doc_id:
                ocr_data = {
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "auto_triggered": True,
                    "raw_response": extracted,
                    "file_id": file_id,
                    "document_type": "company_profile",
                }
                await conn.execute(
                    """UPDATE documents SET ocr_status = 'completed', ocr_completed_at = NOW(),
                       ocr_extracted_data = $1, updated_at = NOW() WHERE id = $2""",
                    to_jsonb(ocr_data),
                    doc_id,
                )

            # Find company linked to this client
            company_id = await conn.fetchval(
                """SELECT c.id FROM companies c
                   JOIN client_company_links ccl ON ccl.company_id = c.id
                   WHERE ccl.client_id = $1 LIMIT 1""",
                client_id,
            )

            if company_id and custom_fields:
                import json as json_module
                # Merge custom_fields (preserve existing, add new)
                existing_cf = await conn.fetchval(
                    "SELECT custom_fields FROM companies WHERE id = $1", company_id,
                )
                merged = json_module.loads(existing_cf) if existing_cf and existing_cf != '{}' else {}
                merged.update(custom_fields)

                # Also update dedicated columns
                update_parts = ["custom_fields = $1", "updated_at = NOW()"]
                params: list[Any] = [json_module.dumps(merged)]
                idx = 2

                addr = extracted.get("registered_address")
                if addr:
                    update_parts.append(f"registered_address = ${idx}")
                    params.append(str(addr)[:500])
                    idx += 1

                akta = extracted.get("akta_no")
                if akta:
                    update_parts.append(f"akta_pendirian_no = ${idx}")
                    params.append(str(akta)[:100])
                    idx += 1

                sk = extracted.get("sk_no")
                if sk:
                    update_parts.append(f"sk_menhumkam_no = ${idx}")
                    params.append(str(sk)[:100])
                    idx += 1

                params.append(company_id)
                await conn.execute(
                    f"UPDATE companies SET {', '.join(update_parts)} WHERE id = ${idx}",
                    *params,
                )
                logger.info(f"Auto OCR company profile: updated company {company_id} with {len(custom_fields)} fields")

        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR company profile failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}


async def _dispatch_ocr_by_folder(
    db_pool: Any,
    client_id: int,
    file_id: str,
    folder_name: str,
    filename: str,
    doc_id: int | None = None,
    document_type: str | None = None,
) -> dict:
    """Central OCR dispatcher — delegates to shared service."""
    from backend.services.documents.ocr_dispatcher_service import (
        dispatch_ocr_by_folder as _shared_dispatch,
    )

    return await _shared_dispatch(
        db_pool=db_pool,
        client_id=client_id,
        file_id=file_id,
        folder_name=folder_name,
        filename=filename,
        doc_id=doc_id,
        document_type=document_type,
    )


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
            WHERE id = $1 AND deleted_at IS NULL
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


@router.get("/companies/{company_id}/documents", operation_id="get_crm_company_documents")
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
        # Verify client exists (exclude soft-deleted)
        client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id)
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



# DOCUMENT/ALERTS ENDPOINTS → crm_enhanced_documents.py, crm_enhanced_alerts.py
