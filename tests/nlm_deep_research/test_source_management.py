"""Tests for source_management.py — SVS, NHS, staleness, should_import, lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.evaluator.nlm_deep_research.source_management import (
    HALF_LIFE_DAYS,
    TIER_VALUES,
    LifecycleStage,
    NHSClassification,
    NotebookHealthInput,
    Source,
    SourceDates,
    SourceDedup,
    SourceFlags,
    SourceScores,
    SourceType,
    SVSClassification,
    archive_source,
    classify_nhs,
    classify_svs,
    compute_nhs,
    compute_staleness,
    compute_svs,
    emergency_prune,
    find_title_duplicates,
    normalize_title,
    promote_to_active,
    recompute_all_svs,
    should_import,
)

from .conftest import NOW, days_ago, make_source


# =====================================================================
# SVS — Source Value Score
# =====================================================================


class TestComputeStaleness:
    """Tests for the exponential decay staleness function."""

    def test_zero_days_gives_near_zero_staleness(self):
        staleness = compute_staleness(SourceType.NEWS, 0.0, None)
        assert staleness == pytest.approx(0.0, abs=0.001)

    def test_half_life_gives_about_0_63(self):
        half_life = HALF_LIFE_DAYS[SourceType.NEWS]  # 15 days
        staleness = compute_staleness(SourceType.NEWS, half_life, None)
        # 1 - exp(-1) = 0.6321
        assert staleness == pytest.approx(0.6321, abs=0.01)

    def test_no_temporal_data_returns_0_5(self):
        staleness = compute_staleness(SourceType.REGULATION, None, None)
        assert staleness == 0.5

    def test_confirmed_valid_overrides_published(self):
        """confirmed_valid is more recent so t_effective uses the minimum."""
        staleness_old = compute_staleness(SourceType.REGULATION, 300.0, None)
        staleness_refreshed = compute_staleness(SourceType.REGULATION, 300.0, 5.0)
        assert staleness_refreshed < staleness_old

    def test_law_in_force_almost_never_stale(self):
        staleness = compute_staleness(SourceType.LAW_IN_FORCE, 365.0, None)
        assert staleness < 0.01  # half-life is 99999 days

    def test_negative_days_ignored(self):
        staleness = compute_staleness(SourceType.NEWS, -5.0, None)
        assert staleness == 0.5  # falls back to no data


class TestClassifySVS:
    """Tests for SVS classification thresholds."""

    def test_essential(self):
        assert classify_svs(0.70) == SVSClassification.ESSENTIAL
        assert classify_svs(0.95) == SVSClassification.ESSENTIAL

    def test_valuable(self):
        assert classify_svs(0.45) == SVSClassification.VALUABLE
        assert classify_svs(0.69) == SVSClassification.VALUABLE

    def test_marginal(self):
        assert classify_svs(0.25) == SVSClassification.MARGINAL
        assert classify_svs(0.44) == SVSClassification.MARGINAL

    def test_expendable(self):
        assert classify_svs(0.00) == SVSClassification.EXPENDABLE
        assert classify_svs(0.24) == SVSClassification.EXPENDABLE


class TestComputeSVS:
    """Tests for the composite SVS computation."""

    def test_high_tier_pinned_source_is_essential(self):
        src = make_source(
            tier=0, tier_label="T0",
            published=days_ago(1),
            claims=["c1", "c2", "c3"],
            times_cited=5,
            pinned=True,
        )
        scores = compute_svs(src, now=NOW)
        assert scores.svs_classification == SVSClassification.ESSENTIAL
        assert scores.svs_total >= 0.70

    def test_low_tier_stale_source_is_expendable(self):
        src = make_source(
            tier=6, tier_label="T6",
            source_type=SourceType.NEWS,
            published=days_ago(180),
            claims=[],
            times_cited=0,
        )
        scores = compute_svs(src, now=NOW)
        assert scores.svs_classification == SVSClassification.EXPENDABLE

    def test_svs_clamped_to_unit_interval(self):
        src = make_source(
            tier=0, tier_label="T0",
            published=NOW,
            claims=["a", "b", "c", "d"],
            times_cited=10,
            pinned=True,
        )
        scores = compute_svs(src, now=NOW)
        assert 0.0 <= scores.svs_total <= 1.0

    def test_breakdown_keys_present(self):
        src = make_source()
        scores = compute_svs(src, now=NOW)
        for key in ("v_tier", "v_claims", "staleness", "v_citations", "v_uniqueness", "bonus"):
            assert key in scores.svs_breakdown

    def test_enforcement_divergence_gives_half_bonus(self):
        src_normal = make_source(enforcement_divergence=False)
        src_diverge = make_source(enforcement_divergence=True)
        s_normal = compute_svs(src_normal, now=NOW)
        s_diverge = compute_svs(src_diverge, now=NOW)
        assert s_diverge.svs_total > s_normal.svs_total

    def test_tier_label_prefix_resolution(self):
        """A tier_label like T2_REGIONAL should resolve to T2."""
        src = make_source(tier=2, tier_label="T2_REGIONAL")
        scores = compute_svs(src, now=NOW)
        assert scores.svs_breakdown["v_tier"] == TIER_VALUES["T2"]

    def test_unknown_tier_label_falls_back_to_md(self):
        src = make_source(tier=99, tier_label="UNKNOWN_TIER")
        scores = compute_svs(src, now=NOW)
        assert scores.svs_breakdown["v_tier"] == TIER_VALUES["MD"]


# =====================================================================
# NHS — Notebook Health Score
# =====================================================================


class TestClassifyNHS:
    """Tests for NHS classification thresholds."""

    def test_excellent(self):
        assert classify_nhs(0.80) == NHSClassification.EXCELLENT
        assert classify_nhs(1.0) == NHSClassification.EXCELLENT

    def test_normal(self):
        assert classify_nhs(0.60) == NHSClassification.NORMAL
        assert classify_nhs(0.79) == NHSClassification.NORMAL

    def test_degraded(self):
        assert classify_nhs(0.40) == NHSClassification.DEGRADED
        assert classify_nhs(0.59) == NHSClassification.DEGRADED

    def test_critical(self):
        assert classify_nhs(0.00) == NHSClassification.CRITICAL
        assert classify_nhs(0.39) == NHSClassification.CRITICAL


class TestComputeNHS:
    """Tests for the composite NHS computation."""

    def test_healthy_notebook(self):
        sources = [
            make_source(
                source_id=f"S-{i}",
                published=days_ago(5),
                claims=[f"c{i}"],
                times_cited=3,
            )
            for i in range(55)
        ]
        health = NotebookHealthInput(
            active_count=55,
            sources=sources,
            clusters_with_claims=5,
            categories_with_claims=10,
            duplicates_found_this_week=0,
            sources_evaluated_this_week=10,
        )
        result = compute_nhs(health, now=NOW)
        assert result.nhs_classification in (NHSClassification.EXCELLENT, NHSClassification.NORMAL)
        assert 0.0 <= result.nhs_total <= 1.0

    def test_overcapacity_degrades_score(self):
        sources = [
            make_source(source_id=f"S-{i}", published=days_ago(5))
            for i in range(90)
        ]
        health = NotebookHealthInput(
            active_count=90,
            sources=sources,
            clusters_with_claims=5,
            categories_with_claims=10,
            duplicates_found_this_week=0,
            sources_evaluated_this_week=10,
        )
        result = compute_nhs(health, now=NOW)
        assert result.h_capacity < 1.0

    def test_empty_notebook_gives_zero_freshness(self):
        health = NotebookHealthInput(
            active_count=0,
            sources=[],
            clusters_with_claims=0,
            categories_with_claims=0,
            duplicates_found_this_week=0,
            sources_evaluated_this_week=0,
        )
        result = compute_nhs(health, now=NOW)
        assert result.h_freshness == 0.0
        assert result.h_quality == 0.0

    def test_high_dedup_ratio_degrades_score(self):
        health = NotebookHealthInput(
            active_count=10,
            sources=[make_source(source_id=f"S-{i}", published=days_ago(5)) for i in range(10)],
            clusters_with_claims=3,
            categories_with_claims=5,
            duplicates_found_this_week=8,
            sources_evaluated_this_week=10,
        )
        result = compute_nhs(health, now=NOW)
        assert result.h_dedup == pytest.approx(0.2, abs=0.01)


# =====================================================================
# should_import — 6-gate pre-import filter
# =====================================================================


class TestShouldImport:
    """Tests for the 6-gate pre-import filter."""

    def test_happy_path_passes_all_gates(self):
        ok, reason = should_import(
            url="https://imigrasi.go.id/new-regulation",
            source_type="regulation",
            language="id",
            publication_date=days_ago(10),
            tier_label="T2",
            existing_sources=[],
            now=NOW,
        )
        assert ok is True
        assert reason == "OK"

    def test_gate1_domain_denylist(self):
        ok, reason = should_import(
            url="https://tripadvisor.com/bali-visa",
            source_type="news",
            language="en",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False
        assert "denylist" in reason.lower()

    def test_gate1_balizero_blocked(self):
        ok, reason = should_import(
            url="https://balizero.com/article/test",
            source_type="news",
            language="en",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False

    def test_gate2_url_duplicate(self):
        existing = make_source(url="https://example.com/page")
        ok, reason = should_import(
            url="https://example.com/page",
            source_type="news",
            language="en",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[existing],
            now=NOW,
        )
        assert ok is False
        assert "duplicate" in reason.lower()

    def test_gate3_invalid_source_type(self):
        ok, reason = should_import(
            url="https://example.com/test",
            source_type="blog_post",
            language="en",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False
        assert "source type" in reason.lower()

    def test_gate4_too_old(self):
        ok, reason = should_import(
            url="https://example.com/old",
            source_type="news",
            language="en",
            publication_date=days_ago(90),
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False
        assert "days old" in reason.lower()

    def test_gate4_canonical_bypasses_date(self):
        """T0 and T1 sources bypass the publication date check."""
        ok, reason = should_import(
            url="https://example.com/old-but-canonical",
            source_type="regulation",
            language="id",
            publication_date=days_ago(365),
            tier_label="T0",
            existing_sources=[],
            now=NOW,
        )
        assert ok is True

    def test_gate4_no_date_for_non_canonical(self):
        ok, reason = should_import(
            url="https://example.com/no-date",
            source_type="news",
            language="en",
            publication_date=None,
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False
        assert "publication date" in reason.lower()

    def test_gate5_invalid_language(self):
        ok, reason = should_import(
            url="https://example.com/chinese",
            source_type="news",
            language="zh",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[],
            now=NOW,
        )
        assert ok is False
        assert "language" in reason.lower()

    def test_gate6_budget_exhausted(self):
        ok, reason = should_import(
            url="https://example.com/over-budget",
            source_type="news",
            language="en",
            publication_date=days_ago(5),
            tier_label="T3",
            existing_sources=[],
            weekly_imports_used=20,
            weekly_budget=20,
            now=NOW,
        )
        assert ok is False
        assert "budget" in reason.lower()

    def test_none_url_bypasses_domain_and_dedup(self):
        """File-based sources have no URL — gates 1 and 2 are skipped."""
        ok, reason = should_import(
            url=None,
            source_type="regulation",
            language="id",
            publication_date=days_ago(5),
            tier_label="T1",
            existing_sources=[],
            now=NOW,
        )
        assert ok is True


# =====================================================================
# Lifecycle transitions
# =====================================================================


class TestLifecycleTransitions:
    """Tests for promote, archive, emergency_prune."""

    def test_promote_to_active(self):
        src = make_source(stage=LifecycleStage.CANDIDATE)
        result = promote_to_active(src, now=NOW)
        assert result.stage == LifecycleStage.ACTIVE
        assert result.dates.promoted == NOW

    def test_archive_source(self):
        src = make_source(stage=LifecycleStage.ACTIVE)
        result = archive_source(src, now=NOW)
        assert result.stage == LifecycleStage.ARCHIVE
        assert result.dates.last_reviewed == NOW

    def test_emergency_prune_noop_below_target(self):
        sources = [make_source(source_id=f"S-{i}") for i in range(5)]
        kept, pruned = emergency_prune(sources, target_count=10, now=NOW)
        assert len(pruned) == 0
        assert len(kept) == 5

    def test_emergency_prune_removes_lowest_svs(self):
        sources = [
            make_source(
                source_id=f"S-{i}",
                tier=i,
                tier_label=f"T{i}",
                claims=[f"c{i}"] if i < 2 else [],
                times_cited=4 - i,
                published=days_ago(i * 30),
            )
            for i in range(5)
        ]
        kept, pruned = emergency_prune(sources, target_count=3, now=NOW)
        assert len(pruned) == 2
        # Pruned sources should be archived
        for s in pruned:
            assert s.stage == LifecycleStage.ARCHIVE

    def test_emergency_prune_never_removes_pinned(self):
        sources = [
            make_source(source_id="PIN", pinned=True, tier=6, tier_label="T6"),
            make_source(source_id="LOW", tier=6, tier_label="T6", claims=[]),
            make_source(source_id="MED", tier=3, tier_label="T3"),
        ]
        kept, pruned = emergency_prune(sources, target_count=1, now=NOW)
        pinned_ids = {s.nlm_source_id for s in kept if s.flags.pinned}
        assert "PIN" in pinned_ids

    def test_promote_then_archive_lifecycle(self):
        src = make_source(stage=LifecycleStage.CANDIDATE)
        promote_to_active(src, now=NOW)
        assert src.stage == LifecycleStage.ACTIVE
        archive_source(src, now=NOW)
        assert src.stage == LifecycleStage.ARCHIVE


# =====================================================================
# Batch operations
# =====================================================================


class TestBatchOperations:
    """Tests for recompute_all_svs, normalize_title, find_title_duplicates."""

    def test_recompute_all_svs_updates_scores(self):
        sources = [make_source(source_id=f"S-{i}") for i in range(3)]
        updated = recompute_all_svs(sources, now=NOW)
        for src in updated:
            assert src.scores.svs_total > 0

    def test_normalize_title(self):
        assert normalize_title("  Hello, World!  ") == "hello world"
        assert normalize_title("KBLI-2025 Update!!") == "kbli2025 update"

    def test_find_title_duplicates(self):
        existing = [
            make_source(source_id="A", title="PP 34/2021 tentang TKA"),
            make_source(source_id="B", title="Something Else"),
        ]
        # Set normalized title for matching
        existing[0].dedup.title_normalized = normalize_title("PP 34/2021 tentang TKA")
        existing[1].dedup.title_normalized = normalize_title("Something Else")

        dupes = find_title_duplicates("pp 34/2021 tentang TKA", existing)
        assert len(dupes) == 1
        assert dupes[0].nlm_source_id == "A"

    def test_find_title_duplicates_no_match(self):
        existing = [make_source(source_id="A", title="Other Topic")]
        existing[0].dedup.title_normalized = normalize_title("Other Topic")
        dupes = find_title_duplicates("Completely Different", existing)
        assert len(dupes) == 0
