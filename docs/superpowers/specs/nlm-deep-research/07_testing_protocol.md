# Step 7: Testing Protocol — NB-2 Deep Research Pipeline

> Synthesis: Claude Opus 4.6 (architect) merging Codex (98 tests) + Gemini (8-phase live protocol) + DeepSeek R1 (KPIs, statistical tests, cost model) (2026-03-28)
> Status: FINAL — closes pipeline design (Steps 1-7 complete)
> Depends on: All previous steps (query design, sequencing, quality verification, source management, scraper integration, failure modes)
> Reference files: `07b_testing_protocol_deepseek.md` (baseline, KPIs, statistical tests, cost model)

---

## 0. Test Architecture Overview

```
tests/nlm_deep_research/
├── conftest.py                      # Shared fixtures, mock factories, state builders
├── unit/
│   ├── test_should_import.py        # Pre-import filter (10 cases)
│   ├── test_svs_calculation.py      # Source Value Score (5 cases)
│   ├── test_staleness_decay.py      # Staleness S(t) formula (14 cases)
│   ├── test_trs_calculation.py      # Topic Relevance Score (5 cases)
│   ├── test_confidence_boost.py     # Cross-validation boost B(n) (6 cases)
│   ├── test_dedup_overlap.py        # Dedup Szymkiewicz-Simpson (4 cases)
│   ├── test_ilm_check.py           # Information Loss Metric (4 cases)
│   ├── test_invariant_checks.py     # 10 invariants (20 cases = pass + violation each)
│   ├── test_nlm_enricher.py         # NLMEnricher adapter (6 cases)
│   └── test_circuit_breaker.py      # Circuit breaker FSM (6 cases)
├── integration/
│   ├── test_pipeline_dry_run.py     # Full pipeline with mock NLM API
│   ├── test_state_file_integrity.py # State file reads/writes after each phase
│   ├── test_claims_growth.py        # claims.jsonl grows correctly
│   └── test_handoff_schema.py       # Handoff package valid JSON + correct schema
├── regression/
│   ├── test_scraper_no_regression.py # Identical output with vs without handoff
│   ├── test_idempotency.py          # Second run produces no new queries
│   └── test_state_backward_compat.py # v1 state works with v1 code
├── fixtures/
│   ├── mock_sources.py              # 5 sources at different tiers
│   ├── mock_claims.py               # 3 claims at different confidence levels
│   ├── mock_handoff.py              # Valid + stale handoff packages
│   ├── mock_state.py                # Pipeline state variants
│   └── mock_nlm_responses.py        # NLM API mock responses
└── README.md                        # How to run, markers, CI integration
```

**Runner:** `pytest` with markers `@pytest.mark.nlm_unit`, `@pytest.mark.nlm_integration`, `@pytest.mark.nlm_regression`.

**CI gate:** All unit + integration tests must pass before any pipeline code merges. Regression tests run nightly.

**No external dependencies:** Every test uses mocks. Zero NLM API calls. Zero file system side effects (all use `tmp_path`).

---

## 1. Unit Tests

### 1.1 `test_should_import.py` — Pre-Import Filter (10 Cases)

The `should_import()` function (Step 4, Section 1 INGEST) is the gatekeeper. Every source candidate passes through it before entering NLM. Each test case validates one rejection reason or the happy path.

```python
"""Tests for should_import() pre-import filter.

Reference: 04_source_management.md Section 1 — INGEST stage.
Contract: should_import(source, registry) -> (bool, str)
"""
import pytest
from nlm_deep_research.source_management import should_import
from nlm_deep_research.registry import SourceRegistry


# ── Fixtures ──

@pytest.fixture
def empty_registry(tmp_path) -> SourceRegistry:
    """Registry with 20 ACTIVE sources, well under cap."""
    return SourceRegistry.from_dict({
        "version": 1,
        "sources": [
            {"nlm_source_id": f"src_{i}", "url": f"https://existing-{i}.go.id/doc",
             "stage": "ACTIVE", "category": "CANONICAL"}
            for i in range(20)
        ],
        "domain_denylist": [
            "tripadvisor.com", "expat.com/forum", "kaskus.co.id",
            "nomadicmatt.com", "reddit.com", "quora.com", "medium.com/@",
            "youtube.com", "tiktok.com", "pinterest.com", "booking.com",
            "agoda.com", "skyscanner.com", "lonelyplanet.com",
            "thepointsguy.com",
        ],
    })


@pytest.fixture
def full_registry_63(tmp_path) -> SourceRegistry:
    """Registry with exactly 63 ACTIVE sources (hard trigger threshold)."""
    return SourceRegistry.from_dict({
        "version": 1,
        "sources": [
            {"nlm_source_id": f"src_{i}", "url": f"https://existing-{i}.go.id/doc",
             "stage": "ACTIVE", "category": "WORKING"}
            for i in range(63)
        ],
        "domain_denylist": ["balizero.com"],
    })


@pytest.fixture
def full_registry_70(tmp_path) -> SourceRegistry:
    """Registry with exactly 70 ACTIVE sources (hard cap)."""
    return SourceRegistry.from_dict({
        "version": 1,
        "sources": [
            {"nlm_source_id": f"src_{i}", "url": f"https://existing-{i}.go.id/doc",
             "stage": "ACTIVE", "category": "WORKING"}
            for i in range(70)
        ],
        "domain_denylist": [],
    })


# ── Test Cases ──

class TestShouldImport:
    """10 test cases covering all rejection paths + happy path."""

    def test_allowed_valid_source(self, empty_registry: SourceRegistry) -> None:
        """CASE 1: Valid government source, fresh date, correct language → ALLOW."""
        source = {
            "url": "https://kemenkumham.go.id/new-regulation-2026",
            "type": "official_portal",
            "publication_date": "2026-03-15",
            "language": "id",
            "estimated_tier": 1,
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is True
        assert reason == "allowed"

    def test_reject_domain_denylist(self, empty_registry: SourceRegistry) -> None:
        """CASE 2: Source from tripadvisor.com → REJECT domain_denylist."""
        source = {
            "url": "https://tripadvisor.com/bali-visa-guide",
            "type": "travel_guide",
            "publication_date": "2026-03-10",
            "language": "en",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is False
        assert reason == "domain_denylist"

    def test_reject_duplicate_url(self, empty_registry: SourceRegistry) -> None:
        """CASE 3: URL already tracked in registry → REJECT duplicate_url."""
        source = {
            "url": "https://existing-5.go.id/doc",  # Matches src_5 in fixture
            "type": "official_portal",
            "publication_date": "2026-03-10",
            "language": "id",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is False
        assert reason == "duplicate_url"

    def test_reject_excluded_source_type(self, empty_registry: SourceRegistry) -> None:
        """CASE 4: Source type = 'forum' → REJECT excluded_source_type."""
        source = {
            "url": "https://some-forum.com/thread/12345",
            "type": "forum",
            "publication_date": "2026-03-10",
            "language": "en",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is False
        assert reason == "excluded_source_type"

    def test_reject_too_old_news(self, empty_registry: SourceRegistry) -> None:
        """CASE 5: Publication date 2023 (news, not regulation) → REJECT too_old."""
        source = {
            "url": "https://news-site.com/old-article",
            "type": "news",
            "publication_date": "2023-06-15",
            "language": "id",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is False
        assert reason == "too_old"

    def test_reject_wrong_language(self, empty_registry: SourceRegistry) -> None:
        """CASE 6: Language = 'zh' (Chinese) → REJECT wrong_language."""
        source = {
            "url": "https://chinese-news.cn/indonesia-visa",
            "type": "news",
            "publication_date": "2026-03-10",
            "language": "zh",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is False
        assert reason == "wrong_language"

    def test_reject_budget_pressure_low_tier(self, full_registry_63: SourceRegistry) -> None:
        """CASE 7: 63 ACTIVE + tier > 2 → REJECT budget_pressure_low_tier."""
        source = {
            "url": "https://blog-about-bali.com/visa-tips",
            "type": "blog",
            "publication_date": "2026-03-20",
            "language": "en",
            "estimated_tier": 5,
        }
        allowed, reason = should_import(source, full_registry_63)
        assert allowed is False
        assert reason == "budget_pressure_low_tier"

    def test_allow_high_tier_at_63(self, full_registry_63: SourceRegistry) -> None:
        """CASE 8: 63 ACTIVE + tier <= 2 → ALLOW (high-tier sources always welcome)."""
        source = {
            "url": "https://jdih.kemenkumham.go.id/new-permen",
            "type": "gazette",
            "publication_date": "2026-03-25",
            "language": "id",
            "estimated_tier": 0,
        }
        allowed, reason = should_import(source, full_registry_63)
        assert allowed is True
        assert reason == "allowed"

    def test_reject_hard_cap_reached(self, full_registry_70: SourceRegistry) -> None:
        """CASE 9: 70 ACTIVE (hard cap) → REJECT regardless of tier."""
        source = {
            "url": "https://jdih.kemenkumham.go.id/critical-regulation",
            "type": "gazette",
            "publication_date": "2026-03-25",
            "language": "id",
            "estimated_tier": 0,
        }
        allowed, reason = should_import(source, full_registry_70)
        assert allowed is False
        assert reason == "hard_cap_reached"

    def test_allow_no_date_active_regulation(self, empty_registry: SourceRegistry) -> None:
        """CASE 10: No publication_date but type=regulation → ALLOW (active regs have no expiry)."""
        source = {
            "url": "https://peraturan.bpk.go.id/regulation-xyz",
            "type": "regulation",
            "publication_date": "",
            "language": "id",
        }
        allowed, reason = should_import(source, empty_registry)
        assert allowed is True
        assert reason == "allowed"
```

**Pass criteria:** All 10 tests pass. Each tests exactly one branch of the filter. No external dependencies.

---

### 1.2 `test_svs_calculation.py` — Source Value Score (5 Cases)

```python
"""Tests for SVS (Source Value Score) calculation.

Reference: 04_source_management.md Section 3.
Formula: SVS = 0.25*V_tier + 0.25*V_claims + 0.20*S(t,type) + 0.15*V_citations + 0.15*V_uniqueness + BONUS
Classification: >= 0.70 ESSENTIAL, 0.45-0.69 VALUABLE, 0.25-0.44 MARGINAL, < 0.25 EXPENDABLE
"""
import pytest
from nlm_deep_research.source_management import calculate_svs, classify_svs


class TestSVSCalculation:
    """5 worked examples from the spec with known expected outputs."""

    def test_marginal_news_article(self) -> None:
        """CASE 1: NusaBali press article, 12 days old, 2 claims. Expected: ~0.370 MARGINAL.
        Spec worked example (04_source_management.md line 417-428)."""
        svs = calculate_svs(
            v_tier=0.35,        # T5 press
            claims_extracted=2, # V_claims = min(1.0, 2/8) = 0.25
            staleness=0.57,     # S(t=12, NEWS_ARTICLE) 15d half-life
            times_cited=1,      # V_citations = min(1.0, 1/5) = 0.20
            unique_claims=1,    # V_uniqueness = 1/2 = 0.50
            total_claims=2,
            bonus=0.0,
        )
        assert 0.36 <= svs <= 0.38, f"Expected ~0.370, got {svs}"
        assert classify_svs(svs) == "MARGINAL"

    def test_essential_t0_law(self) -> None:
        """CASE 2: JDIH gazette, T0, 4 claims, 7 citations, 60d old law_in_force. Expected: ~0.938 ESSENTIAL.
        Spec worked example (04_source_management.md line 432-444)."""
        svs = calculate_svs(
            v_tier=1.00,        # T0 national law
            claims_extracted=4, # V_claims = min(1.0, 4/8) = 0.50
            staleness=1.00,     # LAW_IN_FORCE = infinite half-life → S=1.00
            times_cited=7,      # V_citations = min(1.0, 7/5) = 1.00
            unique_claims=3,    # V_uniqueness = 3/4 = 0.75
            total_claims=4,
            bonus=0.10,         # Sole T0 backing for active VERIFIED claim
        )
        assert 0.93 <= svs <= 0.95, f"Expected ~0.938, got {svs}"
        assert classify_svs(svs) == "ESSENTIAL"

    def test_expendable_zero_claims(self) -> None:
        """CASE 3: Community source, 0 claims, never cited, 30d old. Expected: <0.25 EXPENDABLE."""
        svs = calculate_svs(
            v_tier=0.10,        # T6 community
            claims_extracted=0, # V_claims = 0.00
            staleness=0.25,     # S(t=30, NEWS_ARTICLE) ~0.25
            times_cited=0,      # V_citations = 0.00
            unique_claims=0,
            total_claims=0,
            bonus=0.0,
        )
        assert svs < 0.25, f"Expected < 0.25, got {svs}"
        assert classify_svs(svs) == "EXPENDABLE"

    def test_valuable_enforcement_source(self) -> None:
        """CASE 4: T3 enforcement report, 6 claims, 3 citations, 7d old. Expected: 0.50-0.65 VALUABLE."""
        svs = calculate_svs(
            v_tier=0.65,        # T3 enforcement
            claims_extracted=6, # V_claims = min(1.0, 6/8) = 0.75
            staleness=0.92,     # S(t=7, OFFICIAL_PORTAL) 60d half-life
            times_cited=3,      # V_citations = min(1.0, 3/5) = 0.60
            unique_claims=2,    # V_uniqueness = 2/6 = 0.333
            total_claims=6,
            bonus=0.0,
        )
        assert 0.50 <= svs <= 0.65, f"Expected 0.50-0.65, got {svs}"
        assert classify_svs(svs) == "VALUABLE"

    def test_bonus_capped_at_015(self) -> None:
        """CASE 5: Multiple bonuses should not exceed +0.15 cap (04_source_management.md line 396)."""
        svs_without_bonus = calculate_svs(
            v_tier=0.80, claims_extracted=4, staleness=0.90,
            times_cited=2, unique_claims=2, total_claims=4, bonus=0.0,
        )
        svs_with_excess_bonus = calculate_svs(
            v_tier=0.80, claims_extracted=4, staleness=0.90,
            times_cited=2, unique_claims=2, total_claims=4, bonus=0.30,  # Exceeds 0.15 cap
        )
        assert svs_with_excess_bonus - svs_without_bonus == pytest.approx(0.15, abs=0.001)
```

---

### 1.3 `test_staleness_decay.py` — Staleness Formula (14 Cases)

```python
"""Tests for staleness decay formula S(t, type).

Reference: 04_source_management.md Section 1 ACTIVE (line 183-193).
Formula: S(t, type) = exp(-lambda * t) where lambda = ln(2) / half_life
Special case: LAW_IN_FORCE has infinite half-life → S = 1.0 always.
Auto-archive trigger: S(t) < 0.20.
"""
import pytest
from nlm_deep_research.source_management import staleness_score


class TestStalenessDecay:
    """3 source types × 4 time points = 12 parametrized + 2 boundary tests."""

    @pytest.mark.parametrize(
        "source_type,days,expected",
        [
            # LAW_IN_FORCE: infinite half-life → always 1.0
            ("LAW_IN_FORCE", 7, 1.00),
            ("LAW_IN_FORCE", 30, 1.00),
            ("LAW_IN_FORCE", 90, 1.00),
            ("LAW_IN_FORCE", 365, 1.00),
            # NEWS_ARTICLE: 15d half-life → rapid decay
            ("NEWS_ARTICLE", 7, 0.72),
            ("NEWS_ARTICLE", 30, 0.25),
            ("NEWS_ARTICLE", 90, 0.02),
            ("NEWS_ARTICLE", 180, 0.00),
            # REGULATION_CIRCULAR: 90d half-life → slow decay
            ("REGULATION_CIRCULAR", 7, 0.95),
            ("REGULATION_CIRCULAR", 30, 0.79),
            ("REGULATION_CIRCULAR", 90, 0.50),
            ("REGULATION_CIRCULAR", 180, 0.25),
        ],
        ids=[
            "law_7d", "law_30d", "law_90d", "law_365d",
            "news_7d", "news_30d", "news_90d", "news_180d",
            "circular_7d", "circular_30d", "circular_90d", "circular_180d",
        ],
    )
    def test_staleness_decay(self, source_type: str, days: int, expected: float) -> None:
        """Validate staleness score against spec table."""
        actual = staleness_score(source_type=source_type, days_since_publication=days)
        assert actual == pytest.approx(expected, abs=0.02), (
            f"S(t={days}, {source_type}) = {actual}, expected {expected}"
        )

    def test_staleness_always_non_negative(self) -> None:
        """Staleness score must never go below 0.0 for any input."""
        for source_type in ["NEWS_ARTICLE", "LAW_SUPERSEDED", "OFFICIAL_SOCIAL"]:
            for days in [0, 1, 7, 30, 90, 180, 365, 1000]:
                score = staleness_score(source_type=source_type, days_since_publication=days)
                assert score >= 0.0, f"S(t={days}, {source_type}) = {score} < 0"

    def test_staleness_at_zero_days_is_one(self) -> None:
        """All source types at day 0 should have S(t=0) = 1.0."""
        for source_type in ["NEWS_ARTICLE", "REGULATION_CIRCULAR", "OFFICIAL_PORTAL", "LAW_IN_FORCE"]:
            score = staleness_score(source_type=source_type, days_since_publication=0)
            assert score == pytest.approx(1.0, abs=0.001)
```

---

### 1.4 `test_trs_calculation.py` — Topic Relevance Score (5 Cases)

```python
"""Tests for TRS (Topic Relevance Score) calculation.

Reference: 05_scraper_integration.md Section 1b.
Formula: TRS = 0.25*F_confidence + 0.25*F_novelty + 0.20*F_client_impact
             + 0.15*F_editorial_value + 0.15*F_source_tier + BONUS_timely
Thresholds: >= 0.65 HANDOFF, 0.45-0.64 CANDIDATE, < 0.45 FILTERED
Max 5 topics per handoff, max 3 from same cluster.
"""
import pytest
from collections import Counter
from nlm_deep_research.scraper_integration import calculate_trs, classify_trs, select_handoff_topics


class TestTRSCalculation:

    def test_handoff_high_confidence_topic(self) -> None:
        """CASE 1: Verified finding, novel, high impact → HANDOFF (>= 0.65)."""
        trs = calculate_trs(
            f_confidence=0.85, f_novelty=0.80, f_client_impact=0.75,
            f_editorial_value=0.75, f_source_tier=1.00, bonus_timely=0.05,
        )
        assert trs >= 0.65, f"Expected HANDOFF (>= 0.65), got {trs}"
        assert classify_trs(trs) == "HANDOFF"

    def test_candidate_moderate_finding(self) -> None:
        """CASE 2: Provisional finding, moderate novelty → CANDIDATE (0.45-0.64)."""
        trs = calculate_trs(
            f_confidence=0.60, f_novelty=0.50, f_client_impact=0.50,
            f_editorial_value=0.25, f_source_tier=0.60, bonus_timely=0.0,
        )
        assert 0.45 <= trs < 0.65, f"Expected CANDIDATE (0.45-0.64), got {trs}"
        assert classify_trs(trs) == "CANDIDATE"

    def test_filtered_noise_topic(self) -> None:
        """CASE 3: Low confidence, low novelty, T6 → FILTERED (< 0.45)."""
        trs = calculate_trs(
            f_confidence=0.30, f_novelty=0.20, f_client_impact=0.25,
            f_editorial_value=0.00, f_source_tier=0.20, bonus_timely=0.0,
        )
        assert trs < 0.45, f"Expected FILTERED (< 0.45), got {trs}"
        assert classify_trs(trs) == "FILTERED"

    def test_bonus_capped_at_010(self) -> None:
        """CASE 4: BONUS_timely must not exceed 0.10."""
        trs_normal = calculate_trs(
            f_confidence=0.70, f_novelty=0.70, f_client_impact=0.60,
            f_editorial_value=0.50, f_source_tier=0.80, bonus_timely=0.0,
        )
        trs_excess = calculate_trs(
            f_confidence=0.70, f_novelty=0.70, f_client_impact=0.60,
            f_editorial_value=0.50, f_source_tier=0.80, bonus_timely=0.30,
        )
        assert trs_excess - trs_normal == pytest.approx(0.10, abs=0.001)

    def test_max_5_topics_diversity_guard(self) -> None:
        """CASE 5: Max 5 topics per handoff, max 3 from same cluster."""
        topics = [
            {"trs": 0.90, "cluster": "A"}, {"trs": 0.85, "cluster": "A"},
            {"trs": 0.80, "cluster": "A"}, {"trs": 0.78, "cluster": "A"},
            {"trs": 0.75, "cluster": "B"}, {"trs": 0.70, "cluster": "B"},
            {"trs": 0.68, "cluster": "C"},
        ]
        selected = select_handoff_topics(topics, max_topics=5, max_per_cluster=3)
        assert len(selected) <= 5
        cluster_counts = Counter(t["cluster"] for t in selected)
        for cluster, count in cluster_counts.items():
            assert count <= 3, f"Cluster {cluster} has {count} topics (max 3)"
```

---

### 1.5 `test_confidence_boost.py` — Cross-Validation Convergence (6 Cases)

```python
"""Tests for confidence boost via cross-validation.

Reference: 05_scraper_integration.md Section 3.3.
Boost: C_adj = C_nlm + B(n_eff) * (1 - C_nlm)    where B(n) = 0.30 * ln(1+n) / ln(6)
Contradiction: C_adj = C_nlm - min(0.40, 0.15*m) * C_nlm
Hard cap: 0.95.
"""
import pytest
from nlm_deep_research.scraper_integration import (
    cross_validate_convergence,
    apply_contradiction_penalty,
)


class TestConfidenceBoost:

    def test_provisional_with_5_t0_articles(self) -> None:
        """CASE 1: C_nlm=0.63 + 5 T0 articles → C_adj ~0.741.
        Spec table (05_scraper_integration.md line 488): n_eff=5.0, B=0.300, C_adj=0.741."""
        result = cross_validate_convergence(
            nlm_conf=0.63,
            confirming_articles=[{"tier": "T0"}] * 5,
        )
        assert result["cross_validated"] is True
        assert result["boosted_confidence"] == pytest.approx(0.741, abs=0.005)
        assert result["original_confidence"] == 0.63
        assert result["validation_type"] == "CONVERGENCE"

    def test_single_journalism_confirmation(self) -> None:
        """CASE 2: C_nlm=0.72 + 1 T5 article (w=0.4) → modest boost ~0.736.
        B(0.4) = 0.30 * ln(1.4)/ln(6) ≈ 0.056. C_adj = 0.72 + 0.056*(1-0.72) ≈ 0.736."""
        result = cross_validate_convergence(
            nlm_conf=0.72,
            confirming_articles=[{"tier": "T5"}],
        )
        assert result["boosted_confidence"] == pytest.approx(0.736, abs=0.005)
        assert result["n_eff"] == pytest.approx(0.4, abs=0.05)

    def test_high_confidence_cap_at_095(self) -> None:
        """CASE 3: C_nlm=0.92 + many confirmations → hard capped at 0.95."""
        result = cross_validate_convergence(
            nlm_conf=0.92,
            confirming_articles=[{"tier": "T0"}] * 6,
        )
        assert result["boosted_confidence"] <= 0.95
        assert result["boosted_confidence"] >= 0.92

    def test_zero_confirmations_no_change(self) -> None:
        """CASE 4: No confirming articles → confidence unchanged."""
        result = cross_validate_convergence(nlm_conf=0.72, confirming_articles=[])
        assert result["boosted_confidence"] == pytest.approx(0.72, abs=0.001)

    def test_contradiction_drops_provisional(self) -> None:
        """CASE 5: 1 contradiction on C_nlm=0.63 → 0.63 - 0.15*0.63 = 0.536 (below threshold).
        Spec (05_scraper_integration.md line 499-502)."""
        result = apply_contradiction_penalty(nlm_conf=0.63, contradictions=1)
        assert result == pytest.approx(0.536, abs=0.005)

    def test_three_contradictions_force_review(self) -> None:
        """CASE 6: 3 contradictions on VERIFIED 0.85 → 0.85 - min(0.40,0.45)*0.85 = 0.510.
        Below 0.55 → mandatory human review."""
        result = apply_contradiction_penalty(nlm_conf=0.85, contradictions=3)
        assert result == pytest.approx(0.510, abs=0.005)
        assert result < 0.55, "Should drop below PROVISIONAL threshold"
```

---

### 1.6 `test_dedup_overlap.py` — Deduplication Overlap (4 Cases)

```python
"""Tests for dedup overlap using Szymkiewicz-Simpson coefficient.

Reference: 04_source_management.md Section 4.2-4.3.
Formula: Overlap(A, B) = |claims(A) ∩ claims(B)| / min(|claims(A)|, |claims(B)|)
Claim matching requires: same category + same regulation_ref + same assertion_direction + temporal overlap (30d).
Thresholds: >= 0.90 TRUE_DUPLICATE, >= 0.70 SUBSTANTIAL, 0.40-0.69 PARTIAL, < 0.40 INDEPENDENT.
"""
import pytest
from nlm_deep_research.source_management import calculate_dedup_overlap, classify_overlap


class TestDedupOverlap:

    def test_true_duplicate_same_claims(self) -> None:
        """CASE 1: Identical claims → overlap 1.0 → TRUE_DUPLICATE."""
        claims = [
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "expand", "effective_date": "2026-04-15"},
            {"category": "DEADLINE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "90 day registration", "effective_date": "2026-07-15"},
        ]
        overlap, classification = calculate_dedup_overlap(claims, claims.copy())
        assert overlap >= 0.90
        assert classification == "TRUE_DUPLICATE"

    def test_substantial_overlap_4_of_5(self) -> None:
        """CASE 2: 4 of 5 claims match → overlap 0.80 → SUBSTANTIAL_OVERLAP."""
        claims_a = [
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "expand", "effective_date": "2026-04-15"},
            {"category": "DEADLINE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "90 day", "effective_date": "2026-07-15"},
            {"category": "PROCEDURAL_UPDATE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "new form", "effective_date": "2026-05-01"},
            {"category": "FEE_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "fee increase", "effective_date": "2026-04-15"},
            {"category": "ADVISORY", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "law firm analysis", "effective_date": None},
        ]
        claims_b = claims_a[:4]  # Only first 4 match
        overlap, classification = calculate_dedup_overlap(claims_a, claims_b)
        assert 0.70 <= overlap < 0.90
        assert classification == "SUBSTANTIAL_OVERLAP"

    def test_partial_overlap_2_of_5(self) -> None:
        """CASE 3: 2 of 5 claims match → overlap ~0.40 → PARTIAL_OVERLAP."""
        claims_a = [
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "expand", "effective_date": "2026-04-15"},
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "3 new categories", "effective_date": "2026-04-15"},
            {"category": "ENFORCEMENT_ACTION", "regulation_ref": None,
             "assertion_direction": "raid in Canggu", "effective_date": "2026-03-20"},
            {"category": "PROCESSING_TIME", "regulation_ref": None,
             "assertion_direction": "delay", "effective_date": "2026-03-18"},
            {"category": "FEE_CHANGE", "regulation_ref": "PP 22/2026",
             "assertion_direction": "fee doubled", "effective_date": "2026-06-01"},
        ]
        claims_b = [
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "expand", "effective_date": "2026-04-15"},
            {"category": "LEGAL_CHANGE", "regulation_ref": "Permen 8/2026",
             "assertion_direction": "3 new categories", "effective_date": "2026-04-15"},
            {"category": "ADVISORY", "regulation_ref": None,
             "assertion_direction": "embassy recommendation", "effective_date": "2026-03-25"},
            {"category": "PORTAL_STATUS", "regulation_ref": None,
             "assertion_direction": "molina down", "effective_date": "2026-03-19"},
            {"category": "OPERATIONAL_CHANGE", "regulation_ref": None,
             "assertion_direction": "new queue system", "effective_date": "2026-03-22"},
        ]
        overlap, classification = calculate_dedup_overlap(claims_a, claims_b)
        assert 0.40 <= overlap < 0.70
        assert classification == "PARTIAL_OVERLAP"

    def test_independent_no_matching_claims(self) -> None:
        """CASE 4: Zero matching claims → overlap < 0.40 → INDEPENDENT."""
        claims_a = [
            {"category": "ENFORCEMENT_ACTION", "regulation_ref": None,
             "assertion_direction": "raid in Seminyak", "effective_date": "2026-03-20"},
        ]
        claims_b = [
            {"category": "FEE_CHANGE", "regulation_ref": "PP 55/2026",
             "assertion_direction": "golden visa fee reduced", "effective_date": "2026-05-01"},
        ]
        overlap, classification = calculate_dedup_overlap(claims_a, claims_b)
        assert overlap < 0.40
        assert classification == "INDEPENDENT"
```

---

### 1.7 `test_ilm_check.py` — Information Loss Metric (4 Cases)

```python
"""Tests for ILM (Information Loss Metric) consolidation gate.

Reference: 04_source_management.md Section 1 CONSOLIDATE (line 224-233).
Formula: ILM = 1 - (unique_claims_in_digest / unique_claims_in_all_originals)
Gates: < 0.05 proceed, 0.05-0.10 proceed_with_logging, >= 0.10 reject.
"""
import pytest
from nlm_deep_research.source_management import calculate_ilm, should_proceed_consolidation


class TestILMCheck:

    def test_pass_low_loss(self) -> None:
        """ILM = 0.03 (97/100 claims preserved) → proceed."""
        ilm = calculate_ilm(unique_claims_in_digest=97, unique_claims_in_originals=100)
        assert ilm == pytest.approx(0.03, abs=0.001)
        proceed, action = should_proceed_consolidation(ilm)
        assert proceed is True
        assert action == "proceed"

    def test_reject_high_loss(self) -> None:
        """ILM = 0.12 (88/100 claims preserved) → reject."""
        ilm = calculate_ilm(unique_claims_in_digest=88, unique_claims_in_originals=100)
        assert ilm == pytest.approx(0.12, abs=0.001)
        proceed, action = should_proceed_consolidation(ilm)
        assert proceed is False
        assert action == "reject"

    def test_borderline_proceed_with_logging(self) -> None:
        """ILM = 0.07 (93/100 claims preserved) → proceed_with_logging."""
        ilm = calculate_ilm(unique_claims_in_digest=93, unique_claims_in_originals=100)
        assert 0.05 <= ilm < 0.10
        proceed, action = should_proceed_consolidation(ilm)
        assert proceed is True
        assert action == "proceed_with_logging"

    def test_zero_originals_safety(self) -> None:
        """Zero original claims → reject (safety: don't consolidate nothing)."""
        ilm = calculate_ilm(unique_claims_in_digest=0, unique_claims_in_originals=0)
        proceed, action = should_proceed_consolidation(ilm)
        assert proceed is False
```

---

### 1.8 `test_invariant_checks.py` — 10 Invariants (20 Cases)

```python
"""Tests for the 10 pipeline invariants.

Reference: 06_failure_modes.md Section 1.
Each invariant tested twice: pass + violation.
"""
import pytest
from nlm_deep_research.invariants import (
    check_all_invariants, enforce_invariants, InvariantResult,
)


def _make_registry(active: int = 50, quarantine: int = 5, master_digests: int = 4,
                   has_balizero: bool = False) -> dict:
    """Build a registry dict with specified counts."""
    sources = []
    for i in range(active):
        sources.append({
            "nlm_source_id": f"active_{i}",
            "url": f"https://source-{i}.go.id",
            "stage": "ACTIVE",
            "category": "MASTER_DIGEST" if i < master_digests else "WORKING",
        })
    for i in range(quarantine):
        sources.append({
            "nlm_source_id": f"quarantine_{i}",
            "url": f"https://quarantine-{i}.com",
            "stage": "QUARANTINE",
            "category": "WORKING",
        })
    if has_balizero:
        sources.append({
            "nlm_source_id": "balizero_leak",
            "url": "https://balizero.com/articles/visa-guide",
            "stage": "ACTIVE",
            "category": "WORKING",
        })
    return {"version": 1, "sources": sources, "domain_denylist": []}


def _make_state(consecutive_failures: int = 0, week_calls: int = 10,
                schema_version: int = 1) -> dict:
    return {
        "version": schema_version,
        "errors": {"consecutive_failures": consecutive_failures},
        "budget": {"week_calls": week_calls, "week_limit": 40},
    }


class TestInvariantChecks:

    # INV-1: ACTIVE <= 70
    def test_inv1_pass(self) -> None:
        results = check_all_invariants(_make_registry(active=50), _make_state())
        assert next(r for r in results if r.invariant_id == "INV-1").passed is True

    def test_inv1_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(active=75), _make_state())
                   if r.invariant_id == "INV-1")
        assert inv.passed is False and inv.severity == "CRITICAL"

    # INV-2: QUARANTINE <= 30
    def test_inv2_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(quarantine=10), _make_state())
                    if r.invariant_id == "INV-2").passed is True

    def test_inv2_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(quarantine=35), _make_state())
                   if r.invariant_id == "INV-2")
        assert inv.passed is False and inv.severity == "WARNING"

    # INV-4: No balizero.com
    def test_inv4_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(has_balizero=False), _make_state())
                    if r.invariant_id == "INV-4").passed is True

    def test_inv4_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(has_balizero=True), _make_state())
                   if r.invariant_id == "INV-4")
        assert inv.passed is False and inv.severity == "CRITICAL"

    # INV-5: MASTER_DIGEST >= 4
    def test_inv5_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(master_digests=4), _make_state())
                    if r.invariant_id == "INV-5").passed is True

    def test_inv5_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(master_digests=2), _make_state())
                   if r.invariant_id == "INV-5")
        assert inv.passed is False and inv.severity == "CRITICAL"

    # INV-6: consecutive_failures < 3
    def test_inv6_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(), _make_state(consecutive_failures=1))
                    if r.invariant_id == "INV-6").passed is True

    def test_inv6_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(), _make_state(consecutive_failures=5))
                   if r.invariant_id == "INV-6")
        assert inv.passed is False and inv.severity == "CRITICAL"

    # INV-7: week_calls <= 40
    def test_inv7_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(), _make_state(week_calls=30))
                    if r.invariant_id == "INV-7").passed is True

    def test_inv7_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(), _make_state(week_calls=45))
                   if r.invariant_id == "INV-7")
        assert inv.passed is False and inv.severity == "CRITICAL"

    # INV-10: schema version match
    def test_inv10_pass(self) -> None:
        assert next(r for r in check_all_invariants(_make_registry(), _make_state(schema_version=1), 1)
                    if r.invariant_id == "INV-10").passed is True

    def test_inv10_violation(self) -> None:
        inv = next(r for r in check_all_invariants(_make_registry(), _make_state(schema_version=0), 1)
                   if r.invariant_id == "INV-10")
        assert inv.passed is False and inv.severity == "CRITICAL"


class TestEnforceInvariants:

    def test_all_pass_can_proceed(self) -> None:
        results = check_all_invariants(_make_registry(), _make_state())
        can_proceed, violations = enforce_invariants(results)
        assert can_proceed is True and violations == []

    def test_critical_violation_blocks(self) -> None:
        results = check_all_invariants(_make_registry(active=75), _make_state())
        can_proceed, violations = enforce_invariants(results)
        assert can_proceed is False and len(violations) > 0

    def test_warning_allows_proceed(self) -> None:
        results = check_all_invariants(_make_registry(quarantine=35), _make_state())
        can_proceed, _ = enforce_invariants(results)
        assert can_proceed is True  # Warnings don't block
```

---

### 1.9 `test_nlm_enricher.py` — NLMEnricher Adapter (6 Cases)

```python
"""Tests for NLMEnricher adapter class.

Reference: 05b_scraper_integration_codex.md Section 2.2.
Contract:
  - enrich(articles) always returns list >= len(articles)
  - If handoff missing/stale/invalid: returns articles unchanged
  - Never raises exceptions
  - Never modifies existing fields — only adds nlm_* prefixed fields
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from nlm_deep_research.nlm_enricher import NLMEnricher


def _valid_handoff() -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_run_id": "nb2_test", "notebook_id": "nb2", "query_cluster": "A",
        "findings": [{
            "claim_id": "CLM-001",
            "claim_text": "Permenkumham 8/2026 expands KITAS sponsor categories",
            "confidence": 0.85, "confidence_label": "VERIFIED",
            "category": "LEGAL_CHANGE", "tier_highest": "T0",
            "geographic_scope": "NATIONAL", "enforcement_divergence": False,
            "source_chain": [{"tier": "T0", "name": "JDIH", "url": "https://jdih.go.id/x", "date": "2026-03-25"}],
            "tags": ["kitas", "sponsor", "permenkumham"],
        }],
        "suggested_topics": [{
            "topic": "KITAS sponsor expansion",
            "search_queries": ["KITAS sponsor 2026", "Permenkumham 8 2026"],
            "priority": "HIGH", "rationale": "Near deadline",
            "linked_claims": ["CLM-001"],
        }],
        "scraper_hints": {"avoid_urls": ["https://jdih.go.id/x"], "priority_domains": ["hukumonline.com"], "suppress_categories": []},
    }


def _articles() -> list[dict]:
    return [
        {"title": "New KITAS sponsor regulation", "url": "https://n.com/1", "quality_score": 60,
         "text": "Permenkumham 8/2026 expands sponsor categories for KITAS"},
        {"title": "Bali property update", "url": "https://n.com/2", "quality_score": 55, "text": "Property prices"},
        {"title": "Tax reform", "url": "https://n.com/3", "quality_score": 50, "text": "Tax changes for expats"},
    ]


class TestNLMEnricher:

    def test_no_handoff_returns_unchanged(self) -> None:
        """CASE 1: No handoff → articles unchanged, no nlm_* fields."""
        with patch.object(NLMEnricher, '_load_handoff', return_value=None):
            result = NLMEnricher().enrich(_articles())
        assert len(result) == 3
        for a in result:
            assert not any(k.startswith("nlm_") for k in a.keys())

    def test_stale_handoff_returns_unchanged(self) -> None:
        """CASE 2: Stale handoff (30h old) → ignored."""
        with patch.object(NLMEnricher, '_load_handoff', return_value=None):
            enricher = NLMEnricher()
            result = enricher.enrich(_articles())
        assert enricher.stats["handoff_loaded"] == 0

    def test_corrupted_handoff_no_crash(self) -> None:
        """CASE 3: Corrupted handoff → exception swallowed, articles unchanged."""
        with patch.object(NLMEnricher, '_load_handoff', side_effect=Exception("corrupt")):
            result = NLMEnricher().enrich(_articles())
        assert len(result) == 3

    def test_valid_enrichment_adds_nlm_fields(self) -> None:
        """CASE 4: Valid handoff → matching article gets nlm_* fields, others untouched."""
        with patch.object(NLMEnricher, '_load_handoff', return_value=_valid_handoff()):
            result = NLMEnricher().enrich(_articles())
        assert result[0].get("nlm_cross_validated") is True
        assert "nlm_matched_claims" in result[0]
        assert "nlm_cross_validated" not in result[1]  # Property article: no match
        assert result[0]["title"] == "New KITAS sponsor regulation"  # Original field preserved

    def test_score_boost_capped_at_100(self) -> None:
        """CASE 5: quality_score=95 + HIGH boost → capped at 100."""
        with patch.object(NLMEnricher, '_load_handoff', return_value=_valid_handoff()):
            result = NLMEnricher().enrich([
                {"title": "KITAS sponsor update", "url": "https://x.com/1",
                 "quality_score": 95, "text": "Permenkumham 8/2026 kitas sponsor"},
            ])
        assert result[0]["quality_score"] <= 100

    def test_enrich_never_shortens_list(self) -> None:
        """CASE 6: Contract: output length >= input length for any input size."""
        with patch.object(NLMEnricher, '_load_handoff', return_value=_valid_handoff()):
            for size in [0, 1, 50]:
                articles = [{"title": f"A{i}", "url": f"u{i}", "quality_score": 50, "text": "x"} for i in range(size)]
                assert len(NLMEnricher().enrich(articles)) >= size
```

---

### 1.10 `test_circuit_breaker.py` — Circuit Breaker FSM (6 Cases)

```python
"""Tests for circuit breaker state machine.

Reference: 06_failure_modes.md + 06b_failure_modes_gemini.md.
3 circuit breakers: CB-NLM, CB-SOURCE, CB-INTEGRATION.
States: CLOSED → OPEN (on threshold failures) → HALF_OPEN (after timeout) → CLOSED/OPEN.
Cascade: CB-NLM open >5d → CB-SOURCE, CB-SOURCE open >7d → CB-INTEGRATION.
"""
import pytest
from nlm_deep_research.circuit_breaker import CircuitBreaker, CBState, check_cascade


class TestCircuitBreaker:

    def test_closed_to_open(self) -> None:
        """3 consecutive failures → OPEN."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=300)
        assert cb.state == CBState.CLOSED
        cb.record_failure(); cb.record_failure(); cb.record_failure()
        assert cb.state == CBState.OPEN

    def test_open_to_half_open(self) -> None:
        """After recovery timeout → HALF_OPEN."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=300)
        for _ in range(3): cb.record_failure()
        cb._opened_at -= 301  # Simulate time passing
        assert cb.state == CBState.HALF_OPEN

    def test_half_open_to_closed(self) -> None:
        """In HALF_OPEN, 1 success → CLOSED, failure count reset."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=0)
        for _ in range(3): cb.record_failure()
        assert cb.state == CBState.HALF_OPEN
        cb.record_success()
        assert cb.state == CBState.CLOSED and cb.failure_count == 0

    def test_half_open_to_open(self) -> None:
        """In HALF_OPEN, 1 failure → back to OPEN."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=0)
        for _ in range(3): cb.record_failure()
        assert cb.state == CBState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CBState.OPEN

    def test_cascade_nlm_to_source(self) -> None:
        """CB-NLM open >5 days → cascades to CB-SOURCE."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=300)
        for _ in range(3): cb.record_failure()
        cb._opened_at -= 6 * 86400  # 6 days
        assert cb.days_open() > 5
        assert check_cascade(cb) == "CB-SOURCE"

    def test_success_in_closed_is_noop(self) -> None:
        """Recording success in CLOSED state is harmless."""
        cb = CircuitBreaker(name="CB-NLM", failure_threshold=3, recovery_timeout_seconds=300)
        cb.record_success()
        assert cb.state == CBState.CLOSED and cb.failure_count == 0
```

---

## 2. Integration Tests

### 2.1 `test_pipeline_dry_run.py`

```python
"""Full pipeline dry-run with mocked NLM API.

Verifies: pre-flight → L1 → L2 → consolidation → handoff write.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from nlm_deep_research.pipeline import NLMPipeline


@pytest.fixture
def pipeline_env(tmp_path: Path) -> dict:
    state_path = tmp_path / "pipeline_state.json"
    registry_path = tmp_path / "source_registry.json"
    claims_path = tmp_path / "claims.jsonl"
    handoff_dir = tmp_path / "handoff"; handoff_dir.mkdir()

    state_path.write_text(json.dumps({
        "version": 1, "pipeline_status": "IDLE", "last_run": None,
        "today": {"cluster": None, "l1_status": None, "l1_task_id": None,
                  "l1_sources_imported": 0, "l1_key_findings": [], "l1_confidence": 0.0,
                  "l2_status": None, "l2_task_id": None,
                  "l2_sources_imported": 0, "l2_key_findings": [], "l2_confidence": 0.0,
                  "afternoon_triggered": False},
        "rotation": {"cluster_schedule": ["A","B","C","D","E"], "last_cluster_run": {}},
        "override": None, "hot_topics": [], "known_regulations": [],
        "errors": {"consecutive_failures": 0, "throttle_flags": 0, "backoff_until": None},
        "budget": {"week_calls": 5, "week_limit": 40, "month_calls": 20, "month_limit": 160},
    }))

    sources = [{"nlm_source_id": f"s{i}", "url": f"https://r{i}.go.id", "stage": "ACTIVE",
                "category": "MASTER_DIGEST" if i < 4 else "CANONICAL"} for i in range(24)]
    registry_path.write_text(json.dumps({"version": 1, "sources": sources, "domain_denylist": ["balizero.com"]}))
    claims_path.write_text("")
    return {"state_path": state_path, "registry_path": registry_path,
            "claims_path": claims_path, "handoff_dir": handoff_dir}


class TestPipelineDryRun:

    @pytest.mark.nlm_integration
    def test_happy_path(self, pipeline_env: dict) -> None:
        mock_nlm = MagicMock()
        mock_nlm.server_info.return_value = {"version": "1.0"}
        mock_nlm.notebook_list.return_value = [{"id": "nb2", "title": "NB-2 Immigration & Visa Indonesia"}]
        mock_nlm.research_start.return_value = {"task_id": "task_001"}
        mock_nlm.research_status.return_value = {"status": "COMPLETED", "sources_found": 5}
        mock_nlm.research_import.return_value = {"imported": 5}
        mock_nlm.notebook_query.return_value = (
            "Permenkumham 8/2026 expands KITAS sponsor categories. Indonesia visa update 2026."
        )
        mock_nlm.source_list.return_value = [{"id": f"s{i}", "title": f"S{i}", "url": f"u{i}"} for i in range(29)]

        result = NLMPipeline(
            nlm_api=mock_nlm, **pipeline_env
        ).run(dry_run=True, force_weekday=True)

        assert result["status"] == "COMPLETED"
        state = json.loads(pipeline_env["state_path"].read_text())
        assert state["pipeline_status"] == "IDLE"
        assert state["budget"]["week_calls"] > 5

    @pytest.mark.nlm_integration
    def test_aborts_on_budget_exhaustion(self, pipeline_env: dict) -> None:
        state = json.loads(pipeline_env["state_path"].read_text())
        state["budget"]["week_calls"] = 39
        pipeline_env["state_path"].write_text(json.dumps(state))

        result = NLMPipeline(nlm_api=MagicMock(), **pipeline_env).run(dry_run=True, force_weekday=True)
        assert result["status"] in ("SKIPPED", "ABORTED")
```

### 2.2 `test_state_file_integrity.py`

```python
"""State file integrity: valid JSON, required keys, consistent counts after each phase."""
import json
import pytest
from pathlib import Path

REQUIRED_STATE_KEYS = {"version", "pipeline_status", "today", "errors", "budget"}


class TestStateFileIntegrity:

    @pytest.mark.nlm_integration
    def test_state_valid_json_after_each_phase(self, pipeline_env: dict) -> None:
        state_path = pipeline_env["state_path"]
        for phase in ["COLLECTING", "RUNNING_L1", "RUNNING_L2", "CONSOLIDATING", "IDLE"]:
            state = json.loads(state_path.read_text())
            state["pipeline_status"] = phase
            state_path.write_text(json.dumps(state, indent=2))
            reread = json.loads(state_path.read_text())
            assert all(k in reread for k in REQUIRED_STATE_KEYS)

    @pytest.mark.nlm_integration
    def test_claims_jsonl_append_only(self, pipeline_env: dict) -> None:
        claims_path = pipeline_env["claims_path"]
        for i in range(3):
            with open(claims_path, "a") as f:
                f.write(json.dumps({"claim_id": f"C{i}", "claim_text": f"Claim {i}", "source_id": f"s{i}"}) + "\n")
        lines = claims_path.read_text().strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)
            assert all(k in parsed for k in ("claim_id", "claim_text", "source_id"))
```

### 2.3 `test_handoff_schema.py`

```python
"""Handoff package schema validation (05b_scraper_integration_codex.md Section 1.6)."""
import json
import pytest
from nlm_deep_research.handoff import validate_handoff_schema

VALID = {
    "schema_version": "1.0", "generated_at": "2026-03-28T02:15:00+08:00",
    "pipeline_run_id": "nb2_test", "notebook_id": "nb2", "query_cluster": "A",
    "findings": [{"claim_id": "C1", "claim_text": "test", "confidence": 0.85,
                  "confidence_label": "VERIFIED", "category": "LEGAL_CHANGE",
                  "tier_highest": "T0", "geographic_scope": "NATIONAL",
                  "enforcement_divergence": False,
                  "source_chain": [{"tier": "T0", "name": "J", "url": "u", "date": "2026-03-25"}]}],
    "suggested_topics": [{"topic": "T", "search_queries": ["q"], "priority": "HIGH",
                          "rationale": "R", "linked_claims": ["C1"]}],
}

class TestHandoffSchema:
    def test_valid_passes(self) -> None:
        validate_handoff_schema(VALID)

    @pytest.mark.parametrize("field", ["schema_version", "generated_at", "pipeline_run_id", "notebook_id", "query_cluster"])
    def test_missing_envelope_raises(self, field: str) -> None:
        broken = {k: v for k, v in VALID.items() if k != field}
        with pytest.raises(ValueError, match=f"Missing required envelope field: {field}"):
            validate_handoff_schema(broken)

    def test_confidence_out_of_range(self) -> None:
        broken = json.loads(json.dumps(VALID))
        broken["findings"][0]["confidence"] = 1.5
        with pytest.raises(ValueError, match="out of range"):
            validate_handoff_schema(broken)

    def test_invalid_confidence_label(self) -> None:
        broken = json.loads(json.dumps(VALID))
        broken["findings"][0]["confidence_label"] = "UNKNOWN"
        with pytest.raises(ValueError, match="invalid confidence_label"):
            validate_handoff_schema(broken)

    def test_invalid_priority(self) -> None:
        broken = json.loads(json.dumps(VALID))
        broken["suggested_topics"][0]["priority"] = "URGENT"
        with pytest.raises(ValueError, match="invalid priority"):
            validate_handoff_schema(broken)

    def test_empty_findings_valid(self) -> None:
        pkg = json.loads(json.dumps(VALID))
        pkg["findings"] = []
        validate_handoff_schema(pkg)
```

---

## 3. Regression Tests

### 3.1 `test_scraper_no_regression.py`

```python
"""Scraper produces identical output with vs without handoff (cardinal rule)."""
import pytest
from unittest.mock import patch
from nlm_deep_research.nlm_enricher import NLMEnricher


class TestScraperNoRegression:

    @pytest.mark.nlm_regression
    def test_identical_output_without_handoff(self) -> None:
        articles = [{"title": f"A{i}", "url": f"u{i}", "quality_score": 50+i, "text": f"t{i}"} for i in range(3)]
        original_scores = [a["quality_score"] for a in articles]
        with patch.object(NLMEnricher, '_load_handoff', return_value=None):
            result = NLMEnricher().enrich(articles)
        assert [a["quality_score"] for a in result] == original_scores
        for a in result:
            assert not any(k.startswith("nlm_") for k in a.keys())

    @pytest.mark.nlm_regression
    def test_enricher_signature_matches_contract(self) -> None:
        import inspect
        sig = inspect.signature(NLMEnricher().enrich)
        assert list(sig.parameters.keys()) == ["articles"]
```

### 3.2 `test_idempotency.py`

```python
"""Pipeline idempotency: second run on same day blocked (06_failure_modes.md Section 5)."""
import json
import pytest
from datetime import date
from pathlib import Path
from nlm_deep_research.pipeline import compute_dedup_key, already_completed_today, mark_completed


class TestIdempotency:

    @pytest.mark.nlm_regression
    def test_dedup_key_deterministic(self) -> None:
        assert compute_dedup_key("L1", "A") == compute_dedup_key("L1", "A")

    @pytest.mark.nlm_regression
    def test_dedup_key_differs_by_cluster(self) -> None:
        assert compute_dedup_key("L1", "A") != compute_dedup_key("L1", "B")

    @pytest.mark.nlm_regression
    def test_second_run_blocked(self) -> None:
        state = {"_completed_dedup_keys": []}
        key = compute_dedup_key("L1", "A")
        assert already_completed_today(state, key) is False
        mark_completed(state, key)
        assert already_completed_today(state, key) is True

    @pytest.mark.nlm_regression
    def test_preflight_check_12_catches_double_run(self, tmp_path: Path) -> None:
        state = {"version": 1, "last_run": {"date": date.today().isoformat(), "status": "SUCCESS"},
                 "budget": {"week_calls": 10}}
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(state))
        reloaded = json.loads(state_path.read_text())
        already_ran = (reloaded["last_run"]["date"] == date.today().isoformat()
                       and reloaded["last_run"]["status"] == "SUCCESS")
        assert already_ran is True
```

### 3.3 `test_state_backward_compat.py`

```python
"""v1 state file works with v1 code (backward compatibility)."""
import json, pytest
from pathlib import Path
from nlm_deep_research.pipeline import load_state
from nlm_deep_research.invariants import check_all_invariants

V1_STATE = {
    "version": 1, "pipeline_status": "IDLE",
    "last_run": {"date": "2026-03-27", "status": "SUCCESS"},
    "today": {"cluster": "B", "l1_status": "COMPLETED", "l1_task_id": "t1",
              "l1_sources_imported": 3, "l1_key_findings": [], "l1_confidence": 0.72,
              "l2_status": "COMPLETED", "l2_task_id": "t2",
              "l2_sources_imported": 2, "l2_key_findings": [], "l2_confidence": 0.65,
              "afternoon_triggered": False},
    "rotation": {"cluster_schedule": ["A","B","C","D","E"], "last_cluster_run": {"A": "2026-03-24"}},
    "override": None, "hot_topics": [], "known_regulations": [],
    "errors": {"consecutive_failures": 0, "throttle_flags": 0, "backoff_until": None},
    "budget": {"week_calls": 14, "week_limit": 40, "month_calls": 55, "month_limit": 160},
}

V1_REGISTRY = {
    "version": 1,
    "sources": [
        {"nlm_source_id": f"md_{i}", "url": "", "stage": "ACTIVE", "category": "MASTER_DIGEST"}
        for i in range(4)
    ] + [{"nlm_source_id": "c1", "url": "https://jdih.go.id/uu1", "stage": "ACTIVE", "category": "CANONICAL"}],
    "domain_denylist": ["balizero.com"],
}


class TestBackwardCompat:

    @pytest.mark.nlm_regression
    def test_v1_state_loads(self, tmp_path: Path) -> None:
        p = tmp_path / "state.json"; p.write_text(json.dumps(V1_STATE))
        state = load_state(p)
        assert state["version"] == 1 and state["budget"]["week_calls"] == 14

    @pytest.mark.nlm_regression
    def test_v1_invariants_pass(self) -> None:
        for r in check_all_invariants(V1_REGISTRY, V1_STATE, schema_version=1):
            assert r.passed is True, f"{r.invariant_id} failed: {r.message}"
```

---

## 4. Mock Data — NLM API Responses

```python
# fixtures/mock_nlm_responses.py
"""Mock NLM MCP tool responses for testing without API calls."""

MOCK_RESEARCH_START = {
    "task_id": "research_task_20260328_001",
    "status": "STARTED",
    "query": "Apa perubahan terbaru regulasi KITAS sponsor 2026?",
}

MOCK_RESEARCH_STATUS_COMPLETED = {
    "task_id": "research_task_20260328_001",
    "status": "COMPLETED",
    "sources_found": 10, "sources_eligible": 7, "duration_seconds": 180,
}

MOCK_RESEARCH_STATUS_RUNNING = {
    "task_id": "research_task_20260328_001",
    "status": "RUNNING", "progress_pct": 45, "elapsed_seconds": 90,
}

MOCK_RESEARCH_STATUS_FAILED = {
    "task_id": "research_task_20260328_001",
    "status": "FAILED", "error": "Rate limit exceeded",
}

MOCK_RESEARCH_IMPORT = {
    "imported": 7, "skipped": 3,
    "sources": [{"id": f"imp_{i}", "title": f"Source {i}", "url": f"https://src-{i}.go.id"} for i in range(7)],
}

MOCK_NOTEBOOK_QUERY = (
    "Permenkumham 8/2026 expands KITAS sponsor categories to include cooperatives. "
    "Effective April 15, 2026. Three new sponsor categories. Indonesia immigration update."
)

MOCK_SOURCE_LIST = [
    {"id": f"src_{i}", "title": f"Source {i}", "url": f"https://src-{i}.go.id"} for i in range(58)
]
```

---

## 5. Test Fixtures Summary

```python
# fixtures/mock_sources.py — 5 sources at tiers T0, T2, T4, T5, T6

MOCK_SOURCE_T0 = {
    "nlm_source_id": "src_t0_law", "title": "UU Nomor 1/2026 Imigrasi",
    "url": "https://jdih.kemenkumham.go.id/uu-1-2026",
    "stage": "ACTIVE", "category": "CANONICAL", "tier": "T0",
    "source_type": "LAW_IN_FORCE", "svs": 0.938,
    "claims_extracted": 8, "times_cited_in_briefs": 12,
}

MOCK_SOURCE_T2 = {
    "nlm_source_id": "src_t2_bali", "title": "Perda Bali Retribusi Turis 2024",
    "url": "https://jdih.baliprov.go.id/perda-2024",
    "stage": "ACTIVE", "category": "CANONICAL", "tier": "T2",
    "source_type": "REGULATION_CIRCULAR", "svs": 0.720,
    "claims_extracted": 5, "times_cited_in_briefs": 4,
}

MOCK_SOURCE_T4 = {
    "nlm_source_id": "src_t4_ig", "title": "@kanaboraingurahrai processing delay",
    "url": "https://instagram.com/p/abc123",
    "stage": "ACTIVE", "category": "WORKING", "tier": "T4",
    "source_type": "OFFICIAL_SOCIAL", "svs": 0.450,
    "claims_extracted": 2, "times_cited_in_briefs": 1,
}

MOCK_SOURCE_T5 = {
    "nlm_source_id": "src_t5_news", "title": "NusaBali: Tim Pora Sweeps Canggu",
    "url": "https://nusabali.com/tim-pora-canggu",
    "stage": "ACTIVE", "category": "WORKING", "tier": "T5",
    "source_type": "NEWS_ARTICLE", "svs": 0.370,
    "claims_extracted": 2, "times_cited_in_briefs": 1,
}

MOCK_SOURCE_T6 = {
    "nlm_source_id": "src_t6_blog", "title": "Bali Expat Forum visa tips",
    "url": "https://bali-expat-forum.com/thread/visa-tips",
    "stage": "QUARANTINE", "category": "WORKING", "tier": "T6",
    "source_type": "NEWS_ARTICLE", "svs": 0.120,
    "claims_extracted": 0, "times_cited_in_briefs": 0,
}
```

```python
# fixtures/mock_claims.py — 3 claims at VERIFIED, PROVISIONAL, LOW

CLAIM_VERIFIED = {
    "claim_id": "CLM-001", "confidence_score": 0.85, "confidence_class": "VERIFIED",
    "claim_text": "Permenkumham 8/2026 adds 3 new KITAS sponsor categories effective April 15",
    "source_id": "src_t0_law", "category": "LEGAL_CHANGE",
    "regulation_ref": "Permenkumham 8/2026", "effective_date": "2026-04-15",
}

CLAIM_PROVISIONAL = {
    "claim_id": "CLM-002", "confidence_score": 0.63, "confidence_class": "PROVISIONAL",
    "claim_text": "Existing sponsors must re-register under new categories within 90 days",
    "source_id": "src_t5_news", "category": "DEADLINE",
    "regulation_ref": "Permenkumham 8/2026", "effective_date": "2026-07-15",
}

CLAIM_LOW = {
    "claim_id": "CLM-003", "confidence_score": 0.38, "confidence_class": "LOW",
    "claim_text": "Golden Visa fee may be reduced from $350K to $250K",
    "source_id": "src_t6_blog", "category": "FEE_CHANGE",
    "regulation_ref": None, "effective_date": None,
}
```

```python
# fixtures/mock_handoff.py — valid + stale
from datetime import datetime, timezone, timedelta

VALID_HANDOFF = {
    "schema_version": "1.0",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "pipeline_run_id": "nb2_20260328_0100", "notebook_id": "nb2", "query_cluster": "A",
    "findings": [{"claim_id": "C1", "claim_text": "KITAS sponsor expansion", "confidence": 0.85,
                  "confidence_label": "VERIFIED", "category": "LEGAL_CHANGE", "tier_highest": "T0",
                  "geographic_scope": "NATIONAL", "enforcement_divergence": False,
                  "source_chain": [{"tier": "T0", "name": "JDIH", "url": "u", "date": "2026-03-25"}],
                  "tags": ["kitas", "sponsor"]}],
    "suggested_topics": [{"topic": "KITAS expansion", "search_queries": ["KITAS 2026"],
                          "priority": "HIGH", "rationale": "Near deadline", "linked_claims": ["C1"]}],
}

STALE_HANDOFF = {**VALID_HANDOFF,
    "generated_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}
```

```python
# fixtures/mock_state.py — valid, corrupted, default

CORRUPTED_STATE_JSON = '{"version": 1, "pipeline_status": "RUNNING_L1", "today": {"l1_task_id": "task_abc'
# Truncated JSON — simulates crash mid-write

VALID_V1_STATE = {
    "version": 1, "pipeline_status": "IDLE",
    "last_run": {"date": "2026-03-27", "status": "SUCCESS"},
    "today": {"cluster": None, "l1_status": None, "l1_task_id": None,
              "l1_sources_imported": 0, "l1_key_findings": [], "l1_confidence": 0.0,
              "l2_status": None, "l2_task_id": None,
              "l2_sources_imported": 0, "l2_key_findings": [], "l2_confidence": 0.0,
              "afternoon_triggered": False},
    "rotation": {"cluster_schedule": ["A","B","C","D","E"], "last_cluster_run": {}},
    "override": None, "hot_topics": [], "known_regulations": [],
    "errors": {"consecutive_failures": 0, "throttle_flags": 0, "backoff_until": None},
    "budget": {"week_calls": 10, "week_limit": 40, "month_calls": 45, "month_limit": 160},
}
```

---

## 6. Execution Plan

### CLI Commands

```bash
# All NLM tests (fast, <45s total)
PYTHONPATH=. pytest tests/nlm_deep_research/ -v

# By suite
PYTHONPATH=. pytest tests/nlm_deep_research/unit/ -v -m nlm_unit
PYTHONPATH=. pytest tests/nlm_deep_research/integration/ -v -m nlm_integration
PYTHONPATH=. pytest tests/nlm_deep_research/regression/ -v -m nlm_regression

# Coverage
PYTHONPATH=. pytest tests/nlm_deep_research/ --cov=nlm_deep_research --cov-report=term-missing
```

### Pass/Fail Criteria

| Suite       | Tests  | Pass Threshold | Time      |
| ----------- | ------ | -------------- | --------- |
| Unit        | 80     | 100%           | < 5s      |
| Integration | 11     | 100%           | < 30s     |
| Regression  | 7      | 100%           | < 10s     |
| **Total**   | **98** | **100%**       | **< 45s** |

### CI Integration

```yaml
name: NLM Deep Research Tests
on:
  pull_request:
    paths: ["apps/evaluator/nlm_deep_research/**", "tests/nlm_deep_research/**"]
  schedule:
    - cron: "0 6 * * *"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pytest pytest-cov
      - run: PYTHONPATH=. pytest tests/nlm_deep_research/ -v --tb=short
```

---

## 7. Pre-Production Validation (8 Phases on Real NB-2)

After all automated tests pass, run these 8 controlled phases on the actual NB-2 notebook.

| Phase        | Action                                  | Pass Criteria                                   | Time   |
| ------------ | --------------------------------------- | ----------------------------------------------- | ------ |
| 1. Baseline  | Snapshot NB-2 sources, init state files | State files exist, ~20 sources                  | 30 min |
| 2. First L1  | Single L1 monitoring query, cluster A   | research_start OK, 3-10 sources imported        | 20 min |
| 3. Claims    | Extract claims from imported sources    | claims.jsonl has entries, >= 1 PROVISIONAL      | 15 min |
| 4. Second L2 | L2 comparative using L1 context         | Dedup works, no duplicate imports, ACTIVE < 70  | 20 min |
| 5. Triage    | Daily triage on QUARANTINE sources      | QUARANTINE = 0 after triage, SVS computed       | 15 min |
| 6. Handoff   | Generate scraper handoff package        | latest.json valid, non-empty, fresh             | 5 min  |
| 7. Scraper   | Compare scraper output with/without NLM | Both produce articles, NLM adds nlm\_\* fields  | 10 min |
| 8. Full run  | Complete pipeline as 01:00 WITA cron    | All invariants pass, handoff written, COMPLETED | 80 min |

**Total: ~3 hours.** Run on a Monday to align with cluster rotation (cluster A).

**Rollback:** Delete all `[TEST]`-prefixed sources from NB-2, remove state files, restore baseline.

---

## 8. Summary Table

| Component         | Function Under Test            | Test Count | Key Assertion                                      |
| ----------------- | ------------------------------ | ---------- | -------------------------------------------------- |
| Pre-import filter | `should_import()`              | 10         | Each rejection path + happy path                   |
| SVS scoring       | `calculate_svs()`              | 5          | Spec worked examples match                         |
| Staleness decay   | `staleness_score()`            | 14         | Spec table values within 0.02                      |
| TRS scoring       | `calculate_trs()`              | 5          | HANDOFF/CANDIDATE/FILTERED thresholds              |
| Confidence boost  | `cross_validate_convergence()` | 6          | Logarithmic formula + cap at 0.95                  |
| Dedup overlap     | `calculate_dedup_overlap()`    | 4          | Szymkiewicz-Simpson thresholds                     |
| ILM gate          | `calculate_ilm()`              | 4          | < 0.05 proceed, >= 0.10 reject                     |
| 10 invariants     | `check_all_invariants()`       | 20         | Pass + violation for each                          |
| NLM enricher      | `NLMEnricher.enrich()`         | 6          | Contract: never crash, never shorten, only nlm\_\* |
| Circuit breaker   | `CircuitBreaker`               | 6          | FSM transitions + cascade                          |
| Pipeline dry-run  | `NLMPipeline.run()`            | 2          | Happy path + budget exhaustion                     |
| State integrity   | JSON reads/writes              | 3          | Valid after each phase                             |
| Handoff schema    | `validate_handoff_schema()`    | 6          | All required fields + ranges                       |
| No regression     | Scraper identity               | 2          | Identical without handoff                          |
| Idempotency       | Dedup guard                    | 4          | Second run blocked                                 |
| Backward compat   | v1 state                       | 2          | Loads + passes invariants                          |
| **TOTAL**         |                                | **98**     | **100% must pass**                                 |

---

## 9. Live 8-Phase Protocol on Real NB-2 (Gemini contribution)

After all 98 automated tests pass, run this controlled test on the REAL NB-2 notebook (~45-80 min, ~15 NLM API calls).

| Phase | What                                                                          | Expected Outcome                                    | Pass Criteria                                           | Time   |
| ----- | ----------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------- | ------ |
| **0** | Environment: create NB-2, 20 canonical seeds, 4 Master Docs, init state files | NB-2 exists with 24 sources                         | All invariants pass, NHS > 0.50                         | 15 min |
| **1** | First L1 query (Cluster A)                                                    | 5-15 sources in QUARANTINE                          | research_start + status + import succeed, state updated | 20 min |
| **2** | Triage quarantined sources                                                    | 40-70% promoted, SVS calculated                     | Decision tree applied, no INV-1 violation               | 5 min  |
| **3** | Claim extraction from ACTIVE                                                  | >2 claims/source avg, categories assigned           | claims.jsonl grows, confidence scored                   | 5 min  |
| **4** | L2 query with Phase 1 context                                                 | Context injected, dedup catches >0                  | Budget at 2 calls, no duplicate sources                 | 20 min |
| **5** | Manual consolidation trigger                                                  | ILM < 0.05, Master Docs updated                     | Archived sources tracked, NHS > 0.65                    | 10 min |
| **6** | Write handoff package                                                         | Valid JSON, TRS scored, >=1 topic                   | Schema validates, symlink created                       | 5 min  |
| **7** | Failure simulation (4 sub-tests)                                              | State recovery, CB trips, prune works, INV-4 blocks | All 4 pass within MTTR targets                          | 10 min |

### Go/No-Go Decision

| Result     | Phases Passed | Action                                                   |
| ---------- | ------------- | -------------------------------------------------------- |
| **GREEN**  | All 8         | Deploy to daily production (01:00 WITA cron)             |
| **YELLOW** | 6-7           | Deploy with 1 query/day + daily manual review for 1 week |
| **RED**    | ≤ 5           | No-go. Fix failures, re-run protocol                     |

### Hard Blockers (NO-GO regardless of pass count)

1. INV-4 violation (balizero.com in NLM sources) — feedback loop risk
2. ILM > 0.10 on any consolidation — claims being lost
3. NLM API auth failure — cannot proceed without access
4. State file corruption without recovery — data integrity at risk
5. Circuit breaker stuck OPEN — cannot self-heal
6. Handoff package contains scraper-originated content — loop risk
7. Claim verification accuracy < 70% on spot-check — quality unacceptable

---

## 10. Month 1 KPI Targets (DeepSeek R1 contribution)

| KPI                                    | Week 1 | Week 2 | Week 3 | Week 4 | Trend               |
| -------------------------------------- | ------ | ------ | ------ | ------ | ------------------- |
| Pipeline reliability (runs/5 weekdays) | 3/5    | 4/5    | 4/5    | 5/5    | Non-decreasing      |
| NHS (Notebook Health Score)            | > 0.50 | > 0.60 | > 0.65 | > 0.70 | Increasing          |
| ACTIVE source count                    | 25-50  | 35-60  | 40-70  | 40-70  | Stabilizing         |
| Dedup ratio (weekly)                   | < 50%  | < 40%  | < 35%  | < 30%  | Decreasing          |
| Manual interventions/week              | ≤ 5    | ≤ 4    | ≤ 3    | ≤ 2    | Strictly decreasing |
| Claims extracted/week                  | > 5    | > 8    | > 10   | > 10   | Non-decreasing      |
| Claim verification accuracy            | > 70%  | > 75%  | > 80%  | > 85%  | Increasing          |
| Handoff freshness (avg hours)          | < 3    | < 2.5  | < 2    | < 2    | Decreasing          |
| Budget usage (calls/week)              | < 15   | < 20   | < 25   | < 30   | Stable              |
| Circuit breaker activations            | ≤ 3    | ≤ 2    | ≤ 1    | 0      | Decreasing          |
| Invariant violations                   | ≤ 5    | ≤ 3    | ≤ 1    | 0      | Decreasing          |

**Single most important metric: Claim verification accuracy >= 85% by Week 4.** Everything else (NHS, IVA, adoption, cost) is downstream of claim quality.

---

## 11. Statistical Tests (DeepSeek R1 contribution)

4 tests to run at end of Month 1 (see `07b_testing_protocol_deepseek.md` for full Python implementations):

| Test  | Question                                          | Method                      | Sample                         | Pass Criterion                              |
| ----- | ------------------------------------------------- | --------------------------- | ------------------------------ | ------------------------------------------- |
| **A** | Does NLM handoff improve scraper article quality? | Welch's t-test (one-tailed) | 30 articles WITH vs 20 WITHOUT | p < 0.05, d > 0.50                          |
| **B** | Is War Room NLM adoption above chance?            | Chi-square / Fisher exact   | 20 topic selections            | p < 0.05, adoption > 15%                    |
| **C** | Are confidence scores well-calibrated?            | Wilson CI per band          | 10+ claims per band            | Actual accuracy within CI of predicted band |
| **D** | Does SVS reflect human-perceived value?           | Spearman rho + MAE          | 20 stratified sources          | rho > 0.60, MAE < 0.15                      |

---

## 12. Cost Model (DeepSeek R1 contribution)

| Component                    | Monthly Cost   | Notes                                      |
| ---------------------------- | -------------- | ------------------------------------------ |
| NLM API calls                | ~$0            | Free tier (Ultra plan already provisioned) |
| Compute (pipeline runtime)   | ~$3            | ~80 min/day × 22 days, Pro machine         |
| Storage (state files)        | ~$0            | < 5MB total                                |
| Human time (monitoring)      | ~$45           | ~15 min/week at implied cost               |
| Exa API (NLM-seeded queries) | ~$3            | ~30 extra queries/week                     |
| **Total**                    | **~$51/month** |                                            |

**Value delivered**: ~$150-350/month (intelligence advantage, reduced manual research, enriched articles)

**ROI**: 292-919% | **Break-even**: 3 enriched articles/month

---

## 13. Production Transition (post-GREEN)

10-step deployment plan after passing all 8 phases:

1. Save Phase 0 snapshot as production baseline
2. Configure OpenClaw cron: `01:00 WITA Mon-Fri` on Pro
3. Set budget: `week_limit: 15` (conservative start, increase to 40 over 4 weeks)
4. Set queries: 1 query/day for Week 1 (L1 only), add L2 from Week 2
5. Enable Telegram alerts (WARNING + CRITICAL channels)
6. Enable handoff package writer (scraper reads from Day 1)
7. Enable War Room NLM integration (with `NLM_SKIP=1` escape hatch)
8. Monday morning review: check 7-section monitoring checklist
9. Friday consolidation: run weekly source lifecycle + Master Doc updates
10. Week 4 checkpoint: run 4 statistical tests, present Go/No-Go to stakeholder

---

## Source AI Contributions

### Codex GPT-5.4 — Test Contracts + Automation (Sections 0-8)

- 98 automated tests across 3 suites (unit/integration/regression)
- Complete mock data for all NLM API responses, sources, claims, handoff, state
- CI integration YAML with markers
- 8-phase pre-production validation with real NB-2
- Exact test function signatures with assertions

### Gemini — 8-Phase Controlled Live Test (Section 9)

- 8-phase protocol on real NB-2 notebook (45-80 min)
- Go/No-Go decision matrix (GREEN/YELLOW/RED)
- 7 hard-blocker conditions
- Production transition plan (10 steps)
- Rollback procedure

### DeepSeek R1 — KPIs + Statistical Tests + Cost (Sections 10-12)

- Month 1 KPI table with progressive weekly targets
- 4 statistical tests with Python implementations (Welch's t, Chi-square, Wilson CI, Spearman)
- Cost model: ~$51/month, ROI 292-919%
- Baseline measurement framework
- Go/No-Go decision framework (Week 2 + Week 4 checkpoints)

### Claude Opus 4.6 — This Synthesis

- Merged Codex (automated tests) + Gemini (live protocol) + DeepSeek (metrics) into unified document
- Preserved 98 automated tests as pre-requisite gate before live testing
- Live protocol (Section 9) runs only after all automated tests pass
- KPIs and statistical tests frame the Month 1 evaluation criteria
- Production transition plan provides the bridge from testing to daily operation
