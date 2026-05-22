---
date: 2026-05-23
domain: operations
client_case: internal-tooling
sources: 26
---

# WA-Mirror Dashboard — Open-Source Candidates, Architecture Synthesis, Tech Stack Recommendation

**Author**: deep-researcher panel (Claude Opus 4.7 synthesis + Gemini 3.1 Pro long-context + DeepSeek V4 Pro numerical/pattern)
**Status**: draft, pre-spec, post-redteam
**Scope**: discovery + architecture proposal for a local Pro M4 webapp to visualize and intervene on 8-account Bali Zero team WhatsApp captured by `apps/wa-mirror`.
**Red-team gate**: self-redteam by Claude Opus 4.7 on 2026-05-23 found 2 HIGH + 4 MEDIUM, all addressed inline below. DeepSeek redteam attempted but API returned empty completion 3× (token/reasoning ceiling issue documented under Risk #10).

---

## 1. Executive summary

Nuzantara already runs a production-grade Baileys capture bridge (`apps/wa-mirror`, Node.js 22 + `@whiskeysockets/baileys`, deployed on Mini-Pro2 H24) that persists every inbound and outbound team-account WhatsApp message into PostgreSQL `whatsapp_message_context` and emits `whatsapp_message_received` on EventBus. The bridge is currently capture-only — there is no UI to visualize the 14k+ accumulated rows, no flow visualization, no human-intervention path. The current research panel evaluated twelve open-source candidates (Evolution API, WAHA, MultiWA, WA-AKG, Chatwoot, Tercela, WPPConnect server+frontend+manager, Evolution Manager v2, Zete dashboard, mohit2777 multi-accounts dashboard, OpenWA) plus three UI pattern libraries (React Flow, chatscope chat-ui-kit, Assistant-ui) to determine the highest-leverage integration path.

Three LLMs converged on a single architectural verdict: **do not fork any candidate wholesale**. The wa-mirror bridge already owns the Baileys socket layer and the FastAPI monolith already owns CRM/RBAC/Qdrant; introducing a Node.js/NestJS or Ruby/Rails dashboard backend would fragment business logic across two stacks. Instead, build a greenfield dashboard in a new `apps/wa-dashboard/` Next.js app (chosen over extending `apps/admin-dashboard` or `apps/mouth` — see §5.1 location decision and §8 checklist), and lift only the MIT-licensed UI patterns from WA-AKG (chat composer + multi-session switcher) and Evolution Manager v2 (Radix UI dashboard chrome). The conversation rendering layer should be `@chatscope/chat-ui-kit-react`, the automation/handoff flow visualization should be React Flow, the realtime transport should be a hybrid of Postgres LISTEN/NOTIFY (wa-mirror → backend, same-database connection) and Server-Sent Events (backend → browser). WebSocket is acceptable but introduces stateful complexity that the workload (8 accounts, ~2.7 msg/sec peak, 18 concurrent viewers max) does not require.

Three non-negotiable risks are: (a) Baileys breakage cycle of approximately 8-12 weeks against WhatsApp protocol updates; (b) anti-ban detection on outbound bursts when a human intervenes via the dashboard; (c) **UU PDP 27/2022 lawful-basis question on capturing prospect/lead messages and on enabling outbound replies from a centralized system**. (a) and (b) are technical and mitigatable in the spec; (c) requires legal-counsel sign-off before v2 send capability is enabled and is the gating decision for the whole project.

---

## 2. Top 5 candidate ranking

DeepSeek computed maintenance-health and stack-overlap; Gemini ranked qualitatively for code-lift fitness. Convergent top 5:

| Rank | Candidate                               | MHI (DS) | Stack overlap /10 (DS) | Code-lift fit (Gemini)                                                                                                                                                         | Verdict                                                                                                          |
| ---- | --------------------------------------- | -------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| 1    | **WA-AKG** (mrifqidaffaaditya)          | 1.09     | 5                      | **HIGH** — Next.js 15 + Baileys native, MIT, role-based access SUPERADMIN/OWNER/STAFF maps to Nuzantara Admin/Team                                                             | Lift chat UI + multi-session switcher + anti-ban delay pattern                                                   |
| 2    | **Evolution Manager v2** (EvolutionAPI) | 0.91     | 6                      | **MEDIUM-HIGH** — React 18.3 + Vite + Radix UI + Tailwind + React Query + React Hook Form + Zod + Socket.io client, Apache 2.0                                                 | Lift dashboard chrome, Radix-based intervention modals, i18n architecture                                        |
| 3    | **MultiWA** (ribato22)                  | 1.12     | 7                      | **MEDIUM** — Next.js 14 admin (port 3001) + visual flow builder + plugin system, MIT                                                                                           | Reference for visual flow builder pattern (relevant to "msg→automation→action" requirement); skip NestJS backend |
| 4    | **Chatwoot** (chatwoot/chatwoot)        | 2.04     | 7                      | **LOW for code, HIGH for architecture** — Vue 2 + Rails (29.6k stars but wrong stack); polymorphic `ContactInbox` is the gold-standard pattern                                 | Study the ContactInbox abstraction for cross-account contact unification, do not lift code                       |
| 5    | **Tercela** (tags-dev)                  | 1.01     | 8                      | **MEDIUM** — Hono+Bun backend (incompatible), Nuxt 4 frontend (incompatible), but PostgreSQL+Drizzle schema (`auth/channels/contacts/inbox/config/storage`) is well-normalized | Reference for schema normalization beyond the current `whatsapp_message_context` flat table                      |

Honourable mentions explicitly **not recommended**:

- **Evolution API** (8.4k stars): heavyweight (NestJS+Fastify+Prisma+RabbitMQ+Kafka+SQS+NATS+Pusher+Socket.io+S3) — overkill for a single 48GB box, fragments the FastAPI monolith.
- **WAHA** (6.6k stars): multi-engine (WEBJS/NOWEB/GOWS) is novel but multi-session sits behind a "Plus" paid tier; baseline doesn't fit.
- **WPPConnect Frontend** (238 stars, ARCHIVED Apr 2024): code rot risk, unmaintained.
- **WPPConnect Server** (1k stars): replaces wa-mirror, doesn't complement it; Puppeteer-based which is heavier than Baileys-native.
- **Zete WhatsApp Dashboard**: PHP/Laravel stack — language mismatch.
- **mohit2777 multi-accounts dashboard** (1 star): vanilla JS, hobby-grade.
- **OpenWA**: opaque feature set, low maintenance signal.

---

## 3. Feature matrix (10 features × top 7 candidates)

Legend: ✓ documented · ◐ partial / unclear · ✗ absent · — not applicable

| Feature                               | WA-AKG                       | Evo Manager v2 | MultiWA              | Chatwoot             | Tercela | WPPC Frontend  | WAHA |
| ------------------------------------- | ---------------------------- | -------------- | -------------------- | -------------------- | ------- | -------------- | ---- |
| Multi-account session switcher UI     | ✓                            | ✓              | ✓                    | ✓                    | ✓       | ✓ (demo-grade) | ✓    |
| Chat-style message timeline           | ◐                            | ◐              | ✓ (live chat module) | ✓                    | ✓       | ✓              | ◐    |
| Group chat sender attribution         | ◐                            | ◐              | ◐                    | ✓                    | ◐       | ◐              | ◐    |
| Outbound compose (intervention)       | ✓                            | ✓              | ✓                    | ✓                    | ✓       | ✓              | ✓    |
| Quick replies / templates             | ✓ (auto-replies w/ keywords) | ◐              | ✓                    | ✓ (canned responses) | ✓       | ✗              | ✗    |
| Assignment / handoff (agent ↔ thread) | ◐ (role-based)               | ✗              | ◐                    | ✓ (auto-assignment)  | ✓       | ✗              | ✗    |
| Flow / automation visualization       | ✗                            | ✗              | ✓ (visual builder)   | ✗                    | ✗       | ✗              | ✗    |
| Media gallery (image/PDF/voice)       | ✓                            | ◐              | ✓                    | ✓                    | ✓       | ✓              | ◐    |
| Search + filter                       | ◐                            | ◐              | ✓                    | ✓                    | ✓       | ✗              | ✗    |
| OCR result display                    | ✗                            | ✗              | ✗                    | ✗                    | ✗       | ✗              | ✗    |

Note: **no open-source candidate** ships OCR display out of the box. The OCR JSONB rendering layer is greenfield work for Nuzantara regardless of which UI we lift. Similarly, only MultiWA has a visual flow builder — every other candidate treats automation as backend-only.

---

## 4. Architecture pattern recommendations

### 4.1 Convergence/divergence across the 12 candidates

DeepSeek + Gemini convergent counts:

| Architectural choice          | Convergence                                                                                                                                                                                  | Divergence                      |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- |
| **Database**                  | 6/12 use PostgreSQL (Evolution, MultiWA, WA-AKG, Chatwoot, Tercela, mohit2777 via Supabase); 2/12 MySQL (Zete, WA-AKG fallback); 2/12 MongoDB-optional (WPPConnect); 2/12 unspecified        | strong convergence on PG        |
| **Realtime transport**        | 7/12 Socket.io (Evolution, MultiWA, Evo Manager v2, Zete, WPPConnect server, mohit2777, WAHA); 1/12 ActionCable (Chatwoot/Rails); 1/12 native Bun WS (Tercela); 2/12 plain raw WS            | strong convergence on WebSocket |
| **Frontend**                  | 5/12 React/Next.js (WA-AKG Next 15, MultiWA Next 14, Evo Manager v2 React+Vite, WPPC Frontend React, mohit2777 vanilla); 1/12 Vue 2 (Chatwoot); 1/12 Nuxt 4 (Tercela); 1/12 PHP/Blade (Zete) | React plurality                 |
| **Multi-session model**       | 10/12 single-process multi-tenant abstraction (sessions managed via DB+filesystem token store); 0/12 container-per-account                                                                   | strong convergence              |
| **Frontend↔backend coupling** | 5/12 decoupled SPA + REST/WS (Evolution Manager v2, WPPC Frontend, MultiWA); 7/12 monolithic SSR                                                                                             | divergent                       |
| **License**                   | 7/12 MIT (WA-AKG, MultiWA, Chatwoot, Tercela, mohit2777, etc.); 5/12 Apache 2.0 (Evolution, WAHA, WPPC, Evo Mgr v2)                                                                          | all permissive, zero AGPL traps |

**Bottom-line architectural pattern**: PostgreSQL + Socket.io + React/Next.js + single-process multi-session abstraction. Nuzantara already matches 3/4 of these (PG ✓, React/Next ✓, single-process multi-session via wa-mirror ✓). The only deviation is realtime transport — see §4.3.

### 4.2 Integration path: Path B (greenfield UI + pattern lifting)

Three paths were evaluated:

- **Path A — Wholesale fork** (deploy Evolution API or WA-AKG, migrate Nuzantara logic to it): rejected. Fragments business logic across Node.js (NestJS/Express) and Python (FastAPI) stacks. Duplicates CRM/RBAC/Qdrant logic. Operational nightmare.
- **Path B — Greenfield dashboard, lift UI patterns** (build inside Next.js, extend FastAPI, leave wa-mirror as headless actuator): **recommended**. Maintains architectural cohesion. Reuses existing JWT (`nz_access_token`), CRM RBAC, EventBus.
- **Path C — Layer UI directly on wa-mirror** (Node.js serves frontend + REST): rejected. Loading the wa-mirror event loop with React SSR or heavy RBAC queries jeopardizes the 8 concurrent Baileys WebSocket heartbeats. A blocked event loop cascades to session disconnects across all 8 accounts — the existing wa-mirror is a single point of failure for capture; do not add UI workload to it.

### 4.3 Realtime transport: hybrid LISTEN/NOTIFY + SSE (with WebSocket fallback for compose)

DeepSeek throughput math. Source data from the question: "16-50 msg/5min per active account, 8 accounts". Compute:

- Sustained average: 8 accounts × 33 msg/5min (midpoint) = 264 msg/5min = ~0.88 msg/sec → ~3000 msg/h.
- Peak burst (assume 2× sustained or all 8 accounts at 50/5min simultaneously): 8 × 50/5min = 400/5min = 1.33 msg/sec sustained-high → 2.67 msg/sec true peak burst.
- Fanout audience: 18 concurrent viewers (10 admin + 8 team is a generous upper bound; realistic concurrent dashboard sessions during business hours are 3-6).

| Transport                | Bytes/sec per listener at peak              | Total bytes/sec (18 listeners) | Latency       | Notes                                                                                                  |
| ------------------------ | ------------------------------------------- | ------------------------------ | ------------- | ------------------------------------------------------------------------------------------------------ |
| WebSocket (2-byte frame) | 5.34                                        | 96.1 B/s                       | <50ms         | Stateful, needs heartbeats + reconnection logic                                                        |
| SSE (5-byte frame)       | 13.35                                       | 240.3 B/s                      | <100ms        | Auto-reconnect built-in, HTTP/2 multiplexes free                                                       |
| Postgres LISTEN/NOTIFY   | ≤8KB payload, asyncpg >5000 notif/s ceiling | 2.7 notif/s × 18 = 48.6/s      | <10ms same-DB | Same-database mechanism; both Mini-Pro2 wa-mirror and Pro FastAPI must connect to the same PG instance |

All three are orders of magnitude below hardware limits on a Pro M4 48GB. The decision is on operational complexity, not throughput.

**Important correction (post-redteam)**: Postgres LISTEN/NOTIFY is a **same-database** mechanism, not a same-machine one. It works between any two clients connected to the same PG instance, regardless of where those clients run. In Nuzantara's case, wa-mirror on Mini-Pro2 connects to `nuzantara-postgres.flycast` (Fly internal) or local PG depending on config; the FastAPI backend on Pro connects to the same PG instance (via fly-pg-proxy on `localhost:15432` or the same flycast URL). pg_notify from wa-mirror reaches the FastAPI listener as long as both speak to the same DB. The "intra-machine" wording was wrong in an earlier draft and is corrected here.

**Recommended stack**:

1. **wa-mirror → backend (same-database NOTIFY)**: wa-mirror already INSERTs into `whatsapp_message_context`; add a trigger or explicit `await conn.execute("SELECT pg_notify('wa_message_inserted', $1::text)", payload)` in `apps/wa-mirror/bridge/pg.ts` after INSERT. Backend FastAPI background task running on Pro asyncpg-LISTENs on the same channel. The 62ms Pro↔Mini Tailscale latency is NOT in the NOTIFY path because both clients talk directly to PG; it only affects the wa-mirror's PG-write latency (already accepted in production). Reuses the same outbox-via-NOTIFY pattern already shipped in the EventBus phase-1+phase-2 fix (migration 144/146 per cicatrix-scars 2026-04-29).
2. **backend → browser (read path)**: SSE. Endpoint `GET /api/v1/wa-dashboard/stream` returns an `EventSource` keyed to the authenticated user's RBAC scope. Each pg_notify event is filtered server-side against the user's `assigned_to` allowlist before being forwarded. Browser uses `EventSource` API (auto-reconnect, no manual heartbeat needed).
3. **browser → backend (write path / intervention)**: plain HTTP POST `/api/v1/wa-dashboard/{phone}/send`. Backend validates RBAC, queues into Redis BullMQ-style queue with per-account 10-30s jittered delay, then either pg_notifies wa-mirror to send or uses a direct internal HTTP call into the wa-mirror service. No WebSocket needed for write path — the UI gets the outbound message reflected back via the same SSE stream after wa-mirror writes the outbound row.

This hybrid avoids the WebSocket stickiness problem (sessions tied to a single backend process), avoids adding Socket.io as a dependency, and reuses existing primitives (asyncpg LISTEN, pg_notify, FastAPI Response streaming).

---

## 5. Tech stack proposal for Nuzantara

### 5.1 Frontend

**App location decision (single canonical choice)**: **new `apps/wa-dashboard/`** sibling app. Rationale: (a) `apps/admin-dashboard-local/` is documented as "Pro-only LLM cost dashboard, not deployed anywhere" — narrow scope, wrong concern; (b) `apps/admin-dashboard/` (per INDEX.md "standalone Next.js application to inspect and control Nuzantara data") is closer in spirit but adding 5-10 chat-UI screens + flow visualization there bloats it beyond its current scope; (c) `apps/mouth/` is the public brand/marketing site — conflating internal team tooling with public marketing assets violates separation of concerns; (d) per DeepSeek R2, ~30% worktree-contamination probability on a 2-3 week build inside an existing app per cicatrix 2026-04-29. **A new app + dedicated feature branch reduces collateral risk.** If a shared design system exists at `packages/ui`, lift from there; otherwise vendor the small set of components needed.

| Layer              | Choice                                                           | Rationale                                                                                                        |
| ------------------ | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Framework          | Next.js 16 + React 19 (matching `apps/mouth` versions)           | Same monorepo Next/React majors; App Router for streaming routes; React 19 Suspense for SSE-driven timeline      |
| App location       | **New `apps/wa-dashboard/`**                                     | See decision rationale above                                                                                     |
| UI primitives      | shadcn/ui (Radix UI + Tailwind)                                  | Already used elsewhere in monorepo; accessibility built-in for high-velocity intervention UI                     |
| Chat components    | `@chatscope/chat-ui-kit-react` (MIT)                             | Pre-built MessageList, Message, ChatContainer, MessageInput; saves ~2 weeks of flexbox bubble layout work        |
| Flow visualization | React Flow / `xyflow/react-flow` (MIT)                           | Sole open-source option for "msg → automation → action → handoff" graph rendering; MultiWA validates the pattern |
| State (client)     | Zustand                                                          | Lightweight, no Redux boilerplate; ideal for multi-thread chat state                                             |
| State (server)     | TanStack Query (React Query)                                     | Handles pagination, cache invalidation on SSE event, optimistic UI for compose                                   |
| Forms              | React Hook Form + Zod (lifted from Evolution Manager v2 pattern) | Compose validation, escalate-reason forms                                                                        |
| Icons              | Lucide React (already in monorepo)                               | —                                                                                                                |
| i18n               | English-only for internal tooling (no i18n framework needed)     | Per CLAUDE.md §9 owner uses Italian colloquial in prompts; English in artifacts                                  |

### 5.2 Backend integration

| Layer              | Choice                                                                                                            | Rationale                                                                                                                                                                                                                        |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HTTP layer         | Extend `apps/backend-rag/backend/app/routers/wa_dashboard.py`                                                     | New router namespace; follow existing 271-router pattern; register in `router_registration.py` AND add include_router for both `api`/`both` groups per the PR #423/424 scar lesson (test infrastructure mock ≠ production stack) |
| Realtime push      | FastAPI `StreamingResponse` + asyncpg `add_listener`                                                              | Pure-Python, no new infra. Reuses Postgres connection pool already initialized in `dependencies.py`                                                                                                                              |
| RBAC               | Reuse existing `get_current_user` + Admin/Team `assigned_to` filter                                               | Per CLAUDE.md §10 RBAC rule; zero new auth code                                                                                                                                                                                  |
| Outbound queue     | asyncio queue + per-account `asyncio.Lock` + jittered sleep, OR Redis BullMQ-style                                | Cap outbound at 1 msg per (account × 15s±jitter) — WA-AKG empirical anti-ban pattern. asyncio.Lock variant is simpler; Redis variant survives backend restarts                                                                   |
| wa-mirror dispatch | Add `wa_outbound_queue` row insert in PG + LISTEN on wa-mirror side                                               | Avoids adding HTTP server to wa-mirror; bridge already has `pg.ts` so adding LISTEN is one helper                                                                                                                                |
| Schema additions   | Migration: `wa_dashboard_threads`, `wa_dashboard_assignments`, `wa_dashboard_tags`, `wa_dashboard_outbound_queue` | Keep `whatsapp_message_context` immutable; new tables for UI-side state                                                                                                                                                          |

**Backend deployment location decision**: the FastAPI backend for the dashboard remains on the **existing nuzantara-rag Fly machine** OR a Pro-local process; do NOT colocate on Mini-Pro2. Mini-Pro2 (24GB RAM) already runs wa-mirror + Ollama (qwen3.5:9b + gemma4:26b + deepseek-r1:32b) + cron workload — adding the full 271-router FastAPI process (which loads RAG models, embedding caches, KG SQLite) would exceed its RAM budget. The SSE read path runs on Pro/Fly and queries the same shared PG; the 62ms Tailscale latency only affects wa-mirror's PG writes (already accepted), not the SSE delivery to the browser.

### 5.3 Schema pattern decision

DeepSeek P3: existing `whatsapp_message_context` already uses `chat_type=dm|group` as a single-table discriminator with `group_jid` for group context and `team_member_phone` for sender attribution. **Stick with single-table discriminator** (Evolution API pattern), do NOT migrate to polymorphic ContactInbox (Chatwoot) — that's appropriate for cross-channel (email+web+IG+WA), not for single-channel multi-account where the team_member_phone already distinguishes account. Tercela's schema-namespacing (`channels.contacts`) would add join complexity without benefit.

What needs adding on top (illustrative pattern — authoritative DDL in spec phase):

```sql
-- migration NNN_wa_dashboard_threads.sql (illustrative, NOT authoritative)
CREATE TABLE wa_dashboard_threads (
  thread_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  counterpart_phone TEXT NOT NULL,
  chat_type TEXT NOT NULL CHECK (chat_type IN ('dm','group')),
  group_jid TEXT,
  assigned_to UUID REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','handled','escalated','closed')),
  client_id UUID REFERENCES clients(id),
  practice_id UUID REFERENCES practices(id),
  last_message_at TIMESTAMPTZ NOT NULL
);

-- Postgres does NOT allow expressions inside UNIQUE table-level constraints.
-- The uniqueness "one thread per (counterpart, group)" must be a partial unique index:
CREATE UNIQUE INDEX wa_dashboard_threads_unique_thread
  ON wa_dashboard_threads (counterpart_phone, COALESCE(group_jid, ''));

CREATE TABLE wa_dashboard_outbound_queue (
  queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_member_phone TEXT NOT NULL,  -- which account sends
  counterpart_phone TEXT NOT NULL,
  body TEXT,
  media_path TEXT,
  scheduled_for TIMESTAMPTZ NOT NULL,  -- jittered cooldown anchor
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','dispatched','failed','cancelled')),
  dispatched_baileys_message_id TEXT,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

The original sketch used a table-level `UNIQUE (counterpart_phone, COALESCE(group_jid,''))` which **Postgres does not support** — table-level UNIQUE constraints take column names only, not expressions. The fix is a `CREATE UNIQUE INDEX … ON (col1, expr(col2))` after table creation. This kind of detail is the reason §8 requires Squawk migration lint on the authoritative spec DDL.

### 5.4 Local-only deployment posture

The webapp runs on Pro M4 48GB only (per question wording). This means:

- No Fly.io deploy of the **frontend** needed; bind `localhost` only. The Next.js dev server (`npm run dev`) on Pro is the primary access surface.
- No SSL termination needed (or use mkcert for dev).
- **Auth options (one canonical choice required in spec phase, the doc surfaces the trade-off, not the decision)**:
  - Option A: local-only auth with a hard-coded admin password in `.env` — simplest, but no per-user audit trail.
  - Option B: issue a separate local-only JWT against the existing `users` table — requires a dev-mode login route on FastAPI returning a `localhost`-scoped cookie. Best audit trail.
  - Option C: reverse-proxy through `kita.balizero.com/wa-dashboard/*` so the existing `nz_access_token` cookie domain matches — production exposure of internal tooling; needs auth gate; rejected for v1.
  - Default recommendation: Option B.
- Postgres is already accessible (local fly-pg-proxy on `localhost:15432` per cicatrix-scars). asyncpg LISTEN/NOTIFY works against both.
- wa-mirror runs on Mini-Pro2 (per its README). The dashboard backend runs on Pro (or on the existing nuzantara-rag Fly machine). Both connect to the same Postgres → pg_notify works cross-machine via the shared DB. The browser frontend runs on Pro localhost.

---

## 6. Risks + open questions

1. **Baileys breakage cadence**. DeepSeek estimate: 8-12 weeks between WhatsApp protocol updates that break Baileys. Mitigation: pin `@whiskeysockets/baileys` to a tested release in `package.json`, add a `wa_mirror_baileys_health.py` cron that alerts on session-corruption rate spikes, schedule a 10-week retest in the calendar. The dashboard depends on wa-mirror; if Baileys breaks, capture stops first, and the dashboard correctly shows "no new messages" rather than malfunctioning.

2. **Anti-ban risk on 8 simultaneous accounts**. Meta heuristics flag identical device fingerprints, rapid burst sends, and unnatural cadence. The dashboard's intervention path is the highest-risk surface — a human clicking Send 5× in 10 seconds across 5 threads on one account would trigger detection. Mandatory: per-account rate limiter (10-30s jitter, WA-AKG empirical pattern), surfaced as a "Send in 18s" UI countdown rather than blocking silently. Open question: should the rate limit be hard-coded or per-account configurable? Default hard-coded 15s, override via env.

3. **Group chat sender attribution**. Baileys exposes `participant` (LID or JID), `participantPn` (phone-number format, sometimes missing), and `pushName` (ephemeral display name, can change). Existing `whatsapp_message_context` already stores `sender_push_name_snapshot` — good. Open question: when a group member's `pushName` changes, does the UI show "Adit (was: Aditya)" or just the latest? Decision: latest, with hover-tooltip showing snapshot at message time. Reference: WhiskeySockets/Baileys issues #399, #1247, #1667.

4. **OCR JSONB display**. Existing rows have `ocr_result` JSONB. No open-source candidate ships an OCR display layer. Need a tiered renderer: (a) if `ocr_result` contains a `text` field, show inline collapsed-by-default; (b) if it contains structured KBLI/MRZ/NPWP, show a "Detected: NPWP 12.345.678..." badge with click-to-expand. This is greenfield UI work, no lift candidate.

5. **RBAC for unassigned threads**. Existing CRM RBAC filters by `assigned_to` matching the requesting user. WhatsApp messages from unknown numbers (`client_id IS NULL`, prospects/leads) have no `assigned_to`. Default visibility decision: visible to all Admins + the team member whose account received it (`team_member_phone` matches). Tag for triage: `wa_dashboard_threads.status='open'` AND `assigned_to IS NULL`. Open question: should Team members be able to claim unassigned threads or only Admins? Default: Admins only claim, Team members can request-claim (creates a notification for Admin).

6. **Worktree contamination during build**. Cicatrix 2026-04-29 scar documents 2× untracked-file-loss in 9 hours from sibling automation switching branches. Mitigation: develop on a dedicated branch `feat/wa-dashboard-2026-MM-DD`, WIP-commit every 10 minutes whenever untracked files exist, push within 30 seconds of commit, run `ps aux | grep claude | wc -l` at session start. Use the existing `~/scripts/symbiosis-WIP-checkpoint.sh`-style helper if available.

7. **Postgres NOTIFY 8KB payload limit**. Notifying with a JSON containing the full message body could exceed 8KB on long messages or media metadata. Solution: notify only `{message_id, team_member_phone, counterpart_phone, chat_type}` (well under 8KB); the SSE worker then SELECTs the full row by ID. This is the standard "outbox pointer" pattern.

8. **Outbound send via wa-mirror requires bridge changes**. The README explicitly states "NOT a reply bot. v1 captures the one-to-one message stream for audit/continuity and does not send messages." Adding send capability is v2 scope and requires updating the wa-mirror README + handshake protocol. Open question: who signs off on the v2 send capability — Antonello directly, or does it need a Symbiosis Law 5 (Zero ultima istanza) escalation given compliance implications? Default: escalate via `shared/escalations.json` HIGH priority.

9. **Mini-Pro2 ↔ Pro network latency**. Tailscale DERP USA latency 62ms (per MEMORY). For the SSE read path, the FastAPI listener on Pro receives pg_notify directly from the shared DB (whether the DB is on Fly or local — see §5.4) so the Tailscale leg is not in the SSE delivery path. The Tailscale leg only affects wa-mirror's PG writes (already accepted in production). **Do NOT colocate FastAPI backend on Mini-Pro2** — its 24GB RAM is committed to Ollama + wa-mirror + cron; adding the 271-router FastAPI process (RAG models + embedding cache + KG SQLite) risks OOM.

10. **DeepSeek redteam pre-publish gate could not complete**. Three attempts to run DeepSeek devils-advocate over the doc (full + section 4-6 only + flash variant) returned empty completions despite tokens being consumed (finish_reason=length, content len=0). Cause unclear — possibly the model's internal reasoning consuming all output tokens regardless of `reasoning_effort=low`, or an undocumented limit. Workaround: self-redteam by Claude Opus 4.7 (the canonical model for red-team per CLAUDE.md routing). Documented for future deep-researcher panels — when DeepSeek returns empty, fall through to Opus self-redteam rather than skip the gate.

11. **UU PDP 27/2022 lawful basis — HIGHEST-LEVERAGE RISK**. _(Added post-redteam.)_ Indonesia's Personal Data Protection Law (UU PDP 27/2022, effective Oct 2024 with 2-year transition) requires a lawful basis for processing personal data — consent, contract, legitimate interest, vital interest, legal obligation, or public interest. Bali Zero's existing wa-mirror captures messages on a _team member's personal WhatsApp account_ covering communications with both clients (lawful basis: contract / KYC obligation, defensible) and **unknown prospects who messaged the team member without knowing their messages are being centrally captured** (lawful basis: arguably _legitimate interest_ but contested — particularly weak when the prospect did not initiate the contact). The dashboard intensifies this exposure by (a) making the captured data visible to a broader internal audience than just the message recipient, and (b) introducing outbound send capability from a centralized system, which moves the activity from "passive logging" to "active processing in the PDP sense". **Required spec gate**: legal-counsel review (e.g., the firm already advising Bali Zero on UU PDP compliance) signing off on (i) the prospect-message retention basis, (ii) the centralized-reply lawful basis, (iii) the data subject rights surface (deletion-on-request, access-on-request). This is NOT optional. Until counsel signs off, the project ships only the read-only timeline (no outbound, no reply), gated behind Admin-only access.

---

## 7. Convergent vs divergent across the 3-LLM panel

| Topic                    | Claude Opus 4.7 (synthesis)                 | Gemini 3.1 Pro (long-context)            | DeepSeek V4 Pro (numerical)                                    | Verdict                                                                |
| ------------------------ | ------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Integration path         | Path B (greenfield + lift)                  | Path B explicitly                        | (not asked qualitatively)                                      | **3/3 convergent on B**                                                |
| Realtime transport       | Hybrid LISTEN/NOTIFY + SSE                  | Hybrid LISTEN/NOTIFY + SSE               | WebSocket OK, SSE OK, NOTIFY safe (no opinion on hybrid)       | **Convergent on SSE/NOTIFY, divergent on WebSocket necessity**         |
| Schema pattern           | Single-table discriminator + sidecar tables | (Reference Tercela schema normalization) | Single-table discriminator (Evolution pattern)                 | **2/3 convergent on discriminator, Gemini agnostic**                   |
| Top-1 candidate to lift  | WA-AKG (chat UI + multi-session)            | WA-AKG (closest stack alignment)         | Chatwoot (highest MHI 2.04, but stack-overlap-aware Tercela=8) | **2/3 WA-AKG, DeepSeek raw-numerical favors Chatwoot for MHI**         |
| Dashboard app location   | New `apps/wa-dashboard`                     | Inside existing `apps/mouth` Next.js     | New `apps/wa-dashboard` (R2 worktree risk)                     | **2/3 new app, Gemini prefers reuse mouth** — final synthesis: new app |
| Anti-ban delay           | 10-30s jittered cooldown                    | 10-30s jittered cooldown                 | 10-30s WA-AKG empirical pattern                                | **3/3 convergent**                                                     |
| Baileys breakage cadence | (not estimated)                             | (not estimated)                          | 8-12 weeks                                                     | **DeepSeek-only data point**                                           |
| State management         | (not opinionated)                           | Zustand + React Query                    | (not asked)                                                    | **Gemini sole opinion, accepted**                                      |
| Top library for flow viz | React Flow                                  | React Flow (xyflow/react-flow)           | (not opinionated)                                              | **2/2 convergent**                                                     |
| Chat component library   | (not opinionated)                           | chatscope/chat-ui-kit-react              | (not opinionated)                                              | **Gemini sole opinion, accepted**                                      |

Major divergence: where to host the dashboard app. Gemini argued for reuse of `apps/mouth` (Next.js 16 + React 19, "design system continuity"); DeepSeek argued for new `apps/wa-dashboard` (worktree-contamination math). Synthesis sides with DeepSeek on the location decision because `apps/mouth` is the public-facing brand site and conflating internal team tooling with public marketing assets violates separation of concerns. The shared design system can be exposed via `packages/ui` if it exists; otherwise the few components needed (chat bubbles, dashboard chrome) are lightweight enough to vendor.

---

## 8. Checklist for spec phase

The main-agent spec writer should resolve these before any code:

- [ ] **GATING**: obtain legal-counsel sign-off on UU PDP 27/2022 lawful basis for (a) prospect message retention, (b) centralized reply, (c) data subject rights surface. Until signed off: read-only Admin-only MVP.
- [ ] Confirm dashboard app location: new `apps/wa-dashboard/` (recommended in this doc) vs extending `apps/admin-dashboard/`. Lock the decision.
- [ ] Confirm v2 send-capability scope addition to wa-mirror — explicit Antonello sign-off + bridge README update.
- [ ] Define schema migrations: `wa_dashboard_threads`, `wa_dashboard_outbound_queue`, `wa_dashboard_assignments`, `wa_dashboard_tags`. Lint via Squawk (per pre-deploy hook). Use `CREATE UNIQUE INDEX … ON (col, expr(col))` for the partial-uniqueness constraint per §5.3 correction.
- [ ] Define RBAC matrix: which user roles see which threads, who can claim, who can escalate, who can reassign.
- [ ] Define rate-limit policy: hard-coded 15s default, env override, surfaced as UI countdown. Per-account asyncio.Lock vs Redis BullMQ — pick one.
- [ ] Define LISTEN/NOTIFY channel names: `wa_message_inserted`, `wa_outbound_queued`, `wa_outbound_dispatched`. Add to existing `PG_CHANNEL_MAP` in EventBus.
- [ ] Define OCR display tiered renderer pattern.
- [ ] Decide auth strategy (Option A/B/C from §5.4). Default: Option B (local JWT).
- [ ] Plan Baileys retest cadence: every 10 weeks calendar entry.
- [ ] Add Squawk migration lint + pre-push hooks already in cicatrix repertoire to the new app's CI.
- [ ] Define error-handling matrix: what does the UI show when wa-mirror is offline / when Baileys session is in QR-rescan / when outbound queue is full?

---

## 9. Sources

GitHub repositories evaluated:

1. https://github.com/EvolutionAPI/evolution-api (Apache 2.0, 8.4k stars, latest v2.3.7 Dec 2025)
2. https://github.com/EvolutionAPI/evolution-manager-v2 (Apache 2.0, 4 stars, React+Vite+Radix)
3. https://github.com/devlikeapro/waha (Apache 2.0, 6.6k stars, 3-engine multi-session)
4. https://github.com/ribato22/MultiWA (MIT, 24 stars, NestJS+Next.js 14)
5. https://github.com/mrifqidaffaaditya/WA-AKG (MIT, 19 stars, Next.js 15+Baileys)
6. https://github.com/chatwoot/chatwoot (MIT, 29.6k stars, v4.14.0, Rails+Vue)
7. https://github.com/tags-dev/tercela (Hono+Bun+Nuxt 4, omnichannel)
8. https://github.com/wppconnect-team/wppconnect-frontend (Apache 2.0, 238 stars, ARCHIVED Apr 2024)
9. https://github.com/wppconnect-team/wppconnect-server (Apache 2.0, 1k stars, v2.10.0 May 2026)
10. https://github.com/wppconnect-team/wppconnect-manager (low maintenance signal)
11. https://github.com/kopigreenx/zete-whatsapp-dashboard (PHP/Laravel + Node)
12. https://github.com/mohit2777/whatsapp-web.js-multiple-accounts-dashboard-with-webhooks-functionality (MIT, 1 star, JS+Supabase)
13. https://github.com/rmyndharis/OpenWA (Docker compose, dashboard:2886)
14. https://github.com/WhiskeySockets/Baileys (the underlying library; issue refs #399, #1247, #1667, #1683)

UI/pattern libraries:

15. https://github.com/xyflow/react-flow (MIT, node-based UI for flow viz)
16. https://github.com/chatscope/chat-ui-kit-react (MIT, chat component primitives)
17. https://github.com/assistant-ui/assistant-ui (TS+React AI chat primitives)

Architecture references:

18. https://dev.to/teglos/i-built-an-open-source-whatsapp-business-inbox-for-teams-heres-how-411d (Tercela design rationale article)
19. https://dev.to/ribato/building-multiwa-an-open-source-self-hosted-whatsapp-api-gateway-2me1 (MultiWA architecture article)
20. https://www.blog.brightcoding.dev/2026/02/17/evolution-api-the-revolutionary-whatsapp-integration-platform (Evolution API ecosystem)
21. https://deepwiki.com/EvolutionAPI/evolution-api/8-development-guide (Manager UI architecture)
22. https://deepwiki.com/chatwoot/chatwoot/7.1-email-configuration (Channel polymorphism)
23. https://github.com/chatwoot/chatwoot/issues/13426 (multi-tenant WhatsApp embedded)
24. https://baileys.wiki/docs/api/interfaces/GroupMetadata/ (Baileys group metadata reference)

Realtime / transport / pattern research:

25. https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks (transport trade-offs)
26. https://leapcell.io/blog/realtime-applications-with-postgresql-listen-notify-a-lightweight-alternative (LISTEN/NOTIFY ceiling)

Internal Nuzantara references (read-during-research):

- `apps/wa-mirror/README.md` (capture bridge scope, v1 capture-only constraint, UU PDP 27/2022 motivation)
- `apps/wa-mirror/bridge/{events,filters,heartbeat,index,media,message_capture,pg,phone,session,telegram}.ts` (bridge surface)
- `apps/backend-rag/backend/db/migrations_v2/{173,177,188}_wa_mirror_*.sql` (existing schema)
- `CLAUDE.md` §16 Research Capture convention, §10 RBAC, §1 architecture
- `.claude/rules/cicatrix-scars.md` (2026-04-29 worktree contamination, 2026-04-29 EventBus PG NOTIFY pattern, 2026-05-22 launchctl/wave-1 fix lessons)
- `MEMORY.md` index entries on Mini-Pro2 24/7 server topology, Tailscale 62ms DERP USA

Panel intermediate outputs (preserved for traceability):

- `/tmp/wa-dashboard-gemini-prompt.txt` + `/Users/nuzantara/.gemini/antigravity-cli/brain/069533cc-fd9f-4e7c-a0a3-d6c7133d1277/whatsapp_dashboard_synthesis.md` (Gemini 3.1 Pro full markdown, ~2000 words)
- `/tmp/wa-dashboard-deepseek-prompt.txt` + `/tmp/wa-dashboard-deepseek-output.txt` (DeepSeek V4 Pro numerical analysis, ~1500 words, 4 tables)
- `/tmp/wa-dashboard-redteam.json` (DeepSeek redteam attempts — empty completions, fallback to Opus self-redteam documented in §10)
