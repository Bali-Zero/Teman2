"""
Tests for the enriched-prompt bug fix in scripts/wr2_draft_generator.py.

Locks down PR-1 §C bug fix: when an enrichment object is available and the
WR2_USE_FULL_ENRICHED_PROMPT flag is on, the draft prompt is built from the
structured 1400-2000-word enrichment fields instead of summary[:3500].

The previous behavior shipped only 25% of the available material to Claude;
this fix is the difference between "11 slides built on a paragraph" and
"11 slides built on the_facts + bali_zero_take + in_practice + next_steps + faq".

These tests don't call Claude — they verify the prompt construction
deterministically, which is the unit boundary we control.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

# wr2_draft_generator imports asyncpg/httpx at module load. Both are in the
# backend-rag venv → available when run via PYTHONPATH=. + venv python.
SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from wr2_draft_generator import _build_draft_prompt, _build_enriched_brief  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# _build_enriched_brief
# ─────────────────────────────────────────────────────────────────────────

def test_enriched_brief_renders_all_sections() -> None:
    """Full enrichment object → all 6 section labels appear in output."""
    enrichment = {
        "thirty_second_brief": {
            "what": "BKPM raided unlicensed PMAs",
            "why_it_matters": "Compliance risk for foreign investors",
            "who": "Foreign-owned PT PMA without OSS",
            "risk_level": "high",
        },
        "the_facts": "Paragraph 1.\n\nParagraph 2.",
        "bali_zero_take": "Editorial perspective.",
        "in_practice": "What expats should do.",
        "next_steps": "Action items.",
        "faq": [
            {"question": "Q1?", "answer": "A1."},
            {"question": "Q2?", "answer": "A2."},
        ],
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "30-second brief" in brief
    assert "The facts" in brief
    assert "Bali Zero editorial take" in brief
    assert "In practice" in brief
    assert "Next steps" in brief
    assert "FAQ" in brief


def test_enriched_brief_includes_field_content() -> None:
    """Verbatim content from each field must appear in the rendered brief."""
    enrichment = {
        "the_facts": "BKPM published Reg 5/2026 on 2026-04-23.",
        "bali_zero_take": "This shifts the compliance burden to consultants.",
        "next_steps": "Audit OSS status within 30 days.",
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Reg 5/2026 on 2026-04-23" in brief
    assert "compliance burden to consultants" in brief
    assert "Audit OSS status within 30 days" in brief


def test_enriched_brief_handles_empty_enrichment() -> None:
    """Empty dict → empty brief (caller falls back to summary path)."""
    assert _build_enriched_brief({}, live_reasons=None) == ""
    assert _build_enriched_brief({"unknown_field": "noise"}, live_reasons=None) == ""


def test_enriched_brief_skips_missing_sections() -> None:
    """Partial enrichment renders only the sections that exist."""
    brief = _build_enriched_brief(
        {"the_facts": "Only the facts here.", "in_practice": ""},
        live_reasons=None,
    )
    assert "The facts" in brief
    assert "Only the facts here." in brief
    # No bali_zero_take / next_steps / faq → labels absent
    assert "Bali Zero editorial take" not in brief
    assert "Next steps" not in brief
    assert "FAQ" not in brief


def test_enriched_brief_thirty_second_partial_fields() -> None:
    """Partial 30-second brief renders only present subfields."""
    brief = _build_enriched_brief(
        {"thirty_second_brief": {"what": "Decree published", "risk_level": "medium"}},
        live_reasons=None,
    )
    assert "What: Decree published" in brief
    assert "Risk level: medium" in brief
    assert "Why it matters" not in brief
    assert "Who is affected" not in brief


def test_enriched_brief_appends_live_reasons() -> None:
    enrichment = {"the_facts": "Facts."}
    brief = _build_enriched_brief(
        enrichment,
        live_reasons=[
            "BKPM Reg 5/2026 published 2026-04-23",
            "Deportation of 12 nationals 2026-04-25",
        ],
    )
    assert "Live news signals" in brief
    assert "BKPM Reg 5/2026 published 2026-04-23" in brief
    assert "Deportation of 12 nationals 2026-04-25" in brief


def test_enriched_brief_caps_live_reasons_at_three() -> None:
    brief = _build_enriched_brief(
        {"the_facts": "Facts."},
        live_reasons=["one", "two", "three", "four", "five"],
    )
    assert "one" in brief
    assert "three" in brief
    assert "four" not in brief
    assert "five" not in brief


def test_enriched_brief_empty_live_reasons_no_section() -> None:
    """Empty list → no Live news signals section (avoid empty header)."""
    brief = _build_enriched_brief({"the_facts": "Facts."}, live_reasons=[])
    assert "Live news signals" not in brief


def test_enriched_brief_caps_faq_at_six() -> None:
    enrichment = {
        "faq": [{"question": f"Q{i}?", "answer": f"A{i}."} for i in range(10)]
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Q5?" in brief
    assert "Q6?" not in brief


def test_enriched_brief_skips_malformed_faq_entries() -> None:
    enrichment = {
        "faq": [
            {"question": "Q1?", "answer": "A1."},
            "not a dict",
            {"question": "", "answer": "missing question"},
            {"question": "Q4?", "answer": "A4."},
        ],
    }
    brief = _build_enriched_brief(enrichment, live_reasons=None)
    assert "Q1?" in brief
    assert "Q4?" in brief
    assert "missing question" not in brief


# ─────────────────────────────────────────────────────────────────────────
# _build_draft_prompt — flag gating
# ─────────────────────────────────────────────────────────────────────────

def test_legacy_path_used_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default behavior: enriched ignored, summary[:3500] used. Preserves
    pre-§C behavior for safe rollback."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    enrichment = {
        "the_facts": "ENRICHED FACT TEXT",
        "bali_zero_take": "ENRICHED TAKE",
    }
    prompt = _build_draft_prompt(
        topic="Test topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=enrichment,
        live_reasons=["should not appear"],
    )
    assert "LEGACY SUMMARY CONTENT" in prompt
    assert "ENRICHED FACT TEXT" not in prompt
    assert "ENRICHED TAKE" not in prompt


def test_enriched_path_used_when_flag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag on + enrichment present → prompt is built from structured fields."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enrichment = {
        "the_facts": "ENRICHED FACT TEXT",
        "bali_zero_take": "ENRICHED TAKE",
        "in_practice": "ENRICHED PRACTICE",
    }
    prompt = _build_draft_prompt(
        topic="Test topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=enrichment,
        live_reasons=None,
    )
    assert "ENRICHED FACT TEXT" in prompt
    assert "ENRICHED TAKE" in prompt
    assert "ENRICHED PRACTICE" in prompt
    # Section labels present → confirms _build_enriched_brief path was taken
    assert "The facts" in prompt
    assert "Bali Zero editorial take" in prompt


def test_falls_back_to_summary_when_flag_on_but_no_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on but enrichment empty → graceful fallback to summary path.

    Critical: items that pre-date §B (enrichment=None) must still produce a
    valid prompt instead of crashing or sending Claude an empty body.
    """
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    prompt = _build_draft_prompt(
        topic="Legacy topic",
        summary="LEGACY SUMMARY CONTENT",
        source_url="https://example.com",
        enrichment=None,
        live_reasons=None,
    )
    assert "LEGACY SUMMARY CONTENT" in prompt


def test_falls_back_to_summary_when_enrichment_is_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on but enrichment={} → also falls back to summary path."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    prompt = _build_draft_prompt(
        topic="t",
        summary="LEGACY SUMMARY CONTENT",
        source_url="",
        enrichment={},
        live_reasons=None,
    )
    assert "LEGACY SUMMARY CONTENT" in prompt


def test_summary_truncated_at_3500_in_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy invariant preserved: summary[:3500] cap stays in place to
    avoid blowing the context budget on the back-compat path."""
    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    long_summary = "x" * 5000 + "TAIL_MARKER"
    prompt = _build_draft_prompt(
        topic="t", summary=long_summary, source_url="",
        enrichment=None, live_reasons=None,
    )
    assert "TAIL_MARKER" not in prompt  # everything past 3500 is dropped


def test_enriched_prompt_is_substantially_longer_than_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of this bug fix: with the enriched object, the
    prompt body Claude sees is materially larger than ~3500 chars. We
    don't pin exact size (it's content-dependent), only that the
    enriched-mode prompt is meaningfully bigger than the legacy one
    on the same data — confirming we're shipping more material.
    """
    enrichment = {
        "thirty_second_brief": {
            "what": "What happened.",
            "why_it_matters": "Why it matters.",
            "who": "Who is affected.",
            "risk_level": "medium",
        },
        "the_facts": "x" * 1500,
        "bali_zero_take": "y" * 600,
        "in_practice": "z" * 600,
        "next_steps": "w" * 400,
        "faq": [{"question": f"Q{i}?", "answer": "a" * 100} for i in range(4)],
    }

    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "false")
    legacy = _build_draft_prompt(
        topic="t", summary="short summary", source_url="",
        enrichment=enrichment, live_reasons=None,
    )

    monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", "true")
    enriched = _build_draft_prompt(
        topic="t", summary="short summary", source_url="",
        enrichment=enrichment, live_reasons=None,
    )

    # System prompt is fixed ~2000 chars; only the body section changes
    # between modes. Enriched body must be substantially larger than the
    # legacy "short summary" path. We assert delta >= 3000 chars — enough
    # to confirm we're shipping the_facts + take + practice + steps + faq
    # instead of the truncated paragraph.
    assert len(enriched) - len(legacy) >= 3000
    assert len(enriched) > 4000  # crosses the 3500 ceiling the bug imposed


def test_topic_and_source_appear_in_both_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Common-prompt invariants: topic and source_url labels appear
    regardless of which body path was taken."""
    for flag in ("false", "true"):
        monkeypatch.setenv("WR2_USE_FULL_ENRICHED_PROMPT", flag)
        prompt = _build_draft_prompt(
            topic="My Topic",
            summary="summary",
            source_url="https://example.com/article",
            enrichment={"the_facts": "facts"},
            live_reasons=None,
        )
        assert "My Topic" in prompt
        assert "https://example.com/article" in prompt
