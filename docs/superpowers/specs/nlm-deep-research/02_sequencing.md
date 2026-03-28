# Step 2: Sequencing — NB-2 Deep Research Pipeline

> Synthesis: Gemini + Codex GPT-5.4 + DeepSeek R1 (2026-03-28)
> Status: Brainstorm complete

---

## 1. Daily Pipeline Architecture

### Timeline Consensus

All 3 AI agree on the core structure but diverge on timing. Key constraint: intel scraper (03:00), NB-1 refresh (04:30), team start (08:00).

| Phase             | Gemini (tight)   | Codex (detailed) | DeepSeek (generous) |
| ----------------- | ---------------- | ---------------- | ------------------- |
| Scraper gate      | 03:30            | 03:20            | 03:30               |
| Signal collection | 03:35-03:40      | 03:20-03:45      | 03:30-04:00         |
| Query planning    | (inline)         | 03:45-04:10      | 04:00-04:30         |
| NB-1 refresh      | 04:30 (existing) | 04:30-05:00      | 04:30-05:00         |
| **First query**   | **03:40**        | **05:00**        | **05:15**           |
| **Second query**  | **04:00**        | **05:20**        | **06:15**           |
| Consolidation     | 04:15-04:25      | 06:30-07:15      | 07:00-07:15         |
| Team handoff      | 04:25 (ready by) | 07:45 (ready by) | 08:00 (ready by)    |

### Key Divergence: Before or After NB-1 Refresh?

- **Gemini**: Run NB-2 BEFORE NB-1 refresh (03:40-04:25), finish before 04:30
- **Codex**: Run NB-2 AFTER NB-1 refresh (05:00-06:30), NB-1 as upstream context
- **DeepSeek**: Run NB-2 AFTER NB-1 refresh (05:15-08:00), most generous timing

**Resolution**: Gemini's approach is best because:

1. NB-2 (immigration) has zero dependency on NB-1 (codebase) — no upstream context needed
2. Finishing by 04:25 means results are ready 3.5 hours before team starts
3. No NLM API contention (different API surfaces: NB-2 uses research_start, NB-1 uses source add)

### Recommended Timeline

> **ARCHITETTURA CRITICA: NLM Deep Research e' UPSTREAM rispetto all'intel scraper.**
> NLM gira PRIMA dello scraper e produce un report verificato che lo scraper riceve in input.
> Lo scraper ha gia' materiale analizzato e puo' decidere se arricchirlo per farne un articolo.
> Il tema puo' poi essere scelto come topic giornaliero dalla War Room.
>
> Flusso: NLM Deep Research (01:00-02:30) → Report → Intel Scraper (03:00) → War Room

```
01:00  NB-2 PIPELINE START
01:05  PHASE 1: Signal collection (5 min)
         - Read yesterday's state file (hot_topics, known_regulations)
         - Check hot_topics decay (age each signal, drop if >7 days)
         - Select today's cluster from rotation
         - Read previous scraper output (yesterday's articles, for context)
01:10  PHASE 2: Query 1 — L1 Monitoring (20 min)
         - research_start(mode=deep)
         - research_status(poll_interval=30, max_wait=600)
         - research_import(filtered sources)
         - notebook_query(verification prompt)
         - Save results + evaluate signals
01:30  PHASE 3: Inter-query assessment (5 min)
         - Parse L1 for breaking signals
         - If BREAKING → override L2 with targeted query
         - If NORMAL → proceed with scheduled L2
         - Inject L1 context snippet into L2 query
01:35  PHASE 4: Query 2 — L2 Comparative (20 min)
         - research_start with L1 context prefix
         - Same verify/import/save cycle
01:55  PHASE 5: Consolidation + Report Generation (15 min)
         - Generate daily_intelligence_brief.json:
           {key_findings, new_regulations, confidence_scores,
            suggested_article_topics, cluster, hot_topics}
         - Write brief to: ~/.agent/decisions/nlm_briefs/YYYY-MM-DD.json
         - Write NLM note in NB-2 with daily summary
         - Telegram notification (if high-value findings)
         - Persist pipeline state
02:10  PHASE 6: Scraper Handoff Package (10 min)
         - Generate scraper_input.json from brief:
           {verified_topics: [...], suggested_angles: [...],
            regulation_refs: [...], confidence_per_topic: {...}}
         - Write to: ~/.agent/decisions/nlm_to_scraper/latest.json
         - This file is what intel scraper reads at 03:00
02:20  PIPELINE COMPLETE

02:20-03:00  BUFFER (40 min safety margin)

03:00  INTEL SCRAPER starts (Pro, OpenClaw)
         - Fa il suo lavoro AUTONOMAMENTE come sempre (scraping siti news, pubblicazione articoli)
         - IN PIU': ha a disposizione nlm_to_scraper/latest.json come contesto aggiuntivo
         - Lo scraper NON dipende dal brief NLM — se il file non c'e', gira uguale
         - Il brief NLM e' un ARRICCHIMENTO: temi gia' verificati che lo scraper
           puo' usare per cross-validare o per dare priorita' editoriale
03:30  Scraper complete → articles published

04:30  NB-1 code refresh (existing, no conflict)

08:00  TEAM START
         - Daily Intelligence Brief ready in Telegram
         - Scraper articles already published
         - War Room can pick NLM topics as daily themes

14:00  PHASE 7 (CONDITIONAL): Afternoon follow-up
         - Only if morning detected breaking signal OR manual trigger
         - 1 fast research (mode=fast, ~3 min)
         - Clears override flag
```

**Total daily window: 01:00-02:20 WITA (~80 minutes), 2 deep research queries + report generation.**
**40 minutes buffer before scraper at 03:00.**

### Per-Query Timing Budget

| Component                   | Time          | Note                        |
| --------------------------- | ------------- | --------------------------- |
| research_start              | 1 min         | API call initiation         |
| research_status polling     | 8-12 min      | Deep mode typical           |
| research_import             | 2-3 min       | Filter + import top sources |
| notebook_query verification | 2 min         | Summarize findings          |
| State persistence           | 1-2 min       | Write JSON                  |
| **Total per query**         | **15-20 min** | Hard timeout: 25 min        |

---

## 2. Inter-Query Dependencies

### Consensus: Semi-sequential with context injection (3/3)

All agree: Query B should depend on Query A, but through a **lightweight transformation**, not raw prose forwarding.

**Mechanism:**

1. After L1 completes, extract key entities: new regulation numbers, changed rules, dates, affected visa types
2. Build context snippet (max 200 words / 3 key findings)
3. Prepend to L2 query template as `CONTEXT:` prefix
4. If L1 found nothing material → run L2 as-is (no forced chaining)

**Example flow:**

```
L1 result: "Permenkumham 8/2026 memperluas kategori KITAS sponsor..."
   ↓ extract
Context snippet: "Permenkumham 8/2026, KITAS sponsor expansion, effective April 2026"
   ↓ inject
L2 query: "CONTEXT: Permenkumham 8/2026 perubahan sponsor KITAS.
           Bagaimana kebijakan KITAS sponsor Indonesia 2026 dibandingkan
           Thailand Smart Visa dan Malaysia EP?"
```

**Why NOT full sequential chain:**

- NLM Deep Research cannot read its own previous results programmatically
- `research_start` takes a query string and searches independently each time
- Only chaining mechanism: us injecting context text into the query string
- Fully sequential (write L1 as NLM note, then query against it) adds complexity with marginal benefit

**Codex unique insight — structured extraction between queries:**

```
Extract from A:
  - new_entities
  - new_dates
  - changed_rules
  - contradictions
  - missing_confirmations
  - affected_nationalities / visa_types

Convert to:
  - hypotheses_confirmed
  - hypotheses_open
  - must_verify_with_primary_source
  - followup_targets

B is modified using ONLY these fields (not raw prose)
```

---

## 3. Breaking News Override

### Detection: 3-layer (Gemini), score-based (Codex), keyword+threshold (DeepSeek)

**Merged detection approach:**

> **NOTE:** Times below match the adopted 01:00-02:20 upstream pipeline window.
> Layer 1 reads YESTERDAY's scraper output (scraper runs at 03:00, after NLM).

| Layer                           | Source                           | What to check                                                                                                                                                      |
| ------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 — Yesterday's scraper (01:05) | Intel scraper output (yesterday) | Regex: `(UU\|PP\|Permen\|Permenkumham)\s+\d+\s*Tahun\s*202[5-9]`. Hot keywords: `moratorium`, `larangan`, `dicabut`, `darurat`. Density: 3+ articles on same topic |
| 2 — L1 result (~01:30)          | NLM response from today's query  | New regulation number not in `known_regulations` set. Recency phrases: `baru saja`, `efektif per`, `mulai berlaku`. 5+ unique sources for single finding           |
| 3 — Manual (anytime)            | Telegram command                 | `/nlm_override "description" cluster=X priority=critical`                                                                                                          |

**Scoring (Codex approach):**

```
source_authority: 0-30
novelty: 0-20
breadth: 0-20
compliance_risk: 0-20
contradiction: 0-10
Total >= 75 → BREAKING override
Total >= 90 → CRITICAL (immediate team alert)
```

**Override behavior:**

1. Replace scheduled L2 with emergency focused query (not add — budget discipline)
2. Schedule afternoon follow-up (Phase 6) automatically
3. Telegram alert immediate
4. Override persists 72h (3 daily cycles), then auto-decay
5. Pushed scheduled query goes to tomorrow (not dropped)

**Escalation classification (Codex):**

- `confirmed critical` → team alert before 08:00
- `probable critical` → watch alert + priority query tomorrow
- `unconfirmed rumor` → monitoring flag only, no schedule disruption

---

## 4. Weekly/Monthly Cadence

### Weekly Rotation

| Day     | L1 Cluster        | L2/L3             | Afternoon         | Notes                                     |
| ------- | ----------------- | ----------------- | ----------------- | ----------------------------------------- |
| **Mon** | A (Work permits)  | L2 comparative    | —                 | Fresh week, highest-volume                |
| **Tue** | B (Stay permits)  | L2 comparative    | —                 |                                           |
| **Wed** | C (Visit visas)   | L2 comparative    | —                 |                                           |
| **Thu** | D (Special visas) | **L3 predictive** | —                 | Strategic day: synthesize Mon-Wed signals |
| **Fri** | E (Compliance)    | L2 comparative    | **Consolidation** | Weekly brief generation                   |
| **Sat** | —                 | —                 | —                 | OFF (govt gazette Mon-Fri only)           |
| **Sun** | —                 | —                 | —                 | OFF                                       |

### L4 Cross-Domain: Monthly Only

- First Thursday of each month, replaces L3 slot
- Queries span NB-2 + NB-3 (company) + NB-4 (tax)

### Friday Consolidation (exact scope)

```
1. AGGREGATE: Read Mon-Fri daily state files
2. DEDUPLICATE: Same regulation found on multiple days = 1 finding
3. RANK: By recurrence × source diversity × client impact
4. WEEKLY BRIEF: JSON + Telegram digest
   - top_findings (ranked)
   - new_regulations (with status)
   - cluster_coverage map
   - follow_ups_pending
   - next_week_priority
5. NLM NOTE: Write weekly summary as note in NB-2
6. ARCHIVE: Move daily states to weekly/ subdirectory
```

### Monthly Master Brief

- **Trigger**: Last Friday of month, after normal consolidation
- **Content**: Aggregated weekly briefs + regulatory landscape delta + trend analysis + pipeline health metrics
- **Fully automated** except `recommendations` field (human review flag)

### Quarterly Audit (checklist)

1. Source freshness: expired PDFs?
2. Query template relevance: retire dead, add new
3. Cluster balance: override skew?
4. Signal decay: anything stuck >30 days?
5. Budget review: API calls, cost, rate limit incidents
6. Accuracy spot-check: 3 random weekly briefs vs official gazette
7. Pipeline drift: execution times growing?

---

## 5. Rate Limiting & Backpressure

### Budget Strategy: Conservative Start

| Period                 | Queries/day          | Total/week  | Note                     |
| ---------------------- | -------------------- | ----------- | ------------------------ |
| Week 1-2 (calibration) | 2 deep + 0-1 fast    | 10-15       | Measure NLM behavior     |
| Week 3-4 (expansion)   | 2 deep + 1 verify    | 15-20       | If no throttling         |
| Month 2+ (steady)      | 2 deep + conditional | 10-15       | Drop afternoon if stable |
| **Never exceed**       |                      | **40/week** | Hard budget cap          |

### Timeout Handling

> **NOTE:** Times below match the adopted 01:00-02:20 upstream pipeline window.

| L1 finish time | Action on L2                                     |
| -------------- | ------------------------------------------------ |
| Before 01:45   | L2 runs normally (deep mode)                     |
| 01:45-02:00    | L2 runs in fast mode (saves ~10 min)             |
| After 02:00    | L2 SKIPPED, pushed to afternoon fast             |
| After 02:25    | L1 itself killed (hard timeout), pipeline FAILED |

02:25 hard deadline = 5 min buffer before INV-9 at 02:30, 30 min before scraper at 03:00.

### Throttle Detection

| Signal                          | Indicator                                 |
| ------------------------------- | ----------------------------------------- |
| Source count < 3 on deep query  | Expected: 15-40. Flag: POSSIBLY_THROTTLED |
| Response < 100 words            | Flag: POSSIBLY_EMPTY                      |
| Identical response to yesterday | Flag: POSSIBLY_CACHED                     |
| 2+ flags same week              | Reduce to 1 query/day for 3 days          |
| 3+ flags same week              | PAUSE pipeline, Telegram alert            |

### Queue States (Codex)

```
planned → ready → running → cooldown → completed
                         ↘ timed_out
                         ↘ cancelled
            ↘ blocked_on_dependency
            ↘ deferred
```

---

## 6. Orchestration State

### State File Location

`apps/evaluator/nlm_nb2_pipeline_state.json`
(matches existing pattern: `coverage_state.json`, `indexing_state.json`)

### State Schema (synthesis of all 3 AI)

```json
{
  "version": 1,
  "pipeline_status": "IDLE|COLLECTING|RUNNING_L1|ASSESSING|RUNNING_L2|CONSOLIDATING",
  "last_run": {
    "date": "2026-03-28",
    "started_at": "...",
    "completed_at": "...",
    "duration_s": 2820,
    "queries_executed": 2,
    "status": "SUCCESS|PARTIAL|FAILED"
  },
  "today": {
    "cluster": "A",
    "l1_status": "COMPLETED|RUNNING|FAILED|null",
    "l1_task_id": "abc-123",
    "l1_sources_imported": 12,
    "l1_key_findings": ["..."],
    "l1_confidence": 0.73,
    "l2_status": "...",
    "l2_task_id": "...",
    "l2_sources_imported": 8,
    "l2_key_findings": ["..."],
    "l2_confidence": 0.61,
    "afternoon_triggered": false
  },
  "rotation": {
    "cluster_schedule": ["A","B","C","D","E"],
    "last_cluster_run": {"A":"2026-03-24", "B":"2026-03-25", ...}
  },
  "override": null | {
    "trigger": "...",
    "signal": "Permenkumham 8/2026",
    "detected_at": "...",
    "expires_at": "...",
    "source": "l1_result|scraper|manual"
  },
  "hot_topics": [{
    "signal": "...",
    "first_seen": "...",
    "last_seen": "...",
    "occurrences": 3,
    "decay_score": 0.85,
    "cluster": "A"
  }],
  "known_regulations": ["UU 6/2023", "Permenkumham 22/2023", ...],
  "errors": {
    "consecutive_failures": 0,
    "throttle_flags": 0,
    "backoff_until": null
  },
  "budget": {
    "week_calls": 12,
    "week_limit": 40,
    "month_calls": 45,
    "month_limit": 160
  }
}
```

### Crash Recovery

```
If l1_status == "COMPLETED" and l2_status != "COMPLETED" → resume at RUNNING_L2
If l1_status == "RUNNING" and task_id exists → poll existing task (NLM persists server-side)
If l1_status == null → start from COLLECTING_SIGNALS
If both completed → resume at CONSOLIDATING
```

Key: `research_status` accepts `task_id`, so we can resume polling a research started before crash.

### Dedup Guard

```
dedup_key = hash(template_id + cluster + date)
Before enqueue: if same dedup_key completed today → skip
```

Handles the macOS launchd quirk where cron fires twice.

### Event History (Codex addition)

Append-only `query_history.jsonl` alongside the mutable `pipeline_state.json`:

- Per-query: template_id, cluster, level, started_at, duration, result_class, entities_found, confidence
- Enables quarterly performance audit without parsing state snapshots

---

## Source AI Contributions

### Gemini — Best on architecture + timing

- Tight 03:30-04:25 window (before NB-1, no contention)
- 7-state state machine with crash recovery via task_id polling
- Most detailed state schema with known_regulations set
- 72h override with auto-decay

### Codex — Best on discipline + edge cases

- Structured extraction between queries (not raw prose)
- Slot-based budget (not just count): time + query + emergency reserve
- Queue states: planned→ready→running→cooldown→completed/timed_out/cancelled
- Event history as append-only JSONL alongside mutable state JSON
- Score-based breaking news (75 threshold, 90 critical)
- Friday consolidation as full scope definition

### DeepSeek — Best on thoroughness

- DAG-based dependency graph for parallel+sequential hybrid
- 45 min per-query estimate (most conservative, good for initial calibration)
- 3-tier priority queue: breaking(10) > sequential-dependent(7) > independent(5)
- PostgreSQL suggestion for state (overkill for us, but correct for scale)
- SHA-256 dedup on template+params+date range

---

## Key Decisions Summary

| Decision     | Choice                                     | Rationale                                                                          |
| ------------ | ------------------------------------------ | ---------------------------------------------------------------------------------- |
| Daily window | **01:00-02:20 WITA**                       | **UPSTREAM of scraper (03:00). NLM produces verified report, scraper consumes it** |
| Queries/day  | 2 deep + 0-1 conditional                   | Conservative for unknown rate limits                                               |
| Inter-query  | Semi-sequential, context snippet           | NLM can't chain natively                                                           |
| Override     | 72h auto-decay, score >= 75                | Prevents permanent rotation bias                                                   |
| Weekend      | OFF                                        | Indonesian gazette Mon-Fri only                                                    |
| L3           | Weekly (Thursday)                          | Needs Mon-Wed accumulated context                                                  |
| L4           | Monthly (1st Thursday)                     | Cross-domain is expensive                                                          |
| State        | JSON in apps/evaluator/                    | Matches existing patterns                                                          |
| Recovery     | task_id polling after crash                | NLM tasks persist server-side                                                      |
| Backoff      | 3 failures OR 3 throttle flags → 48h pause | Budget protection                                                                  |
