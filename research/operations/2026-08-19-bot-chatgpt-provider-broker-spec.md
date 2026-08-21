---
date: 2026-08-19
domain: operations
client_case: zantara-wa-provider
discovered_by: "Fable session (M5), on Zero's 2026-08-19 order («gia fatto, quindi passiamo a chatgpt»); v3 after four adversarial rounds of the 3-seat panel"
sources:
  - "memory: decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15 (owner ruling + 2026-08-18 riconferma + 2026-08-19 privacy-gate attestation and transition order)"
  - "research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md on origin/main (Stage 1 acceptance matrix §4, gates §3.5-3.6, blocked list §6)"
  - "research/operations/2026-08-15-bot-provider-failure-matrix.md on origin/main (selected-provider failure rows; quota class UNMEASURED)"
  - "research/operations/2026-08-15-bot-openai-provider-threat-model.md + privacy plan on origin/main (R28 corrections; privacy plan gates 1-4 before any real client text)"
  - "apps/backend-rag/backend/services/integrations/wa_outbox_worker.py on origin/main (claim/fence/reclaim :531-584, coalescing :449-455, latest-message invariant :437-441, 24h check :957-991, residual double-send :1072-1083)"
  - "apps/backend-rag/backend/services/integrations/wa_inbox_bot.py on origin/main (RAG hop :538, internal-key :360-368, abstain stub since 2026-08-11 :487-493, text-level checks :131/:610/:647/:668)"
  - "migrations_v2/206_wa_meta_inbox.sql on origin/main (status CHECK constraint :78-79 — pending/generating/claimed/done/failed only)"
  - "apps/backend-rag/backend/llm/codex_exec_client.py on origin/main (stdin-only, --ephemeral --ignore-rules, sanitized taxonomy, stderr rules, no internal semaphore)"
  - "Pro seat identity measured 2026-08-19: codex-cli 0.147.0, `Logged in using ChatGPT`, account antonellosiano@gmail.com (email field only, auth file never dumped)"
  - "Panel reviews executed 2026-08-19, four rounds: v1 → Codex GPT-5.6 red-team BLOCKED (22) · Kimi K3 FIX-FIRST (10, code-verified) · Gemini via agy SHIP (5 improvements); v2 → Codex BLOCKED (5 NEW) · Kimi FIX-FIRST (3 new, 10/10 v1 RESOLVED); v3 → Codex FIX-FIRST (4 asks) · Kimi FIX-FIRST (2 new, 3/3 RESOLVED) + fresh-context Sonnet proofread; confirmation micro-round on the folded additions → Codex SHIP (4/4 SATISFIED), Kimi verdict recorded in §8. Full outputs in session scratchpad; dispositions in §8"
adversarial_review: kimi-k3
review_corroboration: "codex-gpt-5.6 red-team (BLOCKED v1/v2 → FIX-FIRST v3 → SHIP after confirmation micro-round), gemini-3.1-pro constructive (SHIP)"
---

# BOT-V4 v3 — ChatGPT-provider broker for the Zantara WA bot (panel-revised)

> **v1 → v2 → v3.** Spec v1 proposed the pull-broker and was reviewed by three cross-family
> seats: Codex red-team **BLOCKED**, Kimi K3 **FIX-FIRST** (both grounded in file:line reads of
> the live code), agy **SHIP** with improvements. The panel agreed the pull-model core is sound
> and agreed on where v1 declared closed what was open: gate re-application, the state machine,
> coalescing/ordering, injection/exfiltration, the privacy ladder, latency math, and S3
> statistics. v2 rewrote the design around those findings; two further re-review rounds plus a
> fresh-context proofread drove v3. §8 dispositions every item of every round, ending in
> Codex SHIP on the confirmation micro-round.

## 0. Authority and scope

Zero's 2026-08-19 order («già fatto, quindi passiamo a chatgpt»), recorded in the owner-ruling
memory before v1 was written:

1. **Privacy toggle attested OFF by owner** for the seat `codex login status` authenticates on
   Pro (measured: **antonellosiano@gmail.com**, codex-cli 0.147.0). Attestation, not machine
   verification — and per the privacy plan it covers ONE of the required controls: the
   Codex-specific data controls are partly separate and still need live verification (§6, G-P1).
2. **New owner mandate**: shadow-first wiring (flag-OFF code) is in scope, including the business
   decision to route client WhatsApp text through the ChatGPT Pro subscription once the
   technical/privacy gates of §6 are green. The ToS residual was accepted 2026-08-15.
3. **Nothing flips today.** Serving stays on Gemini until the §6 ladder is green and the owner
   presses the S4 switch. Every stage must be reversible; §5 states exactly what is config-only
   and what is not (v1's blanket "config-only at every stage" was refuted — Kimi F7, Codex 21).

Out of scope: deleting/reviving `openai_responses_client.py`; changes to the abstain-policy SSOT
values; any paid API key; replacing Path B with an OpenClaw-style channel brain.

## 1. Constraints (measured; unchanged from v1 except C10-C12 added by the panel)

| # | Constraint | Source |
| --- | --- | --- |
| C1 | Fly is not a Codex host; no CLI/credential there | shadow plan §1.6 |
| C2 | Seat lives on Pro; non-login processes need `/opt/homebrew/bin` in PATH (Node shebang) | #4322 |
| C3 | Fly→Pro inbound does not exist; Pro→Fly HTTPS is established | wa_inbox_bot.py |
| C4 | `CodexExecClient` is text-in/text-out; no native tools/system channel | shadow plan §1.5 |
| C5 | Client text never on argv/env; stdin only; `--ephemeral --ignore-rules`; empty cwd; sanitized errors; raw stderr never persisted | adapter |
| C6 | Abstain gates are the product and stay SSOT on Fly — **and several gates read the ANSWER TEXT, so they can only run after the text exists** (Kimi F1) | reasoning.py, wa_inbox_bot.py |
| C7 | All DB writes stay in Fly backend code | CLAUDE.md §10 |
| C8 | Ambiguous seat-wide failure stops the lane and pages; never rotate accounts. **Quota/usage-window is an UNMEASURED class today — it MUST get its own classifier before C8 can distinguish throttling from seat death** (Kimi R3) | failure matrix |
| C9 | PricingTool only, one all-inclusive price — enforced by grounding IN the package plus the quotable-relevance veto run on the RETURNED text at finalization | corner §5 |
| C10 | `codex exec --sandbox read-only` blocks writes, NOT reads: an adversarial WA message could steer the coding agent to read host files into the answer. The broker host identity must own nothing worth stealing except its own seat credential (Codex CR2, Kimi F5) | threat model R28 |
| C11 | `wa_outbox` status CHECK admits only `pending/generating/claimed/done/failed`; the reclaimer cleans only `claimed|generating`; coalescing sees only `pending`. **No new row states.** (Kimi F2/F3, Codex CR4) | migration 206, worker |
| C12 | The worker holds a per-thread advisory lock across generation+send; ordering and coalescing semantics depend on it — the broker leg must run UNDER that lock, not around it (Codex CR4) | wa_outbox_worker.py |

## 2. Architecture — synchronous broker leg inside the existing claim (v2 core, v3-hardened)

The single biggest v2 change: **the outbox row never leaves the existing state machine.** The
worker claims the row exactly as today (`status=claimed`, thread advisory lock held, lease
heartbeat running) and keeps ownership for the whole generation. The broker is a *generation
subcontractor* reached through a separate `broker_jobs` table — `wa_outbox` gains no new status,
the reclaimer/coalescing/fence/24h logic is untouched by construction.

```
┌────────────────────────────  Fly (nuzantara-rag)  ─────────────────────────────┐
│ wa_outbox_worker claims row (status=claimed, thread lock held, heartbeat)      │
│   route = codex? (flag WA_GENERATION_PROVIDER=codex ∧ breaker CLOSED ∧         │
│                   queue admission OK ∧ 24h-window margin OK)                   │
│     yes → build CONTEXT PACKAGE (deterministic retrieval, §2.2) →              │
│           ONE TRANSACTION, fenced on the row's claim (Codex NEW-2):            │
│             UPDATE wa_outbox SET generation_route='codex'                      │
│               WHERE id=$row AND status='claimed' AND lease fence holds;        │
│             INSERT broker_jobs(job_id, mode='serve', package,                  │
│               evidence_inputs, package_hash, thread_epoch, deadline_at,        │
│               state='offered')  — atomic: no crash window between marker       │
│               and job in either direction                                      │
│           → wait ≤ T_exec (async, lock held) on job state                      │
│         ├ state='completed_pending_consume' → FINALIZATION PIPELINE (§2.3)     │
│         │   on returned text; consume CASes job → 'consumed' + payload NULL    │
│         │     → send / typed outcome per §2.3 (TEXT_DEFECT → Gemini leg;       │
│         │       POLICY verdicts → their existing terminal handling, never      │
│         │       another LLM call)                                              │
│         └ deadline_at reached → CAS state='expired' → Gemini leg, same claim   │
│     no  → Gemini leg (today's path, unchanged)                                 │
│                                                                                │
│ POST /api/wa-broker/claim     (X-WA-Broker-Key, dedicated)                     │
│   CAS offered→leased (fence_token, lease TTL); returns package                 │
│ POST /api/wa-broker/complete  (X-WA-Broker-Key)                                │
│   CAS leased→completed_pending_consume WHERE job_id+fence_token+state='leased' │
│   ∧ now<deadline_at; else 410 no-op. Idempotent: same completion_key           │
│   re-POST → same 200; conflicting text for a completed job → 409, never       │
│   a new generation. (Codex H5/H6)                                              │
└──────────────────────────────────▲─────────────────────────────────────────────┘
                                   │ outbound HTTPS only
┌──────────────────────────────────┴────────────────────────────────────────────┐
│ Pro, dedicated OS user `zantara-codex` (§4): wa_codex_broker launchagent      │
│   poll claim → CodexExecClient.generate(package via stdin,                    │
│     timeout = server_now-anchored budget on a monotonic timer (§2.1),         │
│     kill process group on expiry)                                             │
│   → complete. Single-flight. Own CODEX_HOME, own seat login, no repos,        │
│   no SSH keys, no fleet secrets. Seat sentinel cron (§4.4).                   │
└───────────────────────────────────────────────────────────────────────────────┘
```

Properties this buys, each previously refuted in v1:

- **No new `wa_outbox` states** (C11): `broker_jobs` is a new table with its own CHECK and its
  own reaper; a dead broker means jobs expire and rows fall to Gemini inside the same claim.
- **`broker_jobs` has a data lifecycle of its own** (Codex NEW-1 — the job row carries client
  text, so it is a PII surface, not plumbing). The `result_text` handoff is a NAMED protocol
  (Codex r3): `/complete` CASes the job to **`completed_pending_consume`** — a NON-terminal
  state that holds `result_text` under the fence — and the worker's finalization (or shadow-sink
  copy) is the single consumer, whose consume step CASes to terminal **`consumed`** and NULLs
  `package`/`evidence_inputs`/`result_text` in that same transaction; the reaper expires a stale
  `completed_pending_consume` (worker died before consuming) to terminal with the same NULLing
  and a typed outcome. Every path to a terminal state NULLs all payload columns atomically;
  terminal rows keep only ids, hashes, timestamps and typed outcome for observability, and a
  purge job deletes them after 7 days — with the purge VERIFIED (post-TTL count asserted zero,
  alarmed if not; a purge that silently stops is scar family #2).
  Read access via the worker's role only. Content class note: the payload is derived from text
  already resident in this same Postgres (conversation store) — the table adds aggregation and a
  second copy, not a new custodian; minimization + verified TTL is the control, matching how the
  originating tables are governed.
- **Offer admission is DB-atomic** (Codex H12): the offering transaction itself enforces
  `count(state IN ('offered','leased')) < max_depth` (single-row depth counter or advisory
  lock — an implementation detail S2 picks, the atomicity is not optional). Two Fly workers
  reading the same stale heartbeat cannot double-offer past the cap, and the single-flight
  broker never sees a queue deeper than what admission promised.
- **Coalescing/ordering unchanged** (Kimi F3, Codex CR4): the thread lock is held for the whole
  leg; a new inbound during the broker wait behaves exactly as it does during a slow Gemini
  generation today. The latest-message invariant is re-checked by the worker at finalization
  time (thread_epoch in the job; a moved thread ⇒ discard the completion and follow §2.3's
  by-class drift handling — never a fresh generation triggered by the discard itself).
- **Double answer structurally excluded at this layer**: only the worker sends, once per row,
  as today. A late `complete` after expiry is a 410 no-op (CAS). **The broker adds ZERO new send
  paths — that is the invariant this spec can honestly claim.** The pre-existing residual
  double-send window at the Graph-send boundary (worker :1072-1083) is NOT widened and NOT
  claimed fixed here; "≤1 external send per row" is therefore NOT asserted as an absolute
  end-to-end property anywhere in this spec (Codex H10 — pre-existing, tracked outside).
- **Retry budget** (Codex H8/H9): the broker leg runs at most ONCE per row (first generation
  attempt only, recorded in `wa_outbox.generation_route` — one new nullable column, additive);
  fail-off consumes no `attempts`; all subsequent attempts are pure Gemini. Hard cap: one codex
  generation + the existing Gemini ladder per row, never codex-per-attempt. **A completion
  discarded for thread-epoch drift (§2.3) COUNTS as the row's one codex leg** — `generation_route`
  is set at offer time, not at acceptance, so the post-discard handling is exactly today's
  post-generation fence-fail path and any regeneration is Gemini. On chatty threads this spends
  at most one codex call per superseded row, never a second (Kimi v2-1).

### 2.1 Deadline, breaker, admission (agy I1, Codex H11/H12, Kimi F8)

- `T_exec` default **15s** (claim-wait ≤3s + exec ≤12s), config `WA_BROKER_DEADLINE_S`. The
  subprocess timeout on Pro is derived from `deadline_at`, never a fixed 60s (Codex H7) — and
  **never from Pro's wall clock** (Kimi N2): the `/claim` response includes `server_now`, the
  broker takes `budget = deadline_at - server_now - net_margin` once at claim and counts it
  down on its own MONOTONIC timer, so cross-machine clock skew can neither kill early nor let
  a subprocess outlive the fence.
- **Circuit breaker on Fly**: 3 consecutive expiries/typed failures → OPEN 5 min (rows route
  straight to Gemini with zero added latency); half-open canary closes it. Breaker state is a
  gauge in the ledger, not just behavior.
- **Admission control**: the heartbeat channel is the `claim` poll itself — no new endpoint.
  Every `/claim` request (including ones that find no job) carries the broker's `queue_state`
  (in-flight count, last exec duration); Fly persists `broker_last_seen_at` + depth on the job
  table's side and the worker offers a job only if that stored gauge predicts a start within
  budget; a stale `broker_last_seen_at` (> 2× poll interval) reads as "broker absent" → direct
  Gemini. No head-of-line tax (Codex H12; mechanism pinned per Kimi v2-2).
- **24h-window margin**: if the Meta window expires within `2×T_exec`, skip the broker leg —
  the +15s must never turn a sendable row into `24h_window_closed` (Kimi F8).
- **Latency SLO is an equation with registered numbers, not a vibe** (Codex H11): the end-to-end
  budget is `queue_wait + retrieval + [offer + claim_wait + exec | T_exec on expiry] +
  finalization + graph_send`, and S3a MUST measure its p50/p95/p99 on the full broker path and
  register an SLO before S3c — starting anchor: codex-route p95 ≤ the live Gemini path's
  measured p95 (corner: 33-94s spread, 74.6s median on synthetic probes), with the fail-off
  worst case adding ≤ `T_exec+1s` over the pure-Gemini figure. If the measured math doesn't
  close, T_exec shrinks or admission tightens — the SLO does not stretch.
- **Seat budget models the real quota window** (Codex H14): S1.5's deliverable includes the
  measured window SHAPE (rolling window length, burst behavior, throttle signature), and the
  broker's budget is a token bucket sized from that measurement — not a naive daily counter.
  Reserved interactive headroom for the owner is part of the same bucket config.

### 2.2 Context package — deterministic retrieval, allowlist schema

For the codex route the package is built by a **deterministic pipeline**: intent/domain gate →
domain→collection map (mandatory collections; hybrid dense+sparse search) → curated-QA injection
→ PricingTool resolution when the pricing intent fires → 12-turn history. No LLM planner in the
codex path — this is what CAN make the route Gemini-free (the depletion-resilience goal), and it
implements the direction the 2026-08-11 research already recommended against the nondeterministic
LLM collection gate. **The Gemini-free property is CONDITIONAL until S2 proves it** (Kimi v2-3):
S2 carries the acceptance criterion "the codex-route package builder invokes zero LLMs" as a
test, and an intent the deterministic gate cannot classify routes the whole row to the Gemini
leg rather than borrowing an LLM planner into the codex path. If S2 cannot satisfy the criterion,
the depletion-resilience claim is downgraded and this spec re-reviewed — decided then, not
asserted now. The Gemini path keeps its agentic loop unchanged.

Package hygiene (Codex M22, CR1): **allowlist schema per field** (`history[]`, `chunks[]`,
`pricing_block`, `persona_digest`, `evidence_inputs`, `thread_epoch`, `package_hash`) — nothing
else serializes. No phone, no `wa:` subject, no CRM fields, no source paths. Client free text IS
present by necessity — its protections are §4 (host isolation) and §6 (the DLP gate that must be
green before any real text flows).

### 2.3 Finalization pipeline — one function, both providers (Kimi F1, Codex H15/H16)

A single `finalize_wa_answer(text, package, evidence)` used by BOTH legs, extracted from the
current `wa_inbox_bot` post-generation sequence, in this order: monologue-leak strip →
KG-scaffold strip → `[ESCALATE]` handling → workflow-only check → quotable-relevance/pricing
veto against the package's PricingTool block → label/abstain gate on evidence (SSOT thresholds)
→ `_abstain_answer_worth_sending` → **host-secret egress scan (§4.3, codex leg only)** →
channel formatting → send-or-stub + human-notify. The evidence inputs are frozen in the job row
(`package_hash`); at finalization the worker verifies `thread_epoch` unchanged — and drift is
handled BY CLASS, never by blanket regeneration (Codex H15 + NEW-4): **human takeover /
`handling_version` change → discard the completion and STAND DOWN** (the automation stops, as
the worker's existing human-takeover guard already does — no regeneration, no send);
**newer-inbound drift → discard, and the newer message's own row answers** (this row follows
today's superseded semantics). The discard itself never triggers a fresh generation, and per §2
the discarded codex leg was the row's only one.

Finalization outcomes are TYPED (Codex NEW-5): **TEXT_DEFECT** (monologue leak, secret-scan
hit, malformed/oversized output) → fail-off to the Gemini leg within the same claim — a
different generator can legitimately cure a defective text. **POLICY verdicts** (label/abstain
gate, workflow-only, `[ESCALATE]`, not-worth-sending) → the existing terminal handling for that
verdict (stub, escalate, human notify) exactly as on the Gemini path — never converted into
another LLM call, because the verdict derives from the frozen evidence and would be identical
regardless of which provider wrote the text.

The refuted v1 sentence "the broker cannot ship an answer the gates would refuse" becomes true
only through this section: the gates run ON the returned text, in the same process that sends.

## 3. Phases

| Phase | Content | Gate | Reversal |
| --- | --- | --- | --- |
| S0 | Mandate + attestation recorded | done 2026-08-19 | n/a |
| S1 | Stage-1 offline eval on Pro (synthetic corpus, pre-registered rubric — registration doc in this lane) | shadow plan §4 matrix, all rows | offline |
| S1.5 | **Quota/usage-window measurement** with owner-authorized budget: scripted burst battery through the real seat, capture the actual throttle strings → dedicated `CodexQuotaError` class (closes the UNMEASURED row; without it C8 pages on routine throttling — Kimi R3) | classifier merged + measured capacity model (calls/min, burst behavior) | offline |
| S2 | Build flag-OFF: `broker_jobs` migration (additive table + one nullable `wa_outbox.generation_route` column), 2 endpoints, worker broker-leg, finalization extraction, broker daemon, dedicated-user provisioning script, tests (fail-off branch DRIVEN in tests — W101/W116 class; chaos rows of §7) | CI + cross-family diff review; Codex re-verdict required (it BLOCKED v1) | flag absent; migration is additive-only (drop = one down-migration; NOT config — stated honestly, Codex 21) |
| S3a | **Synthetic live shadow**: replay the S1 fixture set through the full Fly→Pro→OpenAI path (`WA_CODEX_SHADOW=synthetic`); proves plumbing, capacity, breaker, egress scan — zero client text | pre-registered pass set: 0 fence violations, 0 double-completions, p90 exec ≤ 12s, breaker/expiry behavior observed | flag off |
| S3b | **Real-text preconditions** (§6 ladder) — nothing flows yet | every §6 gate green, each with its named artifact | n/a |
| S3c | **Real-traffic shadow** (`WA_CODEX_SHADOW=real`): shadow jobs are **`mode='shadow'` and fully decoupled from the serving lifecycle** (Codex NEW-3) — the Gemini path serves exactly as today (lock held only for its own generation+send, zero added wait); AFTER the serving outcome is finalized the worker inserts a shadow job carrying the same frozen package + outcome snapshot; **cohort enrollment is DURABLE** (Codex r3-H20): a denominator record (thread_id, message_id, epoch, unique key) is written in the SAME transaction that records the serving outcome — before any shadow generation — and a reconciler compares denominator rows against shadow results so a crash between serving outcome and shadow completion is COUNTED as a missing observation, never silently censored; shadow completions are copied by the worker into the G-P4 sink — **a SEPARATE analysis table, not `broker_jobs`**: the `broker_jobs` row is transport only and follows §2's lifecycle (payload NULLed at terminal, row purged at 7d), while the sink row holds the comparison record under G-P4's own TTL ≤ 14d — never touch `wa_outbox`, have no serving-deadline coupling and no fail-off — but they are NOT exempt from a terminal state (Kimi N1): every shadow job carries its own generous `expires_at` (fixed TTL, hours-scale) and the same reaper CASes it to `expired` with the same payload-NULL-at-terminal, so a backlogged broker can never leave shadow payloads un-NULLed and un-purged. **Every processed turn is recorded — answered, abstained, failed, timed out** — sampling only answered turns is forbidden (Codex H20) | statistical criteria pre-registered BEFORE enabling (N, strata, primary metrics, non-inferiority margin, stop rules — frozen in a dated registration doc, same discipline as Stage 1's) | flag off; sink TTL + deletion runbook |
| S4 | Cutover: owner flips `WA_GENERATION_PROVIDER=codex`; Gemini becomes fail-off | owner's hand (Legge 5) after S3c review | flag back (genuinely config-only at this stage) |

S1 and S1.5 can run while S2 is built; S1's golden packages become S2's CI fixtures (agy I4).

## 4. Pro-side isolation and seat protection

### 4.1 Dedicated OS identity (Codex CR2, Kimi F5)
The broker and every codex subprocess run as a new login-less user **`zantara-codex`** on Pro:
own `$HOME`, own `CODEX_HOME`, seat authenticated once by the operator (`codex login` as that
user — one-time GUI/device action, §Solo-operatore), no SSH keys, no repo checkouts, no fleet
secrets, no Keychain items beyond its own. The only secret it holds is its own seat credential —
which is the one thing the process cannot function without. Blast radius of a successful
injection-read: its own auth file. Which leads to:

### 4.2 The residual the owner must re-accept — now a NAMED GATE, with its blast radius bounded
Even in 4.1's cage, an adversarial message can in principle steer the agent to read **its own**
`auth.json` and emit it — and the §4.3 scans are pattern/canary-based, which a sophisticated
encoder can in principle defeat (fragmentation, encoding, paraphrase). This spec does not
pretend otherwise. What bounds the loss: the credential is ONE ChatGPT seat token,
**rotatable by re-login**, held by a user that owns nothing else — no client data beyond the
package the attacker already controls as its sender, no fleet secrets, no repos. Acceptance of
this bounded residual is **gate G-P6** in §6 (owner, recorded with the bound stated) — a
decision with a name and a date, not a paragraph someone once read (Codex CR2).

### 4.3 Egress secret scan + canaries (Codex CR2/H17, Kimi F5)
`finalize_wa_answer` on the codex leg scans the returned text for secret-shaped content
(key/token patterns, PEM/OpenSSH headers, `auth.json` fragments, JWT shapes) and for **canary
tokens** planted in the `zantara-codex` environment precisely to be leak tripwires — any hit:
drop text, fail to Gemini, P0 alert. Canary leak tests are part of S3a's pass set. Crash/core
capture disabled for the broker; bounded stdin/stdout sizes; the spool carries job ids and typed
outcomes, never text.

**The persistence property is claimed over ENUMERATED paths, not the universe** (Codex H17,
narrowed honestly at round 3): the property this spec asserts is "no prompt/answer persistence
in the paths the `zantara-codex` identity controls" — its home (CODEX_HOME, caches, logs,
session stores), the per-job TMPDIR (created per job, wiped after), and the system temp dirs
writable by that user, all ENUMERATED in the S2 test and swept for a unique canary embedded in
a synthetic exec; pass = zero hits outside the wiped tmpdir. Channels outside that user's
control (unified logging, kernel crash artifacts) are addressed by configuration where
disable-able and EXCLUDED from the claim where not — stated, not silently absorbed. The sweep
verifies `--ephemeral` does what its name claims instead of trusting it; it runs in S2 tooling
on Pro and re-runs in S3a's pass set.

### 4.4 Seat sentinel and quota (Codex H14)
Cron probe as `zantara-codex` (login status + 1-token synthetic exec, its consumption attributed
in the ledger), Telegram on death; `CodexQuotaError` (from S1.5) is DISTINCT from auth-death —
quota trips the breaker with a timed reopen, auth-death stops the lane and pages (C8). A global
per-day call budget for the broker — a SECONDARY hard ceiling alongside §2.1's window-shaped
token bucket, never its substitute — is config-set from S1.5's measured capacity and reserves
headroom for the owner's own interactive use of the seat.

## 5. Rollback truth table (replaces v1's refuted blanket claim)

| Stage | Reversal | Config-only? |
| --- | --- | --- |
| S2 code | flag absent/off | functional-off: yes. Schema removal: NO — a down-migration (additive objects, no data loss). Stated split, not blurred (Codex M21) |
| S3a | `WA_CODEX_SHADOW` off | yes |
| S3c | flag off; **accumulated sink is PII that survives the flag** → TTL ≤ 14d + deletion runbook + access limited to the worker role; reversal includes running the deletion | no — flag + data hygiene |
| S4 | `WA_GENERATION_PROVIDER=gemini` | yes |
| Dormant endpoints | exist regardless of flags; dedicated key + per-endpoint scope + rate limit is the standing control | n/a |

## 6. Real-text gate ladder (G-P*) — all green before S3c (Kimi F4, Codex CR1/H18)

| Gate | Artifact that proves it | Owner |
| --- | --- | --- |
| G-P1 | Live verification of ChatGPT **and Codex-specific** data-control settings on the seat, dated, re-checked at S4 | operator[gui] + session record |
| G-P2 | UU PDP / Art. 56 basis artifact: consent/disclosure path for routing client chat text to OpenAI (the existing PENDING-ARMS cloud-text gap, now decided for this provider by the owner — the artifact documents basis + revoca path, it does not re-litigate the decision) | Zero (business/legal) — §Solo-operatore |
| G-P3 | **A named DLP policy, not just the allowlist** (Codex CR1): detection categories enumerated (NIK/KTP, passport number, NPWP, phone, email, bank/account numbers, credential shapes) over ALL free-text fields (`text`, `history[]`, `chunks[]`), each with its transformation (placeholder substitution; any reversal map never leaves Fly), **fail-closed on detector error** (package not built → row routes to Gemini), and a measured recall test on a synthetic PII corpus with a registered floor. Egress scan armed (S3a-proven) | session, artifact reviewed cross-family |
| G-P4 | Shadow sink design (Codex H18): a Postgres table in the existing Fly DB (no new custodian — its content class already resides in the conversation store there), minimized columns, worker-role-only access, no export path, TTL ≤ 14d enforced by a purge job whose effect is VERIFIED (post-TTL count asserted zero, alarmed otherwise), deletion runbook covering early teardown | session, reviewed |
| G-P5 | S1.5 quota classifier + capacity model merged | session |
| G-P6 | Owner's recorded acceptance of the §4.2 bounded residual (seat-credential exfiltration past pattern/canary scans), with the bound as stated there — **and the bound itself VERIFIED, not assumed** (Codex r3): the gate's artifact includes a measured inventory of what a stolen `auth.json` can actually reach (scopes/surfaces probed, not presumed seat-only) and a revocation test — re-login performed, the pre-rotation token probed DEAD afterwards. If either probe widens the bound, the acceptance is re-put to the owner with the wider bound | Zero — §Solo-operatore (probes: session) |

## 7. Chaos/soak rows S2 tests must drive (Codex H19 — subset, each an invariant test)

Pro reboot mid-lease · Fly deploy mid-wait · lost `complete` HTTP response (idempotent re-POST)
· duplicate claim race · `kill -9` broker mid-exec (process-group reap, job expiry) · clock skew
between claim and deadline CAS · oversized package/answer (bounded, typed error) · CLI
auto-update changing argv behavior (version pin check in the daemon) · mixed-version deploy
(old worker + new endpoints and vice versa — additive schema makes both directions read-safe).
Invariants: ≤1 accepted generation per job; the worker INITIATES ≤1 send per row (the
pre-existing Graph ack window stays outside this spec's claim — §2); fail-off within SLO.
**S2's deliverable is the full per-case table** — initial state, fault point, expected final
state, max time-to-converge for every row above (Codex H19); the list here scopes it, the
table proves it.

## 8. Panel dispositions (v1 → v2 → v3)

- **Codex CR1 (PII boundary)** → §6 ladder; real text gated on G-P1..P5. **CR2 (injection
  read)** → §4.1-4.3. **CR3 (substitution point undefined)** → §2.2: deterministic
  retrieve→package→synthesize interface; codex replaces the whole generation for its route,
  Gemini loop untouched on its own route. **CR4 (locks/coalescing)** → §2: broker leg inside
  the held claim+lock; no parked states. **H5/H6 (fence/idempotency)** → §2 CAS + completion_key.
  **H7 (timeout)** → §2.1 derived timeout + process-group kill. **H8/H9 (retry semantics)** →
  §2 one-codex-per-row rule + `generation_route` column. **H10 (Graph double-send)** → explicitly
  out of scope, pre-existing, tracked — the spec now claims only "zero new send paths", never
  an absolute ≤1-send invariant (§2, §7). **H11/H12 (latency/HOL)** → §2.1 breaker + DB-atomic
  admission + T=15s + registered SLO equation. **H13 (key)** → dedicated `X-WA-Broker-Key`,
  per-endpoint scope, constant-time compare, rate limit (also Kimi F6 — decided, not deferred).
  **H14 (seat)** → §4.4 + §2.1 token bucket sized on the measured window shape. **H15 (stale
  gates)** → §2.3 drift handled by class (takeover → stand down; superseded → superseded row
  answers). **H16 (finalization coverage)** → §2.3 single pipeline with typed outcomes.
  **H17 (no-disk not proven)** → §4.3 canary filesystem sweep, run in S2 and S3a.
  **H18 (S3 PII store)** → G-P4 concretized + §5 row. **H19 (distributed failures)** → §7 +
  S2 per-case table deliverable. **H20 (S3
  statistics)** → S3c pre-registration rule. **M21 (rollback)** → §5 truth table. **M22
  (blacklist→allowlist)** → §2.2.
- **Kimi F1** → §2.3 (gates on returned text; C6 amended). **F2** → §2 (no new states;
  `broker_jobs`). **F3** → §2 (lock held; epoch check). **F4** → §6. **F5** → §4. **F6** →
  dedicated key decided. **F7** → §5. **F8** → §2.1 window-margin guard. **F9** → citations
  re-anchored to `wa_inbox_bot.py:487-598` (the 2026-08-11 abstain-stub rework) instead of
  unresolvable PR shorthand. **F10** → fence semantics now live entirely in `broker_jobs`.
- **agy I1-I5** → §2.1 (split lease, breaker), S3a/S3c (bootstrap + pre-registered matrix),
  ledger/counters (§4.4 + observability fields in `broker_jobs`: `outcome`, `error_class`
  incl. QUOTA, latency split claim/exec/network, breaker gauge), §3 (S1 golden packages as S2
  fixtures), §2.2/§4 (dedicated key, TOCTOU via epoch+hash, subprocess quarantine).
- **Kimi re-review of v2** (2026-08-19): all 10 v1 findings RESOLVED, none reopened; 3 new
  narrow defects, each folded back in the section it names — **v2-1** epoch-drift discard counts
  as the row's one codex leg (§2 retry-budget bullet), **v2-2** admission heartbeat pinned to
  the `/claim` poll itself with a staleness rule (§2.1), **v2-3** "Gemini-free" made conditional
  on an S2 zero-LLM acceptance test with a named downgrade path (§2.2).
- **Codex re-review of v2** (2026-08-19, verdict BLOCKED on v2 — this v3 pass is its
  disposition): 12/22 RESOLVED (incl. CR3 substitution point and CR4 locks/coalescing),
  1 UNRESOLVED (H10 — answered by retracting the absolute invariant, see above), 9 PARTIALLY —
  each strengthened where its row above now says so (CR1 → G-P3 named DLP policy; CR2 → §4.2
  named gate G-P6 + bounded blast radius; H11 SLO equation; H12 DB-atomic admission; H14
  window-shaped budget; H17 canary sweep; H18 G-P4 concretized; H19 per-case table; H20
  all-outcomes recording; M21 honest S2 row). 5 NEW findings, all accepted: **NEW-1** →
  `broker_jobs` payload lifecycle (§2 bullet: NULL-at-terminal + verified 7d purge), **NEW-2** →
  route-marker + job insert in ONE fenced transaction (§2 diagram), **NEW-3** → S3c shadow jobs
  `mode='shadow'`, fully decoupled from the serving lifecycle (§3), **NEW-4** → drift handled by
  class, takeover = stand down (§2.3), **NEW-5** → typed finalization outcomes, POLICY verdicts
  never become another LLM call (§2.3).
- **Kimi round 3 on v3** (2026-08-19): v2-1/2/3 all RESOLVED; 2 new narrow findings, both
  folded in — **N1** shadow jobs get their own `expires_at` + the same payload-NULL-at-terminal
  (§3 S3c row), **N2** the broker's countdown runs on `server_now`-anchored budget + a
  monotonic timer, never Pro's wall clock (§2.1).
- **Codex round 3 on v3** (2026-08-19): **BLOCKED dissolved → FIX-FIRST.** 12 further items
  RESOLVED (CR1, H10-H12, H14, H18, H19, M21, NEW-2..5); 4 PARTIALLY, each with the exact
  sentence the spec had to add, all folded in this same pass — **r3-CR2** the credential bound
  is probed (scope inventory + revocation test) and re-put to the owner if wider (G-P6 row),
  **r3-H17** the no-persistence claim narrowed to enumerated controlled paths with out-of-control
  channels named and excluded (§4.3), **r3-H20** durable cohort enrollment: denominator record
  in the serving-outcome transaction + reconciler so censored observations are counted (§3 S3c),
  **r3-NEW-1** the `result_text` handoff protocol: `completed_pending_consume` → single consumer
  → `consumed` with atomic payload NULL, reaper covers a dead consumer (§2 bullet + diagram).
- **Confirmation micro-rounds on the folded additions** (2026-08-19): each seat was shown ONLY
  the spec text added in answer to its own residual findings — Codex: 4/4 SATISFIED (CR2, H17,
  H20, NEW-1), **VERDICT: SHIP**; Kimi: 2/2 SATISFIED (N1, N2), **VERDICT: SHIP**. Final panel
  state: agy SHIP · Codex SHIP · Kimi SHIP.
- **Fresh-context proofread of v3** (Sonnet, 2026-08-19): caught a real leftover — §2's
  coalescing bullet still said "regenerate fresh" after §2.3 had moved to by-class drift
  handling (the correction-leaves-a-stale-sibling class) — and the transport-vs-sink TTL
  ambiguity; both fixed (§2 bullet now defers to §2.3; §3 states the G-P4 sink is a separate
  table from `broker_jobs`, 14d vs 7d respectively).

## 9. What this spec still does not decide

- ~~S1 fixture thresholds~~ — REGISTERED 2026-08-19 in
  `research/operations/2026-08-19-bot-stage1-registration.md` (72 fixtures, SHA-256-frozen,
  6 categories, per-stratum thresholds, invalidation rules), same lane as this spec.
- S3c N/strata/thresholds (registered at S3b close, before enabling).
- The deterministic domain→collection map's exact contents (S2 design detail with its own
  tests; the Gemini path is the behavioral reference).
- Whether the second ChatGPT Pro seat ever joins (post-S3c data; C8 forbids silent rotation).

## Adversarial review

Seat: **Kimi K3** (declared token), corroborated by **Codex GPT-5.6 sol** red-team and
**Gemini 3.1 Pro** (agy) — four rounds total, every finding dispositioned in §8. Final
verdicts: Codex SHIP (after BLOCKED×2 → FIX-FIRST → confirmation micro-round 4/4 SATISFIED),
Kimi SHIP (after FIX-FIRST×3 → 2/2 SATISFIED), agy SHIP. ~40 findings raised across rounds;
**three objections survive by design rather than by fix**, each carried openly in the spec:

1. **The Graph-send ack window** (Codex H10): pre-existing, not widened, explicitly outside
   this spec's claims — the spec asserts only "zero new send paths" (§2, §7).
2. **The seat-credential exfiltration residual** (Codex CR2): bounded, probed, and owner-gated
   as G-P6 — accepted risk, not a solved one (§4.2).
3. **The Gemini-free depletion-resilience claim** (Kimi v2-3): CONDITIONAL on S2's zero-LLM
   package-builder test, with a named downgrade-and-re-review path (§2.2).

## §Solo-operatore

- One-time `codex login` as the `zantara-codex` user on Pro (device-code/GUI).
- G-P1 live verification of ChatGPT + Codex data-control settings (account GUI).
- G-P2 UU PDP basis artifact (business/legal).
- S4 cutover flip.
