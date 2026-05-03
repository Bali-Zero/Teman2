"""
CRM Documents — consolidated module.

Merges:
  - document_categorizer.py  (auto_categorize_document, extract_expiry_date, …)
  - document_upload_service.py (DocumentUploadService)
"""

import re
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating
from backend.services.integrations.drive_folder_service import DriveFolderService

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Document Auto-Categorization (from document_categorizer.py)
# ─────────────────────────────────────────────────────────────────────────────

FAMILY_MEMBER_KEYWORDS: list[str] = [
    "family", "familie", "famig",
    "spouse", "moglie", "marito", "wife", "husband",
    "child", "children", "figlio", "figlia", "figlie", "figli", "bambino",
    "son", "daughter", "member", "anggota",
    "_fam_", "-fam-", "_fam.", " fam ",
    "dependant", "dependent",
    "marriage", "pernikahan", "akta nikah", "nikah",
    "birth", "kelahiran", "akta kelahiran",
    "family card", "kartu keluarga",
]

CATEGORIZATION_RULES: dict[str, dict[str, list[str]]] = {
    "family": {
        "passport_family": ["passport", "paspor"],
        "visa_family": ["visa", "e-visa", "evisa", "voa", "b211", "b-211"],
        "kitas_family": ["kitas", "kitap", "imk", "itk", "itas", "stay permit"],
        "family_card": ["kk", "kartu keluarga", "family card"],
        "birth_certificate": ["birth", "kelahiran", "akta kelahiran", "born"],
        "marriage_certificate": ["marriage", "pernikahan", "akta nikah", "nikah"],
    },
    "personal": {
        "passport": ["passport", "paspor", "pport"],
        "photo": ["photo", "foto", "picture", "selfie", "image", "foto_wajah"],
        "alamat": [
            "alamat", "address", "ktp", "id card", "kartu tanda penduduk",
            "domicile address", "residential address",
        ],
        "cv": ["cv", "resume", "curriculum vitae"],
    },
    "immigration": {
        "kitas": ["kitas", "kitap", "itas", "limited stay", "stay permit"],
        "imk": ["imk", "izin masuk kembali", "reentry", "re-entry"],
        "itk": ["itk", "izin tinggal kunjungan"],
        "visa": ["visa", "voa", "b211", "b-211", "c1", "c2"],
        "evisa": ["e-visa", "evisa", "electronic visa", "e visa"],
        "imta": ["imta", "work permit", "izin kerja", "working permit", "rptka"],
        "merp": ["merp", "multiple exit re-entry"],
        "sktt": ["sktt", "temporary residence certificate"],
        "sponsor_letter": ["sponsor letter", "surat sponsor", "sponsorship letter"],
        "telex_visa": ["telex", "vitas", "approval letter"],
    },
    "pma": {
        "akta": [
            "akta", "deed", "pendirian", "notarial",
            "akta pendirian", "akta perubahan", "deed of establishment",
        ],
        "sk": ["sk ", "sk_", "sk-", "surat keputusan", "kemenkumham", "ministry of law", "menkumham"],
        "nib": ["nib", "oss", "nomor induk berusaha", "business id"],
        "npwp_company": [
            "npwp", "npwp perusahaan", "npwp badan", "npwp pt",
            "company tax", "npwp company", "tax id company",
        ],
        "profile_perseroan": [
            "profil perseroan", "profile perseroan", "company profile",
            "profil perusahaan", "profile perusahaan", "company presentation",
            "profil pt", "profil perseroan baru",
        ],
        "siup": ["siup", "tdp", "izin usaha", "business license"],
        "domicile": ["surat domisili", "domicile letter", "keterangan domisili"],
        "legalisation": ["legalisation", "legalisasi", "apostille", "notarised"],
        "wlkp": ["wlkp", "wajib lapor", "lapor ketenagakerjaan"],
        "bpjs": ["bpjs", "bpjs ketenagakerjaan", "bpjs kesehatan"],
        "organogram": ["bagan organisasi", "organogram", "organization chart", "org chart", "struktur organisasi"],
        "rekening_koran": ["rekening koran perusahaan", "bank statement company", "rekening koran pt"],
    },
    "tax": {
        "spt": ["spt"],
        "spt_company": [
            "spt company", "spt badan", "spt perusahaan",
            "annual tax company", "pajak tahunan badan",
        ],
        "spt_personal": [
            "spt personal", "spt pribadi", "spt tahunan pribadi",
            "annual tax personal", "spt op", "spt tahunan",
        ],
        "npwp_personal": [
            "npwp personal", "npwp pribadi", "npwp perorangan",
            "personal tax id", "npwp",
        ],
        "lkpm_report": [
            "lkpm", "laporan kegiatan penanaman modal",
            "investment activity report", "investment report",
        ],
        "bpjs": ["bpjs", "social insurance", "jamsostek", "kesehatan bpjs", "ketenagakerjaan bpjs"],
        "pph": [
            "pph", "income tax", "pajak penghasilan", "withholding tax",
            "bukti potong", "pemotongan pajak",
        ],
        "ppn": ["ppn", "vat", "value added tax", "pajak pertambahan nilai"],
        "invoice_tax": ["faktur pajak", "tax invoice", "efaktur"],
    },
    "other": {
        "contract": [
            "contract", "kontrak", "agreement", "perjanjian",
            "lease", "rental agreement", "mou", "memorandum",
        ],
        "letter": ["surat", "letter", "correspondence", "notifikasi"],
        "form": ["form", "formulir", "application form"],
        "receipt": ["receipt", "tanda terima", "kwitansi", "invoice"],
        "other": ["other", "misc", "miscellaneous", "lainnya"],
    },
}

CATEGORY_TO_FOLDER: dict[str, str] = {
    "family": "04_Family",
    "personal": "00_Profile",
    "immigration": "01_Immigration",
    "pma": "02_Company",
    "tax": "03_Tax",
    "other": "99_Misc",
}


def auto_categorize_document(filename: str) -> dict[str, Any]:
    """Automatically categorize a document based on its filename."""
    if not filename:
        return _fallback_categorization()

    filename_lower = filename.lower()
    filename_normalized = filename_lower.replace("_", " ").replace("-", " ")
    is_family_doc = any(kw in filename_normalized for kw in FAMILY_MEMBER_KEYWORDS)

    for category, doc_types in CATEGORIZATION_RULES.items():
        if category == "family" and not is_family_doc:
            continue
        for doc_type, keywords in doc_types.items():
            for keyword in keywords:
                if keyword in filename_normalized:
                    return {
                        "document_type": _format_document_type(doc_type),
                        "document_category": category,
                        "confidence": _calculate_confidence(filename_normalized, keyword),
                        "matched_keyword": keyword,
                    }

    return _fallback_categorization()


def _format_document_type(doc_type: str) -> str:
    return doc_type.replace("_", " ").title()


def _calculate_confidence(filename: str, matched_keyword: str) -> float:
    filename_clean = re.sub(r"\.(pdf|jpg|jpeg|png|doc|docx|xlsx)$", "", filename)
    if matched_keyword == filename_clean:
        return 1.0
    if filename_clean.startswith(matched_keyword):
        return 0.9
    if re.search(rf"\b{re.escape(matched_keyword)}\b", filename_clean):
        return 0.85
    if matched_keyword in filename_clean:
        return 0.7
    return 0.6


def _fallback_categorization() -> dict[str, Any]:
    return {
        "document_type": "Other",
        "document_category": "other",
        "confidence": 0.5,
        "matched_keyword": None,
    }


def extract_expiry_date(filename: str) -> str | None:
    """Extract expiry date from filename if present."""
    if not filename:
        return None

    patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
        (r"(\d{4})/(\d{2})/(\d{2})", "%Y/%m/%d"),
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
    ]
    for pattern, date_format in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                from datetime import datetime
                date_str = match.group(0)
                date_obj = datetime.strptime(date_str, date_format)
                if 1900 <= date_obj.year <= 2100:
                    return date_obj.strftime("%Y-%m-%d")
            except (ValueError, IndexError) as exc:
                logger.debug(
                    "crm_documents.filename_date_pattern_mismatch",
                    extra={"pattern": pattern, "error_type": type(exc).__name__},
                )
                continue
    return None


def extract_person_name(filename: str) -> str | None:
    """Extract person name from filename (convention: [Type]_[NAME]_[Date].[ext])."""
    if not filename:
        return None
    name_without_ext = re.sub(r"\.(pdf|jpg|jpeg|png|doc|docx|xlsx)$", "", filename, flags=re.IGNORECASE)
    parts = name_without_ext.split("_")
    if len(parts) < 2:
        return None
    potential_name_parts = parts[1:]
    if potential_name_parts and re.search(r"\d{4}", potential_name_parts[-1]):
        potential_name_parts = potential_name_parts[:-1]
    if not potential_name_parts:
        return None
    return " ".join(potential_name_parts).strip()


def auto_categorize_documents_batch(filenames: list[str]) -> list[dict[str, Any]]:
    """Batch categorize multiple documents."""
    return [auto_categorize_document(filename) for filename in filenames]


def get_categorization_stats(categorizations: list[dict[str, Any]]) -> dict[str, Any]:
    """Get statistics about a batch of categorizations."""
    if not categorizations:
        return {"total": 0, "by_category": {}, "by_confidence": {}, "avg_confidence": 0.0, "uncategorized": 0}

    by_category: dict[str, int] = {}
    confidence_sum = 0.0
    confidence_ranges = {"high": 0, "medium": 0, "low": 0}

    for cat in categorizations:
        category = cat["document_category"]
        confidence = cat["confidence"]
        by_category[category] = by_category.get(category, 0) + 1
        confidence_sum += confidence
        if confidence >= 0.8:
            confidence_ranges["high"] += 1
        elif confidence >= 0.6:
            confidence_ranges["medium"] += 1
        else:
            confidence_ranges["low"] += 1

    return {
        "total": len(categorizations),
        "by_category": by_category,
        "by_confidence": confidence_ranges,
        "avg_confidence": confidence_sum / len(categorizations),
        "uncategorized": by_category.get("other", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DocumentUploadService (from document_upload_service.py)
# ─────────────────────────────────────────────────────────────────────────────

class DocumentUploadService:
    """Service for handling document uploads to Drive."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.drive_service = DriveFolderService()

    async def upload_from_portal(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,
        mime_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """Client uploads document from portal (my.balizero.com)."""
        return await self._upload_document(
            client_id=client_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            mime_type=mime_type,
            uploaded_by="client",
        )

    async def upload_from_crm(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,
        uploaded_by_email: str,
        mime_type: str = "application/pdf",
    ) -> dict[str, Any]:
        """Team leader uploads document from CRM."""
        return await self._upload_document(
            client_id=client_id,
            file_content=file_content,
            filename=filename,
            document_type=document_type,
            mime_type=mime_type,
            uploaded_by=uploaded_by_email,
        )

    @cache_invalidating([
        lambda self, client_id, *a, **k: f"zantara:crm_client:{client_id}:documents:*",
        "zantara:crm_documents:*",
        "zantara:portal_documents:*",
    ])
    async def _upload_document(
        self,
        client_id: int,
        file_content: bytes,
        filename: str,
        document_type: str,
        mime_type: str,
        uploaded_by: str,
    ) -> dict[str, Any]:
        client_data = await self._fetch_client_data(client_id)
        if not client_data:
            return {"success": False, "error": "Client not found"}

        drive_data = await self._get_or_create_drive_folder(client_id, client_data)
        if not drive_data.get("success"):
            return {"success": False, "error": drive_data.get("error", "Drive folder error")}

        upload_result = await self.drive_service.upload_document(
            client_folder_id=drive_data["folder_id"],
            file_content=file_content,
            filename=filename,
            mime_type=mime_type,
        )

        if not upload_result.get("success"):
            return {"success": False, "error": upload_result.get("error", "Upload failed")}

        await self._save_document_record(
            client_id=client_id,
            filename=filename,
            document_type=document_type,
            drive_file_id=upload_result["file_id"],
            drive_file_url=upload_result["file_url"],
            uploaded_by=uploaded_by,
        )

        logger.info(f"Document {filename} uploaded for client {client_id}")
        return {
            "success": True,
            "file_id": upload_result["file_id"],
            "file_url": upload_result["file_url"],
            "folder_url": drive_data["folder_url"],
        }

    async def _fetch_client_data(self, client_id: int) -> dict | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, full_name, email, drive_folder_id, drive_folder_url FROM clients WHERE id = $1",
                client_id,
            )
            return dict(row) if row else None

    async def _get_or_create_drive_folder(self, client_id: int, client_data: dict) -> dict[str, Any]:
        if client_data.get("drive_folder_id"):
            return {
                "success": True,
                "folder_id": client_data["drive_folder_id"],
                "folder_url": client_data.get("drive_folder_url", ""),
            }

        folder_result = await self.drive_service.create_client_folder(
            client_name=client_data["full_name"],
            client_id=client_id,
        )
        if not folder_result.get("success"):
            return folder_result

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE clients
                SET
                    drive_folder_id = $1,
                    drive_folder_url = $2,
                    drive_documents_folder_id = $3,
                    drive_final_folder_id = $4,
                    updated_at = NOW()
                WHERE id = $5
                """,
                folder_result["folder_id"],
                folder_result["folder_url"],
                folder_result["documents_folder_id"],
                folder_result["final_documents_folder_id"],
                client_id,
            )

        return {
            "success": True,
            "folder_id": folder_result["folder_id"],
            "folder_url": folder_result["folder_url"],
            "documents_folder_id": folder_result["documents_folder_id"],
            "final_folder_id": folder_result["final_documents_folder_id"],
        }

    async def _save_document_record(
        self,
        client_id: int,
        filename: str,
        document_type: str,
        drive_file_id: str,
        drive_file_url: str,
        uploaded_by: str,
    ) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO client_documents (
                    client_id, filename, document_type,
                    drive_file_id, drive_file_url, uploaded_by,
                    uploaded_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                client_id, filename, document_type,
                drive_file_id, drive_file_url, uploaded_by,
            )

    async def get_client_documents(self, client_id: int) -> list[dict]:
        """Get all documents for a client."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, filename, document_type, drive_file_url,
                    uploaded_by, uploaded_at
                FROM client_documents
                WHERE client_id = $1
                ORDER BY uploaded_at DESC
                """,
                client_id,
            )
            return [dict(row) for row in rows]
