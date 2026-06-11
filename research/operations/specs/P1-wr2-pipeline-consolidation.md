---
date: 2026-06-11
domain: operations
client_case: none
sources:
  - disk-state verification 2026-06-11 (launchctl, plists, scripts/, ~/.claude/skills/bali-zero-brand/, deploy worktree)
  - live Fly Postgres via postgres-nuzantara MCP (system_settings, war_room_drafts, topic_type_log, wr2_* tables)
  - research/operations/2026-06-04-wr2-autopsy-report.md (leads re-verified per anti-hallucination rule)
  - PR #1228 (3bc4a7cb9), PR #1236 (bf5e5bb69), PR #1275 (a45c67909), PR #1125, PR #1133 (migration 216)
  - memories: decision_wr2_renderer_html_css_over_canva_2026_06_06, audit_system_fable5_2026_06_11 (F23), wr2_html_renderer_convergence_chain_2026_06_10
---

# P-1 — WR2 Pipeline Consolidation Spec

**Status**: DRAFT — gated on 4-LLM panel verdict (§6) + Antonello GO. Nothing merged to main.
**Scope**: architectural consolidation of the two WR2 carousel pipelines into one. The renderer
decision (HTML/CSS → PNG via Playwright) is ALREADY MADE AND SHIPPED (PR #1236, flag ON since
2026-06-09 15:46 UTC) and is NOT re-litigated here.
**Hard rules honored**: Legge 5 (no software IG publish — terminal status stays `rendered`,
human publishes manually), Legge 7 (every stage has a before/after metric), anti-hallucination
(every file:line below was re-verified on disk in this session; commands cited inline).

---

## §1 GROUND — verified on-disk map of the two pipelines (2026-06-11)

### 1.1 The actual state is THREE generations, not two

The autopsy framed WR2 as two pipelines. Disk-state shows three generations, one of which
(gen-1) the autopsy conflated into "Pipeline A":

| Gen | Name | Where | State today |
|---|---|---|---|
| 1 | Skill-cortex agent pipeline (May) | `~/.claude/skills/bali-zero-brand/_*.py` + SQLite state | Semi-stale; 2 LaunchAgents still loaded |
| 2 | **Pipeline A** — scripts orchestrator | `scripts/wr2_carousel_orchestrator.py` + dispatcher + telegram gate | DEAD: all 3 LaunchAgents disabled (F23, 2026-06-11) |
| 3 | **Pipeline B** — live draft lane | `scripts/wr2_topic_selector.py` → … → `scripts/wr2_html_render_apply.py` | LIVE but motor off + 3 operational blockers |

### 1.2 Pipeline A (gen-2) — dead, with evidence

| Component | Verification (this session) | Result |
|---|---|---|
| `scripts/wr2_carousel_orchestrator.py` (37KB) | `git log -1 -- <file>` | last commit `acbf5228a` 2026-05-28 (#894) |
| `scripts/wr2_carousel_dispatcher.py` | `grep -rn topic_ready` whole repo | **2 hits, both inside the dispatcher itself** — the `topic_ready` channel has NO producer anywhere; the only consumer is this disabled dispatcher. Doubly dead. |
| `scripts/wr2_telegram_publish_gate.py` | `git log -1` | last commit 2026-05-28 (#901) |
| LaunchAgents `com.balizero.wr2.{carousel-dispatcher,telegram-gate,supervisor}` | `launchctl print-disabled gui/501` | all `=> disabled` (F23 bootout 2026-06-11); not present in `launchctl list` |
| `publish_after_approval()` orchestrator:818-906 | `sed -n '818,906p'` | contains a REAL Meta Graph publish call (`IGPublisher().publish`) + `transition_state(..., "published")` — **a Legge 5 violation living in dead code** |
| `backend/services/publisher/ig_publisher.py` | `grep -rn IGPublisher` | runtime callers: ONLY the dead orchestrator. Plus `service_initializer.py:1021-1040` validates IG credentials at every backend startup for this dead path |
| A-state tables | live PG query | `wr2_carousel_runs` = 11 rows (May test runs), `wr2_orchestrator_metrics` = 46, `wr2_carousel_events_outbox` = 0, `wr2_publish_attempts` = **0 rows ever** |
| Wrappers | plist ProgramArguments | `~/scripts/wr2-carousel-dispatcher-wrapper.sh`, `~/scripts/wr2-telegram-gate-wrapper.sh` (HOME copies, orphaned with their plists) |

### 1.3 Pipeline B (gen-3) — the live lane, status flow verified per script

Status state machine (verified by `grep "WHERE status\|SET status"` per script):

```
topic_selector (cron 05:10 WITA)            INSERT war_room_drafts status='briefed'
  └─ scores staging items from backend API; mata-garuda wr2-bridge.hourly feeds intel upstream
draft_generator        'briefed'             → 'drafts' | 'rejected'
image_generator        'drafts'              → 'drafts_imaged' | 'image_failed'   (hero via Codex $imagegen → Tigris)
fact_extractor         'drafts_imaged'       → 'drafts_imaged_facted'
fact_checker           'drafts_imaged_facted'→ 'drafts_imaged_checked' | 'fact_check_failed'
html_render_apply      'drafts_imaged_checked' → CAS lease 'rendering' →
                         'rendered' + drive_url + wa_outbox notify (Antonello + Damar)
                       | 'rendered_shadow' (WR2_HTML_SHADOW=1)
                       | 'render_failed' (after 3 attempts) | release back for retry
```

Terminal SOFTWARE status = `rendered`. Human gate = WhatsApp message with Drive link
(durable `wa_outbox`, html_render_apply.py:4-12); Damar publishes manually. **No IG/Graph call
anywhere in the live lane** (verified: `IGPublisher` grep has zero hits in B scripts).

Kill-switches (live PG `system_settings`, queried this session):

| key | value | updated |
|---|---|---|
| `wr2_html_renderer_enabled` | **true** | 2026-06-09 15:46 |
| `wr2_canva_desktop_apply_enabled` | **false** | 2026-06-09 15:47 |
| `wr2_canva_renderer_enabled` | false | 2026-05-15 |
| `wr2_fact_checker_enabled` / `wr2_fact_extractor_enabled` | true | — |

Runtime home: every B stage runs from the **deploy worktree** `~/Desktop/nuzantara-deploy`
(via `~/.openclaw/bin/wr2/wr2-script-wrapper.sh`; html-apply inline-bash also pins
`WR2_REPO_ROOT=$HOME/Desktop/nuzantara-deploy` + dedicated `.venv-wr2-html`). Verified
2026-06-11: deploy worktree at `984edce37` = origin/main, **0 behind**, includes #1275
designer-loop fixes. HOME-fork rule: repo `scripts/` is the source of truth; deploy worktree
syncs via `com.balizero.wr2.deploy-puller` (hourly) after merge — any fix here reaches
production only after merge + pull.

### 1.4 The motor is OFF — B currently has no automatic advancement

- `wr2_supervisor.py` = B's event-driven orchestrator: LISTEN `wr2_status_change` (local
  pg-proxy :15432) → `launchctl kickstart` next stage plist + startup/periodic reconciliation.
  **Disabled** (F23). 28,615 heartbeat rows prove it ran for weeks before.
- The 6 stage plists have **NO StartCalendarInterval/StartInterval and RunAtLoad absent/false**
  (verified per plist). Only topic-selector has a cron (05:10). ⇒ with the supervisor off,
  drafts advance only on manual kickstart.
- PG trigger `wr2_status_change_trg` (verified in `pg_trigger`) fires NOTIFY **into the void**
  — channel not in `PG_CHANNEL_MAP`, no outbox durability (known scar), zero listeners.
- `wr2_supervisor.py:97` TRANSITIONS still maps `('drafts_imaged_facted','drafts_imaged_checked')
  → com.balizero.wr2.canva-apply` — **re-enabling the supervisor today would kickstart the
  flag-OFF Canva apply, not html-apply**. One-line patch required before re-enable.
- `wr2_supervisor_watchdog.py` (loaded, KeepAlive): logs show `supervisor_down stale but
  cooldown active` AND `pipeline_frozen check skipped (canva-renderer kill switch OFF)` —
  its frozen/success-rate protections are **keyed to the dead Canva flag** ⇒ silently disarmed
  under the HTML cutover (esiste-ma-disarmato, W64 class).

### 1.5 Production evidence (live DB, 2026-06-11)

| Fact | Value |
|---|---|
| Last `rendered` draft | 2026-06-08 21:46 — the LAST Canva render, pre-cutover |
| HTML lane successful renders | **0** (`drive_url_shadow` count = 0; no `rendered` after 06-09) |
| `render_failed` | 5 drafts, 2026-06-10 (pre-#1275 designer-loop fixes, merged 06-11) |
| Stuck non-terminal drafts | 2 × `drafts_imaged_checked` (since 06-09) + 1 × `drafts_imaged` (06-11) |
| `topic_type_log` (mig 216) | 7 rows; **last write 2026-06-08 21:46** = the last Canva render |
| `topic_type_log` write site | ONLY `wr2_canva_desktop_apply.py:267` (grep INSERT whole repo) — **orphaned by the cutover: the variety log stopped being fed on 06-09** |
| `dominant_mode` distribution | unknown 6/7 (86%), human-silhouette 1/7 |
| fact-extractor health | last run FAILED: `ClaudeOAuthError … keychain: exit=1` under launchd (log 2026-06-11 08:20) — blocks `drafts_imaged → drafts_imaged_facted` |

**Net: WR2 produces nothing end-to-end today.** Cutover happened (flags flipped), the fixes
that make the HTML lane converge are merged (#1275) and present in the deploy worktree, but
(a) nothing kicks the stages, (b) fact-extractor is keychain-broken, (c) the variety-log write
is orphaned in the flag-OFF Canva script.

### 1.6 Gen-1 skill-cortex remnants (autopsy meta-correction)

The 2026-06-05 META scar declared `_state-schema.sql:63` / `_voyager-curriculum.py:49` /
SQLite `topic_type_log` HALLUCINATED ("find → 0 results"). That find ran **in the repo only**.
Verified this session: both files EXIST in `~/.claude/skills/bali-zero-brand/` with exactly the
cited content (`_state-schema.sql:63` = `CREATE TABLE IF NOT EXISTS topic_type_log` SQLite;
`_voyager-curriculum.py:49` = the LEFT JOIN). The autopsy cited real files in the skill cortex,
not repo files. Consequence: there are **two topic_type_log stores** (SQLite skill-dir, fed by
nothing; Postgres mig 216, fed by nothing since 06-09). The scar needs a correction note
(follow-up, not in this spec's diff).

Gen-1 live remnants:

| Label | Script | State |
|---|---|---|
| `com.balizero.wr2.queue-server` | `_damar-queue-server.py` (Damar review UI, localhost:8765, backs `apps/war-room/output/queue/human-review-queue.json`, last write 06-09) | RUNNING (pid live) |
| `com.balizero.wr2.voyager.weekly` | `_voyager-curriculum.py` — reads the SQLite log nobody writes | loaded, exit 0 |
| `com.balizero.wr2.reflexion.weekly`, `ig-scraper.daily`, `ig-metrics-analyst.weekly`, `external-bench.monthly` | brand-skill learning loop | loaded |

### 1.7 Adjacent-but-out-of-scope WR2 labels (do not touch)

`connector / oracle / strategos / dossier-compiler / learner-nightly / newsletter / trend-hunter /
measurer / sla-worker / daily-metrics / e2e-probe / hardening / pg-proxy / pg-queue-sync /
deploy-puller / plist-watchdog / worktree-gc / matagaruda.wr2-bridge` = the broader war-room
cognitive/infra stack (backend.services.* modules). They share the `wr2.` label prefix but are
not the carousel A/B split. Out of P-1 scope.

### 1.8 Residual WR2 worktrees (retirement inventory)

| Worktree | Branch | Dirty | Subsumed by |
|---|---|---|---|
| `.worktrees/wr2-html-css-renderer-pro-render` | `agent/air-m5/wr2/html-css-renderer-2026-06-07` | 0 files | PR #1228 (squash `3bc4a7cb9`) |
| `.worktrees/wr2-html-engine-rebase` | `agent/air-m5/wr2/html-renderer-rebase-2026-06-09` | 0 files | PR #1228/#1236 chain |
| `.worktrees/wr2-wiring-impl` | `agent/air-m5/wr2/wiring-impl-2026-06-09` | 0 files | PR #1236 (squash `bf5e5bb69`) |
| `~/.worktrees/wr2-renderer-demo` (extra) | same branch as pro-render | 0 files | PR #1228 |
| `/private/tmp/wr2-shadow-f10` (extra) | detached `928c00718` | — | F10 shadow attempt |

Branch heads are NOT ancestors of origin/main (squash merges) → subsumption must be proven by
content-diff, not ancestry (procedure in §4 R3).

---

## §2 SALVAGE INVENTORY — what of Pipeline A (and gen-1) is worth saving

Key insight from ground: **most of A's intelligence has already been ported to B** by autopsy
batch-1 (PR #1125) and P-4 (PR #1133). What remains is mostly *wiring the ported pieces to the
new chokepoint*, not porting new logic.

| # | Asset | Where it lives | Verdict | Action |
|---|---|---|---|---|
| S1 | **topic_type_log write at render-terminal** | `wr2_canva_desktop_apply.py:267` (flag-OFF) | **PORT — the P0 of this spec** | Move the INSERT into the HTML chokepoint (same transaction as the `rendered` promote in `_pg.persist_html_result_and_enqueue_notifications`, or best-effort right after, mirroring the Canva pattern `ON CONFLICT (draft_id) DO NOTHING`) |
| S2 | Anti-monotony soft-steer + 9 image modes | ALREADY in B (`wr2_draft_generator.py:826-960`, `wr2_topic_type.py`) | KEEP | No port needed; starves without S1 |
| S3 | Anti-monotony hard-reject | ALREADY in B behind `WR2_ANTIMONOTONE_ENFORCE` (default OFF) | ARM LATER | Metric-gated: arm when `topic_type_log` ≥ 20 rows post-S1 (panel: confirm threshold) |
| S4 | Voyager curriculum (underrepresented-topic detection) | gen-1 `_voyager-curriculum.py` reading SQLite log fed by nothing | PORT (small) | Re-point reads to PG `topic_type_log` (mig 216); output feeds topic_selector steer. Low priority, stage 2 |
| S5 | Topic selection scoring | ALREADY live in B (`wr2_topic_selector.py`, cron 05:10) | KEEP | A never had a better one — `topic_ready` had no producer |
| S6 | Narrative-arc storyboarding (multi-subagent Hook/Frame/Discovery/Closing) | orchestrator PIPELINE_STEPS | **DROP** | B's single-pass draft prompt already encodes hook discipline + slide arc; the designer vision-loop (#1228) owns visual composition. A's subagent fan-out never survived production (crash-loop history) and costs OAuth quota |
| S7 | Critic 4-rubric gate | orchestrator critic step + `backend/services/war_room/critic_rubric.py` (zero non-A consumers, verified grep) | DROP (defer) | Visual quality = designer-loop converged gate; facts = fact-checker. Brand-voice rubric is the only uncovered axis — defer as optional post-render check, NOT in P-1 (panel: confirm) |
| S8 | `publish_after_approval` + `IGPublisher` + `wr2_publish_attempts` | orchestrator:818-906, backend publisher | **DROP — Legge 5** | Never used (0 rows). Removing it deletes the only IG-publish capability on this machine: turns "Legge 5 by convention" into "Legge 5 by construction" |
| S9 | Supervisor event-driven motor + reconciliation | `wr2_supervisor.py` (B asset, currently disabled) | **REPAIR + RE-ENABLE** | Patch TRANSITIONS last hop `canva-apply → html-apply`, drop dead `briefed_facted` row, re-enable. Alternative (cron-per-stage) rejected: loses event-latency + reconciliation, and the plists were stripped of schedules by design |
| S10 | Supervisor watchdog | `wr2_supervisor_watchdog.py` (loaded but frozen-checks disarmed) | REPAIR | Re-key PIPELINE_FROZEN/success-rate checks to `wr2_html_renderer_enabled` |
| S11 | A state machine (`wr2_carousel_runs`, `transition_state`) | orchestrator | DROP | B's status flow on `war_room_drafts` is the live state machine |
| S12 | Per-run worktree spawn (dispatcher) | dispatcher | DROP | irrelevant to B |
| S13 | Damar queue UI (gen-1) | `_damar-queue-server.py` (running) | KEEP-FOR-NOW, decision deferred | The LIVE delivery is WhatsApp+Drive; the queue UI is a parallel manual surface. Retiring it is an Antonello/Damar UX decision, not architecture — out of P-1 |

---

## §3 TARGET ARCHITECTURE — one pipeline

```
                       mata-garuda bridge (hourly, intel staging)
                                      │
   05:10 cron ─► topic_selector ──────┴──► war_room_drafts(status='briefed')
                      ▲                                  │ NOTIFY wr2_status_change
                      │ steer (avoid-list / curriculum)  ▼
                      │                        ┌─ SUPERVISOR (re-enabled, patched) ─┐
        PG topic_type_log (mig 216)            │  LISTEN + reconcile → kickstart    │
                      ▲                        └────────────────────────────────────┘
                      │ S1 write                  │         │         │         │
                      │                           ▼         ▼         ▼         ▼
                 html_render_apply ◄── fact_checker ◄── fact_extractor ◄── image_generator ◄── draft_generator
                      │  (chokepoint, kill-switch wr2_html_renderer_enabled)
                      ├── PNGs → Google Drive (SA-DWD)
                      ├── status='rendered'  ◄— TERMINAL SOFTWARE STATUS (Legge 5)
                      ├── INSERT topic_type_log (S1 — closes the variety loop)
                      └── wa_outbox → WhatsApp (Antonello + Damar) with Drive link
                                          │
                                  HUMAN (Damar) publishes manually on Instagram
                                          │
                          (optional later: mark-published backfills
                           topic_type_log.published_at — panel B of mig 216)
```

Properties preserved / gained:

1. **Legge 5 by construction**: after S8 removal, `grep -rn "IGPublisher\|graph.facebook"` over
   `scripts/ + backend/services` returns zero runtime hits. No code path can publish.
2. **Terminal status `rendered`** unchanged; review delivery = durable `wa_outbox` (existing,
   tested C1-C7 in #1236).
3. **Variety loop closed end-to-end**: draft_generator steer (read) ← PG topic_type_log ← S1
   write (chokepoint) — same table, one store. SQLite duplicate retired with gen-1 curriculum
   port (S4).
4. **One motor**: supervisor (event + reconcile). One renderer: HTML engine. Canva = manual
   special-pieces only (per 2026-06-06 decision), zero WR2 cron involvement.
5. **Watchdog re-armed** on the real flag — PIPELINE_FROZEN protection works again.

Operational pre-requisites (not architecture, but block the E2E metric):
- **PRE-1**: fix fact-extractor `ClaudeOAuthError keychain exit=1` under launchd (token must be
  readable by launchd context — same family as the wa-media keychain fix #1208: dedicated
  unlockable keychain or env-file 0600).
- **PRE-2**: P0 from the 2026-06-11 audit — `wr2_html_render_apply.py` httpx INFO logs the
  Telegram token into `~/logs/wr2-html-apply.log`; silence httpx INFO + rotate token (separate
  fix, already tracked).

---

## §4 RETIREMENT PLAN — staged, each stage reversible

### R0 — already done (F23, 2026-06-11), verify only
A's three LaunchAgents are booted out + disabled. Acceptance: `launchctl print-disabled gui/501
| grep -E "carousel-dispatcher|telegram-gate|wr2.supervisor"` → 3 × disabled; `launchctl list |
grep -cE "carousel-dispatcher|telegram-gate"` → 0. (Supervisor's disable gets REVERSED in R4.)

### R1 — repo deletion of Pipeline A (one PR, pure deletion, trivially revertable)
Order matters: consumers first, then producers, then backend.
1. Delete plists: `com.balizero.wr2.carousel-dispatcher.plist`, `com.balizero.wr2.telegram-gate.plist`
   (on Pro: `rm` after `launchctl bootout` no-op since already out). Keep `.backup-wr2-2026-04-23/` untouched.
2. Delete HOME wrappers `~/scripts/wr2-carousel-dispatcher-wrapper.sh`, `~/scripts/wr2-telegram-gate-wrapper.sh`.
3. `git rm scripts/wr2_carousel_orchestrator.py scripts/wr2_carousel_dispatcher.py scripts/wr2_telegram_publish_gate.py`
   (+ their tests if any reference them — grep first).
4. Backend: remove `ig_publisher` startup validation + registration from
   `service_initializer.py:1021-1040` and the lifespan close hook in `app_factory.py:604`;
   `git rm backend/services/publisher/ig_publisher.py` + prune `publisher/__init__.py` exports;
   `git rm backend/services/war_room/critic_rubric.py` (zero consumers).
5. DB (separate migration, AFTER 30-day observation): drop `wr2_carousel_runs`,
   `wr2_orchestrator_metrics`, `wr2_carousel_events_outbox`, `wr2_publish_attempts`. Until then
   they sit inert (0 write paths once code is gone).
   Grep-gates (all must be 0 hits in runtime code before merge):
   `grep -rn "topic_ready\|wr2_carousel_orchestrator\|wr2_telegram_publish_gate\|IGPublisher\|wr2_publish_attempts" scripts/ apps/backend-rag/backend --include='*.py' | grep -v tests/`

### R2 — Canva WR2-lane retirement (AFTER acceptance metric M1 green ≥3 consecutive E2E)
1. `launchctl bootout gui/501/<label> && launchctl disable gui/501/<label>` for:
   `canva-apply`, `canva-gc.weekly`, `canva-lease-watchdog.10min`, `canva-token-watchdog.daily`,
   `canva-oauth-watchdog` (canva-renderer already disabled). Order: apply first (the only one
   that mutates drafts), watchdogs last.
2. `git rm` the WR2-lane Canva scripts: `wr2_canva_desktop_apply.py`, `wr2_canva_headless_apply.py`,
   `wr2_canva_headless_probe.py`, `wr2_canva_pdf_apply.py`, `wr2_canva_pdf_render.py`,
   `wr2_canva_reconcile.py`, `wr2_canva_garbage_collector.py`, `wr2_canva_lease_watchdog.py`,
   `wr2_canva_token_watchdog.py`, `wr2_validate_master.py`, `lint_canva_pending.py` — ONLY after
   S1 has moved the topic_type_log INSERT out of `wr2_canva_desktop_apply.py`.
   `wr2_bootstrap_canva_oauth.py` MAY stay (Canva remains for manual special pieces — Antonello call).
3. Leave `system_settings` rows in place (historical record, no reader).
   Grep-gate: `grep -rln "wr2_canva" scripts/ --include='*.py'` → only allowed survivors.
   Rollback: `git revert` + re-bootstrap plists from git history; flag flip back is 1 SQL UPDATE.

### R3 — worktree + branch cleanup (independent, any time)
For each of the 5 worktrees in §1.8: prove subsumption by content, not ancestry:
`git diff <branch> origin/main -- scripts/wr2_html_renderer/ scripts/wr2_html_render_apply.py`
→ empty or main-is-newer ⇒ `git worktree remove <path>` + `git branch -D <branch>`.
If a diff shows branch-only content: STOP, escalate (it's unmerged work).
Acceptance: `git worktree list | grep -c wr2` → 1 (only this consolidation worktree, which is
removed at PR merge).

### R4 — motor re-enable (the only state-changing step, behind its own verification)
1. Patch `wr2_supervisor.py` TRANSITIONS: `('drafts_imaged_facted','drafts_imaged_checked') →
   "com.balizero.wr2.html-apply"`; remove dead `briefed_facted` rows; update reconciliation map
   symmetrically.
2. Patch `wr2_supervisor_watchdog.py`: frozen/success checks keyed to `wr2_html_renderer_enabled`.
3. Merge → deploy-puller syncs deploy worktree → `launchctl enable gui/501/com.balizero.wr2.supervisor
   && launchctl kickstart gui/501/com.balizero.wr2.supervisor`.
4. Watch 24h: heartbeat fresh, no kickstart of canva-apply (grep supervisor log).
   Rollback: `launchctl disable` again — stages stop advancing automatically (= today's state).

---

## §5 RISKS + FALSIFIABLE ACCEPTANCE (Legge 7)

| ID | Stage | Metric (before → after) | Command |
|---|---|---|---|
| M1 | E2E render | 0 HTML-lane `rendered` since cutover → **≥1 draft `rendered` with drive_url + wa_outbox row** | SQL: `SELECT count(*) FROM war_room_drafts WHERE status='rendered' AND drive_url IS NOT NULL AND updated_at > '2026-06-11'` |
| M2 | S1 variety write | topic_type_log last write 2026-06-08 (orphaned) → **every new `rendered` draft has a row** (count equality) | SQL join war_room_drafts/topic_type_log on draft_id |
| M3 | Variety itself | dominant_mode unknown 6/7 (86%) → **≤30% unknown over the next 10 renders AND ≥3 distinct modes** | SQL GROUP BY dominant_mode on rows with rendered_at > cutover |
| M4 | Legge 5 by construction | IGPublisher importable + validated at startup → **grep 0 runtime hits**; backend boots without ig_publisher registration | grep-gate in R1.5 + `pytest` app-factory smoke |
| M5 | Dead-code mass | A scripts 3 files ≈ 94KB + backend publisher → **deleted; `topic_ready` grep = 0** | `ls`, grep |
| M6 | Motor | stages advance only manually → **supervisor heartbeat < 300s stale, 0 manual kickstarts needed for a full draft→rendered run** | `SELECT max(...) FROM wr2_supervisor_heartbeat` + launchd log |
| M7 | Crash-loop hygiene | 4 disabled labels with plists on disk → **0 loaded WR2 jobs with non-zero last-exit related to A**; no exit-75 entries | `launchctl list \| grep wr2` |
| M8 | Worktrees | 5 residual WR2 worktrees → **1 (this one) then 0** | `git worktree list` |
| M9 | Watchdog re-armed | frozen-check "skipped (canva kill switch OFF)" in log → **frozen-check executes against html flag** | log grep after R4 |

Risks:

| Risk | Mitigation |
|---|---|
| Supervisor re-enable kicks wrong/extra stages (stale TRANSITIONS beyond the known hop) | R4 ships with a unit test asserting the full TRANSITIONS map against the §1.3 state machine; 24h observation; rollback = disable |
| S1 write in the SAME transaction as promote could fail the render on a variety-log error | Mirror the Canva pattern: best-effort write AFTER the promote, `ON CONFLICT DO NOTHING`, failure = WARN not raise (canva_desktop_apply.py:231 precedent) |
| fact-extractor keychain failure blocks the whole E2E (PRE-1) | Fix before measuring M1; known recipe from #1208 (env-file 0600 + wrapper source) |
| R2 deletes a Canva script some manual flow still uses | Antonello GO gate on the R2 file list; `wr2_bootstrap_canva_oauth.py` kept by default |
| Drop of `wr2_*` A-tables breaks an unknown reader | 30-day inert observation between code deletion and migration; postgres-nuzantara read-only scan of `pg_stat_user_tables` seq/idx scans before drop |
| Deploy-worktree drift re-runs old code after merge (W50-class) | deploy-puller is hourly + M1 measured AFTER `git -C ~/Desktop/nuzantara-deploy rev-parse HEAD` matches merge SHA |

Staging: **slice 1 = S1 + S10 + supervisor TRANSITIONS patch (code-only, behind the existing
kill-switch, no launchctl change)** → panel → GO → merge → R4 enable → M1/M2 green → R1 → R2 → R3.

---

## §6 4-LLM PANEL VERDICT (appended after run)

_Pending — asymmetric panel per sota-architecture-loop: Gemini (agy) red-team, Codex GPT-5.5
constructive, DeepSeek V4 Pro logic. NB-1 skipped with reason: internal disk-state domain,
zero regulatory facts at stake (NB would be noise per the loop's ground rules)._
