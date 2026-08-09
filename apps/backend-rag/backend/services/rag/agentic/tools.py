"""
Agentic RAG Tool Definitions

This module contains the essential tool class definitions used by the AgenticRAGOrchestrator.
Each tool inherits from BaseTool and implements the required interface.

Essential Tools (Dec 2025):
- VectorSearchTool: Knowledge base search (Legal, Visa, KBLI).
- PricingTool: Official Service pricing lookup (High Precision).
- TeamKnowledgeTool: Team member information.
- CalculatorTool: Safe mathematical calculations (Safe Math).
- VisionTool: Visual document analysis.
- ImageGenerationTool: AI image generation (Google Imagen / Pollinations fallback).
- WebSearchTool: Web search for topics outside KB (tourism, lifestyle, general info).

DESIGN PRINCIPLE: No hardcoded keywords, patterns, or domain knowledge.
The LLM decides which collection to search based on the tool description.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
from backend.services.agents.tool_authorizer import WA_L0_VECTOR_COLLECTIONS
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.rag.vision_rag import VisionRAGService
from backend.services.tools.definitions import BaseTool

logger = logging.getLogger(__name__)

# Module-level persistent HTTP client for agentic tools
_client: httpx.AsyncClient | None = None


def _get_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Get or create the shared async client for agentic tools."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def close_agentic_tools_client() -> None:
    """Close the module-level async client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    logger.info("Agentic tools module HTTP client closed.")


# Available collections - NO domain mapping, NO keywords
# The LLM reads the description and decides which to use
# Note: Collections ending in _hybrid have BM25 sparse vectors for better search
AVAILABLE_COLLECTIONS = [
    "visa_oracle",
    "legal_unified",
    "kbli_2025_final",  # KBLI 2025 - 1,563 BPS codes + 304 gold editorial (BPS Reg. 7/2025 + PP28/2025)
    "tax_genius",
    "bali_zero_pricing_hybrid",
    "training_conversations_hybrid",  # Migrated to hybrid format Dec 2025
    "immigration_circulars",  # Kemnaker/Imigrasi circulars
    "balizero_news",  # BaliZero intel articles: immigration, tax, bali news, business regulations
]

_WA_URL_RE = re.compile(r"https?://[^\s)\]}>\"']+", re.IGNORECASE)

_WA_ID_METADATA_PREFIXES = (
    ("doc",),
    ("document",),
    ("file",),
    ("drive",),
    ("drive", "document"),
    ("drive", "file"),
    ("google", "drive"),
    ("google", "drive", "document"),
    ("google", "drive", "file"),
    ("internal",),
    ("source",),
    ("source", "document"),
    ("source", "file"),
    ("source", "metadata"),
    ("metadata",),
    ("internal", "document"),
    ("internal", "file"),
)
_WA_URL_METADATA_PREFIXES = (
    (),
    ("doc",),
    ("document",),
    ("file",),
    ("source",),
    ("drive",),
    ("google", "drive"),
    ("internal",),
    ("internal", "source"),
    ("internal", "metadata"),
    ("metadata",),
)


def _wa_rag_metadata_label_words() -> tuple[tuple[str, ...], ...]:
    """Return canonical metadata labels before separator/case normalization."""
    labels = {
        ("source",),
        ("metadata",),
        ("source", "metadata"),
        ("source", "metadata", "inline"),
        ("internal", "metadata"),
        ("internal", "source"),
        ("internal", "source", "metadata"),
        ("internal", "copy"),
        ("collection",),
        ("collection", "id"),
        ("collection", "name"),
        ("source", "collection"),
        ("internal", "collection"),
        ("google", "drive"),
        ("drive", "file"),
    }
    labels.update(prefix + ("id",) for prefix in _WA_ID_METADATA_PREFIXES)
    labels.update(prefix + ("url",) for prefix in _WA_URL_METADATA_PREFIXES)
    return tuple(sorted(labels, key=lambda words: (-len(words), words)))


def _wa_metadata_label_pattern(labels: tuple[tuple[str, ...], ...]) -> str:
    """Build one bounded pattern for snake/kebab/space/camel label variants."""
    token_separator = r"[\s_-]*"
    variants = (token_separator.join(re.escape(word) for word in words) for words in labels)
    return "|".join(sorted(variants, key=len, reverse=True))


_WA_RAG_METADATA_LABEL_WORDS = _wa_rag_metadata_label_words()
_WA_RAG_METADATA_LABEL_PATTERN = _wa_metadata_label_pattern(_WA_RAG_METADATA_LABEL_WORDS)
_WA_RAG_TECHNICAL_LABEL_WORDS = tuple(
    words for words in _WA_RAG_METADATA_LABEL_WORDS if len(words) > 1
)
_WA_RAG_TECHNICAL_LABEL_PATTERN = _wa_metadata_label_pattern(_WA_RAG_TECHNICAL_LABEL_WORDS)
_WA_RAG_METADATA_CANONICAL_LABELS = frozenset(
    "".join(words) for words in _WA_RAG_METADATA_LABEL_WORDS
)
_WA_RAG_SINGLE_WORD_METADATA_CANONICAL_LABELS = frozenset(
    "".join(words) for words in _WA_RAG_METADATA_LABEL_WORDS if len(words) == 1
)

# Structural parsing canonicalizes a complete candidate before accepting it as
# metadata. These two patterns remain only as a compatibility fallback for
# legacy inline, undecorated markers such as "Public rule. Internal copy: ...".
_WA_RAG_EXPLICIT_METADATA_MARKER_RE = re.compile(
    rf"(?<![A-Za-z0-9_-])(?i:(?:{_WA_RAG_METADATA_LABEL_PATTERN}))"
    rf"[ \t]*(?:->|[:=])[ \t]*"
)
_WA_RAG_TECHNICAL_DASH_MARKER_RE = re.compile(
    rf"(?<![A-Za-z0-9_-])(?i:(?:{_WA_RAG_TECHNICAL_LABEL_PATTERN}))"
    rf"[ \t]*-[ \t]*"
)
_WA_RAG_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^<>]*>")
_WA_RAG_LEADING_SCAFFOLD_RE = re.compile(r"^[ \t]*(?:\[\d+\]|\d+[.)])[ \t]*")
_WA_RAG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WA_RAG_STRONG_METADATA_DELIMITER_RE = re.compile(r"(?i:<br\s*/?>)|->|[:=]")
_WA_RAG_DASH_METADATA_DELIMITER_RE = re.compile(r"-")
_WA_RAG_WHITESPACE_METADATA_DELIMITER_RE = re.compile(r"[ \t]+")
_WA_RAG_HTML_TABLE_RE = re.compile(r"(?is)<table\b[^>]*>.*?</table\s*>")
_WA_RAG_HTML_THEAD_RE = re.compile(r"(?is)<thead\b[^>]*>.*?</thead\s*>")
_WA_RAG_HTML_ROW_RE = re.compile(r"(?is)<tr\b[^>]*>.*?</tr\s*>")
_WA_RAG_HTML_CELL_RE = re.compile(r"(?is)<(?P<tag>th|td)\b[^>]*>(?P<body>.*?)</(?P=tag)\s*>")
_WA_RAG_MARKDOWN_ALIGNMENT_CELL_RE = re.compile(r"^[ \t]*:?-{3,}:?[ \t]*$")
_WA_INTERNAL_TITLE_MARKERS = (
    "internal",
    "collection",
    "chunk",
    "doc_id",
    "document id",
    "file_id",
    "file id",
)


def _canonicalize_wa_rag_metadata_candidate(value: str) -> str:
    """Normalize decoration away while retaining exact label semantics."""
    without_scaffolding = _WA_RAG_LEADING_SCAFFOLD_RE.sub("", value)
    without_tags = _WA_RAG_HTML_TAG_RE.sub("", without_scaffolding)
    return _WA_RAG_NON_ALNUM_RE.sub("", without_tags.lower())


def _is_wa_rag_metadata_label(value: str) -> bool:
    """Return whether a complete decorated value is one canonical label."""
    return _canonicalize_wa_rag_metadata_candidate(value) in _WA_RAG_METADATA_CANONICAL_LABELS


def _wa_rag_delimiter_is_outside_html_tag(segment: str, start: int) -> bool:
    """Ignore punctuation inside an HTML tag while parsing label delimiters."""
    last_open = segment.rfind("<", 0, start + 1)
    last_close = segment.rfind(">", 0, start + 1)
    return last_open <= last_close


def _looks_like_wa_rag_metadata_value(value: str) -> bool:
    """Recognize identifier-shaped values for the ambiguous whitespace grammar."""
    without_tags = _WA_RAG_HTML_TAG_RE.sub("", value).lstrip()
    if not without_tags:
        return False
    if without_tags.startswith(("http://", "https://", "{", "[")):
        return True

    first_token = without_tags.split(maxsplit=1)[0].strip("*`'\"[](){}<>#,;:=")
    if not first_token:
        return False
    if first_token.startswith(("http://", "https://")):
        return True
    if "_" in first_token or "/" in first_token or "\\" in first_token:
        return True
    if any(character.isdigit() for character in first_token):
        return True
    uppercase_count = sum(character.isupper() for character in first_token)
    lowercase_count = sum(character.islower() for character in first_token)
    return len(first_token) >= 12 and uppercase_count >= 2 and lowercase_count >= 2


def _find_delimited_wa_rag_metadata_marker_end(
    segment: str,
    delimiter_pattern: re.Pattern[str],
    *,
    require_identifier_value: bool,
    protect_unspaced_single_label: bool = False,
) -> int | None:
    """Return the longest exact label candidate for one delimiter class."""
    candidates: list[tuple[int, int]] = []
    for delimiter in delimiter_pattern.finditer(segment):
        delimiter_text = delimiter.group(0).lower()
        if not delimiter_text.startswith("<br") and not _wa_rag_delimiter_is_outside_html_tag(
            segment, delimiter.start()
        ):
            continue
        canonical_candidate = _canonicalize_wa_rag_metadata_candidate(segment[: delimiter.start()])
        if canonical_candidate not in _WA_RAG_METADATA_CANONICAL_LABELS:
            continue
        value = segment[delimiter.end() :]
        value_is_identifier = _looks_like_wa_rag_metadata_value(value)
        if require_identifier_value and not value_is_identifier:
            continue
        if (
            protect_unspaced_single_label
            and canonical_candidate in _WA_RAG_SINGLE_WORD_METADATA_CANONICAL_LABELS
            and delimiter.start() > 0
            and not segment[delimiter.start() - 1].isspace()
            and delimiter.end() < len(segment)
            and not segment[delimiter.end()].isspace()
            and not value_is_identifier
        ):
            continue
        candidates.append((delimiter.start(), delimiter.end()))

    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _find_structural_wa_rag_metadata_marker(
    raw_line: str,
    cursor: int,
) -> tuple[int, int] | None:
    """Find exact-canonical metadata at a line, pipe, or semicolon boundary."""
    boundary_starts = (0, *(match.start() for match in re.finditer(r"[|;]", raw_line)))
    for marker_start in boundary_starts:
        if marker_start < cursor:
            continue

        content_start = marker_start
        if marker_start < len(raw_line) and raw_line[marker_start] in "|;":
            content_start += 1
        next_boundary = re.search(r"[|;]", raw_line[content_start:])
        segment_end = (
            len(raw_line) if next_boundary is None else content_start + next_boundary.start()
        )
        segment = raw_line[content_start:segment_end]

        strong_marker_end = _find_delimited_wa_rag_metadata_marker_end(
            segment,
            _WA_RAG_STRONG_METADATA_DELIMITER_RE,
            require_identifier_value=False,
        )
        if strong_marker_end is not None:
            return marker_start, content_start + strong_marker_end

        dash_marker_end = _find_delimited_wa_rag_metadata_marker_end(
            segment,
            _WA_RAG_DASH_METADATA_DELIMITER_RE,
            require_identifier_value=False,
            protect_unspaced_single_label=True,
        )
        if dash_marker_end is not None:
            return marker_start, content_start + dash_marker_end

        whitespace_marker_end = _find_delimited_wa_rag_metadata_marker_end(
            segment,
            _WA_RAG_WHITESPACE_METADATA_DELIMITER_RE,
            require_identifier_value=True,
        )
        if whitespace_marker_end is not None:
            return marker_start, content_start + whitespace_marker_end

    return None


def _find_wa_rag_metadata_marker(
    raw_line: str,
    cursor: int,
) -> tuple[int, int] | None:
    """Return the earliest complete metadata label+delimiter marker."""
    matches = [
        marker.span()
        for pattern in (
            _WA_RAG_EXPLICIT_METADATA_MARKER_RE,
            _WA_RAG_TECHNICAL_DASH_MARKER_RE,
        )
        if (marker := pattern.search(raw_line, cursor)) is not None
    ]
    structural_marker = _find_structural_wa_rag_metadata_marker(raw_line, cursor)
    if structural_marker is not None:
        matches.append(structural_marker)
    if not matches:
        return None
    return min(matches, key=lambda marker: (marker[0], -marker[1]))


def _minimize_wa_rag_line(raw_line: str) -> str:
    """Remove inline and structural metadata from one non-table line."""
    # A marker begins a metadata segment. Its value runs to the next
    # structural pipe/semicolon or the end of the line. Iterating lets us
    # retain public segments on either side without ever retaining a partial
    # snake/kebab/camel label.
    public_segments: list[str] = []
    cursor = 0
    while marker := _find_wa_rag_metadata_marker(raw_line, cursor):
        marker_start, marker_end = marker
        prefix = raw_line[cursor:marker_start].rstrip(" |;,:\t")
        if prefix.strip():
            public_segments.append(prefix.strip())

        segment_boundary = re.search(r"[|;]", raw_line[marker_end:])
        if segment_boundary is None:
            cursor = len(raw_line)
            break
        # Keep the structural boundary under the next search cursor so a
        # following dash/whitespace-only metadata segment is recognized.
        cursor = marker_end + segment_boundary.start()
    else:
        remainder = raw_line[cursor:].strip(" |;,:\t")
        if remainder:
            public_segments.append(remainder)

    return _WA_URL_RE.sub("", " ".join(public_segments)).strip()


def _with_original_cell_padding(raw_cell: str, public_cell: str) -> str:
    """Put sanitized cell content back without changing table spacing."""
    leading = raw_cell[: len(raw_cell) - len(raw_cell.lstrip())]
    trailing = raw_cell[len(raw_cell.rstrip()) :]
    return f"{leading}{public_cell}{trailing}"


def _parse_wa_rag_markdown_table_row(
    raw_line: str,
) -> tuple[list[str], list[str], bool, bool] | None:
    """Return raw Markdown pipe-row parts and logical cells when structural."""
    if "|" not in raw_line:
        return None

    parts = re.split(r"(?<!\\)\|", raw_line)
    has_leading_pipe = re.match(r"^[ \t]*\|", raw_line) is not None
    has_trailing_pipe = re.search(r"\|[ \t]*$", raw_line) is not None
    first_cell = 1 if has_leading_pipe else 0
    last_cell = len(parts) - 1 if has_trailing_pipe else len(parts)
    cells = parts[first_cell:last_cell]
    if len(cells) < 2:
        return None

    has_metadata_cell = any(_is_wa_rag_metadata_label(cell) for cell in cells)
    if not (has_leading_pipe and has_trailing_pipe) and not has_metadata_cell:
        return None
    return parts, cells, has_leading_pipe, has_trailing_pipe


def _render_wa_rag_markdown_table_row(
    parts: list[str],
    cells: list[str],
    has_leading_pipe: bool,
    has_trailing_pipe: bool,
) -> str:
    """Render selected raw cells while retaining outer pipes and whitespace."""
    leading = f"{parts[0]}|" if has_leading_pipe else ""
    trailing = f"|{parts[-1]}" if has_trailing_pipe else ""
    return f"{leading}{'|'.join(cells)}{trailing}"


def _is_wa_rag_markdown_alignment_row(cells: list[str]) -> bool:
    """Return whether every cell is a Markdown table alignment marker."""
    return bool(cells) and all(_WA_RAG_MARKDOWN_ALIGNMENT_CELL_RE.fullmatch(cell) for cell in cells)


def _sanitize_wa_rag_markdown_table_row(raw_line: str) -> str | None:
    """Remove canonical label/value cell pairs from a Markdown pipe row."""
    parsed_row = _parse_wa_rag_markdown_table_row(raw_line)
    if parsed_row is None:
        return None
    parts, cells, has_leading_pipe, has_trailing_pipe = parsed_row

    # Alignment markers carry no content and must retain their colon syntax.
    if _is_wa_rag_markdown_alignment_row(cells):
        return raw_line

    public_cells: list[str] = []
    cell_index = 0
    while cell_index < len(cells):
        raw_cell = cells[cell_index]
        if _is_wa_rag_metadata_label(raw_cell):
            # A structural metadata label cell owns the following value cell.
            cell_index += 1
            if cell_index < len(cells) and not _is_wa_rag_metadata_label(cells[cell_index]):
                cell_index += 1
            continue

        minimized_cell = _minimize_wa_rag_line(raw_cell.strip())
        if minimized_cell:
            public_cells.append(
                raw_cell
                if minimized_cell == raw_cell.strip()
                else _with_original_cell_padding(raw_cell, minimized_cell)
            )
        cell_index += 1

    if not public_cells:
        return ""

    return _render_wa_rag_markdown_table_row(
        parts,
        public_cells,
        has_leading_pipe,
        has_trailing_pipe,
    )


def _sanitize_wa_rag_markdown_table_block(
    raw_lines: list[str],
    start: int,
) -> tuple[list[str], int] | None:
    """Remove metadata-owned columns from one complete Markdown table block."""
    if start + 1 >= len(raw_lines):
        return None
    parsed_header = _parse_wa_rag_markdown_table_row(raw_lines[start])
    parsed_alignment = _parse_wa_rag_markdown_table_row(raw_lines[start + 1])
    if parsed_header is None or parsed_alignment is None:
        return None

    header_cells = parsed_header[1]
    alignment_cells = parsed_alignment[1]
    if len(header_cells) != len(alignment_cells) or not _is_wa_rag_markdown_alignment_row(
        alignment_cells
    ):
        return None

    block_end = start + 2
    while block_end < len(raw_lines):
        parsed_row = _parse_wa_rag_markdown_table_row(raw_lines[block_end])
        if parsed_row is None:
            break
        block_end += 1

    private_columns = {
        cell_index
        for cell_index, header_cell in enumerate(header_cells)
        if _is_wa_rag_metadata_label(header_cell)
    }
    if not private_columns:
        return raw_lines[start:block_end], block_end

    public_columns = [
        cell_index for cell_index in range(len(header_cells)) if cell_index not in private_columns
    ]
    if not public_columns:
        return [], block_end

    sanitized_lines: list[str] = []
    for raw_line in raw_lines[start:block_end]:
        parsed_row = _parse_wa_rag_markdown_table_row(raw_line)
        if parsed_row is None:
            continue
        parts, cells, has_leading_pipe, has_trailing_pipe = parsed_row
        public_cells = [cells[index] for index in public_columns if index < len(cells)]
        if public_cells:
            sanitized_lines.append(
                _render_wa_rag_markdown_table_row(
                    parts,
                    public_cells,
                    has_leading_pipe,
                    has_trailing_pipe,
                )
            )
    return sanitized_lines, block_end


def _sanitize_wa_rag_html_table_row(raw_row: str) -> str:
    """Remove canonical label/value cell pairs from one simple HTML row."""
    cells = list(_WA_RAG_HTML_CELL_RE.finditer(raw_row))
    if not cells or not any(_is_wa_rag_metadata_label(cell.group("body")) for cell in cells):
        return raw_row

    public_cells: list[str] = []
    cell_index = 0
    while cell_index < len(cells):
        cell = cells[cell_index]
        if _is_wa_rag_metadata_label(cell.group("body")):
            cell_index += 1
            if cell_index < len(cells) and not _is_wa_rag_metadata_label(
                cells[cell_index].group("body")
            ):
                cell_index += 1
            continue
        public_cells.append(cell.group(0))
        cell_index += 1

    if not public_cells:
        return ""
    return f"{raw_row[: cells[0].start()]}{''.join(public_cells)}{raw_row[cells[-1].end() :]}"


def _sanitize_wa_rag_html_table(raw_table: str) -> str:
    """Strip metadata pairs or metadata-owned columns from a simple HTML table."""
    rows = list(_WA_RAG_HTML_ROW_RE.finditer(raw_table))
    thead_ranges = [
        (section.start(), section.end()) for section in _WA_RAG_HTML_THEAD_RE.finditer(raw_table)
    ]

    def is_structural_header_row(row: re.Match[str]) -> bool:
        cells = list(_WA_RAG_HTML_CELL_RE.finditer(row.group(0)))
        in_thead = any(start <= row.start() < end for start, end in thead_ranges)
        return bool(cells) and (
            in_thead or all(cell.group("tag").lower() == "th" for cell in cells)
        )

    header_row = next(
        (row for row in rows if is_structural_header_row(row)),
        None,
    )
    if header_row is not None and len(rows) > 1:
        header_cells = list(_WA_RAG_HTML_CELL_RE.finditer(header_row.group(0)))
        private_columns = {
            cell_index
            for cell_index, cell in enumerate(header_cells)
            if cell.group("tag").lower() == "th" and _is_wa_rag_metadata_label(cell.group("body"))
        }
        if private_columns:
            public_columns = [
                cell_index
                for cell_index in range(len(header_cells))
                if cell_index not in private_columns
            ]
            if not public_columns:
                return ""

            def remove_private_columns(row_match: re.Match[str]) -> str:
                raw_row = row_match.group(0)
                cells = list(_WA_RAG_HTML_CELL_RE.finditer(raw_row))
                public_cells = [
                    cell.group(0)
                    for cell_index, cell in enumerate(cells)
                    if cell_index in public_columns
                ]
                if not public_cells:
                    return ""
                return (
                    f"{raw_row[: cells[0].start()]}"
                    f"{''.join(public_cells)}"
                    f"{raw_row[cells[-1].end() :]}"
                )

            return _WA_RAG_HTML_ROW_RE.sub(remove_private_columns, raw_table)

    sanitized_table = _WA_RAG_HTML_ROW_RE.sub(
        lambda row: _sanitize_wa_rag_html_table_row(row.group(0)),
        raw_table,
    )
    if (
        _WA_RAG_HTML_ROW_RE.search(sanitized_table) is None
        and not _WA_RAG_HTML_TAG_RE.sub("", sanitized_table).strip()
    ):
        return ""
    return sanitized_table


def _sanitize_wa_rag_html_tables(value: str) -> str:
    """Apply the bounded row/cell parser to simple HTML tables in a result."""
    return _WA_RAG_HTML_TABLE_RE.sub(
        lambda table: _sanitize_wa_rag_html_table(table.group(0)),
        value,
    )


def _minimize_wa_rag_text(value: Any) -> str:
    """Remove transport/source metadata before WA model observation.

    The retrieved legal prose remains intact, including semantic regulation
    names/citations. Raw URLs and explicit RAG scaffolding do not cross the
    tool-result boundary.
    """
    minimized_lines: list[str] = []
    table_sanitized_value = _sanitize_wa_rag_html_tables(str(value or ""))
    raw_lines = table_sanitized_value.splitlines()
    line_index = 0
    while line_index < len(raw_lines):
        table_block = _sanitize_wa_rag_markdown_table_block(raw_lines, line_index)
        if table_block is not None:
            sanitized_table_lines, line_index = table_block
            minimized_lines.extend(line for line in sanitized_table_lines if line.strip())
            continue

        raw_line = raw_lines[line_index]
        line_index += 1
        markdown_row = _sanitize_wa_rag_markdown_table_row(raw_line)
        public_line = (
            _WA_URL_RE.sub("", markdown_row).rstrip()
            if markdown_row is not None
            else _minimize_wa_rag_line(raw_line)
        )
        if public_line.strip():
            minimized_lines.append(public_line)

    return "\n".join(minimized_lines).strip()


def _public_wa_title(value: Any) -> str:
    """Return a minimal public title, never an internal source label."""
    title = _minimize_wa_rag_text(value)
    lowered = title.lower()
    if not title or any(marker in lowered for marker in _WA_INTERNAL_TITLE_MARKERS):
        return "Public legal reference"
    return title


class VectorSearchTool(BaseTool):
    """
    Tool for vector search in knowledge base.

    NO pattern matching. NO keyword routing.
    The LLM decides which collection to search based on the description.
    If no collection specified, searches ALL collections (federated).
    """

    def __init__(self, retriever, user_level: int = 1) -> None:
        self.retriever = retriever
        self.user_level = user_level

    @property
    def name(self) -> str:
        """Return tool name."""
        return "vector_search"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Search the knowledge base for verified information.\n\n"
            "**DEFAULT: FEDERATED SEARCH** - Omit 'collection' to search ALL collections at once.\n"
            "This is recommended for complex questions that may span multiple topics.\n\n"
            "**OPTIONALLY specify a collection** ONLY for focused single-topic queries:\n"
            "- visa_oracle: Visas, KITAS, KITAP, immigration, stay permits\n"
            "- legal_unified: Laws, company types (PT, CV, Firma), regulations\n"
            "- kbli_2025_final: Business classification codes (KBLI 2025, BPS 7/2025 + PP28/2025), 1,563 codes with licensing detail, PMA status\n"
            "- tax_genius: Taxes, PPh, PPN, NPWP, fiscal matters\n"
            "- bali_zero_pricing_hybrid: Official Bali Zero service pricing and costs\n"
            "- training_conversations_hybrid: Procedures, practical examples, FAQs\n"
            "- immigration_circulars: Immigration policy updates, circulars, Kemnaker regulations\n"
            "- balizero_news: Latest news, intel articles, regulation updates, business news from BaliZero\n\n"
            "Example: 'PT PMA requirements' → federated (legal + visa + tax)\n"
            "Example: 'PPh 21 rates' → collection='tax_genius'\n"
            "Example: 'Quanto costa D12?' → collection='bali_zero_pricing_hybrid'"
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query in natural language"},
                "collection": {
                    "type": "string",
                    "enum": AVAILABLE_COLLECTIONS,
                    "description": "The collection to search. Choose based on query topic. Omit to search all.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 8)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, collection: str = None, top_k: int = 8, **kwargs) -> str:
        """
        Execute vector search.

        If collection is specified: search only that collection.
        If collection is None: federated search across ALL collections.
        """
        is_whatsapp = kwargs.get("_is_whatsapp") is True
        requested_collection_trace = (
            ("wa_explicit" if is_whatsapp and collection else "wa_federated")
            if is_whatsapp
            else (collection or "federated_all")
        )

        with trace_span(
            "tool.vector_search",
            {
                "query_length": len(query),
                "requested_collection": requested_collection_trace,
                "top_k": top_k,
            },
        ):
            top_k = int(top_k) if top_k else 8

            # Determine which collections to search
            if is_whatsapp and collection not in (None, ""):
                if collection not in WA_L0_VECTOR_COLLECTIONS:
                    logger.warning("WA vector search denied unavailable collection")
                    return json.dumps(
                        {
                            "content": "This knowledge source is not available in this conversation.",
                            "sources": [],
                        }
                    )
                target_collections = [collection]
                logger.info("WA vector search selected one public collection")
            elif is_whatsapp:
                target_collections = sorted(WA_L0_VECTOR_COLLECTIONS)
                logger.info(
                    "WA federated vector search across %d public collections",
                    len(target_collections),
                )
            elif collection:
                # LLM specified a collection - trust its judgment
                target_collections = [collection]
                logger.info("🔍 [Vector Search] LLM selected collection: %s", collection)
            else:
                # No collection specified - search ALL (federated)
                target_collections = AVAILABLE_COLLECTIONS.copy()
                logger.info(
                    f"🌐 [Federated Search] Searching all {len(target_collections)} collections",
                )

            set_span_attribute(
                "collections_searched",
                "wa_public_safe_set" if is_whatsapp else len(target_collections),
            )

            all_chunks = []
            seen_content = set()

            # Execute search across target collections in parallel for better performance
            import asyncio

            # Determine search method based on feature flags
            from backend.app.core.config import settings as _settings

            use_hybrid = getattr(_settings, "enable_hybrid_search", False)

            async def _search_collection(target_col) -> Any:
                try:
                    per_col_limit = 5 if len(target_collections) > 1 else top_k
                    # Per-collection timeout to prevent one slow collection from blocking everything
                    async with asyncio.timeout(15.0 if use_hybrid else 10.0):
                        if use_hybrid and hasattr(self.retriever, "hybrid_search_with_reranking"):
                            # Full pipeline: BM25 + Dense + RRF + CrossEncoder reranking
                            res = await self.retriever.hybrid_search_with_reranking(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        elif hasattr(self.retriever, "search_with_reranking"):
                            res = await self.retriever.search_with_reranking(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        else:
                            res = await self.retriever.search(
                                query=query,
                                user_level=self.user_level,
                                limit=per_col_limit,
                                collection_override=target_col,
                            )
                        return target_col, res.get("results", [])
                except asyncio.TimeoutError:
                    if is_whatsapp:
                        logger.warning("WhatsApp vector search timed out")
                    else:
                        logger.warning("Vector search timed out")
                    return target_col, []
                except Exception as exc:
                    if is_whatsapp:
                        logger.warning(
                            "WhatsApp vector search failed error_type=%s",
                            type(exc).__name__,
                        )
                    else:
                        logger.warning(
                            "Vector search failed error_type=%s",
                            type(exc).__name__,
                        )
                    return target_col, []

            if use_hybrid:
                logger.info("🔀 [Hybrid Search] Using BM25+Dense+RRF+CrossEncoder pipeline")

            # Structured concurrency (Python 3.11+); _search_collection swallows exceptions.
            async with asyncio.TaskGroup() as tg:
                col_tasks = [tg.create_task(_search_collection(col)) for col in target_collections]
            search_results = [t.result() for t in col_tasks]

            # Process and deduplicate results
            for target_col, chunks_res in search_results:
                for chunk in chunks_res:
                    text = (
                        chunk.get("text", "")
                        if isinstance(chunk, dict)
                        else getattr(chunk, "text", "")
                    )
                    # Deduplicate by first 100 chars
                    if text[:100] not in seen_content:
                        seen_content.add(text[:100])
                        if isinstance(chunk, dict):
                            chunk["_source_collection"] = target_col
                        all_chunks.append(chunk)

            # Sort by score and take top results
            all_chunks.sort(
                key=lambda x: x.get("score", 0) if isinstance(x, dict) else 0,
                reverse=True,
            )
            chunks = all_chunks[:top_k]

            if not chunks:
                set_span_status("ok")
                return json.dumps({"content": "No relevant documents found.", "sources": []})

            # Format output
            formatted_texts = []
            sources_metadata = []

            for i, chunk in enumerate(chunks):
                text = (
                    chunk.get("text", "")
                    if isinstance(chunk, dict)
                    else getattr(chunk, "text", str(chunk))
                )
                metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
                title = metadata.get("title") or "Document"

                source_col = chunk.get("_source_collection", "unknown")
                doc_id = (
                    metadata.get("chapter_id")
                    or metadata.get("document_id")
                    or metadata.get("id", "")
                )

                if is_whatsapp:
                    # WA L0 minimization happens before reasoning turns this
                    # result into the model observation. No raw URL, file/doc
                    # id, collection/source name, score, or RAG snippet
                    # metadata enters the model context or SSE observation.
                    public_title = _public_wa_title(title)
                    public_text = _minimize_wa_rag_text(text)
                    public_parts = [public_title]
                    if public_text:
                        public_parts.append(public_text)
                    formatted_texts.append("\n".join(public_parts))
                    sources_metadata.append({"title": public_title})
                else:
                    # Include document ID in formatted text if available
                    id_prefix = f"ID: {doc_id}\n" if doc_id else ""
                    formatted_texts.append(
                        f"[{i + 1}] Source: {source_col} | Title: {title}\n{id_prefix}{text}",
                    )

                    sources_metadata.append(
                        {
                            "id": i + 1,
                            "title": title,
                            "url": metadata.get("url", ""),
                            "score": chunk.get("score", 0.0) if isinstance(chunk, dict) else 0.0,
                            "collection": source_col,
                            "doc_id": doc_id,
                            "snippet": text[:500],
                        },
                    )

            content_str = "\n\n".join(formatted_texts)
            set_span_status("ok")
            return json.dumps({"content": content_str, "sources": sources_metadata})


class CalculatorTool(BaseTool):
    """Tool for safe mathematical calculations"""

    @property
    def name(self) -> str:
        """Name."""
        return "calculator"

    @property
    def description(self) -> str:
        """Description."""
        return "Perform mathematical calculations. Use for taxes, fees, currency conversions, or any numerical computation."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression (e.g. '1000 * 0.22' or '15000000 / 15500')",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, expression: str, **kwargs) -> str:
        try:
            from backend.app.utils.safe_math import SafeMathError, safe_evaluate

            try:
                result = safe_evaluate(expression)
            except SafeMathError:
                return "Error: unable to evaluate the mathematical expression."

            # Format nicely
            if isinstance(result, float):
                result = int(result) if result == int(result) else round(result, 2)

            return (
                f"Result: {result:,}" if isinstance(result, (int, float)) else f"Result: {result}"
            )

        except Exception:
            return "Error: unable to evaluate the mathematical expression."


class VisionTool(BaseTool):
    """Tool for visual document analysis"""

    def __init__(self) -> None:
        self.vision_service = VisionRAGService()

    @property
    def name(self) -> str:
        """Name."""
        return "vision_analysis"

    @property
    def description(self) -> str:
        """Description."""
        return "Analyze visual elements in documents (PDFs, images). Extract text, tables, or analyze document structure."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to analyze"},
                "query": {"type": "string", "description": "What to look for in the document"},
            },
            "required": ["file_path", "query"],
        }

    async def execute(self, file_path: str, query: str, **kwargs) -> str:
        try:
            # Security: validate file path to prevent path traversal
            from pathlib import Path

            from backend.app.core.config import settings

            resolved = Path(file_path).resolve()
            allowed_dirs = [Path(d).resolve() for d in settings.get_vision_allowed_dirs]

            # Use is_relative_to for robust path checking (Python 3.9+)
            is_allowed = False
            for allowed_dir in allowed_dirs:
                try:
                    if resolved.is_relative_to(allowed_dir):
                        is_allowed = True
                        break
                except ValueError:
                    continue

            if not is_allowed:
                logger.warning("🛡️ VisionTool path traversal blocked: %s", file_path)
                return (
                    "Error: Access denied. File must be in one of the following directories: "
                    + ", ".join(settings.get_vision_allowed_dirs)
                )

            # Validate file extension
            allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
            if resolved.suffix.lower() not in allowed_extensions:
                logger.warning(f"🛡️ VisionTool invalid extension blocked: {resolved.suffix}")
                return f"Error: File type {resolved.suffix} not supported. Allowed types: {', '.join(allowed_extensions)}"

            doc = await self.vision_service.process_pdf(str(resolved))
            result = await self.vision_service.query_with_vision(query, [doc], include_images=True)
            return f"Analysis result: {result['answer']}"
        except Exception as e:
            logger.error("Vision analysis failed: %s", e)
            return f"Vision analysis error: {e}"


class PricingTool(BaseTool):
    """Tool for official service pricing lookup"""

    def __init__(self, pricing_service=None) -> None:
        self.pricing_service = pricing_service or get_pricing_service()

    @property
    def name(self) -> str:
        """Name."""
        return "get_pricing"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "🚨 MANDATORY for ALL Bali Zero service price questions. "
            "Get OFFICIAL pricing from Bali Zero database (NO AI generation, NO memory). "
            "USE THIS when user asks: 'quanto costa', 'price', 'prezzo', 'costo', 'harga', 'berapa', 'cost', 'pricing'. "
            "Returns EXACT current prices from official pricing database. "
            "NEVER guess prices - ALWAYS call this tool first for price questions."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "enum": ["visa", "kitas", "business_setup", "tax_consulting", "legal", "all"],
                    "description": "Category of service",
                },
                "query": {
                    "type": "string",
                    "description": "Specific service to search for",
                },
            },
            "required": ["service_type"],
        }

    async def execute(self, service_type: str = "all", query: str = None, **kwargs) -> str:
        try:
            if not self.pricing_service.loaded:
                return str(
                    {
                        "error": True,
                        "message": "Pricing service unavailable — prices not loaded",
                        "action": "Redirect client to support: info@balizero.com",
                    }
                )
            if query:
                result = self.pricing_service.search_service(query)
            else:
                result = self.pricing_service.get_pricing(service_type)
            return str(result)
        except Exception as exc:
            logger.error("Pricing lookup failed error_type=%s", type(exc).__name__)
            return str(
                {
                    "error": True,
                    "message": "Pricing lookup could not be completed.",
                    "action": "DO NOT guess prices — redirect to support",
                }
            )


class TeamKnowledgeTool(BaseTool):
    """Tool for team member information lookup"""

    def __init__(self, db_pool=None) -> None:
        self.db_pool = db_pool
        self._team_data = None
        self._data_file = None

    def _get_data_file_path(self) -> Path | None:
        if self._data_file is None:
            import os
            from pathlib import Path

            # Logical paths to check (Local Repo vs Docker Container)
            possible_paths = [
                # 1. Local Development (relative to this file)
                Path(__file__).parent.parent.parent.parent / "data" / "team_members.json",
                # 2. Docker Container (Standard App Path)
                Path("/app/backend/data/team_members.json"),
                # 3. Docker Container (Alternative)
                Path("/app/data/team_members.json"),
                # 4. Fallback: Current Working Directory
                Path(os.getcwd()) / "backend" / "data" / "team_members.json",
                # 5. Monorepo Fallback
                Path(os.getcwd())
                / "apps"
                / "backend-rag"
                / "backend"
                / "data"
                / "team_members.json",
                # 6. Monorepo Root Fallback
                Path(os.getcwd()) / "data" / "team_members.json",
            ]

            for path in possible_paths:
                try:
                    if path.exists():
                        self._data_file = path
                        logger.debug(f"[{self.name}] Found team_members.json at: {path}")
                        break
                except Exception as e:
                    logger.warning(f"[{self.name}] Error checking path {path}: {e}")

            if self._data_file is None:
                logger.error(
                    f"[{self.name}] CRITICAL: team_members.json NOT FOUND in any expected location.",
                )

        return self._data_file

    def _load_team_data(self) -> list[dict[str, Any]]:
        if self._team_data is None:
            data_file = self._get_data_file_path()
            if data_file and data_file.exists():
                with open(data_file) as f:
                    self._team_data = json.load(f)
            else:
                self._team_data = []
        return self._team_data

    @property
    def name(self) -> str:
        """Name."""
        return "team_knowledge"

    @property
    def description(self) -> str:
        """Description."""
        return "Get information about team members, their roles, departments, and contact info."

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["list_all", "search_by_role", "search_by_name", "search_by_email"],
                    "description": "Type of query to perform",
                },
                "search_term": {
                    "type": "string",
                    "description": "Term to search for (name, role, or email)",
                },
            },
            "required": ["query_type"],
        }

    async def execute(self, query_type: str = "list_all", search_term: str = "", **kwargs) -> str:
        try:
            team_data = self._load_team_data()
            if not team_data:
                return json.dumps({"error": "Team data not available"})

            search_term = search_term.lower().strip() if search_term else ""

            if query_type == "list_all":
                return json.dumps(
                    [{"name": m.get("name"), "role": m.get("role")} for m in team_data],
                )

            # Search logic
            matches = [m for m in team_data if search_term in json.dumps(m).lower()]
            return json.dumps({"matches": matches, "count": len(matches)})

        except Exception as e:
            logger.error("Team knowledge lookup failed: %s", e)
            return json.dumps({"error": str(e)})


class ImageGenerationTool(BaseTool):
    """Tool for generating images from text prompts using Pollinations.ai (free)."""

    @property
    def name(self) -> str:
        """Name."""
        return "generate_image"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Generate images from text descriptions. Use this when the user asks to "
            "create, generate, draw, or make an image/picture. Returns a URL to the generated image. "
            "Prompt should be descriptive (e.g., 'a blue lotus flower in digital art style')."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed text description of the image to generate",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
                    "description": "Aspect ratio of the image (default: 1:1)",
                },
            },
            "required": ["prompt"],
        }

    async def execute(self, prompt: str, aspect_ratio: str = "1:1", **kwargs) -> str:
        """Generate an image using Pollinations.ai (free, no API key)."""
        from urllib.parse import quote

        with trace_span("tool.generate_image", {"prompt_length": len(prompt)}):
            try:
                aspect_params = {
                    "1:1": "width=1024&height=1024",
                    "16:9": "width=1024&height=576",
                    "9:16": "width=576&height=1024",
                    "4:3": "width=1024&height=768",
                    "3:4": "width=768&height=1024",
                }
                params = aspect_params.get(aspect_ratio, "width=1024&height=1024")
                image_url = (
                    f"https://image.pollinations.ai/prompt/{quote(prompt)}?{params}&nologo=true"
                )

                logger.info(f"[ImageGen] Generating image: {prompt[:50]}...")
                set_span_attribute("success", True)

                return json.dumps(
                    {
                        "success": True,
                        "image_url": image_url,
                        "service": "pollinations",
                        "message": f"Generated image for: {prompt}",
                    },
                )

            except Exception as e:
                logger.error("[ImageGen] Failed: %s", e)
                set_span_status("error", str(e))
                return json.dumps(
                    {"success": False, "error": f"Image generation failed: {e}"},
                )


class WebSearchTool(BaseTool):
    """
    Tool for searching the web when information is not available in the knowledge base.

    Supports two providers:
    - Tavily (preferred): AI-optimized search with 1,000 free queries/month
    - Brave (fallback): Independent search index with 2,000 free queries/month

    Use this tool ONLY when:
    1. The user asks about topics outside Bali Zero's core services (tourism, lifestyle, general info)
    2. The vector_search tool returns no relevant results
    3. The user explicitly asks for current/latest information from the web

    IMPORTANT: Results from this tool are NOT verified by Bali Zero's knowledge base.
    Always include the disclaimer when presenting web search results to users.
    """

    # Standard disclaimer for web results - append to all responses
    WEB_DISCLAIMER = (
        "\n\n---\n"
        "*Note: This information was sourced from the web and has not been verified "
        "by Bali Zero's official knowledge base. For visa, legal, tax, or business setup "
        "questions, please refer to our verified documentation or contact our team directly.*"
    )

    def __init__(self) -> None:
        self._tavily_key = None
        self._brave_key = None

    def _get_keys(self) -> tuple[str | None, str | None]:
        """Lazy load API keys from settings."""
        if self._tavily_key is None and self._brave_key is None:
            from backend.app.core.config import settings

            self._tavily_key = settings.tavily_api_key
            self._brave_key = settings.brave_api_key
        return self._tavily_key, self._brave_key

    @property
    def name(self) -> str:
        """Name."""
        return "web_search"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Search the web for information NOT available in the knowledge base.\n\n"
            "**USE CASES:**\n"
            "1. Tourism, restaurants, lifestyle, current events, general knowledge\n"
            "2. **LOCAL CONTEXT ENRICHMENT**: When user asks about opening a business in a specific "
            "location (e.g., 'restaurant in Canggu', 'hotel in Dago'), use this to find "
            "local competitors, market atmosphere, and scene description. This helps clients "
            "'breathe the atmosphere' of the area.\n\n"
            "**DO NOT use for:** visas, KITAS, PT PMA, taxes, legal - use vector_search instead.\n"
            "Web results are NOT verified and will include a disclaimer."
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query in natural language"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 10)",
                },
            },
            "required": ["query"],
        }

    async def _search_tavily(self, query: str, num_results: int, api_key: str) -> dict[str, Any]:
        """Search using Tavily API (AI-optimized)."""
        url = "https://api.tavily.com/search"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": num_results,
            "search_depth": "basic",
            "include_answer": True,
        }

        client = _get_client()
        response = await client.post(url, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def _search_brave(self, query: str, num_results: int, api_key: str) -> dict[str, Any]:
        """Search using Brave Search API (fallback)."""
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        params = {
            "q": query,
            "count": num_results,
            "text_decorations": False,
            "search_lang": "en",
        }

        client = _get_client()
        response = await client.get(url, headers=headers, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> str:
        """
        Execute web search using Tavily (primary) or Brave (fallback).

        Returns formatted results with source URLs and the standard disclaimer.
        """
        import httpx

        with trace_span(
            "tool.web_search",
            {
                "query_length": len(query),
                "num_results": num_results,
            },
        ):
            tavily_key, brave_key = self._get_keys()

            if not tavily_key and not brave_key:
                logger.warning(
                    "⚠️ [WebSearch] No API keys configured (TAVILY_API_KEY or BRAVE_API_KEY)",
                )
                return json.dumps(
                    {
                        "success": False,
                        "error": "Web search not configured. Please contact support.",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )

            # Clamp num_results
            num_results = min(max(1, int(num_results) if num_results else 5), 10)

            try:
                provider = None
                results = []
                ai_answer = None

                # Try Tavily first (AI-optimized)
                if tavily_key:
                    try:
                        logger.info(f"🌐 [WebSearch] Searching Tavily: {query[:50]}...")
                        data = await self._search_tavily(query, num_results, tavily_key)
                        provider = "tavily"
                        results = data.get("results", [])
                        ai_answer = data.get("answer")  # Tavily provides AI-generated answer
                    except Exception as e:
                        logger.warning("⚠️ [WebSearch] Tavily failed: %s, trying Brave...", e)

                # Fallback to Brave
                if not results and brave_key:
                    try:
                        logger.info(f"🌐 [WebSearch] Searching Brave: {query[:50]}...")
                        data = await self._search_brave(query, num_results, brave_key)
                        provider = "brave"
                        results = data.get("web", {}).get("results", [])
                    except Exception as e:
                        logger.error("❌ [WebSearch] Brave also failed: %s", e)
                        raise

                if not results:
                    set_span_status("ok")
                    return json.dumps(
                        {
                            "success": True,
                            "content": "No relevant web results found for this query.",
                            "sources": [],
                            "disclaimer": self.WEB_DISCLAIMER,
                        },
                    )

                # Format results based on provider
                formatted_results = []
                sources = []

                # Add AI answer if available (Tavily)
                if ai_answer:
                    formatted_results.append(f"**Summary:** {ai_answer}\n")

                for i, result in enumerate(results[:num_results]):
                    if provider == "tavily":
                        title = result.get("title", "Untitled")
                        content = result.get("content", "No content available")
                        url = result.get("url", "")
                    else:  # brave
                        title = result.get("title", "Untitled")
                        content = result.get("description", "No description available")
                        content = content.replace("<strong>", "").replace("</strong>", "")
                        url = result.get("url", "")

                    formatted_results.append(
                        f"[{i + 1}] **{title}**\n   {content[:300]}...\n   Source: {url}",
                    )

                    sources.append(
                        {
                            "id": i + 1,
                            "title": title,
                            "url": url,
                            "content": content[:200],
                            "verified": False,
                        },
                    )

                content = "\n\n".join(formatted_results)
                content_with_disclaimer = content + self.WEB_DISCLAIMER

                logger.info(f"✅ [WebSearch] Found {len(sources)} results via {provider}")
                set_span_status("ok")

                return json.dumps(
                    {
                        "success": True,
                        "content": content_with_disclaimer,
                        "sources": sources,
                        "source_type": "web_search",
                        "provider": provider,
                        "disclaimer": self.WEB_DISCLAIMER,
                        "query": query,
                    },
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"❌ [WebSearch] HTTP error: {e.response.status_code}")
                set_span_status("error", str(e))
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Web search failed: HTTP {e.response.status_code}",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )
            except Exception as e:
                logger.error("❌ [WebSearch] Error: %s", e)
                set_span_status("error", str(e))
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Web search error: {e!s}",
                        "disclaimer": self.WEB_DISCLAIMER,
                    },
                )


class TimeSheetTool(BaseTool):
    """Tool for team timesheet management (clock-in, clock-out, status)"""

    def __init__(self) -> None:
        self._team_data = None

    @property
    def name(self) -> str:
        """Name."""
        return "timesheet"

    @property
    def description(self) -> str:
        """Description."""
        return (
            "Manage work timesheet. Use this to clock in, clock out, or check work status. "
            "REQUIRED: User email address."
            "Actions: clock_in, clock_out, status"
        )

    @property
    def parameters_schema(self) -> dict:
        """Parameters schema."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["clock_in", "clock_out", "status"],
                    "description": "Action to perform",
                },
                "email": {
                    "type": "string",
                    "description": "User email address (required)",
                },
            },
            "required": ["action", "email"],
        }

    def _get_user_id_by_email(self, email: str) -> str | None:
        try:
            from pathlib import Path

            # Try relative to this file first (Local Dev)
            path = Path(__file__).parent.parent.parent.parent / "data" / "team_members.json"

            # If not found, try Docker paths
            if not path.exists():
                path = Path("/app/backend/data/team_members.json")

            if not path.exists():
                path = Path("/app/data/team_members.json")

            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                    for m in data:
                        if m.get("email", "").lower() == email.lower():
                            return m.get("id")
        except Exception as e:
            logger.debug("[TimeSheetTool] Failed to lookup user by email %s: %s", email, e)
        return None

    async def execute(self, action: str, email: str, **kwargs) -> str:
        try:
            from backend.services.analytics.team_timesheet_service import get_timesheet_service

            service = get_timesheet_service()
            if not service:
                return json.dumps({"error": "Timesheet service unavailable"})

            user_id = self._get_user_id_by_email(email)
            if not user_id:
                return json.dumps({"error": f"User ID not found for email {email}"})

            if action == "clock_in":
                res = await service.clock_in(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            if action == "clock_out":
                res = await service.clock_out(user_id, email, metadata={"source": "agent"})
                return json.dumps(res)
            if action == "status":
                res = await service.get_my_status(user_id)
                return json.dumps(res)
            return json.dumps({"error": f"Unknown action {action}"})

        except Exception as e:
            return json.dumps({"error": str(e)})


# W0 safety pre-arm (S1, 2026-07-25): defensive bounds for the LLM-supplied
# `limit`/`days_ahead` kwargs CRMTool.execute() feeds straight into `LIMIT $N`
# SQL. An LLM can be induced (or can simply hallucinate) into requesting an
# unbounded row count — mirrors the identical pattern already hardened in
# team_crm_tools.py's `_clamp_limit`/`_clamp_days` (same constants shape,
# kept as separate module-local functions here since CRMTool predates and is
# broader-scoped than the WA team-assistant tools).
_CRM_DEFAULT_LIMIT = 20
_CRM_MAX_LIMIT = 50
_CRM_DEFAULT_DAYS_AHEAD = 30
_CRM_MAX_DAYS_AHEAD = 365


def _clamp_crm_limit(limit: Any) -> int:
    """Coerce+clamp a caller-supplied `limit` to [1, _CRM_MAX_LIMIT].

    Non-numeric / missing input degrades to the documented default (20)
    rather than raising — an LLM can pass a string, None, or a list instead
    of an int, and CRMTool.execute() must never crash on that.
    """
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return _CRM_DEFAULT_LIMIT
    return max(1, min(n, _CRM_MAX_LIMIT))


def _clamp_crm_days_ahead(days_ahead: Any) -> int:
    """Coerce+clamp a caller-supplied `days_ahead` to [1, _CRM_MAX_DAYS_AHEAD].

    Same non-numeric fallback contract as `_clamp_crm_limit`.
    """
    try:
        n = int(days_ahead)
    except (TypeError, ValueError):
        return _CRM_DEFAULT_DAYS_AHEAD
    return max(1, min(n, _CRM_MAX_DAYS_AHEAD))


class CRMTool(BaseTool):
    """Tool for querying the CRM database — client counts, search, practice status."""

    def __init__(self, db_pool=None) -> None:
        self.db_pool = db_pool

    @property
    def name(self) -> str:
        return "crm_query"

    @property
    def description(self) -> str:
        return (
            "REQUIRED for ANY question about clients, practices, or business data. "
            "Queries the LIVE CRM database (PostgreSQL) and returns real numbers.\n\n"
            "ALWAYS use this tool FIRST when the user asks:\n"
            "- 'How many clients?' → use query_type='client_stats'\n"
            "- 'Find client X' → use query_type='search_clients'\n"
            "- 'Expiring visas/KITAS' → use query_type='expiring_documents'\n"
            "- 'Breakdown by service' → use query_type='practice_stats'\n"
            "- 'Recent/new clients' → use query_type='recent_clients'\n\n"
            "This is the ONLY tool that can give real client counts and practice data. "
            "Do NOT answer client questions without calling this tool first."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "client_stats",
                        "search_clients",
                        "expiring_documents",
                        "practice_stats",
                        "recent_clients",
                    ],
                    "description": "Type of CRM query to run.",
                },
                "search_term": {
                    "type": "string",
                    "description": "Search term for client name, email, or passport (used with search_clients).",
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Number of days ahead to check for expirations (default 30).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 20).",
                },
            },
            "required": ["query_type"],
        }

    async def execute(
        self,
        query_type: str = "client_stats",
        search_term: str = "",
        days_ahead: int = 30,
        limit: int = 20,
        **kwargs,
    ) -> str:
        if not self.db_pool:
            return json.dumps({"error": "CRM database not available"})

        # W0 S1: clamp BEFORE any branch below builds a query — every
        # branch that feeds `limit` into `LIMIT $N` (search_clients,
        # expiring_documents, practice_stats, recent_clients) shares this
        # single clamped value, so a fix here covers the whole class in one
        # place instead of one call site at a time.
        limit = _clamp_crm_limit(limit)
        days_ahead = _clamp_crm_days_ahead(days_ahead)

        try:
            async with self.db_pool.acquire() as conn:
                if query_type == "client_stats":
                    row = await conn.fetchrow("""
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'active') AS active_clients,
                            COUNT(*) FILTER (WHERE status = 'lead') AS leads,
                            COUNT(*) FILTER (WHERE status = 'inactive') AS inactive,
                            COUNT(*) AS total
                        FROM clients
                    """)
                    practice_row = await conn.fetchrow("""
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'on_process') AS on_process,
                            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                            COUNT(*) FILTER (WHERE status = 'sending_invoice') AS sending_invoice,
                            COUNT(*) FILTER (WHERE status = 'waiting_documents') AS waiting_documents,
                            COUNT(*) FILTER (WHERE status = 'inquiry') AS inquiry,
                            COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                            COUNT(*) AS total
                        FROM practices
                    """)
                    return json.dumps(
                        {
                            "clients": dict(row) if row else {},
                            "practices": dict(practice_row) if practice_row else {},
                        },
                        default=str,
                    )

                elif query_type == "search_clients":
                    if not search_term:
                        return json.dumps({"error": "search_term required"})
                    rows = await conn.fetch(
                        """
                        SELECT id, full_name, email, nationality, status, phone
                        FROM clients
                        WHERE full_name ILIKE $1 OR email ILIKE $1 OR passport_number ILIKE $1
                        ORDER BY updated_at DESC
                        LIMIT $2
                    """,
                        f"%{search_term}%",
                        limit,
                    )
                    return json.dumps([dict(r) for r in rows], default=str)

                elif query_type == "expiring_documents":
                    rows = await conn.fetch(
                        """
                        SELECT c.full_name, c.email, c.nationality,
                               p.practice_type_id, p.status, p.notes,
                               p.updated_at
                        FROM practices p
                        JOIN clients c ON c.id = p.client_id
                        WHERE p.status IN ('on_process', 'waiting_documents', 'sending_invoice')
                          AND p.practice_type_id IN (
                              SELECT id FROM practice_types
                              WHERE name ILIKE '%kitas%' OR name ILIKE '%visa%' OR name ILIKE '%kitap%'
                          )
                        ORDER BY p.updated_at DESC
                        LIMIT $1
                    """,
                        limit,
                    )
                    return json.dumps([dict(r) for r in rows], default=str)

                elif query_type == "practice_stats":
                    rows = await conn.fetch(
                        """
                        SELECT
                            COALESCE(pt.name, 'Unknown') AS service_type,
                            COUNT(*) AS count,
                            COUNT(*) FILTER (WHERE p.status = 'on_process') AS on_process,
                            COUNT(*) FILTER (WHERE p.status = 'completed') AS completed
                        FROM practices p
                        LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                        GROUP BY pt.name
                        ORDER BY count DESC
                        LIMIT $1
                    """,
                        limit,
                    )
                    return json.dumps([dict(r) for r in rows], default=str)

                elif query_type == "recent_clients":
                    rows = await conn.fetch(
                        """
                        SELECT id, full_name, email, nationality, status, created_at
                        FROM clients
                        WHERE status = 'active'
                        ORDER BY created_at DESC
                        LIMIT $1
                    """,
                        limit,
                    )
                    return json.dumps([dict(r) for r in rows], default=str)

                else:
                    return json.dumps({"error": f"Unknown query_type: {query_type}"})

        except Exception as e:
            logger.error("[CRMTool] Query failed: %s", e)
            return json.dumps({"error": f"CRM query failed: {e!s}"})


def create_default_tools(search_service: Any = None) -> list[BaseTool]:
    """
    Create default tool set for AgenticRAGOrchestrator.

    This is used as a fallback when creating a minimal orchestrator
    for channel routing when the main orchestrator is not initialized.

    Args:
        search_service: Optional SearchService instance for VectorSearchTool

    Returns:
        List of BaseTool instances with essential tools
    """
    tools = []

    # 1. VectorSearchTool (if search_service available)
    if search_service:
        tools.append(VectorSearchTool(retriever=search_service))

    # 2. PricingTool (essential for pricing queries)
    pricing_service = get_pricing_service()
    tools.append(PricingTool(pricing_service=pricing_service))

    # 3. CalculatorTool (always available)
    tools.append(CalculatorTool())

    # 4. TeamKnowledgeTool (always available)
    tools.append(TeamKnowledgeTool())

    logger.info(f"Created {len(tools)} default tools for orchestrator")
    return tools
