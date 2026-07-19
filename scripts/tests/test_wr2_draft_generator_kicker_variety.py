"""
Tests for the kicker/subhead variety fix (2026-07-20) + the same-day
red-team fix round (guard-starvation, steer-reset, per-row isolation,
schema-example de-anchor, fullwidth-colon bypass, colon-prefix lower bound,
exhausted-pool degrade, MUST-NOT cap).

PR #2544 (2026-07-16) banned "OUR TAKE"/"OUR READ"/"OUR VIEW" and added an
example kicker list to rule #7 -- since then 3/3 decks used "THE SIGNAL: ..."
(the FIRST example in that list). Root cause: variety instructions were
prompt-only prose with no memory of previous output; every fixed example
becomes an invariant. This extends the ONE axis that already had a proven
DB-armed lookback (register/image-mode, P-4 Art 10.6) to the take-slide
kicker and the cover subhead, and de-anchors BOTH static example surfaces
(rule #7's "e.g." list AND the Structure JSON worked example's take-slide
headline) so no single example can calcify again.

The 2026-07-20 red-team round (Codex NO-SHIP, 4 MAJOR + 6 MINOR) additionally
fixed: (1) guard starvation + steer-reset in the regen loop -- guards used
to short-circuit each other and an anti-sameness retry silently discarded
the editorial-variety steer; (2) a single malformed DB row used to zero out
the WHOLE fetched history; (3) the Structure JSON schema example still
taught a literal, unrotated kicker; plus 6 minor robustness fixes (fullwidth
colon, colon-prefix word-count floor, exhausted-pool degrade, MUST-NOT cap,
kicker-length wording, recency-clock note).

These tests don't call Claude -- pure helpers + mocked asyncpg conn.
"""

from __future__ import annotations

import json
import random
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_draft_generator as dg  # noqa: E402
from wr2_draft_generator import (  # noqa: E402
    KICKER_EXAMPLE_VOCABULARY,
    _VARIETY_STEER_KICKER_CAP,
    _build_draft_prompt,
    _build_variety_steer,
    _extract_take_kicker,
    _kicker_collision,
    _normalize_kicker,
    _render_kicker_examples,
    _render_schema_kicker,
    _sample_kickers,
    fetch_recent_editorial_signatures,
)


# ─────────────────────────────────────────────────────────────────────────
# _extract_take_kicker
# ─────────────────────────────────────────────────────────────────────────

def test_extract_kicker_colon_shape() -> None:
    assert _extract_take_kicker("THE SIGNAL: A headline, not a rule") == "THE SIGNAL"


def test_extract_kicker_preserves_original_casing() -> None:
    """Extraction returns the deck's own casing verbatim -- normalization
    for matching happens separately in _normalize_kicker."""
    assert _extract_take_kicker("Our read: the door got selective") == "Our read"


def test_extract_kicker_no_colon_short_headline_uses_whole_headline() -> None:
    """No colon, <=5 words -> the whole headline is treated as the kicker."""
    assert _extract_take_kicker("The Upshot Today") == "The Upshot Today"


def test_extract_kicker_no_colon_long_headline_is_skipped() -> None:
    """No colon, >5 words -> not a kicker shape, skip (None)."""
    headline = "This headline has more than five words total"
    assert len(headline.split()) > 5
    assert _extract_take_kicker(headline) is None


def test_extract_kicker_long_colon_prefix_is_skipped() -> None:
    """A >5-word prefix before the colon is not a 2-5 word kicker -- skip
    rather than mis-signature it."""
    headline = "This is a really really long kicker prefix here: the rest"
    prefix = headline.partition(":")[0]
    assert len(prefix.split()) > 5
    assert _extract_take_kicker(headline) is None


def test_extract_kicker_empty_headline_returns_none() -> None:
    assert _extract_take_kicker("") is None
    assert _extract_take_kicker(None) is None  # type: ignore[arg-type]


def test_extract_kicker_single_word_colon_prefix_is_skipped() -> None:
    """2026-07-20 red-team MINOR #6: a ONE-word prefix before the colon is a
    scene-setter/dateline, not a kicker (rule #7's kicker is always a short
    PHRASE, 2-5 words). 'BALI: THE DOOR JUST CLOSED' must be skipped."""
    assert _extract_take_kicker("BALI: THE DOOR JUST CLOSED") is None


def test_extract_kicker_two_word_colon_prefix_is_kept() -> None:
    """Lower bound is 2, not 3 -- a legitimate 2-word kicker still extracts."""
    assert _extract_take_kicker("THE CATCH: something happened") == "THE CATCH"


def test_extract_kicker_fullwidth_colon_is_caught() -> None:
    """2026-07-20 red-team MINOR #5: a fullwidth colon (U+FF1A) NFKC-folds
    to ASCII ':' -- must not bypass extraction. Returned text comes from the
    NFKC-normalized string (casing untouched)."""
    headline = "THE SIGNAL： fresh angle"  # U+FF1A fullwidth colon
    assert _extract_take_kicker(headline) == "THE SIGNAL"


# ─────────────────────────────────────────────────────────────────────────
# _normalize_kicker
# ─────────────────────────────────────────────────────────────────────────

def test_normalize_kicker_case_and_trailing_punct() -> None:
    assert _normalize_kicker("THE SIGNAL:") == _normalize_kicker("the signal")


def test_normalize_kicker_nbsp_folds_to_space() -> None:
    """NFKC folds NBSP (U+00A0) to a plain space before whitespace collapse."""
    nbsp_variant = "THE SIGNAL"
    assert _normalize_kicker(nbsp_variant) == _normalize_kicker("THE SIGNAL")


def test_normalize_kicker_never_touches_internal_punctuation() -> None:
    """Internal hyphen ('THE TRADE-OFF') is not a terminal char, must survive."""
    assert "-" in _normalize_kicker("THE TRADE-OFF")


# ─────────────────────────────────────────────────────────────────────────
# _kicker_collision -- GUILT (must fire)
# ─────────────────────────────────────────────────────────────────────────

def _take_slide(headline: str) -> dict:
    return {"slide_type": "take", "headline": headline}


def test_collision_guilt_plain_match() -> None:
    slides = [_take_slide("The Signal: fresh angle")]
    hit = _kicker_collision(slides, ["THE SIGNAL"])
    assert hit == "The Signal"  # verbatim, this deck's own casing


def test_collision_guilt_recent_has_trailing_colon() -> None:
    """Robustness: the recorded recent kicker itself carries a trailing
    colon (e.g. extracted sloppily upstream) -- normalization strips it on
    both sides, so the match still fires."""
    slides = [_take_slide("The Signal: fresh angle")]
    hit = _kicker_collision(slides, ["THE SIGNAL:"])
    assert hit == "The Signal"


def test_collision_guilt_nbsp_variant() -> None:
    """Robustness: an NBSP standing in for a space in the recent history
    must not defeat the match (NFKC-fold, mirrors composer.py's guard)."""
    slides = [_take_slide("The Signal: fresh angle")]
    hit = _kicker_collision(slides, ["THE SIGNAL"])
    assert hit == "The Signal"


def test_collision_guilt_fullwidth_colon_deck_headline() -> None:
    """2026-07-20 red-team MAJOR #4 item (d): the NEW deck's headline uses a
    fullwidth colon -- extraction must still catch it (MINOR #5), and the
    resulting kicker must still collide against the recent history."""
    slides = [_take_slide("THE SIGNAL： a fresh spin")]
    hit = _kicker_collision(slides, ["THE SIGNAL"])
    assert hit == "THE SIGNAL"


# ─────────────────────────────────────────────────────────────────────────
# _kicker_collision -- INNOCENCE (must NOT fire, whole-string only)
# ─────────────────────────────────────────────────────────────────────────

def test_collision_innocence_unrelated_kicker() -> None:
    slides = [_take_slide("The Precedent: a different angle")]
    assert _kicker_collision(slides, ["THE SIGNAL"]) is None


def test_collision_innocence_substring_not_whole_word() -> None:
    """'TAKEAWAY FOR SELLERS' contains 'TAKE' as a substring but must not
    collide with a recent kicker 'TAKE' -- whole-string only (scar family #3)."""
    slides = [_take_slide("TAKEAWAY FOR SELLERS")]
    assert _kicker_collision(slides, ["TAKE"]) is None


def test_collision_innocence_superset_phrase() -> None:
    """'THE SIGNAL TODAY' must not collide with 'THE SIGNAL' -- whole-string,
    not prefix/contains match."""
    slides = [_take_slide("THE SIGNAL TODAY")]
    assert _kicker_collision(slides, ["THE SIGNAL"]) is None


def test_collision_innocence_no_recent_history() -> None:
    slides = [_take_slide("THE SIGNAL: fresh")]
    assert _kicker_collision(slides, []) is None


def test_collision_innocence_non_take_slide_ignored() -> None:
    """A slide that happens to contain a colliding headline but is NOT a
    take-slide must not trigger collision (only slide_type == 'take' counts)."""
    slides = [{"slide_type": "body", "headline": "THE SIGNAL: not actually a take"}]
    assert _kicker_collision(slides, ["THE SIGNAL"]) is None


def test_collision_innocence_single_word_colon_prefix() -> None:
    """2026-07-20 red-team MAJOR #4 item (e): 'BALI: THE DOOR JUST CLOSED'
    has a 1-word colon-prefix -- not extracted as a kicker at all (MINOR
    #6), so it can never collide, even against a maximally-permissive
    recent list."""
    slides = [_take_slide("BALI: THE DOOR JUST CLOSED")]
    assert _kicker_collision(slides, ["BALI", "THE DOOR JUST CLOSED"]) is None


# ─────────────────────────────────────────────────────────────────────────
# _build_variety_steer
# ─────────────────────────────────────────────────────────────────────────

def test_variety_steer_empty_history_is_empty_string() -> None:
    assert _build_variety_steer({"kickers": [], "subheads": []}) == ""


def test_variety_steer_contains_kickers_and_subheads() -> None:
    sig = {"kickers": ["THE SIGNAL", "THE UPSHOT"], "subheads": ["VISA UPDATE"]}
    steer = _build_variety_steer(sig)
    assert "THE SIGNAL" in steer
    assert "THE UPSHOT" in steer
    assert "VISA UPDATE" in steer
    assert "MUST NOT" in steer  # kicker line is a hard ban in prompt language


def test_variety_steer_kickers_only() -> None:
    steer = _build_variety_steer({"kickers": ["THE SIGNAL"], "subheads": []})
    assert "THE SIGNAL" in steer
    assert steer  # non-empty


def test_variety_steer_subheads_only() -> None:
    steer = _build_variety_steer({"kickers": [], "subheads": ["TAX ALERT"]})
    assert "TAX ALERT" in steer
    assert steer


def test_variety_steer_caps_kicker_list_at_12() -> None:
    """2026-07-20 red-team MAJOR #4 item (g) / MINOR #8: the MUST-NOT list
    is capped at _VARIETY_STEER_KICKER_CAP (12) even when the fetched
    history carries more -- and the stated count in the sentence matches
    the CAPPED length, not the raw one."""
    assert _VARIETY_STEER_KICKER_CAP == 12
    many_kickers = [f"KICKER NUMBER {i}" for i in range(20)]
    steer = _build_variety_steer({"kickers": many_kickers, "subheads": []})
    for k in many_kickers[:12]:
        assert k in steer
    for k in many_kickers[12:]:
        assert k not in steer
    assert "the last 12 take-slide kickers" in steer


# ─────────────────────────────────────────────────────────────────────────
# _sample_kickers / _render_kicker_examples -- example rotation / de-anchoring
# ─────────────────────────────────────────────────────────────────────────

def test_render_examples_excludes_recent_kicker() -> None:
    random.seed(1)
    rendered = _render_kicker_examples(["THE SIGNAL"])
    assert '"THE SIGNAL"' not in rendered


def test_render_examples_returns_exactly_three() -> None:
    random.seed(2)
    rendered = _render_kicker_examples([])
    # Each example is a quoted phrase separated by ", " -- count the quoted groups.
    assert rendered.count('"') == 6  # 3 examples * 2 quote chars each


def test_render_examples_deterministic_with_seeded_random() -> None:
    random.seed(42)
    first = _render_kicker_examples(["THE SIGNAL"])
    random.seed(42)
    second = _render_kicker_examples(["THE SIGNAL"])
    assert first == second


def test_render_examples_all_entries_come_from_vocabulary() -> None:
    random.seed(3)
    rendered = _render_kicker_examples([])
    normalized_vocab = {_normalize_kicker(k) for k in KICKER_EXAMPLE_VOCABULARY}
    for part in rendered.split(", "):
        stripped = part.strip('"')
        assert _normalize_kicker(stripped) in normalized_vocab


def test_render_examples_exhausted_pool_returns_empty_string() -> None:
    """2026-07-20 red-team MAJOR #4 item (f) / MINOR #7: when recent history
    covers the ENTIRE vocabulary, _render_kicker_examples must return "" --
    NEVER fall back to sampling from the (recently-used) full vocabulary,
    which would silently reintroduce a banned kicker as a "suggestion"."""
    rendered = _render_kicker_examples(list(KICKER_EXAMPLE_VOCABULARY))
    assert rendered == ""


def test_sample_kickers_exhausted_pool_returns_empty_list() -> None:
    assert _sample_kickers(list(KICKER_EXAMPLE_VOCABULARY), 3) == []
    assert _sample_kickers(list(KICKER_EXAMPLE_VOCABULARY), 1) == []


def test_render_system_instructions_degrades_gracefully_when_exhausted() -> None:
    """The rule #7 sentence stays grammatical (no bare 'e.g.  --') when the
    example pool is exhausted -- MINOR #7's degrade-instead-of-empty policy."""
    prompt = _build_draft_prompt(
        topic="X", summary="body", source_url="",
        recent_kickers=list(KICKER_EXAMPLE_VOCABULARY),
    )
    assert "e.g.  —" not in prompt
    assert "used up the usual examples" in prompt


# ─────────────────────────────────────────────────────────────────────────
# _render_schema_kicker -- Structure JSON example de-anchor (MAJOR #3)
# ─────────────────────────────────────────────────────────────────────────

def test_schema_kicker_excludes_recent_history() -> None:
    """2026-07-20 red-team MAJOR #4 item (h): the Structure JSON example's
    take-slide kicker must never render a recently-used kicker. Repeated
    with many seeds to make a false pass (lucky sample) implausible."""
    for seed in range(20):
        random.seed(seed)
        kicker = _render_schema_kicker(["THE SIGNAL"])
        assert _normalize_kicker(kicker) != _normalize_kicker("THE SIGNAL")


def test_schema_kicker_falls_back_to_generic_label_when_exhausted() -> None:
    kicker = _render_schema_kicker(list(KICKER_EXAMPLE_VOCABULARY))
    assert kicker == dg._SCHEMA_KICKER_FALLBACK
    # The fallback is definitionally not IN the vocabulary, so it can never
    # coincide with an actual recently-used kicker.
    assert _normalize_kicker(kicker) not in {
        _normalize_kicker(k) for k in KICKER_EXAMPLE_VOCABULARY
    }


def test_build_draft_prompt_exhausted_pool_schema_uses_angle_bracket_placeholder() -> None:
    """2026-07-20 red-team round-3 item (c): the round-1 fallback
    "YOUR FRESH KICKER" was ITSELF a static, teachable-looking string never
    checked against history. Locked down as fixed: on an exhausted pool the
    rendered Structure JSON schema line must carry the angle-bracket
    TEMPLATE SLOT (unambiguously "fill this in", not a candidate kicker),
    never the old literal fallback, and never any real vocabulary entry
    (which would defeat the whole de-anchoring point)."""
    prompt = _build_draft_prompt(
        topic="X", summary="body", source_url="",
        recent_kickers=list(KICKER_EXAMPLE_VOCABULARY),
    )
    assert '"headline": "<COIN A FRESH 2-4 WORD KICKER>: ...",' in prompt
    assert "YOUR FRESH KICKER" not in prompt
    for vocab_kicker in KICKER_EXAMPLE_VOCABULARY:
        assert f'"headline": "{vocab_kicker}: ...",' not in prompt


def test_build_draft_prompt_schema_headline_never_renders_recent_kicker() -> None:
    """End-to-end: the FULL rendered prompt's Structure JSON example must
    not contain the recently-used kicker as its take-slide headline."""
    for seed in range(10):
        random.seed(seed)
        prompt = _build_draft_prompt(
            topic="X", summary="body", source_url="", recent_kickers=["THE SIGNAL"],
        )
        assert '"headline": "THE SIGNAL: ...",' not in prompt


# ─────────────────────────────────────────────────────────────────────────
# _build_draft_prompt wiring -- both tokens resolved, examples threaded
# ─────────────────────────────────────────────────────────────────────────

def test_build_draft_prompt_threads_recent_kickers_into_examples() -> None:
    random.seed(7)
    expected_examples = _render_kicker_examples(["THE SIGNAL"])
    random.seed(7)
    prompt = _build_draft_prompt(
        topic="X", summary="body", source_url="", recent_kickers=["THE SIGNAL"],
    )
    assert expected_examples in prompt


def test_build_draft_prompt_default_recent_kickers_is_none_safe() -> None:
    """Existing call sites (no recent_kickers arg) must keep working, and
    BOTH placeholder tokens must always be resolved."""
    prompt = _build_draft_prompt(topic="X", summary="body", source_url="")
    assert "__KICKER_EXAMPLES__" not in prompt
    assert "__KICKER_EXAMPLE_TAKE__" not in prompt


def test_build_draft_prompt_kicker_word_count_guidance_is_2_to_4() -> None:
    """2026-07-20 red-team MINOR #9: the vocabulary includes 4-word entries
    ('READ THE FINE PRINT') -- rule #7's stated word-count range must say
    2-4, not the old (too-narrow) 2-3."""
    prompt = _build_draft_prompt(topic="X", summary="body", source_url="")
    assert "2-4 words" in prompt
    assert "2-3 words" not in prompt


# ─────────────────────────────────────────────────────────────────────────
# fetch_recent_editorial_signatures -- DB best-effort + per-row isolation
# ─────────────────────────────────────────────────────────────────────────

def _slides_row(slides: list[dict], *, as_json_string: bool = False):
    blob = {"slides": slides}
    return {"slides_json": json.dumps(blob) if as_json_string else blob}


@pytest.mark.asyncio
async def test_fetch_signatures_extracts_kickers_and_subheads() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            _slides_row(
                [
                    {"slide_type": "cover", "is_cover": True, "subhead": "VISA UPDATE"},
                    {"slide_type": "take", "headline": "THE SIGNAL: a fresh angle"},
                ]
            ),
        ]
    )
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig["kickers"] == ["THE SIGNAL"]
    assert sig["subheads"] == ["VISA UPDATE"]


@pytest.mark.asyncio
async def test_fetch_signatures_handles_json_string_slides_json() -> None:
    """slides_json may arrive as a JSON string from asyncpg (no jsonb codec
    registered on this connection) -- mirrors wr2_daily_reconciler.py /
    wr2_fact_checker.py's defensive isinstance(str) parsing."""
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            _slides_row(
                [{"slide_type": "take", "headline": "THE UPSHOT: something"}],
                as_json_string=True,
            ),
        ]
    )
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig["kickers"] == ["THE UPSHOT"]


@pytest.mark.asyncio
async def test_fetch_signatures_case_insensitive_dedup_keeps_first_casing_and_order() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            _slides_row([{"slide_type": "take", "headline": "The Signal: first"}]),
            _slides_row([{"slide_type": "take", "headline": "THE SIGNAL: duplicate"}]),
            _slides_row([{"slide_type": "take", "headline": "The Upshot: second"}]),
        ]
    )
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    # Dedup keeps the FIRST occurrence's casing; order preserved (newest-first
    # is the row order the SQL already sorts by, this function just doesn't
    # reorder further).
    assert sig["kickers"] == ["The Signal", "The Upshot"]


@pytest.mark.asyncio
async def test_fetch_signatures_best_effort_on_fetch_exception() -> None:
    """conn.fetch raising -> empty shape, no exception propagates."""
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=RuntimeError("connection reset"))
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig == {"kickers": [], "subheads": []}


@pytest.mark.asyncio
async def test_fetch_signatures_best_effort_on_malformed_json() -> None:
    """A row whose slides_json string doesn't parse must not crash the
    whole lookback -- best-effort degrade to empty (single-row case)."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"slides_json": "{not valid json"}])
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig == {"kickers": [], "subheads": []}


@pytest.mark.asyncio
async def test_fetch_signatures_empty_rows_returns_empty_shape() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig == {"kickers": [], "subheads": []}


@pytest.mark.asyncio
async def test_fetch_signatures_mixed_good_malformed_good_keeps_both_good_rows() -> None:
    """2026-07-20 red-team MAJOR #4 item (c) / MAJOR #2: per-row isolation.
    Row order is good -> malformed -> good; the malformed row (index 1)
    must be skipped WITHOUT wiping the surrounding good rows' kickers. The
    OLD single try/except-around-the-whole-loop shape would have zeroed
    out ALL THREE rows' worth of history on this exact input."""
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            _slides_row([{"slide_type": "take", "headline": "THE UPSHOT: first good row"}]),
            {"slides_json": "{not valid json at all"},
            _slides_row([{"slide_type": "take", "headline": "THE PRECEDENT: second good row"}]),
        ]
    )
    sig = await fetch_recent_editorial_signatures(conn, limit=10)
    assert sig["kickers"] == ["THE UPSHOT", "THE PRECEDENT"]


# ─────────────────────────────────────────────────────────────────────────
# Regen wiring -- unified escalation accumulation (MAJOR #1)
# ─────────────────────────────────────────────────────────────────────────

def _fake_slides_response(
    take_headline: str = "Headline 2", closer_body: str = "Short close now."
) -> dict:
    return {
        "register": "analitico",
        "register_reason": "test",
        "slides": [
            {
                "slide_number": i,
                "slide_type": "cover" if i == 1 else ("take" if i == 2 else ("cta" if i == 6 else "body")),
                "is_cover": i == 1,
                "is_hero_image": i == 1,
                "headline": take_headline if i == 2 else f"Headline {i}",
                "subhead": "TEST TAG" if i == 1 else "",
                "body": (closer_body if i == 6 else f"Body copy for slide {i}."),
                "image_prompt": "editorial scene" if i == 1 else "",
            }
            for i in range(1, 7)
        ],
    }


def _base_row(draft_id: uuid.UUID) -> dict:
    return {
        "id": draft_id,
        "topic": "New KITAS Rule Takes Effect",
        "brief_json": {
            "article_summary": "A concrete news event happened today with real facts.",
            "enrichment": {},
            "staging_type": "regulation",
            "liveness_tier": None,
            "source_url": "https://example.com",
        },
    }


def _wire_process_one_mocks(monkeypatch: pytest.MonkeyPatch, compose_mock: AsyncMock) -> None:
    monkeypatch.setattr(dg, "claude_compose_slides", compose_mock)
    monkeypatch.setattr(dg, "generate_cover_image", AsyncMock(return_value=(None, "skip-in-test")))
    monkeypatch.setattr(dg, "_send_telegram", MagicMock())
    monkeypatch.setattr(dg.wom, "resolve_carousel_id", AsyncMock(return_value="cid-test"))
    monkeypatch.setattr(dg.wom, "record_step", AsyncMock())


@pytest.mark.asyncio
async def test_process_one_regenerates_on_kicker_collision_then_accepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loop-level integration (mirrors the B2 _process_one pattern in
    test_wr2_draft_generator_enriched_prompt.py): the DB lookback reports
    'THE SIGNAL' as a recently-used kicker; the first compose attempt
    reuses it (collision -> regen); the second attempt coins a fresh
    kicker -> accepted. Proves the guard fires even though
    WR2_ANTIMONOTONE_ENFORCE defaults to off (this guard is unconditional)."""
    draft_id = uuid.uuid4()
    row = _base_row(draft_id)

    conn = MagicMock()
    conn.execute = AsyncMock()

    async def _fetch_side_effect(sql, *args, **kwargs):  # noqa: ANN001, ARG001
        if "slides_json" in sql:
            return [_slides_row([{"slide_type": "take", "headline": "THE SIGNAL: prior"}])]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch_side_effect)

    compose_mock = AsyncMock(
        side_effect=[
            _fake_slides_response("THE SIGNAL: reused kicker"),  # attempt 1: collides
            _fake_slides_response("THE UPSHOT: fresh angle"),  # attempt 2: fresh
        ]
    )
    _wire_process_one_mocks(monkeypatch, compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    assert compose_mock.await_count == 2

    second_call_kwargs = compose_mock.await_args_list[1].kwargs
    assert "THE SIGNAL" in second_call_kwargs["avoid_steer"]
    assert "reused the kicker" in second_call_kwargs["avoid_steer"]

    persist_calls = [c for c in conn.execute.call_args_list if "status" in c.args[0]]
    assert any("'drafts'" in c.args[0] for c in persist_calls)


@pytest.mark.asyncio
async def test_process_one_closer_and_kicker_both_fire_no_starvation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-07-20 red-team MAJOR #4 item (a): the FIRST attempt has BOTH a
    too-long closer AND a colliding kicker. The OLD structure's closer
    guard `continue`d immediately, so the kicker guard never ran on that
    attempt's output and the model never learned about the collision. The
    FIXED structure evaluates every guard before deciding, so the SECOND
    attempt's prompt must carry BOTH escalation messages."""
    draft_id = uuid.uuid4()
    row = _base_row(draft_id)

    conn = MagicMock()
    conn.execute = AsyncMock()

    async def _fetch_side_effect(sql, *args, **kwargs):  # noqa: ANN001, ARG001
        if "slides_json" in sql:
            return [_slides_row([{"slide_type": "take", "headline": "THE SIGNAL: prior"}])]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch_side_effect)

    long_closer = " ".join(f"word{i}" for i in range(dg.CLOSER_MAX_WORDS + 5))
    compose_mock = AsyncMock(
        side_effect=[
            # attempt 1: closer too long AND kicker collides
            _fake_slides_response("THE SIGNAL: reused kicker", closer_body=long_closer),
            # attempt 2: both fixed -> accepted
            _fake_slides_response("THE UPSHOT: fresh angle", closer_body="Short close now."),
        ]
    )
    _wire_process_one_mocks(monkeypatch, compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    assert compose_mock.await_count == 2

    second_call_steer = compose_mock.await_args_list[1].kwargs["avoid_steer"]
    # No starvation: BOTH the closer escalation AND the kicker escalation
    # are present in the SAME retry prompt.
    assert "closer" in second_call_steer.lower()
    assert "reused the kicker" in second_call_steer
    assert "THE SIGNAL" in second_call_steer


@pytest.mark.asyncio
async def test_process_one_antimonotone_regen_preserves_editorial_variety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-07-20 red-team MAJOR #4 item (b): after an anti-sameness-style
    regen, the retry prompt must STILL contain the EDITORIAL VARIETY block.
    The OLD code rebuilt `avoid_steer = _build_avoid_steer(recent) + (...)`
    from scratch on an anti-sameness collision, silently dropping the
    editorial-variety steer computed before the loop -- a "steer reset" bug
    this test locks down as fixed (base_steer is now immutable inside the
    loop; only `escalations` accumulates)."""
    draft_id = uuid.uuid4()
    row = _base_row(draft_id)

    conn = MagicMock()
    conn.execute = AsyncMock()

    async def _fetch_side_effect(sql, *args, **kwargs):  # noqa: ANN001, ARG001
        if "slides_json" in sql:
            # Non-empty editorial history -> _build_variety_steer produces a
            # real EDITORIAL VARIETY block (kicker chosen so it never
            # collides with either fake response's headline below).
            return [_slides_row([{"slide_type": "take", "headline": "THE CATCH: prior"}])]
        if "topic_type_log" in sql:
            return [{"register": "analitico", "dominant_mode": "event-photo"}]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch_side_effect)

    monkeypatch.setenv("WR2_ANTIMONOTONE_ENFORCE", "true")
    monkeypatch.setattr(dg.tt, "derive_domain", lambda topic: "visa")  # noqa: ARG005
    monkeypatch.setattr(dg.tt, "derive_dominant_mode", lambda slides_json: "event-photo")  # noqa: ARG005

    collide_calls = {"n": 0}

    def _collides(register, dominant_mode, recent):  # noqa: ARG001
        collide_calls["n"] += 1
        return collide_calls["n"] == 1  # collide on attempt 1 only

    monkeypatch.setattr(dg.tt, "collides_with_recent", _collides)

    compose_mock = AsyncMock(
        side_effect=[
            _fake_slides_response("THE UPSHOT: attempt one"),
            _fake_slides_response("THE PRECEDENT: attempt two"),
        ]
    )
    _wire_process_one_mocks(monkeypatch, compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    assert compose_mock.await_count == 2

    second_call_steer = compose_mock.await_args_list[1].kwargs["avoid_steer"]
    assert "EDITORIAL VARIETY" in second_call_steer
    assert "THE CATCH" in second_call_steer
    assert "forbidden combination" in second_call_steer  # antimonotone escalation present too


@pytest.mark.asyncio
async def test_process_one_multi_guard_escalation_not_exclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-07-20 red-team round-3 item (a) (MAJOR #1 residue): when BOTH
    the closer guard and the kicker guard fire on the same attempt, the
    closer escalation must NOT claim exclusivity ("Rewrite ONLY the
    closer") -- that wording contradicts the kicker escalation riding the
    SAME retry prompt, which also demands a change. The retry prompt must
    carry BOTH instructions without either claiming to be the only one."""
    draft_id = uuid.uuid4()
    row = _base_row(draft_id)

    conn = MagicMock()
    conn.execute = AsyncMock()

    async def _fetch_side_effect(sql, *args, **kwargs):  # noqa: ANN001, ARG001
        if "slides_json" in sql:
            return [_slides_row([{"slide_type": "take", "headline": "THE SIGNAL: prior"}])]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch_side_effect)

    long_closer = " ".join(f"word{i}" for i in range(dg.CLOSER_MAX_WORDS + 5))
    compose_mock = AsyncMock(
        side_effect=[
            _fake_slides_response("THE SIGNAL: reused kicker", closer_body=long_closer),
            _fake_slides_response("THE UPSHOT: fresh angle", closer_body="Short close now."),
        ]
    )
    _wire_process_one_mocks(monkeypatch, compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    assert compose_mock.await_count == 2

    second_call_steer = compose_mock.await_args_list[1].kwargs["avoid_steer"]
    assert "ONLY the closer" not in second_call_steer
    # Both escalations are still present -- dropping "ONLY" must not have
    # silently dropped the CONTENT of the closer guidance either.
    assert "Rewrite the closer" in second_call_steer
    assert "reused the kicker" in second_call_steer


@pytest.mark.asyncio
async def test_process_one_resolved_guard_escalation_cleared_next_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-07-20 red-team round-3 item (b) (MINOR "clear-on-pass"):
    attempt 0 has a too-long closer (fires) with a fresh kicker (passes).
    Attempt 1 fixes the closer (passes) but reuses a kicker (fires). The
    THIRD attempt's prompt must NOT carry attempt 0's now-stale closer
    escalation (which would misdescribe attempt 1 -- its closer was fine)
    but MUST carry the live kicker escalation from attempt 1."""
    draft_id = uuid.uuid4()
    row = _base_row(draft_id)

    conn = MagicMock()
    conn.execute = AsyncMock()

    async def _fetch_side_effect(sql, *args, **kwargs):  # noqa: ANN001, ARG001
        if "slides_json" in sql:
            return [_slides_row([{"slide_type": "take", "headline": "THE SIGNAL: prior"}])]
        return []

    conn.fetch = AsyncMock(side_effect=_fetch_side_effect)

    long_closer = " ".join(f"word{i}" for i in range(dg.CLOSER_MAX_WORDS + 5))
    compose_mock = AsyncMock(
        side_effect=[
            # attempt 0: closer too long, kicker fresh -> only "closer" fires
            _fake_slides_response("THE UPSHOT: attempt zero", closer_body=long_closer),
            # attempt 1: closer fixed, kicker reused -> "closer" resolved, "kicker" fires
            _fake_slides_response("THE SIGNAL: attempt one", closer_body="Short close now."),
            # attempt 2: both fine -> accepted
            _fake_slides_response("THE PRECEDENT: attempt two", closer_body="Short close now."),
        ]
    )
    _wire_process_one_mocks(monkeypatch, compose_mock)

    outcome = await dg._process_one(conn, row)

    assert outcome == "success"
    assert compose_mock.await_count == 3

    third_call_steer = compose_mock.await_args_list[2].kwargs["avoid_steer"]
    # The resolved closer objection from attempt 0 must be GONE.
    assert "Rewrite the closer" not in third_call_steer
    assert "was too long" not in third_call_steer
    # The live kicker objection from attempt 1 must still be present.
    assert "reused the kicker" in third_call_steer
    assert "THE SIGNAL" in third_call_steer
