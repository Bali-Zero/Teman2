# Step 4: Source Management — NB-2 Deep Research Pipeline

> Synthesis: Claude Opus 4.6 (architect) + DeepSeek R1 (formulas) + Gemini (architecture) + Codex (discipline) (2026-03-28)
> Status: Brainstorm complete
> Dependencies: Steps 1-3 (query design, sequencing, quality verification)

---

## 1. Source Lifecycle: 6-Stage State Machine

### State Diagram

```
                              ┌──────────────────────────────────────────────────┐
                              │                                                  │
                              ▼                                                  │
  ┌─────────┐   auto    ┌────────────┐   daily    ┌─────────┐   promote   ┌──────────┐
  │  INGEST  │─────────▶│ QUARANTINE  │──────────▶│ TRIAGE   │──────────▶│  ACTIVE   │
  └─────────┘           └────────────┘            └─────────┘           └──────────┘
       │                      │                       │                      │  │
       │                 reject (noise)           reject (dup/low)      aging │  │ absorbed
       │                      │                       │                      │  │
       │                      ▼                       ▼                      │  ▼
       │                 ┌─────────┐             ┌─────────┐            ┌──────────────┐
       │                 │ DELETED  │             │ DELETED  │            │ CONSOLIDATE  │
       │                 └─────────┘             └─────────┘            └──────────────┘
       │                                                                     │
       │                                                                     │ digest written
       │                                                                     ▼
       │                                                                ┌─────────┐
       └────────────────────────── canonical (bypass) ─────────────────▶│ ARCHIVE  │
                                                                        └─────────┘
```

### Stage Definitions

| Stage           | Entry Trigger                                                    | Max Duration                              | Max Count                          | Exit Conditions                                                 |
| --------------- | ---------------------------------------------------------------- | ----------------------------------------- | ---------------------------------- | --------------------------------------------------------------- |
| **INGEST**      | `research_import` auto-imports sources from deep research        | 0 (instant pass-through)                  | Unbounded (transient)              | Immediate transition to QUARANTINE                              |
| **QUARANTINE**  | Every imported source lands here first                           | 24h (until next daily triage)             | 30                                 | Daily triage promotes or rejects                                |
| **TRIAGE**      | Daily pipeline Phase 5 (01:55 WITA)                              | 15 min (within consolidation)             | N/A (processing state)             | Promote to ACTIVE, reject to DELETED, flag for dedup            |
| **ACTIVE**      | Triage promotes source                                           | 90 days (working) / unlimited (canonical) | 70 hard cap                        | Aging trigger, absorption into Master Digest, or manual archive |
| **CONSOLIDATE** | Weekly Friday consolidation OR 80% capacity trigger              | 1 day (Friday pipeline)                   | N/A (processing state)             | Absorbed sources archived, Master Digest updated                |
| **ARCHIVE**     | Source absorbed into digest, or aged out, or capacity management | Permanent                                 | Unlimited (external tracking only) | Never re-enters NB-2. Claims preserved in metadata DB           |

### Stage Details

#### INGEST (instant, transient)

**What happens:** Before `research_import` pulls sources into NB-2, each candidate runs through a **pre-import filter** (`should_import()`). Only sources that pass all gates are imported.

**Pre-import filter (Codex contribution — runs BEFORE NLM import):**

```python
def should_import(source: dict, registry: SourceRegistry) -> tuple[bool, str]:
    """Gate function. Returns (allow, rejection_reason)."""
    url = source.get("url", "")
    normalized = normalize_url(url)

    # 1. Domain denylist
    if any(d in normalized for d in registry.domain_denylist):
        return False, "domain_denylist"

    # 2. URL dedup (exact + canonical match against ALL tracked sources)
    if registry.url_exists(normalized):
        return False, "duplicate_url"

    # 3. Source type exclusion
    EXCLUDED = {"forum", "social_personal", "travel_blog", "affiliate", "reddit", "quora"}
    if source.get("type") in EXCLUDED:
        return False, "excluded_source_type"

    # 4. Publication date floor (2024+ for news, any date for active regulations)
    pub_date = source.get("publication_date", "")
    if pub_date and pub_date < "2024-01-01":
        return False, "too_old"

    # 5. Language filter (Indonesian, English, Malay only)
    lang = source.get("language", "").lower()
    if lang and lang not in ("id", "en", "ms", ""):
        return False, "wrong_language"

    # 6. Budget pressure gates
    current = registry.count_in_nb2()
    if current >= 63 and source.get("estimated_tier", 6) > 2:
        return False, "budget_pressure_low_tier"
    if current >= 70:
        return False, "hard_cap_reached"

    return True, "allowed"
```

**Initial domain denylist (grows dynamically when a domain produces 3+ discards/week):**

```
tripadvisor.com, expat.com/forum, kaskus.co.id, nomadicmatt.com,
thepointsguy.com, reddit.com, quora.com, medium.com/@, youtube.com,
tiktok.com, pinterest.com, booking.com, agoda.com, skyscanner.com,
lonelyplanet.com
```

**Transition:** Sources passing the filter are imported via `research_import` and enter QUARANTINE. Rejected sources are logged in the state file with rejection reason but never enter NLM.

**Metadata captured at ingest:**

```json
{
  "nlm_source_id": "src_abc123",
  "ingest_timestamp": "2026-03-28T01:22:00+08:00",
  "ingest_query_id": "NB2-L1-2026-03-28",
  "ingest_method": "research_import",
  "raw_url": "https://...",
  "raw_title": "...",
  "detected_language": "id|en",
  "detected_tier": null,
  "category": null,
  "stage": "QUARANTINE"
}
```

#### QUARANTINE (max 24h, max 30 sources)

**What happens:** Sources sit untriaged until the next daily pipeline consolidation phase. They are IN the NLM notebook (NLM needs them imported to query against them), but our external state file marks them as unverified.

**Why quarantine?** Two reasons:

1. NLM Deep Research can import 10-20 sources per query. We run 2 queries/day = potentially 20-40 raw sources. Many are duplicates, noise, or low-tier.
2. We need time to assess tier, check for duplicates against existing ACTIVE sources, and score confidence before committing.

**Overflow rule:** If quarantine hits 30 sources (backlog from weekend gap or pipeline failures), oldest-first triage in next run. Never accumulate >30.

#### TRIAGE (processing state, within daily consolidation)

**What happens:** Each quarantined source is evaluated against the triage decision tree:

```
new_source arrives from QUARANTINE
  |
  +-- Exact URL match in ACTIVE set? --YES--> SKIP (delete from NB-2)
  |
  +-- Content overlap >= 0.90 with existing? --YES--> ARCHIVE (true duplicate)
  |
  +-- Content overlap >= 0.70 with existing?
  |     +-- New source SVS > existing SVS? --YES--> REPLACE (archive old, activate new)
  |     +-- No --> ARCHIVE new (existing is better)
  |
  +-- Source tier = T6 AND no T0-T4 corroboration? --YES--> ARCHIVE (unverifiable)
  |
  +-- Confidence 0.35-0.54 AND single source AND has claims?
  |     --YES--> DEMOTE to QUARANTINE (re-evaluate in 72h for corroboration)
  |              If still uncorroborated after 72h: ARCHIVE
  |
  +-- ACTIVE count >= 70?
  |     +-- New source SVS > min(existing SVS)? --YES--> REPLACE lowest-SVS
  |     +-- No --> ARCHIVE new (no room for marginal source)
  |
  +-- Relevance check: about immigration/visa/enforcement? --NO--> DELETE
  |
  +-- Recency check: published 2024+ OR regulation in force? --NO--> DELETE
  |
  +-- All checks pass --> ACTIVE
```

**Promotion criteria (all must pass):**

- Tier T0-T5 confirmed
- Not a duplicate of existing ACTIVE source (overlap < 0.70)
- Relevant to NB-2 scope (immigration, visa, enforcement, compliance)
- Passes recency check (2024+ for news, or active regulation)
- ACTIVE count would not exceed 70 after promotion

If ACTIVE count would exceed 70: trigger CONSOLIDATE before promoting.

#### ACTIVE (main working set, max 70 sources)

**What happens:** Source is live in NB-2, contributes to all `notebook_query` responses, and is tracked with full metadata.

**Sub-categories within ACTIVE (see Section 2 for budget):**

- Canonical: permanent references (laws, regulations) — no aging
- Working: temporary intelligence (news, enforcement reports, social posts) — 90-day max
- Master Digest: our synthesized documents — updated, never aged
- Reference: standing tables and guides — 6-12 month lifespan

**Aging rules for Working sources (exponential decay):**

| Source Type         | Half-Life | S at 7d | S at 30d | S at 90d |
| ------------------- | --------- | ------- | -------- | -------- |
| LAW_IN_FORCE        | Infinite  | 1.00    | 1.00     | 1.00     |
| LAW_SUPERSEDED      | 30 days   | 0.85    | 0.50     | 0.13     |
| REGULATION_CIRCULAR | 90 days   | 0.95    | 0.79     | 0.50     |
| OFFICIAL_PORTAL     | 60 days   | 0.92    | 0.71     | 0.35     |
| OFFICIAL_SOCIAL     | 30 days   | 0.85    | 0.50     | 0.13     |
| NEWS_ARTICLE        | 15 days   | 0.72    | 0.25     | 0.02     |
| ANALYSIS_REPORT     | 120 days  | 0.96    | 0.84     | 0.59     |
| MASTER_DIGEST       | 180 days  | 0.97    | 0.89     | 0.71     |

**Staleness formula:** `S(t, type) = e^(-lambda * t)` where `lambda = ln(2) / half_life`.
(Note: previous version had redundant `max(0, 1-(1-e^x))` — simplified. `e^(-x)` is always positive, no floor needed.)

**Auto-archive trigger:** `S(t, type) < 0.20` OR SVS < 0.25 after 14 days.

**Refresh mechanism:** When a source is cited by a new Deep Research result, its `last_confirmed_valid` timestamp resets. `t_effective = min(days_since_publication, days_since_last_confirmed)`.

**Manual pin:** A source can be pinned (exempt from aging) via state file flag. Use for sources with ongoing enforcement significance that was never formalized.

#### CONSOLIDATE (processing state, weekly + triggered)

**Triggers:**

1. **Scheduled:** Every Friday during consolidation phase
2. **Capacity:** When ACTIVE count hits 56 (80% of 70 cap)
3. **Manual:** Telegram command `/nlm_consolidate`

**Consolidation trigger conditions (ALL must be true):**

```
N_sources >= 4 on same topic           # At least 4 sources
AND all in same claim_category          # e.g., all LEGAL_CHANGE about Permenkumham X
AND topic_age >= 14 days                # Topic tracked 2+ weeks
AND no source added in last 3 days      # Topic has cooled
AND total_unique_claims >= 6            # Enough substance to justify
```

**Process:**

1. UNION all claims from N sources (deduplicated by claim matching)
2. For each unique claim, select BEST source chain (highest tier, most specific quote, 2 sources minimum)
3. Synthesize digest document (header + claims + source chains + archived source IDs)
4. Add digest as new source (`source_add` type=text, category=MASTER_DIGEST)
5. Archive N originals (`source_delete` from NB-2, metadata preserved externally)

**Information Loss Metric (ILM):**

```
ILM = 1.0 if originals == 0 else 1 - (unique_claims_in_digest / unique_claims_in_all_originals)
```

(Guard: if zero originals, ILM = 1.0 → rejects consolidation. Prevents division by zero.)

| ILM       | Action                                                       |
| --------- | ------------------------------------------------------------ |
| < 0.05    | Proceed                                                      |
| 0.05-0.10 | Proceed with logging of dropped claims                       |
| > 0.10    | REJECT: do NOT archive originals, review consolidation logic |

**Claims that MUST be preserved:** Any VERIFIED or PROVISIONAL claim, any claim with `enforcement_divergence: true`, any claim that is sole evidence for a specific assertion, all T0-T2 source chain entries.

#### ARCHIVE (permanent, external only)

**What happens:** Source is removed from NB-2 (`source_delete`) but its full metadata + extracted claims are preserved in the external state file and `claim_archive.jsonl`.

**What is preserved:** Full source metadata (URL, title, tier, dates, all scores), all extracted claims with confidence scores, which Master Digest absorbed the claims, archive reason.

**What is lost:** NLM can no longer query against the original source text. This is acceptable because key claims are preserved in Master Digests (which ARE in NB-2), the external claim archive enables future re-import if needed, and original URLs remain for manual reference.

### Hard SLA Enforcement (Codex contribution)

| Stage              | Max Duration                    | If SLA Breached                                  |
| ------------------ | ------------------------------- | ------------------------------------------------ |
| INGEST             | 0 (transient)                   | N/A — filter passes or rejects immediately       |
| QUARANTINE         | 48h (2 pipeline runs)           | Auto-discard. Log as `quarantine_sla_breach`     |
| TRIAGE             | 0 (transient — within same run) | N/A                                              |
| ACTIVE (working)   | 90 days                         | Auto-archive regardless of SVS                   |
| ACTIVE (canonical) | Unlimited                       | Manual review only                               |
| CONSOLIDATE        | 7 days (1 Friday cycle)         | Force to ARCHIVE. Log `consolidation_incomplete` |

---

## 2. Source Categories & Budget

### Budget Allocation (70 ACTIVE cap)

```
+----------------------------------------------------------------+
|                    70 ACTIVE SOURCE BUDGET                       |
|                                                                 |
|  +-----------------------+  +------------------------------+    |
|  |  CANONICAL: 15-25     |  |  WORKING: 25-35              |    |
|  |  (permanent anchors)  |  |  (rolling intelligence)      |    |
|  |                       |  |                              |    |
|  |  Target: 20           |  |  Target: 30                  |    |
|  |  Min: 15              |  |  Max: 35 (triggers consol.)  |    |
|  |  Max: 25              |  |  Min: 15 (alarm if below)    |    |
|  +-----------------------+  +------------------------------+    |
|                                                                 |
|  +-----------------------+  +------------------------------+    |
|  |  MASTER DIGEST: 4-8   |  |  REFERENCE: 3-6              |    |
|  |  (synthesized docs)   |  |  (standing tables)           |    |
|  |                       |  |                              |    |
|  |  Fixed 4 minimum:     |  |  Target: 5                   |    |
|  |    MD-1 Change Log    |  |  Min: 3                      |    |
|  |    MD-2 Ops Status    |  |  Max: 6                      |    |
|  |    MD-3 Cross-Domain  |  |                              |    |
|  |    MD-4 Open Questions|  |                              |    |
|  +-----------------------+  +------------------------------+    |
|                                                                 |
|  HEADROOM: ~11 slots (15%) for ingest spikes / breaking news    |
|  IDEAL STEADY STATE: ~59 sources                                |
+----------------------------------------------------------------+
```

### Ideal Steady-State Composition (Month 3+)

| Category      | Count  | % of Budget | Tier Distribution              |
| ------------- | ------ | ----------- | ------------------------------ |
| Canonical     | 20     | 29%         | T0: 8-10, T1: 5-7, T2: 3-5     |
| Working       | 30     | 43%         | T2-T3: 5-8, T4: 5-8, T5: 10-15 |
| Master Digest | 5      | 7%          | N/A (our own documents)        |
| Reference     | 5      | 7%          | T0-T2 derived                  |
| **Headroom**  | **10** | **14%**     | Buffer for ingest spikes       |
| **Total**     | **70** | **100%**    |                                |

### Why 70 and Not Higher?

NLM Ultra tier allows 600 sources per notebook. But NB-2 is an intelligence notebook, not a document store:

1. **Signal-to-noise ratio degrades** above ~80 sources — NLM synthesis quality drops when irrelevant sources dilute the context window
2. **Query latency increases** with source count — each `notebook_query` considers all sources
3. **Consolidation discipline** is the core value proposition — Master Digests compress 10 articles into 1 verified summary
4. **Headroom for spikes** — breaking news can import 15+ sources in a day; we need room without emergency archival
5. **Budget for other notebooks** — 8 notebooks sharing 600-source cap means ~75 per notebook is fair share

### Canonical Source Seed List (NB-2 Initial Population)

| #     | Source                                        | Tier  | Type             | Language |
| ----- | --------------------------------------------- | ----- | ---------------- | -------- |
| 1     | UU Nomor 1 Tahun 2026 (Imigrasi)              | T0    | Law              | ID       |
| 2     | UU Nomor 6 Tahun 2011 (Imigrasi, predecessor) | T0    | Law              | ID       |
| 3     | PP tentang PNBP Kemenkumham (latest)          | T0    | Regulation       | ID       |
| 4     | Permenkumham 22/2023 (visa/stay permits)      | T0    | Regulation       | ID       |
| 5     | Permenkumham on ITAS/ITAP categories          | T0    | Regulation       | ID       |
| 6     | Permenaker on RPTKA/TKA (latest)              | T0    | Regulation       | ID       |
| 7     | Permenaker on DKPTKA (latest)                 | T0    | Regulation       | ID       |
| 8-10  | Surat Edaran Ditjen Imigrasi (latest 3)       | T1    | Circular         | ID       |
| 11    | BKPM Investment Guidelines (PMA)              | T1    | Official guide   | ID/EN    |
| 12    | OSS-RBA operating procedures                  | T1    | Official guide   | ID       |
| 13    | Perda/Pergub Bali on foreign workers          | T2    | Local regulation | ID       |
| 14    | DPMPTSP Bali requirements guide               | T2    | Local guide      | ID       |
| 15    | Bali tourist levy regulation (2024)           | T2    | Local regulation | ID       |
| 16-18 | Key Permenkumham implementing regulations     | T0    | Regulation       | ID       |
| 19-20 | Additional circulars as identified            | T1-T2 | Various          | ID       |

---

## 3. Source Value Score (SVS)

### Purpose

When NB-2 approaches capacity, SVS determines which sources stay and which get archived. Higher SVS = more valuable = keep.

### Formula

```
SVS = min(1.0,
    W_tier * V_tier
  + W_claims * V_claims
  + W_freshness * S(t, type)
  + W_citations * V_citations
  + W_uniqueness * V_uniqueness
  + min(0.15, BONUS)    # BONUS capped at 0.15
)
```

### Weights

| Factor                               | Weight | Rationale                                                |
| ------------------------------------ | ------ | -------------------------------------------------------- |
| **Tier Authority (V_tier)**          | 0.25   | High-tier sources are harder to replace                  |
| **Claims Extracted (V_claims)**      | 0.25   | Sources with many verified claims are dense intelligence |
| **Freshness S(t,type)**              | 0.20   | Fresh sources carry current intelligence                 |
| **Citation Frequency (V_citations)** | 0.15   | Sources cited in briefs/queries are actively useful      |
| **Uniqueness (V_uniqueness)**        | 0.15   | Sources with non-overlapping claims are irreplaceable    |

### Sub-Score Definitions

**V_tier** (from Step 3 tier system):

| Tier                         | V_tier |
| ---------------------------- | ------ |
| T0 (national law)            | 1.00   |
| T1 (national implementation) | 0.90   |
| T2 (regional authority)      | 0.80   |
| T3 (enforcement)             | 0.65   |
| T4 (official social)         | 0.50   |
| T5 (press)                   | 0.35   |
| T6 (community)               | 0.10   |

**V_claims** (normalized by extraction density):

```
V_claims = min(1.0, claims_extracted / 8)
```

- 0 claims: V = 0.00 (source added but never produced intelligence)
- 4 claims: V = 0.50 (typical good source)
- 8+ claims: V = 1.00 (dense intelligence source — capped)

**V_citations** (how often the source was referenced in pipeline outputs):

```
V_citations = min(1.0, times_cited_in_briefs / 5)
```

- 0 citations: V = 0.00 (imported but never used — dead weight)
- 3 citations: V = 0.60 (regularly referenced)
- 5+ citations: V = 1.00 (core reference source)

**V_uniqueness** (fraction of claims that ONLY this source provides):

```
V_uniqueness = unique_claims / max(1, total_claims)
```

**BONUS** (additive, max +0.15):

| Condition                                                         | Bonus |
| ----------------------------------------------------------------- | ----- |
| Source is the SOLE T0-T2 backing for an active VERIFIED claim     | +0.10 |
| Source was manually promoted/pinned by operator                   | +0.05 |
| Source covers a regulatory gap (no other source on this subtopic) | +0.10 |
| Source is a Master Digest                                         | +0.05 |

### SVS Classification

| SVS Range   | Classification | Action                                                             |
| ----------- | -------------- | ------------------------------------------------------------------ |
| >= 0.70     | **ESSENTIAL**  | Never auto-archive. Manual review only                             |
| 0.45 - 0.69 | **VALUABLE**   | Keep unless at hard capacity. Archive last                         |
| 0.25 - 0.44 | **MARGINAL**   | First candidates for consolidation or archive                      |
| < 0.25      | **EXPENDABLE** | Auto-archive. If V_claims = 0 and age > 14d: auto-delete from NB-2 |

### Worked Examples

```
Source: NusaBali article "Tim Pora sweeps Canggu businesses"
  V_tier = 0.35 (T5 press)
  V_claims = 0.25 (2 claims extracted)
  S(t=12, NEWS_ARTICLE) = 0.57 (12-day old news)
  V_citations = 0.20 (cited once in brief)
  V_uniqueness = 0.50 (1 of 2 claims is unique)
  BONUS = 0

SVS = 0.25*0.35 + 0.25*0.25 + 0.20*0.57 + 0.15*0.20 + 0.15*0.50
    = 0.088 + 0.063 + 0.114 + 0.030 + 0.075
    = 0.370 --> MARGINAL

Decision: Candidate for consolidation into weekly enforcement digest.
```

```
Source: JDIH Gazette -- Permenkumham 3/2026
  V_tier = 1.00 (T0 national law)
  V_claims = 0.50 (4 claims extracted)
  S(t=60, LAW_IN_FORCE) = 1.00 (no decay)
  V_citations = 1.00 (cited in 7 briefs)
  V_uniqueness = 0.75 (3 of 4 claims unique)
  BONUS = +0.10 (sole T0 backing for active claim)

SVS = 0.25*1.00 + 0.25*0.50 + 0.20*1.00 + 0.15*1.00 + 0.15*0.75 + 0.10
    = 0.250 + 0.125 + 0.200 + 0.150 + 0.113 + 0.100
    = 0.938 --> ESSENTIAL

Decision: Never archive. Core source.
```

---

## 4. Deduplication Strategy

### 4.1 When to Deduplicate

| Timing                            | Scope                         | Depth                       | Trigger                     |
| --------------------------------- | ----------------------------- | --------------------------- | --------------------------- |
| **At INGEST** (before NLM import) | URL match against tracked set | Exact URL                   | Every research_import       |
| **Daily triage** (01:55 WITA)     | QUARANTINE vs ACTIVE          | Title + content fingerprint | Every pipeline run          |
| **Weekly consolidation** (Friday) | ACTIVE vs ACTIVE              | Full claim overlap analysis | Scheduled                   |
| **On-demand**                     | Any stage                     | Manual review               | ACTIVE count > 56 (80% cap) |

### 4.2 Detection Methods

#### Level 1: Exact URL Match (instant, at INGEST)

```python
# If same URL already tracked (any stage), don't even import into NLM
if source.url in tracked_urls:
    action = "SKIP_IMPORT"
```

#### Level 2: Title Similarity (fast, during triage)

```python
# Normalized title comparison
title_a = normalize(source.title)  # lowercase, strip dates, remove outlet name
title_b = normalize(active_source.title)
if fuzz_ratio(title_a, title_b) > 0.85:
    flag = "PROBABLE_DUPLICATE"
```

#### Level 3: Content Fingerprint (medium, during triage)

```python
# SimHash of first 500 words of source content
# NLM provides source content via source_get_content
fingerprint = simhash(source_content[:500_words])
for active in active_sources:
    if hamming_distance(fingerprint, active.fingerprint) < 3:
        flag = "CONTENT_DUPLICATE"
```

#### Level 4: Claim Overlap (deep, during weekly consolidation)

Use claim-level overlap, NOT full-text similarity. Two sources may have different prose but contain the same regulatory information.

```
Overlap(A, B) = |claims(A) intersection claims(B)| / min(|claims(A)|, |claims(B)|)
```

Using `min()` denominator (Szymkiewicz-Simpson coefficient) rather than `union` (Jaccard) because we want to detect when a smaller source is fully contained within a larger one.

**Claim matching criteria — two claims are "same claim" when ALL of:**

1. Same `category` (e.g., both LEGAL_CHANGE)
2. Same `regulation_ref` or `subject_entity`
3. Same `assertion_direction` (e.g., both say "max stay reduced")
4. Temporal overlap: `|effective_date_A - effective_date_B| <= 30 days`

If only conditions 1+2 match but 3 or 4 differ, the claims are `CONFLICTING`, not duplicate.

### 4.3 Dedup Thresholds & Actions

| Scenario                                                     | Overlap   | Action                                                     |
| ------------------------------------------------------------ | --------- | ---------------------------------------------------------- |
| **TRUE_DUPLICATE** (same article, different URL)             | >= 0.90   | Auto-archive lower-SVS source                              |
| **SUBSTANTIAL_OVERLAP** (same regulation, different article) | >= 0.70   | Keep higher-SVS; archive lower unless it has unique claims |
| **PARTIAL_OVERLAP** (overlapping coverage)                   | 0.40-0.69 | Both stay. Flag for consolidation review                   |
| **INDEPENDENT**                                              | < 0.40    | No action. Different intelligence                          |
| **COMPETING_INTERPRETATION** (same reg, different analysis)  | N/A       | Both kept. Tag COMPETING_INTERPRETATION. Escalate to brief |

### 4.4 Resolution Rules (What to Keep)

When two sources cover the same content:

| Priority | Criterion         | Rationale                                                    |
| -------- | ----------------- | ------------------------------------------------------------ |
| 1st      | Higher tier       | T0 regulation beats T5 news article about same regulation    |
| 2nd      | More complete     | Full gazette text beats excerpt                              |
| 3rd      | More recent       | Updated version beats original (if same tier + completeness) |
| 4th      | Original language | Bahasa .go.id original beats English summary                 |
| 5th      | Wider scope       | Article covering 3 changes beats article covering 1 of same  |

**Edge cases:**

- Same regulation from gazette (T0) vs law firm analysis (T5): Keep BOTH. Gazette is canonical, analysis adds interpretation.
- Same enforcement event from 3 news outlets: Keep the one with most specific details, archive others.
- Same Instagram post screenshot from 2 sources: Keep original official account post, archive re-posts.

### 4.5 Dedup Metrics (health monitoring)

| Period  | Healthy | Warning                             | Alarm                                   |
| ------- | ------- | ----------------------------------- | --------------------------------------- |
| Daily   | 0-20%   | >30% (queries returning same stuff) | >50% (query templates stale)            |
| Weekly  | 10-25%  | >35% (rotation not diverse enough)  | >50% (urgent query redesign)            |
| Monthly | 15-30%  | >40% (sources converging)           | >50% (NB-2 saturated on current topics) |

**Alarm response:**

- Daily >30%: Log warning, check query similarity to previous day
- Weekly >35%: Review query templates for week's cluster, add specificity
- Weekly >50%: Emergency: rotate templates, add subtopics, Telegram alert
- Monthly >40%: Trigger early quarterly audit, redesign 30% of templates

---

## 5. Capacity Planning — 600-Source Budget

### 5.1 Source Accumulation Model

**Daily inflow (steady state):**

- 2 deep research queries/day
- Each query imports 3-5 sources after NLM filtering (deep mode typical)
- Daily gross import: 6-10 sources
- After URL dedup at INGEST: 5-8 enter QUARANTINE
- After triage (tier/relevance/dedup): 3-5 promoted to ACTIVE

**Weekly model:**

```
I_weekly = 5 days * 6.4 avg imports/day = 32 sources/week imported
A_weekly = staleness(4-8) + friday_dedup(3-6) + consolidation(1-2) = 8-16/week archived

Unmanaged steady state: ~120 sources (exceeds target)
```

### 5.2 Active Capacity Management

The pure staleness/dedup model stabilizes too high. We need active archive triggers:

```
CAPACITY THRESHOLDS:

  0----15----30----45----56----63----70
  |         |         |    |    |    |
  | ALARM   | NORMAL  | SOFT | HARD | CAP
  | (too    |         | TRIG | TRIG |
  |  few)   |         |      |      |
```

| Threshold        | Count      | Action                                                                   |
| ---------------- | ---------- | ------------------------------------------------------------------------ |
| **ALARM_LOW**    | <15 ACTIVE | Telegram alert: NB-2 underpopulated                                      |
| **NORMAL**       | 15-55      | No action needed                                                         |
| **SOFT_TRIGGER** | 56 (80%)   | Trigger CONSOLIDATE ahead of Friday. Archive lowest-SVS Working sources  |
| **HARD_TRIGGER** | 63 (90%)   | Emergency consolidation. Archive all Working >60 days, all T5-T6 Working |
| **HARD_CAP**     | 70         | No new promotions. QUARANTINE waits until space opens                    |

**Active management algorithm:**

```
IF N > CAPACITY_TARGET_HIGH (70):
    sorted = sources.sort_by(SVS, ascending)
    archive_count = N - CAPACITY_TARGET_MID (55)
    FOR source IN sorted[:archive_count]:
        IF source.SVS < 0.45:  # Only archive MARGINAL or EXPENDABLE
            archive(source)
        ELSE:
            break  # Don't archive VALUABLE sources to hit target
```

### 5.3 Revised Steady-State With Active Management

```
Week 1:  N = 40 + 32 - 8  = 64  --> trim to 55 (archive 9 lowest-SVS)
Week 2:  N = 55 + 32 - 14 = 73  --> trim to 55 (archive 18 lowest-SVS)
Week 3:  N = 55 + 32 - 18 = 69  --> within range, no trim
Week 4:  N = 69 + 32 - 24 = 77  --> trim to 55 (archive 22 lowest-SVS)

Steady state: oscillates 55-70, averaging ~63 (within target)
```

### 5.4 NLM 600-Source Global Budget

NB-2 targets 70 ACTIVE. NLM's per-notebook 600-source limit is NOT a concern:

| Consumed by                 | Count      | Note                                     |
| --------------------------- | ---------- | ---------------------------------------- |
| ACTIVE sources              | 70         | Our target cap                           |
| QUARANTINE (pending triage) | 0-30       | Temporary, triaged daily                 |
| **Total NLM-side**          | **70-100** | Max at any given moment                  |
| ARCHIVED                    | N/A        | Deleted from NLM, external tracking only |

**Cross-notebook budget (8 notebooks, 600 each):**

| Notebook         | Est. Active | Est. Quarantine | Total   |
| ---------------- | ----------- | --------------- | ------- |
| NB-1 Codebase    | ~30         | 0               | 30      |
| NB-2 Immigration | 70          | 30              | 100     |
| NB-3 Company     | 50          | 20              | 70      |
| NB-4 Tax         | 50          | 20              | 70      |
| NB-5 Property    | 40          | 15              | 55      |
| NB-6 Operations  | 30          | 10              | 40      |
| NB-7 Editorial   | 40          | 15              | 55      |
| NB-8 Expat Life  | 40          | 15              | 55      |
| **Total**        | **350**     | **125**         | **475** |

### 5.5 Dedup Failure Scenario (worst case)

If dedup completely fails (R_dedup = 0) and active management disabled:

```
N(week) = 40 + 42*week (net ~42/week growth)
Week 13: ~586 --> HITS 600 LIMIT at ~week 13.3
Time to 600 with zero dedup + zero active management: ~3 months
```

With active management but zero dedup:

```
Weekly trim keeps N at ~65
BUT: trimming 42 sources/week means losing nearly everything imported
Signal: if trim_count > 30/week for 2+ weeks --> dedup is broken --> ALARM
```

---

## 6. Four Master Documents

### 6.1 Architecture Decision: NLM Sources, NOT NLM Notes

**Decision:** Master Documents are uploaded as **NLM sources** (via `source_add` with `source_type=text`), not written as NLM notes.

**Note:** Codex argued for NLM Notes (mutable, no source-limit impact, instant availability). We chose Sources because:

**Rationale:**

- NLM **sources** are considered by the LLM when answering `notebook_query` — they contribute to synthesis
- NLM **notes** are user annotations — visible but NOT weighted in query responses the same way
- We want Master Digests to be first-class context for all NB-2 queries
- Sources can be updated by deleting and re-adding (same title preserves conceptual identity)
- The 4+ Master Documents count against our 70-source ACTIVE budget (4-8 slots permanently reserved)

**Update mechanism:**

```
1. Generate updated Markdown content locally
2. source_delete(old_source_id)
3. source_add(source_type="text", text=new_content,
     title="[NB2-MD] Change Log - Updated 2026-03-28")
4. Record new nlm_source_id in state file
```

**Naming convention:** All Master Documents prefixed with `[NB2-MD]` for easy identification.

### 6.2 Master Document Specifications

#### MD-1: Change Log (Regulatory Change Tracker)

**Purpose:** Running chronological record of all verified regulatory changes affecting immigration and visa in Indonesia.

**Content structure:**

```markdown
# NB-2 Immigration Regulatory Change Log

> Last updated: 2026-03-28 | Entries: 47 | Period: 2025-01-01 to present

## Active Changes (Currently in Effect)

### 2026-03-20 -- Permenkumham 8/2026: KITAS Sponsor Category Expansion

- **Status:** VERIFIED (0.91) | Effective: 2026-04-01
- **Impact:** New sponsor categories for KITAS applications
- **Source chain:** JDIH gazette (T0), Ditjen Imigrasi circular (T1)
- **Affected:** KITAS sponsor (Cluster B), family reunification
- **Cross-domain:** None identified
- **Bali impact:** DPMPTSP Bali updated forms (confirmed T2)

## Pending Changes (Announced, Not Yet Effective)

...

## Superseded (Historical Record)

...
```

**Update cadence:** Daily (during consolidation). New VERIFIED claims appended.
**Size management:** When entries >100, oldest superseded entries summarized. Target: 3,000-5,000 words.

#### MD-2: Operations Status (Current State of Offices & Procedures)

**Purpose:** Living snapshot of how immigration offices, systems, and procedures are actually operating RIGHT NOW. The "what's actually happening" document.

**Content structure:**

```markdown
# NB-2 Immigration Operations Status

> Last updated: 2026-03-28 | Confidence: aggregate 0.73

## System Status

- e-Visa Portal (molina.imigrasi.go.id): OPERATIONAL
- OSS-RBA (oss.go.id): OPERATIONAL, intermittent delays on RPTKA module
- SIMPONI (pnbp.kemenkumham.go.id): OPERATIONAL

## Office Operations -- Bali

### Kantor Imigrasi Ngurah Rai

- Status: NORMAL OPERATIONS
- Processing times: KITAS extension ~15 working days
- Known requirements: Original degree certificates for ITAS-RPTKA (PROVISIONAL)
- Operating hours: Mon-Thu 08:00-15:00, Fri 08:00-11:30
- Last confirmed: 2026-03-25 (Instagram @kanaboraingurahrai)

## Enforcement Climate

- Current intensity: MODERATE
- Focus areas: Canggu/Berawa, Kuta
- Last operation: 2026-03-22

## Known Divergences (Local Practice vs National Rule)

...
```

**Update cadence:** 2x/week (Monday + Friday). Claims >14 days unconfirmed get "LAST KNOWN" status.
**Size management:** Historical operations data moves to MD-1 or is dropped. Target: 2,000-3,500 words.

#### MD-3: Cross-Domain Impacts (Immigration x Company/Tax/Property)

**Purpose:** Tracks how immigration changes affect the other 3 business domains served by Bali Zero. L4 cross-domain intelligence.

**Content structure:**

```markdown
# NB-2 Cross-Domain Impact Register

> Last updated: 2026-03-28 | Active impacts: 12

## Immigration --> Company Setup (NB-3)

### RPTKA-before-incorporation requirement

- Trigger: Permenkumham X/2026 Art. 15
- Impact: PMA companies must obtain RPTKA before deed of establishment
- Confidence: VERIFIED (0.88)
- Client action: Sequence change for new PMA clients

## Immigration --> Tax (NB-4)

### KITAS holder NPWP enforcement

...

## Immigration --> Property (NB-5)

### KITAP Hak Pakai eligibility

...

## Pending Analysis

...
```

**Update cadence:** Monthly (first Thursday L4 query) + ad-hoc on cross-domain signals.
**Size management:** Resolved impacts move to archive section. Target: 2,000-4,000 words.

#### MD-4: Open Questions (Unresolved Signals & Pending Verification)

**Purpose:** Active investigation register. What we have detected but cannot yet verify. The "what we don't know" document.

**Content structure:**

```markdown
# NB-2 Open Questions Register

> Last updated: 2026-03-28 | Open: 8 | Resolved this week: 3

## HIGH PRIORITY (blocking client advisory)

### OQ-001: E33G Digital Nomad Visa Implementation Timeline

- First detected: 2026-03-15
- Signal: DG statement at press conference (T5 only)
- What we know: E33G regulation exists but no implementation guidelines
- What we need: Permenkumham implementing regulation, portal, fee schedule
- Follow-up plan: L1 query Cluster D, check JDIH weekly
- Status: OPEN (14 days) | Confidence: 0.42 (MONITORING)

## MEDIUM PRIORITY (watch list)

...

## RESOLVED (last 30 days)

### OQ-005: KITAS extension processing time [RESOLVED 2026-03-25]

- Resolution: Confirmed 15 working days via direct office inquiry (T2)
- Absorbed into: MD-2 Operations Status
```

**Update cadence:** Daily (most dynamic document). New questions from triage, resolutions from new findings.
**Size management:** Resolved questions kept 30 days then purged. Target: 1,500-3,000 words.

### 6.3 Master Document SVS

Master Documents always have:

- `V_tier` = 0.80 (synthetic T2-equivalent)
- `V_claims` = 1.00 (by definition, dense claims)
- `V_uniqueness` = 1.00 (they ARE the consolidation)
- `V_citations` = varies (typically high)
- Staleness = governed by MASTER_DIGEST half-life (180 days)
- **Minimum SVS is approximately 0.75 --> always ESSENTIAL**

### 6.4 Master Document Update Pipeline

```
DAILY (01:55 WITA, during consolidation):
  1. Read current MD-4 (Open Questions)
  2. Check if any new findings resolve an open question --> move to RESOLVED
  3. Check if any new PROVISIONAL claims create a new open question --> add
  4. Append new VERIFIED claims to MD-1 (Change Log)
  5. If new operational claims: flag MD-2 for next update

MONDAY + FRIDAY (within consolidation):
  6. Regenerate MD-2 (Operations Status) from current ACTIVE T2-T4 sources
  7. Check all "LAST KNOWN" entries in MD-2 -- if >14 days unconfirmed, demote

FRIDAY (during weekly consolidation):
  8. Review MD-1 for entry count, summarize old superseded entries if >100
  9. Check MD-3 for stale cross-domain impacts (>60 days unreviewed)

MONTHLY (first Thursday):
  10. Full MD-3 regeneration from L4 cross-domain query results
  11. Full audit: all 4 MDs consistent? MD-4 open questions actually open?
```

---

## 7. Source Metadata Schema & External State File

### 7.1 External State File

**Location:** `apps/evaluator/nlm_nb2_sources.json`
(Alongside `nlm_nb2_pipeline_state.json` from Step 2)

**Why external?** NLM provides no custom metadata fields. We need to track tier, category, claims, lifecycle stage, SVS, and scores externally, keyed by NLM source ID.

### 7.2 Source Record Schema

```json
{
  "schema_version": 1,
  "notebook_id": "NB-2",
  "last_updated": "2026-03-28T02:10:00+08:00",
  "summary": {
    "total_tracked": 142,
    "active": 58,
    "quarantine": 12,
    "archived": 72
  },
  "sources": {
    "src_abc123": {
      "nlm_source_id": "src_abc123",
      "stage": "ACTIVE",
      "category": "working",
      "source_type": "NEWS_ARTICLE",
      "title": "NusaBali: Ngurah Rai Tightens KITAS Extension Requirements",
      "url": "https://www.nusabali.com/...",
      "language": "id",
      "tier": 5,
      "tier_label": "T5_PRESS",

      "dates": {
        "published": "2026-03-20",
        "ingested": "2026-03-21T01:22:00+08:00",
        "promoted": "2026-03-21T01:55:00+08:00",
        "last_reviewed": "2026-03-28T01:55:00+08:00",
        "last_confirmed_valid": "2026-03-25T00:00:00+08:00",
        "expires": "2026-06-19",
        "archived": null
      },

      "ingest": {
        "query_id": "NB2-L1-2026-03-21",
        "query_level": "L1",
        "query_cluster": "A",
        "method": "research_import"
      },

      "scores": {
        "authority": 0.45,
        "type": 0.5,
        "recency": 0.9,
        "corroboration": 0.65,
        "specificity": 0.7,
        "geographic": 1.0,
        "penalty": 0,
        "confidence_composite": 0.63
      },

      "svs": {
        "v_tier": 0.35,
        "v_claims": 0.25,
        "v_freshness": 0.57,
        "v_citations": 0.2,
        "v_uniqueness": 0.5,
        "bonus": 0,
        "total": 0.37,
        "classification": "MARGINAL"
      },

      "claims": [
        {
          "claim_id": "NB2-2026-03-21-003",
          "category": "OPERATIONAL_CHANGE",
          "confidence_class": "PROVISIONAL",
          "confidence_score": 0.63,
          "absorbed_into_md": null,
          "status": "active"
        }
      ],

      "dedup": {
        "url_hash": "sha256:...",
        "title_normalized": "nusabali ngurah rai tightens kitas extension requirements",
        "content_fingerprint": "simhash:...",
        "known_duplicates": []
      },

      "flags": {
        "pinned": false,
        "enforcement_divergence": true,
        "superseded_by": null,
        "manual_review_needed": false,
        "competing_interpretation": false
      }
    }
  },

  "master_documents": {
    "MD-1": {
      "nlm_source_id": "src_md1_xyz",
      "title": "[NB2-MD] Change Log - Updated 2026-03-28",
      "last_updated": "2026-03-28T01:58:00+08:00",
      "entry_count": 47,
      "word_count": 4200,
      "version": 23
    },
    "MD-2": {
      "nlm_source_id": "src_md2_xyz",
      "title": "[NB2-MD] Operations Status - Updated 2026-03-28",
      "last_updated": "2026-03-28T01:58:00+08:00",
      "word_count": 2800,
      "version": 41
    },
    "MD-3": {
      "nlm_source_id": "src_md3_xyz",
      "title": "[NB2-MD] Cross-Domain Impacts - Updated 2026-03-01",
      "last_updated": "2026-03-01T02:00:00+08:00",
      "active_impacts": 12,
      "word_count": 3100,
      "version": 5
    },
    "MD-4": {
      "nlm_source_id": "src_md4_xyz",
      "title": "[NB2-MD] Open Questions - Updated 2026-03-28",
      "last_updated": "2026-03-28T01:56:00+08:00",
      "open_count": 8,
      "resolved_this_week": 3,
      "word_count": 2200,
      "version": 28
    }
  },

  "archive_index": {
    "src_old001": {
      "title": "...",
      "url": "...",
      "archived_date": "2026-03-25",
      "archive_reason": "absorbed_into_md1",
      "original_tier": 5,
      "original_category": "working",
      "claims_preserved": 2,
      "absorbed_into": "MD-1"
    }
  }
}
```

### 7.3 Claim Archive (Append-Only)

**Location:** `apps/evaluator/nlm_nb2_claims.jsonl`

Every extracted claim is logged here, regardless of source lifecycle. This is the permanent record.

```jsonl
{
  "claim_id": "NB2-2026-03-21-003",
  "claim_text": "Ngurah Rai now requires original degree certificates for ITAS-RPTKA extensions",
  "claim_text_id": "Kantor Imigrasi Ngurah Rai sekarang mewajibkan ijazah asli untuk perpanjangan ITAS-RPTKA",
  "category": "OPERATIONAL_CHANGE",
  "confidence_class": "PROVISIONAL",
  "confidence_score": 0.63,
  "source_ids": [
    "src_abc123",
    "src_def456"
  ],
  "extracted": "2026-03-21T01:55:00+08:00",
  "absorbed_into_md": "MD-2",
  "absorbed_date": "2026-03-25",
  "status": "absorbed",
  "geographic_scope": "LOCAL_OFFICE:Ngurah_Rai",
  "affected_visa_types": [
    "KITAS_RPTKA"
  ],
  "affected_services": [
    "work_permit",
    "visa_extension"
  ],
  "expires": "2026-06-19"
}
```

### 7.4 Source-to-Claim Linkage

```
+---------------+     1:N      +----------------+     N:1      +-------------------+
|  NLM Source   |------------->|    Claim       |------------>| Master Digest     |
|  (src_xxx)    |              | (NB2-xxx-xxx)  |             | (MD-1/2/3/4)      |
+---------------+              +----------------+             +-------------------+
     |                              |
     | tracked in                   | logged in
     v                              v
nlm_nb2_sources.json         nlm_nb2_claims.jsonl
```

One source can yield multiple claims. Multiple sources can corroborate the same claim. Claims are eventually absorbed into Master Digests. The claim archive preserves the full provenance chain even after sources are archived from NLM.

---

## 8. Notebook Health Score (NHS) & Alerting

### 8.1 NHS Composite Metric — CANONICAL FORMULA

> **This is the canonical NHS formula.** Any simplified NHS calculations in other documents
> (e.g., `07b_testing_protocol_deepseek.md` Phase 5) are estimation shortcuts — this formula
> is the production implementation.

```
NHS = W1*H_capacity + W2*H_freshness + W3*H_quality + W4*H_coverage + W5*H_dedup
```

**IMPORTANT: All sub-scores MUST be clamped to [0, 1] before weighting.**

| Factor          | Weight | Formula                                        | Ideal               |
| --------------- | ------ | ---------------------------------------------- | ------------------- |
| **H_capacity**  | 0.20   | `max(0, 1 - abs(N - 55) / 55)`                 | N=55 --> H=1.0      |
| **H_freshness** | 0.25   | `avg(S(t, type))` across all sources           | All fresh --> H=1.0 |
| **H_quality**   | 0.25   | `avg(SVS)` across all sources                  | High SVS --> H=1.0  |
| **H_coverage**  | 0.15   | `clusters/5 * 0.6 + categories/10 * 0.4`       | Full --> H=1.0      |
| **H_dedup**     | 0.15   | `max(0, 1 - max(0, dedup_week - 0.15) / 0.35)` | <15% --> H=1.0      |

### 8.2 Per-Pipeline-Run Metrics

```json
{
  "run_date": "2026-03-28",
  "run_id": "nb2-2026-03-28-001",
  "inventory": {
    "total_sources": 63,
    "by_category": {
      "canonical": 18,
      "working": 38,
      "master_digest": 5,
      "reference": 2
    },
    "by_tier": {
      "T0": 5,
      "T1": 8,
      "T2": 5,
      "T3": 4,
      "T4": 6,
      "T5": 30,
      "T6": 5
    }
  },
  "flow": {
    "imported_today": 7,
    "deduped_today": 2,
    "archived_staleness": 1,
    "archived_capacity_trim": 0,
    "net_change": 4
  },
  "quality": {
    "avg_svs": 0.52,
    "median_svs": 0.48,
    "svs_below_025": 3,
    "sources_zero_claims_gt14d": 1,
    "avg_staleness_score": 0.71,
    "sources_below_staleness_020": 2
  },
  "dedup": {
    "pairs_checked": 45,
    "true_duplicates": 1,
    "substantial_overlaps": 1,
    "competing_interpretations": 0,
    "dedup_ratio_today": 0.29,
    "dedup_ratio_week_rolling": 0.22
  },
  "coverage": {
    "clusters_covered_this_week": ["A", "B", "C"],
    "clusters_missing_this_week": ["D", "E"],
    "claim_categories_covered": 7,
    "visa_types_with_active_claims": ["KITAS_INVESTOR", "B211A", "KITAP", "VOA"]
  },
  "health_score": 0.78
}
```

### 8.3 Alert Thresholds

| Metric                      | Normal  | Warning         | Critical    |
| --------------------------- | ------- | --------------- | ----------- |
| **NHS**                     | >= 0.65 | 0.45-0.64       | < 0.45      |
| **Total sources**           | 40-70   | 71-100 or 30-39 | >100 or <30 |
| **Avg staleness**           | >= 0.60 | 0.40-0.59       | < 0.40      |
| **Sources 0 claims >14d**   | 0-2     | 3-5             | >5          |
| **Weekly dedup ratio**      | 10-25%  | 26-40%          | >40%        |
| **Canonical slots**         | 15-20   | <10 or >25      | <5 or >30   |
| **Days since T0-T2 import** | 0-7     | 8-14            | >14         |
| **NHS declining 3+ days**   | N/A     | Telegram alert  | N/A         |

### 8.4 Alert Routing

| Severity     | Channel                         | Response          |
| ------------ | ------------------------------- | ----------------- |
| **Normal**   | JSON log only                   | No action         |
| **Warning**  | Telegram notification           | Review within 24h |
| **Critical** | Telegram alert + pipeline pause | Immediate review  |

### 8.5 Weekly Health Report (Telegram)

```
NB-2 SOURCE HEALTH -- Week of 2026-03-25
========================================

ACTIVE: 58/70 (83%)  [Canonical: 20 | Working: 29 | MD: 4 | Ref: 5]
QUARANTINE: 7
ARCHIVED THIS WEEK: 12
PROMOTED THIS WEEK: 18
REJECTED THIS WEEK: 22

CAPACITY: NORMAL (below 80% threshold)
DEDUP RATE: 18% (healthy: 10-25%)
AVG SOURCE AGE: 34 days (Working only)
OLDEST WORKING: 82 days (nearing 90-day auto-archive)

MASTER DOCUMENTS:
  MD-1 Change Log: 47 entries, 4.2K words (v23)
  MD-2 Operations:  2.8K words, last Mon (v41)
  MD-3 Cross-Domain: 12 impacts, last Mar 1 (v5) [!] STALE
  MD-4 Open Questions: 8 open, 3 resolved (v28)

CLAIMS: 156 total | 14 VERIFIED | 31 PROVISIONAL | 111 archived
NHS: 0.78 (HEALTHY)
```

---

## 9. Operational Cadences Summary

### Daily (Mon-Fri, 01:55-02:10 WITA)

| Task                                    | Duration | Auto? |
| --------------------------------------- | -------- | ----- |
| Triage QUARANTINE (decision tree)       | 3 min    | Yes   |
| Dedup check (URL + title + fingerprint) | 2 min    | Yes   |
| Promote passing sources to ACTIVE       | 1 min    | Yes   |
| Calculate SVS for new ACTIVE sources    | 1 min    | Yes   |
| Extract claims from new sources         | 3 min    | Yes   |
| Update MD-4 (Open Questions)            | 2 min    | Yes   |
| Append to MD-1 (Change Log) if VERIFIED | 2 min    | Yes   |
| Check capacity thresholds               | 30 sec   | Yes   |
| Persist state file + metrics            | 30 sec   | Yes   |

### Twice Weekly (Monday + Friday)

| Task                                     | Duration | Auto? |
| ---------------------------------------- | -------- | ----- |
| Regenerate MD-2 (Operations Status)      | 5 min    | Yes   |
| Check "LAST KNOWN" entries for staleness | 2 min    | Yes   |

### Weekly (Friday)

| Task                                                | Duration | Auto? |
| --------------------------------------------------- | -------- | ----- |
| Full ACTIVE-vs-ACTIVE claim overlap (Level 4 dedup) | 5 min    | Yes   |
| Consolidation: absorb Working into Master Digests   | 10 min   | Yes   |
| Archive aged-out Working (>90 days or S<0.20)       | 3 min    | Yes   |
| Trim MD-1 superseded entries if >100                | 3 min    | Yes   |
| Weekly health report (Telegram)                     | 2 min    | Yes   |

### Monthly (last Friday + first Thursday)

| Task                                   | Duration | Auto?  |
| -------------------------------------- | -------- | ------ |
| Regenerate MD-3 (Cross-Domain) from L4 | 15 min   | Semi   |
| Full audit: 4 MDs consistency          | 10 min   | Semi   |
| Review Canonical: any superseded?      | 5 min    | Manual |
| Review Reference: any outdated?        | 5 min    | Manual |
| Source composition report              | 2 min    | Yes    |

### Quarterly

| Task                                 | Duration | Auto?  |
| ------------------------------------ | -------- | ------ |
| Full Canonical source review         | 30 min   | Manual |
| Dedup health: archive patterns       | 15 min   | Manual |
| Budget review: trends, incidents     | 15 min   | Manual |
| Accuracy spot-check: 5 random claims | 45 min   | Manual |
| Schema/process threshold review      | 30 min   | Manual |

---

## 10. Edge Cases & Design Decisions

### What if NLM Deep Research imports 0 sources?

Log empty result. NOT a failure (valid signal: nothing new). Alert if 3+ consecutive queries across clusters return 0 — possible rate limiting.

### What if a Canonical source is superseded?

Old Canonical transitions to archived with `archive_reason: "superseded_by"` and reference to new source. New law becomes active Canonical. MD-1 records the transition.

### What if we need to re-import an archived source?

Archive index has original URL. Use `source_add(source_type="url", url=original_url)`. Update state file with new NLM source ID and reset lifecycle.

### What about manually imported sources?

Track in same state file with `ingest.method: "manual"`. Go directly to ACTIVE with `category: "canonical"` — bypass quarantine (human-curated).

### What if NLM source IDs change?

Nightmare scenario. Mitigation: state file tracks `url` and `title` alongside `nlm_source_id`. If ID not found, match by URL then title. Log mismatches. Run `source_list_drive` periodically to verify.

### What about NLM source size limits?

NLM text sources can be up to 500,000 characters. Master Documents target 12,000-30,000 characters. Well within limits. If MD-1 exceeds 5,000 words, summarize older entries.

### Weekend quarantine backlog?

Pipeline OFF on weekends (Step 2). No new sources enter quarantine Sat/Sun. Monday absorbs any Friday leftovers (should be 0). Quarantine max 30 handles backlog.

### What if consolidation ILM exceeds 10%?

REJECT the consolidation. Do NOT archive originals. Log for manual review. This means the consolidation logic missed important claims — debug before retrying.

---

## 11. Month 1 Projections & Success Criteria

### Week-by-Week Projection

| Week      | Imports | Archives | Trim | Consolidations | N (end) | NHS (est) |
| --------- | ------- | -------- | ---- | -------------- | ------- | --------- |
| 0 (start) | --      | --       | --   | --             | 40      | 0.70      |
| 1         | 32      | 8        | 9    | 0              | 55      | 0.72      |
| 2         | 32      | 14       | 5    | 0              | 68      | 0.74      |
| 3         | 32      | 18       | 12   | 1 (-3 net)     | 65      | 0.76      |
| 4         | 32      | 22       | 8    | 2 (-8 net)     | 59      | 0.78      |

**Steady state (Month 2+):** N oscillates 55-70, NHS 0.75-0.82.

### Key Performance Indicators

| KPI                          | Target    | Cadence           |
| ---------------------------- | --------- | ----------------- |
| N (source count)             | 55 +/- 15 | Daily             |
| NHS (health score)           | >= 0.70   | Daily             |
| Avg SVS                      | >= 0.45   | Weekly            |
| Dedup ratio (weekly)         | 15-25%    | Weekly            |
| ILM (consolidation loss)     | < 0.05    | Per consolidation |
| Sources with 0 claims >14d   | <= 2      | Daily             |
| Days since last T0-T2 import | <= 7      | Daily             |
| Manual interventions / week  | <= 2      | Weekly            |

### Success Criteria for Month 1 Test

```
PASS if:
  - N stabilizes in 40-70 range by end of week 3
  - NHS never drops below 0.55
  - No more than 2 manual interventions per week needed
  - Dedup ratio never exceeds 40% for a full week
  - Zero consolidations lose > 5% of claims
  - At least 15 canonical sources maintained throughout

FAIL if:
  - N exceeds 100 at any point
  - NHS drops below 0.45 for 2+ consecutive days
  - Manual intervention needed daily
  - Dedup ratio exceeds 50% for any week
  - A consolidation drops a VERIFIED claim
```

---

## 12. Implementation Order

| Phase   | What                                                   | Dependencies           | Effort |
| ------- | ------------------------------------------------------ | ---------------------- | ------ |
| **P1**  | Create `nlm_nb2_sources.json` schema + CRUD utilities  | None                   | 2h     |
| **P2**  | Implement triage logic (decision tree + 5 criteria)    | P1                     | 3h     |
| **P3**  | Implement dedup (Level 1-3: URL, title, fingerprint)   | P1                     | 2h     |
| **P4**  | Implement SVS calculation + classification             | P1                     | 2h     |
| **P5**  | Write 4 initial Master Documents content               | NB-2 with seed sources | 4h     |
| **P6**  | Implement MD update pipeline (daily + weekly)          | P5                     | 4h     |
| **P7**  | Implement capacity management (thresholds + archival)  | P1, P2, P4             | 2h     |
| **P8**  | Implement weekly health report (NHS + Telegram)        | P1-P7                  | 2h     |
| **P9**  | Implement Level 4 dedup (claim overlap, weekly)        | P2, claims JSONL       | 3h     |
| **P10** | Implement consolidation engine (trigger + ILM check)   | P4, P6                 | 3h     |
| **P11** | Integration with Step 2 pipeline (consolidation hooks) | P1-P10                 | 4h     |
| **P12** | Seed NB-2 with 20 Canonical sources from seed list     | NB-2 exists            | 3h     |

**Total estimated effort: ~34 hours**
**Critical path: P1 --> P2 --> P4 --> P6 --> P11** (15h to minimum viable source management)

---

## Source AI Contributions

### DeepSeek R1 (Il Pensatore) — Formulas & Quantification

- Staleness formula with type-specific exponential decay and half-lives
- Source Value Score (SVS): 5-factor weighted formula with bonus system
- Szymkiewicz-Simpson coefficient for claim overlap (catches containment)
- Capacity planning: mathematical steady-state analysis with growth projections
- Information Loss Metric (ILM) as hard gate on consolidation
- Notebook Health Score (NHS) as composite operational metric
- Week-by-week projections for Month 1

### Gemini (Il Consigliere) — Architecture & Lifecycle

- 6-stage lifecycle model (INGEST through ARCHIVE)
- Quarantine concept: all sources enter unverified, triage promotes
- FLAGGED state for contradictions and competing interpretations
- Master Document as NLM sources (not notes) for query inclusion
- Weekly health report format with Telegram integration
- Cross-notebook 600-source budget allocation

### Codex GPT-5.4 (Il Soldato) — Discipline & Process

- `should_import()` pre-filter function (BEFORE NLM import, not just triage) — integrated into §1
- Domain denylist with dynamic growth (3+ discards/week → auto-add) — integrated into §1
- T7 transition: demote from TRIAGE to QUARANTINE for 72h corroboration wait — integrated into triage tree
- Hard SLA enforcement table with auto-discard on breach — integrated after ARCHIVE
- "Raw items temporary, master digests durable" principle
- 4 Master Documents concept (Change Log, Ops Status, Cross-Domain, Open Questions)
- Active capacity management algorithm (don't rely on passive decay alone)
- Consolidation trigger conditions (N>=4 AND cooled AND substantive)
- Dedup alarm response protocol (daily --> weekly --> monthly escalation)
- Full source registry schema with 25+ fields per source — 04b reference file preserved

### Claude Opus 4.6 (Architect) — This Synthesis

Merged all perspectives into unified spec. Key contributions:

- Integrated lifecycle stages into one coherent state machine with concrete transition rules
- Unified SVS + staleness + dedup into a single decision framework for all archival decisions
- Designed the external source metadata schema linking NLM source IDs to our tracking
- Wrote Master Document content templates with concrete examples and update cadences
- Defined operational cadences tying source management to the Step 2 pipeline timing (01:55 WITA)
- Created implementation phases with dependency chain and critical path analysis
