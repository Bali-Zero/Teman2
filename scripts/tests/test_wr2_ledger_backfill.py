"""Tests for wr2_ledger_backfill.py — the historical LLM-labeling backfill
(WR2 editorial-intelligence Fase 4, spec §Mossa-D BLOCKER-2).

Batteries (guilt+innocence, mirroring the repo's parser/gate test discipline):

  - needs_backfill: native arc → NEVER (guilt: even with force); existing
    backfill → skip (innocence: force re-labels); no council / monolith-no-arc
    → label.
  - extract_copy_excerpt: joins headline/subhead/body/take_label; handles
    dict/JSON-string/list; bounded; malformed → "".
  - build_backfill_prompt: constrains arc to the 7-slate + hook to the vocab.
  - parse_backfill_response: valid label; out-of-vocab arc → None; bad hook →
    None; missing spine → None; confidence clamped; JSON-on-last-line among
    prose lines.
  - merge_backfill: ADDITIVE (preserves sibling keys — scar #9); sets the
    backfilled provenance flags; never mutates the input dict.
  - run_backfill: DRY-RUN writes nothing (conn.execute never called); APPLY
    writes the merged blob; idempotent skip of native/backfilled decks;
    sample_qa collection; failed labels counted, never fabricated.

Zero real DB, zero real CLI — conn is AsyncMock, label_deck is monkeypatched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_ledger_backfill as bf  # noqa: E402


# ── needs_backfill (guilt+innocence) ──────────────────────────────────────


def test_native_arc_is_never_backfilled_even_with_force() -> None:
    council = {"arc": "news_alert"}
    assert bf.needs_backfill(council, force=False) is False
    assert bf.needs_backfill(council, force=True) is False  # native is authoritative


def test_existing_backfill_is_skipped_unless_force() -> None:
    council = {"backfill": {"arc": "deadline"}}
    assert bf.needs_backfill(council, force=False) is False
    assert bf.needs_backfill(council, force=True) is True  # force re-labels


def test_monolith_deck_without_arc_is_labeled() -> None:
    assert bf.needs_backfill({"register_reason": "old blob"}, force=False) is True
    assert bf.needs_backfill(None, force=False) is True


def test_native_arc_must_be_nonempty_string() -> None:
    # a blank/whitespace arc is NOT a real native arc → should still be labeled
    assert bf.needs_backfill({"arc": "   "}, force=False) is True
    assert bf.needs_backfill({"arc": ""}, force=False) is True


# ── extract_copy_excerpt ──────────────────────────────────────────────────


def test_excerpt_joins_all_text_fields() -> None:
    blob = {"slides": [
        {"headline": "H1", "subhead": "S1", "body": "B1"},
        {"headline": "H2", "take_label": "T2"},
    ]}
    out = bf.extract_copy_excerpt(blob)
    for token in ("H1", "S1", "B1", "H2", "T2"):
        assert token in out


def test_excerpt_parses_json_string_and_bounds_length() -> None:
    blob = json.dumps({"slides": [{"body": "x" * 5000}]})
    out = bf.extract_copy_excerpt(blob, max_chars=100)
    assert len(out) == 100


def test_excerpt_malformed_returns_empty() -> None:
    assert bf.extract_copy_excerpt("{not json") == ""
    assert bf.extract_copy_excerpt(None) == ""
    assert bf.extract_copy_excerpt({"slides": "not a list"}) == ""


# ── build_backfill_prompt ─────────────────────────────────────────────────


def test_prompt_constrains_arc_and_hook_vocab() -> None:
    deck = bf.DeckToLabel(draft_id="d1", topic="New KITAS Rule", copy_excerpt="some copy")
    prompt = bf.build_backfill_prompt(deck)
    for arc in bf.RATIFIED_ARCS:
        assert arc in prompt
    for hook in bf.HOOK_CATEGORIES:
        assert hook in prompt
    assert "New KITAS Rule" in prompt
    assert "some copy" in prompt


# ── parse_backfill_response (guilt+innocence) ─────────────────────────────


def test_parse_valid_label() -> None:
    out = bf.parse_backfill_response(
        'thinking...\n{"arc":"deadline","spine_gist":"act before SPT","hook_type":"stat","confidence":0.8}'
    )
    assert out == bf.BackfillLabel(arc="deadline", spine_gist="act before SPT", hook_type="stat", confidence=0.8)


def test_parse_out_of_vocab_arc_is_rejected() -> None:
    out = bf.parse_backfill_response('{"arc":"listicle","spine_gist":"x","hook_type":"stat","confidence":0.9}')
    assert out is None


def test_parse_bad_hook_is_rejected() -> None:
    out = bf.parse_backfill_response('{"arc":"deadline","spine_gist":"x","hook_type":"vibes","confidence":0.9}')
    assert out is None


def test_parse_missing_spine_is_rejected() -> None:
    out = bf.parse_backfill_response('{"arc":"deadline","spine_gist":"","hook_type":"stat","confidence":0.9}')
    assert out is None


def test_parse_confidence_clamped_and_defaulted() -> None:
    hi = bf.parse_backfill_response('{"arc":"explainer","spine_gist":"x","hook_type":"list","confidence":9}')
    assert hi is not None and hi.confidence == 1.0
    missing = bf.parse_backfill_response('{"arc":"explainer","spine_gist":"x","hook_type":"list"}')
    assert missing is not None and missing.confidence == 0.0


def test_parse_picks_last_json_line_among_prose() -> None:
    out = bf.parse_backfill_response(
        'Here is my analysis.\n'
        '{"arc":"news_alert","spine_gist":"first draft","hook_type":"stat","confidence":0.5}\n'
        'Actually, on reflection:\n'
        '{"arc":"myth_buster","spine_gist":"final","hook_type":"contrarian","confidence":0.7}'
    )
    assert out is not None and out.arc == "myth_buster" and out.spine_gist == "final"


def test_parse_no_json_returns_none() -> None:
    assert bf.parse_backfill_response("no json here at all") is None


# ── merge_backfill (additive, scar #9) ────────────────────────────────────


def test_merge_preserves_sibling_keys_and_marks_provenance() -> None:
    council = {"register": "analitico", "some_monolith_key": {"nested": 1}}
    label = bf.BackfillLabel(arc="comparison", spine_gist="A vs B", hook_type="list", confidence=0.6)
    merged = bf.merge_backfill(council, label)
    # sibling keys survive
    assert merged["register"] == "analitico"
    assert merged["some_monolith_key"] == {"nested": 1}
    # backfill sub-object written with provenance
    assert merged["backfill"]["arc"] == "comparison"
    assert merged["backfill"]["backfilled"] is True
    assert merged["backfill"]["model"] == bf._BACKFILL_MODEL
    # input not mutated
    assert "backfill" not in council


def test_merge_on_none_council_creates_blob() -> None:
    label = bf.BackfillLabel(arc="explainer", spine_gist="s", hook_type="story", confidence=0.5)
    merged = bf.merge_backfill(None, label)
    assert merged["backfill"]["arc"] == "explainer"


# ── run_backfill (dry-run vs apply, idempotence, QA) ──────────────────────


def _deck_row(draft_id: str, council, slides=None):
    return {
        "id": draft_id,
        "topic": f"topic-{draft_id}",
        "slides_json": slides if slides is not None else {"slides": [{"headline": "H", "body": "B"}]},
        "council_debate_json": council,
    }


def _conn(rows):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_dry_run_writes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(
        bf, "label_deck",
        lambda deck: bf.BackfillLabel(arc="deadline", spine_gist="s", hook_type="stat", confidence=0.9),
    )
    conn = _conn([_deck_row("11111111-1111-1111-1111-111111111111", {"register_reason": "monolith"})])
    summary = await bf.run_backfill(conn, apply=False, force=False, sample_qa=5, limit=None)
    assert summary["labeled"] == 1
    assert summary["written"] == 0
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_writes_merged_blob(monkeypatch) -> None:
    monkeypatch.setattr(
        bf, "label_deck",
        lambda deck: bf.BackfillLabel(arc="deadline", spine_gist="s", hook_type="stat", confidence=0.9),
    )
    conn = _conn([_deck_row("11111111-1111-1111-1111-111111111111", {"register_reason": "monolith"})])
    summary = await bf.run_backfill(conn, apply=True, force=False, sample_qa=5, limit=None)
    assert summary["written"] == 1
    conn.execute.assert_awaited_once()
    # the written payload carries the backfill sub-object
    written_json = conn.execute.await_args.args[2]
    assert json.loads(written_json)["backfill"]["arc"] == "deadline"


@pytest.mark.asyncio
async def test_native_and_backfilled_decks_are_skipped(monkeypatch) -> None:
    monkeypatch.setattr(
        bf, "label_deck",
        lambda deck: bf.BackfillLabel(arc="deadline", spine_gist="s", hook_type="stat", confidence=0.9),
    )
    conn = _conn([
        _deck_row("11111111-1111-1111-1111-111111111111", {"arc": "news_alert"}),  # native → skip
        _deck_row("22222222-2222-2222-2222-222222222222", {"backfill": {"arc": "x"}}),  # done → skip
        _deck_row("33333333-3333-3333-3333-333333333333", {"register_reason": "old"}),  # target
    ])
    summary = await bf.run_backfill(conn, apply=True, force=False, sample_qa=5, limit=None)
    assert summary["skipped_native_or_done"] == 2
    assert summary["labeled"] == 1
    assert summary["written"] == 1


@pytest.mark.asyncio
async def test_failed_label_is_counted_not_fabricated(monkeypatch) -> None:
    monkeypatch.setattr(bf, "label_deck", lambda deck: None)  # LLM failed
    conn = _conn([_deck_row("11111111-1111-1111-1111-111111111111", {"register_reason": "monolith"})])
    summary = await bf.run_backfill(conn, apply=True, force=False, sample_qa=5, limit=None)
    assert summary["failed"] == 1
    assert summary["written"] == 0
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sample_qa_is_collected(monkeypatch) -> None:
    monkeypatch.setattr(
        bf, "label_deck",
        lambda deck: bf.BackfillLabel(arc="explainer", spine_gist="s", hook_type="list", confidence=0.7),
    )
    rows = [_deck_row(f"{i:08d}-0000-0000-0000-000000000000".replace(" ", ""), {"register_reason": "m"}) for i in range(4)]
    conn = _conn(rows)
    summary = await bf.run_backfill(conn, apply=False, force=False, sample_qa=2, limit=None)
    assert len(summary["qa_samples"]) == 2
    assert summary["qa_samples"][0]["arc"] == "explainer"


@pytest.mark.asyncio
async def test_deck_without_copy_is_a_failed_not_a_blank_label(monkeypatch) -> None:
    called = {"n": 0}

    def _label(deck):
        called["n"] += 1
        return bf.BackfillLabel(arc="deadline", spine_gist="s", hook_type="stat", confidence=0.9)

    monkeypatch.setattr(bf, "label_deck", _label)
    conn = _conn([_deck_row("11111111-1111-1111-1111-111111111111", {"register_reason": "m"}, slides={"slides": []})])
    summary = await bf.run_backfill(conn, apply=True, force=False, sample_qa=5, limit=None)
    assert summary["failed"] == 1
    assert called["n"] == 0  # never even called the LLM on empty copy
