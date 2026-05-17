# Design: ZANTARA COCKPIT — Hybrid dashboard + EvoSkill MVP

**Date**: 2026-05-17
**Status**: v2 revised after 4-LLM panel (DeepSeek + Codex + devils-advocate; Gemini 429-exhausted)
**Codename**: ZANTARA COCKPIT (centro di comando organismo Bali Zero)
**Author**: Claude Opus 4.7 (1M context)
**Recovery note**: re-written 2026-05-17 after worktree destruction by sibling automation (first PR draft commit was never reached — lesson: commit spec IMMEDIATELY on creation).

## Panel review history

**v1 panel** (4-LLM 2026-05-17): 4 CRITICAL convergent 2-3/3:

1. **Migration 178 collision** vs existing `178_dream_room_state.sql` (Codex empirical + devils-advocate F1) → **v2 fix**: renumber 180+181
2. **Action layer mutates DB-directly bypass services + lease** (Codex contradiction L178-L181 vs L397, devils-advocate F5) → **v2 fix**: intent-table pattern, cockpit writes only to `cockpit_intents`, existing services/cron consume
3. **9 POST endpoints + rate-limit posticipato S5** (DeepSeek CRITICAL, Codex CRITICAL) → **v2 fix**: rate-limit from S1, action allowlist hardcoded, no `gh pr merge` from cockpit
4. **3 SSE streams + PG pool max=3 starvation** (DeepSeek CRITICAL, Codex HIGH, devils-advocate F3 verified empirically `db.ts:20`) → **v2 fix**: singleton SSE multiplexed + dedicated pg.Client outside pool

Plus 8 HIGH addressed inline (PIN brute-force protections, WR2 channel separation from supervisor, lease check on cron kill, WR2 lifecycle states audit against migration 163, EvoSkill strip verification deferred, plist worktree path trap hardcoded main path, NB-INTEL Health routing audit, SSE timeout 30min + heartbeat 25s).

Panel artifacts: `/tmp/cockpit-review-{deepseek,codex,gemini}.txt`, devils-advocate report (15 findings).

---

## Context

Bali Zero opera 16 Claude subagent + 124 launchd cron (35 agentic + 89 infra) + 50 NB attivi + 3533 sources NotebookLM. L'organismo è già **in produzione**. Mancano 2 cose:

1. **Antonello vede solo via Telegram alert** — niente immediatezza operativa, niente "click to act"
2. **Le 2 file in `agent-library/` (02-patterns + 03-lessons) sono carta morta** — invecchiano da soli, già drift al merge (60 NB scritti, 50 reali)

Questo spec disegna un sistema hybrid:

- **A — Zantara Cockpit**: dashboard locale Pro-only con design Bloomberg terminal + 12 widget (4 globali + 4 Intel-Lake + 4 WR2). Action layer per dare ordini via intent-table.
- **B — agent-library-evolver**: backend EvoSkill-vendored che evolve settimanalmente i 2 file, scrivendo PR draft. Il Cockpit le mostra come "Decisions Attesa" cliccabili.

Insieme chiudono il loop: organismo apprende (B) → Antonello vede e governa (A) → organismo riceve direttive (A → intent queue → cron consume).

---

## Mappa empirica stack (verified)

### Dashboard base esistente (`apps/admin-dashboard-local/`)

- Next.js **16.1.6** + React 18 + Tailwind 3.4 + recharts 2.13 (no shadcn, no SWR, no WebSocket)
- 2 route attive: `/cost-dashboard` (6 widget cost LLM) + `/observatory` (30s polling cell observatory)
- `lib/db.ts`: lazy Pool max 3, auto-detect `DATABASE_URL_LOCAL` → `FLY_TUNNEL_URL` fallback
- Theming: `html className="dark"` forced, slate-950 palette, **no design tokens**, **no CSS variables**
- `next.config.mjs`: `LOCAL_ONLY=1` env guard (crash on Vercel/Fly deploy)
- Avvio: `bash scripts/start-cost-dashboard.sh` → port 3100

### Intel-Lake stack

| PG table               | Purpose                                      | Mig |
| ---------------------- | -------------------------------------------- | --- |
| `intel_items`          | Canonical SoT, 12+ producers, routing_status | 168 |
| `intel_observations`   | Append-only producer-hit log                 | 168 |
| `intel_lake_audit_log` | Endpoint auth audit                          | 168 |
| `intel_validator_log`  | 3-tier validation (regex+citation+kg)        | 116 |
| `intel_item_nb_pushes` | N:M routing item→NB                          | 171 |
| `events_outbox`        | Durable replay-on-reconnect                  | 144 |

| Cron                             | Schedule | Script                                   |
| -------------------------------- | -------- | ---------------------------------------- |
| `intel-lake-router.5min`         | 300s     | `~/scripts/intel-lake-router-cron.sh`    |
| `intel-lake-nb-pusher.15min`     | 900s     | `~/scripts/intel-lake-nb-pusher-cron.sh` |
| `intel-lake.outbox-drain.minute` | 60s      | `~/scripts/intel-lake-outbox-drain.py`   |
| `intel-lake.shadow-validate.6h`  | 21600s   | disabled at startup                      |

**Sources**: `apps/bali-intel-scraper/config/unified_sources.json` — **609 sources, 18 categories**.

**NB-INTEL routing**: 5 NB UUIDs (Immigration, Tax, Regulation, AI-Research, Press) per `scripts/intel-lake-router-a2/intel-lake-routing-rules.json:8-14`.

**Validators**: 3-tier (regex 0.3 + citation 0.4 + kg 0.3), score ≥0.6 → valid.

### WR2 stack

| PG table                   | Purpose                                       | Mig |
| -------------------------- | --------------------------------------------- | --- |
| `war_room_drafts`          | Drafts lifecycle (17 states verified mig 163) | 112 |
| `war_room_metrics`         | Post-publication (IG/Brevo/UTM)               | 112 |
| `wr2_supervisor_heartbeat` | Liveness probe 60s                            | 161 |

**WR2 lifecycle states** (v2 audit fix Codex HIGH): production constraint in `migration 163_war_room_status_fact_stages.sql:37` has **17 states**, not 9. S3 deliverable MUST audit live constraint via `\d+ war_room_drafts` before designing pipeline widget.

**Canva renderer v2** (`apps/backend-rag/backend/services/canva_renderer_v2/`, 10 moduli): orchestrator + lease CAS (`_pg.py:48-69`) + reset_stale_leases (`159-176`) + token storage HMAC+flock + canva MCP + PDF pipeline.

**WR2 cron** (16+ plist `com.balizero.wr2.*`): supervisor daemon + watchdog 60s + draft-generator + fact-checker + fact-extractor + image-generator + canva-renderer 5min + canva-apply + lease-watchdog 10min + oauth-watchdog + token-watchdog daily + gc weekly + measurer 6h + daily-metrics + sla-worker 30min + trend-hunter 2h.

**OAuth Canva**: `~/.config/wr2/canva_tokens.json`, HMAC integrity, flock exclusive, proactive refresh 300s margin.

---

## Design language (locked)

**Bloomberg Terminal neon-green** — inspired by **Signal** (DashboardPack 2026):

- Background: `#0a0e0a` (near-black green tint), `#0f1411` (panel)
- Foreground: `#00ff41` (matrix green, healthy), `#39ff14` (active)
- Accents: `#ffb000` (amber, warning), `#ff3838` (red, critical)
- Typography: **JetBrains Mono**. Sizes 11/13/15/18px (dense)
- Borders: `#1f2a1f` thin 1px
- Layout: dense grid 4×3, no hero, no marketing
- Charts: recharts neon palette, no gradients

CSS variables in `cockpit-shell.css`, scoped to `data-cockpit="true"` root.

---

## Architecture v2

### Action layer — intent-table pattern (v2 CRITICAL fix)

Cockpit **NEVER** writes directly to PG tables with services + lease + state machines (`war_room_drafts`, `intel_items`). Writes to **`cockpit_intents`** (mig 181), existing services/cron consume.

```
# READ-ONLY endpoints (S1):
GET  /api/cockpit/cron/list           → launchctl print parsed (cached 2s)
GET  /api/cockpit/decisions           → gh pr list --draft + escalations
GET  /api/cockpit/intel/stats         → SELECT count by routing_status
GET  /api/cockpit/wr2/drafts          → SELECT war_room_drafts (read-only)
GET  /api/cockpit/canva/status        → read canva_tokens.json + lease state

# SAFE actions (S1+, non-destructive):
POST /api/cockpit/cron/run            {label} → launchctl start (allowlist 35 agentic)
POST /api/cockpit/wr2/brief           {topic} → spawn wr2_draft_generator.py subprocess

# INTENT-TABLE actions (S2+, destructive):
POST /api/cockpit/intent/create       {action, params, reason} → INSERT cockpit_intents

# Specific intents (consumed by existing services):
- intent='intel.skip'        → intel-lake-router-cron.sh next run
- intent='intel.rerun'       → re-emit outbox event
- intent='wr2.approve'       → wr2_supervisor.py (CAS-aware)
- intent='wr2.reject'        → wr2_supervisor.py
- intent='cron.kill'         → Telegram alert to Antonello, NO auto-exec
- intent='library.approve-pr'→ Antonello manual merge
```

**Safety layer v2** (panel finding 4-LLM):

1. **Origin check**: only `localhost`/`127.0.0.1` (rejects remote even VPN)
2. **PIN bcrypt** in `~/.config/zantara-cockpit/pin.hash` — file mode `0600`
3. **Rate-limit FROM S1** (panel CRITICAL): in-memory Map TTL, 5 failed → 5min lockout per client
4. **2-step modal** + 1s delay + reason text required for any intent
5. **Action allowlist hardcoded** in `lib/cockpit-allowlist.ts`: 35 agentic cron labels
6. **Audit log immutable**: `cockpit_audit_log` with HMAC-SHA256 chain (mig 180)
7. **No `gh pr merge`** from cockpit (panel CRITICAL): cockpit emits intent, Antonello merges manually
8. **No direct DB writes** to live tables: cockpit → `cockpit_intents` + `cockpit_audit_log` only

**Migration numbers v2** (panel CRITICAL F1 empirical):

- `178_dream_room_state.sql` exists (verified Codex)
- `179_newsletter_confirmation_token_unique.sql` exists
- Cockpit migrations: **180** audit, **181** intents

### Realtime — v2 SINGLETON multiplexed (post-panel)

v1 had 3 SSE streams each holding `pg.Client`, saturating `max:3` pool.

**v2 architecture**:

- ONE SSE connection per browser (channel-multiplexed via `?ch=live,intel,wr2`)
- ONE dedicated `pg.Client` per Node.js process (OUTSIDE main pool, lifecycle in `lib/cockpit-sse.ts`)
- LISTEN channels: `intel_lake_event`, `war_room_drafts_update` (new, NOT `wr2_status_change` which belongs to supervisor — panel F4), `cockpit_pulse`
- Heartbeat 30s, `Last-Event-ID` resume, backoff jitter (1s→30s max)
- Connection cap: 1 SSE per browser session (cookie `cockpit-session-id`)
- Reconnect storm: >5 drops/60s → frontend "degraded mode" banner

**S1 scope**: NO SSE yet (deferred to S5). S1-S4 use **polling only** (10s/30s/60s per widget).

### Files structure (S1 target)

```
apps/admin-dashboard-local/
  app/cockpit/
    layout.tsx                        # JetBrains Mono + Bloomberg shell
    page.tsx                          # 12-widget grid
    cockpit-shell.css                 # CSS variables
  app/api/cockpit/
    auth/route.ts                     # POST PIN verify
    cron/list/route.ts                # GET cron status
    cron/run/route.ts                 # POST allowlisted run
    decisions/route.ts                # GET pending PRs
    intent/create/route.ts            # POST intent queue
  components/cockpit/
    WidgetFrame.tsx
    StatusDot.tsx
    WidgetPlaceholder.tsx
    PinGate.tsx
    GlobalPulse.tsx                   # Widget 1 LIVE
    DecisionsAttesa.tsx               # Widget 2 LIVE
  lib/
    cockpit-allowlist.ts              # 35 agentic cron hardcoded
    cockpit-auth.ts                   # bcrypt + rate-limit
    cockpit-audit.ts                  # HMAC SHA-256 chain
    cockpit-launchctl.ts              # parse launchctl print, cache 2s
    cockpit-pg.ts                     # PG query helpers + audit insert + intent create
  middleware.ts                       # origin + PIN cookie gate
  scripts/
    setup-cockpit-pin.sh              # interactive PIN init
    start-cockpit.sh                  # LOCAL_ONLY=1 + COCKPIT_HMAC_KEY launcher
  tests/cockpit/
    allowlist.test.ts
    auth.test.ts
    audit.test.ts

apps/backend-rag/backend/db/migrations_v2/
  180_cockpit_audit_log.sql           # HMAC chain
  181_cockpit_intents.sql             # intent queue
```

---

## Anti-pattern mitigation

| Risk                               | Mitigation                                                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Action without confirmation        | 2-step modal + 1s delay + PIN required + reason min 5 chars                                                 |
| Stale data shown                   | Polling with status dot stale-after-N indicator                                                             |
| Cockpit DB-write to live tables    | Read-only by default; intents only                                                                          |
| Auth bypass                        | Origin localhost + PIN bcrypt + audit log + rate-limit S1                                                   |
| EvoSkill privacy leak              | Companion spec v5 — redaction layer mandatory fail-closed                                                   |
| EvoSkill v1.1.0 strip verification | S4 Phase 0: AST scan + `py_compile` gate before any vendor commit                                           |
| Worktree path trap                 | S5 plist HARDCODES `/Users/nuzantara/Desktop/nuzantara/apps/admin-dashboard-local/...` (main, NOT worktree) |
| Self-induced load `launchctl list` | Single `cockpit-launchctl.ts` instance, 2s cache, 35-label allowlist (no full launchctl list)               |
| Audit log mutability               | HMAC SHA-256 chain (panel MEDIUM)                                                                           |
| Cost runaway                       | EvoSkill `BUDGET_USD=1.00` per-iter fail-closed                                                             |

---

## Cost & LLM routing

**Cockpit (A)**:

- Zero LLM calls inline. All LLM via subprocess (cron, EvoSkill).
- Hosting: localhost Pro, $0.
- Monthly est: **$0**.

**EvoSkill MVP (B)**: see companion spec v5.

- Per weekly run: ~$0.10-0.20 DeepSeek
- Monthly est: **~$1.00**

---

## Verification & rollout

| Phase    | Action                                                                  |
| -------- | ----------------------------------------------------------------------- |
| S1 smoke | localhost:3100/cockpit visible, 12-widget grid, 2 live + PIN gate works |
| S2 smoke | skip 1 intel item via intent, observe in widget                         |
| S3 smoke | approve 1 draft via intent, observe transition                          |
| S4 smoke | dry-run evolver, verify proposals output, NO real PR                    |
| S5 smoke | E2E browser test, launchd plist auto-boot, SSE live                     |

---

## 5-session roadmap (parallel max)

| Sess            | Track                                | Effort | Output                                                                    |
| --------------- | ------------------------------------ | ------ | ------------------------------------------------------------------------- |
| S1 Foundation   | sequential                           | 15h    | PR draft #1: shell + grid + 2 widget + auth + intent skeleton             |
| S2 Intel-Lake   | parallel A (after S1 merge)          | 15h    | PR #2: 4 widget + intent consumers wire                                   |
| S3 WR2          | parallel B (after S1 merge)          | 15h    | PR #3: 4 widget + canva integration                                       |
| S4 EvoSkill MVP | parallel C (off main, after S1 spec) | 12h    | PR #4: vendor + cron + draft PR pipeline                                  |
| S5 Polish       | sequential (after S2+S3+S4)          | 8h     | PR #5: SSE multiplexed + Cosa Imparato + Comandi Rapidi + plist auto-boot |

**Total wall-clock parallelized**: ~38h vs 65h sequenziale.

---

## Known limitations v1 (accepted)

| Limitation                                 | Severity | Plan action                 |
| ------------------------------------------ | -------- | --------------------------- |
| No mobile UI                               | LOW      | Tailwind responsive partial |
| No multi-tenant                            | LOW      | Antonello-only              |
| No history view                            | MEDIUM   | v2 add time-series          |
| EvoSkill upstream refresh manual quarterly | MEDIUM   | UPSTREAM.md tracked         |
| FTS5 BM25 threshold not calibrated         | MEDIUM   | Smoke phase 0               |
| recharts limited customization             | LOW      | OK v1                       |

---

## References

- Companion spec EvoSkill: `2026-05-17-agent-library-evoskill-design.md` v5
- Inspiration: DashboardPack 2026 "Signal" template
- Mapping artifacts: subagent reports (Explore Intel-Lake + WR2 + dashboard)
- Symbiosis Laws: SYMBIOSIS.md
- L2 autonomous ops: AUTONOMOUS_OPS.md
- Brand cortex: ~/.claude/skills/bali-zero-brand/
