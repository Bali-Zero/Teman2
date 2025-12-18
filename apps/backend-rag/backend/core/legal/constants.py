"""
Constants for Indonesian Legal Document Processing
Regex patterns, keywords, and structure markers
"""

import re

# ============================================================================
# NOISE PATTERNS - Headers/Footers to remove
# ============================================================================

NOISE_PATTERNS = [
    # Page numbers
    re.compile(r"^Halaman\s+\d+\s+dari\s+\d+", re.IGNORECASE | re.MULTILINE),
    # Certification footer
    re.compile(
        r"^Salinan sesuai dengan aslinya.*?(?=\n)", re.IGNORECASE | re.MULTILINE | re.DOTALL
    ),
    # President header (repeated on every page)
    re.compile(r"^PRESIDEN REPUBLIK INDONESIA\s*\n", re.IGNORECASE | re.MULTILINE),
    # Page separators
    re.compile(r"^\s*-\s*\d+\s*-\s*$", re.MULTILINE),
    # Multiple blank lines
    re.compile(r"\n{3,}", re.MULTILINE),
    # Common PDF extraction artifacts
    re.compile(r"^\s*\d+\s*$", re.MULTILINE),  # Standalone page numbers
]

# ============================================================================
# LEGAL DOCUMENT TYPE PATTERNS
# ============================================================================

LEGAL_TYPE_PATTERN = re.compile(
    r"(UNDANG-UNDANG|PERATURAN PEMERINTAH|KEPUTUSAN PRESIDEN|PERATURAN MENTERI|QANUN|PERATURAN DAERAH|PERATURAN KEPALA)",
    re.IGNORECASE,
)

# Abbreviations mapping
LEGAL_TYPE_ABBREV = {
    "UNDANG-UNDANG": "UU",
    "PERATURAN PEMERINTAH": "PP",
    "KEPUTUSAN PRESIDEN": "Keppres",
    "PERATURAN MENTERI": "Permen",
    "QANUN": "Qanun",
    "PERATURAN DAERAH": "Perda",
    "PERATURAN KEPALA": "Perkep",
}

# ============================================================================
# METADATA EXTRACTION PATTERNS
# ============================================================================

# Document number (supports "12", "12A", "12/2024")
NUMBER_PATTERN = re.compile(r"NOMOR\s+(\d+[A-Z]?)(?:[/-]\d+)?", re.IGNORECASE)

# Year
YEAR_PATTERN = re.compile(r"TAHUN\s+(\d{4})", re.IGNORECASE)

# Topic (text after "TENTANG" until "DENGAN RAHMAT" or end)
TOPIC_PATTERN = re.compile(
    r"TENTANG\s+(.+?)(?=DENGAN RAHMAT|Menimbang|Mengingat|$)", re.IGNORECASE | re.DOTALL
)

# Status indicators
STATUS_PATTERNS = {
    "dicabut": re.compile(r"DICABUT|TIDAK BERLAKU|DIGANTI", re.IGNORECASE),
    "berlaku": re.compile(r"BERLAKU|MASIH BERLAKU", re.IGNORECASE),
}

# ============================================================================
# STRUCTURE MARKERS - Indonesian Legal Hierarchy
# ============================================================================

# Konsiderans (Considerations)
KONSIDERANS_MARKERS = [
    "Menimbang",
    "Mengingat",
]

# Batang Tubuh (Body) structure
BAB_PATTERN = re.compile(
    r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE
)
BAGIAN_PATTERN = re.compile(
    r"^Bagian\s+([A-Za-z]+|\d+)\s+(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE
)
PARAGRAF_PATTERN = re.compile(r"^Paragraf\s+(\d+)\s+(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)

# Pasal (Article) - CRITICAL UNIT
PASAL_PATTERN = re.compile(
    r"^Pasal\s+(\d+[A-Z]?)\s*(.+?)(?=^Pasal\s+\d+|^BAB\s+|^Penjelasan|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Ayat (Clause/Paragraph within Pasal)
# Ayat (Clause/Paragraph within Pasal)
AYAT_PATTERN = re.compile(
    r"(?:^|\n)\s*\((\d+)\)\s*(.+?)(?=(?:^|\n)\s*\(\d+\)|$)", re.MULTILINE | re.DOTALL
)

# Penjelasan (Elucidation)
PENJELASAN_PATTERN = re.compile(
    r"^Penjelasan\s+(?:Umum|Atas|Pasal|Ayat)", re.IGNORECASE | re.MULTILINE
)

# ============================================================================
# CHUNKING CONFIGURATION
# ============================================================================

# Maximum tokens per Pasal before splitting by Ayat
MAX_PASAL_TOKENS = 1000

# Context template for chunk injection
CONTEXT_TEMPLATE = (
    "[CONTEXT: {type} NO {number} TAHUN {year} - TENTANG {topic}{bab}{pasal}]\n{content}"
)

# ============================================================================
# WHITESPACE NORMALIZATION
# ============================================================================

# Common PDF extraction issues
WHITESPACE_FIXES = [
    (r"[ \t]+", " "),  # Multiple spaces/tabs to single (PRESERVE NEWLINES!)
    (r"\n\s+\n", "\n\n"),  # Blank lines with spaces
    (r"([a-z])\n([A-Z])", r"\1 \2"),  # Broken sentences
]
