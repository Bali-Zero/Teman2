"""Unit tests for scripts/wr2_fact_checker.py (Sprint B B-bis).

Covers:
- Per-claim deterministic verifier (law / quote / number / date / other)
- _aggregate_status (pass / degraded / fail rules)
- Status transition mapping (fail → fact_check_failed; pass/degraded → drafts_imaged_checked)
- LLM cross-check upgrades only unverifiable, never downgrades verified
- OB-3 invariant guard
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
CHECKER_PATH = SCRIPTS_DIR / "wr2_fact_checker.py"


@pytest.fixture
def fc(tmp_path):
    sys.modules.pop("wr2_fact_checker", None)
    spec = importlib.util.spec_from_file_location("wr2_fact_checker", CHECKER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_fact_checker"] = mod
    spec.loader.exec_module(mod)
    mod.TELEMETRY_PATH = tmp_path / "checker.jsonl"
    return mod


# ─────────────────────────────────────────────────────────────────────────
# Per-claim verifier (deterministic)
# ─────────────────────────────────────────────────────────────────────────

def test_verify_law_claim_exact_citation_match(fc):
    src_laws = {"PP 28/2025", "PMK 81/2024"}
    out = fc._verify_law_claim("Reference: PP 28/2025 supersedes PP 5/2021", src_laws, "PP 28/2025 text")
    assert out["verdict"] == "verified"


def test_verify_law_claim_unknown_citation(fc):
    out = fc._verify_law_claim("Reference: XYZ 999/9999", set(), "PP 28/2025 text")
    assert out["verdict"] == "unverifiable"


def test_verify_law_claim_substring_fallback(fc):
    out = fc._verify_law_claim("subhi office", set(), "subhi office is in Kerobokan")
    assert out["verdict"] == "verified"


def test_verify_quote_claim_exact_match(fc):
    out = fc._verify_quote_claim("we will streamline the process", "Bimo said: we will streamline the process today")
    assert out["verdict"] == "verified"


def test_verify_quote_claim_smart_quotes(fc):
    """Smart-quote-wrapped claim should match plain source."""
    out = fc._verify_quote_claim("“we will streamline”", "Bimo: we will streamline today")
    assert out["verdict"] == "verified"


def test_verify_quote_claim_not_found_unverifiable(fc):
    out = fc._verify_quote_claim("never said this exact thing", "completely different source text")
    assert out["verdict"] == "unverifiable"


def test_verify_number_match(fc):
    out = fc._verify_number_or_date_claim("rate is 1.5 percent", "rate is 1.5 percent across all categories", "number")
    assert out["verdict"] == "verified"


def test_verify_number_drift_contradicted(fc):
    out = fc._verify_number_or_date_claim("rate is 999 percent", "actual rate is 1.5 across all categories", "number")
    assert out["verdict"] == "contradicted"


def test_verify_number_partial_match_unverifiable(fc):
    out = fc._verify_number_or_date_claim("rates are 1.5 and 88", "rate is 1.5 percent only", "number")
    assert out["verdict"] == "unverifiable"


def test_verify_date_year_match(fc):
    out = fc._verify_number_or_date_claim("deadline 2026", "deadline year 2026 confirmed", "date")
    assert out["verdict"] == "verified"


def test_verify_date_drift_contradicted(fc):
    out = fc._verify_number_or_date_claim("deadline 2030", "deadline 2026 confirmed", "date")
    assert out["verdict"] == "contradicted"


def test_verify_other_substring(fc):
    out = fc._verify_other_claim("Bali Zero Kerobokan office", "office at Bali Zero Kerobokan, Jl. Raya")
    assert out["verdict"] == "verified"


def test_verify_other_token_overlap_60pct(fc):
    """≥60% of >3-char tokens present → verified."""
    out = fc._verify_other_claim(
        "Indonesian taxation regulation deadline",
        "the Indonesian regulation specifies deadline rules for taxation purposes"
    )
    assert out["verdict"] == "verified"


def test_verify_other_low_overlap_unverifiable(fc):
    out = fc._verify_other_claim(
        "completely unrelated nonsense gibberish words",
        "the Indonesian regulation about taxation"
    )
    assert out["verdict"] == "unverifiable"


def test_verify_claim_dispatches_by_type(fc):
    """_verify_claim picks the right helper per claim['type']."""
    src_text = "The PP 28/2025 deadline is 2026"
    src_laws = fc._find_law_citations(src_text)
    # law
    law_out = fc._verify_claim(
        {"claim": "PP 28/2025", "type": "law"}, src_text, src_laws
    )
    assert law_out["verdict"] == "verified"
    # date
    date_out = fc._verify_claim(
        {"claim": "deadline 2026", "type": "date"}, src_text, src_laws
    )
    assert date_out["verdict"] == "verified"
    # other
    other_out = fc._verify_claim(
        {"claim": "deadline", "type": "other"}, src_text, src_laws
    )
    assert other_out["verdict"] == "verified"


def test_verify_claim_empty_text_unverifiable(fc):
    out = fc._verify_claim({"claim": "", "type": "law"}, "src", set())
    assert out["verdict"] == "unverifiable"


# ─────────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────────

def test_aggregate_pass_when_all_verified(fc):
    claims = [
        {"verdict": "verified"},
        {"verdict": "verified"},
    ]
    assert fc._aggregate_status(claims) == "pass"


def test_aggregate_fail_when_any_contradicted(fc):
    claims = [
        {"verdict": "verified"},
        {"verdict": "contradicted"},
        {"verdict": "verified"},
    ]
    assert fc._aggregate_status(claims) == "fail"


def test_aggregate_degraded_when_unverifiable_no_contradicted(fc):
    claims = [
        {"verdict": "verified"},
        {"verdict": "unverifiable"},
    ]
    assert fc._aggregate_status(claims) == "degraded"


def test_aggregate_pass_when_no_claims(fc):
    """Vacuously true: empty claims list → pass (lets canva-apply consume it)."""
    assert fc._aggregate_status([]) == "pass"


# ─────────────────────────────────────────────────────────────────────────
# Status transition mapping
# ─────────────────────────────────────────────────────────────────────────

def test_persist_checked_pass_advances_to_drafts_imaged_checked(fc):
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": []}, "pass"
        )
    )
    conn.execute.assert_awaited_once()
    args = conn.execute.call_args[0]
    # 4th positional arg is the new status.
    assert args[4] == "drafts_imaged_checked"
    assert args[3] == "pass"


def test_persist_checked_fail_advances_to_fact_check_failed(fc):
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "contradicted"}]}, "fail"
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "fact_check_failed"


def test_persist_checked_degraded_still_proceeds_to_canva_apply(fc):
    """degraded is NOT a terminal state — canva-apply consumes it."""
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded"
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "drafts_imaged_checked"
    assert args[3] == "degraded"


# ─────────────────────────────────────────────────────────────────────────
# End-to-end per-draft pipeline
# ─────────────────────────────────────────────────────────────────────────

def _make_facted_row(draft_id: uuid.UUID, claims: list[dict], source: str) -> dict:
    return {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": {"slides": [{"index": 1, "title": "X", "body": source}]},
        "research_json": {"text": source},
        "council_debate_json": None,
        "fact_check_json": {"claims": claims, "extracted_at": "2026-05-08T00:00:00+00:00"},
    }


def test_process_one_draft_pass(fc):
    draft_id = uuid.uuid4()
    src = "PP 28/2025 establishes 1.5% rate for 2026"
    row = _make_facted_row(draft_id, [
        {"claim": "PP 28/2025", "slide_index": 1, "type": "law", "context": ""},
        {"claim": "rate 1.5", "slide_index": 1, "type": "number", "context": ""},
    ], src)
    conn = MagicMock()
    conn.execute = AsyncMock()
    ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is True
    args = conn.execute.call_args[0]
    assert args[3] == "pass"
    assert args[4] == "drafts_imaged_checked"


def test_process_one_draft_fail(fc):
    draft_id = uuid.uuid4()
    src = "actual rate is 1.5 percent"
    row = _make_facted_row(draft_id, [
        {"claim": "rate 999 percent", "slide_index": 1, "type": "number", "context": ""},
    ], src)
    conn = MagicMock()
    conn.execute = AsyncMock()
    with patch.object(fc, "_send_telegram", lambda *_a, **_kw: None):
        ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is False  # fail outcome → False so caller can count
    args = conn.execute.call_args[0]
    assert args[3] == "fail"
    assert args[4] == "fact_check_failed"


def test_process_one_draft_handles_string_blobs(fc):
    """asyncpg may return JSONB columns as either dict or str (depending on conn config)."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": json.dumps({"slides": [{"index": 1, "title": "X", "body": "PP 28/2025"}]}),
        "research_json": json.dumps({"text": "PP 28/2025"}),
        "council_debate_json": None,
        "fact_check_json": json.dumps({"claims": [{"claim": "PP 28/2025", "slide_index": 1, "type": "law"}]}),
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is True
    args = conn.execute.call_args[0]
    assert args[3] == "pass"


def test_llm_cross_check_only_upgrades_unverifiable(fc):
    """LLM verdict 'verified' upgrades unverifiable claim; cannot downgrade verified."""
    draft_id = uuid.uuid4()
    row = _make_facted_row(draft_id, [
        # Will be unverifiable deterministically (low token overlap)
        {"claim": "obscure paraphrase no match", "slide_index": 1, "type": "other", "context": ""},
    ], "completely different source text")
    conn = MagicMock()
    conn.execute = AsyncMock()
    fake_llm = AsyncMock(return_value={"verdict": "verified", "note": "LLM says match"})
    with patch.object(fc, "_llm_verify_claim", fake_llm):
        ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=True))
    assert ok is True
    args = conn.execute.call_args[0]
    # After upgrade, status should be 'pass' not 'degraded'.
    assert args[3] == "pass"


def test_llm_cross_check_skipped_for_already_verified(fc):
    """If deterministic verifier already says 'verified', don't waste an LLM call."""
    draft_id = uuid.uuid4()
    row = _make_facted_row(draft_id, [
        {"claim": "PP 28/2025", "slide_index": 1, "type": "law"},
    ], "PP 28/2025 text")
    conn = MagicMock()
    conn.execute = AsyncMock()
    llm_mock = AsyncMock()
    with patch.object(fc, "_llm_verify_claim", llm_mock):
        asyncio.run(fc._process_one_draft(conn, row, llm_enabled=True))
    llm_mock.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────
# OB-3 invariant guard
# ─────────────────────────────────────────────────────────────────────────

def test_uses_claude_oauth_client_not_anthropic_sdk():
    """OB-3 hard rule via AST inspection (mirrors fact-extractor test)."""
    import ast
    tree = ast.parse(CHECKER_PATH.read_text())
    used_oauth_client = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("anthropic")
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("anthropic")
            if node.module and node.module.endswith("claude_oauth_client"):
                used_oauth_client = True
    assert used_oauth_client
