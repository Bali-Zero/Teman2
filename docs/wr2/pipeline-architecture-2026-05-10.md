# WR2 carousel pipeline — architecture review (2026-05-10)

Audit done after the night-of recovery cycle that fixed PRs #552, #565,
#566, plus this hardening PR. This document captures the architectural
findings (M1, M2 from the audit) and the migration paths the operator
can take when budget allows.

## Today's pipeline (as of 2026-05-10)

```
Topic selector → topic
       │
       ▼
Brief interpreter → briefed
       │
       ▼
Draft generator → drafts (slides_json populated)
       │
       ▼
Image generator → drafts_imaged
       │
       ▼
Fact extractor / checker → drafts_imaged_checked
       │
       ▼
[FIFO queue, MAX_DRAFTS_PER_RUN=1]
       │
       ▼
wr2_canva_desktop_apply.py (LaunchAgent)
       │
       ├─ writes:  apps/war-room/output/canva/canva_pending.json
       │
       ├─ AppleScript: Cmd+N + paste skill body in Claude Desktop
       │
       │   ┌──────────────────────────────────────┐
       │   │  Claude Desktop runs canva-apply     │
       │   │  ──> Phase -1 validate (NEW)         │
       │   │  ──> Phase 0 wipe master text        │
       │   │  ──> Phase A apply ops to master     │
       │   │  ──> Phase B resize-design (clone)   │
       │   │  ──> Phase C wipe master again       │
       │   │  ──> Phase D write carousel_canva.json│
       │   └──────────────────────────────────────┘
       │
       ├─ polls:    apps/war-room/output/canva/carousel_canva.json
       │
       └─ on success: UPDATE war_room_drafts SET status='rendered',
                              canva_design_id=...
```

## M1 — Three sources of truth, only one canonical

State of a single draft lives in three places:

1. **`war_room_drafts` (Postgres)** — `status`, `canva_design_id`,
   `canva_edit_url`, `canva_view_url`, `canva_applied_at`. The pipeline
   stages all read/write here.
2. **`canva_pending.json` (filesystem)** — input to the apply skill.
   Status flips `pending` → `applied` when the skill finishes.
3. **`carousel_canva.json` (filesystem)** — output of the apply skill.
   Has `design_id` and `status: applied` after Phase D.
4. **Canva folder contents** — the actual designs in the Carousel
   folder, queryable via `mcp__claude_ai_Canva__list-folder-items`.

Three of these can disagree:

- **DB vs JSON**: if the script times out before persisting, JSON shows
  `applied` but DB still says `drafts_imaged`. Observed 2026-05-10
  03:48 WITA on draft de69f035. Fixed in this PR via late-reconciliation
  in the script + `wr2_canva_reconcile.py` standalone tool.
- **JSON vs Canva**: `carousel_canva.json` only reflects the LAST run.
  If the same skill ran twice (re-kickstart, manual experiment), the
  earlier design exists in Canva but is missing from JSON. Observed
  with `DAHJNBAUUOk` tonight.
- **Canva vs DB**: orphan designs in the folder with no draft pointer.
  Cleanup job is now `wr2_canva_garbage_collector.py`.

**Decision (recorded in this PR):** the database is the canonical
state. The JSON files are effimeral I/O between the script and the
skill — they should NOT be relied on as durable state. Future contracts
should:

- Have the skill write directly to Postgres via a thin shim (e.g. a
  SQL UPSERT script the skill calls after Phase D, instead of writing
  JSON). This eliminates the script's poll loop entirely.
- Or keep the JSON but auto-prune it after the script reads it once
  (so a stale JSON can never lead to confusion).

Neither is shipped here. The reconciler script (`wr2_canva_reconcile.py`)
is the bridge: when the gap appears, run it manually.

## M2 — GUI automation as a production-critical path

The current architecture orchestrates a daily-cadence editorial pipeline
through Claude Desktop's GUI, driven by AppleScript Cmd+V + Enter. This
emerged organically from a prototype and has notable limitations:

- **Throttling**: Claude Desktop has its own usage envelope and Canva
  MCP latency. Skill durations observed tonight: 412s (run #1), ~25min
  (run #2 throttled), ~7min (run #3). Variance is 4×.
- **Focus contention**: AppleScript fails if the Claude window isn't
  frontmost. Tonight every kickstart's attempt 1/5 failed because the
  operator was still in iTerm2 when the script started. Mitigated in
  this PR with `PRE_KEYSTROKE_GRACE_SEC` (default 8s).
- **State fragility**: closing Claude Desktop or restarting the Mac
  invalidates the active session, which the apply step assumes is open.
- **Manual presence**: the operator MUST be at the workstation when a
  run kicks off (to bring Claude forward + leave it idle). Production
  cron CAN'T fire reliably without human babysitting.

Three migration paths considered:

### Path A: Headless Canva REST API

Investigated — rejected. The Canva Connect API does not expose
element-level text replacement on custom Instagram designs. The
pipeline depends on `replace_text` operations and `update_fill` for
hero images, neither available outside the MCP / authenticated
desktop session.

### Path B: Headless Playwright with persisted Canva session

Doable. Approach:

1. Operator logs into Canva once in a Playwright-controlled browser.
2. Save `storageState.json` to disk (cookies + localStorage).
3. Future runs spawn a headless Chromium with that state, drive the
   Canva editor URLs directly with `page.evaluate()` calls that hit
   Canva's internal client APIs (the same ones the MCP uses).
4. Replace `wr2_canva_desktop_apply.py` with `wr2_canva_playwright.py`.

Estimated effort: 2-3 dev-days. Wins:
- Production cron can fire without operator presence.
- No focus contention (browser is hidden).
- Skill duration becomes deterministic (no Claude Desktop in the loop).

Risks:
- Canva can rotate their internal API and break us. Periodic re-auth
  required (storageState expires).
- Reverse-engineering effort for Phase A's adaptive remap that the
  current skill does as a "seasoned designer" — Playwright would need
  the same logic in plain Python.

### Path C: Keep Desktop, add monitor watchdog

Lightest touch. The current PR already adds:
- Reconciler script (recovers from missed UPDATE).
- Plist watchdog (recovers from disappeared LaunchAgent).
- Daily metrics (visibility into how often the failure modes fire).

If the failure rate stays acceptable (< 1 manual-intervention/week),
Path C is the right ROI. Only re-evaluate if the pipeline scales beyond
3-5 carousels/day or if Damar (the consumer) becomes blocked by
manual cycles.

## Decision (this PR)

**Take Path C now.** Re-evaluate after 30 days of metrics. Concretely:

1. The hardening shipped in this PR makes Path C self-healing for the
   identified failure modes.
2. `wr2_daily_metrics.py` will tell us if Path B is needed.
3. The reconciler is a pressure release valve so manual interventions
   don't lose data.

If, after 30 days, `wr2_daily_metrics.py` reports a reconciliation gap
> 0 on more than 7 days, OR if median skill duration goes above 15 min,
escalate to Path B.
