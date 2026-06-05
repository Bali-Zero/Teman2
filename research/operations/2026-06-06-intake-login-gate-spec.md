---
title: "INTAKE Login Gate — mandatory pre-workspace clearance (3 gates)"
status: REVIEWED by 4-LLM panel 2026-06-06 (Gemini 3.1 Pro · GPT-5.5 Codex · DeepSeek V4 Pro · Claude Opus 4.8) — awaiting Antonello approval
panel_verdict: ship-with-fixes (3/4) · redesign (1/4, Codex) — §11 records the 8 consensus fixes folded in
author: Claude Opus 4.8 (1M)
date: 2026-06-06
relates_to:
  - research/operations/2026-06-06-fase5c-go-live-spec.md   # the writer this gate fronts
  - apps/backend-rag/backend/app/routers/intake_review.py    # gate 1 backend (DONE)
  - apps/backend-rag/backend/app/routers/compliance_alerts.py # gate 3 backend (mostly DONE)
  - apps/backend-rag/backend/app/routers/hr_late_reply.py     # gate 2 backend (token-only today)
constitution: free-first, CLI-only LLM, PII stays local, server-side identity is truth
---

# INTAKE Login Gate

## 0. One-paragraph summary

After a Bali Zero worker logs into `kita.balizero.com`, they land on a **mandatory
clearance screen** that blocks the rest of the workspace (Dashboard, Clients, Process,
HR…) until **three queues that belong to them personally are at zero**:

1. **📄 Documents** received on their WhatsApp/email that need approve/reject.
2. **⏰ Late note** — if they clocked in after the limit today and haven't explained it.
3. **🚨 Client deadlines** — their assigned clients with a statutory deadline ≤ 7 days
   not yet acknowledged.

It is a **hard gate, zero escape**: the only ways past are to *resolve* each item
(approve/reject the doc, submit the late reason, acknowledge the deadline). There is no
"skip". The gate applies to **everyone who has an inbox** (salaried workers). Admins:
see §8 (open decision).

This is the human face of the FASE 5C writer — the writer scrives nel CRM, the gate is
where a human decides *which* documents get written.

---

## 1. Why a gate (not just a menu item)

A passive "Documents" menu item gets ignored — exactly the failure mode of the
Surya/Receh case: things arrive on a personal phone and silently rot because nobody is
forced to look. A gate converts "you should look" into "you cannot work until you look".

Scope discipline: the gate's job is **forced disposal of per-person obligations that
already have a clear owner and a clear done-state**. We deliberately picked the three
queues that satisfy both. We explicitly excluded leave-approval, payroll, cockpit
intents, and policy-acknowledgement (no per-worker owner OR no terminal state OR not
yet built) — see §9.

---

## 2. The three gates — data sources (all verified on origin/main 2026-06-06)

### Gate 1 — Documents 📄  (backend: DONE)

- **State**: `intake_queue` + `document_routing_proposal` (migration
  `212_intake_unified.sql`). Pending = `status IN ('review_pending','review_claimed')`.
- **Owner per-person**: derived at query-time — `entity_resolution.candidates[].client_id
  → clients.assigned_to`, matched against `user_email`. Admin bypass via `is_crm_admin`.
  This is the EXISTING logic in `intake_review.py:201-204` (queue) / `:355-356` (claim).
- **Done state**: `status IN ('routed','rejected','dead','done')` — terminal, leaves the
  pending set.
- **Endpoints (exist)**: `GET /api/intake/review/queue`, `POST …/{id}/claim`,
  `POST …/{id}/approve`, `POST …/{id}/reject`, `POST …/{id}/release`.
- **Gap**: the queue is scoped by `assigned_to` (who the client belongs to), NOT yet by
  *who received the WhatsApp* (`whatsapp_message_context.team_member_email`, dropped in
  `whatsapp_adapter.py`). For NO_MATCH orphans there is no `assigned_to` at all → today
  they are admin-only-visible. **This is the one real backend gap for gate 1** (see §6).

### Gate 2 — Late note ⏰  (backend: PARTIAL — token-only today)

- **State**: `attendance_late_incidents` (migration `092_…`). Pending =
  `state IN ('AWAITING_REPLY','REMINDER_SENT','ESCALATED')` for `late_date = today`.
- **Owner per-person**: `email` column — exact, no derivation needed. Best owner-match of
  the three.
- **Done state**: `state IN ('RESOLVED','RESOLVED_LATE')` (+ `reply_received_at NOT NULL`).
- **Endpoints (exist)**: only the **unauthenticated token flow** —
  `GET/POST /hr/late-reply/{id}?token=…` in `hr_late_reply.py`. The token IS the auth;
  it arrives by email.
- **Gap**: no "**my** pending late incidents for the logged-in user" endpoint, and no way
  to submit a reason as an *authenticated* user (only via the email token). **Gate 2
  needs a new small authenticated endpoint** (see §6).

### Gate 3 — Client deadlines 🚨  (backend: MOSTLY DONE)

- **State**: `compliance_alerts` (migration `114_…`). Pending =
  `status IN ('pending','sent')` AND `deadline <= today + 7`.
- **Owner per-person**: `client_id → clients.assigned_to = user_email` — the EXISTING
  scoping in `compliance_alerts.py:152,173`. Admin sees all (`_is_admin`).
- **Done / acknowledge**: the CHECK already allows `status='acknowledged'`
  (`114_…:39`). So "I've got this" = transition `pending/sent → acknowledged`. This is an
  **acknowledge, not a resolve** (resolving a KITAS renewal takes days; blocking daily
  until resolved would be torture — operator-confirmed).
- **Endpoints (exist)**: `GET /api/compliance-alerts` (mine, scoped) +
  `POST /api/compliance-alerts/{alert_id}/outcome`.
- **Gap**: confirm `outcome` accepts an `acknowledged` transition; if it only writes a
  resolution outcome, add `acknowledged` as a permitted outcome. Minor.

---

## 3. The gate contract (frontend ↔ backend)

### 3.1 Single status endpoint — `GET /api/intake/gate/status`

One call the workspace layout makes on every load. Returns the per-user clearance state:

```jsonc
{
  "blocked": true,                  // true if ANY section non-empty
  "sections": {
    "documents":  { "count": 3, "blocking": true },
    "late_note":  { "count": 1, "blocking": true },
    "deadlines":  { "count": 2, "blocking": true }
  },
  "as_of": "2026-06-06T01:12:00Z"
}
```

- Identity is taken from `get_current_user` **server-side** — never from the frontend
  `storedProfile`/localStorage (which is spoofable). The gate's authority is the JWT.
- `blocking: true` only for the three chosen gates. Adding a 4th gate later = add a key;
  the frontend renders any section it's told about (data-driven, no redeploy to toggle).
- This endpoint is **cheap**: three `SELECT EXISTS/COUNT` with the existing indexes
  (`idx_iq_review_pending`, `idx_late_incidents_state_sent`, `ix_compliance_alerts_deadline`).
  Target < 50 ms. It is called on every workspace mount, so it must stay a count-only
  probe — it does NOT return the items themselves.

### 3.2 The gate is enforced in TWO places (defence in depth)

1. **Frontend** (`apps/mouth (workspace)/layout.tsx`): if `blocked`, render the gate
   screen instead of `children` and hide the sidebar nav targets. UX layer.
2. **Backend** (every workspace data router): a dependency `require_gate_cleared(user)`
   that 423-Locks (`HTTP 423 Locked`) any workspace API call while the user is blocked.
   Without this, a worker could bypass the screen by hitting `/api/clients` directly.
   **The frontend gate is convenience; the backend lock is the actual gate.**

> ⚠️ Open question for the panel: 423 on *all* workspace routers is a big blast radius.
> Alternative: gate only the **mutating** endpoints (POST/PATCH/DELETE) so a blocked
> worker can still *read* but not *act*. See §8 Q3.

### 3.3 Clearing each section (reuses existing endpoints where possible)

| Section | Action in gate | Endpoint | New? |
|---|---|---|---|
| 📄 Documents | Take / Approve / Reject | `…/claim`, `…/approve`, `…/reject` | exists |
| ⏰ Late note | Submit reason (authenticated) | `POST /api/hr/my-late-incident/resolve` | **NEW** |
| 🚨 Deadlines | "I've got this" → acknowledge | `POST /api/compliance-alerts/{id}/outcome` (outcome=`acknowledged`) | verify |

When all three sections report `count = 0`, `blocked` flips to `false` → "Enter
workspace →".

---

## 4. New backend work (minimal — 2 endpoints + 1 status probe)

1. **`GET /api/intake/gate/status`** — the §3.1 probe. New router
   `app/routers/intake_gate.py`. Three count queries, no PII in the response (counts
   only). PUBLIC_ENDPOINTS: NO (auth required). Must be registered in BOTH
   `router_registration.py` include-functions (scar: 2026-05-02 manifest-vs-registration
   parity).

2. **`POST /api/hr/my-late-incident/resolve`** — authenticated equivalent of the token
   form. Looks up today's incident `WHERE email = current_user.email AND state IN
   ('AWAITING_REPLY','REMINDER_SENT','ESCALATED')`, sets `state` (RESOLVED or
   RESOLVED_LATE by the same rule as `hr_late_reply.py:256-259`), stores `reply_content`,
   `reply_received_at = now()`. Idempotent (already-resolved → 200 no-op). Reuses the
   exact state-transition map already in `hr_late_reply.py` — do NOT duplicate the logic,
   extract it to a shared helper (anti-drift, same discipline as `_require_active_claim`
   in intake_review).

3. **`require_gate_cleared` dependency** — shared FastAPI dependency that calls the same
   three count queries and raises `423` if blocking. Applied per §3.2 (scope = panel
   decision §8 Q3).

**No migration required.** All three tables exist; `compliance_alerts.status` already
permits `acknowledged`. If gate 1 NO_MATCH orphan routing (§6) is included in v1, that
needs the `whatsapp_adapter.py` link-back — but that is sequenced as a **follow-up**, not
a blocker for v1 (v1 gate 1 = `assigned_to`-scoped, same as today's queue).

---

## 5. Frontend work

- New gate screen component under `apps/mouth/src/app/(workspace)/` — rendered by the
  layout when `GET /gate/status` returns `blocked`. Single scrolling screen, three
  sections (Late → Documents → Deadlines), matching the approved ASCII mockup. English UI.
- The layout already fetches a user profile on mount (`layout.tsx:70-86`); add the gate
  fetch alongside it. While `gate/status` is in flight, show the existing loading state
  (do NOT flash the workspace then yank it — render gate-or-loading, never workspace,
  until status is known).
- Each section's action buttons call the §3.3 endpoints, then re-fetch `gate/status`.
- "All clear" state → `[ Enter workspace → ]` reveals `children` + sidebar.

---

## 6. Known gap: "received by whom" vs "assigned to whom" (gate 1)

The approved mockup says each worker sees the documents **they received** on WA/email.
Today the intake queue is scoped by `clients.assigned_to` (who owns the *client*), which
is a *different* thing — and for NO_MATCH orphans there is no `assigned_to` at all.

- `whatsapp_message_context.team_member_email` DOES capture who received the WA, but
  `whatsapp_adapter.py` drops it when building the intake row (`source_ref =
  whatsapp:{staging_id}`, `client_hint = matched_client_id` — no receiver carried).
- **v1 decision (proposed)**: ship the gate with `assigned_to` scoping (works today,
  zero new DB), and treat "scope by receiver + route orphans to receiver" as a **fast
  follow** that (a) carries `team_member_email` into the intake row and (b) adds it to
  the queue filter. This keeps v1 small and avoids coupling the gate to a schema change.
- Flag for the panel: is `assigned_to`-only acceptable for v1, or is "by receiver"
  load-bearing enough that it must be in v1? (§8 Q1)

---

## 7. Failure modes & safety

- **Empty-state correctness**: if a worker is genuinely clear, `blocked=false` and they
  never see the gate. The gate must not false-positive (e.g. a `compliance_alert` for a
  client NOT assigned to them must not block them).
- **Status-probe outage**: if `GET /gate/status` errors, **fail OPEN or CLOSED?**
  Proposed: **fail OPEN** (let them into the workspace) — a status-probe bug must not
  brick the entire company out of kita. Log + alert instead. (Panel Q4.)
- **Stuck on an ambiguous document**: hard-gate's weak point. Mitigation: Reject is
  always a valid exit ("not sure → Reject, it's cleared not lost"). The reject path is
  flag-independent and already live (#1147).
- **Late-note for a day off / approved leave**: must not raise an incident on a day the
  worker is on approved leave. Confirm the attendance cron already excludes leave days
  (else the gate inherits a false-positive). (Panel Q5.)
- **Admin lockout**: if admins are gated (§8 Q2) and an admin has a stuck item, they
  could lock themselves out of the very tools needed to fix it → admins should always
  retain a bypass to at least the HR/intake admin views.

---

## 8. Open decisions for the 4-LLM panel

- **Q1** — Gate 1 scope in v1: `assigned_to`-only (ship now) vs "by receiver" required
  (couples to `whatsapp_adapter` change). Recommended: `assigned_to` v1 + receiver fast-follow.
- **Q2** — Do admins (zero@/asya@/antonellosiano@) pass through the gate too? Operator
  said "everyone with an inbox". Recommended: yes, but with a permanent escape hatch to
  HR/intake admin views to avoid self-lockout (§7).
- **Q3** — Backend enforcement scope: 423 on ALL workspace routers vs only mutating
  (POST/PATCH/DELETE) endpoints. Recommended: mutating-only (read stays open) — smaller
  blast radius, still prevents acting-while-blocked.
- **Q4** — `gate/status` outage: fail OPEN vs CLOSED. Recommended: fail OPEN + alert.
- **Q5** — Late-note false positives on leave/holiday/weekend: confirm cron exclusion
  before gating, else gate inherits bad data.
- **Q6** — Deadline button semantics: `acknowledge` (recommended, returns if ignored too
  long) vs must-resolve (rejected as torture). Confirm "returns if ignored" re-surface
  rule (e.g. acknowledged deadline re-blocks at deadline-1day if still `acknowledged`).

---

## 9. Explicitly out of scope (and why)

| Candidate | Why excluded from v1 |
|---|---|
| 📱 Personal-channel reconciliation (anti-Surya) | Needs a new `reconciled` flag + schema; high value but is the §6 fast-follow's natural home. Phase 2. |
| Leave-request approval | Owner is the manager, not the worker → not a per-worker gate. |
| Payroll sign-off | Only the payroll manager acts; workers don't. |
| Cockpit intents | No per-user owner column → can't scope per login. |
| Policy/handbook acknowledgement | No table exists; would be built from zero. Good Phase 3. |

---

## 10. Build sequence (after panel + approval — NOT started)

1. Backend: `intake_gate.py` status probe (3 count queries) + tests on `nuzantara_dev`.
2. Backend: `POST /api/hr/my-late-incident/resolve` (extract shared state-transition
   helper from `hr_late_reply.py`) + tests.
3. Backend: confirm/extend compliance `outcome=acknowledged` + test.
4. Backend: `require_gate_cleared` dependency (scope per Q3) + register routers in BOTH
   include-functions (manifest-parity scar) + integration test that a blocked user gets
   423 on a mutating workspace endpoint.
5. Frontend: gate screen + layout interception + re-fetch-on-action + "Enter workspace".
6. E2E: blocked → clear each section → unlock.

All tests run on the Pro `nuzantara_dev` (the pool fixture skips if unreachable;
skipping on Air-M5 hid 4 real bugs in #1145).

---

## 11. 4-LLM panel results (2026-06-06) — consensus fixes folded into the spec

Panel: Gemini 3.1 Pro (agy), GPT-5.5 (Codex), DeepSeek V4 Pro, Claude Opus 4.8.
Verdict: **ship-with-fixes ×3, redesign ×1 (Codex — same defects, harsher grade).**
Votes were near-unanimous on all 6 questions. The 8 fixes below are now BINDING on the
build (§10), not optional.

### Unanimous / strong-majority fixes (MUST)

- **F1 — Allowlist the clearing endpoints from the 423 lock (4/4).** The single worst bug:
  if `require_gate_cleared` guards *every* router, it also guards `gate/status` and the
  approve/reject/claim/late-resolve/acknowledge endpoints → a blocked user can NEVER
  clear → infinite lock. **Fix**: the gate dependency applies to workspace *business*
  routers only, with an explicit allowlist: `gate/status`, intake
  claim/approve/reject/release, `my-late-incident/resolve`, compliance
  `outcome`, auth/profile, and admin-rescue routes. (Supersedes §3.2 as written.)

- **F2 — Lateness must NOT be scoped to `late_date = today` (Gemini + Claude).** Querying
  only today lets a worker wait until tomorrow to escape an unexplained late note. **Fix**:
  pending = `state IN ('AWAITING_REPLY','REMINDER_SENT','ESCALATED')` for ALL dates, not
  just today. (Amends §2 Gate 2 + §4.2.)

- **F3 — Other-claimed documents must not block you (Gemini + DeepSeek + Codex).**
  Including `review_claimed` in the blocking count means: if worker A claims a doc on a
  client shared with worker B, worker B is gated on a doc they can't touch. **Fix**: the
  blocking count for a user = `review_pending` + `review_claimed BY THAT USER`. Docs
  claimed by someone else are excluded from your gate. (Amends §2 Gate 1.)

- **F4 — Backend gate evaluator owns fail-open, not just the frontend (Codex + Claude).**
  §7 says "fail open" but only the frontend stated it; the backend dependency would
  fail-CLOSED on a DB error. **Fix**: ONE shared gate evaluator used by both the probe and
  the dependency; on its own internal error it fails OPEN + audit-logs + alerts (circuit
  breaker). The hard-gate guarantee comes from the evaluator computing live counts, not
  from a cached probe. (Reconciles §0 hard-gate with §7 Q4 fail-open.)

- **F5 — Gate must re-engage after entry (DeepSeek + Claude).** Status is fetched only on
  mount, so a worker who clears once stays in all day while new obligations arrive.
  **Fix**: re-evaluate on every workspace route change (cheap count probe) + force the
  gate screen if `blocked` flips true. Document that the probe is point-in-time. (Amends
  §3.1 + §5.)

- **F6 — Admin unbounded-queue lockout (DeepSeek + Claude).** `is_crm_admin` sees ALL
  pending docs company-wide → an admin is blocked on hundreds of items, no exit. **Fix**:
  admin's gate is scoped to items they personally received/are assigned to; PLUS a
  permanent visible "Admin override" on the gate screen routing to intake/HR admin views
  without clearing. (Amends §2 Gate 1 admin + §7 + §8 Q2.)

### High-value additions the spec missed (SHOULD, panel-surfaced)

- **F7 — Stale-claim recovery (Codex).** A doc `review_claimed` by someone absent/fired/
  blocked keeps a co-assignee gated forever. The claim lease already has
  `lease_expires_at` (P0#5) — surface it: expired claims drop back to `review_pending`
  (already happens on next claim) AND the gate count must treat an *expired* foreign claim
  as claimable, not as a permanent foreign block. Add "blocked by another claimant
  (expires in N min)" to the UI. (New, ties to F3.)

- **F8 — Workload ceiling for returners (Claude).** A worker back from leave with 40 docs +
  15 deadlines is trapped for hours by the hard-gate — it punishes absence hardest. **Fix**:
  above a threshold (e.g. > 15 blocking items) the gate shows "high volume — request help"
  with an escalation to admin + optional batch-acknowledge for deadlines. (New, §7.)

### Loopholes flagged (track, decide later — NOT v1 blockers)

- **L1 — Clock-in loophole (Gemini).** A worker who never clocks in generates no late
  incident → escapes Gate 2 entirely. The gate can't fix a missing clock-in; this belongs
  to the attendance system (a "no clock-in by 10:00" incident). Logged for the attendance
  owner, out of scope here.

- **L2 — Double-action race on shared-client docs (DeepSeek).** Two co-assignees could act
  on the same doc. F3 + forced-claim-before-approve (already the intended flow; make it
  mandatory in the UI: Approve/Reject disabled until Taken) closes most of it. The
  claim/lease atomic UPDATE (intake_review `:363-371`) is the backstop.

### Panel vote tally on the 6 open questions

| Q | Outcome (consensus) |
|---|---|
| Q1 — gate 1 scope | **by-receiver in v1** — DECIDED by Antonello 2026-06-06: ship the bigger v1. The `assigned_to` shortcut is rejected. v1 MUST carry `whatsapp_message_context.team_member_email` (and the email-intake equivalent) through `whatsapp_adapter.py` into the intake row, then scope the queue + the gate count by receiver. NO_MATCH orphans route to whoever received them. This makes the gate the direct anti-Surya control. |
| Q2 — admins gated? | **yes, with visible override** (4/4) |
| Q3 — enforcement scope | **mutating-only + allowlist** (4/4), contingent on F1+F4 |
| Q4 — probe outage | **fail OPEN + alert** (4/4), via F4 evaluator |
| Q5 — late false-positives | **confirm cron excludes leave/weekend/holiday BEFORE gating** (4/4) — blocking |
| Q6 — deadline button | **acknowledge + re-surface at deadline−1day** (4/4) |

### The one place the panel split

Q1 is the only real fork: the whole panel wants **by-receiver in v1**, but that's the
one item with real new cost (carrying `team_member_email` from
`whatsapp_message_context` through `whatsapp_adapter.py` into the intake row, then
filtering the queue by it). The spec's original "assigned_to v1 + fast-follow" was the
cheap path; the panel says cheap-path v1 doesn't deliver what was approved. **This is the
single decision to put to Antonello.**
