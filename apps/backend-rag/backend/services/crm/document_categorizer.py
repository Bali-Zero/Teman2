"""
Document Auto-Categorization Service

Automatically detects document type and category from filenames for the CRM.
Useful for bulk migration and automatic organization of client documents.
"""

import re
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# OFFICIAL FOLDER MAPPING (matches Drive structure)
#
# 00_Profile    → passport, photo, alamat (address)
# 01_Immigration → kitas, visa, e-visa, IMK, ITK (applicant only)
# 02_Company    → akta + SK, NIB, NPWP company, profile perseroan
# 03_Tax        → SPT company, SPT personal, NPWP personal, LKPM report
# 04_Family     → passport/visa/kitas-IMK-ITK of family members
# 99_Misc       → contract, other
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that signal "family member" document → 04_Family
FAMILY_MEMBER_KEYWORDS: list[str] = [
    "family",
    "familie",
    "famig",  # generic family markers
    "spouse",
    "moglie",
    "marito",
    "wife",
    "husband",
    "child",
    "children",
    "figlio",
    "figlia",
    "figlie",
    "figli",
    "bambino",
    "son",
    "daughter",
    "member",
    "anggota",
    "_fam_",
    "-fam-",
    "_fam.",
    " fam ",  # filename conventions
    "dependant",
    "dependent",
    # Documents that are inherently family docs (always go to 04_Family)
    "marriage",
    "pernikahan",
    "akta nikah",
    "nikah",
    "birth",
    "kelahiran",
    "akta kelahiran",
    "family card",
    "kartu keluarga",
]

# Comprehensive keyword mapping for document categorization
# Priority order: family → profile → immigration → company → tax → other
CATEGORIZATION_RULES: dict[str, dict[str, list[str]]] = {
    # ── 04_Family: family member documents (checked FIRST) ──────────────────
    "family": {
        "passport_family": ["passport", "paspor"],  # combined with family kw
        "visa_family": ["visa", "e-visa", "evisa", "voa", "b211", "b-211"],
        "kitas_family": ["kitas", "kitap", "imk", "itk", "itas", "stay permit"],
        "family_card": ["kk", "kartu keluarga", "family card"],
        "birth_certificate": ["birth", "kelahiran", "akta kelahiran", "born"],
        "marriage_certificate": ["marriage", "pernikahan", "akta nikah", "nikah"],
    },
    # ── 00_Profile: applicant profile docs (passport, foto, address) ─────────
    "personal": {
        "passport": ["passport", "paspor", "pport"],
        "photo": ["photo", "foto", "picture", "selfie", "image", "foto_wajah"],
        "alamat": [
            "alamat",
            "address",
            "ktp",
            "id card",
            "kartu tanda penduduk",
            "domicile address",
            "residential address",
        ],
        "cv": ["cv", "resume", "curriculum vitae"],
    },
    # ── 01_Immigration: e-visa, IMK/ITK, KITAS (NO passport — that's Profile)
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
    # ── 02_Company: company formation & legal docs ───────────────────────────
    "pma": {
        "akta": [
            "akta",
            "deed",
            "pendirian",
            "notarial",
            "akta pendirian",
            "akta perubahan",
            "deed of establishment",
        ],
        "sk": [
            "sk ",
            "sk_",
            "sk-",
            "surat keputusan",
            "kemenkumham",
            "ministry of law",
            "menkumham",
        ],
        "nib": ["nib", "oss", "nomor induk berusaha", "business id"],
        "npwp_company": [
            "npwp",
            "npwp perusahaan",
            "npwp badan",
            "npwp pt",
            "company tax",
            "npwp company",
            "tax id company",
        ],
        "profile_perseroan": [
            "profil perseroan",
            "profile perseroan",
            "company profile",
            "profil perusahaan",
            "profile perusahaan",
            "company presentation",
            "profil pt",
            "profil perseroan baru",
        ],
        "siup": ["siup", "tdp", "izin usaha", "business license"],
        "domicile": ["surat domisili", "domicile letter", "keterangan domisili"],
        "legalisation": ["legalisation", "legalisasi", "apostille", "notarised"],
        "wlkp": ["wlkp", "wajib lapor", "lapor ketenagakerjaan"],
        "bpjs": ["bpjs", "bpjs ketenagakerjaan", "bpjs kesehatan"],
        "organogram": ["bagan organisasi", "organogram", "organization chart", "org chart", "struktur organisasi"],
        "rekening_koran": ["rekening koran perusahaan", "bank statement company", "rekening koran pt"],
    },
    # ── 03_Tax: tax documents ────────────────────────────────────────────────
    "tax": {
        "spt": ["spt"],
        "spt_company": [
            "spt company",
            "spt badan",
            "spt perusahaan",
            "annual tax company",
            "pajak tahunan badan",
        ],
        "spt_personal": [
            "spt personal",
            "spt pribadi",
            "spt tahunan pribadi",
            "annual tax personal",
            "spt op",
            "spt tahunan",
        ],
        "npwp_personal": [
            "npwp personal",
            "npwp pribadi",
            "npwp perorangan",
            "personal tax id",
            "npwp",
        ],
        "lkpm_report": [
            "lkpm",
            "laporan kegiatan penanaman modal",
            "investment activity report",
            "investment report",
        ],
        "bpjs": ["bpjs", "social insurance", "jamsostek", "kesehatan bpjs", "ketenagakerjaan bpjs"],
        "pph": [
            "pph",
            "income tax",
            "pajak penghasilan",
            "withholding tax",
            "bukti potong",
            "pemotongan pajak",
        ],
        "ppn": ["ppn", "vat", "value added tax", "pajak pertambahan nilai"],
        "invoice_tax": ["faktur pajak", "tax invoice", "efaktur"],
    },
    # ── 99_Misc: contracts and everything else ───────────────────────────────
    "other": {
        "contract": [
            "contract",
            "kontrak",
            "agreement",
            "perjanjian",
            "lease",
            "rental agreement",
            "mou",
            "memorandum",
        ],
        "letter": ["surat", "letter", "correspondence", "notifikasi"],
        "form": ["form", "formulir", "application form"],
        "receipt": ["receipt", "tanda terima", "kwitansi", "invoice"],
        "other": ["other", "misc", "miscellaneous", "lainnya"],
    },
}

# Category → Drive folder name
CATEGORY_TO_FOLDER: dict[str, str] = {
    "family": "04_Family",
    "personal": "00_Profile",
    "immigration": "01_Immigration",
    "pma": "02_Company",
    "tax": "03_Tax",
    "other": "99_Misc",
}


def auto_categorize_document(filename: str) -> dict[str, Any]:
    """
    Automatically categorize a document based on its filename.

    Uses keyword matching against predefined rules to determine the most
    likely document type and category.

    Args:
        filename: The document filename (e.g., "Passport_MARCO_2028-12-31.pdf")

    Returns:
        Dictionary with:
            - document_type: Best guess document type (str)
            - document_category: Category (immigration/pma/tax/personal/other)
            - confidence: Confidence score 0-1 (float)
            - matched_keyword: The keyword that triggered the match (str)

    Examples:
        >>> auto_categorize_document("passport_john.pdf")
        {
            'document_type': 'Passport',
            'document_category': 'immigration',
            'confidence': 0.9,
            'matched_keyword': 'passport'
        }

        >>> auto_categorize_document("KITAS_scan_2024.jpg")
        {
            'document_type': 'Kitas',
            'document_category': 'immigration',
            'confidence': 0.9,
            'matched_keyword': 'kitas'
        }
    """
    if not filename:
        return _fallback_categorization()

    # Normalize: lowercase + replace underscores/hyphens with spaces for keyword matching
    filename_lower = filename.lower()
    filename_normalized = filename_lower.replace("_", " ").replace("-", " ")

    # Detect if the filename contains a family member keyword
    is_family_doc = any(kw in filename_normalized for kw in FAMILY_MEMBER_KEYWORDS)

    # Try each category in priority order
    for category, doc_types in CATEGORIZATION_RULES.items():
        # Skip family category if no family keyword is present
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

    # No match found
    return _fallback_categorization()


def _format_document_type(doc_type: str) -> str:
    """
    Format document type for display.

    Converts snake_case to Title Case.

    Examples:
        'passport' -> 'Passport'
        'npwp_company' -> 'Npwp Company'
        'sk_kemenkumham' -> 'Sk Kemenkumham'
    """
    return doc_type.replace("_", " ").title()


def _calculate_confidence(filename: str, matched_keyword: str) -> float:
    """
    Calculate confidence score based on match quality.

    Args:
        filename: Lowercase filename
        matched_keyword: The keyword that matched

    Returns:
        Confidence score between 0.5 and 1.0
    """
    # Remove common extensions for better matching
    filename_clean = re.sub(r"\.(pdf|jpg|jpeg|png|doc|docx|xlsx)$", "", filename)

    # Exact match (keyword is entire filename)
    if matched_keyword == filename_clean:
        return 1.0

    # Keyword at start of filename
    if filename_clean.startswith(matched_keyword):
        return 0.9

    # Keyword is a word boundary match (not part of another word)
    if re.search(rf"\b{re.escape(matched_keyword)}\b", filename_clean):
        return 0.85

    # Keyword anywhere in filename
    if matched_keyword in filename_clean:
        return 0.7

    # Partial match (shouldn't reach here, but just in case)
    return 0.6


def _fallback_categorization() -> dict[str, Any]:
    """
    Return fallback categorization for unknown documents.

    Returns:
        Dictionary with 'other' category and low confidence
    """
    return {
        "document_type": "Other",
        "document_category": "other",
        "confidence": 0.5,
        "matched_keyword": None,
    }


def extract_expiry_date(filename: str) -> str | None:
    """
    Extract expiry date from filename if present.

    Looks for common date patterns in filenames:
    - YYYY-MM-DD (2024-12-31)
    - YYYY/MM/DD (2024/12/31)
    - DD-MM-YYYY (31-12-2024)
    - YYYYMMDD (20241231)

    Args:
        filename: Document filename

    Returns:
        ISO formatted date string (YYYY-MM-DD) or None if not found

    Examples:
        >>> extract_expiry_date("Passport_MARCO_2028-12-31.pdf")
        "2028-12-31"

        >>> extract_expiry_date("KITAS_20251215.jpg")
        "2025-12-15"

        >>> extract_expiry_date("random_file.pdf")
        None
    """
    if not filename:
        return None

    # Patterns to try (in order of priority)
    patterns = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),  # 2024-12-31
        (r"(\d{4})/(\d{2})/(\d{2})", "%Y/%m/%d"),  # 2024/12/31
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),  # 31-12-2024
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),  # 20241231
    ]

    for pattern, date_format in patterns:
        match = re.search(pattern, filename)
        if match:
            try:
                from datetime import datetime

                # Extract matched groups
                date_str = match.group(0)

                # Parse according to format
                date_obj = datetime.strptime(date_str, date_format)

                # Validate date is reasonable (not too far in past/future)
                year = date_obj.year
                if 1900 <= year <= 2100:
                    # Return in ISO format
                    return date_obj.strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                # Invalid date, try next pattern
                continue

    return None


def extract_person_name(filename: str) -> str | None:
    """
    Extract person name from filename.

    Assumes naming convention: [Type]_[NAME]_[Date].[ext]

    Args:
        filename: Document filename

    Returns:
        Extracted name or None

    Examples:
        >>> extract_person_name("Passport_MARCO_ROSSI_2028-12-31.pdf")
        "MARCO ROSSI"

        >>> extract_person_name("KITAS_JOHN_DOE.jpg")
        "JOHN DOE"
    """
    if not filename:
        return None

    # Remove extension
    name_without_ext = re.sub(
        r"\.(pdf|jpg|jpeg|png|doc|docx|xlsx)$", "", filename, flags=re.IGNORECASE,
    )

    # Split by underscore
    parts = name_without_ext.split("_")

    # Need at least 2 parts (type + name)
    if len(parts) < 2:
        return None

    # First part is usually document type, remaining is name (except last if date)
    potential_name_parts = parts[1:]

    # Remove last part if it looks like a date
    if potential_name_parts and re.search(r"\d{4}", potential_name_parts[-1]):
        potential_name_parts = potential_name_parts[:-1]

    if not potential_name_parts:
        return None

    # Join name parts with space
    return " ".join(potential_name_parts).strip()


# Batch categorization for efficiency
def auto_categorize_documents_batch(filenames: list[str]) -> list[dict[str, Any]]:
    """
    Batch categorize multiple documents.

    More efficient than calling auto_categorize_document() in a loop
    for large numbers of documents.

    Args:
        filenames: List of filenames to categorize

    Returns:
        List of categorization dictionaries
    """
    return [auto_categorize_document(filename) for filename in filenames]


# Statistics helper
def get_categorization_stats(categorizations: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Get statistics about a batch of categorizations.

    Useful for migration quality assessment.

    Args:
        categorizations: List of categorization results

    Returns:
        Dictionary with statistics:
            - total: Total documents
            - by_category: Count by category
            - by_confidence: Count by confidence range
            - avg_confidence: Average confidence score
            - uncategorized: Number of 'other' category documents
    """
    if not categorizations:
        return {
            "total": 0,
            "by_category": {},
            "by_confidence": {},
            "avg_confidence": 0.0,
            "uncategorized": 0,
        }

    by_category = {}
    confidence_sum = 0
    confidence_ranges = {"high": 0, "medium": 0, "low": 0}

    for cat in categorizations:
        category = cat["document_category"]
        confidence = cat["confidence"]

        # Count by category
        by_category[category] = by_category.get(category, 0) + 1

        # Sum for average
        confidence_sum += confidence

        # Confidence ranges
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
        "avg_confidence": confidence_sum / len(categorizations) if categorizations else 0,
        "uncategorized": by_category.get("other", 0),
    }
