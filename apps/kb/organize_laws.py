"""
Organize Indonesian Laws and Create Excel Inventory
- Scans Zantara_KB_Source folder for existing laws
- Adds scraped laws if not already present
- Creates Excel file with: Name, Date, Category, Importance Level
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import PyPDF2
import pandas as pd

# Paths
DESKTOP = Path.home() / "Desktop"
ZANTARA_KB_SOURCE = DESKTOP / "Zantara_KB_Source"
SCRAPED_LAWS_DIR = Path(__file__).parent / "data" / "raw_laws"
SCRAPED_METADATA = Path(__file__).parent / "data" / "laws_metadata.jsonl"
OUTPUT_EXCEL = DESKTOP / "Indonesian_Laws_Inventory.xlsx"

# Importance levels based on regulation type
IMPORTANCE_LEVELS = {
    "UUD": 1,  # Highest - Constitution
    "UU": 2,  # High - National Law
    "Perpres": 3,  # Medium-High - Presidential Regulation
    "PP": 4,  # Medium - Government Regulation
    "Peraturan": 5,  # Medium - Regulation
    "Keputusan": 6,  # Medium-Low - Decision
    "Instruksi": 7,  # Low - Instruction
    "Perda": 8,  # Low - Regional Regulation
    "Perbup": 9,  # Low - Regent Regulation
    "Perwali": 10,  # Low - Mayor Regulation
    "Permen": 11,  # Low - Ministerial Regulation
    "PMK": 12,  # Low - Ministerial Decree
    "Unknown": 99,  # Unknown
}


def extract_pdf_metadata(pdf_path: Path) -> Dict:
    """Extract metadata from PDF file"""
    metadata = {
        "filename": pdf_path.name,
        "filepath": str(pdf_path),
        "size_bytes": pdf_path.stat().st_size,
        "modified_date": datetime.fromtimestamp(pdf_path.stat().st_mtime).isoformat(),
        "page_count": 0,
    }

    try:
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)

            # Get page count
            metadata["page_count"] = len(pdf_reader.pages)

            # Try to get PDF metadata
            if pdf_reader.metadata:
                if pdf_reader.metadata.title:
                    metadata["title"] = pdf_reader.metadata.title
                if pdf_reader.metadata.author:
                    metadata["author"] = pdf_reader.metadata.author
                if pdf_reader.metadata.subject:
                    metadata["subject"] = pdf_reader.metadata.subject
                if pdf_reader.metadata.creation_date:
                    metadata["creation_date"] = str(pdf_reader.metadata.creation_date)

            # Extract text from first page to identify regulation type
            if len(pdf_reader.pages) > 0:
                first_page_text = pdf_reader.pages[0].extract_text()
                metadata["first_page_text"] = first_page_text[:500]  # First 500 chars

                # Try to identify regulation type from text
                for reg_type in IMPORTANCE_LEVELS.keys():
                    if reg_type != "Unknown" and reg_type in first_page_text:
                        metadata["detected_type"] = reg_type
                        break

                # Try to extract year
                year_match = re.search(r"\b(19|20)\d{2}\b", first_page_text)
                if year_match:
                    metadata["detected_year"] = int(year_match.group())
    except Exception as e:
        metadata["error"] = str(e)

    return metadata


def get_regulation_type(filename: str, text: str = "") -> str:
    """Determine regulation type from filename or text"""
    # Normalize text: replace special spaces (\xa0) and special dashes (‐) with normal ones
    if text:
        text = text.replace("\xa0", " ")  # Replace non-breaking space with normal space
        text = text.replace("‐", "-")  # Replace U+2010 with normal dash
    combined = (filename + " " + text).upper()
    text_upper = text.upper()[:2000] if text else ""  # First 2000 chars of text

    # Known health laws (when text extraction fails)
    known_health_laws = {
        "TENAGA KESEHATAN": "UU",  # Health Workers Law
        "KESEHATAN JIWA": "UU",  # Mental Health Law (UU 18/2014)
        "KEKARANTINAAN KESEHATAN": "UU",  # Health Quarantine Law (UU 6/2018)
    }
    for key, reg_type in known_health_laws.items():
        if key in combined:
            return reg_type

    # Check for "Civil Code" - Indonesian Civil Code is a historical law/code
    if "CIVIL CODE" in combined:
        # Indonesian Civil Code (Burgerlijk Wetboek) is a legal code
        # Check if it mentions Indonesian Civil Code or Burgerlijk Wetboek
        if (
            "INDONESIAN" in combined
            or "BURGERLIJK" in text_upper
            or "WETBOEK" in text_upper
        ):
            return "UU"  # Historical law/code
        # If it contains regulation keywords, it might be a legal code
        if re.search(
            r"UNDANG[\s\-‐]UNDANG|PERATURAN|PROMULGATED|PUBLICATION", text_upper
        ):
            return "UU"  # Could be a compilation of laws
        # Otherwise, it's likely a generic reference document
        return "Unknown"

    # Exclude non-legal documents (keep as Unknown)
    non_legal_keywords = [
        "PRICE LIST",
        "INVOICE",
        "RESUME",
        "CV",
        "KITAS",
        "PERMIT",
        "SURAT UNDANGAN",
        "KLARIFIKASI",
        "HASIL",
        "RUNPOD",
        "IMIGRASI_FILE",  # Immigration form files
        "SURAT PERMOHONAN",  # Application letters
        "LAPORAN HASIL",  # Reports
        "SURVEI",  # Surveys
        "PROPERTY DISPUTE",  # Strategy documents, not laws
        "MANAGEMENT STRATEGY",  # Strategy documents
        "PT. ",  # Company documents (if starts with PT.)
    ]

    # Check if filename starts with non-legal patterns
    filename_upper = filename.upper()
    if filename_upper.startswith("PT. ") or filename_upper.startswith("PT "):
        return "Unknown"
    if any(keyword in combined for keyword in non_legal_keywords):
        # But check if it's actually a legal document (e.g., "PERATURAN" or "UNDANG-UNDANG" in text)
        # Handle variations: "UNDANG-UNDANG", "UNDANG -UNDANG", "UNDANG‐UNDANG"
        is_legal_doc = (
            "PERATURAN" in text_upper
            or re.search(r"UNDANG\s*[\s\-‐]\s*UNDANG", text_upper)
            or re.search(r"\bUU\b", combined)  # Also check filename for UU pattern
        )
        if not is_legal_doc:
            return "Unknown"

    # Check text content first (more reliable than filename)
    # UUD (Constitution) - most specific
    if "UUD" in combined or "UNDANG-UNDANG DASAR" in combined or "1945" in combined:
        return "UUD"

    # Check for "UNDANG-UNDANG REPUBLIK INDONESIA NOMOR X TAHUN YYYY" pattern in text
    # Handle special characters like "‐" (U+2010) instead of "-" (U+002D)
    # Also handle spaces: "UNDANG -UNDANG" or "UNDANG-UNDANG" or "UNDANG‐UNDANG"
    if re.search(
        r"UNDANG\s*[\s\-‐]\s*UNDANG\s+REPUBLIK\s+INDONESIA\s+NOMOR", text_upper
    ):
        return "UU"

    # Also check for "UNDANG-UNDANG" followed by "NOMOR" (more flexible)
    if re.search(r"UNDANG\s*[\s\-‐]\s*UNDANG.*?NOMOR\s+\d+", text_upper):
        return "UU"

    # Pattern matching for filename patterns like UU_36_2009, PP_35_2021, etc.
    # UU pattern: UU_XX_YYYY or UU_XX_YYYY_Description or "UU PPh No 36 Th 2008"
    # Check filename patterns first (before text patterns)
    # Match "UU" followed by space/underscore/dash and number, or "UU [Name] No [Number]"
    if re.search(
        r"\bUU[_\-]\d+|UU\s+NOMOR|UU\s+[A-Z]+\s+NO\.?\s+\d+|UNDANG[\s\-‐]UNDANG\s+NOMOR",
        combined,
    ):
        return "UU"

    # PP pattern: PP_XX_YYYY or PP_XX_YYYY_Description
    if re.search(r"^PP[_\-]\d+|PP\s+NOMOR|PERATURAN\s+PEMERINTAH\s+NOMOR", combined):
        return "PP"

    # Perpres pattern: PERPRES_XX_YYYY
    if re.search(
        r"^PERPRES[_\-]\d+|PERPRES\s+NOMOR|PERATURAN\s+PRESIDEN\s+NOMOR", combined
    ):
        return "Perpres"

    # Perda pattern: PERDA_XX_YYYY
    if re.search(r"^PERDA[_\-]\d+|PERDA\s+NOMOR|PERATURAN\s+DAERAH\s+NOMOR", combined):
        return "Perda"

    # Permen pattern: PERMEN_XX_YYYY
    if re.search(
        r"^PERMEN[_\-]\d+|PERMEN\s+NOMOR|PERATURAN\s+MENTERI\s+NOMOR", combined
    ):
        return "Permen"

    # PMK pattern: PMK_XX_YYYY
    if re.search(
        r"^PMK[_\-]\d+|PMK\s+NOMOR|PERATURAN\s+MENTERI\s+KEUANGAN\s+NOMOR", combined
    ):
        return "PMK"

    # UU (National Law) - check in text content for "UNDANG-UNDANG" without "PERATURAN"
    # Handle special characters like "‐" (U+2010) instead of "-" (U+002D)
    # Also handle spaces: "UNDANG -UNDANG" or "UNDANG-UNDANG" or "UNDANG‐UNDANG"
    if (
        re.search(r"UNDANG\s*[\s\-‐]\s*UNDANG", text_upper)
        and "PERATURAN" not in text_upper[:500]
    ):
        return "UU"

    # UU (National Law) - check standalone UU in filename/text
    if re.search(r"\bUU\b", combined) and not re.search(
        r"PERATURAN.*UU|UU.*PERATURAN", combined
    ):
        # Make sure it's not part of "PERATURAN UNDANG-UNDANG"
        if "PERATURAN UNDANG-UNDANG" not in combined:
            return "UU"

    # Perpres (Presidential Regulation)
    if "PERPRES" in combined or "PERATURAN PRESIDEN" in combined:
        return "Perpres"

    # PP (Government Regulation) - check standalone PP
    if re.search(r"\bPP\b", combined) or "PERATURAN PEMERINTAH" in combined:
        return "PP"

    # PMK (Ministerial Decree)
    if "PMK" in combined or "PERATURAN MENTERI KEUANGAN" in combined:
        return "PMK"

    # Permen (Ministerial Regulation)
    if "PERMEN" in combined or "PERATURAN MENTERI" in combined:
        return "Permen"

    # Perda (Regional Regulation)
    if "PERDA" in combined or "PERATURAN DAERAH" in combined:
        return "Perda"

    # Perbup (Regent Regulation)
    if "PERBUP" in combined or "PERATURAN BUPATI" in combined:
        return "Perbup"

    # Perwali (Mayor Regulation)
    if "PERWALI" in combined or "PERATURAN WALIKOTA" in combined:
        return "Perwali"

    # Keputusan (Decision)
    if "KEPUTUSAN" in combined:
        return "Keputusan"

    # Instruksi (Instruction)
    if "INSTRUKSI" in combined:
        return "Instruksi"

    # Generic Peraturan (Regulation)
    if "PERATURAN" in combined:
        return "Peraturan"

    return "Unknown"


def get_importance_level(reg_type: str) -> int:
    """Get importance level (1 = highest, 99 = lowest)"""
    return IMPORTANCE_LEVELS.get(reg_type, IMPORTANCE_LEVELS["Unknown"])


def classify_category(name: str, text: str = "") -> str:
    """Classify category based on name and text content"""
    combined = (name + " " + text).upper()

    # Immigration/Visa
    if any(
        keyword in combined
        for keyword in [
            "IMMIGRAZIONE",
            "IMMIGRATION",
            "VISA",
            "KITAS",
            "KITAP",
            "IMIGRASI",
            "PASSPORT",
            "PASPOR",
            "PERMIT",
            "IZIN TINGGAL",
        ]
    ):
        return "Immigrazione"

    # Tax
    if any(
        keyword in combined
        for keyword in [
            "TASSE",
            "TAX",
            "PAJAK",
            "NPWP",
            "PPH",
            "PPN",
            "KEUANGAN",
            "FISCAL",
            "WITHHOLDING",
        ]
    ):
        return "Tasse"

    # Health
    if any(
        keyword in combined
        for keyword in [
            "SANITA",
            "HEALTH",
            "KESEHATAN",
            "RUMAH SAKIT",
            "HOSPITAL",
            "BIDAN",
            "KEBIDANAN",
            "PERAWAT",
            "KEPERAWATAN",
            "DOKTER",
            "MEDICAL",
            "KARANTINA",
            "KEKARANTINAAN",
        ]
    ):
        return "Sanita"

    # Company & Licenses
    if any(
        keyword in combined
        for keyword in [
            "COMPANY",
            "LICENSE",
            "IZIN",
            "PERUSAHAAN",
            "PT",
            "CV",
            "OSS",
            "NIB",
            "KBLI",
            "BUSINESS",
            "USAHA",
            "PERIZINAN",
        ]
    ):
        return "Company&Licenses"

    # Labor/Work
    if any(
        keyword in combined
        for keyword in [
            "LAVORO",
            "LABOR",
            "KETENAGAKERJAAN",
            "KERJA",
            "WORK",
            "EMPLOYMENT",
            "PEKERJA",
            "BURUH",
            "APARATUR SIPIL",
            "ASN",
        ]
    ):
        return "Lavoro"

    # Education
    if any(
        keyword in combined
        for keyword in [
            "ISTRUZIONE",
            "EDUCATION",
            "PENDIDIKAN",
            "SEKOLAH",
            "UNIVERSITAS",
            "SCHOOL",
            "UNIVERSITY",
            "PELAJAR",
            "MAHASISWA",
        ]
    ):
        return "Istruzione"

    # Environment
    if any(
        keyword in combined
        for keyword in [
            "AMBIENTE",
            "ENVIRONMENT",
            "LINGKUNGAN",
            "IKLIM",
            "CLIMATE",
            "HUTAN",
            "FOREST",
            "AIR",
            "WATER",
            "TANAH",
            "SOIL",
        ]
    ):
        return "Ambiente"

    # Financial Sector
    if any(
        keyword in combined
        for keyword in [
            "FINANCIAL",
            "KEUANGAN",
            "BANK",
            "PERBANKAN",
            "FINANCIAL",
            "INVESTASI",
            "INVESTMENT",
            "SAHAM",
            "STOCK",
        ]
    ):
        return "Settore_Finanziario"

    # Construction/Urban Planning
    if any(
        keyword in combined
        for keyword in [
            "EDILIZIA",
            "CONSTRUCTION",
            "BANGUNAN",
            "GEDUNG",
            "KONSTRUKSI",
            "URBANISTICA",
            "TATA KOTA",
            "PERKOTAAN",
            "INFRASTRUKTUR",
        ]
    ):
        return "Edilizia_Urbanistica"

    # Transport/Shipping
    if any(
        keyword in combined
        for keyword in [
            "TRASPORTI",
            "TRANSPORT",
            "SHIPPING",
            "PENGANGKUTAN",
            "KAPAL",
            "PELABUHAN",
            "PORT",
            "LOGISTIK",
            "LOGISTICS",
        ]
    ):
        return "Trasporti_Shipping"

    # Codes & Classifications
    if any(
        keyword in combined
        for keyword in [
            "CODICI",
            "CODE",
            "KLASIFIKASI",
            "CLASSIFICATION",
            "KBLI",
            "STANDAR",
            "STANDARD",
            "NOMENKLATUR",
        ]
    ):
        return "Codici_e_Codificazioni"

    # Additional patterns for better classification
    # Financial Services Authority (OJK)
    if "OJK" in combined or "OTORITAS JASA KEUANGAN" in combined:
        return "Settore_Finanziario"

    # Real Estate / Property
    if any(
        keyword in combined
        for keyword in ["REAL ESTATE", "TANAH", "PROPERTY", "RUMAH", "PERUMAHAN"]
    ):
        return "Edilizia_Urbanistica"

    # IT / Technology
    if any(
        keyword in combined
        for keyword in ["ITE", "INFORMASI", "TEKNOLOGI", "TELEKOMUNIKASI", "DIGITAL"]
    ):
        return "Codici_e_Codificazioni"  # Or could be a new category

    # Civil Administration
    if any(
        keyword in combined
        for keyword in ["ADMINDUK", "ADMINISTRASI", "KEPENDUDUKAN", "CIVIL"]
    ):
        return "Codici_e_Codificazioni"

    # Marriage / Family Law
    if any(
        keyword in combined
        for keyword in [
            "PERKAWINAN",
            "MARRIAGE",
            "KELUARGA",
            "FAMILY",
            "PERNIKAHAN",
            "NIKAH",
        ]
    ):
        return "Codici_e_Codificazioni"  # Family law as legal framework

    # Constitution (UUD 1945) - must check before other UUD patterns
    if ("UUD" in combined and "1945" in combined) or combined.startswith("UUD"):
        return "Codici_e_Codificazioni"  # Constitution as fundamental legal framework

    # Real Estate / Property / Agrarian - check again with more keywords
    # Check for "REAL_ESTATE" (with underscore) as well
    if any(
        keyword in combined
        for keyword in [
            "REAL ESTATE",
            "REAL_ESTATE",
            "REALESTATE",
            "TANAH",
            "PROPERTY",
            "RUMAH",
            "PERUMAHAN",
            "AGRARIA",
            "AGRARIAN",
            "AGRARIS",
        ]
    ):
        return "Edilizia_Urbanistica"

    # Fisheries / Marine / Aquaculture - check again
    if any(
        keyword in combined
        for keyword in [
            "FISHERIES",
            "PERIKANAN",
            "KELAUTAN",
            "MARINE",
            "IKAN",
            "AQUACULTURE",
            "BUDIDAYA",
            "FISHING",
        ]
    ):
        return "Ambiente"

    # Refund / Reimbursement - financial/tax related
    if any(
        keyword in combined
        for keyword in ["REFUND", "REIMBURSEMENT", "PENGEMBALIAN", "PEMBAYARAN KEMBALI"]
    ):
        return "Tasse"

    # Generic UU (Undang-Undang) - if no specific category found, classify by common patterns
    if "UU" in combined and "NOMOR" in combined:
        # Check if it's a numbered UU without clear category
        # Most numbered UUs without clear topic are general legal frameworks
        return "Codici_e_Codificazioni"

    # Generic PP (Peraturan Pemerintah) - many are about business/licenses
    # Check for PP pattern (PP-XX-YYYY or PP_XX_YYYY)
    if re.search(r"\bPP[-_]?\d+", combined) or (
        "PP" in combined and len(combined.split()) < 15
    ):
        return "Company&Licenses"

    # Default: keep as non-classified
    return "Non classificati"


def scan_existing_laws() -> List[Dict]:
    """Scan Zantara_KB_Source folder for existing PDF laws"""
    print("Scanning Zantara_KB_Source folder...")
    laws = []

    if not ZANTARA_KB_SOURCE.exists():
        print(f"Warning: Zantara_KB_Source folder not found at {ZANTARA_KB_SOURCE}")
        return laws

    pdf_files = list(ZANTARA_KB_SOURCE.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in Zantara_KB_Source")

    for pdf_path in pdf_files:
        try:
            metadata = extract_pdf_metadata(pdf_path)

            # Determine category from folder structure
            relative_path = pdf_path.relative_to(ZANTARA_KB_SOURCE)
            category = (
                relative_path.parts[0] if len(relative_path.parts) > 1 else "Root"
            )

            # Get regulation type
            reg_type = get_regulation_type(
                pdf_path.name, metadata.get("first_page_text", "")
            )

            # Extract name from filename (remove .pdf extension)
            name = pdf_path.stem

            # Extract date
            date = metadata.get("detected_year") or metadata.get("modified_date", "")
            if isinstance(date, str) and len(date) > 4:
                # Try to extract year from date string
                year_match = re.search(r"\b(19|20)\d{2}\b", date)
                if year_match:
                    date = int(year_match.group())
                else:
                    date = ""

            # Classify category if it's "Non classificati" or "Root"
            if category == "Non classificati" or category == "Root":
                category = classify_category(name, metadata.get("first_page_text", ""))

            law_data = {
                "name": name,
                "date": date,
                "category": category,
                "regulation_type": reg_type,
                "importance_level": get_importance_level(reg_type),
                "quantity": metadata.get("page_count", 0),
                "filepath": str(pdf_path),
                "filename": pdf_path.name,
                "size_mb": round(metadata["size_bytes"] / (1024 * 1024), 2),
                "source": "Zantara_KB_Source",
            }

            laws.append(law_data)

        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            continue

    print(f"Processed {len(laws)} laws from Zantara_KB_Source")
    return laws


def load_scraped_laws() -> List[Dict]:
    """Load scraped laws from metadata file and also scan PDF directory"""
    print("Loading scraped laws...")
    laws = []

    # First, try to load from metadata file
    if SCRAPED_METADATA.exists():
        with open(SCRAPED_METADATA, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        item = json.loads(line)

                        # Check if PDF exists
                        pdf_filename = item.get("local_filename", "")
                        pdf_path = SCRAPED_LAWS_DIR / pdf_filename

                        if not pdf_path.exists():
                            continue

                        # Extract metadata
                        name = item.get("title", pdf_filename.replace(".pdf", ""))
                        year = item.get("year", "")

                        # Extract page count and classify category
                        pdf_metadata = extract_pdf_metadata(pdf_path)
                        page_count = pdf_metadata.get("page_count", 0)
                        first_page_text = pdf_metadata.get("first_page_text", "")

                        # Determine regulation type using improved function
                        reg_type = get_regulation_type(name, first_page_text)
                        # Fallback to item type if still Unknown and item has type
                        if reg_type == "Unknown" and item.get("type"):
                            reg_type = get_regulation_type(
                                item.get("type", ""), first_page_text
                            )

                        # Classify category
                        category = classify_category(name, first_page_text)
                        if category == "Non classificati":
                            category = "Scraped_Laws"  # Fallback for scraped laws

                        law_data = {
                            "name": name,
                            "date": year,
                            "category": category,
                            "regulation_type": reg_type,
                            "importance_level": get_importance_level(reg_type),
                            "quantity": page_count,
                            "filepath": str(pdf_path),
                            "filename": pdf_filename,
                            "size_mb": round(
                                pdf_path.stat().st_size / (1024 * 1024), 2
                            ),
                            "source": "BPK_Scraped",
                        }

                        laws.append(law_data)

                    except json.JSONDecodeError as e:
                        print(f"Error parsing metadata line: {e}")
                        continue

    # Also scan PDF directory directly for any PDFs not in metadata
    if SCRAPED_LAWS_DIR.exists():
        pdf_files = list(SCRAPED_LAWS_DIR.glob("*.pdf"))
        existing_filenames = {law["filename"] for law in laws}

        for pdf_path in pdf_files:
            if pdf_path.name not in existing_filenames:
                # Extract metadata from filename and PDF
                metadata = extract_pdf_metadata(pdf_path)
                name = pdf_path.stem
                reg_type = get_regulation_type(
                    pdf_path.name, metadata.get("first_page_text", "")
                )

                # Try to extract year from filename or PDF
                year_match = re.search(r"\b(19|20)\d{2}\b", pdf_path.name)
                year = (
                    int(year_match.group())
                    if year_match
                    else metadata.get("detected_year", "")
                )

                # Classify category
                category = classify_category(name, metadata.get("first_page_text", ""))
                if category == "Non classificati":
                    category = "Scraped_Laws"  # Fallback for scraped laws

                law_data = {
                    "name": name,
                    "date": year,
                    "category": category,
                    "regulation_type": reg_type,
                    "importance_level": get_importance_level(reg_type),
                    "quantity": metadata.get("page_count", 0),
                    "filepath": str(pdf_path),
                    "filename": pdf_path.name,
                    "size_mb": round(pdf_path.stat().st_size / (1024 * 1024), 2),
                    "source": "BPK_Scraped",
                }

                laws.append(law_data)

    print(f"Loaded {len(laws)} scraped laws")
    return laws


def merge_and_deduplicate(
    existing_laws: List[Dict], scraped_laws: List[Dict]
) -> List[Dict]:
    """Merge laws and remove duplicates based on filename similarity"""
    print("Merging and deduplicating laws...")

    # Create a set to track seen laws (by normalized name)
    seen = set()
    merged_laws = []

    # Normalize name for comparison
    def normalize_name(name: str) -> str:
        # Remove common words and normalize
        name = name.lower()
        name = re.sub(
            r"\b(pdf|undang|undang-undang|peraturan|tahun|nomor|no)\b", "", name
        )
        name = re.sub(r"[^\w\s]", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name[:50]  # First 50 chars for comparison

    # Add existing laws first
    for law in existing_laws:
        norm_name = normalize_name(law["name"])
        if norm_name not in seen:
            seen.add(norm_name)
            merged_laws.append(law)

    # Add scraped laws if not duplicate
    added_count = 0
    skipped_count = 0

    for law in scraped_laws:
        norm_name = normalize_name(law["name"])
        if norm_name not in seen:
            seen.add(norm_name)
            merged_laws.append(law)
            added_count += 1
        else:
            skipped_count += 1

    print(f"Merged: {len(merged_laws)} total laws")
    print(f"  - Existing: {len(existing_laws)}")
    print(f"  - Added from scraped: {added_count}")
    print(f"  - Skipped duplicates: {skipped_count}")

    return merged_laws


def create_excel(laws: List[Dict], output_path: Path):
    """Create Excel file with laws inventory"""
    print(f"Creating Excel file: {output_path}")

    # Prepare data for Excel
    excel_data = []
    for law in laws:
        excel_data.append(
            {
                "Name": law["name"],
                "Date": law["date"],
                "Category": law["category"],
                "Regulation Type": law["regulation_type"],
                "Importance Level": law["importance_level"],
                "Importance": get_importance_label(law["importance_level"]),
                "Quantity": law.get("quantity", 0),  # Page count
                "Filename": law["filename"],
                "Size (MB)": law["size_mb"],
                "Source": law["source"],
                "Filepath": law["filepath"],
            }
        )

    # Create DataFrame
    df = pd.DataFrame(excel_data)

    # Sort by importance level, then by date (descending)
    # Handle missing dates by converting to numeric
    df["Date_Numeric"] = pd.to_numeric(df["Date"], errors="coerce").fillna(0)
    df = df.sort_values(["Importance Level", "Date_Numeric"], ascending=[True, False])
    df = df.drop(columns=["Date_Numeric"])

    # Create Excel writer with formatting
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Laws Inventory", index=False)

        # Get the worksheet
        worksheet = writer.sheets["Laws Inventory"]

        # Auto-adjust column widths
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).map(len).max(), len(str(col)))
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

    print(f"Excel file created successfully: {output_path}")
    print(f"Total laws: {len(df)}")


def get_importance_label(level: int) -> str:
    """Get human-readable importance label"""
    if level == 1:
        return "Highest (Constitution)"
    elif level == 2:
        return "High (National Law)"
    elif level <= 4:
        return "Medium-High"
    elif level <= 7:
        return "Medium"
    else:
        return "Low"


def main():
    """Main function"""
    print("=" * 60)
    print("Indonesian Laws Organization and Inventory")
    print("=" * 60)

    # Scan existing laws
    existing_laws = scan_existing_laws()

    # Load scraped laws
    scraped_laws = load_scraped_laws()

    # Merge and deduplicate
    all_laws = merge_and_deduplicate(existing_laws, scraped_laws)

    # Create Excel
    create_excel(all_laws, OUTPUT_EXCEL)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total laws in inventory: {len(all_laws)}")
    print(f"Excel file: {OUTPUT_EXCEL}")
    print("=" * 60)


if __name__ == "__main__":
    main()
