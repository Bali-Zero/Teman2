# Step 4b: Source Management — Codex Perspective (Discipline + Separation)

> Agent: Codex GPT-5.4 perspective (operational discipline, data structures, hard rules)
> Date: 2026-03-28
> Complements: `04_source_management.md` (DeepSeek R1 — formulas + quantification)
> Status: Brainstorm complete

---

## 1. Source Lifecycle — 6 Stages with Hard Transition Rules

### Stage Diagram

```
           ┌──────────────────────────────────────────────────────────────┐
           │                      NOT in NB-2                            │
           │                                                             │
           │   INGEST ──┬── DISCARD (pre-import filter rejects)          │
           │            │                                                │
           └────────────┼────────────────────────────────────────────────┘
                        │
                        ▼ research_import succeeds
           ┌────────────────────────────────────────────────────────────┐
           │                       IN NB-2                              │
           │                                                            │
           │   QUARANTINE ──┬── TRIAGE ──┬── ACTIVE                     │
           │                │            │     │                        │
           │                │            │     ├── CONSOLIDATE ── ARCHIVE│
           │                │            │     │                   ▲    │
           │                │            │     └───────────────────┘    │
           │                │            │                              │
           │                │            └── DISCARD (delete from NB-2) │
           │                │                                           │
           │                └── DISCARD (quarantine SLA breach)         │
           └────────────────────────────────────────────────────────────┘
```

### Exact Transition Table

Every transition has an **objective, testable condition**. No judgment calls.

| #   | From        | To                    | Trigger                                 | Condition (ALL must be true)                                         | SLA                                                  |
| --- | ----------- | --------------------- | --------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------- |
| T1  | INGEST      | QUARANTINE            | `research_import` API returns success   | `should_import()` returned True                                      | Immediate                                            |
| T2  | INGEST      | DISCARD               | Pre-import filter                       | Any `should_import()` rejection reason                               | Immediate                                            |
| T3  | QUARANTINE  | TRIAGE                | Next pipeline run's consolidation phase | Source has existed in NB-2 for >= 1 complete query cycle             | **Max 24h**                                          |
| T4  | QUARANTINE  | DISCARD               | SLA breach                              | Source in QUARANTINE for 2+ pipeline runs (48h) without triage       | Auto-cleanup                                         |
| T5  | TRIAGE      | ACTIVE                | Confidence scoring + dedup check        | Score >= 0.55 AND dedup overlap < 0.70 AND claims >= 1               | Same run                                             |
| T6  | TRIAGE      | DISCARD               | Score too low                           | Score < 0.35 AND claims = 0                                          | Same run. `source_delete` from NB-2                  |
| T7  | TRIAGE      | QUARANTINE (demote)   | Needs corroboration                     | Score 0.35-0.54 AND single source AND claims >= 1                    | Re-evaluate in 72h. If still uncorroborated, DISCARD |
| T8  | ACTIVE      | CONSOLIDATE           | Claims absorbed                         | Age >= 14d AND claims_absorbed / claim_count >= 0.80                 | Friday consolidation                                 |
| T9  | ACTIVE      | CONSOLIDATE           | Superseded                              | Higher-tier source covers >= 70% of same claims                      | Next daily run                                       |
| T10 | ACTIVE      | ARCHIVE               | Emergency prune                         | NB-2 count >= 70 AND this source has lowest prune_score among ACTIVE | Immediate                                            |
| T11 | ACTIVE      | ARCHIVE               | Staleness                               | DeepSeek staleness S(t) < 0.20 (see 04_source_management.md §1)      | Daily check                                          |
| T12 | ACTIVE      | ARCHIVE               | Source dead                             | URL returns 404/410 on periodic recheck                              | Next recheck                                         |
| T13 | CONSOLIDATE | ARCHIVE               | Claims verified absorbed                | Master Doc contains all claims from this source with citations       | Same Friday or next Monday                           |
| T14 | CONSOLIDATE | ACTIVE (promote back) | New information found                   | Source has new claims added after consolidation was initiated        | Rare, but possible if source URL updates             |

### Hard SLA Table

| Stage       | Max Duration                                  | If SLA Breached                                                          |
| ----------- | --------------------------------------------- | ------------------------------------------------------------------------ |
| INGEST      | 0 (transient — import or discard immediately) | N/A                                                                      |
| QUARANTINE  | 48h (2 pipeline runs)                         | Auto-discard. Log as `quarantine_sla_breach`                             |
| TRIAGE      | 0 (transient — score and route in same run)   | N/A                                                                      |
| ACTIVE      | 60 days (hard max regardless of SVS)          | Force to CONSOLIDATE if claims absorbed, else ARCHIVE                    |
| CONSOLIDATE | 7 days (1 Friday cycle)                       | Force to ARCHIVE. If claims not absorbed, log `consolidation_incomplete` |

### Capacity Per Stage

| Stage                              | Hard Cap | Rationale                                                                        |
| ---------------------------------- | -------- | -------------------------------------------------------------------------------- |
| QUARANTINE                         | 15       | If > 15 sources waiting triage, pipeline is importing faster than processing     |
| ACTIVE                             | 50       | Core working set. Leaves room for 4 Master Doc notes + permanent refs            |
| CONSOLIDATE                        | 10       | Temporary holding. Should drain to 0 every Friday                                |
| **Total pipeline-managed in NB-2** | **70**   | Our operational ceiling. Permanent refs (visa handbooks etc.) use separate slots |

---

## 2. The 4 Master Documents — Detailed Design

### Decision: NLM Notes (NOT Uploaded Sources)

**Why Notes:**

1. **Mutable.** `note_update` overwrites in place. Sources are immutable once uploaded.
2. **No source-limit impact.** Notes do NOT count toward the 600-source cap.
3. **Instant availability.** Notes are queryable immediately. Uploaded sources need indexing.
4. **Frequency.** We update Master Docs 1-5x/week. Creating 5 new sources/week is wasteful; updating 1 note is clean.

**Naming convention** (prefix prevents accidental deletion):

```
[MASTER] Change Log — NB-2 Immigration
[MASTER] Operations Status — NB-2 Immigration
[MASTER] Cross-Domain Impacts — NB-2 Immigration
[MASTER] Open Questions — NB-2 Immigration
```

### Master 1: Change Log

**Content:** Chronological record of all VERIFIED and PROVISIONAL regulatory/operational changes.

```markdown
# [MASTER] Change Log — NB-2 Immigration

Updated: 2026-03-28T02:10+08:00 | Run: 2026-03-28 cluster=A | Entries: 47

---

## 2026-03-28 — KITAS Sponsor Categories Expanded

- **Category:** LEGAL_CHANGE
- **Confidence:** 0.87 VERIFIED
- **Regulation:** Permenkumham 8/2026, effective 2026-04-15
- **Scope:** NATIONAL
- **Affected visa types:** KITAS_SPONSOR, KITAS_KERJA
- **Summary:** Eligible sponsor categories expanded to include registered cooperatives
  and social organizations, in addition to PT/CV/Foundation.
- **Source chain:**
  [T0] JDIH Kemenkumham gazette (2026-03-25)
  [T1] imigrasi.go.id press release (2026-03-27)
  [T5] Jakarta Post (2026-03-28)
- **Claims from:** src_2026-03-27_001, src_2026-03-27_005, src_2026-03-28_002
- **Client action:** Update KITAS onboarding docs. Notify cooperative-sponsored clients.

---

## 2026-03-25 — Ngurah Rai Original Degree Requirement

- **Category:** OPERATIONAL_CHANGE
- **Confidence:** 0.63 PROVISIONAL ⚠️
- **Scope:** LOCAL_OFFICE: Ngurah Rai
- **Gap:** No Surat Edaran found. See OQ-047.
  ...

---

## [NO CHANGES DETECTED] 2026-03-20

Pipeline checked clusters A, B, C. No new regulation changes found.

---

## Archive (older than 90 days)

### 2025-12-15 — UU 1/2026 Immigration Law Published

...
```

**Update triggers:**

- T1: Any claim reaches VERIFIED (>= 0.75)
- T2: Any PROVISIONAL claim gets promoted to VERIFIED
- T3: Regulation effective date passes (status: "upcoming" → "in effect")
- T4: Friday consolidation (batch update)
- T5: No changes for 7 consecutive days → add `[NO CHANGES DETECTED]` entry

**Staleness rule:** Entries > 90 days move to `## Archive` section (still in the note, clearly historical).

**Max size target:** ~3,000 words. When approaching 4,000, archive oldest entries more aggressively.

### Master 2: Operations Status

**Content:** Current state of immigration offices, portals, processing times. This is a **snapshot**, not a log.

```markdown
# [MASTER] Operations Status — NB-2 Immigration

Updated: 2026-03-28T02:10+08:00 | Run: 2026-03-28

---

## Portal Status

| Portal                     | Status         | Checked | Notes                         |
| -------------------------- | -------------- | ------- | ----------------------------- |
| molina.imigrasi.go.id      | ✅ OPERATIONAL | 03-28   | —                             |
| oss.go.id                  | ⚠️ DEGRADED    | 03-27   | Login timeouts (T5: NusaBali) |
| visa-online.imigrasi.go.id | ✅ OPERATIONAL | 03-28   | —                             |

## Processing Times (Bali)

| Office     | Visa Type        | Current     | Normal   | Status     | Source        |
| ---------- | ---------------- | ----------- | -------- | ---------- | ------------- |
| Ngurah Rai | KITAS Extension  | 15 biz days | 5-7 days | 🔴 DELAYED | T4+T5 (2 src) |
| Ngurah Rai | B211A Extension  | 3 biz days  | 3 days   | 🟢 NORMAL  | T1            |
| Denpasar   | KITAP Conversion | 25 biz days | 20 days  | 🟡 SLOW    | T5            |

## Active Enforcement

| Operation      | Area          | Since | Status | Sources |
| -------------- | ------------- | ----- | ------ | ------- |
| Tim Pora sweep | Canggu/Berawa | 03-22 | ACTIVE | T3+T5   |

## Current Advisories

- ⚠️ Bring original degree certs for ITAS at Ngurah Rai (PROVISIONAL since 03-20, OQ-047)
- ✅ B211A online extension working for all categories
- ⚠️ OSS-RBA login issues — use alternative browser (PROVISIONAL since 03-27)
```

**Update triggers:**

- T1: Any OPERATIONAL_CHANGE or PROCEDURAL_UPDATE claim at any confidence level
- T2: Any ENFORCEMENT_ACTION from Bali sources
- T3: Every Monday (refresh processing times, clear stale advisories)
- T4: Advisory ages 14+ days without re-confirmation → mark `[UNCONFIRMED — may no longer apply]`

**Staleness rule:** Every row has a `Checked` column. If any `Checked` date > 7 days old, entry gets `[STALE]` flag. Monday pipeline specifically targets stale entries for refresh queries.

**Max size target:** ~1,500 words. This is a dashboard, not a history book.

### Master 3: Cross-Domain Impacts

**Content:** How immigration changes affect tax, company, property, compliance.

```markdown
# [MASTER] Cross-Domain Impacts — NB-2 Immigration

Updated: 2026-03-14T02:10+08:00 | Last L4 query: 2026-03-07

---

## Immigration → Tax

### KITAS NPWP Obligation [VERIFIED 0.82]

Permenkumham 8/2026 + DJP SE-2026: ALL KITAS holders must obtain NPWP
within 30 days of issuance.
**Client impact:** Include NPWP in KITAS onboarding. Affects ~60% of active clients.
**Source:** Change Log 2026-03-15. Cross-verified NB-4 (Tax).

### Digital Nomad Tax Residency [MONITORING]

UU 1/2026 may change tax residency rules for E33G holders.
No implementing regulation yet. Signal since 2026-03-10. See OQ-051.

## Immigration → Company Setup

### RPTKA Before NIB [PROVISIONAL 0.71]

New OSS-RBA flow requires approved RPTKA before NIB activation for PMA
with foreign workers.
**Client impact:** Company setup extends 10-15 biz days if foreign director needs KITAS.
**Source:** Change Log 2026-03-22.

## Immigration → Property

No active cross-domain links. Last reviewed: 2026-03-07 (L4-3 query).

## Immigration → Compliance

(Section reserved for future L4 queries)
```

**Update triggers:**

- T1: L4 cross-domain query results (monthly, 1st Thursday)
- T2: Any Change Log entry with `affected_services` spanning 2+ domains
- T3: Manual trigger `/nlm_crossdomain`
- T4: Any section not reviewed in 30 days → auto-generate a targeted L4 query

**Max size target:** ~1,200 words. Concise links, not deep analysis.

### Master 4: Open Questions

**Content:** Intelligence gaps, unresolved signals, pending confirmations.

```markdown
# [MASTER] Open Questions — NB-2 Immigration

Updated: 2026-03-28T02:10+08:00
Open: 8 | Resolved this week: 3 | Total resolved: 42

---

## HIGH (affects client advisory)

### OQ-047: Ngurah Rai degree certificate requirement

- Opened: 2026-03-20 | Age: 8 days
- Confidence: 0.63 PROVISIONAL
- Gap: No Surat Edaran backing this practice change
- Queries: 3 attempted (L1 on 03-20, 03-25, 03-28)
- Next: Query "surat edaran persyaratan ijazah asli ITAS 2026"
- Escalate by: 2026-04-03 (call Ngurah Rai office if unresolved)

### OQ-051: E33G visa implementation timeline

- Opened: 2026-03-25 | Age: 3 days
- Confidence: 0.48 MONITORING
- Gap: Government announced E33G but no implementing regulations published
- Queries: 1 attempted (D2 on 03-25)
- Next: L3 predictive query next Thursday

## MEDIUM (monitoring)

### OQ-044: Bali tourist levy impact on B211A processing

- Opened: 2026-03-15 | Age: 13 days
- Queries: 2 attempted
- Next: Check Pemprov Bali for Pergub update

## RESOLVED (last 7 days)

### OQ-039 ✅ PNBP fee increase for KITAS extension

- Opened: 2026-03-10 | Resolved: 2026-03-26 (16 days)
- Resolution: Confirmed via PP 28/2025 on JDIH. New fee Rp 3,500,000 (was 2,500,000).
  Effective 2026-04-01.
- Absorbed into: Change Log 2026-03-26, Operations Status fee table.
```

**Update triggers:**

- T1: Every pipeline run — check if new claims answer an existing OQ
- T2: PROVISIONAL claim cannot be verified in 48h → auto-create OQ
- T3: OQ resolution — claim reaches VERIFIED → close OQ, link Change Log entry
- T4: Friday — review all OQs, close stale (> 30d no progress, no client impact)
- T5: next_action date passes without update → escalate priority by 1 level

**Hard rules:**

- Maximum **15 open questions** at any time. Must close lowest-priority before opening new.
- OQs open > 30 days with no progress → either close as "Cannot verify" or escalate to manual.
- Every OQ must have a `next_action` with a specific date.

### Versioning Strategy for Master Docs

NLM `note_update` is destructive (overwrites). We cannot rely on NLM for history.

**External version tracking:**

1. **Content hash per update.** Every time we call `note_update`, compute SHA-256 of the new content. Store in `source_registry.json → master_docs → <name> → content_hash`.

2. **Friday snapshots.** Every Friday consolidation, save the full text of all 4 Master Docs to:

   ```
   ~/.agent/decisions/nlm_master_snapshots/
   ├── 2026-03-28/
   │   ├── change_log.md
   │   ├── operations_status.md
   │   ├── cross_domain.md
   │   └── open_questions.md
   ├── 2026-04-04/
   │   └── ...
   ```

3. **Retention:** 12 weeks of snapshots. Quarterly audit can diff any 2 weeks.

4. **Recovery:** If a `note_update` corrupts content, restore from latest Friday snapshot.

---

## 3. Deduplication — "Reduce Uncertainty in Layers"

### 3-Layer Algorithm

```
LAYER 1: URL Match                (instant, 100% certain)
    ↓ no match
LAYER 2: URL Canonical Match      (instant, 95% certain)
    ↓ no match
LAYER 3: Claim Content Overlap    (expensive, variable certainty)
```

#### Layer 1: URL Exact Match

```python
def normalize_url(url: str) -> str:
    """Normalize URL for exact comparison."""
    url = url.lower().strip().rstrip("/")
    # Remove tracking parameters
    url = re.sub(r'[?&](utm_\w+|fbclid|gclid|ref|source|campaign)=[^&]*', '', url)
    # Remove trailing ? if all params stripped
    url = url.rstrip("?&")
    # Remove www prefix
    url = re.sub(r'^https?://(www\.)?', 'https://', url)
    return url
```

Match → DISCARD incoming. Existing source already in NB-2.

#### Layer 2: URL Canonical Match

Same domain + same path, different scheme/params/fragment:

```
https://imigrasi.go.id/berita/123  ==  http://imigrasi.go.id/berita/123
hukumonline.com/article/abc?p=1   ==  hukumonline.com/article/abc?p=2
```

Match → DISCARD incoming. Log as `dedup_canonical`.

#### Layer 3: Claim Content Overlap

Run ONLY when Layers 1-2 pass (no URL match). This is the expensive check.

**Method:** Compare extracted claims at the semantic level.

Two claims are the "same claim" when ALL of:

1. Same `category` (both LEGAL_CHANGE, both OPERATIONAL_CHANGE, etc.)
2. Same `regulation_ref` or `subject_entity`
3. Same `assertion_direction` (both say "requirement added", not one says added and one says removed)
4. Temporal overlap: `|effective_date_A - effective_date_B| <= 30 days`

```
overlap_ratio = matching_claims / min(claims_in_A, claims_in_B)
```

Using `min()` denominator (Szymkiewicz-Simpson, per DeepSeek's recommendation) to catch when a smaller source is fully contained in a larger one.

| Overlap   | Classification      | Action                                                              |
| --------- | ------------------- | ------------------------------------------------------------------- |
| >= 0.90   | TRUE_DUPLICATE      | Auto-discard lower-value source                                     |
| 0.70-0.89 | SUBSTANTIAL_OVERLAP | Keep higher-tier/fresher. Archive other UNLESS it has unique claims |
| 0.40-0.69 | PARTIAL_OVERLAP     | Both survive. Flag `dedup_group` in registry                        |
| < 0.40    | INDEPENDENT         | No dedup action                                                     |

### Priority Rules (Which Copy Survives)

| Scenario                                                   | Keep     | Archive | Reason                                      |
| ---------------------------------------------------------- | -------- | ------- | ------------------------------------------- |
| Same regulation: gazette (T0) vs news (T5)                 | T0       | T5      | Authority                                   |
| Same regulation: gazette (T0) vs law firm analysis (T5)    | **BOTH** | —       | Different value: T0=text, T5=interpretation |
| Same enforcement action: NusaBali (T5) vs Tribun Bali (T5) | Earlier  | Later   | Same tier → temporal priority               |
| Same change: IG post (T4) vs official website (T1)         | T1       | T4      | T4 was early signal, T1 confirms            |
| Gazette (T0) vs amended gazette (T0)                       | **BOTH** | —       | Tag `supersedes`/`superseded_by`            |

**Hard rule for regulations:** Max **2 sources per regulation** in NB-2:

- The highest-tier source (gazette or circular)
- The most useful interpretation (named firm analysis > generic news)

All others → extract claims → absorb into Change Log → archive.

### Dedup Alarm Thresholds

| Metric                                     | Healthy | Warning | Alarm                                  |
| ------------------------------------------ | ------- | ------- | -------------------------------------- |
| Daily dedup rate                           | < 20%   | 20-30%  | > 30% for 3 consecutive days           |
| Same-URL reimport                          | 0%      | 1-5%    | > 5% (URL normalization bug)           |
| Cross-run dedup (yesterday's source today) | < 10%   | 10-20%  | > 20% (queries too similar day-to-day) |
| Claim overlap in new sources               | < 40%   | 40-60%  | > 60% (queries exhausted this topic)   |

**Alarm response:**

- Daily > 30% for 3 days → **rotate query templates** for current cluster
- Same-URL > 5% → **debug pre-import filter** (normalization logic)
- Cross-run > 20% → **add `sejak [last_run_date]` temporal anchor** to queries
- Claim overlap > 60% → **escalate from L1 to L2/L3** for this topic

---

## 4. Source Budget Management (600 Limit)

### Import Arithmetic

```
Per query (deep mode):    ~15 raw sources returned
Pre-import filter:        ~40-50% rejected (denylist, dedup, low-tier, old)
Net per query:            ~8 imported to QUARANTINE
After triage:             ~5 reach ACTIVE
After Layer 3 dedup:      ~4 net new ACTIVE

Daily (2 queries):        ~8 net new ACTIVE sources
Weekly (5 days):          ~40 net new ACTIVE sources
```

**Time to fill 30 pipeline-managed slots** (starting from 40 permanent + 0 pipeline):

- 30 / 8 = **~4 days** without any archival
- Therefore: **daily source management is mandatory**, weekly consolidation alone is insufficient

### Pre-Import Filter (`should_import()`)

This is the single most important budget control. It runs BEFORE `research_import`.

```python
def should_import(
    source: dict,
    registry: SourceRegistry,
) -> tuple[bool, str]:
    """Gate function. Returns (allow, rejection_reason)."""

    url = source.get("url", "")
    normalized = normalize_url(url)

    # 1. Domain denylist
    if any(d in normalized for d in registry.domain_denylist):
        return False, "domain_denylist"

    # 2. URL dedup (Layer 1 + 2)
    if registry.url_exists(normalized):
        return False, "duplicate_url"
    if registry.url_canonical_exists(normalized):
        return False, "duplicate_canonical"

    # 3. Source type exclusion
    if source.get("type") in EXCLUDED_TYPES:
        return False, "excluded_source_type"

    # 4. Publication date floor
    pub_date = source.get("publication_date", "")
    if pub_date and pub_date < "2024-01-01":
        return False, "too_old"

    # 5. Language filter
    lang = source.get("language", "").lower()
    if lang and lang not in ("id", "en", "ms", ""):
        return False, "wrong_language"

    # 6. Budget pressure gates
    current = registry.count_in_nb2()
    if current >= 65:
        # Pressure zone: only T0-T2
        est_tier = source.get("estimated_tier", 6)
        if est_tier > 2:
            return False, "budget_pressure_low_tier"
    if current >= 70:
        return False, "hard_cap_reached"

    return True, "allowed"

EXCLUDED_TYPES = frozenset({
    "forum", "social_personal", "travel_blog",
    "travel_guide", "affiliate", "reddit", "quora",
})
```

**Domain denylist (initial, grows dynamically):**

```python
INITIAL_DENYLIST = [
    "tripadvisor.com", "expat.com/forum", "kaskus.co.id",
    "nomadicmatt.com", "thepointsguy.com", "reddit.com",
    "quora.com", "medium.com/@", "youtube.com",
    "tiktok.com", "pinterest.com", "booking.com",
    "agoda.com", "skyscanner.com", "lonelyplanet.com",
]
```

Denylist grows when: any domain produces 3+ discarded sources in a single week.

### Emergency Pruning Protocol

**Trigger:** NB-2 count >= 70 at any point during a pipeline run.

**Cut order** (strictly sequential, stop when count drops below 60):

| Priority | Cut target                                                          | Expected freed |
| -------- | ------------------------------------------------------------------- | -------------- |
| 1        | All CONSOLIDATE stage sources                                       | 0-10           |
| 2        | All QUARANTINE sources older than 12h                               | 0-5            |
| 3        | ACTIVE T5-T6 sources older than 7 days                              | 0-10           |
| 4        | ACTIVE T3-T4 sources older than 14 days with >= 80% claims absorbed | 0-8            |
| 5        | ACTIVE sources by ascending prune_score (lowest value first)        | As needed      |

**Prune score** (per DeepSeek's SVS, simplified for emergency use):

```
prune_score = (tier_weight × 0.30) + (freshness × 0.25)
            + (claim_absorption × 0.25) + (reference_freq × 0.20)

tier_weight:      T0=1.0, T1=0.9, T2=0.8, T3=0.7, T4=0.6, T5=0.4, T6=0.2
freshness:        max(0, 1 - days_old/30)
claim_absorption: 1.0 if ALL claims in Master Docs, 0.0 if none
reference_freq:   times_cited_in_last_4_briefs / 4
```

Lower score = cut first.

**NEVER prune (regardless of count):**

- T0 sources less than 60 days old
- Sources with pending PROVISIONAL claims tied to Open Questions
- Sources explicitly marked `pinned: true` by operator

### Archival Destination

When a source is deleted from NB-2:

| Data            | Preserved where                                                        | Retention |
| --------------- | ---------------------------------------------------------------------- | --------- |
| Verified claims | Master Documents (notes in NB-2)                                       | Permanent |
| Source metadata | `source_registry.json` (marked `stage: ARCHIVE`)                       | 6 months  |
| Full record     | `~/.agent/decisions/nlm_source_archive/YYYY-MM/archived_sources.jsonl` | 6 months  |
| URL             | Registry (allows re-import detection)                                  | Permanent |
| Full text       | **NOT preserved.** Re-import URL if needed                             | —         |

---

## 5. External Tracking — Source Registry

### File Location

```
apps/evaluator/nlm_nb2_source_registry.json
```

Matches existing patterns: `coverage_state.json`, `indexing_state.json` in same directory.

### Schema

```json
{
  "version": 2,
  "notebook_id": "cff93ab0-813a-42f2-a8de-36987e724271",
  "last_updated": "2026-03-28T02:15:00+08:00",

  "counts": {
    "quarantine": 3,
    "active": 34,
    "consolidate": 2,
    "total_in_nb2": 39,
    "permanent_refs": 40,
    "archived_total": 127,
    "master_notes": 4
  },

  "budget": {
    "hard_cap": 70,
    "warning_at": 60,
    "pressure_at": 65,
    "utilization_pct": 55.7
  },

  "domain_denylist": [
    "tripadvisor.com",
    "expat.com/forum",
    "kaskus.co.id",
    "nomadicmatt.com",
    "reddit.com",
    "quora.com",
    "youtube.com"
  ],

  "sources": {
    "src_2026-03-28_001": {
      "source_id": "src_2026-03-28_001",
      "nlm_source_id": "abc-123-def-456",
      "stage": "ACTIVE",
      "url": "https://jdih.kemenkumham.go.id/...",
      "url_normalized": "https://jdih.kemenkumham.go.id/...",
      "title": "Permenkumham 8/2026 tentang Perubahan...",
      "tier": 0,
      "tier_label": "T0_NATIONAL_PRIMARY_LAW",
      "source_type": "OFFICIAL_GAZETTE",

      "confidence": {
        "current": 0.91,
        "class": "VERIFIED",
        "history": [
          { "date": "2026-03-27", "score": 0.72, "class": "PROVISIONAL" },
          { "date": "2026-03-28", "score": 0.91, "class": "VERIFIED" }
        ]
      },

      "claims": [
        {
          "claim_id": "NB2-2026-03-28-001",
          "text": "Permenkumham 8/2026 expands KITAS sponsor categories to cooperatives",
          "category": "LEGAL_CHANGE",
          "confidence": 0.91,
          "absorbed_into": "change_log",
          "absorbed_date": "2026-03-28"
        },
        {
          "claim_id": "NB2-2026-03-28-002",
          "text": "New regulation effective 2026-04-15",
          "category": "LEGAL_CHANGE",
          "confidence": 0.91,
          "absorbed_into": "change_log",
          "absorbed_date": "2026-03-28"
        }
      ],
      "claim_count": 3,
      "claims_absorbed": 2,
      "claims_pending": 1,

      "dedup": {
        "group": "permenkumham_8_2026",
        "supersedes": null,
        "superseded_by": null,
        "overlap_checked_against": ["src_2026-03-27_005"]
      },

      "dates": {
        "publication": "2026-03-25",
        "imported": "2026-03-27T01:35:00+08:00",
        "activated": "2026-03-27T01:55:00+08:00",
        "last_referenced": "2026-03-28",
        "quarantine_until": null
      },

      "reference_count": 4,
      "language": "id",
      "geographic_scope": "NATIONAL",
      "pipeline_run": "2026-03-27",
      "query_template": "A1",
      "cluster": "A",
      "pinned": false,
      "tags": ["permenkumham", "kitas", "sponsor"]
    }
  },

  "master_docs": {
    "change_log": {
      "nlm_note_id": "note-cl-001",
      "title": "[MASTER] Change Log — NB-2 Immigration",
      "last_updated": "2026-03-28T02:10:00+08:00",
      "word_count": 2847,
      "entry_count": 47,
      "content_hash": "sha256:a1b2c3d4..."
    },
    "operations_status": {
      "nlm_note_id": "note-os-001",
      "title": "[MASTER] Operations Status — NB-2 Immigration",
      "last_updated": "2026-03-28T02:10:00+08:00",
      "word_count": 1203,
      "entry_count": 12,
      "content_hash": "sha256:d4e5f6g7..."
    },
    "cross_domain": {
      "nlm_note_id": "note-cd-001",
      "title": "[MASTER] Cross-Domain Impacts — NB-2 Immigration",
      "last_updated": "2026-03-14T02:10:00+08:00",
      "word_count": 891,
      "entry_count": 6,
      "content_hash": "sha256:h8i9j0k1..."
    },
    "open_questions": {
      "nlm_note_id": "note-oq-001",
      "title": "[MASTER] Open Questions — NB-2 Immigration",
      "last_updated": "2026-03-28T02:10:00+08:00",
      "word_count": 1456,
      "open_count": 8,
      "resolved_total": 42,
      "content_hash": "sha256:l2m3n4o5..."
    }
  },

  "master_doc_snapshots": [
    {
      "date": "2026-03-28",
      "change_log": {
        "hash": "sha256:a1b2c3d4...",
        "words": 2847,
        "entries": 47
      },
      "operations_status": {
        "hash": "sha256:d4e5f6g7...",
        "words": 1203,
        "entries": 12
      },
      "cross_domain": {
        "hash": "sha256:h8i9j0k1...",
        "words": 891,
        "entries": 6
      },
      "open_questions": {
        "hash": "sha256:l2m3n4o5...",
        "words": 1456,
        "open": 8
      }
    }
  ],

  "dedup_stats": {
    "today": {
      "checked": 28,
      "rejected_url": 4,
      "rejected_content": 2,
      "rate_pct": 21.4
    },
    "this_week": {
      "checked": 145,
      "rejected_url": 22,
      "rejected_content": 11,
      "rate_pct": 22.8
    },
    "alarm_active": false,
    "alarm_reason": null
  }
}
```

### What This Tracks That NLM Does Not

| Field                             | Purpose                                   | NLM provides? |
| --------------------------------- | ----------------------------------------- | ------------- |
| `stage`                           | Lifecycle state machine                   | No            |
| `tier` + `tier_label`             | Source authority scoring                  | No            |
| `confidence.current` + `.history` | Quality gate + trend                      | No            |
| `claims[]`                        | Atomic claim extraction results           | No            |
| `claims_absorbed`                 | Consolidation readiness metric            | No            |
| `dedup.group`                     | Which sources cover same topic/regulation | No            |
| `pipeline_run`                    | Traceability to specific execution        | No            |
| `query_template`                  | Which query found this source             | No            |
| `reference_count`                 | Usage frequency (for pruning decisions)   | Partially     |
| `geographic_scope`                | Bali vs national vs other                 | No            |
| `pinned`                          | Operator override to prevent auto-archive | No            |

---

## 6. Cadence Matrix

### Daily (every pipeline run, 01:00-02:20 WITA)

| Time  | Task                    | Duration | Description                                                |
| ----- | ----------------------- | -------- | ---------------------------------------------------------- |
| 01:00 | Registry load           | <1s      | Load `nlm_nb2_source_registry.json`                        |
| 01:00 | Budget check            | <1s      | Count sources, determine pressure level (green/yellow/red) |
| 01:05 | Quarantine triage       | 2 min    | Score yesterday's quarantine sources → ACTIVE or DISCARD   |
| 01:10 | Pre-import filter (Q1)  | per src  | `should_import()` on each raw result from query 1          |
| 01:35 | Pre-import filter (Q2)  | per src  | `should_import()` on each raw result from query 2          |
| 01:55 | Claim extraction        | 5 min    | Extract atomic claims from today's new ACTIVE sources      |
| 02:00 | Open Questions check    | 2 min    | Do new findings resolve any OQ?                            |
| 02:05 | Master Doc micro-update | 3 min    | Add VERIFIED claims to Change Log, update Ops Status       |
| 02:10 | Staleness scan          | 1 min    | Flag ACTIVE sources with DeepSeek S(t) < 0.20 → ARCHIVE    |
| 02:12 | Dedup stats update      | <1s      | Update `dedup_stats.today`                                 |
| 02:13 | Emergency prune check   | 1 min    | If count > 70, execute pruning protocol                    |
| 02:15 | Registry save           | <1s      | Persist to disk                                            |

**Daily overhead: ~15 min** integrated into the existing 80-min pipeline window.

### Friday Consolidation (weekly, extends pipeline by ~25 min)

| Task                     | Duration | Description                                               |
| ------------------------ | -------- | --------------------------------------------------------- |
| Full dedup sweep         | 5 min    | Layer 3 across ALL ACTIVE sources (not just today's)      |
| Consolidation candidates | 3 min    | Identify ACTIVE with age > 14d AND >= 80% claims absorbed |
| Master Doc full update   | 5 min    | Write all 4 Master Docs with week's findings              |
| Open Questions review    | 3 min    | Close stale OQs, escalate overdue                         |
| Master Doc snapshot      | 2 min    | Save full text to `nlm_master_snapshots/YYYY-MM-DD/`      |
| Archive execution        | 3 min    | `source_delete` for CONSOLIDATE stage sources             |
| Denylist review          | 2 min    | Add domains with 3+ weekly discards                       |
| Weekly Telegram summary  | 1 min    | Source health metrics digest                              |
| Dedup stats weekly       | 1 min    | Compute `dedup_stats.this_week`, check alarms             |

**Total Friday overhead: ~25 min.** Pipeline window: 01:00 - ~02:45 (still before 03:00 scraper).

### Monthly Audit (last Friday of month, additional ~20 min)

| Task                      | Duration | Description                                                  |
| ------------------------- | -------- | ------------------------------------------------------------ |
| Source age histogram      | 3 min    | Distribution of ACTIVE sources by age. Alarm if median > 21d |
| Tier distribution         | 2 min    | ACTIVE by tier. Alarm if T5+T6 > 40%                         |
| Claim absorption audit    | 5 min    | Claims extracted vs absorbed. Target: > 80% within 14 days   |
| Master Doc quality review | 3 min    | Word count trends, entry count trends, stale sections        |
| Dedup monthly analysis    | 3 min    | Monthly rate vs prior month. Investigate if delta > 10pp     |
| Pre-import filter tuning  | 2 min    | Review rejection reasons. Tune if false positive > 10%       |
| Budget projection         | 1 min    | At current rates, any capacity concerns next month?          |
| Archive cleanup           | 1 min    | Purge archive records > 6 months (keep manifests)            |

**Monthly output:** `~/.agent/decisions/nlm_audits/YYYY-MM_monthly_audit.json`

### Quarterly Review Checklist

| #   | Task                         | Method                                                                |
| --- | ---------------------------- | --------------------------------------------------------------------- |
| 1   | Source accuracy spot-check   | Pick 10 random ACTIVE sources, verify URLs still live and accurate    |
| 2   | Master Doc accuracy check    | Pick 5 random Change Log entries, verify against JDIH                 |
| 3   | Query template effectiveness | Rank templates by avg SVS of sources they produced. Retire bottom 20% |
| 4   | Dedup algorithm calibration  | Is 0.85 cosine threshold right? Check false positive/negative rate    |
| 5   | Pipeline performance metrics | Avg sources/day, avg lifespan, avg SVS, trend lines                   |
| 6   | Domain denylist review       | Full review: blocking legit sources? Missing noisy ones?              |
| 7   | Cross-notebook comparison    | When NB-3+ live: check for cross-NB duplicate sources                 |

**Quarterly output:** `~/.agent/decisions/nlm_audits/YYYY-QN_quarterly_review.json`

---

## 7. Telegram Weekly Health Summary

Every Friday, the consolidation phase sends:

```
📊 NB-2 Source Health — Week of 2026-03-24

Sources: 42/70 (60%)
  ACTIVE: 34 | QUARANTINE: 3 | CONSOLIDATE: 5
  Imported: 67 | Archived: 12 | Net: +3

Dedup: 23% (145 checked, 33 rejected)
  ⚠ Warning if > 20% for 2nd consecutive week

Tiers: T0-1: 8 (24%) | T2-3: 12 (35%) | T4: 6 (18%) | T5-6: 8 (24%)

Claims: 18 new, 14 absorbed (78% rate)
  Target: ≥80%

Open Questions: 8 open, 3 resolved
  Oldest: OQ-047 (8d) Ngurah Rai degree req

Master Docs: 4/4 updated ✅
  Change Log: 2,847w (47 entries)
  Ops Status: 1,203w (12 entries)
  Cross-Domain: 891w (6 entries)
  Open Qs: 1,456w (8 open, 42 resolved)

NHS: 0.78 (stable ✅)
```

---

## 8. Key Differences from DeepSeek R1 Perspective

This Codex document complements `04_source_management.md` (DeepSeek R1). Here's what each covers best:

| Aspect                     | DeepSeek R1 (04)                                   | Codex (04b)                                              |
| -------------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| Staleness formula          | Exponential decay with type-specific half-lives ✅ | References DeepSeek's formula                            |
| Source Value Score (SVS)   | Full formula with 5 factors + bonus ✅             | Uses DeepSeek's SVS for pruning                          |
| Dedup overlap metric       | Szymkiewicz-Simpson coefficient ✅                 | Uses same, adds URL normalization code                   |
| Capacity projections       | Week-by-week math with failure scenarios ✅        | Import arithmetic + pre-import filter                    |
| Notebook Health Score      | Composite formula with 5 factors ✅                | References DeepSeek's NHS                                |
| Consolidation formula      | Information Loss Metric (ILM) ✅                   | References DeepSeek's consolidation                      |
| **Lifecycle transitions**  | 7 states with basic flow                           | **14 numbered transitions with conditions + SLAs**       |
| **Master Doc content**     | Table with refresh cadence                         | **Full markdown templates for all 4 docs**               |
| **Master Doc as notes**    | "Master digest sources"                            | **NLM Notes (not sources) — doesn't count vs 600 limit** |
| **Pre-import filter**      | Mentioned in capacity model                        | **Full `should_import()` pseudocode**                    |
| **Source registry schema** | Health dashboard JSON                              | **Full registry schema (25+ fields per source)**         |
| **Cadence matrix**         | Decision tables (daily/weekly/monthly/quarterly)   | **Minute-by-minute pipeline integration**                |
| **Emergency pruning**      | Active capacity management                         | **5-priority cut order with prune_score**                |
| **Versioning**             | Not covered                                        | **Friday snapshots + content hashes**                    |
| **Telegram summary**       | Alert routing table                                | **Full message template**                                |

**For the final merged spec:** combine DeepSeek's formulas (staleness, SVS, NHS, ILM, capacity math) with Codex's operational structures (lifecycle transitions, Master Doc templates, registry schema, pre-import filter, cadence matrix).
