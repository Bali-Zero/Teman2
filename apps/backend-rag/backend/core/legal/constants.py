"""
Constants for Indonesian Legal Document Processing
Regex patterns, keywords, and structure markers
"""

import re

# ============================================================================
# ReDoS NOTE — py/polynomial-redos, cured 2026-08-01
# ============================================================================
# THE SHAPE: two quantifiers that can both eat the SAME `\n`. Two forms of it here.
#
#   (a) a MULTILINE anchor (`^`, or the `(?:^|\n)` idiom) followed by `\s*` — `\s`
#       matches `\n`, the very character the anchor already ranges over, so the engine
#       gets O(n) start positions × O(n) backtracking on any run of blank lines;
#   (b) `\s*\n?\s*` — three overlapping quantifiers on one run, O(n²) partitions from a
#       SINGLE start position, which is why (b) hides from the payloads that expose (a).
#
# A legal PDF's OCR dump is mostly blank lines, and `/api/legal/ingest` accepts them.
#
# THE CURE IS `[^\S\n]` — "whitespace except newline" — NOT `[ \t\r]`. That distinction
# is load-bearing and was caught by adversarial review, not by the author: Python's `\s`
# on a str pattern also matches NBSP (`\xa0`), FORM FEED (`\f` — the PDF page break!),
# vertical tab, and every Unicode space. `[ \t\r]` silently dropped them, and
# `WHITESPACE_FIXES` does not normalise them away, so `\xa0Pasal 1` parsed to ZERO
# articles instead of two. `[^\S\n]` is exactly `\s` minus `\n`: verified identical to
# the pre-fix patterns on space, tab, CR, NBSP, FF, VT, EM-space and narrow-NBSP.
#
# MEASURED (`n` doubling: ~2x is linear, ~4x is quadratic):
#   form (a), on `"\n" * n`, 4k→32k:
#     PASAL_PATTERN   0.021 → 0.077 → 0.348 → 1.652 s
#     AYAT_PATTERN    0.019 → 0.080 → 0.318 → 1.168 s
#     page patterns   0.019 → 0.069 → 0.283 → 1.122 s
#   form (b), on `"BAB I" + "\n" * n`, 2k→16k:
#     BAB_PATTERN     0.046 → 0.184 → 0.689 → 2.868 s
#   after the cure: every one under 6 ms, ~2x per doubling. BAB at 16k: 0.0014 s.
#
# HOW (b) STAYED HIDDEN, because the next audit will hit the same wall: a bare run of
# newlines never gets past `^BAB`, and a payload with any non-newline character lets the
# trailing `(.+?)` succeed immediately. Only `<literal prefix> + "\n" * n` reproduces it.
# The first audit here measured BAB "linear, <1ms at 16k" and wrote that in this comment;
# it was false, and the payload — not the pattern — was why. Probe a pattern's INTERIOR
# with its own literal prefix, or you are measuring your payload.
#
# THE CLASS AUDIT: SEVEN distinct quadratic patterns lived in this module, and the
# scanner saw three of them — PASAL_PATTERN (5 alerts, across chunker and parser), the
# inline copy in `quality_validators` (1), and BAB_PATTERN (2). It never flagged
# AYAT_PATTERN, either page-marker pattern, or the cleaner's Step-5 copy. Three of the
# seven were literal DUPLICATES of another; each is now a shared constant, so the next
# audit has names to check instead of spellings to find.
# ============================================================================

# The "a line holding only a page number" rule. Defined ONCE: `cleaner.py` Step 5
# used to carry a second literal copy of it, which is how two spellings of one rule
# drift apart.
PAGE_NUMBER_LINE = r"^[^\S\n]*\d+[^\S\n]*$"

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
    re.compile(r"^[^\S\n]*-[^\S\n]*\d+[^\S\n]*-[^\S\n]*$", re.MULTILINE),
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

# Ordered LONGEST-FIRST wherever one name is a prefix of another. Python
# alternation is first-match-wins at a given position, so "UNDANG-UNDANG" listed
# before "UNDANG-UNDANG DASAR" would silently file the constitution as an
# ordinary law, and "PERATURAN PEMERINTAH" before its PENGGANTI form would file
# an emergency regulation (Perppu) as a government regulation (PP). Both are
# identity collisions waiting to happen, since document_id is built from the
# abbreviation.
LEGAL_TYPE_NAMES = (
    "PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG",
    "UNDANG-UNDANG DASAR",
    "UNDANG-UNDANG",
    "PERATURAN PEMERINTAH",
    "PERATURAN PRESIDEN",
    "KEPUTUSAN PRESIDEN",
    "INSTRUKSI PRESIDEN",
    "PERATURAN MENTERI",
    "KEPUTUSAN MENTERI",
    "INSTRUKSI MENTERI",
    "PERATURAN GUBERNUR",
    "KEPUTUSAN GUBERNUR",
    "PERATURAN BUPATI",
    "PERATURAN WALIKOTA",
    "PERATURAN WALI KOTA",
    "PERATURAN DAERAH",
    "PERATURAN BADAN",
    "PERATURAN KEPALA",
    "SURAT EDARAN",
    "QANUN",
)

_LEGAL_TYPE_ALTERNATION = "|".join(re.escape(name) for name in LEGAL_TYPE_NAMES)

LEGAL_TYPE_PATTERN = re.compile(rf"({_LEGAL_TYPE_ALTERNATION})", re.IGNORECASE)

# Abbreviations mapping. Every name in LEGAL_TYPE_NAMES must appear here --
# a missing entry does not raise, it falls through to the full Indonesian name
# and quietly changes the shape of document_id (see the tripwire test).
LEGAL_TYPE_ABBREV = {
    "PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG": "Perppu",
    "UNDANG-UNDANG DASAR": "UUD",
    "UNDANG-UNDANG": "UU",
    "PERATURAN PEMERINTAH": "PP",
    "PERATURAN PRESIDEN": "Perpres",
    "KEPUTUSAN PRESIDEN": "Keppres",
    "INSTRUKSI PRESIDEN": "Inpres",
    "PERATURAN MENTERI": "Permen",
    "KEPUTUSAN MENTERI": "Kepmen",
    "INSTRUKSI MENTERI": "Inmen",
    "PERATURAN GUBERNUR": "Pergub",
    "KEPUTUSAN GUBERNUR": "Kepgub",
    "PERATURAN BUPATI": "Perbup",
    "PERATURAN WALIKOTA": "Perwali",
    "PERATURAN WALI KOTA": "Perwali",
    "PERATURAN DAERAH": "Perda",
    "PERATURAN BADAN": "Perban",
    "PERATURAN KEPALA": "Perkep",
    "SURAT EDARAN": "SE",
    "QANUN": "Qanun",
}

# ============================================================================
# METADATA EXTRACTION PATTERNS
# ============================================================================

# Document number (supports "12", "12A", "12/2024")
NUMBER_PATTERN = re.compile(r"NOMOR\s+(\d+[A-Z]?)(?:[/-]\d+)?", re.IGNORECASE)

# Year
YEAR_PATTERN = re.compile(r"TAHUN\s+(\d{4})", re.IGNORECASE)

# ---------------------------------------------------------------------------
# TITLE-BLOCK IDENTITY PATTERN
# ---------------------------------------------------------------------------
# Why this exists. The three patterns above are searched INDEPENDENTLY over the
# whole document, each taking its first hit. Every Indonesian regulation cites
# other regulations, so that lets the type come from one instrument, the number
# from a second and the year from a third -- an identity assembled from three
# different laws. It is not hypothetical: PP 31/2013 (Immigration) was stored as
# number 5409, and a ministerial decree measured on 2026-08-25 came out as
# "UU 28/2025" with every field scavenged from its own citation list.
#
# This pattern requires type, number and year to be CO-LOCATED, in title order,
# inside a bounded window, so all three can only come from one instrument.
# Measured over the 188 real PDFs in kb_sources (27 with a filename that states
# the expected answer): 20/27 correct before, 26/27 after. The single remaining
# miss is a PDF whose title page does not survive parsing at all -- no pattern
# can reach it.
#
# The gaps are bounded and lazy ({0,120} and {0,40}) and no quantifier nests
# over an overlapping character class. Measured against 200k-character
# pathological inputs: 0.011s and 0.006s. This file already carries a ReDoS
# scar (see the page-pattern comment above) -- the bounds are load-bearing,
# not decorative.

# A document number is NOT always an integer. Ministerial decrees are numbered
# alphanumerically (e.g. "M.IP-19.GR.01.01"), so the token is captured broadly
# here and interpreted in normalize_document_number().
_NUMBER_TOKEN = r"[A-Za-z0-9][A-Za-z0-9./-]{0,40}"

LEGAL_TITLE_PATTERN = re.compile(
    rf"(?P<type>{_LEGAL_TYPE_ALTERNATION})"
    rf"[\s\S]{{0,120}}?"
    rf"NOMOR\s*(?P<number>{_NUMBER_TOKEN})"
    rf"[\s\S]{{0,40}}?"
    rf"TAHUN\s*(?P<year>(?:19|20)\d{{2}})",
    re.IGNORECASE,
)

# The citation list opens with "Menimbang"/"Mengingat"; the title block is what
# precedes it. The search deliberately starts at CITATION_SEARCH_OFFSET rather
# than 0: on some scans the cleaner hoists those two words to the very front of
# the text, and a guard that merely required `start > 200` then fell through to
# the whole document (measured on Perpres 157/2024).
CITATION_START_PATTERN = re.compile(r"\bMENIMBANG\b|\bMENGINGAT\b", re.IGNORECASE)
CITATION_SEARCH_OFFSET = 200
TITLE_BLOCK_FALLBACK_CHARS = 6000

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
# `(?:[^\S\n]*\n)*[^\S\n]*` replaces `\s*\n?\s*`: BAB's title may sit one or more blank
# lines below its number, and `.` here is NOT DOTALL, so the prefix — unlike PASAL's —
# genuinely has to cross those newlines to reach the title. Written as "any number of
# whole lines, then horizontal space", each iteration consuming exactly ONE `\n`, it
# still crosses them but with no ambiguity left to backtrack over.
# The old spelling was three overlapping quantifiers on the same run: on
# `"BAB I" + "\n" * n` it took 0.046 / 0.184 / 0.689 / 2.868 s at n=2k/4k/8k/16k (4.2x
# per doubling); after, ~1 ms and ~2x. See the ReDoS note at the top of this file — and
# note that reaching it needs a payload carrying the literal PREFIX, since a bare run of
# newlines never gets past `^BAB` (CodeQL #7778/#7783 named it; the payloads that fail to
# reproduce it are the ones without `BAB I` in front).
BAB_PATTERN = re.compile(
    r"^BAB\s+([IVX]+|[A-Z]+|\d+)(?:[^\S\n]*\n)*[^\S\n]*(.+?)(?=\n|$)",
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
    r"(?:^|\n)[^\S\n]*Pasal\s+([IVXLC]+|\d+[A-Z]?)(?:[^\S\n]*\n)*[^\S\n]*(.+?)(?=(?:^|\n)[^\S\n]*Pasal\s+(?:[IVXLC]+|\d+[A-Z]?)|^[^\S\n]*BAB\s+|^Penjelasan|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Ayat (Clause/Paragraph within Pasal)
# `quality_validators.extract_ayat_numbers()` needs the marker alone, without the body,
# so the prefix is a shared constant. It used to be a second literal copy there — and
# CodeQL flagged the COPY (#7777) while missing the original, which is what a duplicated
# rule does to a scanner.
AYAT_MARKER_PREFIX = r"(?:^|\n)[^\S\n]*\((\d+)\)"

AYAT_PATTERN = re.compile(
    AYAT_MARKER_PREFIX + r"\s*(.+?)(?=(?:^|\n)[^\S\n]*\(\d+\)|$)",
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
