---
date: 2026-06-11
domain: operations
client_case: none
sources:
  - disk-state verification 2026-06-11 (launchctl, plists, scripts/, ~/.claude/skills/bali-zero-brand/, deploy worktree)
  - live Fly Postgres via postgres-nuzantara MCP (system_settings, war_room_drafts, topic_type_log, wr2_* tables, events_outbox, pg_proc trigger body)
  - research/operations/2026-06-04-wr2-autopsy-report.md (leads re-verified per anti-hallucination rule)
  - PR #1228 (3bc4a7cb9), PR #1236 (bf5e5bb69), PR #1275 (a45c67909), PR #1125, PR #1133 (migration 216), migration 164
  - memories: decision_wr2_renderer_html_css_over_canva_2026_06_06, audit_system_fable5_2026_06_11 (F23), wr2_html_renderer_convergence_chain_2026_06_10
  - 4-LLM asymmetric panel 2026-06-11 (§6): Gemini agy red-team, Codex GPT-5.5 constructive, DeepSeek V4 Pro logic — every load-bearing panel claim re-verified on disk by the orchestrator
---

# P-1 — WR2 Pipeline Consolidation Spec (REV 2, post-panel)

**Status**: REVISED after 4-LLM panel — awaiting Antonello GO. Nothing merged to main.
**Scope**: architectural consolidation of the WR2 carousel pipelines into one. The renderer
decision (HTML/CSS → PNG via Playwright) is ALREADY MADE AND SHIPPED (PR #1236, flag ON since
2026-06-09 15:46 UTC) and is NOT re-litigated here.
**Hard rules honored**: Legge 5 (no software IG publish — terminal status stays `rendered`,
human publishes manually), Legge 7 (every stage has a before/after metric), anti-hallucination
(every file:line below was re-verified on disk in this session, including every panel claim).

**REV 2 delta**: incorporates 24 panel findings — Gemini red-team 7 (1 BLOCKER, 3 HIGH),
Codex constructive 12, DeepSeek logic 5. Material changes: S1 implementation moved out of
`_pg.py` (package-boundary crash risk), watchdog re-key extended to telemetry source
(degrade-open blindness), `wr2_worktree_gc.py` dependency on `wr2_carousel_runs` discovered
(would crash on table drop), worker drain-loop added (supervisor kickstart starvation),
Gate 0 hardened, metrics M1/M2/M6 made strictly falsifiable.

---

## §1 GROUND — verified on-disk map (2026-06-11)

### 1.1 The actual state is THREE generations, not two

| Gen | Name | Where | State today |
|---|---|---|---|
| 1 | Skill-cortex agent pipeline (May) | `~/.claude/skills/bali-zero-brand/_*.py` + SQLite state | Semi-stale; 2 LaunchAgents still loaded |
| 2 | **Pipeline A** — scripts orchestrator | `scripts/wr2_carousel_orchestrator.py` + dispatcher + telegram gate | DEAD: all 3 LaunchAgents disabled (F23, 2026-06-11) |
| 3 | **Pipeline B** — live draft lane | `scripts/wr2_topic_selector.py` → … → `scripts/wr2_html_render_apply.py` | LIVE but degraded: motor off, mid-chain unscheduled, 3 operational blockers |

### 1.2 Pipeline A (gen-2) — dead, with evidence

| Component | Verification (this session) | Result |
|---|---|---|
| `scripts/wr2_carousel_orchestrator.py` (37KB) | `git log -1 -- <file>` | last commit `acbf5228a` 2026-05-28 (#894) |
| `scripts/wr2_carousel_dispatcher.py` | `grep -rn topic_ready` whole repo | **2 hits, both inside the dispatcher itself** — `topic_ready` has NO producer anywhere; the only consumer is this disabled dispatcher. Doubly dead. |
| `scripts/wr2_telegram_publish_gate.py` | `git log -1` | last commit 2026-05-28 (#901) |
| LaunchAgents `com.balizero.wr2.{carousel-dispatcher,telegram-gate,supervisor}` | `launchctl print-disabled gui/501` | all `=> disabled` (F23); not in `launchctl list` |
| `publish_after_approval()` orchestrator:818-906 | `sed -n '818,906p'` | REAL Meta Graph publish call (`IGPublisher().publish`) + `transition_state(..., "published")` — **a Legge 5 violation living in dead code** |
| `backend/services/publisher/ig_publisher.py` | `grep -rn IGPublisher` | runtime callers: ONLY the dead orchestrator. `service_initializer.py:1021-1040` validates IG credentials at every backend startup for this dead path; lifespan close hook `app_factory.py:604` |
| A-state tables | live PG query | `wr2_carousel_runs` = 11 rows (May test runs), `wr2_orchestrator_metrics` = 46, `wr2_carousel_events_outbox` = 0, `wr2_publish_attempts` = **0 rows ever** |
| ⚠️ `wr2_carousel_runs` HAS a live reader | red-team finding, re-verified: `grep -n wr2_carousel_runs scripts/wr2_worktree_gc.py` | **`wr2_worktree_gc.py:90`** (`com.balizero.wr2.worktree-gc.daily`, loaded) SELECTs it to protect in-flight worktrees — table drop without patching GC first = daily crash |
| A tests | `ls scripts/tests/` | `test_wr2_carousel_orchestrator.py`, `test_wr2_telegram_publish_gate.py`, `apps/backend-rag/backend/tests/services/publisher/test_ig_publisher.py` exist — must go in R1 |
| Wrappers | plist ProgramArguments | `~/scripts/wr2-carousel-dispatcher-wrapper.sh`, `~/scripts/wr2-telegram-gate-wrapper.sh` (HOME copies). Repo has only `infra/launchagents/com.balizero.wr2.carousel-dispatcher.plist.example` — live plists are HOME-only |

### 1.3 Pipeline B (gen-3) — the live lane, status flow verified per script

```
topic_selector (cron 05:10 WITA)            INSERT war_room_drafts status='briefed'
  └─ scores staging items from backend API; mata-garuda wr2-bridge.hourly feeds intel upstream
draft_generator   (MAX_DRAFTS_PER_RUN=2)  'briefed'              → 'drafts' | 'rejected'
image_generator                            'drafts'               → 'drafts_imaged' | 'image_failed'
fact_extractor                             'drafts_imaged'        → 'drafts_imaged_facted'
fact_checker                               'drafts_imaged_facted' → 'drafts_imaged_checked' | 'fact_check_failed'
html_render_apply (MAX_DRAFTS_PER_RUN=1)  'drafts_imaged_checked' → CAS lease 'rendering' →
                    'rendered' + drive_url + wa_outbox notify (Antonello + Damar)
                  | 'rendered_shadow' (WR2_HTML_SHADOW=1)
                  | 'render_failed' (after 3 attempts, _html_attempts circuit breaker)
```

Failure statuses are **intentionally terminal-manual** (DeepSeek finding 1, resolved by naming
the consumers): `rendered`/`fact_check_failed` → supervisor Telegram alert (ALERT_STATUSES);
`render_failed` → `_ops_alert` (html_render_apply); `rejected`/`image_failed` → log only,
surfaced by the (re-keyed, §2 S10) watchdog frozen-check.

Terminal SOFTWARE status = `rendered`. Human gate = WhatsApp message with Drive link
(durable `wa_outbox`); Damar publishes manually. **No IG/Graph call anywhere in the live lane.**

Kill-switches (live PG `system_settings`, queried this session):

| key | value | updated |
|---|---|---|
| `wr2_html_renderer_enabled` | **true** | 2026-06-09 15:46 |
| `wr2_canva_desktop_apply_enabled` | **false** | 2026-06-09 15:47 |
| `wr2_canva_renderer_enabled` | false | 2026-05-15 |
| `wr2_fact_checker_enabled` / `wr2_fact_extractor_enabled` | true | — |

Runtime home: every B stage runs from the **deploy worktree** `~/Desktop/nuzantara-deploy`
(via `~/.openclaw/bin/wr2/wr2-script-wrapper.sh`; html-apply inline-bash pins
`WR2_REPO_ROOT=$HOME/Desktop/nuzantara-deploy` + dedicated `.venv-wr2-html`). Verified:
deploy worktree at `984edce37` = origin/main, **0 behind**, includes #1275. HOME-fork rule:
repo `scripts/` is source of truth; production picks fixes up only after merge + deploy-puller.

### 1.4 The motor is OFF — B advancement today is degraded, not absent

(REV 2: corrected after panel — REV 1 wrongly said "no automatic advancement" and "NOTIFY
into the void".)

- Schedules verified with `plutil -p` on ALL stage plists: **topic-selector 05:10 cron;
  html-apply `StartInterval=600`** (HOME + repo `infra/launchagents/` copies agree);
  draft-generator / image-generator / fact-extractor / fact-checker / canva-apply have **no
  schedule and no RunAtLoad** — they exist to be kickstarted by the supervisor.
  ⇒ today the chokepoint self-polls every 10 min, but the **mid-chain
  (briefed→drafts→drafts_imaged→facted→checked) advances only on manual kickstart**.
- `wr2_supervisor.py` = B's event-driven motor: LISTEN `wr2_status_change` → kickstart next
  stage + startup `_replay_outbox()` + periodic reconcile (default 300s interval,
  `WR2_RECONCILE_STALE_MIN` staleness). **Disabled** (F23). 28,615 heartbeat rows prove it ran for weeks.
- The channel IS durable (REV 1 error): live trigger body (queried from `pg_proc`) inserts
  into `events_outbox` + `pg_notify` with `_outbox_id` (migration 164). Live counts: 251
  events, **0 unconsumed** (last ack 2026-06-11 02:03 — an external drain acks the channel
  even with the supervisor down). Red-team's "unbounded bloat" claim is empirically false
  today, and replay-on-enable is bounded (last 500, deduped, status re-read makes stale
  events no-ops).
- `wr2_supervisor.py` maps are STALE for the cutover: **both** `TRANSITIONS:97` **and**
  `NONTERMINAL_TO_NEXT_STAGE:109` route `drafts_imaged_checked` work to
  `com.balizero.wr2.canva-apply` (flag-OFF). Re-enabling unpatched = motor kicks the dead lane.
- **Supervisor drain-assumption contradiction (red-team BLOCKER, verified)**: supervisor
  kickstarts without `-k` assuming "workers drain ALL pending drafts in one bulk SELECT"
  (wr2_supervisor.py:20-22) — but `wr2_html_render_apply.py:61` caps at
  `MAX_DRAFTS_PER_RUN=1` and `wr2_draft_generator.py:50` at 2. A busy worker swallows the
  kickstart; the new draft waits for reconcile (≥30 min staleness). At current volume
  (1-3 drafts/day) this is latency, not loss — but it contradicts the motor's design and
  must be aligned (§4 R4 drain-loop).
- `wr2_supervisor_watchdog.py` (loaded, KeepAlive) is **fully Canva-keyed** (verified):
  gate flag `wr2_canva_renderer_enabled` (:187-206), success-rate telemetry
  `~/logs/wr2_canva_apply_telemetry.jsonl` (:79), freshness column `canva_applied_at` (:37).
  Logs confirm: `pipeline_frozen check skipped (canva-renderer kill switch OFF)`. Worse
  (red-team HIGH, verified :269-273): **empty/missing telemetry → `rate_pct=100.0`
  degrade-open** — once Canva retires, the success-rate probe goes permanently blind unless
  re-keyed to a DB-derived source. Esiste-ma-disarmato, W64 class.

### 1.5 Production evidence (live DB, 2026-06-11)

| Fact | Value |
|---|---|
| Last `rendered` draft | 2026-06-08 21:46 — the LAST Canva render, pre-cutover |
| HTML lane successful renders | **0** (`drive_url_shadow` = 0; no `rendered` after 06-09) |
| `render_failed` | 5 drafts, 2026-06-10 (pre-#1275 designer-loop fixes, merged 06-11) |
| Stuck non-terminal drafts | 2 × `drafts_imaged_checked` (06-09) + 1 × `drafts_imaged` (06-11) |
| `topic_type_log` (mig 216) | 7 rows; **last write 2026-06-08 21:46** = the last Canva render |
| `topic_type_log` write site | ONLY `wr2_canva_desktop_apply.py:267` (grep whole repo) — **orphaned by the cutover: the variety log stopped being fed on 06-09** |
| `dominant_mode` distribution | unknown 6/7 (86%), human-silhouette 1/7 |
| fact-extractor health | last run FAILED: `ClaudeOAuthError … keychain: exit=1` under launchd (log 2026-06-11 08:20) — blocks `drafts_imaged → drafts_imaged_facted` |
| Token leak (audit P0, confirmed by Codex) | `_ops_alert()` builds the Telegram URL with the bot token in the path; httpx INFO logs it to `~/logs/wr2-html-apply.log` → PRE-2 |

**Net: WR2 produces nothing end-to-end today.** Cutover happened, the convergence fixes are
merged and deployed, but (a) the mid-chain has no motor, (b) fact-extractor is
keychain-broken, (c) the variety-log write is orphaned in the flag-OFF Canva script.

### 1.6 Gen-1 skill-cortex remnants (autopsy meta-correction)

The 2026-06-05 META scar declared `_state-schema.sql:63` / `_voyager-curriculum.py:49` /
SQLite `topic_type_log` HALLUCINATED ("find → 0 results"). That find ran **in the repo only**.
Verified this session: both files EXIST in `~/.claude/skills/bali-zero-brand/` with exactly
the cited content. The autopsy cited real skill-cortex files, not repo files. Consequence:
**two topic_type_log stores exist** (SQLite skill-dir, fed by nothing; Postgres mig 216, fed
by nothing since 06-09). The scar needs a correction note (follow-up, separate from this diff).

Gen-1 live remnants: `queue-server` (`_damar-queue-server.py`, RUNNING — Damar review UI on
localhost:8765 backed by `human-review-queue.json`, last write 06-09), `voyager.weekly`
(reads the SQLite log nobody writes), `reflexion.weekly`, `ig-scraper.daily`,
`ig-metrics-analyst.weekly`, `external-bench.monthly`.

### 1.7 Adjacent-but-out-of-scope WR2 labels (do not touch)

`connector / oracle / strategos / dossier-compiler / learner-nightly / newsletter /
trend-hunter / measurer / sla-worker / daily-metrics / e2e-probe / hardening / pg-proxy /
pg-queue-sync / deploy-puller / plist-watchdog / worktree-gc / matagaruda.wr2-bridge` = the
broader war-room cognitive/infra stack. Out of P-1 scope — EXCEPT `worktree-gc`, which R1
must patch (§1.2 finding) before the A-tables migration.

### 1.8 Residual WR2 worktrees (retirement inventory)

| Worktree | Branch | Dirty | Subsumed by |
|---|---|---|---|
| `.worktrees/wr2-html-css-renderer-pro-render` | `agent/air-m5/wr2/html-css-renderer-2026-06-07` | 0 | PR #1228 (squash `3bc4a7cb9`) |
| `.worktrees/wr2-html-engine-rebase` | `agent/air-m5/wr2/html-renderer-rebase-2026-06-09` | 0 | PR #1228/#1236 chain |
| `.worktrees/wr2-wiring-impl` | `agent/air-m5/wr2/wiring-impl-2026-06-09` | 0 | PR #1236 (squash `bf5e5bb69`) |
| `~/.worktrees/wr2-renderer-demo` (extra) | same branch as pro-render | 0 | PR #1228 |
| `/private/tmp/wr2-shadow-f10` (extra) | detached `928c00718` | — | F10 shadow attempt |

Branch heads are NOT ancestors of origin/main (squash merges) → subsumption must be proven by
content-diff, not ancestry (§4 R3).

---

## §2 SALVAGE INVENTORY — what of Pipeline A (and gen-1) is worth saving

Key insight: **most of A's intelligence was already ported to B** by autopsy batch-1
(PR #1125) and P-4 (PR #1133). What remains is wiring the ported pieces to the new chokepoint.

| # | Asset | Where it lives | Verdict | Action |
|---|---|---|---|---|
| S1 | **topic_type_log write at render-terminal** | `wr2_canva_desktop_apply.py:267` (flag-OFF) | **PORT — the P0 of this spec** | REV 2 (panel): do NOT put the INSERT inside `_pg.py` (backend package importing `scripts/wr2_topic_type` = ModuleNotFoundError crash risk in app/pytest context). Extract the ledger write from `wr2_canva_desktop_apply.py` into a sibling script module (e.g. `scripts/wr2_topic_type_log.py`), call it **best-effort from `wr2_html_render_apply.py` AFTER** `_pg.persist_html_result_and_enqueue_notifications()` returns — scripts/ is already on sys.path there. Idempotent `ON CONFLICT (draft_id) DO NOTHING`, failure = WARN + ops-alert (not raise) |
| S2 | Anti-monotony soft-steer + 9 image modes | ALREADY in B (`wr2_draft_generator.py:826-960`, `wr2_topic_type.py`) | KEEP | No port needed; starves without S1 |
| S3 | Anti-monotony hard-reject | ALREADY in B behind `WR2_ANTIMONOTONE_ENFORCE` (default OFF) | ARM LATER | Metric-gated: arm when `topic_type_log` ≥ 20 post-S1 rows |
| S4 | Voyager curriculum (underrepresented-topic detection) | gen-1 `_voyager-curriculum.py` reading SQLite log fed by nothing | PORT (small), stage 2 | Re-point reads to PG `topic_type_log` (mig 216); output feeds topic_selector steer |
| S5 | Topic selection scoring | ALREADY live in B (`wr2_topic_selector.py`) | KEEP | A never had a better one — `topic_ready` had no producer |
| S6 | Narrative-arc storyboarding (multi-subagent) | orchestrator PIPELINE_STEPS | **DROP** | B's draft prompt encodes hook/arc; designer vision-loop (#1228) owns composition. A's fan-out never survived production and costs OAuth quota |
| S7 | Critic 4-rubric gate | orchestrator critic step + `backend/services/war_room/critic_rubric.py` (zero non-A consumers) | DROP (defer) | Visual = designer-loop converged gate; facts = fact-checker. Brand-voice rubric = only uncovered axis — optional post-render check, NOT in P-1 |
| S8 | `publish_after_approval` + `IGPublisher` + `wr2_publish_attempts` | orchestrator:818-906, backend publisher | **DROP — Legge 5** | Never used (0 rows). Removing it turns "Legge 5 by convention" into "Legge 5 by construction" |
| S9 | Supervisor event-driven motor + reconciliation | `wr2_supervisor.py` (B asset, disabled) | **REPAIR + RE-ENABLE** | Patch **both** maps (`TRANSITIONS` + `NONTERMINAL_TO_NEXT_STAGE`): `canva-apply → html-apply`; drop dead `briefed_facted` rows; align worker drain (R4). Alternative (cron-per-stage) rejected: loses event latency + reconciliation; plists were stripped of schedules by design |
| S10 | Supervisor watchdog | `wr2_supervisor_watchdog.py` (loaded, Canva-keyed, degrade-open) | REPAIR (scope extended by panel) | Re-key: (a) gate flag → `wr2_html_renderer_enabled`; (b) success-rate source → **DB-derived** (`status='rendered' AND drive_url IS NOT NULL` vs `render_failed` over the 7-day window) replacing the JSONL telemetry file (kills the degrade-open 100% blindness); (c) freshness column `canva_applied_at` → `drive_url`/`updated_at`; (d) add daily S1-reconcile probe: `rendered` drafts missing a `topic_type_log` row > 24h → alert (closes DeepSeek M2 hole) |
| S11 | A state machine (`wr2_carousel_runs`, `transition_state`) | orchestrator | DROP | B's status flow on `war_room_drafts` is the live state machine. ⚠️ table drop gated on the `wr2_worktree_gc.py` patch (§4 R1) |
| S12 | Per-run worktree spawn (dispatcher) | dispatcher | DROP | irrelevant to B |
| S13 | Damar queue UI (gen-1) | `_damar-queue-server.py` (running) | KEEP-FOR-NOW | Live delivery = WhatsApp+Drive; the queue UI is a parallel manual surface. Retiring it is an Antonello/Damar UX decision — out of P-1 |
| S14 | (NEW, red-team) Fact-check BEFORE image-gen | pipeline order | DEFER (stage 2, Antonello call) | Today image_generator burns Codex `$imagegen` credits on drafts that may later land `fact_check_failed`. Reordering (extract/check facts on text → then images) saves credits but touches the status flow + both supervisor maps. Not in slice 1 |

---

## §3 TARGET ARCHITECTURE — one pipeline

```
                       mata-garuda bridge (hourly, intel staging)
                                      │
   05:10 cron ─► topic_selector ──────┴──► war_room_drafts(status='briefed')
                      ▲                                  │ trigger → events_outbox + NOTIFY
                      │ steer (avoid-list / curriculum)  ▼            wr2_status_change (mig 164, durable)
                      │                        ┌─ SUPERVISOR (re-enabled, both maps patched,
        PG topic_type_log (mig 216)            │   replay_outbox + reconcile + drain-aligned) ─┐
                      ▲                        └───────────────────────────────────────────────┘
                      │ S1 write (script-side,            │         │         │         │
                      │ best-effort post-persist)         ▼         ▼         ▼         ▼
                 html_render_apply ◄── fact_checker ◄── fact_extractor ◄── image_generator ◄── draft_generator
                      │  (chokepoint, kill-switch wr2_html_renderer_enabled,
                      │   StartInterval=600 kept as fallback until M1 green, then removed)
                      ├── PNGs → Google Drive (SA-DWD)
                      ├── status='rendered'  ◄— TERMINAL SOFTWARE STATUS (Legge 5)
                      ├── best-effort INSERT topic_type_log (S1 — closes the variety loop)
                      └── wa_outbox → WhatsApp (Antonello + Damar) with Drive link
                                          │
                                  HUMAN (Damar) publishes manually on Instagram
                                          │
                          (optional later: mark-published backfills
                           topic_type_log.published_at — panel B of mig 216)
```

Properties:

1. **Legge 5 by construction**: after S8 removal, the IG-publish capability grep (§4 R1
   gate, narrowed per panel) returns zero runtime hits. No code path can publish.
2. **Terminal status `rendered`** unchanged; review delivery = durable `wa_outbox`.
3. **Variety loop closed end-to-end**: draft_generator steer (read) ← PG topic_type_log ←
   S1 write (chokepoint). One store; SQLite duplicate retired with the S4 curriculum port.
4. **One motor**: supervisor (event + replay + reconcile), with workers aligned to its drain
   assumption. html-apply's 600s poll is a temporary belt-and-braces fallback (R4b removes it
   after first M1 green).
5. **Watchdog re-armed on DB-derived signals** — no degrade-open telemetry file.

Operational pre-requisites = **Gate 0, HARD precondition of R4** (panel-promoted):
- **PRE-1**: fix fact-extractor `ClaudeOAuthError keychain exit=1` under launchd (recipe from
  #1208: env-file 0600 + wrapper source, or dedicated unlockable keychain) + a launchd-context
  auth selftest.
- **PRE-2**: silence the httpx INFO token leak in `wr2_html_render_apply.py` logging + rotate
  the Telegram token (audit P0, already tracked) — BEFORE R4 multiplies render/alert traffic.

---

## §4 RETIREMENT PLAN — staged, each stage reversible

### R0 — already done (F23, 2026-06-11), verify only
Acceptance: `launchctl print-disabled gui/501 | grep -E "carousel-dispatcher|telegram-gate|wr2.supervisor"`
→ 3 × disabled; `launchctl list | grep -cE "carousel-dispatcher|telegram-gate"` → 0.
(Supervisor's disable gets REVERSED in R4.)

### R1 — repo deletion of Pipeline A (one PR, pure deletion + 1 patch, trivially revertable)
Order: consumers first, then producers, then backend.
1. **Patch `scripts/wr2_worktree_gc.py`** (panel BLOCKER-adjacent): remove/feature-gate
   `fetch_inflight_carousels` (`:90` SELECT on `wr2_carousel_runs`) so the GC no longer
   depends on an A-table. Ship in the SAME PR as the deletions, BEFORE the table-drop migration.
2. HOME cleanup (Pro, not git): `rm ~/Library/LaunchAgents/com.balizero.wr2.{carousel-dispatcher,telegram-gate}.plist`
   (already booted out) + `rm ~/scripts/wr2-carousel-dispatcher-wrapper.sh ~/scripts/wr2-telegram-gate-wrapper.sh`.
   Repo side: `git rm infra/launchagents/com.balizero.wr2.carousel-dispatcher.plist.example`.
3. `git rm scripts/wr2_carousel_orchestrator.py scripts/wr2_carousel_dispatcher.py
   scripts/wr2_telegram_publish_gate.py scripts/tests/test_wr2_carousel_orchestrator.py
   scripts/tests/test_wr2_telegram_publish_gate.py`.
4. Backend: remove ig_publisher startup validation + registration
   (`service_initializer.py:1021-1040`) and the lifespan close hook (`app_factory.py:604`);
   `git rm backend/services/publisher/ig_publisher.py
   apps/backend-rag/backend/tests/services/publisher/test_ig_publisher.py`; prune
   `publisher/__init__.py` exports; `git rm backend/services/war_room/critic_rubric.py`;
   clean stale docstrings (`scripts/wr2_html_renderer/renderer.py:10`,
   `lint_canva_pending.py:122` message text).
5. DB (separate migration, AFTER 30-day inert observation AND R1.1 deployed): drop
   `wr2_carousel_runs`, `wr2_orchestrator_metrics`, `wr2_carousel_events_outbox`,
   `wr2_publish_attempts`. Pre-drop evidence: `pg_stat_user_tables` seq/idx scan counters flat.
   Grep-gates (0 hits in runtime code before merge — narrowed per panel; `graph.facebook`
   dropped because WhatsApp/Meta sensors legitimately use Graph):
   `grep -rn "topic_ready|wr2_carousel_orchestrator|wr2_telegram_publish_gate|IGPublisher|ig_publisher|wr2_publish_attempts|media_publish" scripts/ apps/backend-rag/backend --include='*.py' | grep -v tests/`

### R2 — Canva WR2-lane retirement (AFTER M1 green ≥3 consecutive E2E)
1. `launchctl bootout gui/501/<label> && launchctl disable gui/501/<label>` for:
   `canva-apply` (do this one already at R4 — DeepSeek robustness note), `canva-gc.weekly`,
   `canva-lease-watchdog.10min`, `canva-token-watchdog.daily`, `canva-oauth-watchdog`
   (canva-renderer already disabled). Apply first, watchdogs last.
2. `git rm` WR2-lane Canva scripts: `wr2_canva_desktop_apply.py`, `wr2_canva_headless_apply.py`,
   `wr2_canva_headless_probe.py`, `wr2_canva_pdf_apply.py`, `wr2_canva_pdf_render.py`,
   `wr2_canva_reconcile.py`, `wr2_canva_garbage_collector.py`, `wr2_canva_lease_watchdog.py`,
   `wr2_canva_token_watchdog.py`, `wr2_validate_master.py` — ONLY after S1 has moved the
   topic_type_log write out of `wr2_canva_desktop_apply.py`.
   **Manual-Canva decision list (Antonello call, default KEEP)**: `wr2_bootstrap_canva_oauth.py`,
   `lint_canva_pending.py` (not a daemon; Canva stays for manual special pieces per the
   2026-06-06 decision).
3. Leave `system_settings` rows in place (historical record).
   Grep-gate: `grep -rln "wr2_canva" scripts/ --include='*.py'` → only the decision-list survivors.
   Rollback: `git revert` + re-bootstrap plists from git history; flag flip back = 1 SQL UPDATE.

### R3 — worktree + branch cleanup (independent, any time)
For each of the 5 worktrees in §1.8, prove subsumption by content (pathspec EXPANDED per panel):
`git diff <branch> origin/main -- scripts/wr2_html_renderer/ scripts/wr2_html_render_apply.py
apps/backend-rag/backend/services/canva_renderer_v2/ apps/backend-rag/backend/tests/
scripts/tests/ infra/launchagents/ apps/backend-rag/backend/db/migrations_v2/`
→ empty or main-is-newer ⇒ `git worktree remove <path>` + `git branch -D <branch>`.
Branch-only content ⇒ STOP, escalate (unmerged work).
Acceptance: `git worktree list | grep -c wr2` → 1 (this one), then 0 at PR merge.

### R4 — motor re-enable (the only state-changing step; HARD-gated on Gate 0 = PRE-1 + PRE-2)
1. Patch `wr2_supervisor.py`: **both** `TRANSITIONS` and `NONTERMINAL_TO_NEXT_STAGE` →
   `com.balizero.wr2.html-apply`; remove dead `briefed_facted` rows from both; unit test
   asserting **no supervisor target contains `canva-apply`** and the maps cover exactly the
   §1.3 state machine.
2. **Drain-loop alignment (red-team BLOCKER)**: make `wr2_html_render_apply.py` loop until
   `fetch_pending_draft_ids` returns empty (CAS lease already makes this safe) instead of
   `MAX_DRAFTS_PER_RUN=1`-and-exit; bump draft_generator to drain its briefed queue. This
   restores the supervisor's documented drain assumption (wr2_supervisor.py:20-22).
3. Patch `wr2_supervisor_watchdog.py` per S10 (flag + DB-derived success rate + freshness +
   S1-reconcile probe) + tests.
4. Bootout/disable `canva-apply` label (flag already OFF; removes the theoretical
   reconcile-misfire surface).
5. Merge → deploy-puller syncs → `launchctl enable gui/501/com.balizero.wr2.supervisor &&
   launchctl kickstart gui/501/com.balizero.wr2.supervisor`. Replay on boot is bounded
   (≤500, deduped, no-op on stale statuses — §1.4).
6. **R4b**: after first M1 green, remove `StartInterval=600` from the html-apply plist
   (repo + HOME) and re-bootstrap — completing the "one motor" story.
   Watch 24h: heartbeat fresh, zero canva-apply kickstarts in supervisor log.
   Rollback: `launchctl disable` supervisor → back to today's state (html-apply 600s poll
   still on until R4b, so rollback mid-way keeps the chokepoint alive).

---

## §5 RISKS + FALSIFIABLE ACCEPTANCE (Legge 7)

All SQL timestamps UTC; capture `r4_enabled_at` (UTC) at R4.5 and parameterize every metric
on it (panel fix — no `updated_at > '2026-06-11'` local/UTC ambiguity).

| ID | Stage | Metric (before → after) | Command |
|---|---|---|---|
| M1 | E2E render | 0 HTML-lane `rendered` since cutover → **≥1 draft `rendered`** | `SELECT count(*) FROM war_room_drafts WHERE status='rendered' AND drive_url IS NOT NULL AND updated_at >= :r4_enabled_at` |
| M2 | S1 variety write | last ledger write 2026-06-08 (orphaned) → **every post-R4 `rendered` draft has a ledger row within 24h** (best-effort + watchdog reconcile probe alerting on gaps — resolves the DeepSeek equality/best-effort contradiction) | `SELECT count(*) FROM war_room_drafts d LEFT JOIN topic_type_log t ON t.draft_id=d.id WHERE d.status='rendered' AND d.updated_at >= :r4_enabled_at AND d.updated_at < now()-interval '24 hours' AND t.draft_id IS NULL` → **0** |
| M3 | Variety itself | dominant_mode unknown 6/7 (86%) → **≤30% unknown AND ≥3 distinct modes over the next 10 renders** | `SELECT dominant_mode, count(*) FROM topic_type_log WHERE rendered_at >= :r4_enabled_at GROUP BY 1` |
| M4 | Legge 5 by construction | IGPublisher importable + validated at startup → **narrowed grep-gate 0 runtime hits**; backend boots without ig_publisher registration | R1.5 grep + app-factory pytest smoke |
| M5 | Dead-code mass | A scripts 3 files ≈ 94KB + backend publisher + 3 test files → **deleted; `topic_ready` grep = 0** | `ls`, grep |
| M6 | Motor (REV 2, falsifiable from DB alone — no launchd-log forensics) | mid-chain advances only manually → **a draft INSERTed at `briefed` after R4 reaches `rendered` with every stage-to-stage `updated_at` delta < 45 min and supervisor heartbeat gap < 300s throughout** | stage-delta SQL on `war_room_drafts.updated_at` history (via events_outbox rows for the draft) + `SELECT max(created_at) FROM wr2_supervisor_heartbeat` |
| M7 | Crash-loop hygiene | 4 disabled labels with plists on disk → **0 loaded WR2 jobs with A-related non-zero last-exit; no exit-75** | `launchctl list \| grep wr2` |
| M8 | Worktrees | 5 residual WR2 worktrees → **1 (this one) then 0** | `git worktree list` |
| M9 | Watchdog re-armed | frozen-check "skipped (canva kill switch OFF)" + success-rate degrade-open 100% on empty file → **frozen + success-rate checks execute against html flag + DB-derived rate; probe returns real rate with 0-attempt window flagged as NO-DATA (not 100%)** | watchdog log grep + unit test on `_probe_success_rate_*` |
| M10 | GC survives table drop | `wr2_worktree_gc.py:90` queries `wr2_carousel_runs` → **GC daily exit 0 with the table absent (staging test before the drop migration)** | run GC against a DB without the table |

Risks:

| Risk | Mitigation |
|---|---|
| Supervisor re-enable kicks wrong/extra stages | R4.1 unit test on both maps; 24h observation; rollback = disable |
| S1 write failure breaks render or silently starves the ledger | Best-effort AFTER persist (render unaffected) + watchdog S1-reconcile probe alerts on 24h gaps (M2) |
| `_pg.py` import of scripts/ crashes backend (panel HIGH) | S1 implemented script-side only; `_pg.py` untouched by S1 |
| fact-extractor keychain failure blocks E2E | Gate 0 PRE-1 hard precondition before R4 |
| Token leak amplified by R4 traffic | Gate 0 PRE-2 (silence httpx INFO + rotate) before R4 |
| Drop of A-tables breaks `worktree-gc` (panel HIGH) | R1.1 GC patch ships BEFORE the drop migration; M10 staging test |
| Busy-worker kickstart starvation (panel BLOCKER) | R4.2 drain-loop; at 1-3 drafts/day residual risk is latency-only, bounded by reconcile |
| R2 deletes a Canva script a manual flow uses | Manual-Canva decision list (bootstrap + lint) default-KEEP, Antonello GO on the rest |
| Deploy-worktree drift re-runs old code (W50-class) | M-gates measured only after `git -C ~/Desktop/nuzantara-deploy rev-parse HEAD` == merge SHA |
| Codex credit burn on fact-failing drafts | S14 deferred reorder (stage 2, explicit Antonello call) |

**Staging**: slice 1 = S1 (script-side) + S10 watchdog re-key + supervisor both-maps patch +
R4.2 drain-loop + R1.1 GC patch + unit tests — **code-only, zero launchctl changes, inert
until R4 enable, behind the existing kill-switch**. Then: panel ✅ (done) → Antonello GO →
merge slice 1 → Gate 0 → R4 enable → M1/M2/M6 green → R1 → R2 → R3 → table-drop migration.

---

## §6 4-LLM PANEL VERDICT (run 2026-06-11, asymmetric per sota-architecture-loop)

| Panelist | Role | Verdict | Findings |
|---|---|---|---|
| **Gemini 3.1 Pro** (agy CLI, read the repo itself) | Red-team ("destroy it") | **NO-GO** (on REV 1) | 7: 1 BLOCKER (kickstart-vs-MAX_DRAFTS starvation), 3 HIGH (worktree-gc table dependency; watchdog telemetry degrade-open blindness; `_pg.py` import boundary crash), 2 MEDIUM (outbox live-path ack; image-gen before fact-check credit burn), 1 LOW (M6 unfalsifiable) |
| **Codex GPT-5.5** (read the repo itself) | Constructive ("save it") | **GO-WITH-FIXES** | 12 improvements: Gate 0 promotion of PRE-1/PRE-2; S1 as script-side helper reuse; BOTH supervisor maps; html-apply StartInterval reality + R4b; full watchdog re-key incl. DB-derived rate; migration-164 durability correction; narrowed Legge-5 grep; tests/docstrings in R1; HOME-vs-repo plist split; UTC cutover-scoped metrics; lint_canva_pending to manual list; expanded R3 pathspec |
| **DeepSeek V4 Pro** (reasoning high, spec-only) | Logic | **GO-WITH-FIXES** | 5: failure-status orphans (resolved: consumers named §1.3); M2 equality vs best-effort contradiction (resolved: 24h-window + watchdog probe); §1.4 internal contradiction on durability (resolved: live trigger verified outbox-backed); M6 under-specified (resolved: DB-only metric); canva-apply loaded during R4 (resolved: bootout at R4.4) |
| NB-1 | — | SKIPPED | Internal disk-state domain, zero regulatory facts at stake — NB would be noise (sota-loop ground rule) |

**Orchestrator re-verification (anti-hallucination, W65 discipline)**: every load-bearing
panel claim was re-run on disk/DB by the orchestrator before incorporation. Confirmed TRUE:
`wr2_worktree_gc.py:90`, `MAX_DRAFTS_PER_RUN` 1/2, `RECONCILE` defaults, watchdog
`rate_pct=100.0` on empty telemetry, html-apply `StartInterval=600` (REV 1 ground error —
`plutil -extract` had failed silently; `plutil -p` is the reliable form), live trigger body
outbox-backed (mig 164; REV 1 "NOTIFY into the void" retracted), both supervisor maps on
canva-apply, A-test files exist. Corrected against empirics: red-team's outbox-bloat claim —
live counts show 251 events / 0 unconsumed (an external drain acks the channel), so bloat is
not occurring; bounded-replay note added instead.

**Disposition of the red-team NO-GO**: all 7 findings are incorporated as spec changes in
REV 2 (S1 re-design, S10 scope extension, R1.1 GC patch, R4.2 drain-loop, R4.4 canva-apply
bootout, M6 rewrite, S14 deferred reorder). The NO-GO applied to REV 1; REV 2 is the
red-team's findings made structural. Final orchestrator verdict: **GO-WITH-FIXES,
fixes already folded in — pending Antonello GO before any merge.**
