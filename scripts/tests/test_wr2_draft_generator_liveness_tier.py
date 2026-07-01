"""
Tests for A1 — liveness_tier propagation into the draft prompt.

The topic selector already writes liveness_tier into brief_json; the drafter
used to drop it. A1 wires it end-to-end: read → normalise → inject a one-line
editorial framing (NOT a length or tone constraint — that's A2/A3). These tests
verify the injection deterministically without calling Claude.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import (  # noqa: E402
    _LIVENESS_FRAMING,
    _build_draft_prompt,
    _normalise_liveness_tier,
    claude_compose_slides,
)


# ── normalisation ─────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("breaking", "breaking"),
        ("BREAKING", "breaking"),
        ("  Developing  ", "developing"),
        ("evergreen", "evergreen"),
        ("manual", ""),          # operator topics → no framing
        ("nonsense", ""),
        ("", ""),
        (None, ""),
        (123, ""),               # never raises on non-str
    ],
)
def test_normalise_liveness_tier(raw, expected) -> None:
    assert _normalise_liveness_tier(raw) == expected


# ── framing injection ─────────────────────────────────────────────────────
@pytest.mark.parametrize("tier", ["breaking", "developing", "evergreen"])
def test_valid_tier_injects_its_framing_line(tier) -> None:
    prompt = _build_draft_prompt(
        topic="X", summary="body text here", source_url="", liveness_tier=tier,
    )
    assert _LIVENESS_FRAMING[tier] in prompt
    # exactly one framing line — no cross-contamination between tiers
    others = [t for t in _LIVENESS_FRAMING if t != tier]
    for other in others:
        assert _LIVENESS_FRAMING[other] not in prompt


@pytest.mark.parametrize("tier", ["", "manual", "unknown"])
def test_absent_or_manual_tier_injects_no_framing(tier) -> None:
    prompt = _build_draft_prompt(
        topic="X", summary="body text here", source_url="", liveness_tier=tier,
    )
    for line in _LIVENESS_FRAMING.values():
        assert line not in prompt
    # the article still renders
    assert "ARTICLE TO TURN INTO A CAROUSEL" in prompt


def test_framing_is_context_only_not_a_length_or_tone_constraint() -> None:
    """A1 is framing, not A2/A3: the injected line must not dictate a slide count
    or a specific tone slug (those belong to later PRs)."""
    for line in _LIVENESS_FRAMING.values():
        low = line.lower()
        assert "slide" not in low  # no "use 5 slides" etc.
        for tone in ("rituale", "analitico", "ironico", "militante",
                     "pedagogico", "poetico", "tecnico"):
            assert tone not in low


def test_default_call_omits_tier_and_stays_backcompat() -> None:
    """Callers that don't pass liveness_tier get the old prompt (no framing)."""
    prompt = _build_draft_prompt(topic="X", summary="body", source_url="")
    for line in _LIVENESS_FRAMING.values():
        assert line not in prompt


# ── SSOT parity: drafter tier set must not drift from the selector's ───────
def test_tier_set_matches_selector_ssot() -> None:
    """cicatrix #9 guard: the drafter's LIVENESS_TIER_VALID must equal the
    selector's. If someone adds a tier on one side only, this fails loudly
    instead of silently dropping the new tier's framing."""
    import wr2_draft_generator as drafter
    import wr2_topic_selector as selector

    assert drafter.LIVENESS_TIER_VALID == selector.LIVENESS_TIER_VALID


# ── end-to-end: compose_slides forwards the tier to the prompt ─────────────
def test_compose_slides_forwards_tier_into_prompt() -> None:
    captured = {}

    class _Resp:
        text = '{"register": "analitico", "slides": []}'
        token_label = "test"

    async def _fake_complete(prompt, **kw):  # noqa: ANN001
        captured["prompt"] = prompt
        return _Resp()

    with patch("wr2_draft_generator.complete_async", new=AsyncMock(side_effect=_fake_complete)):
        import asyncio

        asyncio.run(
            claude_compose_slides(
                topic="New KITAS rule", summary="body", source_url="",
                liveness_tier="breaking",
            )
        )
    assert _LIVENESS_FRAMING["breaking"] in captured["prompt"]
