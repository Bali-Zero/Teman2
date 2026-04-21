# Mata Garuda × War Room Cockpit — Design Spec

**Date:** 2026-04-21
**Author:** Claude Opus 4.7 (max effort) + Antonello Siano (Zero)
**Status:** Draft for user review
**Scope:** First dashboard of the Nuzantara Command Center (Mac desktop app).
**Location of produced app:** `apps/command-center/` (new package, not created yet)

---

## 1. Purpose

A single-view Mac desktop cockpit that unifies the **intelligence harvesting** layer
(Mata Garuda) with the **production publishing** pipeline (War Room v2). Zero operates
the end-to-end flow from here: from raw OSINT signal → through the 11-stage WR
pipeline → to the mandatory Review Gate where he approves, edits, or rejects
each artifact before it reaches the 5-channel publisher.

The cockpit replaces today's fragmented surface (Telegram buttons + SSH terminal +
grep on log files + admin-dashboard web page) with a **single cockpit window that
cannot be fully dismissed while a mandatory decision is pending**.

This is the **first dashboard** of a larger Command Center that will grow to cover
CRM, Compliance, Finance, Intel, Silent-failure feed (see the broader analysis in
the audit document 2026-04-21-kita-clients-process-email-audit.md §future). Shipping
Mata Garuda × WR first validates the architecture, the real-time layer, and the
mandatory-decision UX on the single most intricate pipeline in the codebase.

---

## 2. Users & Scope

**MVP (this spec):** single-user — Zero on Pro (M4 48GB). Auth is a no-op
(localhost connection). All cockpit features available.

**Post-MVP architecture (built-in, not active):** role-based filtering scaffolding
present from day one so that a future Asya/Ari/Krishna distribution requires only
an auth layer swap (JWT reuse from kita.balizero.com) and a DMG build, not a
rewrite. Every panel/action is gated by a `role_required` metadata tag so the
filter is a one-line change per feature when activated.

---

## 3. Stack

| Layer         | Choice                                                   | Why                                                                             |
| ------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Shell         | Tauri v2 (Rust core + web frontend)                      | 10-15MB bundle, native IPC, spawns subprocesses (ssh, fly, curl, psql) directly |
| Frontend      | React 19 + TypeScript, from `packages/core`              | Reuse existing BZ tokens, logo, auth client, UI primitives                      |
| State         | Zustand (small, no Redux weight)                         | Each panel has its own slice                                                    |
| Real-time     | Redis pub/sub + HTTP polling (B+A decision)              | See §7 Real-time Layer                                                          |
| Storage local | SQLite via Tauri's plugin (cached snapshots, SLA timers) | Works offline on plane/bad wifi                                                 |
| Build         | Tauri CLI + pnpm monorepo                                | Shares lockfile, CI reuses existing pipelines                                   |

Deliverable: `apps/command-center/` monorepo package + `.dmg` build in
`.github/workflows/build-command-center.yml` for future distribution (not triggered
on main push at MVP — manual dispatch only).

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  TAURI SHELL (Rust)                                         │
│  ├─ Subprocess manager: ssh air / fly / curl / psql         │
│  ├─ Redis client: connects to 127.0.0.1:6379 via Air tunnel │
│  │                (~/tunnel-air.sh) OR direct Pro Redis     │
│  ├─ HTTP client: nuzantara-rag.fly.dev (JWT bearer)         │
│  ├─ Local SQLite: ~/Library/Application Support/            │
│  │                nuzantara-cockpit/cache.sqlite            │
│  └─ IPC bridge → React frontend                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ Tauri commands (typed)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  REACT FRONTEND (single window, multi-panel)                │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ TITLEBAR: badge count "3 decisions" + SLA flash warning ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ PANEL A — Mata Garuda Stream (left column, 35% width)   ││
│  │   ├─ Harvester status (Exa / xAI / Google / IG)         ││
│  │   ├─ Anomaly Mutations pending approval                 ││
│  │   ├─ Trending signals (48h filter)                      ││
│  │   ├─ Regulatory alerts (peraturan.go.id)                ││
│  │   └─ Feedback loop health (garuda:feedback stream)      ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ PANEL B — WR Pipeline (center column, 40% width)        ││
│  │   ├─ Topic queue (draft, research, preprocess)          ││
│  │   ├─ Pipeline timeline per topic (11 stages vertical)   ││
│  │   ├─ Active topic detail (stage status + logs tail)     ││
│  │   └─ Manual /topic inline composer                      ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ PANEL C — Review Gate (right column, 25% width normal)  ││
│  │            EXPANDS to full-screen modal on SLA < 2h     ││
│  │   ├─ Pending review cards with SLA countdown            ││
│  │   ├─ Click card → Split view modal (see §5.3)           ││
│  │   └─ Recent approvals log (last 10)                     ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  BOTTOM STRIP: Publisher channels health (5 dots) + Learner │
│    (last mutation + composite score + auto-revert alerts)   │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Why the layout

- **Left = sources** (Mata Garuda): everything flows **into** WR.
- **Center = pipeline** (WR): the 11-stage production conveyor.
- **Right = decisions** (Review Gate): the mandatory human touchpoint.
- **Bottom = outcomes** (Publisher + Learner): what happened after you clicked approve.

Reading flow matches production flow, left to right.

### 4.2 Mandatory-decision UX

The titlebar badge shows count of pending items. When **any Review Gate card has
SLA < 2h remaining**:

1. Panel C expands to full-screen modal automatically.
2. The app cannot be closed ("cmd+Q" opens a confirmation: "2 reviews will
   auto-reject in 1h24m. Defer all to tomorrow? [Yes, defer all — logged] [Stay]").
3. macOS dock bounces once.
4. Tauri sends native notification with sound.
5. If the user clicks "Defer all", all deferrals go to `shared/cockpit_deferrals.jsonl`
   with reason field (mandatory free-text).

This is **mandatory but not abusive**: the only bar to exit is an explicit logged
decision. No hostage-taking.

---

## 5. Panel Details

### 5.1 Panel A — Mata Garuda Stream

**Purpose:** see what's arriving, what's anomalous, what needs mutation approval.

**Widgets:**

| Widget                    | Data source                                     | Refresh       | Action                                                     |
| ------------------------- | ----------------------------------------------- | ------------- | ---------------------------------------------------------- |
| Harvester health dots     | Redis `garuda:raw` XLEN + last XADD age         | 10s polling   | Click → log tail in drawer                                 |
| Anomaly mutations pending | `garuda:feedback` stream type=mutation_proposal | Redis pub/sub | Approve/Reject/Edit → writes to `genome.py` via SSH-on-Pro |
| Trending signals (top 5)  | `garuda:trending` sorted by score×recency       | 30s polling   | Click → promote to WR `/topic` queue                       |
| Regulatory alerts         | `garuda:processed` filter type=regulatory       | Redis pub/sub | Click → preview PDF + auto-create WR topic                 |
| Feedback loop health      | Last arrival time of `garuda:feedback`          | 1min polling  | Alert dot if >6h stale                                     |

**Empty state:** "Last harvest 12 min ago — 47 items in garuda:raw, 3 trending"

### 5.2 Panel B — WR Pipeline

**Purpose:** see every topic in flight and its stage, intervene if stuck.

**View: vertical timeline per topic, showing the 11 stages:**

```
TOPIC: "New visa fee effective 2026-05-01"
(from Mata Garuda regulatory alert, auto-created 08:12 WITA)

  01  ✅ Topic selected                   08:12  [auto]
  02  ✅ Research complete                09:14  [Exa+xAI+NLM, 62min]
  03  ⏸  Preprocess queued                09:15  [window 01:00-06:05, next: 17h]
  04  ⏳ Brain Trust                      —
  05  ⏳ Visual Gen (Flux.1)              —
  06  ⏳ Layout (Canva template)          —
  07  ⏳ Review Gate                      —
  08  ⏳ Publisher                        —
  09  ⏳ Measurement                      —
  10  ⏳ Learner                          —
  11  ⏳ Scar to Mata Garuda              —

  [Override: Use Claude Director instead of DeepSeek-r1]
```

**Override actions available on stuck topics:**

- **Bypass preprocessor window**: use Claude subprocess instead of DeepSeek-r1
  (writes `topic_id` to `workflow_queue` with `preprocessor_override=claude`).
- **Re-run layout with alt template**: select from a dropdown of 3 backup
  Canva templates; triggers re-layout.
- **Force skip stage**: only for non-critical stages (Measurement, Learner) with
  confirmation dialog. Logged to `shared/cockpit_actions.jsonl`.

**Widgets in this panel:**

| Widget                        | Data source                                                                | Refresh                            | Action                                 |
| ----------------------------- | -------------------------------------------------------------------------- | ---------------------------------- | -------------------------------------- |
| Active topics list            | `pending_topic` table WHERE status NOT IN (published, rejected, timed_out) | Redis pub/sub on `war_room:events` | Click → expand timeline                |
| Selected topic timeline       | Joins across pending_topic, research_jobs, layout_attempts                 | Event-driven                       | Per-stage action buttons               |
| Manual `/topic` composer      | Text input + "Send to Selector"                                            | —                                  | POSTs to `/api/war-room/topic/manual`  |
| Preprocessor window indicator | Current time vs 01:00-06:05 WITA                                           | 1min polling                       | Status pill: "IN WINDOW" / "OUT 4h32m" |

### 5.3 Panel C — Review Gate (split view modal)

**When collapsed (panel mode, right column 25% width):** just cards with SLA
countdown.

**When expanded (modal, full-screen on click or SLA <2h):**

```
┌──────────────────────────────────────────────────────────────────┐
│  REVIEW GATE — Topic #1247                        SLA: 3h 14m    │
│  "Visa fee change — what expats need to know"                    │
├──────────────────────────┬───────────────────────────────────────┤
│                          │                                       │
│  PREVIEW (left half)     │  CONTEXT (right half)                 │
│                          │                                       │
│  [Canva 11-slide]        │  MATA GARUDA DOSSIER                  │
│  slide 1 (cover)         │  • peraturan.go.id 2026-04-20         │
│  slide 2 (hook)          │  • Effective 2026-05-01               │
│  slide 3 (fact 1)        │  • Regex confidence: HIGH             │
│  ...                     │                                       │
│  slide 11 (CTA)          │  RESEARCH                             │
│                          │  • Exa: 18 results (top 5 quoted)     │
│  [click slide → edit    │  • xAI: 42 mentions last 24h          │
│   text inline]           │  • NLM: synthesis by NB-2             │
│                          │                                       │
│                          │  BRAIN TRUST (3 ANGLES)               │
│                          │  ◉ Angle A: "what changes for you"    │
│                          │  ○ Angle B: "cost breakdown"          │
│                          │  ○ Angle C: "timeline to renew"       │
│                          │    [click to swap]                    │
│                          │                                       │
│                          │  FLUX.1 IMAGES                        │
│                          │  [3 thumbnails — click to regenerate] │
│                          │                                       │
├──────────────────────────┴───────────────────────────────────────┤
│  [✅ APPROVE]  [✏️ EDIT & RE-LAYOUT]  [❌ REJECT w/ reason]      │
└──────────────────────────────────────────────────────────────────┘
```

**SLA rules (enforced):**

- Soft 4h → amber pill.
- Repeat 12h → red pill + native notification once.
- Hard 48h → auto-reject, scar to Learner (existing behavior, unchanged).
- <2h → **modal auto-opens** (cannot be dismissed without action or explicit
  "Defer all" with reason).

**Edit flow:**

1. Click slide → inline text editor (the text block only; visuals stay).
2. Save → `pending_topic.status = awaiting_revision`, re-enters layout stage.
3. Cockpit shows "Re-rendering layout..." with Playwright progress.
4. New preview appears when ready.
5. Re-enters the same Review Gate card.

### 5.4 Bottom strip — Publisher + Learner

Always visible at bottom:

```
┌─────────────────────────────────────────────────────────────┐
│ PUBLISHER  🟢 IG  🟢 X  🟡 LI (token 3d)  🟢 Blog  —  TG    │
│ LEARNER    Composite last 7d: 0.68 ↑0.03  No auto-reverts   │
└─────────────────────────────────────────────────────────────┘
```

Click on a channel dot → opens token status + recent publishes. Click on
Learner → opens mutation history with diff view.

---

## 6. Data Flow (end-to-end example)

**Example: Regulatory alert → publish cycle**

1. **Mata Garuda L4** RegulatoryWatcher (cron 06:00 WITA) finds new PDF on
   peraturan.go.id.
2. Writes to `garuda:processed` stream (type=regulatory, confidence=HIGH).
3. **Panel A** receives Redis pub/sub event → highlights new alert card.
4. Zero clicks **"Promote to WR /topic"** → Tauri calls
   `/api/war-room/topic/create` with source=garuda_alert.
5. `pending_topic` row created (status=draft). **Panel B** receives `war_room:events`
   push → topic appears in timeline.
6. Research phase runs (Exa + xAI + NLM parallel). Timeline updates every stage.
7. Preprocessor reaches out-of-window → **Panel B** shows amber "OUT 4h32m".
   Zero clicks **"Use Claude Director"** override → workflow_queue flag set.
8. Brain Trust completes 3 angles. Flux.1 generates 3 images.
9. Layout runs (CSS patch loop). If 3/3 patches fail, **Panel B** alerts red and
   offers "Use fallback template".
10. Layout succeeds → `pending_topic.status = pending_review`. SLA timer starts.
11. **Panel C** card appears with 4h SLA. At 3h30m, card flashes amber.
12. Zero clicks card → split view opens. Reviews dossier, swaps Angle B→C,
    regenerates image 2, edits slide 4 text.
13. Clicks **APPROVE** → `pending_topic.status = approved`. Publisher fires
    parallel to 5 channels.
14. **Bottom strip**: IG turns green within 30s, then X, LI, Blog. If one fails
    (e.g., LI 401), dot turns red with "token refresh needed" link.
15. Measurement runs 24h-7d later. **Bottom strip** updates composite score.
16. Learner writes scar to `garuda:feedback` → closes the loop back to Mata Garuda.

---

## 7. Real-time Layer (B+A hybrid)

**Primary: Redis pub/sub** for event-driven updates.

Channels subscribed:

| Channel                       | Origin      | Panel consumer                 | Event types                                                                           |
| ----------------------------- | ----------- | ------------------------------ | ------------------------------------------------------------------------------------- |
| `garuda:raw` (XREAD)          | Harvester   | A harvester health             | new_item                                                                              |
| `garuda:feedback` (XREAD)     | Various     | A mutations + bottom Learner   | mutation_proposal, auto_revert, scar_received                                         |
| `garuda:processed` (XREAD)    | L3 Nexus    | A regulatory + trending        | anomaly, regulatory, trend                                                            |
| `war_room:events` (SUBSCRIBE) | WR services | B timeline + C review + bottom | topic_created, stage_transition, review_pending, publish_result, measurement_complete |

Tauri Rust core holds the Redis connection; forwards events to React via Tauri
events (`emit("cockpit_event", payload)`).

**Fallback: HTTP polling** for data not event-sourced:

| Data                                  | Endpoint                                | Interval |
| ------------------------------------- | --------------------------------------- | -------- |
| pending_topic table (freshness check) | `GET /api/war-room/topics?since=<ts>`   | 30s      |
| Publisher token status                | `GET /api/war-room/publishers/health`   | 5min     |
| Composite score trend (7d/30d)        | `GET /api/war-room/metrics?window=7d`   | 5min     |
| Preprocessor queue + window state     | `GET /api/war-room/preprocessor/status` | 1min     |

Rust core merges both streams before IPC-forwarding to React, so the frontend
doesn't know which path delivered an event.

### 7.1 Redis connection path

Cockpit runs on Pro. Pro has direct access to its own Redis (port 6379).
Connection string lives in `~/Library/Application Support/nuzantara-cockpit/config.toml`:

```toml
[redis]
url = "redis://127.0.0.1:6379"
# Fallback for when Pro Redis is down: tunnel to Air Redis
fallback_url = "redis://127.0.0.1:16379"  # ~/tunnel-air.sh
```

Rust core tries primary first, falls back after 3 connection failures, notifies
user with a discrete banner (not modal — this is operational info, not mandatory).

---

## 8. Backend Endpoints (new)

Most data already exists via Redis + existing admin endpoints. The cockpit needs
**4 new endpoints** on backend-rag (Fly):

| Endpoint                                | Purpose                                          | RBAC           |
| --------------------------------------- | ------------------------------------------------ | -------------- |
| `GET /api/war-room/topics?since=<ts>`   | List pending/active topics with stage            | `is_crm_admin` |
| `GET /api/war-room/publishers/health`   | Per-channel token expiry + last publish          | `is_crm_admin` |
| `GET /api/war-room/preprocessor/status` | Queue depth + window state                       | `is_crm_admin` |
| `POST /api/war-room/topic/override`     | Override flags (bypass preprocessor, skip stage) | `is_crm_admin` |

Plus **1 new endpoint on Mata Garuda CLI bridge** (Pro-local, exposed via Tauri
subprocess, not HTTP):

| Command                                                                            | Purpose                              |
| ---------------------------------------------------------------------------------- | ------------------------------------ |
| `mata-garuda cockpit mutation-action --id X --action approve/reject/edit --body Y` | Apply mutation decision from cockpit |

These endpoints are thin read/command layers — no business logic. The cockpit is
not a new service; it's a view over existing state.

---

## 9. Persistence (local SQLite)

The cockpit keeps a local cache at
`~/Library/Application Support/nuzantara-cockpit/cache.sqlite` so the UI loads
instantly on launch (no blank state) and works offline:

| Table             | Purpose                                                  | TTL                  |
| ----------------- | -------------------------------------------------------- | -------------------- |
| `cached_topics`   | Last seen pending_topic snapshot                         | Refresh on fetch     |
| `cached_reviews`  | SLA-tracked pending reviews                              | Refresh on WR event  |
| `deferrals_log`   | "Defer all" actions with reason                          | Kept forever (audit) |
| `cockpit_actions` | Every click that mutates state (override, approve, etc.) | Kept 90d             |

Local actions are **shadow-written** to the server endpoint; if server is unreachable,
action queues in SQLite and retries on reconnect. All queued actions are visible
in a "Pending sync" section of Panel C.

---

## 10. Telegram parallel delivery (NOT replaced)

Telegram flows remain **unchanged** in this MVP. The cockpit is a **second surface**
for the same decisions, not a replacement. Both channels update the same database
rows; a decision taken in Telegram is reflected in the cockpit within the next
event tick (Redis event from war_room:events), and vice versa.

This keeps the risk floor low: if the cockpit has a bug, Telegram still works.
Once the cockpit is trusted in production (~1 month of use), future specs may
elect to make the cockpit primary and Telegram secondary.

---

## 11. Error Handling & Degradation

| Failure mode                      | Detection           | User experience                                     | Log destination                 |
| --------------------------------- | ------------------- | --------------------------------------------------- | ------------------------------- |
| Redis primary unreachable         | Connect timeout 3×  | Banner "Redis Pro down, switching to Air tunnel"    | `cache.sqlite::cockpit_actions` |
| Backend-rag unreachable           | HTTP timeout or 5xx | Banner "Backend offline, showing last cached state" | same                            |
| Tauri subprocess fails (ssh/fly)  | exit code non-zero  | Toast error + suggest command to run manually       | same                            |
| User offline entirely             | No Redis, no HTTP   | Full offline mode: read-only from SQLite            | same                            |
| Mata Garuda genome.py write fails | SSH stderr          | Mutation stays pending, retry button appears        | same                            |

No silent failures by design — every swallow has a visible indicator in the UI.

---

## 12. Testing Strategy

**Unit tests** (Rust): Tauri commands, SQLite migrations, Redis client reconnect logic.

**Integration tests** (TS): React panels with mocked Tauri commands.

**End-to-end** (Playwright on Tauri webview): full topic flow simulation with
mock War Room backend.

**Chaos tests** (manual, documented): disconnect Redis, kill backend, pull network,
observe degradation.

No CI for Tauri builds in MVP (manual build). CI added in a later spec.

---

## 13. Build Steps & Milestones

**Milestone 1 — scaffolding (3 days)**

- `apps/command-center/` with Tauri v2 + React 19 + TypeScript.
- Local Redis connection, pub/sub listener, basic event forwarding to React.
- Empty 3-panel shell with placeholder data.

**Milestone 2 — Panel A (3 days)**

- Harvester dots, trending, regulatory alerts cards (read-only).
- "Promote to /topic" action wiring.

**Milestone 3 — Panel B (4 days)**

- Topic timeline rendering.
- Overrides (bypass preprocessor, fallback template, force skip).
- Manual composer.

**Milestone 4 — Panel C (5 days, hardest)**

- Split view modal.
- Canva preview rendering (via existing `/war-room/topics/<id>/preview` endpoint
  or static HTML render of slides).
- Inline slide text editor.
- SLA countdown + auto-modal logic.
- Approve / edit / reject wiring.

**Milestone 5 — bottom strip + polish (2 days)**

- Publisher dots, Learner summary, deferrals log.

**Milestone 6 — 4 new backend endpoints (2 days)**

**Milestone 7 — DMG build + local install (1 day)**

**Total: ~3 weeks of focused work.**

Each milestone is one commit on `feat/command-center-cockpit` branch with its
own PR. Zero reviews after each milestone; cockpit runs in parallel with Telegram
flows throughout.

---

## 14. Out of Scope (explicitly, for follow-up specs)

- Other dashboards (CRM, Compliance, Finance, Silent-failure): future specs.
- Multi-user auth + DMG distribution: future spec (code is structured to accept it).
- Mobile / iPad companion: out.
- Windows/Linux builds: Tauri supports, but out of scope; MVP is Mac-only.
- Replacing Telegram entirely: out (§10).
- Creating brand-new backend services: out (4 thin read endpoints only).

---

## 15. Risks

| Risk                                                                     | Likelihood                      | Mitigation                                                                                        |
| ------------------------------------------------------------------------ | ------------------------------- | ------------------------------------------------------------------------------------------------- |
| Canva template preview rendering inside Tauri webview is slow            | Medium                          | Pre-render to PNG server-side; cockpit loads cached PNGs                                          |
| Redis pub/sub from Tauri Rust has connection-drop issues                 | Low                             | 3× retry with exponential backoff; fallback to polling                                            |
| War Room emits events inconsistently (not all stages push)               | Medium                          | MVP accepts this; polling covers gaps; future WR spec adds missing events                         |
| Zero forgets to approve → auto-reject happens without him seeing cockpit | Low (modal enforces visibility) | Auto-reject already existing Telegram behavior — cockpit adds protection, doesn't remove existing |
| Mata Garuda CLI subprocess calls block UI                                | Low                             | All subprocess calls run in Tauri Rust async; React stays responsive                              |

---

## 16. Success Criteria

MVP ships successfully when:

1. Zero takes ≥3 consecutive WR approvals through the cockpit without opening
   Telegram.
2. ≥1 Mata Garuda mutation approved via cockpit instead of Telegram.
3. ≥1 topic stuck-in-preprocessor bypassed via cockpit override.
4. No production incident caused by cockpit (Telegram parallel remains safety net).
5. Zero reports: "I saved >30 min vs. old Telegram flow" after 1 week of use.

Future dashboards follow the same shape when these criteria are met.
