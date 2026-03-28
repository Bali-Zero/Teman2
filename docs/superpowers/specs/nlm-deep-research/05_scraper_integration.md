# Step 5: Intel Scraper Integration — NB-2 Deep Research Pipeline

> Synthesis: Claude Opus 4.6 (architect) merging Gemini (architecture) + Codex (contracts) + DeepSeek R1 (formulas) (2026-03-28)
> Status: Brainstorm complete — unified synthesis
> Depends on: Step 2 (Sequencing — timing), Step 3 (Quality Verification — claim metadata), Step 4 (Source Management — SVS, staleness, master documents)
> Reference files: `05b_scraper_integration_codex.md` (adapter class, testing), `05b_scraper_integration_deepseek.md` (TRS, IVA, KPIs)

---

## 0. System Context

Three independent systems must be connected without creating hard dependencies:

```
┌─────────────────────────┐
│  NLM Deep Research      │  01:00-02:20 WITA
│  (NB-2 Immigration)     │  Produces: verified intelligence brief
│  Upstream producer      │  Output: ~/.agent/decisions/nlm_to_scraper/
└──────────┬──────────────┘
           │ Handoff Package (optional)
           ▼
┌─────────────────────────┐
│  Intel Scraper          │  03:00 WITA (Pro, OpenClaw)
│  (bali-intel-scraper)   │  Scrapes news sites → enriches → publishes
│  Independent consumer   │  Output: data/intel_output_latest.json
└──────────┬──────────────┘
           │ Published articles + topic suggestions
           ▼
┌─────────────────────────┐
│  War Room               │  Manual trigger (human editorial)
│  (war-room)             │  Picks topics → creates carousels → delivers
│  Independent consumer   │  Input: intel_output_latest.json OR NLM brief
└─────────────────────────┘
```

**Cardinal rule:** Each system runs identically whether or not upstream output exists. Integration is ENRICHMENT, never DEPENDENCY.

---

## 1. Handoff Package Format

### 1.1 File Location & Versioning

```
~/.agent/decisions/nlm_to_scraper/
├── 2026-03-28.json            # Dated file (immutable after write)
├── 2026-03-27.json
├── ...
├── latest.json → 2026-03-28.json  # Symlink to most recent
└── _metadata.json             # Index: last 30 days of briefs
```

**Versioning rules:**

- NLM pipeline writes `YYYY-MM-DD.json` at 02:10 WITA
- After write, atomically update `latest.json` symlink: `ln -sf YYYY-MM-DD.json latest.json`
- Files older than 30 days: auto-deleted by NLM pipeline housekeeping
- `_metadata.json`: rolling index with dates, file sizes, finding counts — for observability only

### 1.2 JSON Schema — `scraper_input.json`

> **CANONICAL SCHEMA NOTE (review fix 2026-03-28):**
> The canonical handoff schema is defined in `05b_scraper_integration_codex.md` §1.2 with strict typing.
> Key field name mappings from this illustrative example to canonical:
>
> - `$schema` + `version` → `schema_version` (string, e.g. "1.0")
> - `key_findings` → `findings` (array of typed finding objects)
> - `confidence_score` → `confidence` (number 0.00-1.00)
> - `confidence_class` → `confidence_label` (enum: VERIFIED | PROVISIONAL)
> - `finding_id` → `claim_id` (unique, traceable — one claim per finding entry)
>   All test fixtures and implementation code MUST use the Codex canonical field names.

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-03-28T02:10:00+08:00",
  "pipeline_run_id": "nb2-2026-03-28-0100",
  "notebook_id": "nb2_immigration",
  "query_cluster": "A_work_permits",
  "queries_executed": 2,

  "key_findings": [
    {
      "finding_id": "NB2-2026-03-28-F001",
      "headline": "Permenkumham 8/2026 expands KITAS sponsor categories",
      "headline_id": "Permenkumham 8/2026 memperluas kategori sponsor KITAS",
      "category": "LEGAL_CHANGE",
      "confidence_score": 0.82,
      "confidence_class": "VERIFIED",
      "geographic_scope": "NATIONAL",
      "affected_visa_types": ["KITAS_RPTKA", "KITAS_INVESTOR"],
      "regulation_refs": ["Permenkumham 8/2026", "Art. 47", "Art. 48"],
      "effective_date": "2026-04-15",
      "source_tier_highest": "T0",
      "source_count": 3,
      "brief_section": "LAW",
      "scraper_action_hint": "PRIORITIZE",
      "suggested_search_queries": [
        "Permenkumham 8 2026 KITAS sponsor",
        "perubahan kategori sponsor KITAS 2026",
        "new KITAS sponsor regulation Indonesia"
      ],
      "suggested_article_angle": "What the KITAS sponsor expansion means for foreign companies — new categories open, but compliance burden increases",
      "claims": [
        {
          "claim_id": "NB2-2026-03-28-001",
          "claim_text": "Permenkumham 8/2026 adds 3 new KITAS sponsor categories effective April 15",
          "confidence_score": 0.85,
          "confidence_class": "VERIFIED"
        },
        {
          "claim_id": "NB2-2026-03-28-002",
          "claim_text": "Existing sponsors must re-register under new categories within 90 days",
          "confidence_score": 0.72,
          "confidence_class": "PROVISIONAL"
        }
      ]
    }
  ],

  "suggested_topics": [
    {
      "topic": "KITAS Sponsor Expansion: What Companies Need to Do Before April 15",
      "angle": "The compliance gap — new categories open opportunity but existing sponsors face re-registration deadline",
      "why_now": "Effective date is 18 days away, no major coverage yet",
      "confidence": 0.82,
      "priority": "HIGH",
      "finding_ids": ["NB2-2026-03-28-F001"],
      "target_audience": "foreign_company_owners"
    },
    {
      "topic": "Ngurah Rai Processing Delays: Third Week of ITAS Bottleneck",
      "angle": "Pattern analysis — not isolated incident but systemic staffing issue",
      "why_now": "Third consecutive enforcement_pattern signal, affecting active clients",
      "confidence": 0.65,
      "priority": "MEDIUM",
      "finding_ids": ["NB2-2026-03-28-F003"],
      "target_audience": "expats_visa_holders"
    }
  ],

  "hot_topics": [
    {
      "topic_key": "kitas_sponsor_reform_2026",
      "age_days": 3,
      "decay_status": "ACTIVE",
      "first_seen": "2026-03-25",
      "signal_count": 5,
      "latest_confidence": 0.82
    }
  ],

  "open_questions": [
    {
      "question": "Does Permenkumham 8/2026 Art. 48 override or supplement Art. 47 of the original regulation?",
      "blocking_claims": ["NB2-2026-03-28-002"],
      "suggested_search": "Permenkumham 8/2026 pasal 48 penjelasan",
      "priority": "HIGH"
    }
  ],

  "scraper_context": {
    "yesterday_scraper_overlap": {
      "articles_matching_today_findings": 2,
      "articles_novel_to_nlm": 8,
      "details": "Scraper covered KITAS sponsor topic yesterday but at headline level only"
    },
    "suggested_source_domains": [
      "kemenkumham.go.id",
      "jdih.kemenkumham.go.id",
      "hukumonline.com"
    ],
    "avoid_domains": [],
    "regulatory_categories_active": ["immigration", "legal"]
  },

  "cross_validation_requests": [
    {
      "claim_id": "NB2-2026-03-28-002",
      "claim_text": "Existing sponsors must re-register under new categories within 90 days",
      "current_confidence": 0.72,
      "what_would_boost": "Official source (T0-T2) confirming the 90-day re-registration deadline",
      "what_would_lower": "Official source saying re-registration is voluntary or has different timeline"
    }
  ]
}
```

### 1.3 Field Classification

**REQUIRED fields** (scraper integration fails gracefully without them, but they define the contract):

| Field                 | Type     | Purpose                                   |
| --------------------- | -------- | ----------------------------------------- |
| `version`             | string   | Schema version for backward compatibility |
| `generated_at`        | ISO 8601 | Staleness detection                       |
| `nlm_pipeline_status` | enum     | COMPLETED / PARTIAL / FAILED              |
| `key_findings`        | array    | Core intelligence output                  |
| `suggested_topics`    | array    | Editorial topic suggestions               |

**NICE-TO-HAVE fields** (scraper uses if present, ignores if absent):

| Field                       | Type   | Purpose                                |
| --------------------------- | ------ | -------------------------------------- |
| `hot_topics`                | array  | Multi-day signal tracking              |
| `open_questions`            | array  | Unresolved claims needing scraper help |
| `scraper_context`           | object | Yesterday's overlap analysis           |
| `cross_validation_requests` | array  | Specific claims needing confirmation   |
| `query_cluster`             | string | Which visa cluster was queried today   |

### 1.4 Staleness Detection

The scraper MUST check file age before using:

```python
import os, time, json
from pathlib import Path

HANDOFF_PATH = Path.home() / ".agent/decisions/nlm_to_scraper/latest.json"
MAX_AGE_HOURS = 24

def load_nlm_handoff() -> dict | None:
    """Load NLM handoff package. Returns None if missing or stale."""
    if not HANDOFF_PATH.exists():
        return None

    # Check file age via mtime
    file_age_hours = (time.time() - HANDOFF_PATH.stat().st_mtime) / 3600
    if file_age_hours > MAX_AGE_HOURS:
        return None  # Stale — treat as missing

    try:
        data = json.loads(HANDOFF_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Validate version (canonical field: schema_version, see §1.2 note)
    if data.get("schema_version", "0") < "1.0":
        return None

    # Check pipeline status
    if data.get("nlm_pipeline_status") == "FAILED":
        return None  # NLM failed — don't trust partial output

    return data
```

---

## 1b. Topic Relevance Score (DeepSeek R1 contribution — handoff filter)

Not all NLM findings belong in the handoff package. TRS determines which findings earn a slot.

### Formula

```
TRS = min(1.0,
    0.25 * F_confidence + 0.25 * F_novelty + 0.20 * F_client_impact
  + 0.15 * F_editorial_value + 0.15 * F_source_tier + min(0.10, BONUS_timely)
)
```

**Sub-scores:**

- `F_confidence` = claim.confidence_score (direct pass-through from Step 3)
- `F_novelty` = 1.0 - max_overlap_with_scraper_archive (Szymkiewicz-Simpson vs 30-day scraper articles)
- `F_client_impact` = min(1.0, affected_segments / 4) — segments = unique (visa_type, service) pairs
- `F_editorial_value` = 0.25 \* (has_deadline + has_cross_domain + affects_active_clients + has_actionable_rec)
- `F_source_tier` = max authority score from source chain (T0=1.00...T6=0.20)
- `BONUS_timely` = min(0.10, sum of urgency/enforcement/divergence bonuses)

### Thresholds

| TRS Range | Classification | Action                               |
| --------- | -------------- | ------------------------------------ |
| >= 0.65   | **HANDOFF**    | Include in `scraper_input.json`      |
| 0.45-0.64 | **CANDIDATE**  | Include only if <3 topics at HANDOFF |
| < 0.45    | **FILTERED**   | Not in handoff. Internal log only    |

**Max 5 topics per handoff** (scraper rate limit: 10 req/min). Top 5 by TRS. No more than 3 from same cluster (diversity guard).

---

## 1c. NLMEnricher Adapter (Codex contribution — minimal scraper invasion)

The scraper is a production system. Integration uses an adapter pattern: **1 new file** (`scripts/nlm_enricher.py`), **~18 lines** changed in existing code.

### Contract

```python
class NLMEnricher:
    """
    Contract:
    - enrich(articles) always returns list >= len(articles)
    - If handoff missing/stale/invalid: returns articles unchanged
    - Never raises exceptions — all errors logged and swallowed
    - Never modifies existing article fields — only adds nlm_* prefixed fields
    """
    def enrich(self, articles: list[dict]) -> list[dict]: ...
```

### Key design decisions

- **Triple error boundary**: `_load_handoff()` + `_apply_enrichment()` + `step_nlm_enrich()` — each wrapped in try/except, each returns gracefully
- **Only additive**: `nlm_cross_validated`, `nlm_confidence`, `nlm_context`, `nlm_score_boost` — never modifies `quality_score` or `title`
- **Score boost**: HIGH=+15, MEDIUM=+10, LOW=+5 to `quality_score`, capped at 100

### Schema evolution rules (Codex)

1. **Additive only**: new fields always OPTIONAL
2. **Reader tolerance**: scraper ignores unknown fields (`json.loads()` + access known keys only)
3. **Breaking change protocol**: if "2.0" ever needed, dual-write `latest.json` (v2) + `latest_v1.json` (v1 compat) for 30 days

Full adapter class: see `05b_scraper_integration_codex.md` §2.

---

## 2. Scraper Integration — Three Modes

### 2.1 Integration Mode Decision Tree

```
Scraper starts at 03:00
    │
    ├─ latest.json missing OR stale (>24h) OR pipeline FAILED?
    │   └─ MODE: IGNORE
    │      Scraper runs exactly as today. Zero NLM awareness.
    │
    ├─ latest.json present AND fresh AND pipeline COMPLETED?
    │   │
    │   ├─ Any key_finding with confidence >= 0.75?
    │   │   └─ MODE: PRIORITIZE
    │   │      NLM found verified intelligence. Scraper adjusts priority.
    │   │
    │   └─ All key_findings confidence < 0.75?
    │       └─ MODE: ENRICH
    │          NLM found signals but nothing verified. Scraper uses as context.
    │
    └─ latest.json present AND pipeline PARTIAL?
        └─ MODE: ENRICH (conservative — only use findings with confidence >= 0.55)
```

### 2.2 Mode: IGNORE (No NLM output)

**Scraper behavior:** Identical to current production. No code path changes.

**Components affected:** None.

**This is the default.** The scraper must be 100% functional in IGNORE mode at all times.

### 2.3 Mode: ENRICH (NLM output exists, low-medium confidence)

**What changes:**

1. **Step 1 (Scraping):** After `unified_scraper.scrape_all()`, inject NLM `suggested_search_queries` into the Exa augmentation step as additional search queries.

2. **Step 2.5 (Qwen Filter):** Append NLM context to the scoring prompt as a `CONTEXT:` prefix, so the LLM can boost relevance scores for articles touching NLM-identified topics.

3. **Step 2.7 (Verification):** For articles matching NLM `open_questions`, run targeted Exa search using the NLM-suggested queries (more precise than title-based search).

**What stays untouched:**

- Step 2 (Validation/dedup) — purely mechanical, no NLM input needed
- Step 2.8 (Clustering) — operates on embeddings, not editorial priority
- Step 3 (Enrichment) — Claude enricher doesn't need NLM context
- Steps 5-8 (SEO, approval, publishing, images) — downstream, format-agnostic

**Implementation sketch for Step 1:**

```python
# In step_scraping(), after Exa augmentation block:

nlm = load_nlm_handoff()
if nlm and nlm.get("key_findings"):
    nlm_queries = []
    for finding in nlm["key_findings"]:
        nlm_queries.extend(finding.get("suggested_search_queries", [])[:2])

    if nlm_queries and os.environ.get("EXA_API_KEY"):
        try:
            from exa_py import Exa
            exa = Exa(os.environ["EXA_API_KEY"])
            nlm_articles = []
            for query in nlm_queries[:6]:  # Max 6 NLM-seeded queries
                results = exa.search(
                    query=query,
                    num_results=5,
                    use_autoprompt=False,
                )
                for r in (results.results or []):
                    if r.url not in existing_urls:
                        nlm_articles.append({
                            "title": r.title or "",
                            "url": r.url,
                            "source_name": "NLM-seeded Exa",
                            "category": finding.get("category", "immigration"),
                            "nlm_finding_id": finding["finding_id"],
                            "nlm_confidence": finding["confidence_score"],
                        })
                        existing_urls.add(r.url)
            articles.extend(nlm_articles)
            self.log(f"NLM ENRICH: added {len(nlm_articles)} articles from {len(nlm_queries)} NLM queries")
        except Exception as e:
            self.log(f"NLM ENRICH failed (non-fatal): {e}", "WARN")
```

### 2.4 Mode: PRIORITIZE (NLM output exists, high confidence)

**Everything in ENRICH mode, plus:**

1. **Article selection priority:** In `_select_top_articles()` (Step 3), articles matching NLM `finding_ids` get a priority boost (+15 to quality_score) so they're more likely to be selected for Claude enrichment.

2. **Enrichment context injection:** When Claude enriches articles matching NLM findings, the NLM claim data is injected into the enrichment prompt as verified background:

```python
nlm_context = ""
if article.get("nlm_finding_id") and nlm:
    for finding in nlm.get("key_findings", []):
        if finding["finding_id"] == article["nlm_finding_id"]:
            nlm_context = (
                f"\n\nVERIFIED BACKGROUND (from NLM Deep Research, confidence {finding['confidence_score']:.0%}):\n"
                f"- {finding['headline']}\n"
                f"- Regulation refs: {', '.join(finding.get('regulation_refs', []))}\n"
                f"- Effective date: {finding.get('effective_date', 'unknown')}\n"
                f"Use this as verified context. Do not contradict unless the article explicitly provides newer information.\n"
            )
            break
```

3. **Publishing order:** Articles with NLM backing publish first (lower main_news_position numbers).

### 2.5 Component Modification Summary

| Scraper Component                  | IGNORE    | ENRICH                      | PRIORITIZE                    |
| ---------------------------------- | --------- | --------------------------- | ----------------------------- |
| `step_scraping` (UnifiedScraper)   | No change | No change                   | No change                     |
| `step_scraping` (Exa augmentation) | No change | +NLM queries                | +NLM queries                  |
| `step_validation`                  | No change | No change                   | No change                     |
| `step_qwen_filter`                 | No change | +NLM context in prompt      | +NLM context in prompt        |
| `step_verification`                | No change | +NLM open_questions queries | +NLM open_questions queries   |
| `step_clustering`                  | No change | No change                   | No change                     |
| `_select_top_articles`             | No change | No change                   | +Score boost for NLM matches  |
| `step_enrichment`                  | No change | No change                   | +NLM context in Claude prompt |
| `step_seo`                         | No change | No change                   | No change                     |
| `step_approval`                    | No change | No change                   | No change                     |
| `step_publishing`                  | No change | No change                   | +NLM articles publish first   |
| `step_images`                      | No change | No change                   | No change                     |

**Total files modified: 1** (`run_intel_pipeline.py`). New file: 0. New dependency: 0.

---

## 3. Cross-Validation Protocol

### 3.1 Problem Statement

Two systems independently analyze Indonesian regulatory news. Their findings will sometimes overlap, sometimes conflict, sometimes complement. We need a protocol that:

1. Boosts confidence when both agree
2. Creates new signals when one finds what the other missed
3. Prevents feedback loops (NLM citing scraper articles, scraper citing NLM brief)

### 3.2 Scenario Matrix

```
                        ┌─────────────────────────────────────────┐
                        │         SCRAPER FINDS IT?               │
                        │    YES (article exists)     NO          │
┌───────────────────────┼────────────────────────┬────────────────┤
│ NLM    YES (finding   │ CONVERGENCE            │ NLM-ONLY       │
│ FINDS  exists,        │ Confidence boost.      │ Monitor.       │
│ IT?    conf >= 0.55)  │ Cross-validated.       │ Lower if >48h. │
│        ────────────── │ ────────────────────── │ ──────────────│
│        NO             │ SCRAPER-ONLY           │ NOTHING        │
│                       │ New signal for NLM.    │ (no overlap)   │
│                       │ Flag for next run.     │                │
└───────────────────────┴────────────────────────┴────────────────┘
```

### 3.3 CONVERGENCE — Both systems find the same topic

**Detection:** After scraper Step 2.8 (clustering), check each dossier's primary article title against NLM `key_findings[].headline` using:

1. Exact `regulation_refs` match (deterministic, ~95% precision)
2. Entity+category match (same subject + same claim type, ~80% precision)
3. Jaccard word overlap >= 0.25 (fallback)

**Confidence Boost Formula (DeepSeek R1 — logarithmic with saturation):**

```
C_adjusted = C_nlm + B(n_eff) * (1 - C_nlm)

Where:
  B(n) = 0.30 * ln(1 + n) / ln(6)    # K=0.30, N_max=5
  n_eff = sum(w_i for article_i)       # source-quality-weighted confirmations

Source weights:
  Cites .go.id / official gazette  → w = 1.00
  Named-source journalism          → w = 0.70
  Unnamed/multiple-source          → w = 0.40
  Blog/forum                       → w = 0.20
```

| n_eff | B(n_eff) | C_nlm=0.63 → C_adj | C_nlm=0.72 → C_adj | C_nlm=0.85 → C_adj |
| ----- | -------- | ------------------ | ------------------ | ------------------ |
| 0.0   | 0.000    | 0.630              | 0.720              | 0.850              |
| 1.0   | 0.116    | 0.673              | 0.752              | 0.867              |
| 2.0   | 0.184    | 0.698              | 0.772              | 0.878              |
| 3.0   | 0.231    | 0.715              | 0.785              | 0.885              |
| 5.0+  | 0.300    | 0.741              | 0.804              | 0.895              |

**Key**: Claims at C_nlm >= 0.643 can reach VERIFIED (0.75) through boost alone with sufficient confirmations.
Claims below 0.643 (e.g., 0.63 maxes at 0.741) require direct T0-T2 source confirmation to graduate — journalistic corroboration alone is insufficient. This is by design: low-PROVISIONAL claims need authoritative sources, not more news articles. Hard cap: 0.95.

**Contradiction Penalty (DeepSeek R1):**

```
C_adjusted = C_nlm - min(0.40, 0.15 * m) * C_nlm
```

1 contradiction drops a PROVISIONAL (0.63) below threshold (→ 0.536). 3+ contradictions on a VERIFIED (0.85) → mandatory human review (0.510).

**Implementation:**

```python
import math

def cross_validate_convergence(nlm_conf: float, confirming_articles: list[dict]) -> dict:
    """Boost confidence using logarithmic formula with source-quality weighting."""
    TIER_WEIGHTS = {"T0": 1.0, "T1": 0.9, "T2": 0.8, "T3": 0.7, "T4": 0.6, "T5": 0.4, "T6": 0.2}
    n_eff = sum(TIER_WEIGHTS.get(a.get("tier", "T5"), 0.3) for a in confirming_articles)
    K, N_MAX = 0.30, 5
    b = K * math.log(1 + min(n_eff, N_MAX)) / math.log(1 + N_MAX)
    new_conf = min(0.95, nlm_conf + b * (1 - nlm_conf))
    return {
        "cross_validated": True,
        "original_confidence": nlm_conf,
        "boosted_confidence": round(new_conf, 3),
        "n_eff": round(n_eff, 2),
        "boost_factor": round(b, 3),
        "validation_type": "CONVERGENCE",
    }
```

**Effect on NLM next run:**

- Cross-validated claims get their `last_confirmed_valid` timestamp reset (staleness resets)
- If a PROVISIONAL claim (0.55-0.74) gets boosted above 0.75, it graduates to VERIFIED in next daily brief

**Convergence data written to:**

```
~/.agent/decisions/nlm_to_scraper/cross_validation/YYYY-MM-DD.json
```

### 3.4 NLM-ONLY — NLM found it, scraper didn't

**Detection:** NLM finding has no matching scraper article after Step 2.8.

**Action:**

- If finding is VERIFIED (>= 0.75): No change. NLM already has strong sources. The scraper simply didn't cover it today — acceptable.
- If finding is PROVISIONAL (0.55-0.74) and >48h old with no scraper confirmation: **Lower confidence by -0.05** per day. After 5 days: auto-demote to MONITORING.
- All NLM-ONLY findings are written to `open_questions` in the next handoff package, asking the scraper to look for confirmation tomorrow.

**Rationale:** If a regulatory change is real, the scraper (which monitors 609 sources) should eventually find coverage. Persistent NLM-ONLY findings suggest either: (a) NLM hallucinated, or (b) the news hasn't broken widely yet. Gradual confidence decay handles both.

### 3.5 SCRAPER-ONLY — Scraper found it, NLM didn't

**Detection:** Article has high quality_score (>= 60) and regulatory category, but no matching NLM finding.

**Action:**

- Article enriched and published normally by scraper (no degradation).
- After scraper completes, write a signal file for NLM's next morning run:

```
~/.agent/decisions/scraper_to_nlm/YYYY-MM-DD.json
```

```json
{
  "generated_at": "2026-03-28T03:25:00+08:00",
  "scraper_run_id": "20260328_030000",
  "novel_signals": [
    {
      "title": "Indonesia announces Golden Visa fee reduction",
      "url": "https://...",
      "category": "immigration",
      "quality_score": 78,
      "tier": "T2",
      "verification_status": "verified_t1",
      "suggested_nlm_query": "Golden Visa Indonesia fee reduction 2026 regulations",
      "regulation_refs_found": ["PP 20/2026"]
    }
  ],
  "scraper_stats": {
    "total_scraped": 45,
    "enriched": 12,
    "published": 8,
    "categories": { "immigration": 15, "tax": 12, "business": 18 }
  }
}
```

**NLM reads this at 01:05 next morning** (Phase 1: Signal collection), injecting novel signals as context for that day's query selection.

### 3.6 Feedback Loop Prevention

**The problem:** NLM cites a scraper-published article as a source → scraper publishes an article enriched by NLM findings → NLM next day sees that article and cites it as independent confirmation → circular amplification.

**The safeguard — Source Provenance Tagging:**

Every claim and article carries a `provenance` field tracking its origin:

```json
{
  "provenance": {
    "origin": "NLM_DEEP_RESEARCH",
    "pipeline_run_id": "nb2-2026-03-28-0100",
    "original_sources": ["jdih.kemenkumham.go.id", "hukumonline.com"]
  }
}
```

**Rules:**

| Rule                                                                     | Implementation                                                                                                     |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| NLM MUST NOT cite `balizero.com/intelligence/*` articles as sources      | NLM query templates exclude `balizero.com` domain                                                                  |
| Scraper MUST NOT count NLM-seeded articles as "independent confirmation" | Articles with `nlm_finding_id` field are tagged `source_type: nlm_seeded` and excluded from T1 verification counts |
| Cross-validation only counts INDEPENDENT discovery                       | An article counts as convergence ONLY if it was scraped from an external source (not NLM-seeded Exa query)         |
| NLM MUST NOT use `scraper_to_nlm/` signals as primary sources            | Signal file is used ONLY for query selection priority, never as evidence for claims                                |

**Implementation in NLM Deep Research query templates:**

```python
# In NLM research_start queries, always exclude own ecosystem
EXCLUDE_DOMAINS = [
    "balizero.com",
    "kita.balizero.com",
    "zantara.balizero.com",
]
```

**Implementation in scraper cross-validation:**

```python
def is_independent_article(article: dict) -> bool:
    """Article was scraped independently, not seeded by NLM."""
    return (
        not article.get("nlm_finding_id")
        and article.get("source_name") != "NLM-seeded Exa"
    )
```

### 3.7 Cross-Validation Sequence Diagram

```
         NLM (01:00-02:20)              Scraper (03:00-03:30)
              │                                │
    ┌─────────┴─────────┐                      │
    │ Read yesterday's   │                      │
    │ scraper_to_nlm/    │                      │
    │ for novel signals  │                      │
    └─────────┬─────────┘                      │
              │                                │
    ┌─────────┴─────────┐                      │
    │ Execute queries    │                      │
    │ (signal-aware)     │                      │
    └─────────┬─────────┘                      │
              │                                │
    ┌─────────┴─────────┐                      │
    │ Write handoff pkg  │──── latest.json ────▶│
    │ (02:10)            │                      │
    └─────────┬─────────┘                      │
              │                          ┌──────┴───────┐
              │                          │ Read latest   │
              │                          │ Determine mode│
              │                          └──────┬───────┘
              │                                 │
              │                          ┌──────┴───────┐
              │                          │ Scrape + NLM  │
              │                          │ enrichment    │
              │                          └──────┬───────┘
              │                                 │
              │                          ┌──────┴───────┐
              │                          │ Cross-validate│
              │                          │ vs NLM claims │
              │                          └──────┬───────┘
              │                                 │
              │                          ┌──────┴───────┐
              │         ◀── cross_validation/ ──│ Write results│
              │         ◀── scraper_to_nlm/  ──│              │
              │                          └──────┴───────┘
              │
    (Next morning 01:05)
    ┌─────────┴─────────┐
    │ Read cross_val +   │
    │ scraper_to_nlm     │
    │ Update confidence  │
    │ Adjust queries     │
    └────────────────────┘
```

---

## 4. War Room Topic Selection Flow

### 4.1 Current State

The War Room currently reads `intel_output_latest.json` directly and either:

- Uses manual `--topic` override, OR
- Runs `00_topic_selector.py` which calls Gemini + Google Trends to pick from scraper articles

### 4.2 NLM Integration Point

NLM provides a **second, higher-quality input** for topic selection. The War Room gains access to both:

1. `intel_output_latest.json` — scraper articles (existing)
2. `~/.agent/decisions/nlm_to_scraper/latest.json` — NLM intelligence brief (new)

**NLM `suggested_topics` are pre-scored and pre-angled.** They come with confidence levels, audience targeting, and editorial angles already written. This is strictly better input than raw article titles.

### 4.3 Modified Topic Selection Flow

```
War Room pipeline.sh starts
    │
    ├─ Manual --topic provided?
    │   └─ YES → Use manual topic (override everything)
    │
    ├─ NLM latest.json exists AND fresh (<8h)?
    │   │
    │   └─ YES → Read NLM suggested_topics
    │       │
    │       ├─ Any topic with priority=HIGH and confidence >= 0.75?
    │       │   └─ YES → Use NLM topic (strongest signal)
    │       │           Log: "Topic from NLM Deep Research (confidence X%)"
    │       │
    │       └─ NO → Fall through to existing Gemini selector
    │              But inject NLM topics as context for Gemini
    │
    └─ NLM not available
        └─ Existing flow: Gemini + Google Trends on scraper articles
```

### 4.4 Implementation in `pipeline.sh`

Insert after the Intel Scraper check block, before FASE 0:

```bash
# ── Check NLM Deep Research Brief ──────────────────────
NLM_LATEST="$HOME/.agent/decisions/nlm_to_scraper/latest.json"
NLM_TOPIC=""
NLM_AVAILABLE=false

if [[ -z "$TOPIC" && -f "$NLM_LATEST" ]]; then
  NLM_AGE=$(( $(date +%s) - $(stat -f %m "$NLM_LATEST" 2>/dev/null || echo 0) ))
  if (( NLM_AGE < 28800 )); then  # <8 hours
    NLM_AVAILABLE=true
    # Extract highest-priority topic with confidence >= 0.75
    NLM_TOPIC=$(python3 -c "
import json
d = json.load(open('$NLM_LATEST'))
topics = d.get('suggested_topics', [])
# Filter: HIGH priority + confidence >= 0.75
top = [t for t in topics if t.get('priority') == 'HIGH' and t.get('confidence', 0) >= 0.75]
if top:
    best = max(top, key=lambda t: t.get('confidence', 0))
    print(best['topic'])
" 2>/dev/null || echo "")

    if [[ -n "$NLM_TOPIC" ]]; then
      TOPIC="$NLM_TOPIC"
      NLM_ANGLE=$(python3 -c "
import json
d = json.load(open('$NLM_LATEST'))
for t in d.get('suggested_topics', []):
    if t.get('topic') == '''$NLM_TOPIC''':
        print(t.get('angle', ''))
        break
" 2>/dev/null || echo "")
      NLM_CONF=$(python3 -c "
import json
d = json.load(open('$NLM_LATEST'))
for t in d.get('suggested_topics', []):
    if t.get('topic') == '''$NLM_TOPIC''':
        print(f'{t.get(\"confidence\", 0):.0%}')
        break
" 2>/dev/null || echo "?")
      log "🧠 NLM Deep Research topic selected (confidence: $NLM_CONF)"
      log "   Topic: $TOPIC"
      [[ -n "$NLM_ANGLE" ]] && log "   Angle: $NLM_ANGLE"
    else
      log "ℹ️  NLM brief available but no HIGH-confidence topic — deferring to Gemini selector"
    fi
  else
    log "⏰ NLM brief stale (${NLM_AGE}s) — ignoring"
  fi
fi
```

### 4.5 NLM Context Injection into Topic Selector

When NLM is available but didn't produce a HIGH-confidence topic, inject NLM findings as context for the existing Gemini-based topic selector.

Modify `00_topic_selector.py` to accept an optional `--nlm-brief` argument:

```python
parser.add_argument("--nlm-brief", default="", help="Path to NLM handoff package (optional)")
```

In the prompt construction, append NLM findings:

```python
if args.nlm_brief and Path(args.nlm_brief).exists():
    nlm = json.loads(Path(args.nlm_brief).read_text())
    nlm_findings = []
    for f in nlm.get("key_findings", [])[:5]:
        nlm_findings.append(
            f"- [{f['confidence_class']}] {f['headline']} "
            f"(refs: {', '.join(f.get('regulation_refs', []))})"
        )
    if nlm_findings:
        prompt += (
            f"\n\nADDITIONAL CONTEXT — NLM Deep Research verified findings:\n"
            + "\n".join(nlm_findings)
            + "\n\nThese are pre-verified by automated research. "
            "Give them priority if they have a strong audience angle."
        )
```

### 4.6 Telegram Notification Format

When the scraper publishes articles with NLM backing, and when the War Room selects an NLM-sourced topic, the Telegram notification should indicate the intelligence source:

**Daily Intelligence Brief (NLM pipeline at 02:15):**

```
🧠 NLM Intelligence Brief — 2026-03-28

📊 Cluster: Work Permits (A)
📋 Queries: 2 (L1 monitoring + L2 comparative)

🔴 VERIFIED (1):
• Permenkumham 8/2026 expands KITAS sponsor categories
  Confidence: 82% | Effective: April 15
  Refs: Art. 47, Art. 48

🟡 PROVISIONAL (2):
• Existing sponsors must re-register within 90 days (72%)
• Ngurah Rai processing delays enter third week (65%)

💡 Suggested Topics:
1. KITAS Sponsor Expansion [HIGH, 82%]
2. Ngurah Rai ITAS Bottleneck [MEDIUM, 65%]

❓ Open Questions: 1
📎 Full brief: ~/.agent/decisions/nlm_briefs/2026-03-28.json
```

**War Room topic selection notification:**

```
🚨 WAR ROOM — Topic Selected

📌 Topic: KITAS Sponsor Expansion: What Companies Need to Do Before April 15
🧠 Source: NLM Deep Research (confidence: 82%)
📐 Angle: Compliance gap — new categories open opportunity but re-registration deadline creates urgency
```

### 4.7 Manual Override

The War Room operator can ALWAYS override NLM:

```bash
# Override with manual topic — NLM suggestion ignored
./pipeline.sh "Coretax 2025 Deadline"

# Use NLM topic automatically
./pipeline.sh  # No topic → reads NLM → falls back to Gemini

# Force Gemini selector even when NLM is available
NLM_SKIP=1 ./pipeline.sh
```

---

## 5. Failure Modes

### 5.1 NLM Fails, Scraper Runs

**Symptoms:** `latest.json` missing or `nlm_pipeline_status: FAILED`

**Impact:** Zero. Scraper operates in IGNORE mode (current behavior).

**Recovery:** NLM pipeline has its own crash recovery (Step 2: state machine with 7 states). If it fails, it retries the next morning. The scraper never waits, never retries, never degrades.

### 5.2 Scraper Fails, NLM Ran Successfully

**Symptoms:** `scraper_to_nlm/` file not written. No `intel_output_latest.json` update.

**Impact on NLM:** Minimal. NLM reads yesterday's scraper output at 01:05 for context. If the scraper failed, the NLM will work with stale (but not missing) context. The next morning's NLM run will see `yesterday_scraper_overlap: null` and proceed without it.

**Impact on War Room:** War Room checks Intel age. If `intel_output_latest.json` is >8h old, it falls through to manual topic or uses NLM topic directly. The War Room already handles missing scraper output.

### 5.3 Both Fail

**Impact:** War Room has no fresh intel AND no NLM brief. Pipeline.sh requires either a topic or fresh intel:

```bash
[[ -z "$TOPIC" ]] && die "Nessun topic. Passa ./pipeline.sh 'topic' ..."
```

**Recovery:** Operator must provide manual topic. This is the existing behavior — no regression.

### 5.4 Stale Handoff Package (>24h)

**Detection:** `load_nlm_handoff()` returns `None` (file age check).

**Action:** IGNORE mode. Logged as:

```
[INFO] NLM handoff stale (26.3h) — running in IGNORE mode
```

**Edge case — weekend:** NLM pipeline is OFF on weekends (Step 2: "Weekend OFF — Indonesian gazette Mon-Fri only"). Friday's handoff will be >24h stale by Monday 03:00. This is correct behavior — Friday's findings are likely outdated by Monday.

### 5.5 Partial NLM Pipeline

**Detection:** `nlm_pipeline_status: PARTIAL` (e.g., only L1 completed, L2 timed out).

**Action:** ENRICH mode with conservative filter — only use findings with `confidence_score >= 0.55`.

### 5.6 Corrupted Handoff File

**Detection:** `json.JSONDecodeError` in `load_nlm_handoff()`.

**Action:** Return `None` → IGNORE mode. Log error for investigation.

### 5.7 Schema Version Mismatch

**Detection:** `version` field doesn't match expected pattern.

**Action:**

- Minor version difference (e.g., `1.1.0` vs `1.0.0`): Proceed, but only use fields that exist in the data.
- Major version difference (e.g., `2.0.0` vs `1.0.0`): IGNORE mode. Log warning. This means the NLM pipeline was upgraded without updating the scraper reader.

---

## 6. Metrics & Observability

### 6.1 Attribution Tracking

Every article published by the scraper carries an `nlm_attribution` field:

```json
{
  "nlm_attribution": {
    "mode": "PRIORITIZE",
    "nlm_finding_ids": ["NB2-2026-03-28-F001"],
    "nlm_confidence_at_time": 0.82,
    "nlm_contributed": "search_seed",
    "cross_validated": true,
    "boost_applied": 0.12
  }
}
```

If `nlm_attribution` is `null`, the article was produced entirely independently.

### 6.2 Daily Metrics (appended to scraper pipeline state)

```json
{
  "nlm_integration_metrics": {
    "date": "2026-03-28",
    "mode": "PRIORITIZE",
    "handoff_age_hours": 0.8,
    "nlm_findings_count": 3,
    "nlm_topics_suggested": 2,

    "scraper_articles_total": 45,
    "scraper_articles_nlm_seeded": 6,
    "scraper_articles_nlm_matched": 3,
    "scraper_articles_independent": 36,

    "convergence_count": 2,
    "nlm_only_count": 1,
    "scraper_only_count": 8,

    "confidence_boosts_applied": 2,
    "avg_boost_magnitude": 0.105,

    "war_room_topic_source": "NLM",
    "war_room_nlm_confidence": 0.82
  }
}
```

### 6.3 Weekly Integration Health Report

Generated every Sunday by scraper (or by a separate cron), aggregating 7 days of `nlm_integration_metrics`:

```
📊 NLM-Scraper Integration — Week of 2026-03-24

Pipeline Runs:
  NLM completed: 5/5 (Mon-Fri)
  Scraper completed: 5/5
  Both failed same day: 0

Integration Modes:
  PRIORITIZE: 3 days (Mon, Wed, Thu)
  ENRICH: 1 day (Tue — no VERIFIED findings)
  IGNORE: 1 day (Fri — NLM partial failure)

Cross-Validation:
  CONVERGENCE events: 7 (avg boost +0.11)
  NLM-ONLY persisting >48h: 1 (demoted to MONITORING)
  SCRAPER-ONLY novel signals: 12

Confidence Impact:
  Claims promoted PROVISIONAL → VERIFIED via scraper: 3
  Claims demoted via timeout: 1

War Room Adoption:
  NLM topic used directly: 2/5 days
  NLM topic influenced Gemini selection: 1/5 days
  Manual override: 2/5 days
  NLM adoption rate: 60%

Published Articles:
  With NLM attribution: 8/34 (24%)
  NLM-seeded that made it to publication: 4/18 (22%)
  Average quality_score NLM-seeded: 72
  Average quality_score independent: 58
```

### 6.4 Metric Collection Points

| Metric                                   | Collection Point                             | How                                                  |
| ---------------------------------------- | -------------------------------------------- | ---------------------------------------------------- |
| NLM-sourced topics in published articles | `step_publishing`                            | Count articles with `nlm_attribution != null`        |
| Scraper validation rate of NLM claims    | Cross-validation step (new, post-clustering) | Count CONVERGENCE vs NLM-ONLY                        |
| War Room adoption rate                   | `pipeline.sh`                                | Log whether topic came from NLM or Gemini            |
| NLM handoff staleness                    | `load_nlm_handoff()`                         | Log file age on every run                            |
| Integration mode distribution            | Start of scraper run                         | Log which mode was selected                          |
| Confidence boost effectiveness           | Weekly rollup                                | Compare pre-boost vs post-boost for graduated claims |

### 6.5 Integration Value Added (DeepSeek R1 contribution)

```
IVA = exclusive_topics_from_smaller_system / larger_system_total

IF |T_SCRAPER| >= |T_NLM|: IVA = |NLM_EXCL| / |T_SCRAPER|
IF |T_NLM| > |T_SCRAPER|:  IVA = |SCRAPER_EXCL| / |T_NLM|
```

**Expected cross-validation ratios (steady state, Month 6):**

| Metric            | Target    | Alarm Low                     | Alarm High       |
| ----------------- | --------- | ----------------------------- | ---------------- |
| OVERLAP           | 25-40%    | <10% (disconnected)           | >50% (redundant) |
| NLM_EXCLUSIVE     | 25-40%    | <15% (no added value)         | >60% (too niche) |
| SCRAPER_EXCLUSIVE | 25-40%    | <15% (scraper weak)           | —                |
| IVA               | 0.35-0.55 | <0.10 for 3 weeks (redundant) | —                |

### 6.6 Integration KPIs (DeepSeek R1 contribution)

| KPI                                               | Month 1 Target | Month 6 Target | Cadence |
| ------------------------------------------------- | -------------- | -------------- | ------- |
| NLM→article conversion rate                       | 10-20%         | 15-25%         | Weekly  |
| Cross-val confirmation rate                       | 15-25%         | 25-40%         | Weekly  |
| Handoff freshness (avg age hours)                 | <2h            | <1.5h          | Daily   |
| War Room NLM adoption                             | 10-20%         | 25-35%         | Weekly  |
| False positive rate (NLM topics no one publishes) | <40%           | <25%           | Weekly  |
| IVA (integration value added)                     | 0.15-0.25      | 0.35-0.55      | Weekly  |
| Pipeline reliability (both systems ran)           | >90%           | >95%           | Weekly  |
| E2E yield (NLM claims → published articles)       | 4-13%          | 8-18%          | Monthly |

### 6.7 Alert Thresholds

| Condition                                                         | Alert Level | Channel            |
| ----------------------------------------------------------------- | ----------- | ------------------ |
| NLM handoff missing 3+ consecutive days                           | WARNING     | Telegram           |
| Cross-validation rate = 0% for 5+ days                            | WARNING     | Telegram           |
| CONVERGENCE events = 0 for 7 days                                 | INFO        | Weekly report only |
| NLM-ONLY claims persisting >5 days without resolution             | WARNING     | Telegram           |
| Scraper consistently ignoring NLM topics (adoption <10% over 14d) | INFO        | Weekly report      |
| Feedback loop detected (article cites balizero.com)               | CRITICAL    | Telegram + log     |

---

## 7. File System Layout (Complete)

```
~/.agent/decisions/
├── nlm_briefs/                        # NLM daily intelligence briefs
│   ├── 2026-03-28.json
│   └── ...
├── nlm_to_scraper/                    # NLM → Scraper handoff
│   ├── 2026-03-28.json                # Dated files
│   ├── latest.json → 2026-03-28.json  # Symlink
│   ├── _metadata.json                 # Rolling index
│   └── cross_validation/              # Scraper → NLM cross-val results
│       └── 2026-03-28.json
├── scraper_to_nlm/                    # Scraper → NLM novel signals
│   └── 2026-03-28.json
└── war_room/                          # War Room topic history
    └── topic_history.jsonl            # Append-only log of topic selections

apps/bali-intel-scraper/
├── data/
│   ├── intel_output_latest.json       # Existing: scraper output for War Room
│   └── pipeline/                      # Existing: per-run state files
└── scripts/
    └── run_intel_pipeline.py          # Modified: +NLM integration (1 file)

apps/war-room/
├── pipeline.sh                        # Modified: +NLM topic selection block
└── agents/
    └── 00_topic_selector.py           # Modified: +--nlm-brief argument
```

---

## 8. Implementation Order

### Phase 1: Foundation (Day 1)

1. Create directory structure: `~/.agent/decisions/nlm_to_scraper/`, `scraper_to_nlm/`
2. Implement `load_nlm_handoff()` utility in scraper
3. Add IGNORE/ENRICH/PRIORITIZE mode selection logic at scraper start
4. Write handoff package from NLM pipeline (Phase 6 in Step 2 timing)

### Phase 2: Scraper Integration (Day 2)

5. Modify `step_scraping()` — NLM-seeded Exa queries
6. Modify `step_qwen_filter()` — NLM context in scoring prompt
7. Add cross-validation step after clustering
8. Write `scraper_to_nlm/` signals after pipeline completion

### Phase 3: War Room Integration (Day 3)

9. Modify `pipeline.sh` — NLM topic selection block
10. Modify `00_topic_selector.py` — `--nlm-brief` argument
11. Add NLM attribution to published articles

### Phase 4: Observability (Day 4)

12. Add `nlm_integration_metrics` to pipeline state
13. Implement weekly health report generation
14. Set up Telegram alerts for integration anomalies

### Phase 5: Testing (Day 5)

15. Dry run with synthetic handoff package (all modes)
16. Verify IGNORE mode = zero behavioral change
17. Verify feedback loop prevention (balizero.com exclusion)
18. End-to-end: NLM writes → scraper reads → War Room picks topic

---

## 9. Testing Strategy (Codex contribution)

### Regression Test (CRITICAL)

The scraper MUST produce identical output with and without the handoff file for all non-NLM fields:

```python
def test_scraper_independence():
    """Scraper output is identical with empty vs missing handoff."""
    result_without = run_scraper(handoff=None)
    result_with_empty = run_scraper(handoff={"findings": [], "suggested_topics": []})
    # All non-nlm_* fields must be identical
    for article in result_without:
        matching = find_by_url(result_with_empty, article["url"])
        for key in article:
            if not key.startswith("nlm_"):
                assert article[key] == matching[key]
```

### Key test cases (15 total — see `05b_scraper_integration_codex.md` §6 for full suite)

| Test                           | What it verifies                               |
| ------------------------------ | ---------------------------------------------- |
| `test_no_handoff_file`         | IGNORE mode, scraper unchanged                 |
| `test_stale_handoff`           | >26h file rejected, IGNORE mode                |
| `test_corrupted_json`          | Graceful fallback, no crash                    |
| `test_enrichment_additive`     | NLM fields added, existing untouched           |
| `test_score_boost_cap`         | quality_score never exceeds 100                |
| `test_feedback_loop_detection` | balizero.com articles blocked from NLM sources |
| `test_article_independence`    | Regression: non-NLM fields identical           |

### Feedback Loop Detection (Codex)

```python
def detect_feedback_loop(nlm_sources: list, scraper_articles: list) -> float:
    """Detect if NLM is citing scraper articles or vice versa.
    Returns loop_score: 0.0 = clean, >0.50 = alarm."""
    nlm_urls = {s["url"] for s in nlm_sources}
    scraper_urls = {a["url"] for a in scraper_articles}
    bz_urls = {u for u in nlm_urls if "balizero.com" in u}
    overlap = nlm_urls & scraper_urls  # should be empty
    loop_score = (len(bz_urls) + len(overlap)) / max(1, len(nlm_urls))
    return loop_score  # >= 0.50 triggers Telegram alert
```

---

## 10. Design Decisions & Rationale

### Why file-based handoff instead of API/database?

1. **Decoupling:** File I/O has zero coupling. No shared database, no network dependency.
2. **Debuggability:** `cat latest.json` instantly shows what NLM produced. No query needed.
3. **Resilience:** If NLM crashes, the file simply doesn't appear. Scraper defaults to IGNORE. No error handling needed for missing API endpoints.
4. **Atomic writes:** Write to temp file → rename. No partial reads possible.
5. **Audit trail:** Dated files persist for 30 days. Complete history of what NLM told the scraper.

### Why not make the scraper wait for NLM?

The scraper has been running independently at 03:00 for months. Introducing a dependency would:

- Add a failure mode (NLM slow → scraper delayed → articles late → War Room has stale intel)
- Require timeout/retry logic in the scraper
- Make the scraper's behavior unpredictable (sometimes 03:00, sometimes 03:30)

The 40-minute buffer (02:20 → 03:00) is sufficient. If NLM is still running at 03:00, the scraper reads yesterday's file (or nothing) and proceeds.

### Why confidence thresholds in the scraper rather than in NLM?

NLM already applies thresholds (>= 0.75 VERIFIED, 0.55-0.74 PROVISIONAL). But the scraper applies its own thresholds because:

- The scraper may trust NLM less initially (calibration period)
- Different consumers may want different thresholds (War Room wants HIGH+0.75, scraper might use 0.55 for ENRICH mode)
- Thresholds can be tuned per-consumer without changing NLM output format

### Why cross-validation confidence cap at 0.95?

No automated system should reach 1.0 confidence. The 0.05 gap reserves space for human judgment and prevents over-trust in automated pipelines.

---

## Source AI Contributions

### Gemini (Il Consigliere) — Architecture + Integration Flows

- System context diagram with 3 independent systems
- Handoff package JSON schema with full field definitions
- 3-mode decision tree (IGNORE/ENRICH/PRIORITIZE) with component modification matrix
- Cross-validation scenario matrix with sequence diagram
- War Room topic selection flow with pipeline.sh bash integration
- 7 failure modes with graceful degradation analysis
- File system layout for complete `~/.agent/decisions/` tree
- 5-phase implementation plan

### Codex GPT-5.4 (Il Soldato) — Contracts + Discipline

- `NLMEnricher` adapter class with triple error boundary (~200 lines, 1 new file)
- Strict JSON schema with typed fields, validation function, enum definitions
- Schema evolution rules (additive only, reader tolerance, 30-day dual-write)
- Atomic file write protocol (tmp + os.replace on POSIX)
- Feedback loop detection function with loop_score metric
- 15 unit tests across 4 test classes
- 12-step deployment checklist with rollback plans
- Source provenance tagging for loop prevention

### DeepSeek R1 (Il Pensatore) — Formulas + KPIs

- Topic Relevance Score (TRS): 5-factor weighted formula with timeliness bonus
- Logarithmic confidence boost: B(n) = 0.30 \* ln(1+n)/ln(6) with source-quality-weighted n_eff
- Contradiction penalty: P(m) = min(0.40, 0.15\*m) proportional to current confidence
- Integration Value Added (IVA) = exclusive topics / larger system total
- Cross-validation expected ratios (OVERLAP/NLM_EXCL/SCRAPER_EXCL targets by month)
- 8 primary + 6 secondary KPIs with monthly targets
- Information flow budget with funnel conversion rates
- ROI calculation: break-even at ~$120/mo cost vs ~$350/mo value

### Claude Opus 4.6 (Architect) — This Synthesis

- Merged 3 perspectives into unified spec preserving all critical contributions
- Integrated TRS formula into handoff package selection logic
- Replaced simple linear boost with DeepSeek's logarithmic formula
- Added NLMEnricher contract and schema evolution rules from Codex
- Created testing strategy section with regression test and loop detection
- Added IVA metric and KPI table from DeepSeek into observability section
