# Design: ZANTARA COCKPIT v2 — Bali Zero brand + Subsystem command pages

**Date**: 2026-05-18
**Status**: v3 — revised after 4-LLM panel BLOCKER verdict (Codex empirical CRITICAL findings, Devils-advocate 15 findings, Gemini + DeepSeek concurring)
**Codename**: Zantara Cockpit v2 — "warm operator console" + interactive subsystem commands
**Author**: Claude Opus 4.7 (1M context)
**Replaces**: `2026-05-17-zantara-cockpit-design.md` (PR #712 CLOSED — pivot post-design-review)

---

## Context & pivot rationale

PR #712 v1 ha shippato in 26 commit un cockpit con **12-widget grid Bloomberg neon green**. Antonello al test live: _"il design fa cagare... voglio qualcosa di più caldo e home feel... poi: per ognuno si entra e c'è tutto in dettaglio giusto?"_ — risposta: **NO, drill-down non esisteva**.

v2 fa **2 cambi strutturali**:

1. **Estetica**: dalla palette Bloomberg cold (`#0a0e0a` near-black + `#00ff41` neon green) **alla palette Bali Zero brand cortex** (antracite warm + accent yellow `#F4C430` + Montserrat). I 12-widget grid sostituiti da **4 home tile + 2 door card grandi** (WR2 + Intel-Lake).
2. **Modello interazione**: dalla "lettura statica" alla "**UI che traduce CLI**". Click su WR2 door → `/cockpit/wr2` command page interattiva che fa quello che oggi fai con `python3 wr2_draft_generator.py`, `psql -c "SELECT..."`, `launchctl kickstart`. Stesso per Intel-Lake.

Riusati dalla v1 (cherry-picked in v2 branch): migrations 182+183, lib helpers (allowlist, auth, audit, launchctl, pg), tests TDD. Da riscrivere: CSS, components, page.tsx, API endpoints expanded.

---

## v3 panel-driven fixes (2026-05-18 BLOCKER → addressed inline below)

**4 CRITICAL findings empirically verified**, addressed in v3:

### CRITICAL #1 — NewBriefForm subprocess target wrong (Codex empirical)

**Finding**: `wr2_draft_generator.py` accepts only `--dry-run` and `--draft-id` (verified via `grep "add_argument"`). NO `--topic`. Calling `python3 wr2_draft_generator.py --topic X` would silently fail or error.

**v3 fix**: NewBriefForm endpoint `/api/cockpit/wr2/brief` does **NOT spawn subprocess**. Instead:

```sql
INSERT INTO war_room_drafts (topic, register, status, created_at)
VALUES ($1, $2, 'briefed', NOW())
RETURNING id;
```

The existing supervisor cron will pick up `status='briefed'` drafts and drive the pipeline (research → concept → drafts → etc.). UI feedback: optimistic insert appears immediately in PipelineKanban column "briefed".

**No subprocess spawn from cockpit in S1-S3** — eliminates entire CRITICAL #2 (sanitization).

### CRITICAL #2 — Subprocess sanitization moot (eliminated by #1 fix)

Since v3 doesn't spawn subprocess for brief creation, the sanitization concern is **eliminated**. The only subprocess calls remaining are `launchctl kickstart <label>` (allowlist-validated) and `gh pr list --json ...` (no user input). Both already safe (argv arrays, no shell).

### CRITICAL #3 — Intent table consumers don't exist (Codex empirical)

**Finding**: `cockpit_intents` has 0 readers in entire codebase. Spec assumed "existing services consume" but `grep -rn "cockpit_intents" scripts/` returns empty.

**v3 fix**: intent consumer extension is **explicit deliverable in S2/S3**, not assumed.

**S2 (Intel-Lake) deliverables expanded**:

- New: `scripts/cockpit_intent_consumer_intel.py` — polls `cockpit_intents WHERE intent_type IN ('intel.skip','intel.rerun','intel.re-fact-check') AND status='pending'`, every 30s
- For each: apply mutation (intel_items UPDATE for skip; events_outbox INSERT for rerun), mark intent `status='consumed'`, emit `cockpit_pulse` NOTIFY with `{intent_id, intent_type, result}`
- New plist `com.balizero.cockpit.intent-consumer.intel.30s` (S2 deliverable)

**S3 (WR2) deliverables expanded**:

- Modify existing `wr2_supervisor.py` to: (a) add LISTEN on `cockpit_intents_pending` (new channel), (b) on notify, fetch pending intents of type `wr2.*`, (c) apply with CAS-aware merge (`UPDATE war_room_drafts WHERE id=$1 AND status=$2 AND lease_owner IS NULL`), (d) emit `cockpit_pulse` NOTIFY on success
- New migration: trigger on `cockpit_intents` INSERT emits NOTIFY `cockpit_intents_pending`

### CRITICAL #4 — SSE channels don't exist (Codex empirical)

**Finding**: spec subscribes SSE to `cockpit_pulse` and `war_room_drafts_update` channels. Neither exists. Real WR2 channel is `wr2_status_change` (mig 138, consumed by wr2_supervisor).

**v3 fix**:

- **`cockpit_pulse`**: NEW channel created in S2 + S3 deliverables (intent consumers emit it after applying mutations, as documented in CRITICAL #3 fix above)
- **`war_room_drafts_update`**: DROPPED from spec. WR2 PipelineKanban subscribes to **`wr2_status_change`** (existing, already emitted by `wr2_supervisor`) BUT cockpit listener is **read-only fan-out** — does NOT acknowledge events (acknowledgment stays with supervisor). Risk of double-consume: zero, because cockpit only fans-out to browser SSE clients
- **`intel_lake_event`**: existing (mig 168), already emitted on INSERT. Cockpit Trace subscribes for routing visibility

Updated channel matrix:
| Channel | Emitter | Cockpit role |
|---|---|---|
| `intel_lake_event` | intel_lake mig 168 trigger | Read-only fan-out to Intel-Lake Trace |
| `wr2_status_change` | wr2_supervisor (mig 138) | Read-only fan-out to WR2 Kanban + Trace |
| `cockpit_pulse` | NEW intent-consumer scripts S2+S3 | Read-only fan-out to all Trace cards (intent execution feedback) |
| `cockpit_intents_pending` | NEW trigger S3 on cockpit_intents INSERT | Wakes supervisor to process pending intents |

### HIGH #1 — SSE singleton hot-reload (Devils-advocate F2 + Gemini + DeepSeek + Codex 4/4)

**v3 fix** in `lib/cockpit-sse.ts`:

```ts
// Singleton pattern survives Next.js hot-reload
declare global {
  // eslint-disable-next-line no-var
  var __cockpitSSE: { client: pg.Client; emitter: EventEmitter } | undefined;
}

export async function getSSESingleton() {
  if (globalThis.__cockpitSSE) return globalThis.__cockpitSSE;

  const client = new pg.Client({
    /* dedicated outside pool */
  });
  await client.connect();
  await client.query("LISTEN intel_lake_event");
  await client.query("LISTEN wr2_status_change");
  await client.query("LISTEN cockpit_pulse");

  const emitter = new EventEmitter();
  emitter.setMaxListeners(50); // cap fan-out
  client.on("notification", (msg) => emitter.emit(msg.channel, msg.payload));

  globalThis.__cockpitSSE = { client, emitter };

  // Cleanup on hot-reload (Next.js HMR)
  if (process.env.NODE_ENV === "development") {
    process.on("beforeExit", async () => {
      await client.end();
      globalThis.__cockpitSSE = undefined;
    });
  }

  return globalThis.__cockpitSSE;
}

// Route handler must register cleanup on response close
export function attachSSEClient(
  req: NextRequest,
  send: (data: string) => void,
  channels: string[],
) {
  const { emitter } = globalThis.__cockpitSSE!;
  const handlers = channels.map((ch) => {
    const h = (payload: string) => send(`event: ${ch}\ndata: ${payload}\n\n`);
    emitter.on(ch, h);
    return { ch, h };
  });

  req.signal.addEventListener("abort", () => {
    handlers.forEach(({ ch, h }) => emitter.off(ch, h));
  });
}
```

### HIGH #2 — Effort estimate 50-100% undercount (4/4 panel consensus)

**v3 revised roadmap**:

| Session                                                                               | v2 estimate | v3 honest estimate | Delta    |
| ------------------------------------------------------------------------------------- | ----------- | ------------------ | -------- |
| S1 Foundation (shell + theme + home + SSE singleton + 5 API + cherry-pick lib)        | 12-15h      | **20-25h**         | +60%     |
| S2 Intel-Lake (4 widget + drawer + 4 endpoint + SSE consumer + intent consumer cron)  | 12-15h      | **22-28h**         | +85%     |
| S3 WR2 (Kanban + 7 endpoint + supervisor patch + intent consumer integration + Trace) | 14-18h      | **26-32h**         | +85%     |
| S4 EvoSkill MVP                                                                       | 10-12h      | 10-12h             | OK       |
| S5 Polish                                                                             | 8h          | 10-12h             | +30%     |
| **TOTAL**                                                                             | 56-68h      | **88-109h**        | **+60%** |

Wall-clock parallel (S2+S3+S4 parallel after S1): ~55-70h.

### HIGH #3 — English-only enforcement on supervisor logs (4/4 panel)

**v3 clarification**: `wr2_supervisor.py` logs are already English (verified empirically: "draft %s: %s → %s", "kickstarted %s", "LISTEN wr2_status_change active"). **No retroactive translation needed** for supervisor.

Scope of English-only **NEW v3 narrowing**: applies to UI strings + new code we generate. Existing log messages in production cron scripts are **out of scope** — pre-existing Italian phrases in legacy logs (if any) are NOT a blocker.

CI lint rule (S5 deliverable): pre-commit hook greps `apps/admin-dashboard-local/{components,app,lib}` for common Italian markers (`(?i)\b(prego|grazie|annulla|elimina|conferma|attesa)\b`) — fail if found. Exempts: comments, test fixtures.

### MEDIUM — Polling + SSE flicker (Devils-advocate F5 + Gemini + DeepSeek + Codex 4/4)

**v3 fix**: SSE primary, polling **only** activates when `EventSource.readyState !== OPEN` for >30s. Hook-level state machine:

```ts
const [mode, setMode] = useState<"sse" | "polling-fallback">("sse");
// SSE connected → mode='sse' (no polling)
// SSE drops + heartbeat timeout 30s → mode='polling-fallback' (poll 10s)
// SSE reconnects → setMode('sse') + cancel polling
```

Not "polling OR SSE" anymore — explicit failover state.

### MEDIUM — Logo .gitignore cleanup

**v3 fix**: add to `.gitignore` after `*.PNG` rule:

```
!apps/admin-dashboard-local/public/balizero_logo_circle.png
!mockups/v2/assets/balizero_logo_circle.png
```

Explicit allowlist removes force-add confusion.

### Items NOT requiring spec changes (verified)

- **Migration 184 collision**: verified safe (Codex empirical: main@180, no 181 in flight, 182/183 in branch only)
- **Index `intel_observations(producer_name, observed_at DESC)`**: EXISTS in mig 168:71 (Devils-advocate F11 was false-positive)
- **`BrandTopbar` file structure**: noted in v3 component spec section explicitly

---

---

## Visual mockups (committed reference)

- `mockups/v2/html-home-v2-lighter.html` — Home v2 con palette lighter (`#3A3E4A` page + `#494E5D` card), APPROVED by Antonello 2026-05-18
- `mockups/v2/html-wr2-command-lighter.html` — `/cockpit/wr2` command page completo
- `mockups/v2/png-3-home-lighter-final.png` — Codex imagegen reference
- `mockups/v2/assets/balizero_logo_circle.png` — **Official Bali Zero logo** (940×940 RGBA, provided by Antonello 2026-05-18 from `~/Desktop/balizero_logo_circle.png`). Use everywhere — NEVER recreate via CSS div.

## Logo asset (official)

**Source**: `~/Desktop/balizero_logo_circle.png` (Antonello provided 2026-05-18)
**Format**: PNG, 940×940, 8-bit RGBA, non-interlaced
**Composition**: Black circular background, red stylized "3" + white "ALI ZERO" wordmark + Om symbol bottom-right
**Brand cortex match**: cf. `~/.claude/skills/bali-zero-brand/tokens.json:115-120` (verbatim spec)

**Deployment paths** (both copies committed):

- `mockups/v2/assets/balizero_logo_circle.png` — for design review HTML
- `apps/admin-dashboard-local/public/balizero_logo_circle.png` — for Next.js public route `/balizero_logo_circle.png`

**Component usage** in `<BrandTopbar />`:

```tsx
<img
  src="/balizero_logo_circle.png"
  alt="Bali Zero"
  width={44}
  height={44}
  style={{ borderRadius: "50%" }}
/>
```

**Sizing rule**: 36-48px in topbar contexts. Never stretch non-uniform. Never recolor. Never recreate via CSS (no div with text "3").

---

## Design tokens (locked, Bali Zero brand-cortex-derived)

```css
:root {
  /* Background — +2 tonalità lighter vs brand antracite #2C2F38 (Antonello approved 2026-05-18) */
  --bg-page: #3a3e4a; /* +8% L — page background */
  --bg-card: #494e5d; /* +14% L — elevated tiles/cards */
  --bg-card-hover: #5a6072; /* +18% L — hover state */
  --bg-inset: #2f323d; /* sunken (form inputs, code blocks, trace log) */

  /* Borders */
  --border: #6a7080;
  --border-active: #f4c430; /* yellow on focus/active (brand) */

  /* Brand tokens PRESERVED verbatim from ~/.claude/skills/bali-zero-brand/tokens.json */
  --text-white: #ffffff;
  --text-muted: #9ca3af;
  --accent-yellow: #f4c430; /* single accent — verifiability, key numbers */
  --status-red: #c8102e; /* logo + critical alerts only */
  --status-amber: #d97706; /* warn (not in brand — needed for status, OK) */

  /* Typography (brand) */
  --font-primary: "Montserrat", "Inter", "Poppins", sans-serif;
  --font-mono: "IBM Plex Mono", monospace; /* TRACE log only */

  /* Shadows */
  --shadow-soft: 0 2px 16px rgba(0, 0, 0, 0.28);
  --shadow-hover: 0 4px 24px rgba(0, 0, 0, 0.4);
}
```

**Banned per brand cortex** (verbatim from `tokens.json.banned`): green, blue, purple, brown, beige, pastel, any serif font, Comic Sans, Times New Roman.

---

## Language rule (locked, Antonello 2026-05-18)

**All UI text is ENGLISH.** This OVERRIDES the default CLAUDE.md §Language Protocol "Italian with owner" for this app specifically.

**Rationale**: international scope, future team access, dashboard-product feel.

**Translation table** (current mockups → final implementation):

| Italian (mockup)                                             | English (implementation)            |
| ------------------------------------------------------------ | ----------------------------------- |
| `Decisions Attesa`                                           | `Pending Decisions`                 |
| `Cosa Ha Imparato`                                           | `What It Learned`                   |
| `Comandi Rapidi`                                             | `Quick Commands`                    |
| `Pipeline Live`                                              | `Live Pipeline`                     |
| `Pipeline Live · Live Supervisor Events`                     | `Live Pipeline · Supervisor Events` |
| `Trace · Live Supervisor Events`                             | `Trace · Live Events`               |
| `Canva Status`                                               | (same — English already)            |
| `IG Metrics + Reflexion 7d`                                  | (same)                              |
| `New Brief`                                                  | (same)                              |
| `Renew OAuth` / `Reconcile` / `Stop renderer`                | (same)                              |
| `Force router run` / `Force push` / `Skip` / `Re-fact-check` | (same)                              |
| `Editorial Carousels`                                        | (same)                              |
| `News & Regulations`                                         | (same)                              |

**Conversation with Antonello stays Italian** — only the UI strings in the app are English.

**Scope** of this rule:

- HomeTile labels
- DoorCard titles + descriptions
- WR2 command page: form labels, Kanban column headers, card titles, action buttons, trace log messages (where we generate them)
- Intel-Lake command page: same
- PinGate prompt + button labels
- API error responses (`{"error": "invalid_pin"}` — English keys already)
- Footer text
- Page titles (`<title>`)
- Breadcrumbs

**NOT in scope** (these stay Italian where applicable):

- Commit messages / PR descriptions (per CLAUDE.md "English for commits/PRs/code/docs" — already English)
- Internal Python/TS comments (case-by-case, prefer English for consistency)
- Conversation/sessione Antonello-Claude (Italian per default rule)

---

## Information architecture (3 routes)

### `/cockpit` — Home

```
┌── topbar: Bali Zero logo + status pills (32/35 cron, PG, HMAC, time) ───────┐
│                                                                              │
│  ┌─ tile ─┐ ┌─ tile ─┐ ┌─ tile ─┐ ┌─ tile ─┐                                │
│  │ GLOBAL │ │ DECISN │ │ COSA   │ │ COMAND │  (4 small tiles)                │
│  │ 32/35  │ │ 3      │ │ HA IMP │ │ RAPIDI │                                 │
│  └────────┘ └────────┘ └────────┘ └────────┘                                 │
│                                                                              │
│  ┌────── DOOR CARD WR2 — Editorial Carousels ────────────────── → ┐         │
│  │  13 drafts · supervisor healthy 12s                              │         │
│  │  briefed(4) → researched(2) → drafts(3) → rendering(2) → ...    │         │
│  └─────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  ┌────── DOOR CARD INTEL-LAKE — News & Regulations ─────────── → ┐         │
│  │  847 items · 12 outbox · 3 stuck · 1247 NB pushes 7d            │         │
│  └─────────────────────────────────────────────────────────────────┘         │
│                                                                              │
│  footer: cost month + evolver next run                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### `/cockpit/wr2` — WR2 Command Page

Sostituisce questi CLI workflows attuali:

| CLI command                                                | UI replacement                                            |
| ---------------------------------------------------------- | --------------------------------------------------------- |
| `python3 wr2_draft_generator.py --topic <X>`               | Form NEW BRIEF con dropdown + button "Create Brief"       |
| `psql -c "SELECT * FROM war_room_drafts WHERE status='X'"` | Pipeline LIVE Kanban con 5 colonne                        |
| `python3 wr2_canva_apply.py --draft-id <UUID>`             | Click draft row → action "✓ Approve" inline               |
| `launchctl kickstart com.balizero.wr2.canva-renderer`      | Card Canva Status → button "↻ Reconcile"                  |
| `wr2_canva_lease_watchdog.py` (esecuzione cron)            | Lease state visibile in Canva Status (live polling)       |
| `cat ~/logs/wr2_supervisor.log`                            | TRACE/Terminal card in fondo con SSE stream live          |
| `python3 wr2_canva_token_watchdog.py`                      | OAuth countdown nella Canva Status + button "Renew OAuth" |

**Layout `/cockpit/wr2`** (vedi `html-wr2-command-lighter.html` mockup):

1. Breadcrumb `← Zantara Home / WR2 Editorial Carousels`
2. Page title + subtitle (drafts count + supervisor heartbeat)
3. **Card "+ New Brief"**: form (Topic input, Register dropdown, Audience dropdown, Domain radio) + button yellow "Create Brief"
4. **Card "📋 Pipeline Live"**: Kanban 5 colonne (briefed / researched / drafts / rendering / pending_review). Ogni draft row = title + meta + hover-reveal action buttons inline
5. **Two-column row**: Card "🎨 Canva Status" (OAuth expiry, leases, queue, rejected + action buttons Renew/Reconcile/Stop) | Card "📊 IG Metrics + Reflexion 7d" (engagement delta, top carousel, Reflexion insight)
6. **Card "📡 Trace · Live Supervisor Events"**: monospace log (IBM Plex Mono) live SSE stream con filter level dropdown

### `/cockpit/intel-lake` — Intel-Lake Command Page

Sostituisce CLI workflows:

| CLI                                                                                               | UI                                                         |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `~/scripts/intel-lake-router-cron.sh` (manual force run)                                          | Card "Pipeline Live" → button "Force router run"           |
| `psql -c "SELECT * FROM intel_items WHERE routing_status='X'"`                                    | Tabella items filtrabile per status                        |
| `~/scripts/intel-lake-nb-pusher-cron.sh`                                                          | Card "NB Push Log" con button "Force push"                 |
| `psql -c "SELECT producer_name, MAX(observed_at) FROM intel_observations GROUP BY producer_name"` | Tabella Source Health 609 sources con last-fetch, sortable |
| Update `intel_items.routing_status='skip'` manual                                                 | Click item → action "⊘ Skip" → emits `intent='intel.skip'` |
| Re-trigger fact-checker                                                                           | Click item → "↻ Re-fact-check" → intent                    |

**Layout `/cockpit/intel-lake`**:

1. Breadcrumb
2. Page title (847 items today · 3 stuck · 28 stale)
3. **Card "Pipeline Live"**: 4 status pillars (unrouted / routed_recent / needs_review / skipped) con count yellow + button force per ogni stage
4. **Card "Source Health"**: tabella 609 source paginata (default top 30 by activity) — colonne: domain, category, last_fetch, success_rate_7d, items_today, status_dot. Sort by last_fetch ASC = stale first. Search by domain.
5. **Card "NB Push Log"**: 5 columns NB-IMMIGRATION / NB-TAX / NB-REGULATION / NB-AI-RESEARCH / NB-PRESS. Per ogni NB: count 7d, last push timestamp, button "Force push"
6. **Card "Recent Items"**: ultimi 50 intel items ordinati per first_seen_at DESC. Row: title + source + routing_status + age. Click → drawer panel con full payload + actions (skip/rerun/re-fact-check)
7. **Card "Trace · Routing Events"**: SSE stream PG NOTIFY `intel_lake_event` channel

---

## Architecture (data flow)

### Action layer — intent-table pattern (preserved from v1 spec, v2 panel-validated)

Cockpit **NEVER** muta direttamente `intel_items` / `war_room_drafts`. Tutte le azioni destructive vanno in `cockpit_intents` (mig 183), existing services/cron consumano.

```
# Read-only endpoints (S1):
GET  /api/cockpit/cron/list           → launchctl print parsed (cached 2s)
GET  /api/cockpit/decisions           → gh pr list --draft + escalations
GET  /api/cockpit/intel/stats         → SELECT count by routing_status
GET  /api/cockpit/intel/sources       → SELECT producer_name, MAX(observed_at) ...
GET  /api/cockpit/intel/items         → SELECT * FROM intel_items ORDER BY first_seen_at DESC LIMIT 50
GET  /api/cockpit/intel/nb-pushes     → SELECT nb_uuid, COUNT(*) FROM intel_item_nb_pushes ...
GET  /api/cockpit/wr2/drafts          → SELECT * FROM war_room_drafts WHERE updated_at > NOW() - INTERVAL '7d'
GET  /api/cockpit/wr2/canva-status    → read canva_tokens.json + lease state
GET  /api/cockpit/wr2/ig-metrics      → SELECT FROM war_room_metrics ...
GET  /api/cockpit/wr2/reflexion-latest → read agent-library/proposals/ + filter wr2-reflexion-*

# Safe actions (S1+):
POST /api/cockpit/cron/run            {label, reason} → allowlist + launchctl kickstart
POST /api/cockpit/wr2/brief           {topic, register, audience, domain, reason} → spawn wr2_draft_generator.py
POST /api/cockpit/wr2/canva-renew     → trigger token refresh (existing watchdog)
POST /api/cockpit/wr2/canva-reconcile → trigger wr2_canva_reconcile.py

# Intent-table actions (destructive):
POST /api/cockpit/intent/create       {intent_type, params, reason}
   intent_type ∈ {intel.skip, intel.rerun, intel.re-fact-check, wr2.approve,
                  wr2.reject, wr2.rerender, cron.kill, library.approve-pr, library.reject-pr}

# SSE streams (NEW in v2 — singleton multiplexed per panel-fix v1):
GET  /api/cockpit/sse/multiplexed?ch=live,intel,wr2 → ONE connection, fan-out
```

### SSE singleton (panel v1 CRITICAL fix preserved)

```
Browser → EventSource('/api/cockpit/sse/multiplexed?ch=live,intel,wr2')
            ↓ ONE connection per browser
        Next.js handler (singleton listener-pool per Node process)
            ↓
        Dedicated pg.Client OUTSIDE main pool (max:3)
            ↓
        LISTEN: intel_lake_event, cockpit_pulse, war_room_drafts_update
        Fan-out via EventEmitter to subscribed clients filtered by ch
```

S1 deliverable: SSE multiplexed implemented. v1 differiva a S5; v2 lo include in S1 perché il Trace card lo necessita per UX live.

### Migrations (cherry-picked from v1)

- `182_cockpit_audit_log.sql` — HMAC chain (committed in v2 branch already)
- `183_cockpit_intents.sql` — intent queue (committed in v2 branch already)
- **NEW v2**: `184_cockpit_intent_consumers_seed.sql` — initial DB rows that document which existing cron consumes which intent_type (read-only doc table, not enforced)

---

## File structure (v2 target)

```
apps/admin-dashboard-local/
  app/
    cockpit/
      layout.tsx                        # Montserrat + Bali Zero shell (CHANGED vs v1 JetBrains Mono)
      page.tsx                          # Home v2: 4 tile + 2 door card (NOT 12-widget grid)
      cockpit-shell.css                 # v2 palette tokens (CHANGED — antracite lighter)
      wr2/
        page.tsx                        # /cockpit/wr2 command page (NEW)
      intel-lake/
        page.tsx                        # /cockpit/intel-lake command page (NEW)
    api/cockpit/
      auth/route.ts                     # (from v1, preserved)
      cron/list/route.ts                # (from v1)
      cron/run/route.ts                 # (from v1)
      decisions/route.ts                # (from v1)
      intent/create/route.ts            # (from v1)
      intel/
        stats/route.ts                  # NEW
        sources/route.ts                # NEW
        items/route.ts                  # NEW
        nb-pushes/route.ts              # NEW
      wr2/
        drafts/route.ts                 # NEW
        brief/route.ts                  # NEW (spawn subprocess)
        canva-status/route.ts           # NEW
        canva-renew/route.ts            # NEW
        canva-reconcile/route.ts        # NEW
        ig-metrics/route.ts             # NEW
        reflexion-latest/route.ts       # NEW
      sse/
        multiplexed/route.ts            # NEW (singleton SSE, fan-out 3 channels)
  components/cockpit/
    # Home v2
    HomeTile.tsx                        # NEW small tile (4×1 row 1)
    DoorCard.tsx                        # NEW large door card (1×1 row 2/3)
    BrandTopbar.tsx                     # NEW with Bali Zero logo + status pills
    # Shared
    StatusDot.tsx                       # KEEP from v1
    ActionButton.tsx                    # NEW (yellow primary, secondary outline, danger red)
    PinGate.tsx                         # KEEP from v1
    # WR2 page
    wr2/
      NewBriefForm.tsx                  # NEW
      PipelineKanban.tsx                # NEW (5 cols)
      DraftRow.tsx                      # NEW (with hover-reveal actions)
      CanvaStatusCard.tsx               # NEW
      IgMetricsCard.tsx                 # NEW
      TraceCard.tsx                     # NEW (consumes SSE)
    # Intel-Lake page
    intel/
      PipelinePillars.tsx               # NEW (4 stages)
      SourceHealthTable.tsx             # NEW (paginated, sortable, searchable)
      NbPushLog.tsx                     # NEW (5 columns)
      RecentItemsTable.tsx              # NEW (click → drawer)
      ItemDetailDrawer.tsx              # NEW (slide-over right side)
      IntelTraceCard.tsx                # NEW (SSE intel_lake_event)
  lib/
    cockpit-allowlist.ts                # KEEP from v1
    cockpit-auth.ts                     # KEEP from v1
    cockpit-audit.ts                    # KEEP from v1
    cockpit-launchctl.ts                # KEEP from v1
    cockpit-pg.ts                       # EXTEND with new helpers
    cockpit-sse.ts                      # NEW (singleton pg.Client + fan-out)
    cockpit-subprocess.ts               # NEW (spawn wr2_draft_generator.py etc.)
  middleware.ts                         # KEEP (still works)
  scripts/
    setup-cockpit-pin.sh                # KEEP from v1
    start-cockpit.sh                    # KEEP from v1

apps/backend-rag/backend/db/migrations_v2/
  182_cockpit_audit_log.sql             # cherry-picked from v1
  183_cockpit_intents.sql               # cherry-picked from v1
  184_cockpit_intent_consumers_seed.sql # NEW (doc table)

docs/superpowers/
  specs/
    2026-05-18-zantara-cockpit-v2-design.md  # THIS
  plans/
    2026-05-18-zantara-cockpit-v2-implementation.md  # NEXT

mockups/v2/                              # NEW — committed reference for design review
  html-home-v2-lighter.html              # APPROVED
  html-wr2-command-lighter.html
  png-3-home-lighter-final.png
```

---

## Component spec — key new pieces

### `<HomeTile />`

```tsx
interface HomeTileProps {
  label: string; // "Global Pulse"
  value: string | number; // "32/35" or 3
  meta?: string; // "healthy organism"
  status?: "green" | "amber" | "red";
  onClick?: () => void;
}
```

CSS: `background: var(--bg-card); border-radius: 14px; padding: 22px 26px;`. Hover: `border-color: var(--accent-yellow); transform: translateY(-2px);`.

### `<DoorCard />`

```tsx
interface DoorCardProps {
  title: string; // "WR2 — Editorial Carousels"
  description: string;
  href: string; // "/cockpit/wr2"
  // children: usually a flow/stats inline visualization
}
```

CSS: card large rounded-18px, `::after { content: '→' }` icon top-right, hover translateX(8px) on arrow. Click → `router.push(href)`.

### `<PipelineKanban />` (WR2)

5-column Kanban from `war_room_drafts`. Each column header shows status name + count badge yellow. Draft rows: title + meta + hover-reveal action buttons (Approve/Reject/Rerender) emitting intents.

```tsx
interface PipelineKanbanProps {
  drafts: Array<{
    id: string;
    title: string;
    status: string;
    updatedAt: string;
  }>;
  onAction: (intent: string, draftId: string) => Promise<void>;
}
```

Fetches `/api/cockpit/wr2/drafts` polling 10s OR SSE `war_room_drafts_update` channel.

### `<TraceCard />`

Live log via SSE singleton. Filter level dropdown (all/warn+/error).

```tsx
interface TraceLine {
  timestamp: string; // "17:42:01"
  source: string; // "supervisor"
  level: "info" | "warn" | "error";
  message: string;
}
```

Renders monospace IBM Plex Mono lines. Auto-scroll to bottom unless user scrolled up (paused state).

### `<ItemDetailDrawer />` (Intel-Lake)

Slide-over right-side panel (60% width). Shows full `intel_item` payload + 4 action buttons (Skip / Rerun / Re-fact-check / Open source URL). Closes on Esc or backdrop click.

---

## Anti-pattern mitigation (v2-specific)

| Risk                                                    | Mitigation                                                                                                        |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| **Trace card flood (SSE 1000 events/min)**              | Client-side cap 500 lines visible, FIFO eviction. Backend SSE has rate-limit 50 events/sec per client             |
| **NewBriefForm spawns subprocess with arbitrary topic** | Topic sanitization: max 200 chars, regex strip shell metachars `[;&                                               | $<>]`, audit log includes full input |
| **PipelineKanban race with renderer lease**             | Action button "Approve" → emits intent, NOT direct UPDATE. wr2_supervisor.py CAS-aware applies safely             |
| **SourceHealthTable 609 rows = slow render**            | Paginated 30/page, indexed query on `intel_observations(producer_name, observed_at DESC)`                         |
| **SSE singleton hangs if pg.Client dies**               | Heartbeat 25s + auto-reconnect with 1s/2s/4s/8s backoff. If 5 drops in 60s, frontend shows "degraded mode" banner |
| **Drawer leaks DOM on rapid open/close**                | Use Radix Dialog primitive or controlled state with cleanup on unmount                                            |
| **CanvaStatus polling races with token watchdog cron**  | UI shows last-known + "refreshed Xs ago", not "current". Truth source = cron, UI = mirror                         |
| **Recent Items table fetch storm on filter change**     | Debounce 300ms on search/filter input. Cache per-tag for 60s server-side                                          |

---

## Cost & LLM routing

**Cockpit v2 (A)**:

- Zero LLM calls inline (same as v1 — all LLM via subprocess in cron)
- Localhost only, $0 hosting
- Monthly cost: **$0**

**EvoSkill MVP (B)** — companion spec future S4:

- ~$1.00/month DeepSeek (executor + synthesis)

---

## Roadmap (v2 sessions)

| Session                           | Scope                                                                                                       | Effort | Output      |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------ | ----------- |
| **S1 v2** (THIS)                  | Foundation: shell + theme + home (4 tile + 2 door) + 5 base API + SSE singleton + lib helpers (cherry-pick) | 12-15h | PR draft #1 |
| **S2 v2** Intel-Lake command page | All Intel-Lake components + 4 new API endpoints + drawer + intent wiring                                    | 12-15h | PR #2       |
| **S3 v2** WR2 command page        | All WR2 components + 7 new API endpoints + brief subprocess + intent wiring                                 | 14-18h | PR #3       |
| **S4 v2** EvoSkill MVP (separate) | Vendor evoskill + weekly cron + draft PR pipeline                                                           | 10-12h | PR #4       |
| **S5 v2** Polish                  | Auth hardening, drawer animations, mobile-readable degraded view, plist auto-boot                           | 8h     | PR #5       |

**Parallelization plan**: S2 + S3 + S4 can run in parallel after S1 merges (3 worktree, max 4 parallel rule honored). Total wall-clock: ~38h vs sequential 65h.

---

## Known limitations v2 (accepted)

| Limitation                              | Severity | Plan-phase action                            |
| --------------------------------------- | -------- | -------------------------------------------- |
| No mobile UI (desktop-first)            | LOW      | S5 add tailwind responsive breakpoints       |
| Single-tenant (Antonello only)          | LOW      | RBAC out of scope                            |
| No history view of intent execution     | MEDIUM   | v3: timeline page of consumed intents        |
| FTS5 BM25 calibration (EvoSkill)        | MEDIUM   | S4 Phase 0                                   |
| Drawer state lost on browser refresh    | LOW      | localStorage persist optional                |
| Trace log not persisted across sessions | LOW      | SSE replay last 100 events on reconnect (S5) |

---

## Panel review checklist (for 4-LLM)

Before scrivere il plan, this spec passes through 4-LLM panel (Gemini + Codex + DeepSeek + devils-advocate subagent). Focus areas:

1. **Subprocess spawn safety** (NewBriefForm → `wr2_draft_generator.py`): is topic sanitization sufficient? Are there CLI flags that could be injected?
2. **SSE singleton lifecycle**: connection pool exhaustion if Next.js hot-reloads? Cleanup on hot-reload guaranteed?
3. **Kanban drag-drop ambition**: v2 spec mentions "click row hover action". Future drag-drop status transition (e.g., draft→rendering)? Risk = directly mutating war_room_drafts bypassing CAS lease.
4. **Source Health table 609 rows** — pagination + search adequate, or need virtual scroll?
5. **Intent consumer documentation**: is `184_cockpit_intent_consumers_seed.sql` (read-only doc table) the right way to surface "which cron consumes which intent"? Or better as plain Markdown in repo?
6. **Visual hierarchy**: is 4 tile + 2 door card sufficient for "home", or feels too sparse?
7. **Drawer right-side 60% width**: works on 13" MacBook (1440px)? Or should be modal-center?
8. **Migration 184 collision**: verify empirically — is 184 free at panel-review time?
9. **Brand cortex compliance**: spec uses `#3A3E4A` page bg which is +8% L from token `bg.antracite #2C2F38`. Brand cortex says "primary background = antracite". Is +8% acceptable derivation or should I re-anchor to exact token?
10. **Trace card scroll-pause UX**: when user scrolls up, auto-scroll should pause. Tested pattern? Or risks broken UX?

---

## References

- Cherry-picked from v1: commits 26e36774e, 5801d6ed2, 3ec4d45d1, e2f36a0c2, e8c794fe8, 9baaa9429, e15ce40cf, 7eb749de8
- v1 spec (closed): `docs/superpowers/specs/2026-05-17-zantara-cockpit-design.md` (PR #712 CLOSED)
- Brand cortex: `~/.claude/skills/bali-zero-brand/tokens.json`
- Approved mockups: `mockups/v2/html-home-v2-lighter.html`
- Symbiosis Laws: `SYMBIOSIS.md`
- L2 autonomous ops: `AUTONOMOUS_OPS.md`
