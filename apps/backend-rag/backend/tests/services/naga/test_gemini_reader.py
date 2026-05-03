"""Tests for Naga Gemini bulk reader (Pointer State Pattern).

Validates:
- Evidence map structure (facts, contradictions, gaps, data_points per sub_q)
- File persistence at {output_dir}/{session_id}/evidence.json
- URI matches saved file path
- Graceful handling of invalid / unparseable JSON from generate_fn
- Stripping of ```json code-block wrappers
- Source content truncation to 20K chars
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.services.naga.readers.gemini_reader import (
    _build_prompt,
    _parse_evidence,
    gemini_bulk_read,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_EVIDENCE: dict = {
    "sub_q_1": {
        "facts": [
            {
                "text": "Indonesia requires KITAS for work permits",
                "source_ids": ["s0"],
                "confidence": 0.92,
            }
        ],
        "contradictions": [],
        "gaps": ["No data on processing time"],
        "data_points": [{"label": "Fee", "value": "Rp 2.000.000", "source_id": "s0"}],
    },
    "sub_q_2": {
        "facts": [
            {
                "text": "PT PMA requires minimum Rp 10B investment",
                "source_ids": ["s1"],
                "confidence": 0.85,
            }
        ],
        "contradictions": [
            {
                "claim_a": "Minimum Rp 10B",
                "claim_b": "Minimum Rp 2.5B for certain sectors",
                "source_ids": ["s0", "s1"],
            }
        ],
        "gaps": [],
        "data_points": [],
    },
}


def _make_generate_fn(response_text: str) -> AsyncMock:
    """Create an AsyncMock that returns ``{"text": response_text}``."""
    fn = AsyncMock()
    fn.return_value = {"text": response_text}
    return fn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_bulk_read_returns_evidence_map() -> None:
    """Verify returned evidence_map has correct sub_q keys and structure."""
    generate_fn = _make_generate_fn(json.dumps(_VALID_EVIDENCE))

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_map, _uri = await gemini_bulk_read(
            sub_questions=["What is KITAS?", "What is PT PMA?"],
            sources_content=[
                {"id": "s0", "url": "https://a.com", "content": "KITAS info"},
                {"id": "s1", "url": "https://b.com", "content": "PT PMA info"},
            ],
            generate_fn=generate_fn,
            session_id="test-session",
            output_dir=tmpdir,
        )

    assert "sub_q_1" in evidence_map
    assert "sub_q_2" in evidence_map
    # Each sub_q must have the four required keys
    for key in ("facts", "contradictions", "gaps", "data_points"):
        assert key in evidence_map["sub_q_1"]
        assert key in evidence_map["sub_q_2"]
    # Validate fact structure
    fact = evidence_map["sub_q_1"]["facts"][0]
    assert "text" in fact
    assert "source_ids" in fact
    assert "confidence" in fact


@pytest.mark.asyncio
async def test_gemini_bulk_read_saves_to_file() -> None:
    """Verify evidence.json is created at the expected path."""
    generate_fn = _make_generate_fn(json.dumps(_VALID_EVIDENCE))

    with tempfile.TemporaryDirectory() as tmpdir:
        _evidence_map, uri = await gemini_bulk_read(
            sub_questions=["Q1", "Q2"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "text"}],
            generate_fn=generate_fn,
            session_id="persist-test",
            output_dir=tmpdir,
        )

        expected_path = Path(tmpdir) / "persist-test" / "evidence.json"
        assert expected_path.exists(), f"Expected file at {expected_path}"

        with open(expected_path) as f:
            saved = json.load(f)
        assert saved == _VALID_EVIDENCE


@pytest.mark.asyncio
async def test_gemini_bulk_read_returns_uri() -> None:
    """Verify returned URI matches the file path on disk."""
    generate_fn = _make_generate_fn(json.dumps(_VALID_EVIDENCE))

    with tempfile.TemporaryDirectory() as tmpdir:
        _evidence_map, uri = await gemini_bulk_read(
            sub_questions=["Q1", "Q2"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "data"}],
            generate_fn=generate_fn,
            session_id="uri-test",
            output_dir=tmpdir,
        )

        expected_path = str((Path(tmpdir) / "uri-test" / "evidence.json").resolve())
        assert uri == expected_path


@pytest.mark.asyncio
async def test_gemini_bulk_read_handles_json_error() -> None:
    """When generate_fn returns invalid JSON, return empty evidence with gap notes."""
    generate_fn = _make_generate_fn("This is NOT valid JSON at all {{{")

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_map, uri = await gemini_bulk_read(
            sub_questions=["What is KITAS?", "What is PT PMA?"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "text"}],
            generate_fn=generate_fn,
            session_id="json-error-test",
            output_dir=tmpdir,
        )

    # Must still have all sub_q keys
    assert "sub_q_1" in evidence_map
    assert "sub_q_2" in evidence_map
    # Facts should be empty
    assert evidence_map["sub_q_1"]["facts"] == []
    assert evidence_map["sub_q_2"]["facts"] == []
    # Gaps should note the parse error
    assert any("parse" in g.lower() or "error" in g.lower() for g in evidence_map["sub_q_1"]["gaps"])


@pytest.mark.asyncio
async def test_gemini_bulk_read_handles_code_blocks() -> None:
    """Strips ```json ... ``` wrapper before parsing."""
    wrapped = f"```json\n{json.dumps(_VALID_EVIDENCE)}\n```"
    generate_fn = _make_generate_fn(wrapped)

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_map, _uri = await gemini_bulk_read(
            sub_questions=["Q1", "Q2"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "data"}],
            generate_fn=generate_fn,
            session_id="codeblock-test",
            output_dir=tmpdir,
        )

    assert "sub_q_1" in evidence_map
    assert len(evidence_map["sub_q_1"]["facts"]) == 1


@pytest.mark.asyncio
async def test_gemini_bulk_read_truncates_sources() -> None:
    """Sources with content >20K chars are truncated in the prompt."""
    long_content = "A" * 25_000  # 25K chars, should be truncated to 20K
    generate_fn = _make_generate_fn(json.dumps(_VALID_EVIDENCE))

    with tempfile.TemporaryDirectory() as tmpdir:
        evidence_map, _uri = await gemini_bulk_read(
            sub_questions=["Q1", "Q2"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": long_content}],
            generate_fn=generate_fn,
            session_id="truncate-test",
            output_dir=tmpdir,
        )

    # Verify the generate_fn was called and received truncated content in prompt
    generate_fn.assert_called_once()
    prompt_arg = generate_fn.call_args[0][0]  # first positional arg
    # The prompt should NOT contain the full 25K chars
    assert len(prompt_arg) < 25_000 + 5_000  # prompt overhead + 20K max


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for the prompt builder."""

    def test_includes_sub_questions(self) -> None:
        prompt = _build_prompt(
            sub_questions=["What is KITAS?", "What is PMA?"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "data"}],
        )
        assert "sub_q_1" in prompt
        assert "sub_q_2" in prompt
        assert "What is KITAS?" in prompt
        assert "What is PMA?" in prompt

    def test_includes_source_ids(self) -> None:
        prompt = _build_prompt(
            sub_questions=["Q1"],
            sources_content=[
                {"id": "s0", "url": "https://a.com", "content": "alpha"},
                {"id": "s1", "url": "https://b.com", "content": "beta"},
            ],
        )
        assert "[SOURCE s0]" in prompt
        assert "[SOURCE s1]" in prompt

    def test_truncates_long_content(self) -> None:
        long_content = "X" * 25_000
        prompt = _build_prompt(
            sub_questions=["Q1"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": long_content}],
        )
        # Should contain at most 20K of content chars (plus truncation marker)
        assert "X" * 20_000 in prompt
        assert "X" * 25_000 not in prompt
        assert "[TRUNCATED]" in prompt


class TestParseEvidence:
    """Tests for JSON parsing / validation."""

    def test_valid_json(self) -> None:
        raw = json.dumps(_VALID_EVIDENCE)
        result = _parse_evidence(raw, sub_questions=["Q1", "Q2"])
        assert result == _VALID_EVIDENCE

    def test_strips_code_blocks(self) -> None:
        raw = f"```json\n{json.dumps(_VALID_EVIDENCE)}\n```"
        result = _parse_evidence(raw, sub_questions=["Q1", "Q2"])
        assert result == _VALID_EVIDENCE

    def test_strips_code_blocks_no_language(self) -> None:
        raw = f"```\n{json.dumps(_VALID_EVIDENCE)}\n```"
        result = _parse_evidence(raw, sub_questions=["Q1", "Q2"])
        assert result == _VALID_EVIDENCE

    def test_invalid_json_returns_empty_evidence(self) -> None:
        result = _parse_evidence("not json", sub_questions=["Q1", "Q2"])
        assert "sub_q_1" in result
        assert "sub_q_2" in result
        assert result["sub_q_1"]["facts"] == []
        assert any("parse" in g.lower() or "error" in g.lower() for g in result["sub_q_1"]["gaps"])

    def test_missing_keys_backfilled(self) -> None:
        """If Gemini returns a sub_q without all 4 keys, they are backfilled."""
        partial = {
            "sub_q_1": {"facts": [{"text": "x", "source_ids": [], "confidence": 0.5}]},
            # sub_q_2 missing entirely
        }
        result = _parse_evidence(json.dumps(partial), sub_questions=["Q1", "Q2"])
        # sub_q_1 should have backfilled keys
        for key in ("contradictions", "gaps", "data_points"):
            assert key in result["sub_q_1"]
        # sub_q_2 should exist with empty structure
        assert "sub_q_2" in result
        assert result["sub_q_2"]["facts"] == []


@pytest.mark.asyncio
async def test_gemini_bulk_read_generates_session_id_when_empty() -> None:
    """When session_id is empty string, a UUID-based ID is used."""
    generate_fn = _make_generate_fn(json.dumps(_VALID_EVIDENCE))

    with tempfile.TemporaryDirectory() as tmpdir:
        _evidence_map, uri = await gemini_bulk_read(
            sub_questions=["Q1", "Q2"],
            sources_content=[{"id": "s0", "url": "https://a.com", "content": "data"}],
            generate_fn=generate_fn,
            session_id="",
            output_dir=tmpdir,
        )

    # URI should be a valid path (not contain empty segment)
    assert "//" not in uri.replace("file://", "")
    assert Path(uri).name == "evidence.json"
