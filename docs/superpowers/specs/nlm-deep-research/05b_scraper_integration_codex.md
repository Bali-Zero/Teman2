# Step 5b: Intel Scraper Integration — Codex Perspective (Contracts + Discipline + Edge Cases)

> Agent: Codex perspective (strict schemas, interface contracts, error boundaries, testing)
> Date: 2026-03-28
> Complements: `05_scraper_integration.md` (Gemini — architecture + integration flows)
> Status: Brainstorm complete

---

## 0. Architecture Invariant (Repeat for Clarity)

```
NLM Pipeline (01:00-02:20 WITA)
  |
  v writes handoff package
~/.agent/decisions/nlm_to_scraper/latest.json    <-- atomic write (tmp + rename)
  |
  |  (40-minute gap -- no coupling)
  |
Intel Scraper (03:00 WITA)                        <-- reads handoff IF present
  |                                                  falls back gracefully if absent
  v
POST /api/intel/scraper/submit                    <-- publishes to Fly.io backend
  |
  v
War Room (manual)                                  <-- reads NLM brief (NOT scraper output)
  reads ~/.agent/decisions/nlm_briefs/YYYY-MM-DD.json
```

**Invariants (NEVER violate):**

1. Scraper runs identically with or without handoff file
2. NLM never depends on scraper output for its queries
3. Neither system cites the other as a source
4. War Room reads NLM brief directly, not via scraper

---

## 1. Handoff Contract (Strict Schema)

### 1.1 File Location and Atomicity

```
Path:     ~/.agent/decisions/nlm_to_scraper/latest.json
Temp:     ~/.agent/decisions/nlm_to_scraper/.latest.json.tmp
Archive:  ~/.agent/decisions/nlm_to_scraper/archive/YYYY-MM-DD.json
```

**Write protocol (NLM side):**

```python
import json, os, shutil
from pathlib import Path
from datetime import datetime, timezone

HANDOFF_DIR = Path.home() / ".agent" / "decisions" / "nlm_to_scraper"
HANDOFF_FILE = HANDOFF_DIR / "latest.json"
ARCHIVE_DIR = HANDOFF_DIR / "archive"

def write_handoff(package: dict) -> None:
    """Atomic write: tmp file -> rename. No partial reads possible."""
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Validate before write
    _validate_handoff_schema(package)

    tmp = HANDOFF_DIR / ".latest.json.tmp"
    tmp.write_text(json.dumps(package, indent=2, ensure_ascii=False))
    os.replace(str(tmp), str(HANDOFF_FILE))  # atomic on POSIX

    # Archive with date
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    shutil.copy2(str(HANDOFF_FILE), str(ARCHIVE_DIR / f"{date_str}.json"))
```

**Read protocol (scraper side):**

```python
def read_handoff() -> dict | None:
    """Read handoff file. Return None if missing, stale, or invalid."""
    if not HANDOFF_FILE.exists():
        return None

    try:
        package = json.loads(HANDOFF_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Schema version check
    if package.get("schema_version") != "1.0":
        return None

    # Freshness check: reject if > 26 hours old
    generated_at = package.get("generated_at", "")
    try:
        gen_dt = datetime.fromisoformat(generated_at)
        if gen_dt.tzinfo is None:
            gen_dt = gen_dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - gen_dt).total_seconds() / 3600
        if age_hours > 26:
            return None  # stale -- NLM may not have run last night
    except (ValueError, TypeError):
        return None  # unparseable timestamp

    return package
```

### 1.2 Handoff JSON Schema (v1.0)

Every field is typed. Required fields fail validation if missing.

```jsonc
{
  // --- Envelope ---
  "schema_version": "1.0", // string, REQUIRED. Semver for evolution.
  "generated_at": "2026-03-28T02:15:00+08:00", // string, REQUIRED. ISO 8601 with timezone.
  "pipeline_run_id": "nb2_20260328_0100", // string, REQUIRED. Traceable to NLM run.
  "notebook_id": "nb2_immigration", // string, REQUIRED. Which NLM notebook.
  "query_cluster": "A", // string, REQUIRED. Which cluster ran today.

  // --- Verified Findings ---
  "findings": [
    // array, REQUIRED (can be empty [])
    {
      "claim_id": "CLM-20260328-001", // string, REQUIRED. Unique, traceable.
      "claim_text": "Permenkumham 8/2026 expands KITAS sponsor categories to include cooperatives",
      // string, REQUIRED. Atomic claim, max 300 chars.
      "confidence": 0.87, // number, REQUIRED. 0.00-1.00.
      "confidence_label": "VERIFIED", // enum, REQUIRED. VERIFIED | PROVISIONAL.
      "category": "LEGAL_CHANGE", // enum, REQUIRED. See 1.3.
      "tier_highest": "T0", // enum, REQUIRED. Highest source tier backing this.
      "geographic_scope": "NATIONAL", // enum, REQUIRED. NATIONAL | BALI | LOCAL_OFFICE.
      "affected_visa_types": ["KITAS_SPONSOR", "KITAS_KERJA"],
      // string[], OPTIONAL. Empty if not visa-specific.
      "effective_date": "2026-04-15", // string|null, OPTIONAL. ISO date if known.
      "regulation_ref": "Permenkumham 8/2026", // string|null, OPTIONAL.
      "source_chain": [
        // array, REQUIRED (min 1 entry).
        {
          "tier": "T0", // string, REQUIRED.
          "name": "JDIH Kemenkumham gazette", // string, REQUIRED.
          "url": "https://jdih.kemenkumham.go.id/...", // string, REQUIRED.
          "date": "2026-03-25", // string, REQUIRED. ISO date.
        },
      ],
      "enforcement_divergence": false, // boolean, REQUIRED.
      "tags": ["sponsor", "kitas", "cooperative"], // string[], OPTIONAL.
    },
  ],

  // --- Suggested Topics for Scraper ---
  "suggested_topics": [
    // array, REQUIRED (can be empty [])
    {
      "topic": "KITAS sponsor expansion -- cooperative eligibility",
      // string, REQUIRED. Human-readable topic.
      "search_queries": [
        // string[], REQUIRED (1-3 queries).
        "KITAS cooperative sponsor 2026",
        "Permenkumham 8 2026 sponsor",
      ],
      "priority": "HIGH", // enum, REQUIRED. HIGH | MEDIUM | LOW.
      "rationale": "New regulation with 15-day effective window.",
      // string, REQUIRED.
      "linked_claims": ["CLM-20260328-001"], // string[], REQUIRED. Which findings drive this.
    },
  ],

  // --- Active Signals (from NLM Operations Status master doc) ---
  "active_signals": [
    // array, OPTIONAL
    {
      "signal_type": "PROCESSING_DELAY", // enum. See 1.4.
      "location": "Ngurah Rai", // string.
      "description": "KITAS extension 15 days vs normal 5-7",
      "since": "2026-03-20", // string. ISO date.
      "confidence": 0.63,
      "confidence_label": "PROVISIONAL",
    },
  ],

  // --- Scraper Guidance (NEVER a dependency -- only enrichment hints) ---
  "scraper_hints": {
    // object, OPTIONAL (entire block)
    "avoid_urls": [
      // string[]. URLs NLM already ingested.
      "https://jdih.kemenkumham.go.id/xxx",
    ],
    "priority_domains": [
      // string[]. Domains NLM found valuable today.
      "hukumonline.com",
      "imigrasi.go.id",
    ],
    "suppress_categories": [], // string[]. Categories NLM found exhausted today.
  },

  // --- NLM Health (for monitoring, not logic) ---
  "nlm_health": {
    "notebook_source_count": 58, // int.
    "nhs_score": 0.72, // float. Notebook Health Score from Step 4.
    "queries_run_today": 2, // int.
    "errors": 0, // int.
  },
}
```

### 1.3 Claim Categories (enum)

```
LEGAL_CHANGE          -- New/amended law, PP, Perpres, Permen
OPERATIONAL_CHANGE    -- Portal update, form change, process change
PROCEDURAL_UPDATE     -- New requirement, document change, step change
FEE_CHANGE            -- Cost change for any visa/permit/service
DEADLINE              -- New or changed deadline
ENFORCEMENT_ACTION    -- Raid, sweep, crackdown, inspection campaign
PROCESSING_TIME       -- Change in processing speed at any office
LOCAL_REGULATION      -- Perda, Pergub, Perbup (Bali-specific)
PORTAL_STATUS         -- Portal up/down/degraded
ADVISORY              -- Travel advisory, safety notice, general warning
```

### 1.4 Signal Types (enum)

```
PROCESSING_DELAY      -- Slower than normal at a specific office
ENFORCEMENT_CAMPAIGN  -- Active raid/sweep operation
PORTAL_DEGRADED       -- Government portal partially working
REGULATION_PENDING    -- Upcoming regulation with known effective date
FEE_INCREASE_RUMOR    -- Unconfirmed fee change signal
OFFICE_CLOSURE        -- Temporary office closure
```

### 1.5 Schema Evolution Rules

1. **Additive only**: New fields are always OPTIONAL. Existing fields never change type.
2. **Version bump**: `schema_version` increments to "1.1", "1.2", etc. for additive changes. "2.0" for breaking changes.
3. **Reader tolerance**: Scraper MUST ignore unknown fields (forward compatibility). `json.loads()` + access only known keys.
4. **Writer discipline**: NLM MUST NOT remove fields between versions. Deprecated fields: set to `null`, never delete.
5. **Breaking change protocol**: If "2.0" is ever needed, NLM writes BOTH `latest.json` (v2) AND `latest_v1.json` (v1 compat) for 30 days.

### 1.6 Validation Function

```python
def _validate_handoff_schema(package: dict) -> None:
    """Validate handoff package before write. Raises ValueError on failure."""
    required_envelope = ["schema_version", "generated_at", "pipeline_run_id", "notebook_id", "query_cluster"]
    for field in required_envelope:
        if field not in package:
            raise ValueError(f"Missing required envelope field: {field}")

    if not isinstance(package.get("findings"), list):
        raise ValueError("findings must be a list")
    if not isinstance(package.get("suggested_topics"), list):
        raise ValueError("suggested_topics must be a list")

    # Validate each finding
    required_finding = ["claim_id", "claim_text", "confidence", "confidence_label",
                        "category", "tier_highest", "geographic_scope", "enforcement_divergence",
                        "source_chain"]
    for i, f in enumerate(package["findings"]):
        for field in required_finding:
            if field not in f:
                raise ValueError(f"Finding {i} missing required field: {field}")
        if not 0.0 <= f["confidence"] <= 1.0:
            raise ValueError(f"Finding {i} confidence {f['confidence']} out of range [0,1]")
        if f["confidence_label"] not in ("VERIFIED", "PROVISIONAL"):
            raise ValueError(f"Finding {i} invalid confidence_label: {f['confidence_label']}")

    # Validate each topic
    required_topic = ["topic", "search_queries", "priority", "rationale", "linked_claims"]
    for i, t in enumerate(package["suggested_topics"]):
        for field in required_topic:
            if field not in t:
                raise ValueError(f"Topic {i} missing required field: {field}")
        if t["priority"] not in ("HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"Topic {i} invalid priority: {t['priority']}")
```

---

## 2. Scraper Modification Scope (Minimal Invasive)

### 2.1 Design Principle: Adapter Pattern

The scraper is a production system running nightly at 03:00 WITA. The integration must be:

- **Zero changes to existing scraper logic** (scraping, validation, Qwen filter, enrichment, SEO, approval, publishing)
- **One new file**: `scripts/nlm_enricher.py`
- **One insertion point**: between step `1_scraping` and step `2_validation` in `run_intel_pipeline.py`
- **Total diff in existing code**: ~18 lines

### 2.2 NLMEnricher Adapter Class

```python
#!/usr/bin/env python3
"""
NLM Enricher -- Optional adapter that augments scraper topics with NLM intelligence.

This module reads the NLM handoff package (if present) and enriches the scraper's
article list with priority signals and cross-validation context. It NEVER replaces
the scraper's own topic discovery -- only augments.

Interface:
    enricher = NLMEnricher()
    articles = enricher.enrich(articles)  # returns augmented list, never shorter
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HANDOFF_DIR = Path.home() / ".agent" / "decisions" / "nlm_to_scraper"
HANDOFF_FILE = HANDOFF_DIR / "latest.json"
FRESHNESS_HOURS = 26  # reject handoff older than this
SCHEMA_VERSION = "1.0"


class NLMEnricher:
    """Adapter that optionally loads NLM intelligence for scraper enrichment.

    Contract:
        - enrich(articles) always returns a list >= len(articles)
        - If handoff missing/stale/invalid: returns articles unchanged
        - Never raises exceptions -- all errors are logged and swallowed
        - Never modifies existing article fields -- only adds nlm_* prefixed fields
    """

    def __init__(self) -> None:
        self.handoff: dict[str, Any] | None = None
        self.stats: dict[str, int | str] = {
            "handoff_loaded": 0,
            "findings_count": 0,
            "topics_count": 0,
            "articles_enriched": 0,
            "articles_boosted": 0,
            "skip_reason": "",
        }

    def _load_handoff(self) -> dict[str, Any] | None:
        """Load and validate handoff file. Return None on any failure."""
        if not HANDOFF_FILE.exists():
            self.stats["skip_reason"] = "file_missing"
            logger.info("NLM handoff not found -- running without NLM enrichment")
            return None

        try:
            package = json.loads(HANDOFF_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            self.stats["skip_reason"] = f"parse_error:{e}"
            logger.warning(f"NLM handoff unreadable: {e}")
            return None

        # Schema version gate
        if package.get("schema_version") != SCHEMA_VERSION:
            self.stats["skip_reason"] = f"schema_mismatch:{package.get('schema_version')}"
            logger.warning(
                f"NLM handoff schema {package.get('schema_version')} != {SCHEMA_VERSION}"
            )
            return None

        # Freshness gate
        generated_at = package.get("generated_at", "")
        try:
            gen_dt = datetime.fromisoformat(generated_at)
            if gen_dt.tzinfo is None:
                gen_dt = gen_dt.replace(tzinfo=timezone.utc)
            age_hours = (
                datetime.now(timezone.utc) - gen_dt
            ).total_seconds() / 3600
            if age_hours > FRESHNESS_HOURS:
                self.stats["skip_reason"] = f"stale:{age_hours:.1f}h"
                logger.warning(
                    f"NLM handoff is {age_hours:.1f}h old (max {FRESHNESS_HOURS}h) -- skipping"
                )
                return None
        except (ValueError, TypeError) as e:
            self.stats["skip_reason"] = f"timestamp_error:{e}"
            logger.warning(f"NLM handoff timestamp invalid: {e}")
            return None

        self.stats["handoff_loaded"] = 1
        self.stats["findings_count"] = len(package.get("findings", []))
        self.stats["topics_count"] = len(package.get("suggested_topics", []))
        logger.info(
            f"NLM handoff loaded: {self.stats['findings_count']} findings, "
            f"{self.stats['topics_count']} suggested topics"
        )
        return package

    def enrich(self, articles: list[dict]) -> list[dict]:
        """Augment scraper articles with NLM intelligence.

        Enrichment actions (all additive, never destructive):
        1. Tag articles whose topics match NLM findings (nlm_cross_validated)
        2. Boost quality_score for articles on NLM-suggested topics (+5/+10/+15)
        3. Add nlm_context field with relevant claim text for Claude enricher
        4. Tag articles in NLM avoid_urls as nlm_already_ingested (informational)

        Args:
            articles: Scraper's article list from step 1.

        Returns:
            Same list, possibly with added nlm_* fields on matching articles.
            Length >= input length. Order preserved.
        """
        try:
            self.handoff = self._load_handoff()
        except Exception as e:
            # Absolute safety net -- NEVER crash the scraper
            logger.error(f"NLM handoff load failed unexpectedly: {e}")
            self.handoff = None

        if self.handoff is None:
            return articles

        try:
            return self._apply_enrichment(articles)
        except Exception as e:
            logger.error(f"NLM enrichment failed -- returning articles unchanged: {e}")
            return articles

    def _apply_enrichment(self, articles: list[dict]) -> list[dict]:
        """Core enrichment logic. Separated for clean error boundary."""
        findings = self.handoff.get("findings", [])
        topics = self.handoff.get("suggested_topics", [])
        hints = self.handoff.get("scraper_hints", {})

        avoid_urls = set(hints.get("avoid_urls", []))
        priority_domains = set(hints.get("priority_domains", []))

        # Build keyword index from findings for fuzzy matching
        finding_keywords: dict[str, dict] = {}
        for f in findings:
            if not isinstance(f, dict):
                continue
            tags = [t.lower() for t in f.get("tags", []) if isinstance(t, str)]
            for keyword in tags:
                finding_keywords[keyword] = f
            # Extract key words from claim text (5+ char words)
            claim_text = f.get("claim_text", "")
            if isinstance(claim_text, str):
                for word in claim_text.split():
                    word_clean = word.strip(".,;:()\"'").lower()
                    if len(word_clean) >= 5:
                        finding_keywords[word_clean] = f

        # Build topic keyword index
        topic_keywords: dict[str, dict] = {}
        for t in topics:
            if not isinstance(t, dict):
                continue
            for query in t.get("search_queries", []):
                if not isinstance(query, str):
                    continue
                for word in query.lower().split():
                    word_clean = word.strip(".,;:()\"'")
                    if len(word_clean) >= 4:
                        topic_keywords[word_clean] = t

        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "").lower()
            text_preview = str(
                article.get("text", article.get("summary", ""))
            )[:500].lower()
            combined = f"{title} {text_preview}"

            # 1. Mark if URL already in NLM
            if url in avoid_urls:
                article["nlm_already_ingested"] = True

            # 2. Cross-validate against findings
            matched_findings: list[dict] = []
            seen_claim_ids: set[str] = set()
            for keyword, finding in finding_keywords.items():
                if keyword in combined:
                    claim_id = finding.get("claim_id", "")
                    if claim_id and claim_id not in seen_claim_ids:
                        matched_findings.append(finding)
                        seen_claim_ids.add(claim_id)

            if matched_findings:
                article["nlm_cross_validated"] = True
                article["nlm_matched_claims"] = [
                    {
                        "claim_id": f.get("claim_id"),
                        "claim_text": f.get("claim_text"),
                        "confidence": f.get("confidence"),
                        "confidence_label": f.get("confidence_label"),
                    }
                    for f in matched_findings[:3]  # max 3 to avoid bloat
                ]
                article["nlm_context"] = " | ".join(
                    f.get("claim_text", "") for f in matched_findings[:3]
                )
                self.stats["articles_enriched"] += 1

            # 3. Boost if on suggested topic
            matched_topics: list[dict] = []
            seen_topic_names: set[str] = set()
            for keyword, topic in topic_keywords.items():
                if keyword in combined:
                    t_topic = topic.get("topic", "")
                    if t_topic and t_topic not in seen_topic_names:
                        matched_topics.append(topic)
                        seen_topic_names.add(t_topic)

            if matched_topics:
                best_priority = min(
                    (t.get("priority", "LOW") for t in matched_topics),
                    key=lambda p: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(p, 3),
                )
                boost = {"HIGH": 15, "MEDIUM": 10, "LOW": 5}.get(best_priority, 0)
                old_score = article.get("quality_score", 50)
                article["quality_score"] = min(100, old_score + boost)
                article["nlm_boosted"] = True
                article["nlm_boost_amount"] = boost
                article["nlm_suggested_topic"] = matched_topics[0].get("topic", "")
                self.stats["articles_boosted"] += 1

            # 4. Priority domain flag
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower().replace("www.", "")
                if domain in priority_domains:
                    article["nlm_priority_domain"] = True
            except Exception:
                pass

        logger.info(
            f"NLM enrichment: {self.stats['articles_enriched']} cross-validated, "
            f"{self.stats['articles_boosted']} boosted"
        )
        return articles

    def get_stats(self) -> dict[str, int | str]:
        """Return enrichment statistics for pipeline state tracking."""
        return dict(self.stats)
```

### 2.3 Pipeline Insertion Point

Exact diff for `run_intel_pipeline.py`:

```python
# In PIPELINE_STEPS list, add AFTER '1_scraping':
PIPELINE_STEPS = [
    '1_scraping',
    '1.5_nlm_enrich',    # <-- NEW: NLM enrichment (optional, never blocks)
    '2_validation',
    # ... rest unchanged
]

# In run_step(), add one elif:
elif step == '1.5_nlm_enrich':
    return self.step_nlm_enrich()

# New method on IntelPipeline class:
def step_nlm_enrich(self) -> bool:
    """Step 1.5: Optionally enrich articles with NLM intelligence.

    ALWAYS returns True -- NLM enrichment is never a pipeline blocker.
    """
    articles = self.state.get('articles', [])
    if not articles:
        self.update_step_status('1.5_nlm_enrich', 'skipped', {'reason': 'no_articles'})
        return True

    try:
        from nlm_enricher import NLMEnricher
        enricher = NLMEnricher()
        self.state['articles'] = enricher.enrich(articles)
        self.update_step_status('1.5_nlm_enrich', 'completed', enricher.get_stats())
    except ImportError:
        self.log('NLMEnricher not available -- continuing without NLM', 'WARN')
        self.update_step_status('1.5_nlm_enrich', 'skipped', {'reason': 'import_error'})
    except Exception as e:
        self.log(f'NLM enrichment error (non-fatal): {e}', 'WARN')
        self.update_step_status('1.5_nlm_enrich', 'failed', {'error': str(e)})

    return True  # ALWAYS continue -- NLM is optional enrichment
```

### 2.4 Modification Inventory (Exhaustive)

| File                            | Change                                   | Lines         |
| ------------------------------- | ---------------------------------------- | ------------- |
| `scripts/nlm_enricher.py`       | **NEW** file                             | ~200          |
| `scripts/run_intel_pipeline.py` | Add `'1.5_nlm_enrich'` to PIPELINE_STEPS | 1             |
| `scripts/run_intel_pipeline.py` | Add `elif` branch in `run_step()`        | 2             |
| `scripts/run_intel_pipeline.py` | Add `step_nlm_enrich()` method           | 15            |
| **Total existing code touched** |                                          | **~18 lines** |

Nothing else changes. The scraper's validation, Qwen filter, enrichment, SEO, approval, and publishing are untouched.

---

## 3. Cross-Validation Rules (Feedback Loop Prevention)

### 3.1 Hard Rules (Non-Negotiable)

| Rule                                                 | Enforcement Mechanism                                                                                                                                                    | Violation Detection                                                                                                         |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| **Scraper NEVER cites NLM brief as source**          | NLM brief is not a URL. `nlm_context` is metadata for Claude enricher, never a `source_url`.                                                                             | Audit: check all published articles' `source_url` -- none should contain `nlm`, `notebooklm`, or `localhost`.               |
| **NLM NEVER imports scraper-published articles**     | NLM source registry (`nlm_nb2_sources.json`) has `blocked_domains`: `["balizero.com", "kita.balizero.com"]`. Pre-import filter in Step 4 rejects any URL matching these. | Audit: check all NB-2 sources against blocked domains. Alert if any match.                                                  |
| **Scraper can USE NLM context**                      | `nlm_context` flows to Claude enricher as background. The enriched article MUST cite original web source, not NLM claim.                                                 | Claude enricher prompt explicitly says: "NEVER cite NLM, NotebookLM, or internal intelligence as a source."                 |
| **NLM can READ scraper output for signal detection** | NLM query design can check `intel_output_latest.json` for topic inspiration. Scraper output is a SIGNAL, not a SOURCE.                                                   | NLM query templates never reference `balizero.com`. Signal detection reads titles/categories only, never imports full text. |

### 3.2 Feedback Loop Detection

A feedback loop forms when: NLM finding F1 -> scraper article A1 -> NLM ingests A1 -> NLM "discovers" F1 again as if new.

**Detection metrics (computed weekly):**

```python
def detect_feedback_loop(
    nlm_claims: list[dict],        # from nlm_nb2_claims.jsonl
    scraper_articles: list[dict],  # from published_articles.json
    nlm_sources: list[dict],       # from nlm_nb2_sources.json
) -> dict:
    """
    Returns:
        {
            "loop_detected": bool,
            "loop_score": float,  # 0.0 = clean, 1.0 = full loop
            "evidence": list[str],
        }
    """
    evidence = []

    # Check 1: Any NB-2 source URL matches a published article URL
    scraper_urls = {a.get("source_url", "") for a in scraper_articles}
    nlm_source_urls = {s.get("url", "") for s in nlm_sources}
    overlap = scraper_urls & nlm_source_urls
    if overlap:
        evidence.append(
            f"NLM ingested {len(overlap)} scraper-published URLs: "
            f"{list(overlap)[:3]}"
        )

    # Check 2: Claim text similarity with scraper headlines
    # If NLM "discovers" a claim whose text is >80% Jaccard overlap with a
    # scraper headline published BEFORE the NLM run, it may be recycling.
    for claim in nlm_claims:
        if not isinstance(claim, dict):
            continue
        claim_text = claim.get("claim_text", "")
        claim_words = set(claim_text.lower().split())
        for article in scraper_articles:
            title_words = set(article.get("title", "").lower().split())
            if not claim_words or not title_words:
                continue
            intersection = claim_words & title_words
            union = claim_words | title_words
            jaccard = len(intersection) / len(union) if union else 0
            if jaccard > 0.80:
                article_date = article.get("published_at", "")
                claim_date = claim.get("discovered_at", "")
                if article_date and claim_date and article_date < claim_date:
                    evidence.append(
                        f"Claim '{claim.get('claim_id', '?')}' may echo scraper article "
                        f"'{article.get('title', '')[:50]}' (Jaccard={jaccard:.2f})"
                    )

    loop_score = min(1.0, len(evidence) * 0.25)

    return {
        "loop_detected": loop_score >= 0.50,
        "loop_score": round(loop_score, 2),
        "evidence": evidence,
    }
```

**Alert threshold:** `loop_score >= 0.50` -> Telegram alert. Pipeline continues but logs warning.

**Resolution if detected:**

1. Identify the offending NB-2 source -> `source_delete` from NB-2
2. Add its domain to `blocked_domains` in source registry
3. Reset NLM claims that originated from that source

### 3.3 Information Flow Rules (Summary)

```
ALLOWED:
  NLM --findings--> handoff.json --> scraper (enriches, never cites NLM)
  NLM <--signal-- scraper titles/categories (query inspiration, never full text)
  War Room <-- NLM brief (topic selection with confidence)

FORBIDDEN:
  NLM <--imports-- balizero.com article as NB-2 source
  Scraper --publishes-- NLM claim_text as source attribution
  NLM --discovers-- claim that is actually recycled from prior scraper article
```

---

## 4. War Room Integration

### 4.1 NLM Brief for War Room

The NLM daily brief (`~/.agent/decisions/nlm_briefs/YYYY-MM-DD.json`) is the War Room's intelligence input.

**Brief schema (written by NLM at ~02:15 WITA):**

```jsonc
{
  "date": "2026-03-28",
  "generated_at": "2026-03-28T02:15:00+08:00",
  "notebook_id": "nb2_immigration",

  "editorial_topics": [
    {
      "rank": 1,
      "topic": "KITAS Sponsor Categories Expanded to Cooperatives",
      "suggested_angle": "The hidden opportunity: why cooperative-sponsored KITAS may be cheaper and faster than PT PMA sponsorship for solo entrepreneurs",
      "confidence": 0.87,
      "confidence_label": "VERIFIED",
      "urgency": "HIGH",
      "urgency_reason": "Effective April 15 -- 18 days from now",
      "linked_claims": ["CLM-20260328-001"],
      "source_count": 3,
      "audience_segment": "entrepreneurs, digital nomads with Bali cooperatives",
    },
    {
      "rank": 2,
      "topic": "Ngurah Rai KITAS Processing Delays",
      "suggested_angle": "What the 3x processing delay at Ngurah Rai means for your visa renewal timeline",
      "confidence": 0.63,
      "confidence_label": "PROVISIONAL",
      "urgency": "MEDIUM",
      "urgency_reason": "Active since March 20 -- clients may be affected now",
      "linked_claims": ["CLM-20260328-007"],
      "source_count": 2,
      "audience_segment": "current KITAS holders in Bali",
    },
    {
      "rank": 3,
      "topic": "OSS-RBA Portal Intermittent Failures",
      "suggested_angle": "OSS-RBA login issues are back -- here's what to do if your NIB application is stuck",
      "confidence": 0.55,
      "confidence_label": "PROVISIONAL",
      "urgency": "LOW",
      "urgency_reason": "Non-urgent advisory, affects company setup clients",
      "linked_claims": ["CLM-20260328-012"],
      "source_count": 1,
      "audience_segment": "PT PMA setup clients",
    },
  ],

  "telegram_summary": "...", // pre-formatted for Telegram (see 4.2)

  "full_sections": {
    "law_changes": [],
    "operations": [],
    "cross_domain": [],
    "open_questions": [],
  },
}
```

### 4.2 Telegram Message Format

Sent to War Room Telegram channel at ~02:20 WITA:

```
NLM INTELLIGENCE BRIEF -- 28 Mar 2026
------------------------------------

1. KITAS SPONSOR EXPANSION (VERIFIED, 87%)
   Cooperatives can now sponsor KITAS
   Angle: Hidden opportunity for solo entrepreneurs
   Urgency: HIGH -- effective Apr 15 (18 days)

2. NGURAH RAI DELAYS (PROVISIONAL, 63%)
   KITAS extensions taking 15 days vs normal 5-7
   Angle: Renewal timeline workaround
   Urgency: MEDIUM -- ongoing since Mar 20

3. OSS-RBA PORTAL ISSUES (PROVISIONAL, 55%)
   Login timeouts affecting NIB applications
   Angle: What to do if stuck
   Urgency: LOW -- advisory

------------------------------------
Reply with topic number to select for editorial.
Reply "0" for none (scraper auto-picks).
Reply "custom: [your topic]" for manual override.
```

### 4.3 Manual Override Protocol

| User Reply        | Action           | Effect                                                          |
| ----------------- | ---------------- | --------------------------------------------------------------- |
| `1`, `2`, or `3`  | Select NLM topic | War Room `00_topic_selector.py` receives as `--hint` parameter  |
| `0`               | Skip NLM topics  | Topic selector runs normally without NLM hint                   |
| `custom: [topic]` | Manual override  | Topic selector receives exact text as `--hint`                  |
| No reply by 08:00 | Auto-select      | Topic #1 used as hint if confidence >= 0.75. Otherwise no hint. |

### 4.4 War Room Feedback Loop (Topic Choice -> NLM)

**Feedback file:** `~/.agent/decisions/war_room_feedback/YYYY-MM-DD.json`

```jsonc
{
  "date": "2026-03-28",
  "chosen_topic_rank": 1, // 0 = none, 1-3 = NLM topic, -1 = custom
  "chosen_topic": "KITAS Sponsor Categories Expanded",
  "custom_topic": null, // only if rank == -1
  "chosen_at": "2026-03-28T09:15:00+08:00",
  "chosen_by": "owner", // owner | auto
  "article_published": true,
  "article_url": "https://balizero.com/intelligence/kitas-sponsor-2026",
}
```

**NLM uses this feedback to:**

1. Deprioritize topics already covered by War Room (avoid redundant editorial)
2. Track which NLM confidence levels lead to editorial pickup (calibration)
3. If `chosen_topic_rank == 0` more than 3x/week, reduce topic suggestion aggressiveness

---

## 5. State Management

### 5.1 State File Locations

| File                                                        | Owner          | Purpose                           | Lifecycle                     |
| ----------------------------------------------------------- | -------------- | --------------------------------- | ----------------------------- |
| `~/.agent/decisions/nlm_to_scraper/latest.json`             | NLM            | Active handoff                    | Overwritten nightly, archived |
| `~/.agent/decisions/nlm_to_scraper/archive/YYYY-MM-DD.json` | NLM            | Handoff history                   | 30 days                       |
| `~/.agent/decisions/nlm_briefs/YYYY-MM-DD.json`             | NLM            | Daily brief for humans            | 90 days                       |
| `~/.agent/decisions/war_room_feedback/YYYY-MM-DD.json`      | War Room       | Topic choice feedback             | 90 days                       |
| `~/.agent/decisions/nlm_scraper_xval/YYYY-MM-DD.json`       | Cross-val cron | Daily cross-validation            | 90 days                       |
| `apps/evaluator/nlm_nb2_sources.json`                       | NLM            | Source registry + blocked_domains | Git-tracked, permanent        |
| `apps/evaluator/nlm_nb2_claims.jsonl`                       | NLM            | Claims archive (append-only)      | Monthly rotation              |
| `apps/evaluator/nlm_scraper_convergence.jsonl`              | Cross-val      | Convergence tracking              | Monthly rotation              |

### 5.2 Cross-Validation State File

Written daily after both NLM and scraper have run (~04:00 WITA by cron):

```jsonc
// ~/.agent/decisions/nlm_scraper_xval/2026-03-28.json
{
  "date": "2026-03-28",
  "generated_at": "2026-03-28T04:00:00+08:00",

  "nlm_findings_total": 5,
  "nlm_findings_confirmed_by_scraper": 2,
  "nlm_findings_no_scraper_match": 3,

  "scraper_articles_total": 83,
  "scraper_articles_nlm_enriched": 12,
  "scraper_articles_nlm_boosted": 8,
  "scraper_immigration_articles": 15,

  "confirmed_findings": [
    {
      "nlm_claim_id": "CLM-20260328-001",
      "nlm_claim_text": "Permenkumham 8/2026 expands KITAS sponsor categories",
      "scraper_article_titles": ["New Rules for KITAS Sponsors in Indonesia"],
      "convergence_type": "INDEPENDENT_CONFIRMATION",
      "first_seen_by": "nlm",
      "first_seen_at": "2026-03-28T01:35:00+08:00",
    },
  ],

  "nlm_exclusive_findings": [
    {
      "claim_id": "CLM-20260328-007",
      "claim_text": "Ngurah Rai KITAS processing delayed to 15 days",
      "category": "PROCESSING_TIME",
      "note": "Operational signal -- scraper focused on news, not office operations",
    },
  ],

  "loop_check": {
    "loop_detected": false,
    "loop_score": 0.0,
    "evidence": [],
  },

  "nlm_handoff_was_fresh": true,
  "scraper_ran_successfully": true,
}
```

### 5.3 Convergence Tracking Over Time

Append-only log for longitudinal analysis:

```jsonc
// apps/evaluator/nlm_scraper_convergence.jsonl (one line per event)
{"date":"2026-03-28","claim_id":"CLM-20260328-001","event":"CONFIRMED","confirmer":"scraper","days_to_confirm":0}
{"date":"2026-03-28","claim_id":"CLM-20260328-007","event":"NLM_EXCLUSIVE","days_unconfirmed":1}
{"date":"2026-03-29","claim_id":"CLM-20260328-007","event":"CONFIRMED","confirmer":"scraper","days_to_confirm":1}
{"date":"2026-03-29","claim_id":"CLM-20260329-001","event":"SCRAPER_FIRST","note":"scraper found before NLM"}
```

**Weekly aggregation function:**

```python
def weekly_convergence_report(convergence_file: Path, week: str) -> dict:
    """
    Returns:
        {
            "week": "2026-W13",
            "total_claims": 15,
            "confirmed_same_day": 8,
            "confirmed_within_3_days": 3,
            "nlm_exclusive_7d": 2,
            "scraper_first": 2,
            "nlm_lead_time_avg_hours": 6.2,
            "confirmation_rate": 0.73,
        }
    """
```

### 5.4 Cleanup Cadence

| What                        | When              | Command                                                                             |
| --------------------------- | ----------------- | ----------------------------------------------------------------------------------- |
| Handoff archive > 30 days   | Weekly Sun 04:00  | `find ~/.agent/decisions/nlm_to_scraper/archive/ -name "*.json" -mtime +30 -delete` |
| NLM briefs > 90 days        | Monthly 1st 04:00 | `find ~/.agent/decisions/nlm_briefs/ -name "*.json" -mtime +90 -delete`             |
| War Room feedback > 90 days | Monthly 1st 04:00 | `find ~/.agent/decisions/war_room_feedback/ -name "*.json" -mtime +90 -delete`      |
| Cross-val results > 90 days | Monthly 1st 04:00 | `find ~/.agent/decisions/nlm_scraper_xval/ -name "*.json" -mtime +90 -delete`       |
| Convergence JSONL           | Monthly rotation  | Rename to `convergence_YYYY-MM.jsonl`, start fresh                                  |
| Claims JSONL                | Monthly rotation  | Rename to `claims_YYYY-MM.jsonl`, start fresh                                       |

---

## 6. Testing Strategy

### 6.1 Unit Tests (No Pipeline Required)

File: `tests/unit/test_nlm_enricher.py`

**Test matrix:**

| Test Class         | Test                                  | What It Verifies              |
| ------------------ | ------------------------------------- | ----------------------------- |
| `TestNoHandoff`    | `test_missing_file_returns_unchanged` | Scraper works without handoff |
| `TestNoHandoff`    | `test_invalid_json_returns_unchanged` | Corrupt file handled          |
| `TestNoHandoff`    | `test_stale_handoff_rejected`         | 26h freshness enforced        |
| `TestNoHandoff`    | `test_wrong_schema_version_rejected`  | Version gate works            |
| `TestNoHandoff`    | `test_empty_articles_returns_empty`   | Edge case: no articles        |
| `TestWithHandoff`  | `test_cross_validation_tags_matching` | Findings match articles       |
| `TestWithHandoff`  | `test_topic_boost_applied`            | Score boost +15/+10/+5        |
| `TestWithHandoff`  | `test_avoid_urls_tagged`              | Already-ingested flagged      |
| `TestWithHandoff`  | `test_never_removes_articles`         | Output >= input length        |
| `TestWithHandoff`  | `test_score_never_exceeds_100`        | Cap at 100                    |
| `TestRobustness`   | `test_survives_corrupt_findings`      | Malformed data handled        |
| `TestRobustness`   | `test_survives_missing_fields`        | Partial articles handled      |
| `TestFeedbackLoop` | `test_no_loop_clean_state`            | Clean state passes            |
| `TestFeedbackLoop` | `test_loop_detected_url_overlap`      | URL overlap caught            |
| `TestFeedbackLoop` | `test_loop_detected_claim_echo`       | Claim recycling caught        |

### 6.2 Integration Test: Mock Handoff + Real Pipeline

```bash
# 1. Create mock handoff with current timestamp
# 2. Run pipeline in dry-run mode
# 3. Verify 1.5_nlm_enrich step shows in pipeline state
# 4. Verify handoff_loaded == 1
# 5. Cleanup mock file
```

### 6.3 Regression Test: Scraper Without Handoff

```bash
# 1. Ensure NO handoff file exists
# 2. Run pipeline in dry-run mode
# 3. Verify 1.5_nlm_enrich was skipped or completed with handoff_loaded == 0
# 4. Verify all other steps ran normally
```

### 6.4 Key Assertion: Scraper Independence

The single most important test:

```python
def test_scraper_independence():
    """The scraper produces identical output with and without NLM handoff,
    EXCEPT for nlm_* prefixed fields which are additive metadata."""
    # Run 1: no handoff
    articles_without = run_pipeline_and_get_articles(handoff=None)

    # Run 2: with handoff
    articles_with = run_pipeline_and_get_articles(handoff=mock_handoff)

    # Same articles, same order
    assert len(articles_without) == len(articles_with)
    for a_without, a_with in zip(articles_without, articles_with):
        # All non-nlm fields identical (except quality_score which may be boosted)
        for key in a_without:
            if key == "quality_score":
                # Score can only go UP, never down
                assert a_with.get(key, 0) >= a_without[key]
            elif not key.startswith("nlm_"):
                assert a_with.get(key) == a_without[key], f"Field {key} changed"
```

---

## 7. Deployment Checklist

| Phase              | Step                                        | Risk   | Rollback            |
| ------------------ | ------------------------------------------- | ------ | ------------------- |
| 1. File creation   | Create `nlm_enricher.py` + tests            | None   | Delete file         |
| 1. File creation   | Create `~/.agent/decisions/nlm_to_scraper/` | None   | rmdir               |
| 1. File creation   | Run unit tests                              | None   | N/A                 |
| 2. Pipeline wiring | Add `1.5_nlm_enrich` to pipeline            | LOW    | Remove 1 line       |
| 2. Pipeline wiring | Regression test (no handoff)                | LOW    | N/A                 |
| 2. Pipeline wiring | Integration test (mock handoff)             | LOW    | N/A                 |
| 3. NLM writer      | Implement handoff writer in NLM             | MEDIUM | Disable write call  |
| 3. NLM writer      | Run full NLM->scraper cycle                 | MEDIUM | Delete handoff file |
| 4. War Room        | Add Telegram brief message                  | LOW    | Comment out send    |
| 4. War Room        | Add feedback file writer                    | LOW    | Delete feedback dir |
| 5. Monitoring      | Add cross-val cron                          | LOW    | Remove cron entry   |
| 5. Monitoring      | Add convergence tracking                    | LOW    | Delete JSONL        |

---

## 8. Risk Assessment

| Risk                                  | Severity | Mitigation                                                                         |
| ------------------------------------- | -------- | ---------------------------------------------------------------------------------- |
| NLM handoff corrupts scraper articles | HIGH     | NLMEnricher adds `nlm_*` fields only. Triple try/except. Step always returns True. |
| Scraper becomes dependent on NLM      | HIGH     | Regression test enforces independence. File absence = graceful skip.               |
| Feedback loop forms over weeks        | MEDIUM   | Blocked domains in registry. Weekly detection metric. Telegram alert at >= 0.50.   |
| Handoff file grows unbounded          | LOW      | Max ~5KB by design. Schema constrains content.                                     |
| Schema evolution breaks reader        | LOW      | Additive-only rule. Reader ignores unknown fields.                                 |
| Clock skew NLM vs scraper             | LOW      | 26h window (not 24h) gives 2h margin. Same machine (Pro).                          |

---

## 9. Success Metrics (Month 1)

| Metric                           | Target                   | Measurement              |
| -------------------------------- | ------------------------ | ------------------------ |
| Scraper runs without NLM         | 100%                     | Regression test in CI    |
| Handoff consumed when present    | >= 90%                   | Pipeline state files     |
| Articles cross-validated per run | >= 5 on immigration days | `articles_enriched` stat |
| Feedback loop score              | < 0.25 weekly avg        | Cross-validation state   |
| War Room NLM topic pickup        | >= 2x/week               | Feedback files           |
| NLM-exclusive findings           | >= 1/week                | Convergence tracking     |
| Pipeline latency impact          | < 2 seconds added        | Step timing              |

---

## Appendix A: Claude Enricher Prompt Modification

When `nlm_context` is present on an article, append to the prompt in `claude_cli_enricher.py`:

```python
nlm_context = article.get("nlm_context", "")
if nlm_context:
    prompt += f"""

VERIFIED INTELLIGENCE CONTEXT (from internal analysis -- DO NOT cite as source):
{nlm_context}

IMPORTANT: Use this context to add depth and verify claims, but ALWAYS cite
the original web source URLs. NEVER cite "NLM", "NotebookLM", "internal analysis",
or "intelligence brief" as a source.
"""
```

## Appendix B: Handoff File Size Estimate

| Section          | Avg items | Est. bytes       |
| ---------------- | --------- | ---------------- |
| Envelope         | 6 fields  | ~300             |
| Findings         | 3 avg     | ~2,000           |
| Suggested Topics | 2 avg     | ~600             |
| Active Signals   | 2 avg     | ~400             |
| Scraper Hints    | 3 arrays  | ~300             |
| NLM Health       | 4 fields  | ~100             |
| **Total**        |           | **~3,700 bytes** |

Well within `os.replace()` atomicity on APFS (macOS).
