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


def test_verify_law_claim_no_self_substring_fallback(fc):
    # WR2 autopsy P-5: the self-substring fallback for law claims was REMOVED
    # (with research_json NULL the only "source" was the slides themselves, so
    # every citation self-verified). A claim with no matchable external citation
    # is now 'unverifiable' (aggregates to 'degraded', never a silent 'pass').
    out = fc._verify_law_claim("subhi office", set(), "subhi office is in Kerobokan")
    assert out["verdict"] == "unverifiable"


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
            conn, draft_id, {"claims": []}, "pass", fc.PROVENANCE_SUPPORTED_BY_SOURCE_ARTICLE
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
            conn, draft_id, {"claims": [{"verdict": "contradicted"}]}, "fail",
            fc.PROVENANCE_SOURCE_ABSENT,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "fact_check_failed"


def test_persist_checked_degraded_supported_still_proceeds_to_canva_apply(fc):
    """degraded + provenance=supported_by_source_article is NOT terminal —
    canva-apply consumes it. This provenance value cannot actually be
    produced alongside fact_check_status='degraded' by _aggregate_provenance
    (degraded implies an unverifiable/no-external-truth claim, which always
    yields source_absent/claim_unparseable) — this test exercises
    _persist_checked's OWN routing logic in isolation, independent of how
    the caller derives provenance."""
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded",
            fc.PROVENANCE_SUPPORTED_BY_SOURCE_ARTICLE,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "drafts_imaged_checked"
    assert args[3] == "degraded"


def test_persist_checked_degraded_source_absent_now_blocked(fc):
    """2026-08-03 Change 3 (the fix under test): degraded + provenance=
    source_absent must NOT reach drafts_imaged_checked anymore — this is the
    fail-open hole being closed. It is held at fact_check_failed instead,
    same as a genuine contradiction (wr2_supervisor.py tells them apart for
    alerting purposes without re-opening the canva-eligible gate)."""
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded",
            fc.PROVENANCE_SOURCE_ABSENT,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "fact_check_failed"
    assert args[3] == "degraded"


def test_persist_checked_degraded_claim_unparseable_now_blocked(fc):
    """Same as above for the claim_unparseable provenance bucket."""
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded",
            fc.PROVENANCE_CLAIM_UNPARSEABLE,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "fact_check_failed"
    assert args[3] == "degraded"


# ─────────────────────────────────────────────────────────────────────────
# WR2_PROVENANCE_HARD_GATE_ENABLED — the emergency bypass kill-switch
# ─────────────────────────────────────────────────────────────────────────


def test_hard_gate_enabled_by_default(fc):
    assert fc.WR2_PROVENANCE_HARD_GATE_ENABLED is True


def test_persist_checked_source_absent_bypassed_when_hard_gate_disabled(fc):
    """With the kill-switch off, provenance=source_absent reverts to the
    pre-Change-3 routing: it no longer blocks a 'degraded' draft from
    reaching 'drafts_imaged_checked'."""
    fc.WR2_PROVENANCE_HARD_GATE_ENABLED = False
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded",
            fc.PROVENANCE_SOURCE_ABSENT,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "drafts_imaged_checked"
    assert args[3] == "degraded"


def test_persist_checked_claim_unparseable_bypassed_when_hard_gate_disabled(fc):
    fc.WR2_PROVENANCE_HARD_GATE_ENABLED = False
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "unverifiable"}]}, "degraded",
            fc.PROVENANCE_CLAIM_UNPARSEABLE,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "drafts_imaged_checked"
    assert args[3] == "degraded"


def test_persist_checked_fail_still_blocks_when_hard_gate_disabled(fc):
    """The kill-switch only reverts the provenance-based block — an active
    'fail' status must still terminate at fact_check_failed regardless."""
    fc.WR2_PROVENANCE_HARD_GATE_ENABLED = False
    draft_id = uuid.uuid4()
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(
        fc._persist_checked(
            conn, draft_id, {"claims": [{"verdict": "contradicted"}]}, "fail",
            fc.PROVENANCE_SOURCE_ABSENT,
        )
    )
    args = conn.execute.call_args[0]
    assert args[4] == "fact_check_failed"


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
        "brief_json": {"article_summary": source},
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
        "brief_json": json.dumps({"article_summary": "PP 28/2025"}),
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


# ─────────────────────────────────────────────────────────────────────────
# Regression: research_json is systemically NULL in production; the actual
# research lives in brief_json (article_summary / article_body_full /
# enrichment). The checker must include brief_json in its source corpus or it
# false-flags headline numbers the slides omit for editorial brevity.
# ─────────────────────────────────────────────────────────────────────────

def test_extract_source_text_includes_brief_json(fc):
    """A figure present only in brief_json must land in the source corpus."""
    text = fc._extract_source_text(
        research_json=None,
        council_debate_json=None,
        slides=[{"title": "Pajak", "body": "Aturan baru berlaku"}],
        brief_json={
            "article_summary": "Target setoran pajak Rp 52 triliun tahun ini.",
            "enrichment": {"the_facts": "Angka 2.500 unit terdampak."},
        },
    )
    assert "52" in text
    assert "2.500" in text


def test_process_one_draft_verifies_number_only_in_brief_json(fc):
    """Headline number 52 lives only in brief_json (research_json NULL, slides
    omit it). Before the fix this was a false 'contradicted' → fact_check_failed.
    After the fix the checker verifies it against brief_json."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "Pajak",
        "register": "pedagogico",
        # Slides deliberately omit the headline number (editorial brevity).
        "slides_json": {"slides": [{"index": 1, "title": "Pajak", "body": "Setoran pajak meningkat tahun ini."}]},
        # research_json systemically NULL in production.
        "research_json": None,
        # The real research the article was derived from.
        "brief_json": {"article_summary": "Target setoran pajak Rp 52 triliun tahun ini."},
        "council_debate_json": None,
        "fact_check_json": {
            "claims": [
                {"claim": "target Rp 52 triliun", "slide_index": 1, "type": "number", "context": ""},
            ],
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is True
    args = conn.execute.call_args[0]
    assert args[3] == "pass"  # not "fail"
    assert args[4] == "drafts_imaged_checked"  # not "fact_check_failed"


# ─────────────────────────────────────────────────────────────────────────
# 2026-08-03 — provenance labels (Change 2) + the slide-exclusion fix
# (Change 1) + the hard gate (Change 3). See
# research/marketing/2026-07-18-wr2-fact-check-degraded-root-cause.md.
# ─────────────────────────────────────────────────────────────────────────

# --- _claim_defect_class / _aggregate_provenance direct unit coverage -----

def test_claim_defect_class_word_number_is_unparseable(fc):
    claim = {"verdict": "unverifiable", "note": "no extractable number in claim"}
    assert fc._claim_defect_class(claim) == fc.PROVENANCE_CLAIM_UNPARSEABLE


def test_claim_defect_class_word_date_is_unparseable(fc):
    claim = {"verdict": "unverifiable", "note": "no extractable date in claim"}
    assert fc._claim_defect_class(claim) == fc.PROVENANCE_CLAIM_UNPARSEABLE


def test_claim_defect_class_law_no_citation_is_source_absent(fc):
    """'law claim has no matchable citation' is NOT one of the two literal
    representation-failure notes this file's spec names — it is a claim that
    genuinely carries nothing to corroborate, so it buckets as source_absent,
    not claim_unparseable (deliberate: matches the task's exact-string
    contract, not the broader repr/starvation split the 2026-07-18 root-cause
    report used for a different purpose)."""
    claim = {"verdict": "unverifiable", "note": "law claim has no matchable citation"}
    assert fc._claim_defect_class(claim) == fc.PROVENANCE_SOURCE_ABSENT


def test_claim_defect_class_token_overlap_is_source_absent(fc):
    claim = {"verdict": "unverifiable", "note": "token overlap 1/5 <60%"}
    assert fc._claim_defect_class(claim) == fc.PROVENANCE_SOURCE_ABSENT


def test_aggregate_provenance_empty_claims_is_supported(fc):
    """Vacuous case mirrors _aggregate_status's vacuous 'pass'."""
    assert fc._aggregate_provenance([]) == fc.PROVENANCE_SUPPORTED_BY_SOURCE_ARTICLE


def test_aggregate_provenance_source_absent_wins_over_unparseable(fc):
    claims = [
        {"verdict": "unverifiable", "note": "no extractable number in claim"},
        {"verdict": "unverifiable", "note": "token overlap 1/5 <60%"},
    ]
    assert fc._aggregate_provenance(claims, has_external_truth=True) == fc.PROVENANCE_SOURCE_ABSENT


def test_aggregate_provenance_all_unparseable(fc):
    claims = [
        {"verdict": "unverifiable", "note": "no extractable number in claim"},
        {"verdict": "unverifiable", "note": "no extractable date in claim"},
    ]
    assert (
        fc._aggregate_provenance(claims, has_external_truth=True)
        == fc.PROVENANCE_CLAIM_UNPARSEABLE
    )


def test_aggregate_provenance_all_verified_no_external_truth_is_source_absent(fc):
    """All claims 'verified' but only against the draft's own thin/absent
    source (self-reference) — same 'not trusted' case _aggregate_status caps
    at 'degraded'."""
    claims = [{"verdict": "verified"}]
    assert (
        fc._aggregate_provenance(claims, has_external_truth=False)
        == fc.PROVENANCE_SOURCE_ABSENT
    )


def test_aggregate_provenance_all_verified_with_external_truth_is_supported(fc):
    claims = [{"verdict": "verified"}]
    assert (
        fc._aggregate_provenance(claims, has_external_truth=True)
        == fc.PROVENANCE_SUPPORTED_BY_SOURCE_ARTICLE
    )


# --- End-to-end GUILT / INNOCENCE cases ------------------------------------

def test_process_one_draft_non_law_claim_self_slide_match_is_unverifiable(fc):
    """GUILT (Change 1): a non-law claim matching ONLY the draft's own
    slides — absent from research_json/brief_json/council_debate_json —
    must be 'unverifiable', NOT 'verified'. Before Change 1, `_verify_claim`
    was handed slide-inclusive `source_text` for every non-law claim type, so
    this exact case self-verified (the rubber-stamp hole the root-cause
    report calls out at wr2_fact_checker.py:662/676)."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": {
            "slides": [
                {"index": 1, "title": "X", "body": "Bali Zero opens a branch in Canggu next month"}
            ]
        },
        "research_json": {"text": "completely unrelated external content about something else entirely"},
        "brief_json": {"article_summary": "completely unrelated external content about something else entirely"},
        "council_debate_json": None,
        "fact_check_json": {
            "claims": [
                {"claim": "Bali Zero opens a branch in Canggu", "slide_index": 1, "type": "other", "context": ""},
            ]
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    args = conn.execute.call_args[0]
    persisted = json.loads(args[2])
    assert persisted["claims"][0]["verdict"] == "unverifiable"


def test_process_one_draft_no_external_source_blocked_from_canva(fc):
    """GUILT (Change 3): a draft whose only claim is verifiable ONLY against
    itself (no external truth at all — research/brief/council all empty)
    must NOT reach status='drafts_imaged_checked' anymore. Before Change 3
    this was today's silent-'degraded' fail-open: fact_check_status stayed
    'degraded' but status still advanced to the canva-eligible value."""
    draft_id = uuid.uuid4()
    row = {
        "id": draft_id,
        "topic": "T",
        "register": "pedagogico",
        "slides_json": {"slides": [{"index": 1, "title": "X", "body": "PP 28/2025"}]},
        "research_json": None,
        "brief_json": None,
        "council_debate_json": None,
        "fact_check_json": {
            "claims": [{"claim": "PP 28/2025", "slide_index": 1, "type": "law", "context": ""}],
        },
    }
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    args = conn.execute.call_args[0]
    assert args[3] == "degraded"  # fact_check_status unchanged by Change 3
    assert args[4] == "fact_check_failed"  # but status is now held, not canva-eligible
    persisted = json.loads(args[2])
    assert persisted["provenance"] == fc.PROVENANCE_SOURCE_ABSENT


def test_process_one_draft_law_citation_not_found_gives_source_absent_provenance(fc):
    """GUILT: a law citation not found anywhere in the external source →
    draft provenance = source_absent."""
    draft_id = uuid.uuid4()
    row = _make_facted_row(
        draft_id,
        [{"claim": "PP 99/2099 governs this", "slide_index": 1, "type": "law", "context": ""}],
        "PMK 81/2024 establishes unrelated rules",
    )
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    args = conn.execute.call_args[0]
    persisted = json.loads(args[2])
    assert persisted["provenance"] == fc.PROVENANCE_SOURCE_ABSENT
    assert args[4] == "fact_check_failed"


def test_process_one_draft_word_number_gives_claim_unparseable_provenance(fc):
    """GUILT: a claim whose ONLY defect is 'no extractable number in claim'
    (the number was expressed as a word) → draft provenance =
    claim_unparseable."""
    draft_id = uuid.uuid4()
    row = _make_facted_row(
        draft_id,
        [{"claim": "the fee doubled this year", "slide_index": 1, "type": "number", "context": ""}],
        "PMK 81/2024 sets the fee at four times the base rate",
    )
    conn = MagicMock()
    conn.execute = AsyncMock()
    asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    args = conn.execute.call_args[0]
    persisted = json.loads(args[2])
    assert persisted["claims"][0]["note"] == "no extractable number in claim"
    assert persisted["provenance"] == fc.PROVENANCE_CLAIM_UNPARSEABLE
    assert args[4] == "fact_check_failed"


def test_process_one_draft_all_claims_match_external_gives_supported_provenance(fc):
    """INNOCENCE: genuine external corroboration must NOT be over-tightened
    into a hold — the healthy path still reaches drafts_imaged_checked, and
    its provenance is honestly labeled supported_by_source_article (fidelity
    to the source article), never independently_corroborated."""
    draft_id = uuid.uuid4()
    src = "PP 28/2025 establishes 1.5% rate for 2026"
    row = _make_facted_row(
        draft_id,
        [
            {"claim": "PP 28/2025", "slide_index": 1, "type": "law", "context": ""},
            {"claim": "rate 1.5", "slide_index": 1, "type": "number", "context": ""},
        ],
        src,
    )
    conn = MagicMock()
    conn.execute = AsyncMock()
    ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is True
    args = conn.execute.call_args[0]
    persisted = json.loads(args[2])
    assert persisted["provenance"] == fc.PROVENANCE_SUPPORTED_BY_SOURCE_ARTICLE
    assert args[3] == "pass"
    assert args[4] == "drafts_imaged_checked"


def test_process_one_draft_contradiction_unaffected_by_provenance_gate(fc):
    """INNOCENCE: a genuinely contradicted claim still produces
    fact_check_status='fail' -> status='fact_check_failed', unconditionally
    — Change 2 (provenance labels) and Change 3 (the new gate) must not
    touch this path. Same fixture as test_process_one_draft_fail, asserted
    here explicitly against the provenance-aware gate."""
    draft_id = uuid.uuid4()
    src = "actual rate is 1.5 percent"
    row = _make_facted_row(
        draft_id,
        [{"claim": "rate 999 percent", "slide_index": 1, "type": "number", "context": ""}],
        src,
    )
    conn = MagicMock()
    conn.execute = AsyncMock()
    with patch.object(fc, "_send_telegram", lambda *_a, **_kw: None):
        ok = asyncio.run(fc._process_one_draft(conn, row, llm_enabled=False))
    assert ok is False
    args = conn.execute.call_args[0]
    assert args[3] == "fail"
    assert args[4] == "fact_check_failed"
