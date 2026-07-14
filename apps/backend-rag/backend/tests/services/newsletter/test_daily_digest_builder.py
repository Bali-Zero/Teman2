"""Tests for DailyDigestBuilder — freshness selection, scarce-day fallback."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.models import CrossDossierThesis
from backend.services.intel.dossier_models import IntelItemSummary
from backend.services.newsletter.builder import (
    DEFAULT_DAILY_SCARCE_FLOOR,
    DEFAULT_DAILY_THESES_MAX,
    DEFAULT_DAILY_TOTAL_MAX,
    DailyDigestBuilder,
    _clean_summary,
    _domain_tag_for,
)


def _now() -> datetime:
    return datetime(2026, 7, 14, 8, 0, tzinfo=timezone.utc)


def _thesis(
    title: str = "thesis",
    *,
    generated_at: datetime | None = None,
    implication: str | None = "why it matters",
) -> CrossDossierThesis:
    return CrossDossierThesis(
        id=uuid4(),
        title=title,
        narrative="narrative body",
        source_dossier_ids=[uuid4(), uuid4()],
        confidence=0.8,
        implication=implication,
        generated_at=generated_at or _now() - timedelta(hours=2),
    )


def _intel_item(
    title: str = "Indonesia Cuts Visa-Free Entry by 87%",
    *,
    summary: str = "Indonesia cut visa-free entry to tighten foreign screening.",
    published_at: datetime | None = None,
    source_domain: str = "en.tempo.co",
    topic_tags: list[str] | None = None,
) -> IntelItemSummary:
    now = _now()
    return IntelItemSummary(
        id=uuid4(),
        title=title,
        summary=summary,
        source_domain=source_domain,
        canonical_url="https://en.tempo.co/read/123",
        jurisdiction="ID-national",
        topic_tags=topic_tags or ["visa", "immigration"],
        confidence_score=0.7,
        published_at=published_at or (now - timedelta(hours=5)),
        first_seen_at=now - timedelta(hours=5),
    )


@pytest.fixture
def repos():
    intel = AsyncMock()
    intel.fetch_recent_intel_items = AsyncMock(return_value=[])
    cognitive = AsyncMock()
    cognitive.recent_theses = AsyncMock(return_value=[])
    return intel, cognitive


# ── Empty day ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_daily_empty_is_scarce_and_empty(repos):
    intel, cognitive = repos
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty
    assert content.scarce
    assert content.day == _now().date()


# ── Theses prioritized first ──────────────────────────────


@pytest.mark.asyncio
async def test_theses_prioritized_over_intel_items(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("T1"), _thesis("T2")])
    intel.fetch_recent_intel_items = AsyncMock(return_value=[_intel_item("I1")])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())

    assert len(content.items) == 3  # 2 theses + 1 intel item (total_max=3)
    assert content.items[0].kind == "thesis"
    assert content.items[0].title == "T1"
    assert content.items[1].kind == "thesis"
    assert content.items[2].kind == "intel_item"
    assert not content.scarce


@pytest.mark.asyncio
async def test_theses_capped_at_daily_max(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis(f"T{i}") for i in range(10)])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    thesis_items = [i for i in content.items if i.kind == "thesis"]
    assert len(thesis_items) == DEFAULT_DAILY_THESES_MAX


@pytest.mark.asyncio
async def test_total_items_capped_at_daily_total_max(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("T1"), _thesis("T2")])
    intel.fetch_recent_intel_items = AsyncMock(
        return_value=[_intel_item(f"Visa update {i}") for i in range(10)]
    )
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == DEFAULT_DAILY_TOTAL_MAX


# ── Freshness cutoff ───────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_thesis_excluded(repos):
    intel, cognitive = repos
    stale = _thesis("stale", generated_at=_now() - timedelta(hours=72))
    # recent_theses() is mocked here to emulate the DB already applying a
    # >=lookback_days window server-side; the builder re-filters client-side
    # against the exact lookback_hours cutoff.
    cognitive.recent_theses = AsyncMock(return_value=[stale])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty


# ── Relevance filter on intel_items ────────────────────────


@pytest.mark.asyncio
async def test_irrelevant_intel_item_filtered_out(repos):
    intel, cognitive = repos
    irrelevant = _intel_item(
        title="Royal Tulip Springhill Resort celebrates 9th anniversary",
        summary="A hotel held a blood donation drive and community event.",
        topic_tags=["news-room"],
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[irrelevant])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty


@pytest.mark.asyncio
async def test_relevant_intel_item_included(repos):
    intel, cognitive = repos
    relevant = _intel_item(
        title="DJP sebut ada 143.449 wajib pajak baru",
        summary="Ekstensifikasi pajak DJP mencatat wajib pajak baru.",
        topic_tags=["news-room"],  # tag noisy/irrelevant, but title/summary match "pajak"
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[relevant])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    assert content.items[0].kind == "intel_item"


@pytest.mark.asyncio
async def test_relevant_intel_item_with_empty_summary_excluded(repos):
    """Regression 2026-07-14 (found on real prod data): a relevant item
    with no summary would render a blank body line in the card — skip it
    rather than ship a broken-looking card."""
    intel, cognitive = repos
    blank_summary = _intel_item(
        title="Ekstensifikasi Pajak Melesat, DJP Catat 143.449 WP Baru",
        summary="",
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[blank_summary])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty


@pytest.mark.asyncio
async def test_relevant_intel_item_with_whitespace_only_summary_excluded(repos):
    intel, cognitive = repos
    ws_summary = _intel_item(
        title="Aturan Pajak UMKM Disempurnakan",
        summary="   ",
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[ws_summary])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty


# ── Scarce day flag ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_item_day_is_scarce(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("only one")])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    assert content.scarce is True


@pytest.mark.asyncio
async def test_two_items_day_not_scarce(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("t1"), _thesis("t2")])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == DEFAULT_DAILY_SCARCE_FLOOR
    assert content.scarce is False


# ── Graceful per-source failure ─────────────────────────────


@pytest.mark.asyncio
async def test_theses_failure_falls_back_to_intel_items(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(side_effect=RuntimeError("pg down"))
    intel.fetch_recent_intel_items = AsyncMock(return_value=[_intel_item("Visa rule change")])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    assert content.items[0].kind == "intel_item"


@pytest.mark.asyncio
async def test_intel_items_failure_does_not_abort(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("t1")])
    intel.fetch_recent_intel_items = AsyncMock(side_effect=RuntimeError("pg down"))
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    assert content.items[0].kind == "thesis"


# ── Never fabricates — every item traces to a source ────────


@pytest.mark.asyncio
async def test_thesis_item_uses_implication_as_body(repos):
    intel, cognitive = repos
    cognitive.recent_theses = AsyncMock(return_value=[_thesis("t1", implication="do X because Y")])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.items[0].body == "do X because Y"
    assert content.items[0].source_label == "Bali Zero Connector"


@pytest.mark.asyncio
async def test_intel_item_carries_source_url_and_domain(repos):
    intel, cognitive = repos
    item = _intel_item()
    intel.fetch_recent_intel_items = AsyncMock(return_value=[item])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.items[0].source_url == item.canonical_url
    assert content.items[0].source_label == item.source_domain


# ── domain_tag derived from matched content, not raw noisy tags ─────────
# Regression 2026-07-14: a real prod row about Bali's property market was
# tagged topic_tags=["visa"] — the old (raw-tag) logic would have badged
# it "VISA". The fix derives the badge from which _RELEVANCE_CATEGORIES
# keyword actually matched the title/summary.


def test_domain_tag_for_visa_keyword():
    item = _intel_item(title="Indonesia tightens visa rules", summary="overstay crackdown")
    assert _domain_tag_for(item) == "VISA"


def test_domain_tag_for_tax_keyword():
    item = _intel_item(title="DJP catat wajib pajak baru", summary="ekstensifikasi pajak")
    assert _domain_tag_for(item) == "TAX"


def test_domain_tag_for_property_keyword_not_misled_by_noisy_topic_tag():
    item = _intel_item(
        title="Can You Measure Trust in Bali's Property Market?",
        summary="A look at property transactions and buyer trust in Bali.",
        topic_tags=["visa"],  # noisy/wrong tag on the raw row — must be ignored
    )
    assert _domain_tag_for(item) == "PROPERTY"


@pytest.mark.asyncio
async def test_selected_intel_item_domain_tag_matches_content_not_raw_tag(repos):
    intel, cognitive = repos
    property_item = _intel_item(
        title="Can You Measure Trust in Bali's Property Market?",
        summary="A look at property transactions and buyer trust in Bali.",
        topic_tags=["visa", "immigration"],  # noisy — must not win over content match
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[property_item])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    assert content.items[0].domain_tag == "PROPERTY"


# ── _clean_summary — strip raw RSS/WordPress markup ─────────────────────
# Regression 2026-07-14: a real prod row's summary was the raw RSS
# <description> — HTML tags, HTML entities, and a "The post X appeared
# first on Y." syndication footer appended by WordPress.


def test_clean_summary_strips_html_tags():
    raw = "<p>Trust is one of the most discussed qualities.</p>"
    assert _clean_summary(raw) == "Trust is one of the most discussed qualities."


def test_clean_summary_unescapes_html_entities():
    raw = "Bali&#8217;s property market is opaque."
    assert _clean_summary(raw) == "Bali’s property market is opaque."


def test_clean_summary_strips_wordpress_appeared_first_on_footer():
    raw = (
        "<p>Trust is hard to measure in property.</p>\n"
        '<p>The post <a href="https://x.com/y">Can You Measure Trust</a> appeared first on '
        '<a href="https://indonesiaexpat.id">Indonesia Expat</a>.</p>'
    )
    cleaned = _clean_summary(raw)
    assert "appeared first on" not in cleaned
    assert cleaned == "Trust is hard to measure in property."


def test_clean_summary_truncates_long_text_with_ellipsis():
    raw = "word " * 200
    cleaned = _clean_summary(raw, max_len=50)
    assert len(cleaned) <= 50
    assert cleaned.endswith("…")


def test_clean_summary_plain_text_passthrough_unchanged():
    assert _clean_summary("Indonesia cut visa-free entry by 87 percent.") == (
        "Indonesia cut visa-free entry by 87 percent."
    )


@pytest.mark.asyncio
async def test_raw_wordpress_summary_rendered_as_clean_body(repos):
    intel, cognitive = repos
    wp_item = _intel_item(
        title="Can You Measure Trust in Bali's Property Market?",
        summary=(
            "<p>Trust is hard to measure in Bali&#8217;s property market.</p>\n"
            '<p>The post <a href="https://x.com">Can You Measure Trust</a> appeared first on '
            '<a href="https://indonesiaexpat.id">Indonesia Expat</a>.</p>'
        ),
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[wp_item])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert len(content.items) == 1
    body = content.items[0].body
    assert "<p>" not in body
    assert "appeared first on" not in body
    assert "&#8217;" not in body
    assert body == "Trust is hard to measure in Bali’s property market."


@pytest.mark.asyncio
async def test_summary_that_is_only_wordpress_boilerplate_excluded(repos):
    """A summary that, after cleaning, is empty must be treated the same
    as a genuinely empty summary — skip, don't ship a blank card."""
    intel, cognitive = repos
    boilerplate_only = _intel_item(
        title="Some Bali property story",
        summary=(
            'The post <a href="https://x.com">title</a> appeared first on '
            '<a href="https://indonesiaexpat.id">Indonesia Expat</a>.'
        ),
    )
    intel.fetch_recent_intel_items = AsyncMock(return_value=[boilerplate_only])
    builder = DailyDigestBuilder(intel_repo=intel, cognitive_repo=cognitive)
    content = await builder.build_daily(now=_now())
    assert content.is_empty
