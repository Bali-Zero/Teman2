# Step 5b: Intel Scraper Integration — DeepSeek R1 Perspective (Formulas + KPIs)

> Agent: DeepSeek R1 perspective (quantification, formulas, expected ranges, success metrics)
> Date: 2026-03-28
> Complements: `05_scraper_integration.md` (Gemini — architecture, integration flows, code sketches)
> Depends on: Steps 1-4 (query design, sequencing, quality verification, source management)
> Status: Brainstorm complete

---

## 1. Topic Relevance Score (TRS) — Handoff Filter

### 1.1 Formula

```
TRS = W_conf * F_confidence
    + W_nov  * F_novelty
    + W_imp  * F_client_impact
    + W_ed   * F_editorial_value
    + W_tier * F_source_tier
    + BONUS_timely
```

### 1.2 Weights

| Factor                        | Weight | Rationale                                                           |
| ----------------------------- | ------ | ------------------------------------------------------------------- |
| **Confidence (F_confidence)** | 0.25   | Higher-confidence findings are safer for article production         |
| **Novelty (F_novelty)**       | 0.25   | Findings already covered by scraper have low marginal value         |
| **Client Impact (F_impact)**  | 0.20   | Findings affecting more client segments justify editorial attention |
| **Editorial Value (F_ed)**    | 0.15   | Some findings are technically correct but editorially dead          |
| **Source Tier (F_tier)**      | 0.15   | Higher-tier sourcing lends credibility to published articles        |

### 1.3 Sub-Score Definitions

**F_confidence** — direct pass-through from Step 3 confidence formula:

```
F_confidence = claim.confidence_score  (already 0.00-1.00)
```

A VERIFIED claim (>=0.75) scores higher than PROVISIONAL (0.55-0.74). Claims below 0.55
are filtered by the confidence gate before TRS is computed.

**F_novelty** — inverse overlap with scraper archive (last 30 days):

```
F_novelty = 1.0 - max_overlap_with_scraper_archive
```

Where `max_overlap_with_scraper_archive` is the highest Szymkiewicz-Simpson overlap
(from Step 4 dedup) between this claim and any article published by the scraper in
the trailing 30-day window.

Computation priority order:

1. Exact `regulation_ref` match in any scraper article -> overlap = 0.80 minimum
2. Same `subject_entity` + same `category` -> overlap estimated at 0.60
3. Embedding cosine similarity(`claim_text`, `article.title + article.executive_brief`) > 0.85 -> overlap = 0.90
4. No match found -> overlap = 0.00

| max_overlap | F_novelty | Interpretation                                    |
| ----------- | --------- | ------------------------------------------------- |
| 0.00        | 1.00      | Completely new intelligence                       |
| 0.30        | 0.70      | Tangential coverage exists                        |
| 0.60        | 0.40      | Same regulation covered, different angle possible |
| 0.80        | 0.20      | Substantially covered already                     |
| 0.90+       | 0.10      | Already published (min floor for re-angle value)  |

**F_client_impact** — affected segment count, normalized:

```
F_impact = min(1.0, affected_segments / 4)
```

Segment counting: each unique `(visa_type, service)` pair from the claim metadata = 1 segment.
Cross-domain claims (immigration affecting tax or company setup) receive +1 bonus segment.

| affected_visa_types | affected_services   | Segments | F_impact |
| ------------------- | ------------------- | -------- | -------- |
| 1                   | 1                   | 1        | 0.25     |
| 2                   | 1                   | 2        | 0.50     |
| 2                   | 2                   | 3+       | 0.75     |
| 3+                  | 2+ (+ cross-domain) | 4+       | 1.00     |

**F_editorial_value** — binary composite (each component 0 or 1):

```
F_editorial = 0.25 * has_deadline
            + 0.25 * has_second_order_consequence
            + 0.25 * affects_active_clients
            + 0.25 * has_actionable_recommendation
```

| Component                       | Detection Logic                                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------- |
| `has_deadline`                  | `claim.effective_date` is non-null AND within 90 days of today                               |
| `has_second_order_consequence`  | Claim category is L4 (cross-domain) OR `action_recommendation` references a different domain |
| `affects_active_clients`        | `claim.affected_visa_types` intersects CRM active client visa types (query via MCP at 02:10) |
| `has_actionable_recommendation` | `claim.action_recommendation` is non-empty AND length > 30 chars AND not generic "monitor"   |

**F_source_tier** — from Step 3 authority hierarchy, take highest in source chain:

```
F_tier = max(source.authority_score for source in claim.source_chain)
```

Values: T0=1.00, T1=0.90, T2=0.80, T3=0.70, T4=0.60, T5=0.45, T6=0.20.

**BONUS_timely** — additive, capped at +0.10:

| Condition                                         | Bonus |
| ------------------------------------------------- | ----- |
| `claim.urgency` in `{"IMMEDIATE", "THIS_WEEK"}`   | +0.10 |
| `claim.category == "ENFORCEMENT_ACTION"` AND Bali | +0.05 |
| `claim.enforcement_divergence == true`            | +0.05 |
| Breaking news override active for this cluster    | +0.05 |

Sum of applicable bonuses, then `BONUS_timely = min(0.10, sum)`.

### 1.4 TRS Thresholds and Selection

| TRS Range   | Classification   | Action                                                         |
| ----------- | ---------------- | -------------------------------------------------------------- |
| >= 0.65     | **HANDOFF**      | Include in `scraper_input.json`                                |
| 0.45 - 0.64 | **CANDIDATE**    | Include only if fewer than 3 topics already qualify at HANDOFF |
| 0.30 - 0.44 | **ARCHIVE_ONLY** | Log in brief for internal reference. Not in scraper handoff    |
| < 0.30      | **NOISE**        | Filtered out completely                                        |

**Selection rules:**

1. Maximum **5 topics** per handoff package (scraper has 10 req/min rate limit, must leave capacity for its own work)
2. Sort by TRS descending, take top 5 at HANDOFF threshold
3. If fewer than 3 at HANDOFF: promote top CANDIDATE(s) to fill up to 3
4. If zero at HANDOFF: promote single best CANDIDATE (if TRS >= 0.45)
5. No more than 3 topics from the same visa cluster per handoff (diversity guard)

### 1.5 Worked Examples

**Example 1: TRS = 0.87 -> HANDOFF**

```
Claim: "Permenkumham 3/2026 reduces B211A max stay from 180 to 120 days"
  F_confidence = 0.91 (VERIFIED, T0 gazette source)
  F_novelty    = 0.90 (no scraper article on this regulation yet)
  F_impact     = 0.75 (B211A business + social + medical = 3 segments)
  F_editorial  = 1.00 (deadline 30d, affects active clients, actionable, cross-domain tax implications)
  F_tier       = 1.00 (T0)
  BONUS        = +0.10 (urgency IMMEDIATE)

TRS = 0.25*0.91 + 0.25*0.90 + 0.20*0.75 + 0.15*1.00 + 0.15*1.00 + 0.10
    = 0.228 + 0.225 + 0.150 + 0.150 + 0.150 + 0.100
    = 1.003 -> capped at 1.00

Classification: HANDOFF (rank #1)
```

**Example 2: TRS = 0.54 -> CANDIDATE**

```
Claim: "Third KITAS delay report this week at Ngurah Rai"
  F_confidence = 0.57 (PROVISIONAL)
  F_novelty    = 0.60 (one related scraper article exists, different angle)
  F_impact     = 0.50 (KITAS kerja + investor = 2 segments)
  F_editorial  = 0.50 (affects active clients + actionable, but no hard deadline, no cross-domain)
  F_tier       = 0.45 (T5 press only)
  BONUS        = +0.05 (enforcement Bali scope)

TRS = 0.25*0.57 + 0.25*0.60 + 0.20*0.50 + 0.15*0.50 + 0.15*0.45 + 0.05
    = 0.143 + 0.150 + 0.100 + 0.075 + 0.068 + 0.050
    = 0.586 -> rounds to 0.59

Classification: CANDIDATE (include if <3 topics at HANDOFF)
```

**Example 3: TRS = 0.28 -> NOISE**

```
Claim: "General report on ASEAN labor mobility discussions"
  F_confidence = 0.61 (PROVISIONAL)
  F_novelty    = 0.20 (covered by multiple scraper articles in last 2 weeks)
  F_impact     = 0.25 (1 vague segment)
  F_editorial  = 0.00 (no deadline, no actionable rec, no active client intersection)
  F_tier       = 0.45 (T5 press)
  BONUS        = 0.00

TRS = 0.25*0.61 + 0.25*0.20 + 0.20*0.25 + 0.15*0.00 + 0.15*0.45 + 0.00
    = 0.153 + 0.050 + 0.050 + 0.000 + 0.068 + 0.000
    = 0.321

Classification: NOISE (filtered out from handoff AND brief)
```

### 1.6 Expected TRS Distribution

Based on 2 queries/day producing 3-5 claims:

| TRS Range                | Expected % of claims | Claims/day | Claims/week |
| ------------------------ | -------------------- | ---------- | ----------- |
| HANDOFF (>=0.65)         | 20-35%               | 0.6-1.8    | 3-9         |
| CANDIDATE (0.45-0.64)    | 25-35%               | 0.8-1.8    | 4-9         |
| ARCHIVE_ONLY (0.30-0.44) | 15-25%               | 0.5-1.3    | 2-6         |
| NOISE (<0.30)            | 15-25%               | 0.5-1.3    | 2-6         |

If the HANDOFF rate drops below 15% for 2 consecutive weeks: NLM queries are too analytical/predictive (not enough practical intelligence). Shift query mix toward more L1 monitoring.

If the HANDOFF rate exceeds 50%: threshold may be too permissive. Raise to 0.70.

---

## 2. Cross-Validation Metrics

### 2.1 Set Definitions

Three mutually exclusive sets, measured weekly:

```
Let T_NLM    = {topics/claims found by NLM in week W}
Let T_SCRAPER = {topics/articles published by scraper in week W}

OVERLAP      = T_NLM ∩ T_SCRAPER      (both systems found it)
NLM_EXCL     = T_NLM \ T_SCRAPER       (only NLM — deep intelligence advantage)
SCRAPER_EXCL = T_SCRAPER \ T_NLM       (only scraper — speed/breadth advantage)
```

Where `|OVERLAP| + |NLM_EXCL| + |SCRAPER_EXCL| = |T_NLM ∪ T_SCRAPER|`

### 2.2 Topic Matching Criteria (ordered by precision)

1. **Regulation match (deterministic):** `claim.regulation_ref` appears verbatim in `article.content` or `article.regulation_refs`. Precision: ~95%.
2. **Entity+category match:** `claim.subject_entity` == `article.primary_entity` AND `claim.category` matches `article.category`. Precision: ~80%.
3. **Embedding similarity:** cosine(`claim.claim_text` embedding, `article.title + article.executive_brief` embedding) > 0.82. Precision: ~70%.

Apply in order. Stop at first match. Only independent articles count (not NLM-seeded; see feedback loop rules in Gemini doc section 3.6).

### 2.3 Expected Ratios for Healthy Integration

| Metric             | Month 1 | Month 3 | Month 6 (Steady) | Alarm Low | Alarm High |
| ------------------ | ------- | ------- | ---------------- | --------- | ---------- |
| **OVERLAP %**      | 15-25%  | 20-35%  | 25-40%           | < 10%     | > 50%      |
| **NLM_EXCL %**     | 35-55%  | 30-50%  | 25-40%           | < 15%     | > 60%      |
| **SCRAPER_EXCL %** | 25-45%  | 25-40%  | 25-40%           | < 15%     | —          |

### 2.4 Diagnostic Matrix

| Observed Pattern   | Diagnosis                                                             | Corrective Action                                              |
| ------------------ | --------------------------------------------------------------------- | -------------------------------------------------------------- |
| OVERLAP > 50%      | Systems are redundant; NLM not adding unique intelligence             | Shift NLM queries toward L2/L3/L4 (analytical, not monitoring) |
| OVERLAP < 10%      | Systems are disconnected; NLM and scraper looking at different things | Add more L1 monitoring queries to NLM; check query alignment   |
| NLM_EXCL < 15%     | NLM is not adding value beyond scraper coverage                       | Shift NLM toward predictive/cross-domain queries               |
| NLM_EXCL > 60%     | NLM is in a different universe from editorial needs                   | NLM queries too niche; add practical monitoring queries        |
| SCRAPER_EXCL < 15% | Scraper underperforming (not NLM's problem)                           | Check scraper source diversity; review RSS feeds               |

### 2.5 Integration Value Added (IVA)

**Definition:**

```
IVA = (U_combined - U_best_single) / U_best_single
```

Where:

- `U_combined` = `|T_NLM ∪ T_SCRAPER|` = total unique topics found by both systems together
- `U_best_single` = `max(|T_NLM|, |T_SCRAPER|)` = best single-system output

**Algebraic expansion:**

```
IVA = (|OVERLAP| + |NLM_EXCL| + |SCRAPER_EXCL| - max(|T_NLM|, |T_SCRAPER|)) / max(|T_NLM|, |T_SCRAPER|)
```

Since `|T_NLM| = |OVERLAP| + |NLM_EXCL|` and `|T_SCRAPER| = |OVERLAP| + |SCRAPER_EXCL|`:

```
IF |T_SCRAPER| >= |T_NLM|:
    IVA = |NLM_EXCL| / |T_SCRAPER|

IF |T_NLM| >= |T_SCRAPER|:
    IVA = |SCRAPER_EXCL| / |T_NLM|
```

In other words: IVA = how many exclusive topics the **smaller** system contributes, relative to the **larger** system's total. This measures the marginal value of integration.

**Expected IVA trajectory:**

| Period  | IVA Target | Rationale                                                   |
| ------- | ---------- | ----------------------------------------------------------- |
| Month 1 | 0.15-0.25  | NLM still calibrating, many L1 queries overlap with scraper |
| Month 3 | 0.30-0.45  | NLM queries refined toward L2/L3, finding unique angles     |
| Month 6 | 0.35-0.55  | Steady state, both systems maximally complementary          |

**IVA alarm:** if IVA < 0.10 for 3 consecutive weeks, one system is redundant. Investigate which one and either retune it or reduce its query budget.

### 2.6 Worked Example — Week Cross-Validation

```
Week 2026-W14:
  NLM claims total:     8  (from 10 queries, 5 weekdays)
  Scraper articles:    14  (from daily scraping runs)

  Matching results:
    OVERLAP:      3  (Permenkumham 3/2026, KITAS delay pattern, VOA fee change)
    NLM_EXCL:     5  (RPTKA digitalization signal, KITAP conversion trend, ...)
    SCRAPER_EXCL: 11  (Golden Visa update, Coretax news, general biz articles, ...)

  Percentages (of union = 19):
    OVERLAP:      3/19 = 15.8%  ✅ (target 15-25%)
    NLM_EXCL:     5/19 = 26.3%  ⚠️ (target 35-55%, slightly low)
    SCRAPER_EXCL: 11/19 = 57.9% (expected: scraper has broader scope)

  IVA = NLM_EXCL / T_SCRAPER = 5/14 = 0.357  ✅ (target 0.15-0.25 for month 1)

  Diagnosis: NLM exclusive slightly below target — consider adding one more L1
  monitoring query per week to catch more practical topics.
```

---

## 3. Confidence Adjustment from Cross-Validation

### 3.1 Boost Formula (Scraper Confirms NLM Claim)

```
C_adjusted = C_nlm + B(n_eff) * (1 - C_nlm)
```

Where:

- `C_nlm` = original NLM confidence score
- `B(n_eff)` = boost factor from effective confirmation count
- `(1 - C_nlm)` = remaining headroom (ensures C never exceeds 1.0, diminishing returns at high C)

**Effective confirmation count** (source-quality-weighted):

```
n_eff = sum(w_i for article_i in confirming_articles)
```

| Scraper article source quality            | w_i  |
| ----------------------------------------- | ---- |
| Cites .go.id / official gazette document  | 1.00 |
| Named-source journalism (quotes official) | 0.70 |
| Unnamed/multiple-source journalism        | 0.40 |
| Blog/forum post                           | 0.20 |

**Boost function** — logarithmic with saturation:

```
B(n) = K * ln(1 + n) / ln(1 + N_max)
```

Parameters:

- `K` = 0.30 (maximum boost = 30% of remaining headroom)
- `N_max` = 5 (saturation: beyond 5 effective confirmations, no additional boost)

**Explicit values:**

| n_eff | B(n_eff) | Example: C_nlm=0.63 -> C_adj | Example: C_nlm=0.72 -> C_adj | Example: C_nlm=0.85 -> C_adj |
| ----- | -------- | ---------------------------- | ---------------------------- | ---------------------------- |
| 0.0   | 0.000    | 0.630                        | 0.720                        | 0.850                        |
| 0.5   | 0.067    | 0.655                        | 0.739                        | 0.860                        |
| 1.0   | 0.116    | 0.673                        | 0.752                        | 0.867                        |
| 1.4   | 0.143    | 0.683                        | 0.760                        | 0.871                        |
| 2.0   | 0.184    | 0.698                        | 0.772                        | 0.878                        |
| 3.0   | 0.231    | 0.715                        | 0.785                        | 0.885                        |
| 4.0   | 0.268    | 0.729                        | 0.795                        | 0.890                        |
| 5.0+  | 0.300    | 0.741                        | 0.804                        | 0.895                        |

**Key properties:**

- A PROVISIONAL claim at 0.63 needs `n_eff >= 3.0` (~4 journalism articles or 3 official articles) to cross the VERIFIED threshold at 0.75
- A VERIFIED claim at 0.85 gains at most +0.045 from full saturation (5+ articles) — already-high-confidence claims barely move
- The `(1 - C_nlm)` factor provides natural diminishing returns: high-confidence claims resist further boosting

### 3.2 Penalty Formula (Scraper Contradicts NLM Claim)

```
C_adjusted = C_nlm - P(m) * C_nlm
```

Where:

- `P(m)` = penalty factor from `m` contradicting articles
- Penalty is proportional to current confidence (high-confidence claims take bigger absolute hits, appropriate because they have more to lose)

```
P(m) = min(0.40, 0.15 * m)
```

| Contradictions (m) | P(m)  | C_nlm=0.63 -> C_adj | C_nlm=0.72 -> C_adj | C_nlm=0.85 -> C_adj |
| ------------------ | ----- | ------------------- | ------------------- | ------------------- |
| 0                  | 0.000 | 0.630               | 0.720               | 0.850               |
| 1                  | 0.150 | 0.536               | 0.612               | 0.723               |
| 2                  | 0.300 | 0.441               | 0.504               | 0.595               |
| 3+                 | 0.400 | 0.378               | 0.432               | 0.510               |

**Key properties:**

- 1 contradiction drops a PROVISIONAL claim (0.63) below PROVISIONAL threshold (0.55) -> MONITORING
- 2 contradictions push a PROVISIONAL claim (0.72) into MONITORING territory (0.504)
- 3+ contradictions push even a VERIFIED claim (0.85) below PROVISIONAL (0.510) -> triggers mandatory human review

### 3.3 Contradiction Detection

An article "contradicts" an NLM claim when:

1. Same `regulation_ref` or `subject_entity`, AND
2. Opposite `assertion_direction` (NLM: "max stay reduced" vs article: "max stay unchanged"), OR
3. Article explicitly disputes: keywords `belum berlaku`, `hoax`, `klarifikasi`, `belum resmi`, `tidak benar`, `not confirmed`, `denied`

**Safeguard:** Contradictions are flagged as `confidence_adjustment: PENDING_CONTRADICTION`. They are NOT auto-applied. The next NLM pipeline run (next morning at 01:05) reads the cross-validation file and verifies before applying the penalty. This prevents a single clickbait article from torpedoing a verified claim.

### 3.4 Combined Case (Confirmations AND Contradictions)

```
IF m_contradictions > 0 AND n_confirmations > 0:
    status = "DISPUTED"
    C_adjusted = C_nlm  # HOLD at original value
    flag = "requires_human_review"
    escalation = true
```

Conflicting evidence means the topic is **contested**, not that the truth is somewhere in the middle. Never average confirmations and contradictions. Escalate to human.

### 3.5 Threshold Transition Table

| Original Class | After Boost (C rises)        | After Penalty (C drops)    |
| -------------- | ---------------------------- | -------------------------- |
| MONITORING     | -> PROVISIONAL if C >= 0.55  | -> UNVERIFIED if C < 0.35  |
| PROVISIONAL    | -> VERIFIED if C >= 0.75     | -> MONITORING if C < 0.55  |
| VERIFIED       | stays VERIFIED (cap at 0.95) | -> PROVISIONAL if C < 0.75 |

### 3.6 Monthly Confidence Flow Analysis

Expected monthly statistics (steady state, month 6):

| Metric                                        | Expected Value                               |
| --------------------------------------------- | -------------------------------------------- |
| Total NLM claims produced/month               | 60-100                                       |
| Claims at PROVISIONAL+                        | 45-80 (75%)                                  |
| Claims entering cross-validation with scraper | 15-30 (in overlap)                           |
| Boosted (confirmed by scraper)                | 10-20 (67%)                                  |
| Penalized (contradicted by scraper)           | 1-3 (5-10%)                                  |
| DISPUTED (both confirm+contradict)            | 0-2 (rare)                                   |
| PROVISIONAL -> VERIFIED via boost             | 4-8/month (15-30% of PROVISIONAL in overlap) |
| VERIFIED -> PROVISIONAL via penalty           | 0-1/month (< 3% of VERIFIED)                 |

---

## 4. War Room Topic Selection Model

### 4.1 Editorial Value Score (EVS)

```
EVS = 0.25 * S_confidence_norm
    + 0.20 * S_novelty
    + 0.20 * S_audience_reach
    + 0.20 * S_timeliness
    + 0.15 * S_narrative_potential
```

**S_confidence_norm** — rescale PROVISIONAL+ range to 0-1:

```
S_confidence_norm = max(0, (claim.confidence - 0.55) / (1.0 - 0.55))
```

| confidence | S_confidence_norm |
| ---------- | ----------------- |
| 0.55       | 0.000             |
| 0.65       | 0.222             |
| 0.75       | 0.444             |
| 0.85       | 0.667             |
| 0.95       | 0.889             |
| 1.00       | 1.000             |

Claims below 0.55 should never reach War Room (filtered by TRS).

**S_novelty** — inverse similarity to published Bali Zero articles (last 90 days):

```
S_novelty = 1.0 - max_similarity_to_published_articles
```

Uses same overlap method as TRS F_novelty, but checks against ALL published editorial articles (not just scraper output). This prevents the War Room from covering the same topic twice.

**S_audience_reach** — size of affected readership:

| Affected Group                                           | Score |
| -------------------------------------------------------- | ----- |
| All foreign investors + expats (major regulatory change) | 1.00  |
| Specific visa-type holders (KITAS, B211A, KITAP)         | 0.70  |
| Specific industry (tech, F&B, hospitality)               | 0.50  |
| Compliance-only (sponsor obligations, reporting)         | 0.35  |
| Niche (single nationality, single immigration office)    | 0.20  |

**S_timeliness** — deadline urgency:

| Condition                          | Score |
| ---------------------------------- | ----- |
| `effective_date` within 14 days    | 1.00  |
| `effective_date` within 30 days    | 0.80  |
| `effective_date` within 90 days    | 0.50  |
| Already in effect (catch-up value) | 0.70  |
| No `effective_date` or > 90 days   | 0.20  |

**S_narrative_potential** — story-worthiness (take highest applicable):

| Signal                                                    | Score |
| --------------------------------------------------------- | ----- |
| Has `enforcement_divergence` (local vs national conflict) | 1.00  |
| Has cross-domain impact (visa x tax, visa x property)     | 0.90  |
| Has "second consequence" (non-obvious downstream effect)  | 0.80  |
| Has before/after comparison (old rule vs new rule)        | 0.70  |
| Has geographic specificity (Bali-specific angle)          | 0.60  |
| Simple factual update (fee change, deadline change)       | 0.30  |

### 4.2 EVS Thresholds

| EVS       | Classification       | Action                                                |
| --------- | -------------------- | ----------------------------------------------------- |
| >= 0.65   | **STRONG CANDIDATE** | Include in War Room prompt as priority option         |
| 0.45-0.64 | **MODERATE**         | Include in War Room prompt as secondary option        |
| < 0.45    | **WEAK**             | Not included in War Room prompt (stays in brief only) |

### 4.3 Adoption Rate Model

```
adoption_rate = NLM_originated_articles / total_editorial_articles (weekly)
```

| Adoption Rate | Health Status      | Diagnosis & Action                                                  |
| ------------- | ------------------ | ------------------------------------------------------------------- |
| < 5%          | UNHEALTHY (low)    | NLM suggestions irrelevant to editorial. Redesign query templates   |
| 5-10%         | CALIBRATING        | Acceptable Month 1. Monitor for improvement                         |
| **10-20%**    | **MONTH 1 TARGET** | NLM supplements editorial without dominating                        |
| **25-35%**    | **MONTH 6 TARGET** | Healthy steady state. NLM is a valued editorial input               |
| 35-50%        | CAUTION            | NLM is becoming primary driver. Monitor editorial independence      |
| > 50%         | UNHEALTHY (high)   | NLM dominates. Cap NLM suggestions at 2/week. Force manual override |

**Week-level expected trajectory:**

| Period  | NLM articles/week | Total articles/week | Adoption Rate |
| ------- | ----------------- | ------------------- | ------------- |
| Month 1 | 0.5-1.5           | 5-10                | 8-18%         |
| Month 3 | 1.5-3.0           | 7-10                | 18-35%        |
| Month 6 | 2.0-3.5           | 7-10                | 25-40%        |

---

## 5. Integration KPIs

### 5.1 Primary KPIs — Measured Weekly

| #   | KPI Name                          | Formula                                                        | M1 Target | M6 Target | Alarm If      |
| --- | --------------------------------- | -------------------------------------------------------------- | --------- | --------- | ------------- |
| 1   | **NLM->Article Conversion**       | `articles_from_NLM / topics_handed_off`                        | 15-25%    | 30-45%    | < 10% (3 wk)  |
| 2   | **Cross-Val Confirmation Rate**   | `claims_confirmed_by_scraper / claims_in_overlap`              | 60-75%    | 75-90%    | < 50%         |
| 3   | **Handoff Freshness**             | `median(scraper_start_ts - nlm_brief_ts)` in minutes           | 40-60 min | 40-60 min | > 120 min     |
| 4   | **War Room Adoption**             | `NLM_editorial_articles / total_editorial`                     | 10-20%    | 25-35%    | < 5% or > 65% |
| 5   | **False Positive Rate**           | `NLM_topics_contradicted_by_scraper / total_topics_handed_off` | < 10%     | < 5%      | > 15%         |
| 6   | **Intelligence Advantage**        | `NLM_exclusive / (NLM_exclusive + overlap)`                    | 40-60%    | 35-55%    | < 20%         |
| 7   | **Integration Value Added (IVA)** | `(combined_unique - max_single) / max_single`                  | 0.15-0.25 | 0.35-0.55 | < 0.10        |
| 8   | **Pipeline Reliability**          | `successful_handoffs / scheduled_handoffs`                     | > 90%     | > 95%     | < 80%         |

### 5.2 Secondary KPIs — Measured Monthly

| #   | KPI Name                              | Formula                                                            | Target            |
| --- | ------------------------------------- | ------------------------------------------------------------------ | ----------------- |
| 9   | **Confidence Upgrade Rate**           | `PROVISIONAL->VERIFIED via scraper / total PROVISIONAL in overlap` | 15-30%            |
| 10  | **Confidence Downgrade Rate**         | `claims_downgraded_after_contradiction / total_claims`             | < 8%              |
| 11  | **Topic Diversity (Shannon Entropy)** | `H = -sum(p_i * log2(p_i))` across 5 visa clusters in handoff      | > 1.20 (max 2.32) |
| 12  | **Scraper Enrichment Pickup**         | `scraper_articles_citing_NLM_context / total_scraper_articles`     | 10-25%            |
| 13  | **NLM Claim Density**                 | `claims_at_PROVISIONAL+ / queries_executed`                        | 1.5-2.5           |
| 14  | **Handoff Efficiency**                | `topics_at_HANDOFF / total_claims_extracted`                       | 20-40%            |

### 5.3 KPI Dashboard Format (Weekly Report)

```
+================================================================+
|  NLM <-> SCRAPER INTEGRATION REPORT — WEEK 2026-W14            |
+================================================================+
|                                                                  |
|  PRIMARY KPIs                                                    |
|  ---------------------------------------------------------------+
|  1. NLM->Article Conversion:   3/10 = 30%  [OK]   (tgt 15-25%) |
|  2. Cross-Val Confirmation:    5/7  = 71%  [OK]   (tgt 60-75%) |
|  3. Handoff Freshness:         45 min med  [OK]   (tgt 40-60m) |
|  4. War Room Adoption:         2/8  = 25%  [OK]   (tgt 10-20%) |
|  5. False Positive Rate:       1/10 = 10%  [WARN] (tgt <10%)   |
|  6. Intelligence Advantage:    5/8  = 63%  [OK]   (tgt 40-60%) |
|  7. IVA:                       0.36        [OK]   (tgt 0.15+)  |
|  8. Pipeline Reliability:      5/5  = 100% [OK]   (tgt >90%)   |
|                                                                  |
|  HEALTH: 7/8 OK, 1 WARNING                                      |
|  ACTION: Review false positive claim NB2-2026-03-25-003          |
|                                                                  |
|  CROSS-VALIDATION BREAKDOWN                                      |
|  ---------------------------------------------------------------+
|  NLM claims:       8    Scraper articles:  14                    |
|  OVERLAP:          3    (15.8%)                                  |
|  NLM_EXCLUSIVE:    5    (26.3%)                                  |
|  SCRAPER_EXCL:    11    (57.9%)                                  |
|  IVA:             5/14 = 0.357                                   |
|                                                                  |
|  CONFIDENCE CHANGES THIS WEEK                                    |
|  ---------------------------------------------------------------+
|  Boosted:     2 claims  (avg +0.085)                             |
|  Penalized:   0 claims                                           |
|  Disputed:    1 claim   (held, pending review)                   |
|  PROV->VER:   1 (NB2-2026-03-24-002: 0.72 -> 0.78)             |
|                                                                  |
+================================================================+
```

### 5.4 KPI Health Summary Formula

```
health_score = (KPIs_in_target / total_KPIs) * 100

GREEN:  health_score >= 75%  (6+ of 8 primary KPIs in target)
YELLOW: health_score >= 50%  (4-5 of 8)
RED:    health_score < 50%   (fewer than 4)
```

---

## 6. Information Flow Budget

### 6.1 The Funnel

```
NLM Deep Research (2 queries/day)
  |
  |  3-5 claims extracted per day
  |  (15-25 claims/week)
  v
[Confidence Filter: >= 0.55]  ~75% pass
  |
  |  2-4 claims/day (10-20/week)
  v
[TRS Relevance Filter: >= 0.45]  ~60% pass
  |
  |  1-3 topics/day (6-12/week)
  v
[Handoff Package: top 5]
  |
  |  1-3 topics/day in scraper_input.json (5-10/week)
  v
[Scraper Pickup]  ~50% explored
  |
  |  0.5-1.5 NLM-influenced articles/day (3-7/week)
  v
[War Room Selection]  ~30% chosen
  |
  |  0.2-0.6 editorial articles/day from NLM (1-3/week)
  v
Published
```

### 6.2 Stage-by-Stage Expected Numbers

| Stage                            | Volume/Day | Volume/Week | Conversion from Previous |
| -------------------------------- | ---------- | ----------- | ------------------------ |
| NLM claims extracted             | 3-5        | 15-25       | (input)                  |
| After confidence filter (>=0.55) | 2-4        | 10-20       | ~75%                     |
| After TRS filter (>=0.45)        | 1-3        | 6-12        | ~60%                     |
| In handoff package               | 1-3        | 5-10        | ~85% (cap at 5/day)      |
| Scraper picks up topic           | 0.5-1.5    | 3-7         | ~50%                     |
| War Room selects                 | 0.2-0.6    | 1-3         | ~35%                     |
| Published editorial article      | 0.2-0.4    | 1-2         | ~60%                     |

### 6.3 Overall End-to-End Yield

```
E2E_yield = published_from_NLM / total_NLM_claims
          = (1-2) / (15-25)
          = 4-13%
```

This is intentionally low. NLM's primary value is NOT article production. It is:

1. **Intelligence enrichment:** scraper articles backed by NLM context are higher quality
2. **Confidence validation:** cross-validation upgrades PROVISIONAL claims to VERIFIED
3. **Early warning:** NLM detects regulatory changes 1-7 days before scraper news coverage
4. **Editorial depth:** War Room articles from NLM topics have pre-verified sourcing

The 4-13% conversion measures only the visible output. The invisible output (better scraper articles, higher confidence scores, earlier detection) is measured by the IVA and cross-validation KPIs.

### 6.4 Noise Diagnosis Table

| Symptom                        | Probable Cause                                  | Fix                                            |
| ------------------------------ | ----------------------------------------------- | ---------------------------------------------- |
| > 15 topics/day in handoff     | TRS threshold too low, NLM too broad            | Raise TRS HANDOFF to 0.70                      |
| < 1 topic/day in handoff       | TRS too high or NLM not finding enough          | Lower TRS HANDOFF to 0.55; check query quality |
| Scraper ignores all NLM topics | Handoff format misaligned with scraper          | Review handoff JSON; align categories          |
| War Room picks only NLM topics | NLM topics are "too good"                       | Cap NLM suggestions at 2 in War Room prompt    |
| Same topic 3+ consecutive days | Hot topic override not decaying                 | Check override.expires_at; force decay         |
| Conversion > 60% at all stages | Pipeline too permissive, noise leaking          | Spot-check quality; raise TRS thresholds       |
| E2E yield > 25%                | Either very few NLM claims or too many articles | Check if NLM claim count dropped; investigate  |

### 6.5 Hard Budget Constraints

| Constraint                      | Limit  | Source                            |
| ------------------------------- | ------ | --------------------------------- |
| NLM queries per day             | 3 max  | Step 2 rate limit budget          |
| Topics in handoff per day       | 5 max  | Scraper 10 req/min constraint     |
| NLM topics in War Room prompt   | 3 max  | Editorial independence safeguard  |
| Handoff file max age for use    | 24h    | Stale intelligence = wrong advice |
| Scraper articles from NLM seeds | <= 30% | Scraper independence guarantee    |
| War Room NLM adoption cap       | <= 50% | Editorial independence            |

---

## 7. Success Criteria — Go/No-Go

### 7.1 Month 1 Pass/Fail (Must Pass 5 of 6)

| #   | Criterion                              | Pass Condition                                       |
| --- | -------------------------------------- | ---------------------------------------------------- |
| 1   | NLM produces actionable intelligence   | >= 8 claims at PROVISIONAL+ per week                 |
| 2   | Handoff reaches scraper reliably       | Pipeline reliability >= 90%                          |
| 3   | Cross-validation produces signal       | OVERLAP 15-25% AND NLM_EXCL 35-55%                   |
| 4   | At least 1 article/week from NLM topic | NLM->Article conversion >= 10%                       |
| 5   | Acceptable false positive rate         | < 15% of handoff topics contradicted by scraper      |
| 6   | No system degradation                  | Scraper daily article count unchanged within +/- 10% |

### 7.2 Month 1 Failure Response

| Failed Criterion | Severity | Response                                                           |
| ---------------- | -------- | ------------------------------------------------------------------ |
| #1               | HIGH     | Review NLM query templates; may need more L1 monitoring queries    |
| #2               | HIGH     | Debug cron timing, file permissions, disk space                    |
| #3               | MEDIUM   | Adjust NLM query focus toward more practical/current topics        |
| #4               | LOW      | Expected variance in Month 1. Monitor 2 more weeks before action   |
| #5               | HIGH     | Tighten NLM confidence thresholds; add more cross-reference stages |
| #6               | CRITICAL | Pause NLM handoff immediately. Investigate scraper performance     |

### 7.3 Month 6 Steady-State Targets

| Metric                      | Target                            |
| --------------------------- | --------------------------------- |
| NLM->Article Conversion     | 30-45%                            |
| Cross-Val Confirmation Rate | 75-90%                            |
| War Room Adoption           | 25-35%                            |
| IVA                         | 0.35-0.55                         |
| False Positive Rate         | < 5%                              |
| Pipeline Reliability        | > 95%                             |
| Confidence Upgrade Rate     | 15-30% of PROVISIONAL -> VERIFIED |
| Topic Diversity (Shannon H) | > 1.20 across 5 visa clusters     |

---

## 8. Anti-Feedback-Loop Safeguards

### 8.1 The Risk

```
NLM finds X -> scraper writes article about X -> NLM re-discovers X from scraper article
-> confidence boosted -> more scraper articles about X -> amplification loop
```

Meanwhile, topics Y and Z starve from attention.

### 8.2 Quantified Safeguards

| #   | Safeguard                     | Formula / Rule                                                               | Measured By                         |
| --- | ----------------------------- | ---------------------------------------------------------------------------- | ----------------------------------- |
| 1   | Source provenance tracking    | Claims carry `discovery_pipeline: "nlm"`. NLM ignores `nlm_derived` articles | `is_independent_article()` check    |
| 2   | Cluster concentration cap     | Max 3/5 handoff topics from same cluster per day; max 60%/week               | `cluster_fraction` in weekly report |
| 3   | Consecutive-day novelty decay | If topic in handoff 3+ consecutive days: `F_novelty *= 0.7^(days - 2)`       | Handoff state file                  |
| 4   | Scraper independence floor    | Scraper >= 50% articles from own RSS (not NLM seeds) per day                 | `nlm_seeded / total` ratio          |
| 5   | NLM self-dedup                | NLM checks against OWN prior handoffs for F_novelty, not just scraper        | Handoff topic_id history            |

### 8.3 Feedback Loop Detection Score

```
loop_score = (consecutive_days_in_handoff / 5) * (topic_fraction_of_scraper_articles / 0.5)
```

| loop_score | Status   | Action                                           |
| ---------- | -------- | ------------------------------------------------ |
| < 0.30     | Normal   | No action                                        |
| 0.30-0.60  | Warning  | Log. Apply novelty decay for this topic          |
| 0.60-0.80  | Active   | Force-exclude topic from next 2 handoffs         |
| > 0.80     | Critical | Telegram alert. Manual review of query templates |

**Example:** Topic X is in handoff for 4 consecutive days (`4/5 = 0.80`) and represents 40% of scraper articles that day (`0.40/0.50 = 0.80`). `loop_score = 0.80 * 0.80 = 0.64` -> Active loop. Force-exclude for 2 days.

---

## 9. ROI Framework — Is Integration Worth It?

### 9.1 Cost Model

| Cost Component                   | Monthly Estimate    | Notes                                       |
| -------------------------------- | ------------------- | ------------------------------------------- |
| NLM Deep Research queries        | ~40-60 queries/mo   | Within free tier or $10-20/mo NLM budget    |
| Exa API (NLM-seeded searches)    | ~120-180 queries/mo | $0.001/query = $0.12-0.18/mo                |
| Compute (OpenClaw cron)          | ~0                  | Runs on Pro, already provisioned            |
| Engineering time (initial setup) | ~5 days             | One-time; Gemini doc section 8 has phasing  |
| Maintenance                      | ~2 hours/month      | Query template tuning, threshold adjustment |

**Total incremental cost: ~$10-20/month + 2h/month maintenance.**

### 9.2 Value Model

| Value Component                     | Quantification                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| Early detection (1-7 days ahead)    | Client advisory lead time; unmeasurable in $ but critical for trust                   |
| Higher article quality (NLM-backed) | Quality score of NLM-backed articles vs independent (target: +10-20 points)           |
| Cross-validated intelligence        | 15-30% of PROVISIONAL claims promoted to VERIFIED (higher trust in brief)             |
| Editorial efficiency                | 25-35% of War Room topics pre-researched (saves 30-60 min editorial research/article) |
| Unique intelligence (NLM-exclusive) | 25-40% of combined intelligence found ONLY by NLM                                     |

### 9.3 Break-Even Condition

Integration pays for itself when:

```
(editorial_time_saved_per_NLM_article * NLM_articles_per_month * hourly_rate)
+ (value_of_early_detection * early_detections_per_month)
> monthly_cost + (maintenance_hours * hourly_rate)
```

Conservative estimate:

- 6 NLM articles/month _ 0.5h saved _ $50/h = $150/month editorial savings
- 2 early detections/month \* $100 client value = $200/month advisory value
- Cost: $20 + 2h\*$50 = $120/month

**Net ROI: +$230/month at steady state.** Positive from Month 2.

---

## Source AI Attribution

This document provides the **DeepSeek R1 perspective**: every concept from the Gemini
architecture document (05_scraper_integration.md) is quantified with explicit formulas,
expected ranges, worked examples, and measurable success criteria.

The two documents are complementary:

- **05_scraper_integration.md** (Gemini): HOW — architecture, code sketches, integration modes, file formats
- **05b_scraper_integration_deepseek.md** (this): HOW MUCH — formulas, thresholds, KPI tables, ROI
