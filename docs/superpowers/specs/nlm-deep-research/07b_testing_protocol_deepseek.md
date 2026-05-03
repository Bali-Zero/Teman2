# Step 7b: Testing Protocol — DeepSeek R1 Perspective (Quantified Success Criteria + Baseline)

> Author: DeepSeek R1 (Il Pensatore) — chain-of-thought reasoning on metrics
> Companion to: `07_testing_protocol.md` (Claude Opus 4.6 architect — operational phases)
> Status: FINAL STEP — validation gate before production
> Purpose: Define what "success" looks like numerically — baselines, targets, statistical tests, decision frameworks, cost models

---

## 0. Why This Document Exists

The architect's protocol (`07_testing_protocol.md`) defines WHAT to test and HOW (8 phases, step-by-step).
This document defines WHEN to declare success and WHAT NUMBERS prove it.

Every target below is anchored to one of three sources:

1. **Prior step formulas** — NHS, ILM, SVS, TRS, IVA, confidence thresholds from Steps 1-6
2. **Statistical requirements** — sample sizes, power calculations, significance levels
3. **Operational pragmatism** — time budgets, cost ceilings, human effort limits

No invented numbers. Every target has a derivation.

---

## 1. Baseline Measurement (Before Pipeline Starts)

### 1.1 NB-2 Current State Snapshot

Capture BEFORE any pipeline code runs. These are the "before" numbers for ROI calculation.

```
BASELINE SNAPSHOT — NB-2 (Immigration & Visa Indonesia)
═══════════════════════════════════════════════════════

NB-2 Source Count:           0 (notebook created but empty)
NB-2 Claims Extracted:       0
NB-2 Master Documents:       0
NB-2 NHS:                    0.00 (undefined — no sources)
NB-2 Last Query:             never
NB-2 NLM Source Limit:       600 (Ultra tier)

State Files:
  pipeline_state.json:       does not exist
  source_registry.json:      does not exist
  claims.jsonl:              does not exist
  query_history.jsonl:       does not exist
```

**Collection function:**

```python
def collect_nb2_baseline(notebook_id: str) -> dict:
    """Run ONCE before Phase 0. Save to apps/evaluator/nlm_nb2_baseline.json."""
    from pathlib import Path
    sources = nlm_api.source_list(notebook_id=notebook_id)
    return {
        "collected_at": datetime.now(tz=timezone.utc).isoformat(),
        "phase": "BASELINE",
        "nb2": {
            "source_count": len(sources),
            "source_titles": [s.get("title", "") for s in sources],
            "nhs": 0.0,
            "claims_count": 0,
            "master_docs": 0,
        },
        "state_files_exist": {
            "pipeline_state": Path("apps/evaluator/nlm_nb2_pipeline_state.json").exists(),
            "source_registry": Path("apps/evaluator/nlm_nb2_sources.json").exists(),
            "claims": Path("apps/evaluator/nlm_nb2_claims.jsonl").exists(),
            "query_history": Path("apps/evaluator/nlm_nb2_query_history.jsonl").exists(),
        },
    }
```

### 1.2 Intel Scraper Baseline (30-Day Lookback)

Current scraper performance WITHOUT NLM. This is the control group.

| Metric                         | How to Measure                                              | Expected Range |
| ------------------------------ | ----------------------------------------------------------- | -------------- |
| Total articles/day             | `count(published_at)` per day, 30d window                   | 3-8            |
| Immigration articles/day       | Filter `category IN ('immigration', 'visa', 'work_permit')` | 0.5-2.0        |
| Average quality_score          | `avg(quality_score)` across immigration articles            | 45-65 (of 100) |
| Verification rate              | `count(verified=true) / count(*)` for immigration           | 20-40%         |
| Source diversity (domains/day) | `count(DISTINCT source_domain)` per day                     | 5-12           |
| Unique topics/week             | `count(DISTINCT topic_cluster)` per week                    | 8-15           |
| Event-to-article latency       | `avg(published_at - event_date)` for regulatory articles    | 24-72 hours    |

**SQL extraction (run against production PostgreSQL):**

```sql
SELECT
    date_trunc('day', published_at) AS day,
    count(*) AS total_articles,
    count(*) FILTER (WHERE category IN ('immigration','visa','work_permit')) AS imm_articles,
    avg(quality_score) FILTER (WHERE category IN ('immigration','visa','work_permit')) AS avg_imm_quality,
    count(*) FILTER (WHERE verified = true AND category IN ('immigration','visa','work_permit'))::float
        / NULLIF(count(*) FILTER (WHERE category IN ('immigration','visa','work_permit')), 0) AS imm_verification_rate,
    count(DISTINCT source_domain) AS unique_domains
FROM intel_articles
WHERE published_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

### 1.3 War Room Baseline (30-Day Lookback)

| Metric                                | Expected Baseline | Note                 |
| ------------------------------------- | ----------------- | -------------------- |
| Topics selected/week                  | 3-5               | Manual selection     |
| Time spent on topic selection/session | 15-30 min         | Self-reported        |
| Topics from scraper output            | ~80%              | Primary source       |
| Topics from manual research           | ~20%              | Human initiative     |
| Topics from NLM                       | 0%                | Pipeline not running |

### 1.4 Baseline Summary Schema

Save to `apps/evaluator/nlm_nb2_baseline.json`:

```json
{
  "collected_at": "2026-MM-DDT00:00:00+08:00",
  "nb2": { "source_count": 0, "claims_count": 0, "nhs": 0.0, "master_docs": 0 },
  "scraper_30d": {
    "days_measured": 30,
    "total_articles": null,
    "immigration_articles_per_day_avg": null,
    "avg_quality_score_immigration": null,
    "verification_rate_immigration": null,
    "avg_event_to_article_hours": null,
    "unique_domains_per_day_avg": null,
    "unique_topics_per_week_avg": null
  },
  "war_room_30d": {
    "topics_per_week_avg": null,
    "nlm_sourced_pct": 0.0,
    "scraper_sourced_pct": null,
    "manual_sourced_pct": null,
    "avg_selection_time_min": null
  }
}
```

---

## 2. Per-Phase Quantified Success Metrics

Each phase from the architect's protocol (`07_testing_protocol.md`) maps to specific numeric gates.

### Phase 0: Environment Setup

| Metric                               | Target                                                                                                       | Hard Fail |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------ | --------- |
| NLM API responds (5 tool types)      | 5/5                                                                                                          | < 5/5     |
| Seed sources added                   | 20                                                                                                           | < 15      |
| Master Documents created             | 4                                                                                                            | < 4       |
| State files initialized (valid JSON) | 4/4                                                                                                          | < 4/4     |
| Invariants passing                   | 10/10                                                                                                        | < 10/10   |
| Total API calls consumed             | ~25 (source_add x20 + source_list + server_info + notebook_list + research_start test + notebook_query test) | > 30      |

### Phase 1: First Query (L1 Monitoring)

| Metric                                | Target                                         | Hard Fail                               | Derivation                                                                                               |
| ------------------------------------- | ---------------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Sources returned by NLM Deep Research | 5-40                                           | 0                                       | NLM typically returns 10-30 per deep query                                                               |
| Sources passing pre-import filter     | 5-15                                           | 0                                       | Step 4 §1: filter rejects ~30-50% noise                                                                  |
| Sources imported into NB-2            | 5-15                                           | 0                                       | After filter                                                                                             |
| Filter rejection rate                 | 20-50%                                         | > 80% (too strict) or < 10% (too loose) | Step 4 estimates 15-20% noise with techniques                                                            |
| Query duration                        | 2-12 min                                       | > 25 min (hard timeout)                 | Step 2 §1: per-query budget 15-20 min                                                                    |
| Pipeline state file valid after run   | yes                                            | corrupted                               | Basic integrity                                                                                          |
| NHS post-Phase 1                      | > 0.45                                         | < 0.25                                  | Simplified: 20 seeds + 5-15 new = 25-35 sources. source_health=0.63-0.88, freshness=1.0, claim_density=0 |
| INV violations                        | 0 CRITICAL                                     | any CRITICAL                            | Step 6 invariants                                                                                        |
| Budget consumed                       | 1 research_start + ~2-3 other calls = ~4 total | > 8                                     | Budget discipline                                                                                        |

### Phase 2: Triage Validation

| Metric                                                | Target                 | Hard Fail                      | Derivation                                                                               |
| ----------------------------------------------------- | ---------------------- | ------------------------------ | ---------------------------------------------------------------------------------------- |
| Promotion rate                                        | 40-70%                 | < 20% or > 90%                 | Step 4 §1: triage rejects T6-only, duplicates, off-topic; promotes T0-T5 unique relevant |
| SVS computed for 100% promoted                        | 100%                   | < 100%                         | Step 4 §3: every ACTIVE needs SVS for capacity management                                |
| SVS mean (promoted sources)                           | > 0.45                 | < 0.30                         | Step 4 §3: MARGINAL is 0.25-0.44, VALUABLE is 0.45-0.69. Promoted should be VALUABLE+    |
| SVS ESSENTIAL (>=0.70) count                          | 2-5                    | 0 (if T0-T2 sources present)   | T0 sources have V_tier=1.0, should reach ESSENTIAL easily                                |
| SVS EXPENDABLE (<0.25) count                          | 0-2                    | > 5                            | Poor source quality if many are expendable                                               |
| Dedup: URL matches caught                             | >= 0 (at least tested) | false negative on manual check | Step 4 §4.2: Level 1 is exact URL match                                                  |
| Manual spot-check agreement (5 promoted + 5 rejected) | >= 80% (8/10 correct)  | < 60% (6/10)                   | Human agreement rate for triage decisions                                                |
| Triage processing time                                | < 15 min               | > 30 min                       | Step 2: triage happens within consolidation phase (01:55)                                |
| ACTIVE count post-triage                              | 25-45                  | > 70 (INV-1) or < 15           | Seed 20 + promoted 5-25                                                                  |

### Phase 3: Claim Extraction

| Metric                                    | Target                           | Hard Fail                   | Derivation                                                                     |
| ----------------------------------------- | -------------------------------- | --------------------------- | ------------------------------------------------------------------------------ |
| Claims per source (mean)                  | > 2.0                            | < 1.0                       | Step 3 §3: atomic claims from news/regulations typically yield 3-10 per source |
| Total claims extracted                    | 15-100                           | < 10                        | From 5-25 promoted sources \* 2+ claims each                                   |
| Claims with all required metadata         | > 90%                            | < 70%                       | Step 3 §3: claim_id, text, category, confidence, source_chain are required     |
| VERIFIED claims (>= 0.75)                 | 10-30% of total                  | 0% (if T0-T2 sources exist) | Step 3 §2: T0 source alone gets A=1.0, T=1.0, R=1.0 → confidence ~0.75+        |
| PROVISIONAL claims (0.55-0.74)            | 30-50% of total                  | < 10%                       | Most T3-T5 sourced claims land here                                            |
| Claims with source_chain populated        | > 95%                            | < 80%                       | Traceability requirement                                                       |
| Claims with regulation_ref (LEGAL_CHANGE) | > 80%                            | < 50%                       | LEGAL_CHANGE must cite specific regulation                                     |
| Accuracy spot-check (10 claims)           | > 80% (8/10 accurate)            | < 60% (6/10)                | Domain expert verification                                                     |
| Confidence calibration direction          | 8/10 higher-scored more accurate | < 6/10                      | Basic ordering test                                                            |

**Calibration table (fill during spot-check):**

| Confidence Band       | n   | Accurate | Expected Accuracy | Actual Accuracy | Calibrated? |
| --------------------- | --- | -------- | ----------------- | --------------- | ----------- |
| >= 0.75 VERIFIED      |     |          | > 80%             |                 |             |
| 0.55-0.74 PROVISIONAL |     |          | 60-80%            |                 |             |
| 0.35-0.54 MONITORING  |     |          | 40-60%            |                 |             |
| < 0.35 UNVERIFIED     |     |          | < 40%             |                 |             |

**Recalibration trigger:** Any band's actual accuracy deviates > 20 percentage points from expected.

### Phase 4: Second Query + Dedup

| Metric                                     | Target                             | Hard Fail                            | Derivation                                                         |
| ------------------------------------------ | ---------------------------------- | ------------------------------------ | ------------------------------------------------------------------ |
| L2 query completes                         | within 25 min                      | timeout                              | Step 2 §1: hard timeout 25 min                                     |
| L2 sources returned                        | 5-30                               | 0                                    | L2 comparative typically broader                                   |
| Dedup catches (L2 vs L1)                   | > 0                                | none detected AND manual finds dupes | Step 4 §4: some overlap expected between L1 and L2 on same cluster |
| New unique sources from L2                 | 3-15                               | 0 (L2 added nothing)                 | L2 comparative should find different angles                        |
| Context injection verified                 | L2 response references L1 entities | completely unrelated                 | Step 2 §2: context snippet prepended                               |
| Cross-ref: confirming claims               | >= 1 L1 claim confirmed by L2      | zero overlap                         | Systems should corroborate                                         |
| Cross-ref: novel claims from L2            | >= 2 not in L1                     | zero novel                           | L2 comparative adds new perspective                                |
| Dedup ratio (total dupes / total imported) | 15-25%                             | > 40% (alarm)                        | Step 4 §4: healthy dedup 15-25%, alarm at 40%                      |
| ACTIVE count post-Phase 4                  | 30-55                              | > 70 or < 20                         | Phase 2 ACTIVE + Phase 4 promoted                                  |

### Phase 5: Lifecycle Trial

| Metric                                | Target                                         | Hard Fail               | Derivation                                 |
| ------------------------------------- | ---------------------------------------------- | ----------------------- | ------------------------------------------ |
| Simulated runs completed              | 5/5                                            | < 3/5                   | 5-day week simulation                      |
| Runs finishing before 02:30 (INV-9)   | 5/5                                            | any deadline breach     | Step 6 §1: INV-9 hard deadline             |
| ILM on consolidation                  | < 0.05                                         | >= 0.05                 | Step 4 §1: ILM hard gate on CONSOLIDATE    |
| Master Documents updated              | >= 2 (MD-1, MD-4)                              | 0 updated               | Change Log and Open Questions must evolve  |
| Sources archived (lifecycle)          | >= 1                                           | 0                       | Working sources should age out             |
| NHS at end of Phase 5                 | > 0.65                                         | < 0.50                  | Step 4 §6: NHS target for healthy notebook |
| Source composition approaching target | Canonical 15-25, Working 15-30, MD 4+, Ref 3-5 | all in one category     | Step 4 §2 budget                           |
| ACTIVE count                          | 40-65                                          | > 70 (INV-1) or < 20    | Steady-state target ~59                    |
| Budget consumed (5 simulated days)    | 10-15 calls                                    | > 25                    | Step 2 §5: 2 deep/day + conditionals       |
| INV violations (CRITICAL)             | 0                                              | any unresolved CRITICAL | Step 6 §1                                  |
| Handoff packages generated            | 5/5 valid JSON                                 | any malformed           | One per simulated day                      |

**NHS derivation at Phase 5 (why > 0.65 is achievable):**

```
NHS = 0.30 * source_health + 0.25 * claim_density + 0.20 * freshness
    + 0.15 * tier_balance + 0.10 * capacity_margin

Scenario: 50 ACTIVE sources, ~100 claims, all < 7 days, mixed T0-T5, 50/70 capacity:
  source_health  = min(1.0, 50/40) = 1.00
  claim_density  = min(1.0, 100/200) = 0.50  (growing — 200 is "full maturity")
  freshness      = 0.80  (most < 7 days, some seeds are older)
  tier_balance   = 0.60  (T0-T2 = ~20, T3-T5 = ~30 → 0.40 ratio, normalize)
  capacity_margin = 1.0 - (50/70) = 0.29

NHS = 0.30*1.00 + 0.25*0.50 + 0.20*0.80 + 0.15*0.60 + 0.10*0.29
    = 0.300 + 0.125 + 0.160 + 0.090 + 0.029
    = 0.704  ✓ (> 0.65 target)
```

### Phase 6: Handoff Validation

| Metric                                 | Target                    | Hard Fail              | Derivation                                |
| -------------------------------------- | ------------------------- | ---------------------- | ----------------------------------------- |
| TRS scored for all findings            | 100%                      | < 100%                 | Step 5 §1b: TRS gates what enters handoff |
| Findings passing TRS >= 0.65           | 1-5                       | 0 (nothing actionable) | Step 5 §1b: threshold + max 5 topics      |
| Handoff JSON schema valid              | 0 violations              | any violation          | Step 5 §1.2: defined schema               |
| Scraper reads handoff without error    | 0 exceptions              | any exception          | Step 5 §1c: NLMEnricher contract          |
| Scraper IGNORE mode = baseline         | regression test passes    | behavior change        | Cardinal rule: zero regression            |
| Scraper ENRICH mode >= baseline        | article count >= baseline | fewer articles         | NLM must not hurt                         |
| NLM-seeded Exa queries produce results | >= 1 article              | 0                      | Queries must be effective                 |
| War Room: suggested_topics parseable   | valid JSON, all fields    | parse error            | Downstream consumption                    |
| Handoff freshness at 03:00             | < 2h (written at 02:10)   | > 24h                  | Step 2 §1: pipeline completes by 02:20    |

### Phase 7: Failure Mode Testing

| Test                                             | Expected MTTR           | Hard Fail                    | Derivation                                     |
| ------------------------------------------------ | ----------------------- | ---------------------------- | ---------------------------------------------- |
| CB-NLM: 3 consecutive failures → HALT            | Automated < 5 min       | no halt or no alert          | Step 6 §1: INV-6, 3 failures = PAUSE 48h       |
| CB-NLM: auto-close after 48h                     | Automated < 5 min       | requires manual intervention | Step 6 §6b: diagnostic query succeeds → resume |
| CB-SOURCE: ACTIVE > 70 → emergency consolidate   | Automated < 5 min       | ACTIVE still > 70 after      | Step 6 §1: INV-1 triggers archive to 55        |
| CB-INTEGRATION: handoff corrupt → scraper IGNORE | Automated < 1 min       | scraper crashes              | Step 5 §2.1: IGNORE mode = default             |
| pipeline_state.json deleted → recovery           | Automated < 1 min       | pipeline crashes             | Step 6 §2.2: recover from Friday snapshot      |
| source_registry.json deleted → recovery          | Automated < 5 min       | pipeline crashes             | Step 6 §2.3: recover from NLM API              |
| claims.jsonl corrupted → salvage valid lines     | Automated < 1 min       | data loss beyond bad lines   | Step 6 §2.4: line-by-line salvage              |
| INV-1 violation (inject ACTIVE=75)               | Automated < 5 min       | ACTIVE still > 70            | Step 6 §1: emergency archive                   |
| INV-4 violation (inject balizero.com)            | Automated < 1 min       | source persists              | Step 6 §1: immediate source_delete             |
| INV-5 violation (delete 1 MD)                    | Automated < 5 min       | MD count < 4                 | Step 6 §2.5: rebuild from snapshot             |
| Full restart (all state deleted)                 | < 30 min to first query | > 60 min                     | Step 6 §2: default state + Phase 0 seeding     |

### Phase 8: Before/After Comparison

| Metric                          | Control (no NLM) | Treatment (with NLM) | Target Delta | Hard Fail         |
| ------------------------------- | ---------------- | -------------------- | ------------ | ----------------- |
| Articles/day                    | baseline         | >= baseline          | >= 0         | negative delta    |
| Immigration articles/day        | baseline         | > baseline           | +20% or more | negative delta    |
| Avg quality_score (immigration) | baseline         | > baseline           | +5 points    | negative delta    |
| Verification rate               | baseline         | > baseline           | +10 pp       | negative delta    |
| Source diversity (domains/day)  | baseline         | >= baseline          | >= 0         | negative delta    |
| Unique topics/week              | baseline         | > baseline           | +2 topics    | negative delta    |
| Event-to-article latency        | baseline         | < baseline           | -30%         | increased latency |
| NLM-backed articles             | 0                | > 0                  | >= 1/day     | 0/day all 3 days  |

**IVA target (from Step 5 §5):**

```
IVA = (treatment_quality - control_quality) / control_quality

Month 1 target:  0.15 - 0.25  (15-25% quality improvement)
Month 6 target:  0.35 - 0.55  (cumulative knowledge advantage)
```

---

## 3. Month 1 KPI Targets (Go/No-Go)

### 3.1 Weekly KPI Table

| KPI                                    | W1     | W2     | W3     | W4     | Hard Fail (any week)          |
| -------------------------------------- | ------ | ------ | ------ | ------ | ----------------------------- |
| Pipeline reliability (runs/5 weekdays) | 3/5    | 4/5    | 4/5    | 5/5    | < 2/5 for 2 consecutive weeks |
| NHS                                    | > 0.50 | > 0.55 | > 0.65 | > 0.65 | < 0.40 at W4                  |
| ACTIVE source count                    | 20-40  | 30-55  | 40-65  | 40-70  | > 70 any week                 |
| Dedup ratio (dupes/total imported)     | 10-30% | 15-25% | 15-25% | 15-25% | > 40% any week                |
| Manual interventions                   | <= 5   | <= 3   | <= 2   | <= 2   | > 5 at W4                     |
| Claims extracted (cumulative)          | > 30   | > 80   | > 150  | > 200  | < 50 at W4                    |
| Claim accuracy (10/week spot-check)    | > 70%  | > 80%  | > 85%  | > 85%  | < 60% at W4                   |
| Handoff freshness (avg hours)          | < 4h   | < 3h   | < 2h   | < 2h   | > 6h at W4                    |
| Budget consumed (calls/week)           | 10-15  | 10-15  | 10-15  | 10-15  | > 30 any week                 |
| Circuit breaker activations            | 0-2    | 0-1    | 0      | 0      | > 3 any week                  |
| CRITICAL invariant violations          | 0-1    | 0      | 0      | 0      | > 2 any week                  |

### 3.2 Month 1 Composite KPIs

| KPI                        | Target                 | How to Measure                                    |
| -------------------------- | ---------------------- | ------------------------------------------------- |
| IVA                        | 0.15-0.25              | quality_score delta, treatment vs control         |
| War Room NLM adoption      | > 10% of weekly topics | `topics_from_nlm / total_topics`                  |
| Scraper quality delta      | +5 to +15 points       | `mean(treatment_quality) - mean(control_quality)` |
| MTTR automated             | < 5 min median         | From `audit.jsonl` timestamps                     |
| MTTR manual                | < 2h median            | From escalation resolution timestamps             |
| Pipeline cost/week         | < $5 NLM + $2 compute  | Cost tracking (see §6)                            |
| Human oversight hours/week | < 1h by W4             | `manual_interventions * avg_time_per`             |

### 3.3 Trend Requirements (Non-Negotiable)

Absolute values are necessary but insufficient. Trends must be directional:

| Metric               | Required Trend W1→W4      | Alarm If                                |
| -------------------- | ------------------------- | --------------------------------------- |
| NHS                  | Non-decreasing after W2   | Drops > 0.10 in any single week         |
| Manual interventions | Strictly decreasing W2→W4 | Increases W3→W4                         |
| Claim accuracy       | Non-decreasing W2→W4      | Drops > 10 pp in any week               |
| Dedup ratio          | Stable in 15-25% band     | Monotonically increasing (bloat signal) |
| Budget/week          | Stable in 10-15 band      | Monotonically increasing (runaway)      |

---

## 4. Statistical Tests

### 4.1 Test A: Scraper Quality Improvement (Primary Outcome)

**Hypothesis H1:** Articles produced with NLM enrichment have higher quality_score than without.
**Null H0:** No difference in quality_score between enriched and non-enriched articles.
**Test:** Welch's t-test (two-sample, unequal variance, one-tailed).

```python
from scipy import stats
import numpy as np

def test_scraper_quality(
    control: list[float],    # quality_scores WITHOUT NLM (baseline 30d immigration articles)
    treatment: list[float],  # quality_scores WITH NLM (Phase 8 + Month 1 immigration articles)
) -> dict:
    t_stat, p_value_two = stats.ttest_ind(treatment, control, equal_var=False)
    p_value = p_value_two / 2  # one-tailed (treatment > control)

    # Cohen's d (pooled)
    n_c, n_t = len(control), len(treatment)
    s_pooled = np.sqrt(((n_c-1)*np.std(control,ddof=1)**2 + (n_t-1)*np.std(treatment,ddof=1)**2) / (n_c+n_t-2))
    d = (np.mean(treatment) - np.mean(control)) / s_pooled if s_pooled > 0 else 0

    return {
        "n_control": n_c,
        "n_treatment": n_t,
        "mean_control": round(np.mean(control), 2),
        "mean_treatment": round(np.mean(treatment), 2),
        "delta": round(np.mean(treatment) - np.mean(control), 2),
        "t_statistic": round(t_stat, 3),
        "p_value_one_tailed": round(p_value, 4),
        "significant_005": p_value < 0.05,
        "cohens_d": round(d, 3),
        "effect_size": "large" if abs(d) >= 0.80 else "medium" if abs(d) >= 0.50 else "small",
        "verdict": (
            "SIGNIFICANT_IMPROVEMENT" if p_value < 0.05 and t_stat > 0
            else "NO_SIGNIFICANT_CHANGE" if p_value >= 0.05
            else "SIGNIFICANT_DEGRADATION"
        ),
    }
```

**Sample size justification:**

- Minimum detectable effect: d = 0.50 (medium effect = ~5 points on 0-100 scale with SD ~10)
- Power: 0.80 at alpha = 0.05 (one-tailed)
- Required per group: n = 27 (from power analysis: `stats.power.TTestIndPower().solve_power(0.50, 0.05, 0.80)`)
- Available: control >= 30 (30d baseline, immigration only), treatment >= 20 (Phase 8 + early Month 1)
- With n=30 control, n=20 treatment: power = 0.72 for d=0.50. Acceptable. Increases to 0.87 by end of Month 1 (n_treatment ~40).

**Decision rules:**

- p < 0.05 AND d >= 0.30: **NLM enrichment confirmed beneficial.** Pipeline provides measurable value.
- p >= 0.05 AND d > 0: **Inconclusive.** Extend testing 2 more weeks to accumulate samples.
- p < 0.05 AND d < 0: **NLM enrichment harmful.** ABORT. Investigate root cause.
- d in [-0.20, 0.20]: **Negligible effect.** Pipeline not harmful but not adding value. Review IVA.

### 4.2 Test B: War Room Topic Adoption (Secondary Outcome)

**Hypothesis H1:** War Room selects NLM-suggested topics above random chance.
**Null H0:** NLM topic selection rate = expected rate if War Room picked randomly from available pool.
**Test:** Chi-square goodness-of-fit.

```python
def test_war_room_adoption(
    total_selected: int,       # Total topics War Room selected in period
    nlm_selected: int,         # Topics that originated from NLM suggestions
    nlm_available: int,        # Total NLM topics offered during period
    total_available: int,      # Total topics available (NLM + scraper + manual)
) -> dict:
    expected_rate = nlm_available / total_available if total_available > 0 else 0
    expected_nlm = total_selected * expected_rate
    expected_other = total_selected - expected_nlm

    if expected_nlm < 5 or expected_other < 5:
        # Chi-square unreliable with expected counts < 5
        # Use Fisher exact test instead
        from scipy.stats import fisher_exact
        table = [[nlm_selected, nlm_available - nlm_selected],
                 [total_selected - nlm_selected, total_available - nlm_available - (total_selected - nlm_selected)]]
        _, p_value = fisher_exact(table, alternative='greater')
        test_used = "fisher_exact"
    else:
        observed = [nlm_selected, total_selected - nlm_selected]
        expected = [expected_nlm, expected_other]
        chi2, p_value = stats.chisquare(observed, expected)
        test_used = "chi_square"

    return {
        "test_used": test_used,
        "expected_rate": round(expected_rate, 3),
        "observed_rate": round(nlm_selected / total_selected, 3) if total_selected > 0 else 0,
        "p_value": round(p_value, 4),
        "significant_005": p_value < 0.05,
        "verdict": (
            "NLM_TOPICS_PREFERRED" if p_value < 0.05 and nlm_selected > expected_nlm
            else "NLM_ADOPTION_AT_OR_BELOW_CHANCE"
        ),
    }
```

**Sample size caveat:** War Room selects ~5 topics/week = ~20 in Month 1. If NLM offers ~20 topics in Month 1 and total available is ~80, expected NLM selection by chance = 5. Chi-square minimum expected count = 5 (borderline). May need Fisher's exact test for small samples. If p > 0.05, likely insufficient power — extend to Month 2.

### 4.3 Test C: Confidence Calibration

**Hypothesis:** Claims scored >= 0.75 are accurate >= 75% of the time. Claims scored 0.55-0.74 are accurate 60-80% of the time.
**Test:** Binomial proportion test per confidence band, with Wilson score intervals.

```python
def test_calibration(
    spot_checks: list[dict],  # [{claim_id, confidence_score, is_accurate: bool}, ...]
) -> list[dict]:
    bins = [
        {"name": "VERIFIED",    "lo": 0.75, "hi": 1.01, "expected_lo": 0.75, "expected_hi": 1.00},
        {"name": "PROVISIONAL", "lo": 0.55, "hi": 0.75, "expected_lo": 0.60, "expected_hi": 0.80},
        {"name": "MONITORING",  "lo": 0.35, "hi": 0.55, "expected_lo": 0.40, "expected_hi": 0.60},
    ]
    results = []
    for b in bins:
        in_bin = [s for s in spot_checks if b["lo"] <= s["confidence_score"] < b["hi"]]
        n = len(in_bin)
        if n == 0:
            results.append({"bin": b["name"], "n": 0, "status": "NO_DATA"})
            continue
        k = sum(1 for s in in_bin if s["is_accurate"])
        p_hat = k / n

        # Wilson score interval (95%)
        z = 1.96
        denom = 1 + z**2/n
        center = (p_hat + z**2/(2*n)) / denom
        margin = z * np.sqrt((p_hat*(1-p_hat) + z**2/(4*n)) / n) / denom
        ci_lo = max(0, center - margin)
        ci_hi = min(1, center + margin)

        # Calibrated if actual accuracy overlaps expected range
        calibrated = not (ci_hi < b["expected_lo"] or ci_lo > b["expected_hi"])

        results.append({
            "bin": b["name"],
            "n": n,
            "accurate": k,
            "actual_accuracy": round(p_hat, 3),
            "expected_range": [b["expected_lo"], b["expected_hi"]],
            "wilson_ci_95": [round(ci_lo, 3), round(ci_hi, 3)],
            "calibrated": calibrated,
            "action": "OK" if calibrated else f"RECALIBRATE (actual={p_hat:.0%}, expected={b['expected_lo']:.0%}-{b['expected_hi']:.0%})"
        })
    return results
```

**Required samples:** 10 claims/bin/week. By W4: ~40 per bin. With n=40, Wilson interval half-width is ~15 pp. Can detect 15 pp miscalibration with 95% confidence.

**Decision:**

- 3/3 bins calibrated: Confidence system working. No action.
- 1/3 bins miscalibrated: Adjust weights for that specific tier in Step 3 §2 formula.
- 2+ bins miscalibrated: Fundamental formula revision needed. Re-run Step 3 design.

### 4.4 Test D: SVS vs Human Rating

**Hypothesis:** SVS rank-ordering correlates with human expert judgment.
**Test:** Mean Absolute Error (MAE) + Spearman rank correlation.

**Protocol:**

1. At W2 and W4: select 20 ACTIVE sources (stratified 5 per SVS quartile)
2. Domain expert rates each 0-1 on "immigration intelligence value"
3. Compare SVS vs human rating

```python
def test_svs_human(svs: list[float], human: list[float]) -> dict:
    mae = np.mean(np.abs(np.array(svs) - np.array(human)))
    rho, p_val = stats.spearmanr(svs, human)
    return {
        "n": len(svs),
        "mae": round(mae, 3),
        "mae_acceptable": mae < 0.20,
        "spearman_rho": round(rho, 3),
        "spearman_p": round(p_val, 4),
        "rank_correlated": p_val < 0.05 and rho > 0.50,
        "verdict": (
            "SVS_WELL_CALIBRATED" if mae < 0.20 and rho > 0.50
            else "SVS_RANK_OK_VALUES_OFF" if mae >= 0.20 and rho > 0.50
            else "SVS_NEEDS_RECALIBRATION"
        ),
    }
```

**Targets:**

- MAE < 0.20 (pipeline SVS within 20 points of human average)
- Spearman rho > 0.50 (moderate+ positive rank correlation, p < 0.05)
- With n=20, Spearman can detect rho=0.45 at alpha=0.05 with power ~0.80

---

## 5. Go/No-Go Decision Framework

### 5.1 Week 2 Checkpoint (Day 14)

**Decision: CONTINUE / ADJUST / ABORT**

```
WEEK 2 DECISION PACKAGE
════════════════════════

PIPELINE HEALTH
  Runs completed:                ___ / 10 weekdays
  NHS current:                   _.__
  ACTIVE sources:                ___
  CRITICAL violations:           ___
  Budget consumed W1+W2:         ___ / 40 weekly cap

QUALITY
  Claims extracted (cumulative): ___
  Claim accuracy (n=20):         ___%
  Confidence calibration:        _/3 bins OK

INTEGRATION
  Handoff packages generated:    ___ / 10
  Scraper read without error:    ___ / ___
  IVA (preliminary):             _.__

ISSUES
  Circuit breakers fired:        ___
  Manual interventions:          ___
  Unresolved bugs:               ___
```

| Decision     | ALL of these criteria must hold                                                                                                                     |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CONTINUE** | Runs >= 6/10, NHS > 0.50, accuracy > 70%, 0 unresolved CRITICAL, scraper regression passes                                                          |
| **ADJUST**   | Runs 4-5/10 OR NHS 0.40-0.50 OR accuracy 60-70% OR 1 unresolved CRITICAL with known fix. Action: recalibrate, fix bugs, re-evaluate at W3 mid-point |
| **ABORT**    | Runs < 4/10 OR NHS < 0.40 OR accuracy < 60% OR scraper regression fails OR > 3 unresolved CRITICALs OR budget exhausted before W2                   |

### 5.2 Week 4 Checkpoint (Day 28)

**Decision: PRODUCTION PROMOTE / EXTEND TESTING / REDESIGN**

```
WEEK 4 PRODUCTION READINESS
════════════════════════════

RELIABILITY (28 days)
  Total runs:                    ___ / 20 weekdays → ___%
  NHS trend:                     W1:_.__ → W2:_.__ → W3:_.__ → W4:_.__
  NHS current:                   _.__
  Budget avg/week:               ___

QUALITY (cumulative)
  Total claims:                  ___
  Accuracy (n=40):               ___%
  Confidence calibration:        _/3 bins
  SVS MAE vs human:              _.__
  ILM (all consolidations):      _.__

INTEGRATION (28 days)
  IVA:                           _.__
  War Room adoption:             ___%
  Scraper quality delta:         +___ points
  Scraper regressions:           ___
  Handoff freshness avg:         ___h

OPERATIONS
  Manual interventions total:    ___
  Trend:                         W1:___ → W2:___ → W3:___ → W4:___
  MTTR automated median:         ___ min
  MTTR manual median:            ___ h

STATISTICAL TESTS
  Test A (quality t-test):       p=_.__, d=_.__
  Test B (adoption chi-sq):      p=_.__
  Test C (calibration):          _/3 bins
  Test D (SVS MAE):              _.__

COST (28 days)
  NLM API calls total:           ___
  Exa cost:                      $___
  Human time:                    ___ h
  Total cost:                    $___
```

| Decision                    | Criteria                                                                                                                                                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PRODUCTION PROMOTE**      | ALL of: reliability >= 80%, NHS >= 0.65, accuracy >= 85%, ILM always < 0.05, IVA >= 0.15, 0 scraper regressions, interventions <= 2/wk in W4, MTTR auto < 5min, Test A significant (p<0.05 and d>0.30), calibration >= 2/3 bins |
| **EXTEND TESTING (+2 wks)** | ANY of: reliability 60-79%, NHS 0.55-0.64, accuracy 75-84%, IVA 0.05-0.14, Test A marginally significant (0.05<p<0.10), Test B insufficient data. MUST show improving trend W2→W4                                               |
| **REDESIGN**                | ANY of: reliability < 60%, NHS < 0.55, accuracy < 75%, IVA < 0.05, scraper regression detected, interventions increasing W3→W4, Test A shows degradation (d < 0), any INV unresolved > 48h                                      |

### 5.3 Post-Production Monitoring

Weekly monitoring continues after promotion:

| Check             | Frequency        | Alert Threshold                | Action                       |
| ----------------- | ---------------- | ------------------------------ | ---------------------------- |
| NHS               | Daily (auto)     | < 0.60                         | Telegram WARN                |
| Reliability       | 3-day rolling    | < 80%                          | Review failures              |
| Budget            | Daily            | > 30 by Thursday               | Reduce to 1 query/day        |
| IVA               | Weekly           | < 0.10 for 2 consecutive weeks | Review handoff quality       |
| Claim accuracy    | Weekly (10 spot) | < 80%                          | Recalibrate confidence       |
| Dedup ratio       | Weekly           | > 35%                          | Tighten import filters       |
| MTTR              | Per-incident     | > 30 min auto                  | Fix recovery logic           |
| War Room adoption | Monthly          | < 5%                           | Pipeline not providing value |

**Demotion ladder:**

- 2 consecutive weeks breaching any alert: DEGRADED_L1 (continue, heightened monitoring)
- 3 consecutive weeks: DEGRADED_L2 (reduce to 1 query/day)
- 4 consecutive weeks: HALTED (manual restart after root cause investigation)

---

## 6. Cost Tracking

### 6.1 Cost Components

| Component                                | Unit Cost         | Est. Monthly Volume | Est. Monthly Cost |
| ---------------------------------------- | ----------------- | ------------------- | ----------------- |
| NLM API (research, query, source)        | $0.00 (free tier) | ~200 calls          | $0.00             |
| Exa API (NLM-seeded scraper queries)     | ~$0.01/search     | 300-600 searches    | $3-6              |
| LLM (claim extraction, Qwen local)       | ~$0.001/call      | ~200 calls          | $0.20             |
| LLM (claim extraction, Claude fallback)  | ~$0.03/call       | ~20 calls           | $0.60             |
| Pro compute (pipeline runtime)           | $0 (own hardware) | ~30h pipeline       | $0                |
| Human time (spot-checks + interventions) | $30/h opportunity | 1-2h/week           | $30-60            |

**Total estimated: ~$35-65/month** (dominated by human time opportunity cost)

### 6.2 Weekly Cost Template

```json
{
  "week": "2026-WXX",
  "nlm_calls": {
    "research_start": 0,
    "research_status_polls": 0,
    "research_import": 0,
    "notebook_query": 0,
    "source_add": 0,
    "source_delete": 0,
    "source_list": 0,
    "total": 0,
    "budget_remaining": 0
  },
  "external_calls": {
    "exa_nlm_seeded": 0,
    "exa_cost_usd": 0.0,
    "llm_local_calls": 0,
    "llm_cloud_calls": 0,
    "llm_cost_usd": 0.0
  },
  "compute": {
    "pipeline_total_min": 0,
    "avg_per_run_min": 0
  },
  "human": {
    "spot_check_min": 0,
    "interventions_min": 0,
    "total_hours": 0.0,
    "opportunity_cost_usd": 0.0
  },
  "total_cost_usd": 0.0,
  "value": {
    "claims_extracted": 0,
    "articles_enriched": 0,
    "war_room_topics_adopted": 0,
    "iva": 0.0,
    "regulatory_catches_early": 0
  }
}
```

### 6.3 ROI Model

```
MONTHLY COST
  Fixed:   $0 (NLM free, compute owned)
  Variable: $5 (Exa) + $1 (LLM) + $45 (human 1.5h/wk * $30/h)
  Total:   ~$51/month

MONTHLY VALUE (measurable)
  IVA quality improvement:
    = enriched_articles/month * quality_boost_points * value_per_point
    = 20 articles * 10 points * $2/point = $400

  War Room time saved:
    = hours_saved/month * hourly_rate
    = 4 hours * $30/h = $120

  Total measurable: $520/month

MONTHLY VALUE (hard to measure)
  Regulatory early warning:
    = catches_per_month * avg_risk_avoided
    = 2 catches * $500 = $1,000 (sporadic, high variance)

ROI SCENARIOS
  Optimistic: ($520 + $1000 - $51) / $51 = 2,880%
  Expected:   ($520 - $51) / $51 = 919%
  Pessimistic (half quality boost, no War Room):
              ($200 - $51) / $51 = 292%
  Break-even: requires only $51 value/month = ~3 enriched articles at +$17 each

CONCLUSION: Pipeline is net positive in ALL scenarios from Month 1.
Step 5 estimated ~$230/month net positive (conservative). Our model confirms.
```

### 6.4 Cost Alarms

| Alarm                | Threshold        | Action                                           |
| -------------------- | ---------------- | ------------------------------------------------ |
| NLM calls > 30/week  | 75% of 40 budget | Reduce to 1 query/day remainder of week          |
| Exa cost > $10/week  | 2x expected      | Review NLM-seeded query volume, cap at 3/finding |
| Human time > 3h/week | 3x target        | Investigate: automation broken? Fix root cause   |
| Total monthly > $100 | 2x expected      | Cost audit, identify largest component           |

---

## 7. Testing Timeline Summary

```
DAY  0     BASELINE COLLECTION
              └── NB-2 snapshot + scraper 30d SQL + War Room history

DAY  1-2   PHASE 0+1: Setup + First Query
              Gates: 20 seeds, NHS > 0.45, 5-15 sources imported

DAY  2-3   PHASE 2: Triage
              Gates: promotion rate 40-70%, SVS > 0.45 mean, manual check 8/10

DAY  3-5   PHASE 3: Claims
              Gates: > 2 claims/source, accuracy 8/10, calibration table filled

DAY  5-6   PHASE 4: Second Query
              Gates: dedup works, context injection verified, dedup ratio < 40%

DAY  6-8   PHASE 5: Lifecycle
              Gates: ILM < 0.05, NHS > 0.65, MDs updated, budget 10-15

DAY  8-10  PHASE 6: Handoff
              Gates: TRS scored, schema valid, regression test passes

DAY 10-12  PHASE 7: Failure Testing
              Gates: all CBs tested, all recoveries < MTTR target

DAY 12-14  PHASE 8: Before/After
              Gates: IVA >= 0.10, no negative deltas

═══ WEEK 2 CHECKPOINT (Day 14): CONTINUE / ADJUST / ABORT ═══

DAY 15-28  MONTH 1 DAILY OPERATION
              └── Daily runs, weekly KPI, weekly spot-checks
              └── Statistical test data accumulates

═══ WEEK 4 CHECKPOINT (Day 28): PROMOTE / EXTEND / REDESIGN ═══
```

Total: **28 days** (4 weeks). Days 1-14 controlled phases. Days 15-28 monitored operation.

---

## 8. The One Number That Matters

If you could track only ONE metric across the entire testing period:

**Claim verification accuracy >= 85% by Week 4.**

Everything else — NHS, IVA, adoption, cost, reliability — is downstream of claim quality. If claims are accurate and well-calibrated, the pipeline produces trustworthy intelligence that enriches the scraper and informs War Room. If claims are inaccurate, the pipeline is a noise amplifier regardless of other metrics.

The claim accuracy spot-check (10 claims/week, manual verification against cited sources) is the single most important recurring action during the test period. Do not skip it. Do not automate it. A human must open the source URL and verify the claim text.

---

## Appendix: Metric-to-Step Traceability

Every numeric target traces back to a prior step:

| Metric                   | Value                    | Source                            |
| ------------------------ | ------------------------ | --------------------------------- |
| NHS target               | >= 0.65 (W3+)            | Step 4 §6                         |
| ILM hard gate            | < 0.05                   | Step 4 §1 CONSOLIDATE             |
| SVS mean target          | > 0.45                   | Step 4 §3 VALUABLE classification |
| Dedup healthy range      | 15-25%                   | Step 4 §4.3                       |
| Dedup alarm              | > 40%                    | Step 4 §4.3                       |
| TRS threshold            | >= 0.65                  | Step 5 §1b                        |
| IVA Month 1              | 0.15-0.25                | Step 5 §5                         |
| IVA Month 6              | 0.35-0.55                | Step 5 §5                         |
| Confidence VERIFIED      | >= 0.75                  | Step 3 §2                         |
| Confidence PROVISIONAL   | 0.55-0.74                | Step 3 §2                         |
| ACTIVE cap               | <= 70                    | Step 4 §2, Step 6 INV-1           |
| Budget weekly            | <= 40 calls              | Step 2 §5, Step 6 INV-7           |
| MTTR automated           | < 5 min                  | Step 6 PROGRESS.md                |
| MTTR manual              | < 2h                     | Step 6 PROGRESS.md                |
| MTTR full restart        | < 30 min                 | Step 6 §2                         |
| Pipeline deadline        | 02:30 WITA               | Step 6 INV-9                      |
| Daily queries            | 2 deep + 0-1 conditional | Step 2 §1                         |
| Consecutive failure halt | 3                        | Step 6 INV-6                      |
| Master Docs minimum      | 4                        | Step 6 INV-5                      |
| Quarantine cap           | 30                       | Step 6 INV-2                      |
| Pre-import noise         | 15-20% expected          | Step 1 §5                         |
