"""LHKPN PDF parser — extracts structured data from KPK asset declarations.

Parses the standardised elhkpn.kpk.go.id PDF format into typed dataclasses
covering personal data, property, vehicles, cash, debts, and total assets.

Handles real-world PDF extraction quirks:
- Multi-line text wrapping (city names split across lines)
- Trailing year glitch ("Rp. 404.000.0002019")
- Dashes for zero values ("Rp. ----")
- Value on next line for vehicles ("Rp.\\n100.000.000")
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from osint_nexus.utils.logging import get_logger

logger = get_logger("parsers.lhkpn")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PropertyItem:
    """A single tanah/bangunan entry from section A."""

    lokasi: str
    luas_tanah_m2: int
    luas_bangunan_m2: int
    tipe: str  # "tanah_bangunan" or "tanah"
    nilai: int
    sumber: str  # e.g. "HASIL SENDIRI", "" if missing

    @property
    def property_id(self) -> str:
        """Deterministic ID from physical characteristics (not value/year)."""
        key = f"{self.lokasi}|{self.luas_tanah_m2}|{self.luas_bangunan_m2}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class VehicleItem:
    """A single kendaraan entry from section B."""

    jenis: str  # e.g. "MOBIL", "MOTOR"
    merk_model: str  # e.g. "TOYOTA VIOS"
    tahun_perolehan: int
    nilai: int
    sumber: str

    @property
    def vehicle_id(self) -> str:
        """Deterministic ID from vehicle identity (not value)."""
        key = f"{self.merk_model}|{self.tahun_perolehan}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class LhkpnReport:
    """Complete parsed LHKPN report."""

    nama: str
    jabatan: str
    nhk: str
    tahun: int
    lembaga: str
    unit_kerja: str
    tanah_bangunan: list[PropertyItem]
    kendaraan: list[VehicleItem]
    kas: int
    hutang: int
    total_harta: int
    source_file: str


# ---------------------------------------------------------------------------
# parse_rp — Rupiah string parser
# ---------------------------------------------------------------------------

# Matches Rp-style values. The trailing-year glitch appends 4 digits (a year)
# after the last group of 3. We match up to the last valid .NNN group and
# discard any trailing digits that don't fit the pattern.
_RP_PATTERN = re.compile(
    r"(?:Rp\.?\s*)?"           # optional "Rp." prefix
    r"([\d]+(?:\.[\d]{3})*)"   # digit groups separated by dots (thousands)
)


def parse_rp(text: str) -> int:
    """Parse Indonesian Rupiah string to integer.

    Handles:
        "Rp. 900.000.000"       → 900000000
        "Rp. ----"              → 0
        "Rp. 404.000.0002019"   → 404000000 (trailing year glitch)
        ""                      → 0
        "900.000.000"           → 900000000 (no Rp prefix)
    """
    if not text or not text.strip():
        return 0

    text = text.strip()

    # Dashes mean zero
    if re.search(r"-{2,}", text):
        return 0

    match = _RP_PATTERN.search(text)
    if not match:
        return 0

    # Remove thousand separators
    digits = match.group(1).replace(".", "")
    return int(digits) if digits else 0


# ---------------------------------------------------------------------------
# Section splitter — splits full PDF text into named sections
# ---------------------------------------------------------------------------

_SECTION_HEADERS = [
    "A. TANAH DAN BANGUNAN",
    "B. ALAT TRANSPORTASI DAN MESIN",
    "C. HARTA BERGERAK LAINNYA",
    "D. SURAT BERHARGA",
    "E. KAS DAN SETARA KAS",
    "F. HARTA LAINNYA",
]


def _split_sections(text: str) -> dict[str, str]:
    """Split PDF text into named sections by their headers.

    Returns a dict mapping header prefix (e.g. "A", "B") to the section text
    including the header line.
    """
    sections: dict[str, str] = {}

    # Build list of (position, key, header) tuples
    markers: list[tuple[int, str, str]] = []
    for header in _SECTION_HEADERS:
        pos = text.find(header)
        if pos >= 0:
            key = header[0]  # "A", "B", etc.
            markers.append((pos, key, header))

    # Also find III. HUTANG and IV. TOTAL
    for pattern, key in [
        ("III. HUTANG", "III"),
        ("IV. TOTAL HARTA KEKAYAAN", "IV"),
    ]:
        pos = text.find(pattern)
        if pos >= 0:
            markers.append((pos, key, pattern))

    markers.sort(key=lambda x: x[0])

    for i, (pos, key, _header) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        sections[key] = text[pos:end].strip()

    return sections


# ---------------------------------------------------------------------------
# _parse_properties — section A parser
# ---------------------------------------------------------------------------

# Pattern for "Tanah dan Bangunan Seluas 340 m2/250 m2 di KAB / KOTA ..."
_PROP_TB_PATTERN = re.compile(
    r"Tanah\s+dan\s+Bangunan\s+Seluas\s+([\d.]+)\s*m2\s*/\s*([\d.]+)\s*m2\s+"
    r"di\s+KAB\s*/\s*KOTA\s+(.*?)"
    r"(?:,?\s*(HASIL\s+\w+|WARISAN|HIBAH))?"
    r"\s+Rp\.\s*([\d.]+)",
    re.DOTALL,
)

# Pattern for "Tanah Seluas 300 m2 di KAB / KOTA ..."  (no building)
_PROP_T_PATTERN = re.compile(
    r"Tanah\s+Seluas\s+([\d.]+)\s*m2\s+"
    r"di\s+KAB\s*/\s*KOTA\s+(.*?)"
    r"(?:,?\s*(HASIL\s+\w+|WARISAN|HIBAH))?"
    r"\s+Rp\.\s*([\d.]+)",
    re.DOTALL,
)

# Pattern for "Bangunan Seluas 142 m2 di KAB / KOTA ..." (building only, no land)
_PROP_B_PATTERN = re.compile(
    r"Bangunan\s+Seluas\s+([\d.]+)\s*m2\s+"
    r"di\s+KAB\s*/\s*KOTA\s+(.*?)"
    r"(?:,?\s*(HASIL\s+\w+|WARISAN|HIBAH))?"
    r"\s+Rp\.\s*([\d.]+)",
    re.DOTALL,
)


def _join_continuation_lines(text: str) -> str:
    """Join lines that are continuations (don't start with a digit or section header).

    In LHKPN PDFs, numbered items can wrap across lines. E.g.:
        "1. Tanah dan Bangunan Seluas 340 m2/250 m2 di KAB / KOTA DELI"
        "SERDANG, HASIL SENDIRI Rp. 900.000.000"

    We join non-numbered continuation lines to the previous line.
    """
    lines = text.split("\n")
    joined: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # A line starting with a digit+dot is a new item, or a section header (A., B., etc.)
        if re.match(r"^\d+\.\s", stripped) or re.match(r"^[A-Z]\.\s", stripped):
            joined.append(stripped)
        elif joined:
            # Continuation line — append to previous
            joined[-1] = joined[-1] + " " + stripped
        else:
            joined.append(stripped)

    return "\n".join(joined)


def _parse_properties(text: str) -> list[PropertyItem]:
    """Parse section A (TANAH DAN BANGUNAN) into PropertyItem list.

    Handles:
    - "Tanah dan Bangunan Seluas X m2/Y m2" → tanah_bangunan type
    - "Tanah Seluas X m2" → tanah type (luas_bangunan = 0)
    - Multi-line text wrapping
    - Missing "HASIL SENDIRI"
    """
    # Check for empty section
    if re.search(r"-{2,}", text.split("\n")[0] if text else ""):
        return []

    joined = _join_continuation_lines(text)
    items: list[PropertyItem] = []

    # Extract numbered items — split on "N. Tanah" or "N. Bangunan" patterns
    # Avoids false splits on thousand separators like "1.015 m2"
    item_texts = re.split(r"(?=\d{1,2}\.\s+(?:Tanah|Bangunan))", joined)

    for item_text in item_texts:
        item_text = item_text.strip()
        if not item_text or not re.match(r"\d+\.\s", item_text):
            continue

        # Try tanah_bangunan pattern first
        tb_match = _PROP_TB_PATTERN.search(item_text)
        if tb_match:
            luas_tanah = int(tb_match.group(1).replace(".", ""))
            luas_bangunan = int(tb_match.group(2).replace(".", ""))
            lokasi_raw = tb_match.group(3).strip()
            sumber = (tb_match.group(4) or "").strip()
            nilai_str = tb_match.group(5)

            # Clean lokasi: remove trailing comma, whitespace
            lokasi = re.sub(r"\s*,?\s*$", "", lokasi_raw).strip()
            # Remove "KOTA " prefix duplication: "KOTA BANDA ACEH" → keep as is
            # but clean extra spaces
            lokasi = re.sub(r"\s+", " ", lokasi)

            items.append(PropertyItem(
                lokasi=lokasi,
                luas_tanah_m2=luas_tanah,
                luas_bangunan_m2=luas_bangunan,
                tipe="tanah_bangunan",
                nilai=parse_rp(f"Rp. {nilai_str}"),
                sumber=sumber,
            ))
            continue

        # Try tanah-only pattern
        t_match = _PROP_T_PATTERN.search(item_text)
        if t_match:
            luas_tanah = int(t_match.group(1).replace(".", ""))
            lokasi_raw = t_match.group(2).strip()
            sumber = (t_match.group(3) or "").strip()
            nilai_str = t_match.group(4)

            lokasi = re.sub(r"\s*,?\s*$", "", lokasi_raw).strip()
            lokasi = re.sub(r"\s+", " ", lokasi)

            items.append(PropertyItem(
                lokasi=lokasi,
                luas_tanah_m2=luas_tanah,
                luas_bangunan_m2=0,
                tipe="tanah",
                nilai=parse_rp(f"Rp. {nilai_str}"),
                sumber=sumber,
            ))
            continue

        # Try bangunan-only pattern (building without land)
        b_match = _PROP_B_PATTERN.search(item_text)
        if b_match:
            luas_bangunan = int(b_match.group(1).replace(".", ""))
            lokasi_raw = b_match.group(2).strip()
            sumber = (b_match.group(3) or "").strip()
            nilai_str = b_match.group(4)

            lokasi = re.sub(r"\s*,?\s*$", "", lokasi_raw).strip()
            lokasi = re.sub(r"\s+", " ", lokasi)

            items.append(PropertyItem(
                lokasi=lokasi,
                luas_tanah_m2=0,
                luas_bangunan_m2=luas_bangunan,
                tipe="bangunan",
                nilai=parse_rp(f"Rp. {nilai_str}"),
                sumber=sumber,
            ))
            continue

        logger.warning("Unparseable property item: %s", item_text[:100])

    return items


# ---------------------------------------------------------------------------
# _parse_vehicles — section B parser
# ---------------------------------------------------------------------------

# Pattern: "MOBIL, TOYOTA VIOS Tahun 2012, HASIL SENDIRI Rp. 100.000.000"
# Note: value can be on next line, so we join first.
_VEHICLE_PATTERN = re.compile(
    r"(\w+),\s+"               # jenis (MOBIL, MOTOR, etc.)
    r"(.+?)\s+"                # merk_model
    r"Tahun\s+(\d{4})"        # tahun_perolehan
    r"(?:,\s*(HASIL\s+\w+|WARISAN|HIBAH))?"  # optional sumber
    r"\s+Rp\.\s*([\d.]+)",    # nilai
    re.DOTALL,
)


def _parse_vehicles(text: str) -> list[VehicleItem]:
    """Parse section B (ALAT TRANSPORTASI DAN MESIN) into VehicleItem list.

    IMPORTANT: The Rp value is often on the NEXT LINE in the PDF.
    We join continuation lines before parsing.
    """
    # Check for empty section
    if re.search(r"-{2,}", text.split("\n")[0] if text else ""):
        return []

    joined = _join_continuation_lines(text)
    items: list[VehicleItem] = []

    # Split by numbered entries
    item_texts = re.split(r"(?=\d+\.\s)", joined)

    for item_text in item_texts:
        item_text = item_text.strip()
        if not item_text or not re.match(r"\d+\.\s", item_text):
            continue

        # Remove the leading number "1. "
        body = re.sub(r"^\d+\.\s*", "", item_text)

        match = _VEHICLE_PATTERN.search(body)
        if match:
            jenis = match.group(1).strip()
            merk_model = match.group(2).strip()
            tahun = int(match.group(3))
            sumber = (match.group(4) or "").strip()
            nilai_str = match.group(5)

            items.append(VehicleItem(
                jenis=jenis,
                merk_model=merk_model,
                tahun_perolehan=tahun,
                nilai=parse_rp(f"Rp. {nilai_str}"),
                sumber=sumber,
            ))
        else:
            logger.warning("Unparseable vehicle item: %s", item_text[:100])

    return items


# ---------------------------------------------------------------------------
# _extract_field — regex helper for personal data
# ---------------------------------------------------------------------------

def _extract_field(text: str, field_name: str) -> str:
    """Extract 'Field : Value' from PDF text."""
    pattern = re.compile(rf"{field_name}\s*:\s*(.+?)(?:\n|$)")
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# parse_lhkpn_pdf — main entry point
# ---------------------------------------------------------------------------

def parse_lhkpn_pdf(pdf_path: Path | str) -> LhkpnReport:
    """Parse a full LHKPN PDF file into a structured LhkpnReport.

    Args:
        pdf_path: Path to the LHKPN PDF file.

    Returns:
        LhkpnReport with all extracted data.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF cannot be parsed.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Parsing LHKPN PDF: %s", pdf_path.name)

    # Extract all text from all pages
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

    if not full_text.strip():
        raise ValueError(f"No text extracted from PDF: {pdf_path}")

    # --- Personal data ---
    # KPK PDFs use UPPERCASE names; normalize to title case so
    # "BUGIE KURNIAWAN" becomes "Bugie Kurniawan" for entity resolution.
    nama = _extract_field(full_text, "Nama").title()
    jabatan = _extract_field(full_text, "Jabatan")
    nhk = _extract_field(full_text, "NHK")
    lembaga = _extract_field(full_text, "LEMBAGA")
    unit_kerja = _extract_field(full_text, "UNIT KERJA")

    # Year: first line of PDF is typically just the year
    tahun = 0
    first_line = full_text.strip().split("\n")[0].strip()
    year_match = re.match(r"^(\d{4})$", first_line)
    if year_match:
        tahun = int(year_match.group(1))

    # --- Split into sections ---
    sections = _split_sections(full_text)

    # --- Parse properties (section A) ---
    tanah_bangunan = _parse_properties(sections.get("A", ""))

    # --- Parse vehicles (section B) ---
    kendaraan = _parse_vehicles(sections.get("B", ""))

    # --- Scalar values ---
    kas = 0
    kas_section = sections.get("E", "")
    if kas_section:
        # The value is on the header line: "E. KAS DAN SETARA KAS Rp. 15.000.000"
        kas_match = re.search(r"Rp\.\s*([\d.\-]+)", kas_section)
        if kas_match:
            kas = parse_rp(f"Rp. {kas_match.group(1)}")

    hutang = 0
    hutang_section = sections.get("III", "")
    if hutang_section:
        hutang_match = re.search(r"Rp\.\s*([\d.\-]+)", hutang_section)
        if hutang_match:
            hutang = parse_rp(f"Rp. {hutang_match.group(1)}")

    total_harta = 0
    total_section = sections.get("IV", "")
    if total_section:
        total_match = re.search(r"Rp\.\s*([\d.\-]+)", total_section)
        if total_match:
            total_harta = parse_rp(f"Rp. {total_match.group(1)}")

    report = LhkpnReport(
        nama=nama,
        jabatan=jabatan,
        nhk=nhk,
        tahun=tahun,
        lembaga=lembaga,
        unit_kerja=unit_kerja,
        tanah_bangunan=tanah_bangunan,
        kendaraan=kendaraan,
        kas=kas,
        hutang=hutang,
        total_harta=total_harta,
        source_file=str(pdf_path),
    )

    logger.info(
        "Parsed LHKPN: %s (%d) — %d properties, %d vehicles, total=%d",
        report.nama,
        report.tahun,
        len(report.tanah_bangunan),
        len(report.kendaraan),
        report.total_harta,
    )

    return report
