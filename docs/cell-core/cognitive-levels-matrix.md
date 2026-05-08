# Cognitive Levels classification matrix — 14 cells

The brainstorm round 2 (`99b_synthesis_v2.md`) settled on **14 cell
candidates** distributed across L0-L4.5. This doc is the working
matrix per-cell with: status / source automation / 7 Leggi pre-check
(via `cell_core.admission_test`) / sprint target.

The "7 Leggi pre-check" column is **NOT** a runtime test result — it's
my offline judgment on whether the cell would PASS or FAIL each Legge
TODAY, given current implementation. Where I see a likely warning or
blocker, I list the remediation Sprint that addresses it.

## Legend

- **Status:** `existing` (cell or pre-cell automation runs in production now)
  / `existing → light promotion` (would just need declarative formalisation)
  / `NEW` (significant new implementation work)
- **7 Leggi pre-check:** ✅ pass / ⚠️ warning / ❌ blocker, in order
  CLI / OSINT / Event / Graceful / Zero / Local / Numbers
- **Sprint target:** the sprint that delivers the cell promotion (per
  99b_synthesis_v2.md sprint plan)

## Matrix

| # | Cell name | Level | Status | Source automation | 7 Leggi pre-check | Sprint target |
|---|---|---|---|---|---|---|
| 1 | `system-doctor-cell` | L1 | existing | cron-agent-python `system_doctor.py` | ✅✅⚠️✅✅✅✅ | Sprint 4 |
| 2 | `seo-guardian-cell` | L1 | existing | `apps/evaluator/seo_cell` + LaunchAgents | ✅✅⚠️✅✅✅✅ | Sprint 4 |
| 3 | `fact-checker-cell` | L1 | existing | cron-agent-python `fact-checker` | ✅✅⚠️✅✅✅✅ | Sprint 4 |
| 4 | `tech-orchestrator-cell` | L1 | existing | cron-agent-python `tech-orchestrator` | ✅✅⚠️✅✅⚠️✅ | Sprint 4 |
| 5 | `conversation-trainer-cell` | L1 | existing | cron-agent-python `conversation-trainer` | ✅✅⚠️✅✅✅✅ | Sprint 4 |
| 6 | `daily-ops-cell` | L1 | existing | cron-agent-python `daily-ops` | ✅✅⚠️✅✅✅✅ | Sprint 4 |
| 7 | `crm-cell` ⭐ NEW | L1 | NEW (consolidated 13 CRM auto) | `crm_automation_engine.py` + `practice_status_listener` + `proactive_compliance_monitor` + lead-scoring + ... | TBD Sprint 3 | Sprint 3 |
| 8 | `intel-scraper-cell` (light) | L1 | existing → light promotion | `apps/bali-intel-scraper/` + cron-agent-python `intel-radar` + `intel-feed-processor` | ✅✅✅✅✅⚠️✅ | Sprint 1 |
| 9 | `hgt-coordinator-cell` ⭐ NEW | L2 | NEW (propose-only quarantine) | OpenClaw + Kimi K2.6 (deferred per Sprint 5 verdict) | ✅✅✅✅✅✅⚠️ | Sprint 1 |
| 10 | `gap-scanner-cell` | L2 | existing | cron-agent-python + Ollama local | ✅✅⚠️✅✅✅✅ | Sprint 6 |
| 11 | `kg-cell` | L2 | existing | knowledge-graph-builder cron | ✅✅⚠️✅✅✅✅ | Sprint 6 |
| 12 | `research-cell` | L2 | existing (NB pipelines orchestrator) | NB-2..NB-10 cron via NotebookLM | ✅✅⚠️✅✅✅✅ | Sprint 6 |
| 13 | `war-room-organism` | L3 | existing (federation 9-cognitive + 4-7 operational LA) | `apps/war-room` + Bali Dispatch (16 LA on Pro live) | ✅✅✅✅✅⚠️✅ | Sprint 2 |
| 14 | `mata-garuda-cell` ⭐ NEW | L4.5 | existing (apps/mata-garuda + zantara-media) → cell promotion | `apps/mata-garuda` 19-pipeline | TBD Sprint 3 | Sprint 3 |

⭐ = new cell from round 2 (not in round 1 list of 12).

## Per-cell remediation notes

### #1 `system-doctor-cell` — L1, Sprint 4

- **⚠️ Event-driven:** today emits Telegram alerts directly from
  `system_doctor.py`. Sprint 0 Track C2 framework (ObservedShellBus)
  will cover the run-trace. Cell-level events should also flow through
  `cognitive_event` channel via inserts on a TBD `system_doctor_alerts`
  table (Sprint 4 W1 work).

### #2 `seo-guardian-cell` — L1, Sprint 4

- Already exists as `apps/evaluator/seo_cell/`. Light promotion: declare
  in `organs_registry.yaml` (Innervation Genoma — file renamed 2026-05-08
  IG-3 from `genome.yaml`), formalize the metrics (SEO score, indexed pages,
  click-through-rate, CrUX scores).
- **⚠️ Event-driven:** seo-cell-daily.sh and seo-cell-28d-check.sh
  write JSON state files, no PG NOTIFY. Sprint 4 W1 wraps in
  ObservedShellBus.

### #3 `fact-checker-cell` — L1, Sprint 4

- cron-agent-python strategy. **⚠️ Event-driven:** today writes to local
  state file. Sprint 4 W1: emit `cognitive_event` on every fact-check
  verdict (high-confidence claim corrections feed Genome scars).

### #4 `tech-orchestrator-cell` — L1, Sprint 4

- **⚠️ Event-driven** AND **⚠️ Local sovereignty**: tech-orchestrator
  reads system-doctor's verdicts to decide escalations. That makes
  its decisions partly derived from another cell's reasoning. Sprint 4
  W1 mitigation: refactor so it reads ONLY substrate signals
  (CPU, latency, error counts) and computes its own verdict; explicitly
  NOT reading system-doctor's decision output.

### #5-6 `conversation-trainer-cell`, `daily-ops-cell` — L1, Sprint 4

- Routine ⚠️ Event-driven mitigations as in #1-3. No structural blockers.

### #7 `crm-cell` ⭐ NEW — L1, Sprint 3

- Consolidates 13 CRM automations. Pre-check TBD because the consolidated
  cell DOESN'T EXIST YET. Sprint 3 deliverable will run the admission
  test on the consolidated definition before promotion. Risk callouts
  for the round 2 brainstorm:
  - **Law 2 OSINT:** must NOT mix client PII with Intel Scraper feeds.
  - **Law 5 Auto-publish:** must NOT auto-send WhatsApp to clients
    (Sahira approval gate stays).

### #8 `intel-scraper-cell` (light) — L1, Sprint 1 W1 ✅ DELIVERED

- Per Sprint 0 Track B4: 3 production runners map onto this cell
  (`apps/bali-intel-scraper/`, intel-radar, intel-feed-processor).
- ✅ All 7 Leggi clean except a **⚠️ Local sovereignty** soft note:
  publishes to `trend_signals` which `dossier-compiler` consumes. As long
  as dossier-compiler reads the substrate, not the scraper's reasoning,
  Law 6 is fine.
- **Sprint 1 W1 delivery (2026-05-02):** declarative cell.yaml at
  `apps/bali-intel-scraper/cell.yaml` (passes
  `pytest packages/cell-core/tests/test_admission.py -k intel_scraper`
  with zero blockers); wrapper modules under
  `apps/bali-intel-scraper/backend/cell/`:
    * `scar_recorder.py` — Genome scars at namespace
      `intel.scraper.<source_slug>.<failure_kind>`, cross-run uses counter.
    * `hgt_publisher.py` — STRUCTURAL pattern broadcast on confidence ≥0.7
      with PII marker filter (defense-in-depth).
    * `event_bridge.py` — emits `intel.scraper.run` row per run via
      `ObservedShellBus` (migration 151).
    * `runner.py` — async-context-manager orchestrator with deterministic
      status (ok|degraded|failed), 35 unit/integration tests.
- **Out of scope for W1 (deferred):** integration into the scraper's
  actual entrypoint (`apps/bali-intel-scraper/backend/app/main.py` /
  cron-agent-python intel-radar / intel-feed-processor); that
  integration is a 1-PR follow-up tracked separately so reviewers can
  read the wrapper layer in isolation.

### #9 `hgt-coordinator-cell` ⭐ NEW — L2, Sprint 1

- The Symbiosis Confrontation pillar that's missing today (per round 2
  audit). Propose-only quarantine: the cell PROPOSES skill/scar deltas
  to the Genome but **does not auto-merge**. ✅ Law 5 satisfied via
  human review at merge time.
- **⚠️ Numbers first:** must declare confidence threshold ≥0.7 + ≥10
  uses gate as a metric on the cell definition (cf. brainstorm round 2
  unanime risk callout "HGT poisoning"). Sprint 1 deliverable will
  encode this as part of the cell's `metrics: [propose_count,
  merge_acceptance_rate, false_positive_rate, p99_latency_ms]`.

### #10 `gap-scanner-cell` — L2, Sprint 6

- No OpenClaw, Ollama local. ✅ Law 1 trivially. Sprint 6 routine
  observability mitigation for ⚠️ Event-driven.

### #11 `kg-cell` — L2, Sprint 6

- knowledge-graph-builder + KG auto-expansion (mig 077 onwards). Trigger
  on `kg_proposals` table → emits `cognitive_event` per insertion. Light
  promotion only — code path already exists.

### #12 `research-cell` — L2, Sprint 6

- NotebookLM NB-2..NB-10 pipeline orchestrator. Cron-driven; ⚠️ Event-driven
  is the standard mitigation.

### #13 `war-room-organism` — L3, Sprint 2

- Sprint 0 Track B1+B2 verified the 9 cognitive backbone organelle
  (oracle/strategos/connector/supervisor/pg-proxy/learner-nightly/
  trend-hunter/measurer/dossier-compiler) plus 4-7 operational organelle.
  All Event-driven via DB triggers (mig 112/113/114/138). ✅ Pass.
- **⚠️ Local sovereignty:** oracle L4 has decisional latitude — DeepSeek
  round 2 risk callout. Sprint 2 mapping doc will explicitly enforce
  "oracle proposes, war-room (council) decides". ✅ then.

### #14 `mata-garuda-cell` ⭐ NEW — L4.5, Sprint 3

- Asset indexer + multi-channel curator (`apps/mata-garuda` + `zantara-media`).
  19-pipeline today. Promotion to cell L4.5 (meta-awareness).
- Pre-check TBD — Sprint 3 deliverable will run admission test on the
  formalized definition. Round 2 risk callouts:
  - **Law 2 OSINT:** Mata-Garuda is INTENTIONALLY OSINT-blindato; Asset
    provenance schema must enforce source + confidence + owner +
    invalidation path (Codex round 2).
  - **Law 6 Local sovereignty:** Mata-Garuda CANNOT depend on
    war-room-organism's decisions — bidirectional innervation, NOT
    sub-cell.

## What's NOT in this matrix

- The **operational organelle** (newsletter, canva-apply, draft-generator,
  image-generator, topic-selector, sla-worker, hardening) inside
  `war-room-organism`. They are workflow steps, not cell candidates per
  Sprint 0 Track B1 verdict.
- **observed-shell tier automations** (translation, BI feeds, regulatory
  monitors, backups). They emit via Sprint 0 Track C2 framework but
  don't get cell status (would fail admission test on Law 7 — too few
  metrics, by design).
- The 18 `cron-agent-python` strategies that don't promote (oss-monitor,
  pajak-monitor, imigrasi-monitor, bi-exchange-rate, vision-doc,
  tdd-pipeline, log-anomaly-detector, fly-watcher). They stay
  cron-agent-python per Opzione C and may emit observed-shell events.

## How to use this matrix

When approaching a cell promotion in its target Sprint:

1. Re-run the admission test against the actual cell definition (YAML)
   at the time of promotion. The matrix's pre-check column is a 2026-05-02
   snapshot; reality may have drifted.
2. Address every ⚠️ in the pre-check column with a specific code or
   doc deliverable in the Sprint plan.
3. Block on ❌ — that cell is NOT ready for promotion. Re-classify it
   as organelle of a parent cell.

## References

- `packages/cell-core/cell_core/admission_test.py` (Track C1 framework)
- `docs/cell-core/admission-test-rubric.md` (Track C1 rubric)
- `apps/backend-rag/backend/services/events/observed_shell.py` (Track C2)
- `docs/audits/sprint0/wr2-ipc-mechanism.md` (Track B2 — WR2 IPC verdict)
- `docs/audits/sprint0/intel-scraper-main-path.md` (Track B4 — Intel Scraper)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md`
  § "Final list — 14 cell candidate"
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/05_cell_architecture_complete.md`
  § "Cognitive Levels L0-L4.5"
