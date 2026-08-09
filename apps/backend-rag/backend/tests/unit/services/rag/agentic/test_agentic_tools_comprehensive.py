"""
Unit tests for Agentic RAG Tools
Target: 100% coverage
Composer: 1
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.agentic.tools import (
    CalculatorTool,
    PricingTool,
    TeamKnowledgeTool,
    VectorSearchTool,
    VisionTool,
    _minimize_wa_rag_text,
)


def _metadata_label_variants(
    family: str,
    words: tuple[str, ...],
) -> list[object]:
    """Generate case/separator variants for one metadata-label family."""
    candidates = (
        ("space-lower", " ".join(words)),
        ("space-upper", " ".join(words).upper()),
        ("space-title", " ".join(word.title() for word in words)),
        ("snake-lower", "_".join(words)),
        ("snake-upper", "_".join(words).upper()),
        ("snake-title", "_".join(word.title() for word in words)),
        ("kebab-lower", "-".join(words)),
        ("kebab-upper", "-".join(words).upper()),
        ("kebab-title", "-".join(word.title() for word in words)),
        ("compact-lower", "".join(words)),
        ("compact-upper", "".join(words).upper()),
        ("camel", words[0] + "".join(word.title() for word in words[1:])),
        ("pascal", "".join(word.title() for word in words)),
    )
    seen: set[str] = set()
    variants: list[object] = []
    for style, label in candidates:
        if label in seen:
            continue
        seen.add(label)
        variants.append(pytest.param(label, id=f"{family}-{style}"))
    return variants


_WA_METADATA_LABEL_CASES = [
    variant
    for family, words in (
        ("doc-id", ("doc", "id")),
        ("document-id", ("document", "id")),
        ("file-id", ("file", "id")),
        ("drive-file-id", ("drive", "file", "id")),
        ("google-drive-file-id", ("google", "drive", "file", "id")),
        ("drive-url", ("drive", "url")),
        ("google-drive-url", ("google", "drive", "url")),
        ("source-metadata", ("source", "metadata")),
        ("source-metadata-inline", ("source", "metadata", "inline")),
        ("source-url", ("source", "url")),
        ("collection", ("collection",)),
        ("url", ("url",)),
        ("metadata", ("metadata",)),
        ("internal-metadata", ("internal", "metadata")),
        ("internal-source", ("internal", "source")),
        ("internal-copy", ("internal", "copy")),
    )
    for variant in _metadata_label_variants(family, words)
]


def _round4_metadata_label_variants(words: tuple[str, ...]) -> tuple[str, ...]:
    """Return the verifier's five independent separator/case label shapes."""
    if len(words) == 1:
        word = words[0]
        alternating_lower = "".join(
            char.upper() if index % 2 else char.lower() for index, char in enumerate(word)
        )
        alternating_upper = "".join(
            char.lower() if index % 2 else char.upper() for index, char in enumerate(word)
        )
        return word, word.upper(), word.title(), alternating_lower, alternating_upper

    title_words = tuple(word.upper() if word in {"id", "url"} else word.title() for word in words)
    return (
        "_".join(words),
        "".join(title_words),
        "-".join(words),
        words[0] + "".join(title_words[1:]),
        " ".join(word.upper() for word in words),
    )


_ROUND4_METADATA_LABEL_FAMILIES = (
    ("document", "id"),
    ("doc", "id"),
    ("file", "id"),
    ("drive", "id"),
    ("google", "drive", "id"),
    ("google", "drive", "file", "id"),
    ("source", "metadata"),
    ("source", "metadata", "inline"),
    ("source", "url"),
    ("collection",),
    ("metadata",),
    ("source",),
    ("internal", "copy"),
)
_ROUND4_METADATA_LABELS = tuple(
    label
    for words in _ROUND4_METADATA_LABEL_FAMILIES
    for label in _round4_metadata_label_variants(words)
)
_ROUND4_METADATA_DELIMITERS = (
    ":",
    " : ",
    "=",
    " = ",
    "-",
    " - ",
    " -> ",
    "->",
    " ",
)
_ROUND4_METADATA_MATRIX = tuple(
    pytest.param(
        label,
        delimiter,
        id=f"label-{label_index:02d}-separator-{delimiter_index:02d}",
    )
    for label_index, label in enumerate(_ROUND4_METADATA_LABELS)
    for delimiter_index, delimiter in enumerate(_ROUND4_METADATA_DELIMITERS)
)


def test_round4_metadata_matrix_is_independent_and_complete():
    """Pin the verifier-sized grammar rather than coupling to production constants."""
    assert len(_ROUND4_METADATA_LABELS) == 65
    assert len(_ROUND4_METADATA_DELIMITERS) == 9
    assert len(_ROUND4_METADATA_MATRIX) == 65 * 9


@pytest.mark.parametrize(("metadata_label", "delimiter"), _ROUND4_METADATA_MATRIX)
def test_wa_sanitizer_strips_full_label_delimiter_position_matrix(
    metadata_label,
    delimiter,
):
    """Every metadata delimiter is removed at line and structural-segment starts."""
    line_value = "private_value_line_42"
    pipe_value = "private_value_pipe_43"
    semicolon_value = "private_value_semicolon_44"
    chained_value = "private_value_chained_45"
    raw_text = (
        f"{metadata_label}{delimiter}{line_value}\n"
        f"Public prefix | {metadata_label}{delimiter}{pipe_value} | Public suffix\n"
        f"Public semicolon; {metadata_label}{delimiter}{semicolon_value}; Public tail\n"
        f"Multi prefix | {metadata_label}{delimiter}{pipe_value} | "
        f"{metadata_label}{delimiter}{chained_value} | Multi suffix\n"
        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku."
    )

    minimized = _minimize_wa_rag_text(raw_text)

    for public_text in (
        "Public prefix",
        "Public suffix",
        "Public semicolon",
        "Public tail",
        "Multi prefix",
        "Multi suffix",
        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.",
    ):
        assert public_text in minimized
    assert metadata_label not in minimized
    assert line_value not in minimized
    assert pipe_value not in minimized
    assert semicolon_value not in minimized
    assert chained_value not in minimized


def test_wa_sanitizer_preserves_non_label_public_phrases_and_legal_citations():
    """Metadata words in ordinary public prose are not structural labels."""
    public_lines = (
        "This public source document explains the filing process.",
        "The document remains available from the issuing authority.",
        "An internal review does not change the published requirement.",
        "This collection of public rules explains source URL requirements.",
        "Public source-based guidance remains useful.",
        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.",
    )

    minimized = _minimize_wa_rag_text("\n".join(public_lines))

    for public_line in public_lines:
        assert public_line in minimized


_ROUND5_DECORATED_LABELS = (
    "file_id",
    "Document ID",
    "Source",
    "source_metadata",
    "Google Drive",
    "Drive File",
    "collection",
)
_ROUND5_DECORATED_DELIMITERS = (": ", " = ", " - ", " -> ", " ")
_ROUND5_WRAPPER_TEMPLATES = (
    pytest.param("{label}{delimiter}", id="plain"),
    pytest.param("`{label}`{delimiter}", id="backtick"),
    pytest.param("[{label}]{delimiter}", id="bracket"),
    pytest.param("**{label}**{delimiter}", id="bold"),
    pytest.param("*{label}*{delimiter}", id="italic"),
    pytest.param("- **{label}**{delimiter}", id="bullet-bold"),
    pytest.param("> `{label}`{delimiter}", id="blockquote-code"),
    pytest.param("### {label}{delimiter}", id="heading"),
    pytest.param("**{label}{delimiter}**", id="delimiter-inside-bold"),
    pytest.param("`{label}{delimiter}`", id="delimiter-inside-code"),
    pytest.param("<strong>{label}</strong>{delimiter}", id="html-strong"),
    pytest.param("<code>{label}{delimiter}</code>", id="html-code-delimiter-inside"),
)


def test_round5_decorated_metadata_matrix_dimensions() -> None:
    """Pin the independent label, delimiter, and wrapper dimensions."""
    assert len(_ROUND5_DECORATED_LABELS) == 7
    assert len(_ROUND5_DECORATED_DELIMITERS) == 5
    assert len(_ROUND5_WRAPPER_TEMPLATES) == 12
    assert (
        len(_ROUND5_DECORATED_LABELS)
        * len(_ROUND5_DECORATED_DELIMITERS)
        * len(_ROUND5_WRAPPER_TEMPLATES)
        == 420
    )


@pytest.mark.parametrize("wrapper_template", _ROUND5_WRAPPER_TEMPLATES)
@pytest.mark.parametrize("metadata_label", _ROUND5_DECORATED_LABELS)
@pytest.mark.parametrize("delimiter", _ROUND5_DECORATED_DELIMITERS)
def test_wa_sanitizer_canonicalizes_decorated_structural_metadata_matrix(
    wrapper_template: str,
    metadata_label: str,
    delimiter: str,
) -> None:
    """Decorated labels are exact-canonicalized at every structural position."""
    marker = wrapper_template.format(label=metadata_label, delimiter=delimiter)
    line_value = "private_round5_line_value"
    pipe_value = "private_round5_pipe_value"
    semicolon_value = "private_round5_semicolon_value"
    chained_value = "private_round5_chained_value"
    raw_text = (
        f"{marker}{line_value}\n"
        f"Public prefix | {marker}{pipe_value} | Public suffix\n"
        f"Public semicolon; {marker}{semicolon_value}; Public tail\n"
        f"Multi prefix | {marker}{pipe_value} | {marker}{chained_value} | Multi suffix\n"
        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku."
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "\n".join(
        (
            "Public prefix Public suffix",
            "Public semicolon Public tail",
            "Multi prefix Multi suffix",
            "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.",
        )
    )
    for private_value in (line_value, pipe_value, semicolon_value, chained_value):
        assert private_value not in minimized


def test_wa_sanitizer_strips_round5_reported_bypasses_without_wrapper_residue() -> None:
    """Pin the reported decorated labels without coupling the fix to secret values."""
    raw_text = (
        "`file_id`: private_code_file_value\n"
        "[Document ID]: private_bracket_doc_value\n"
        "[Source]: private_bracket_source_value\n"
        "- **source_metadata**: private_bullet_bold_value\n"
        "Google Drive: private_google_drive_value\n"
        "Drive File: private_drive_file_value\n"
        "**Document ID:** private_bold_delimiter_value\n"
        "Public regulation guidance remains available."
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "Public regulation guidance remains available."


def test_wa_sanitizer_preserves_public_markdown_html_and_legal_prose() -> None:
    """Formatting is retained when its canonical candidate is not a metadata label."""
    public_lines = (
        "**Important:** File the public document before the deadline.",
        "- The source document is a published legal reference.",
        "> The internal review note does not replace the regulation.",
        "### Public collection notes",
        "The public field named `document_id` is explained here.",
        "[Document 1] describes the public filing rule.",
        "<strong>Public document guidance</strong> remains authoritative.",
        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.",
    )

    minimized = _minimize_wa_rag_text("\n".join(public_lines))

    assert minimized == "\n".join(public_lines)


_ROUND6_STRUCTURAL_CELL_LABELS = (
    pytest.param("Document ID", id="document-space"),
    pytest.param("document_id", id="document-snake"),
    pytest.param("**Source**", id="source-bold"),
    pytest.param("`source_metadata`", id="source-metadata-code"),
    pytest.param("[Collection]", id="collection-bracket"),
    pytest.param("Google Drive", id="google-drive"),
    pytest.param("Drive File", id="drive-file"),
)


@pytest.mark.parametrize("metadata_label", _ROUND6_STRUCTURAL_CELL_LABELS)
def test_wa_sanitizer_strips_round6_table_cell_and_br_matrix(
    metadata_label: str,
) -> None:
    """A canonical label owns the next table cell or explicit HTML break value."""
    raw_text = "\n".join(
        (
            f"| {metadata_label} | private_markdown_cell_value |",
            (f"<table><tr><th>{metadata_label}</th><td>private_html_cell_value</td></tr></table>"),
            f"<b>{metadata_label}</b><br>private_html_break_value",
        )
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == ""


def test_wa_sanitizer_strips_round6_reported_table_and_break_bypasses() -> None:
    """Pin the reported table and HTML-break shapes without value-specific logic."""
    raw_text = "\n".join(
        (
            "| Document ID | MD_TABLE_SECRET |",
            "| Source | MD_SOURCE_SECRET | Collection | MD_COLLECTION_SECRET |",
            ("<table><tr><th>Document ID</th><td>HTML_TABLE_SECRET</td></tr></table>"),
            "<b>Collection</b><br>HTML_BR_SECRET",
        )
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == ""


def test_wa_sanitizer_removes_multiple_markdown_pairs_and_keeps_public_cells() -> None:
    """Metadata cell/value pairs disappear without flattening public table cells."""
    raw_text = (
        "| Public rule | Source | private_source_cell | "
        "Collection | private_collection_cell | Public note |"
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "| Public rule | Public note |"


def test_wa_sanitizer_removes_html_pairs_rows_and_keeps_public_cells() -> None:
    """Simple HTML tables retain public cells and drop metadata-only rows."""
    raw_text = (
        "<table>"
        "<tr><td>Public rule</td><th>Source</th><td>private_source_cell</td>"
        "<td>Public note</td></tr>"
        "<tr><th>Document ID</th><td>private_document_cell</td>"
        "<th>Collection</th><td>private_collection_cell</td></tr>"
        "</table>"
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == ("<table><tr><td>Public rule</td><td>Public note</td></tr></table>")


def test_wa_sanitizer_preserves_round6_public_headings_prose_and_tables() -> None:
    """Generic metadata words remain public when they are ordinary legal prose."""
    public_lines = (
        "## Collection of Indonesian public laws",
        "## Collection International regulatory guidance",
        "**Source of law:** Undang-Undang Nomor 12 Tahun 2011.",
        "## Source documents for public company filings",
        "Source-based guidance remains public.",
        "Collection-wide reporting rules remain public.",
        "| Public topic | Published law |",
        "| --- | --- |",
        "| Collection of Indonesian public laws | Source of law |",
        (
            "<table><tr><th>Public topic</th><th>Published law</th></tr>"
            "<tr><td>Source of law</td><td>Undang-Undang 12/2011</td></tr></table>"
        ),
    )

    minimized = _minimize_wa_rag_text("\n".join(public_lines))

    assert minimized == "\n".join(public_lines)


def test_wa_sanitizer_keeps_explicit_and_technical_whitespace_metadata_blocked() -> None:
    """The prose guard does not reopen explicit or identifier-shaped metadata leaks."""
    raw_text = "\n".join(
        (
            "Source: private human-readable source description",
            "Source - private human-readable source description",
            "Source SOURCE_SPACE_CANARY",
            "Collection COLLECTION_SPACE_CANARY",
            "Document ID DOCUMENT_SPACE_CANARY",
            "Public legal guidance remains available.",
        )
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "Public legal guidance remains available."


def test_wa_sanitizer_removes_private_markdown_columns_across_table_rows() -> None:
    """Canonical metadata headers own their columns in alignment and data rows."""
    raw_text = "\n".join(
        (
            "| Public title | Document ID | Source | Public citation |",
            "| :--- | ---: | :---: | --- |",
            "| UU 6/2023 | private_doc_row_one | private_source_row_one | Pasal 12 [3] |",
            "| PP 5/2021 | private_doc_row_two | private_source_row_two | Pasal 7 |",
        )
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "\n".join(
        (
            "| Public title | Public citation |",
            "| :--- | --- |",
            "| UU 6/2023 | Pasal 12 [3] |",
            "| PP 5/2021 | Pasal 7 |",
        )
    )
    assert "private_" not in minimized


def test_wa_sanitizer_drops_all_private_markdown_column_table() -> None:
    """A metadata-only Markdown table cannot leave orphan alignment or values."""
    raw_text = "\n".join(
        (
            "Public guidance before the table.",
            "| Document ID | source_metadata |",
            "| --- | --- |",
            "| private_doc_row_one | private_source_row_one |",
            "| private_doc_row_two | private_source_row_two |",
            "Public guidance after the table.",
        )
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "\n".join(
        ("Public guidance before the table.", "Public guidance after the table.")
    )


def test_wa_sanitizer_removes_private_html_columns_across_table_rows() -> None:
    """Simple HTML th headers own the corresponding cells in every data row."""
    raw_text = (
        "<table><thead><tr><th>Public title</th><th>Document ID</th>"
        "<th>Source</th><th>Public citation</th></tr></thead>"
        "<tbody><tr><td>UU 6/2023</td><td>private_doc_row_one</td>"
        "<td>private_source_row_one</td><td>Pasal 12 [3]</td></tr>"
        "<tr><td>PP 5/2021</td><td>private_doc_row_two</td>"
        "<td>private_source_row_two</td><td>Pasal 7</td></tr></tbody></table>"
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == (
        "<table><thead><tr><th>Public title</th><th>Public citation</th></tr></thead>"
        "<tbody><tr><td>UU 6/2023</td><td>Pasal 12 [3]</td></tr>"
        "<tr><td>PP 5/2021</td><td>Pasal 7</td></tr></tbody></table>"
    )
    assert "private_" not in minimized


def test_wa_sanitizer_drops_all_private_html_column_table() -> None:
    """A simple HTML table with only metadata-owned columns is removed."""
    raw_text = (
        "Public guidance before."
        "<table><tr><th>Document ID</th><th>Collection</th></tr>"
        "<tr><td>private_doc_row</td><td>private_collection_row</td></tr></table>"
        "Public guidance after."
    )

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == "Public guidance before.Public guidance after."


def test_wa_sanitizer_preserves_public_only_multiline_tables_exactly() -> None:
    """Column ownership is inactive when no canonical metadata header exists."""
    public_markdown = "\n".join(
        (
            "| Public title | Public citation |",
            "| :--- | ---: |",
            "| UU 6/2023 | Pasal 12 [3] |",
            "| PP 5/2021 | Pasal 7 |",
        )
    )
    public_html = (
        "<table><thead><tr><th>Public title</th><th>Published law</th></tr></thead>"
        "<tbody><tr><td>Source of law</td><td>Undang-Undang 12/2011</td></tr>"
        "<tr><td>Collection of laws</td><td>PP 5/2021</td></tr></tbody></table>"
    )
    raw_text = f"{public_markdown}\n{public_html}"

    minimized = _minimize_wa_rag_text(raw_text)

    assert minimized == raw_text


@pytest.fixture(autouse=True)
def patch_tools_deps():
    """Patch trace_span (no-op) and disable hybrid search to isolate VectorSearchTool tests."""
    mock_span = MagicMock()
    mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_span.return_value.__exit__ = MagicMock(return_value=False)
    mock_settings = MagicMock()
    mock_settings.enable_hybrid_search = False
    with (
        patch("backend.services.rag.agentic.tools.trace_span", mock_span),
        patch("backend.app.core.config.settings", mock_settings),
    ):
        yield


@pytest.fixture
def mock_retriever():
    """Mock retriever"""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value={"results": []})
    retriever.search_with_reranking = AsyncMock(return_value={"results": []})
    return retriever


@pytest.fixture
def mock_pricing_service():
    """Mock pricing service"""
    service = MagicMock()
    # get_pricing is not async, it's a regular method
    service.get_pricing = MagicMock(return_value={"items": []})
    service.search_service = MagicMock(return_value={"items": []})
    return service


@pytest.fixture
def mock_team_service():
    """Mock team service"""
    service = MagicMock()
    service.search_member = AsyncMock(return_value=[])
    service.list_members = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_vision_service():
    """Mock vision service"""
    service = AsyncMock()
    service.analyze_image = AsyncMock(return_value={"analysis": "test"})
    return service


class TestVectorSearchTool:
    """Tests for VectorSearchTool"""

    def test_init(self, mock_retriever):
        """Test initialization"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert tool.retriever == mock_retriever

    def test_name(self, mock_retriever):
        """Test tool name"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert tool.name == "vector_search"

    def test_description(self, mock_retriever):
        """Test tool description"""
        tool = VectorSearchTool(retriever=mock_retriever)
        assert "knowledge base" in tool.description.lower()

    def test_parameters_schema(self, mock_retriever):
        """Test parameters schema"""
        tool = VectorSearchTool(retriever=mock_retriever)
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "collection" in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_with_collection(self, mock_retriever):
        """Test execute with specific collection"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [{"text": "test", "score": 0.9, "metadata": {"title": "Test"}}],
        }

        result = await tool.execute(query="test", collection="visa_oracle", top_k=5)
        assert "test" in result
        mock_retriever.search_with_reranking.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_federated_search(self, mock_retriever):
        """Test federated search (no collection)"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [{"text": "test", "score": 0.9, "metadata": {"title": "Test"}}],
        }

        result = await tool.execute(query="test", top_k=5)
        assert "test" in result

    @pytest.mark.asyncio
    async def test_whatsapp_federation_queries_only_public_low_pii_collections(
        self, mock_retriever
    ):
        safe_collections = {
            "visa_oracle",
            "legal_unified",
            "kbli_2025_final",
            "tax_genius",
            "immigration_circulars",
            "balizero_news",
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        await tool.execute(query="synthetic", _is_whatsapp=True)

        searched = {
            call.kwargs["collection_override"]
            for call in mock_retriever.search_with_reranking.await_args_list
        }
        assert searched == safe_collections
        assert "training_conversations_hybrid" not in searched
        assert "bali_zero_pricing_hybrid" not in searched

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "forbidden_collection",
        ["training_conversations_hybrid", "bali_zero_pricing_hybrid"],
    )
    async def test_whatsapp_explicit_forbidden_collection_never_reaches_retriever(
        self,
        mock_retriever,
        forbidden_collection,
    ):
        tool = VectorSearchTool(retriever=mock_retriever)

        result = await tool.execute(
            query="synthetic",
            collection=forbidden_collection,
            _is_whatsapp=True,
        )

        mock_retriever.search_with_reranking.assert_not_awaited()
        mock_retriever.search.assert_not_awaited()
        assert forbidden_collection not in result

    @pytest.mark.asyncio
    async def test_whatsapp_result_minimizes_rag_metadata_before_model_observation(
        self, mock_retriever
    ):
        drive_url = "https://drive.google.com/file/d/CANARY_DOC_ID/view?label=CANARY_DRIVE_URL"
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {
                    "text": (
                        "Peraturan Pemerintah 28/2025 establishes the public legal rule. "
                        f"Internal copy: {drive_url}"
                    ),
                    "score": 0.99,
                    "metadata": {
                        "title": "Peraturan Pemerintah 28/2025",
                        "url": drive_url,
                        "document_id": "CANARY_DOC_ID",
                        "collection": "CANARY_INTERNAL_COLLECTION",
                    },
                }
            ]
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        result = await tool.execute(
            query="synthetic",
            collection="legal_unified",
            _is_whatsapp=True,
        )

        payload = json.loads(result)
        rendered = json.dumps(payload)
        assert "Peraturan Pemerintah 28/2025" in rendered
        assert "CANARY_DRIVE_URL" not in rendered
        assert "drive.google.com" not in rendered
        assert "CANARY_DOC_ID" not in rendered
        assert "CANARY_INTERNAL_COLLECTION" not in rendered
        assert "legal_unified" not in rendered
        assert set(payload) == {"content", "sources"}
        assert payload["sources"] == [{"title": "Peraturan Pemerintah 28/2025"}]

    @pytest.mark.asyncio
    async def test_whatsapp_result_strips_inline_metadata_and_generated_scaffolding(
        self,
        mock_retriever,
    ):
        """Only public prose may cross the WA vector-result boundary.

        The canaries mirror metadata shapes observed in retrieved chunk text;
        the bracketed Pasal citations pin the non-destructive case.
        """
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {
                    "text": (
                        "PP 28/2025 is the public rule. Internal copy: "
                        "https://drive.google.com/file/d/DRIVE_URL_CANARY/view\n"
                        "Google Drive file ID: DRIVE_FILE_ID_CANARY\n"
                        "Document ID DOCUMENT_ID_CANARY\n"
                        "document_id=UNDERSCORE_DOC_CANARY\n"
                        "document-id=HYPHEN_DOC_CANARY\n"
                        "source_metadata=SOURCE_META_CANARY\n"
                        "DocumentID=CAMEL_DOC_CANARY\n"
                        "source_url=SOURCE_URL_CANARY\n"
                        "google_drive_file_id=GOOGLE_DRIVE_CANARY\n"
                        "collection=INTERNAL_COLLECTION_CANARY\n"
                        "source metadata inline: SOURCE_METADATA_CANARY\n"
                        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku."
                    ),
                    "score": 0.99,
                    "metadata": {"title": "Official public regulation"},
                }
            ]
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        payload = json.loads(
            await tool.execute(
                query="synthetic",
                collection="legal_unified",
                _is_whatsapp=True,
            )
        )

        content = payload["content"]
        assert "PP 28/2025 is the public rule." in content
        assert "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku." in content
        assert not content.lstrip().startswith("[1]")
        for canary in (
            "Internal copy:",
            "drive.google.com",
            "DRIVE_URL_CANARY",
            "Google Drive file ID",
            "DRIVE_FILE_ID_CANARY",
            "Document ID",
            "DOCUMENT_ID_CANARY",
            "document_id=",
            "UNDERSCORE_DOC_CANARY",
            "document-id=",
            "HYPHEN_DOC_CANARY",
            "source_metadata=",
            "SOURCE_META_CANARY",
            "DocumentID=",
            "CAMEL_DOC_CANARY",
            "source_url=",
            "SOURCE_URL_CANARY",
            "source_",
            "google_drive_file_id=",
            "GOOGLE_DRIVE_CANARY",
            "google_drive_",
            "collection=",
            "INTERNAL_COLLECTION_CANARY",
            "source metadata inline:",
            "SOURCE_METADATA_CANARY",
        ):
            assert canary not in content

    @pytest.mark.asyncio
    @pytest.mark.parametrize("metadata_label", _WA_METADATA_LABEL_CASES)
    async def test_whatsapp_result_strips_generated_metadata_label_matrix(
        self,
        mock_retriever,
        metadata_label,
    ):
        """Metadata families are structural across case and separator styles."""
        value_canary = "SYNTHETIC_METADATA_VALUE_CANARY"
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {
                    "text": (
                        "Public guidance before private fields. "
                        f"{metadata_label}={value_canary}\n"
                        f"{metadata_label}: {value_canary}\n"
                        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku."
                    ),
                    "score": 0.99,
                    "metadata": {"title": "Official public regulation"},
                }
            ]
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        payload = json.loads(
            await tool.execute(
                query="synthetic",
                collection="legal_unified",
                _is_whatsapp=True,
            )
        )

        content = payload["content"]
        assert "Public guidance before private fields." in content
        assert "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku." in content
        assert metadata_label not in content
        assert value_canary not in content

    @pytest.mark.asyncio
    async def test_whatsapp_result_keeps_public_segments_around_metadata(self, mock_retriever):
        """Structural labels do not consume adjacent public prose or legal citations."""
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {
                    "text": (
                        "Public prefix | source_url=SOURCE_URL_CANARY | Public suffix\n"
                        "Public semicolon; DocumentID=DOCUMENT_ID_CANARY; Public tail\n"
                        "This collection of public rules explains source URL requirements "
                        "and internal metadata standards.\n"
                        "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku."
                    ),
                    "score": 0.99,
                    "metadata": {"title": "Official public regulation"},
                }
            ]
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        payload = json.loads(
            await tool.execute(
                query="synthetic",
                collection="legal_unified",
                _is_whatsapp=True,
            )
        )

        content = payload["content"]
        for public_text in (
            "Public prefix",
            "Public suffix",
            "Public semicolon",
            "Public tail",
            "This collection of public rules explains source URL requirements "
            "and internal metadata standards.",
            "Perpres 10/2021 Pasal 6 [1] dan [3] berlaku.",
        ):
            assert public_text in content
        assert "SOURCE_URL_CANARY" not in content
        assert "DOCUMENT_ID_CANARY" not in content

    @pytest.mark.asyncio
    async def test_whatsapp_retriever_error_log_never_contains_raw_canaries(
        self,
        mock_retriever,
        caplog,
    ):
        exception_canary = "SYNTHETIC_RAW_EXCEPTION_CANARY_5bc1"
        query_canary = "SYNTHETIC_RAW_QUERY_CANARY_7ad2"
        mock_retriever.search_with_reranking.side_effect = RuntimeError(exception_canary)
        tool = VectorSearchTool(retriever=mock_retriever)

        with caplog.at_level(
            "WARNING",
            logger="backend.services.rag.agentic.tools",
        ):
            await tool.execute(
                query=query_canary,
                collection="visa_oracle",
                _is_whatsapp=True,
            )

        assert exception_canary not in caplog.text
        assert query_canary not in caplog.text
        assert "visa_oracle" not in caplog.text
        assert "error_type=RuntimeError" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)

    @pytest.mark.asyncio
    async def test_non_whatsapp_result_keeps_existing_source_metadata_contract(
        self,
        mock_retriever,
    ):
        """The L0 minimizer is scoped to trusted WhatsApp calls only."""
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {
                    "text": "Public guidance with ordinary source prose.",
                    "score": 0.91,
                    "metadata": {
                        "title": "Synthetic source title",
                        "document_id": "NON_WA_DOCUMENT_CANARY",
                        "url": "https://example.test/NON_WA_URL_CANARY",
                    },
                }
            ]
        }
        tool = VectorSearchTool(retriever=mock_retriever)

        payload = json.loads(
            await tool.execute(
                query="synthetic",
                collection="legal_unified",
            )
        )

        assert "[1] Source: legal_unified" in payload["content"]
        assert "ID: NON_WA_DOCUMENT_CANARY" in payload["content"]
        assert payload["sources"][0]["collection"] == "legal_unified"
        assert payload["sources"][0]["doc_id"] == "NON_WA_DOCUMENT_CANARY"
        assert payload["sources"][0]["url"].endswith("NON_WA_URL_CANARY")

    @pytest.mark.asyncio
    async def test_execute_no_results(self, mock_retriever):
        """Test execute with no results"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {"results": []}

        result = await tool.execute(query="test")
        assert "No relevant documents" in result

    @pytest.mark.asyncio
    async def test_execute_with_deduplication(self, mock_retriever):
        """Test deduplication of results"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.return_value = {
            "results": [
                {"text": "test content", "score": 0.9, "metadata": {"title": "Test"}},
                {"text": "test content", "score": 0.8, "metadata": {"title": "Test2"}},
            ],
        }

        result = await tool.execute(query="test")
        # Should deduplicate by first 100 chars
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_retriever):
        """Test error handling"""
        tool = VectorSearchTool(retriever=mock_retriever)
        mock_retriever.search_with_reranking.side_effect = Exception("Search error")

        result = await tool.execute(query="test")
        assert result is not None


class TestCalculatorTool:
    """Tests for CalculatorTool"""

    def test_name(self):
        """Test tool name"""
        tool = CalculatorTool()
        assert tool.name == "calculator"

    def test_description(self):
        """Test tool description"""
        tool = CalculatorTool()
        assert "mathematical" in tool.description.lower()

    def test_parameters_schema(self):
        """Test parameters schema"""
        tool = CalculatorTool()
        schema = tool.parameters_schema
        assert schema["type"] == "object"
        assert "expression" in schema["properties"]

    @pytest.mark.asyncio
    async def test_execute_addition(self):
        """Test addition"""
        tool = CalculatorTool()
        result = await tool.execute(expression="2+2")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_execute_multiplication(self):
        """Test multiplication"""
        tool = CalculatorTool()
        result = await tool.execute(expression="5*3")
        assert "15" in result

    @pytest.mark.asyncio
    async def test_execute_division(self):
        """Test division"""
        tool = CalculatorTool()
        result = await tool.execute(expression="10/2")
        assert "5" in result

    @pytest.mark.asyncio
    async def test_execute_power(self):
        """Test power"""
        tool = CalculatorTool()
        result = await tool.execute(expression="2**3")
        assert "8" in result

    @pytest.mark.asyncio
    async def test_execute_invalid_expression(self):
        """Test invalid expression"""
        tool = CalculatorTool()
        result = await tool.execute(expression="__import__('os')")
        assert "error" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_unsafe_operator(self):
        """Test unsafe operator"""
        tool = CalculatorTool()
        result = await tool.execute(expression="open('file.txt')")
        assert "error" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_whatsapp_error_does_not_reflect_raw_exception(self):
        tool = CalculatorTool()
        error_canary = "SYNTHETIC_CALCULATOR_EXCEPTION_CANARY"

        with patch(
            "backend.app.utils.safe_math.safe_evaluate",
            side_effect=RuntimeError(error_canary),
        ):
            result = await tool.execute(
                expression="SYNTHETIC_CALCULATOR_INPUT_CANARY",
                _is_whatsapp=True,
            )

        assert result == "Error: unable to evaluate the mathematical expression."
        assert error_canary not in result
        assert "SYNTHETIC_CALCULATOR_INPUT_CANARY" not in result


class TestPricingTool:
    """Tests for PricingTool"""

    def test_name(self):
        """Test tool name"""
        tool = PricingTool()
        assert tool.name == "get_pricing"

    def test_description(self):
        """Test tool description"""
        tool = PricingTool()
        assert "pricing" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_with_category(self, mock_pricing_service):
        """Test execute with category"""
        with patch(
            "backend.services.rag.agentic.tools.get_pricing_service",
            return_value=mock_pricing_service,
        ):
            tool = PricingTool()
            # get_pricing is not async, it's a regular method
            mock_pricing_service.get_pricing.return_value = {
                "items": [{"name": "KITAS", "price": "15000000"}],
            }

            result = await tool.execute(service_type="visa")
            assert "KITAS" in result or "15000000" in result

    @pytest.mark.asyncio
    async def test_execute_without_category(self, mock_pricing_service):
        """Test execute without category"""
        with patch(
            "backend.services.rag.agentic.tools.get_pricing_service",
            return_value=mock_pricing_service,
        ):
            tool = PricingTool()
            mock_pricing_service.get_pricing.return_value = {"items": []}

            result = await tool.execute()
            assert result is not None

    @pytest.mark.asyncio
    async def test_whatsapp_error_is_generic_and_log_is_pii_free(
        self,
        mock_pricing_service,
        caplog,
    ):
        query_canary = "SYNTHETIC_PRICING_QUERY_CANARY"
        error_canary = "SYNTHETIC_PRICING_EXCEPTION_CANARY"
        mock_pricing_service.loaded = True
        mock_pricing_service.search_service.side_effect = RuntimeError(error_canary)
        tool = PricingTool(pricing_service=mock_pricing_service)

        with caplog.at_level(logging.ERROR):
            result = await tool.execute(
                service_type="visa",
                query=query_canary,
                _is_whatsapp=True,
            )

        assert "Pricing lookup could not be completed." in result
        assert query_canary not in result
        assert error_canary not in result
        assert query_canary not in caplog.text
        assert error_canary not in caplog.text
        assert "error_type=RuntimeError" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)


class TestTeamKnowledgeTool:
    """Tests for TeamKnowledgeTool"""

    def test_name(self):
        """Test tool name"""
        tool = TeamKnowledgeTool()
        assert tool.name == "team_knowledge"

    def test_description(self):
        """Test tool description"""
        tool = TeamKnowledgeTool()
        assert "team" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_search(self, mock_team_service):
        """Test search query"""
        tool = TeamKnowledgeTool()
        # Mock the _load_team_data method to return test data
        with patch.object(
            tool,
            "_load_team_data",
            return_value=[{"name": "Test", "email": "test@example.com", "role": "developer"}],
        ):
            result = await tool.execute(query_type="search_by_name", search_term="test")
            assert "test" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_list(self, mock_team_service):
        """Test list query"""
        tool = TeamKnowledgeTool()
        # Mock the _load_team_data method to return test data
        with patch.object(
            tool,
            "_load_team_data",
            return_value=[{"name": "Test", "email": "test@example.com"}],
        ):
            result = await tool.execute(query_type="list_all")
            assert result is not None


class TestVisionTool:
    """Tests for VisionTool"""

    def test_name(self):
        """Test tool name"""
        tool = VisionTool()
        assert tool.name == "vision_analysis"

    def test_description(self):
        """Test tool description"""
        tool = VisionTool()
        assert "image" in tool.description.lower() or "vision" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute_allowed_path(self, mock_vision_service):
        """Test execute with file path inside allowed directory."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service
            mock_vision_service.process_pdf = AsyncMock(return_value={"doc": "test"})
            mock_vision_service.query_with_vision = AsyncMock(
                return_value={"answer": "test analysis"},
            )

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test query")
                assert "analysis result" in result.lower()
                mock_vision_service.process_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_blocked_path_outside_allowed_dirs(self, mock_vision_service):
        """Test that paths outside allowed directories are blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/etc/passwd", query="read this")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_path_etc_shadow(self, mock_vision_service):
        """Test that sensitive system files are blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/etc/shadow", query="extract content")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_directory_traversal(self, mock_vision_service):
        """Test that directory traversal via .. is blocked.

        /tmp/../etc/passwd resolves to /etc/passwd which fails the
        allowed-dirs check before the '..' check is reached. Either way,
        the path is blocked -- that's what matters.
        """
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp", "/app/uploads"]
                result = await tool.execute(file_path="/tmp/../etc/passwd", query="read")
                assert "error" in result.lower()
                assert (
                    "not allowed" in result.lower()
                    or "traversal" in result.lower()
                    or "access denied" in result.lower()
                )
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_nested_traversal(self, mock_vision_service):
        """Test that deeply nested directory traversal is blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/app/uploads"]
                result = await tool.execute(file_path="/app/uploads/../../etc/passwd", query="read")
                assert "error" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_blocked_home_directory(self, mock_vision_service):
        """Test that home directory access is blocked."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp"]
                result = await tool.execute(file_path="/home/user/.ssh/id_rsa", query="read")
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_vision_service):
        """Test error handling when vision service fails."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service
            mock_vision_service.process_pdf = AsyncMock(side_effect=Exception("Vision error"))

            with patch("backend.app.core.config.settings") as mock_settings:
                mock_settings.get_vision_allowed_dirs = ["/tmp"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test")
                assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_respects_custom_allowed_dirs(self, mock_vision_service):
        """Test that custom VISION_ALLOWED_DIRS from settings is respected."""
        with patch.object(VisionTool, "__init__", lambda self: None):
            tool = VisionTool()
            tool.vision_service = mock_vision_service

            with patch("backend.app.core.config.settings") as mock_settings:
                # Only /custom/dir is allowed
                mock_settings.get_vision_allowed_dirs = ["/custom/dir"]
                result = await tool.execute(file_path="/tmp/test.pdf", query="test")
                # /tmp should be blocked because only /custom/dir is allowed
                assert "error" in result.lower()
                assert "not allowed" in result.lower() or "access denied" in result.lower()
                mock_vision_service.process_pdf.assert_not_called()
