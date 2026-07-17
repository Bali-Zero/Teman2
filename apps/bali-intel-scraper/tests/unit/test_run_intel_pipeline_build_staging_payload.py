"""
Tests for build_staging_payload in run_intel_pipeline.

Locks down the payload-construction contract between the enricher's
live-news scoring output (art["enrichment"]) and the /api/intel/scraper/submit
staging payload — this is break #1 of the 3-break WR2 liveness chain
(scar family #9, cicatrix-superscar.md): the scraper silently dropped
live_news_score/liveness_tier/live_news_reasons even though the enricher
already computed them (claude_cli_enricher._normalize_live_news_fields).

build_staging_payload is a pure extraction of the dict-building portion of
step_publishing()'s _push() closure — no self, no I/O. The impure parts
(cover-image base64 file read, HTTP POST, Telegram notify, intel-lake
enqueue) stay inside _push().
"""
from __future__ import annotations

import sys
from pathlib import Path


# Add scripts dir to path so the module imports work standalone (the
# bali-intel-scraper package layout is script-based, not installed). Same
# pattern as test_claude_cli_enricher_live_news.py.
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from run_intel_pipeline import build_staging_payload  # type: ignore  # noqa: E402


def _base_art(**enrichment_overrides: object) -> dict:
    return {
        "title": "Fallback title",
        "url": "https://example.com/article",
        "source_name": "test-source",
        "tier": "T2",
        "qwen_score": 8,
        "qwen_category": "immigration",
        "enrichment": {
            "the_facts": "Facts go here.",
            "headline": "Enriched headline",
            **enrichment_overrides,
        },
    }


def test_payload_includes_live_news_fields_when_present() -> None:
    """GUILT: enrichment carrying the 3 live-news fields must appear
    verbatim in the payload sent to /api/intel/scraper/submit."""
    art = _base_art(
        live_news_score=85,
        liveness_tier="breaking",
        live_news_reasons=["official announcement", "effective today"],
    )

    payload = build_staging_payload(art)

    assert payload["live_news_score"] == 85
    assert payload["liveness_tier"] == "breaking"
    assert payload["live_news_reasons"] == ["official announcement", "effective today"]


def test_payload_omits_live_news_fields_when_absent() -> None:
    """INNOCENCE: art without enrichment live-news fields must NOT invent
    them — omit the keys entirely (backend applies defaults on its side)."""
    art = _base_art()

    payload = build_staging_payload(art)

    assert "live_news_score" not in payload
    assert "liveness_tier" not in payload
    assert "live_news_reasons" not in payload


def test_payload_defaults_liveness_tier_and_reasons_when_score_present_alone() -> None:
    """Guards against a malformed enrichment dict that has live_news_score
    but is missing liveness_tier/live_news_reasons — defaults kick in rather
    than propagating None or crashing."""
    art = _base_art(live_news_score=0)
    art["enrichment"].pop("liveness_tier", None)
    art["enrichment"].pop("live_news_reasons", None)

    payload = build_staging_payload(art)

    assert payload["live_news_score"] == 0
    assert payload["liveness_tier"] == "evergreen"
    assert payload["live_news_reasons"] == []


def test_payload_preserves_existing_fields_unchanged() -> None:
    """Byte-identical behavior for pre-existing fields (karpathy: no
    collateral changes from the extraction refactor)."""
    art = _base_art()
    art["seo"] = {"meta_title": "SEO title"}
    art["image_url"] = "https://example.com/cover.jpg"
    art["featured"] = True
    art["enrichment"]["thirty_second_brief"] = "Brief text"
    art["enrichment"]["faq"] = [{"q": "Q1", "a": "A1"}]
    art["enrichment"]["metadata"] = {"suggested_slug": "slug-here", "tags": ["tag1", "tag2"]}

    payload = build_staging_payload(art)

    assert payload["title"] == "Enriched headline"
    assert payload["content"] == "## Facts\n\nFacts go here."
    assert payload["category"] == "immigration"
    assert payload["source_name"] == "test-source"
    assert payload["source_url"] == "https://example.com/article"
    assert payload["relevance_score"] == 80
    assert payload["tier"] == "T2"
    assert payload["seo"] == {"meta_title": "SEO title"}
    assert payload["image_url"] == "https://example.com/cover.jpg"
    assert payload["brief"] == "Brief text"
    assert payload["faq"] == [{"q": "Q1", "a": "A1"}]
    assert payload["slug"] == "slug-here"
    assert payload["tags"] == ["tag1", "tag2"]
    assert payload["featured"] is True
    # cover_image_base64 is intentionally NOT built here — impure (file I/O),
    # stays in _push().
    assert "cover_image_base64" not in payload


def test_payload_falls_back_to_title_when_no_enrichment() -> None:
    """No enrichment dict at all (art["enrichment"] missing) must not
    crash — falls back to art["title"] / empty sections, matching the
    pre-existing legacy-format fallback."""
    art = {
        "title": "Raw title",
        "text": "Raw scraped text.",
        "source": "raw-source",
        "source_url": "https://example.com/raw",
    }

    payload = build_staging_payload(art)

    assert payload["title"] == "Raw title"
    assert "Raw scraped text." in payload["content"]
    assert "live_news_score" not in payload
