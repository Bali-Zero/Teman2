"""
Constants for Indonesian Legal Document Processing
Regex patterns, keywords, and structure markers
"""

import re

# ============================================================================
# ReDoS NOTE — py/polynomial-redos, cured 2026-08-01
# ============================================================================
# THE SHAPE: a MULTILINE anchor (`^`, or the `(?:^|\n)` idiom) followed by `\s*`.
# `\s` matches `\n` — the very character the anchor already ranges over — so the
# engine gets O(n) start positions × O(n) backtracking on any run of blank lines,
# and a legal PDF's OCR dump is mostly blank lines. The cure is `[ \t\r]*`: the
# same horizontal whitespace, minus the one character that overlaps the anchor.
# `\r` stays in the class because `\s` covered it and this module parses CRLF.
#
# MEASURED, on `"\n" * n` (`n` doubling, so ~2x is linear and ~4x is quadratic):
#     PASAL_PATTERN   0.021 → 0.077 → 0.348 → 1.652 s   (4k→32k, ~4x per step)
#     AYAT_PATTERN    0.019 → 0.080 → 0.318 → 1.168 s
#     page patterns   0.019 → 0.069 → 0.283 → 1.122 s
#   after the cure, every one of them: < 0.006 s at n=256k, ~2x per doubling.
#
# THE CLASS AUDIT: SIX distinct quadratic patterns lived in this module, and the
# scanner saw two of them — PASAL_PATTERN (5 alerts, across chunker and parser)
# and the inline copy in `quality_validators` (1 alert). It never flagged
# AYAT_PATTERN, either page-marker pattern, or the cleaner's Step-5 copy. Three of
# the six were literal DUPLICATES of another; each is now a shared constant, so
# the next audit has six names to check instead of nine spellings to find.
#
# NOT changed, deliberately: BAB_PATTERN below is flagged too (structure_parser
# 170/371) but measured LINEAR on every payload aimed at its own ambiguities
# (`\s*\n?\s*`, and the `[IVX]+|[A-Z]+` overlap) — ~2x per doubling, <1ms at 16k.
# It also legitimately spans a blank line between `BAB II` and its title, which
# `[ \t\r]*` would break. Left open with the evidence rather than "fixed" blind.
# ============================================================================

# The "a line holding only a page number" rule. Defined ONCE: `cleaner.py` Step 5
# used to carry a second literal copy of it, which is how two spellings of one rule
# drift apart.
PAGE_NUMBER_LINE = r"^[ \t\r]*\d+[ \t\r]*$"

# ============================================================================
# NOISE PATTERNS - Headers/Footers to remove
# ============================================================================

NOISE_PATTERNS = [
    # Page numbers
    re.compile(r"^Halaman\s+\d+\s+dari\s+\d+", re.IGNORECASE | re.MULTILINE),
    # Certification footer
    re.compile(
        r"^Salinan sesuai dengan aslinya.*?(?=\n)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    # President header (repeated on every page)
    re.compile(r"^PRESIDEN REPUBLIK INDONESIA\s*\n", re.IGNORECASE | re.MULTILINE),
    # Page separators
    re.compile(r"^[ \t\r]*-[ \t\r]*\d+[ \t\r]*-[ \t\r]*$", re.MULTILINE),
    # Common PDF extraction artifacts
    re.compile(PAGE_NUMBER_LINE, re.MULTILINE),  # Standalone page numbers
]
# NOT in the list: `\n{3,}`. Every entry above is substituted with the EMPTY STRING by
# `LegalCleaner.clean()` Step 1, so a `\n{3,}` entry DELETES the paragraph break instead
# of collapsing it — `Pasal 1\n\n\n\nPasal 2` came out as `Pasal 1Pasal 2`, one chunk for
# a document with two articles. Collapsing to `\n\n` is Step 6's job and it does it with
# the right replacement. The two are not redundant copies; only one of them was correct.
#
# This was masked until 2026-08-01: the page patterns above used to be anchored with
# `\s*`, which swallowed the surrounding newlines and kept the run under three. Removing
# the ReDoS also removed the mask — the same `\s`-matches-`\n` overlap caused both.

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
    r"TENTANG\s+(.+?)(?=DENGAN RAHMAT|Menimbang|Mengingat|$)",
    re.IGNORECASE | re.DOTALL,
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
    r"^BAB\s+([IVX]+|[A-Z]+|\d+)\s*\n?\s*(.+?)(?=\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
BAGIAN_PATTERN = re.compile(
    r"^Bagian\s+([A-Za-z]+|\d+)\s+(.+?)(?=\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
PARAGRAF_PATTERN = re.compile(r"^Paragraf\s+(\d+)\s+(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)

# Pasal (Article) - CRITICAL UNIT
# Supports "Pasal 1", "Pasal I", "Pasal 1A"
# Relaxed start anchor to handle OCR artifacts
PASAL_PATTERN = re.compile(
    r"(?:^|\n)[ \t\r]*Pasal\s+([IVXLC]+|\d+[A-Z]?)\s*\n?\s*(.+?)(?=(?:^|\n)[ \t\r]*Pasal\s+(?:[IVXLC]+|\d+[A-Z]?)|^[ \t\r]*BAB\s+|^Penjelasan|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Ayat (Clause/Paragraph within Pasal)
# `quality_validators.extract_ayat_numbers()` needs the marker alone, without the body,
# so the prefix is a shared constant. It used to be a second literal copy there — and
# CodeQL flagged the COPY (#7777) while missing the original, which is what a duplicated
# rule does to a scanner.
AYAT_MARKER_PREFIX = r"(?:^|\n)[ \t\r]*\((\d+)\)"

AYAT_PATTERN = re.compile(
    AYAT_MARKER_PREFIX + r"\s*(.+?)(?=(?:^|\n)[ \t\r]*\(\d+\)|$)",
    re.MULTILINE | re.DOTALL,
)

# Penjelasan (Elucidation)
PENJELASAN_PATTERN = re.compile(
    r"^Penjelasan\s+(?:Umum|Atas|Pasal|Ayat)",
    re.IGNORECASE | re.MULTILINE,
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
