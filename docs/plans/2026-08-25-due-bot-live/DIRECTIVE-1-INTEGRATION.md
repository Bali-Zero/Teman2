# Directive #1 — integration into the lane plan

Owner directive from Zero, 2026-08-25, verbatim copy at `DIRECTIVE-1-owner.md`.
It **amends** `MANDATE.md`. Where it contradicts F4 / F5 / F8 it wins; every other
frozen decision stands unchanged. This file is the orchestrator's integration —
what each change kills, who owns the consequence, and what is now v1.

## 1. What changed, and what each change kills

### 1.1 The team bot's brain (supersedes F8-primary)
Primary is **`qwen3.7-plus` via the TP1 Alibaba door**. Fallback chain, in order:
`qwen3.6-flash` → `glm-5.2` (both same door) → **a local Qwen on the Mini, read-only**,
answering R0 tools only and saying so. A slot is reserved for `qwen3.7-flash` via a
Model Studio key, which becomes primary only if Zero authorises it. The brain is
pluggable by flag/env.

**What this kills:** the local inference plant as the team bot's engine. F8 sized it as
the serving stack; it is now the *third lane of degradation* — one model, R0 tools, no
extended multilingual evals. Any design that assumed the local plant would carry the
team bot's full tool surface is void.

**Required, not optional:** depletion alarms at 30% and 10% of the token plan, and a
circuit breaker that degrades to read-only. Zero's words: *never a dead mute bot*. The
degradation must be **visible** — a bot that silently drops to read-only is worse than
one that refuses loudly, because the person keeps asking and never learns why.

**Two warnings carried in from the directive's own refuter, both load-bearing:** on TP1,
pin an explicit **version**, never an alias — deprecation churn is quarterly, and every
re-pin needs a smoke test. Read the exact slugs from a live `GET /models`; never deduce
one from a table. A table is a stale proxy for the live list, and this session has already
paid for that exact shape more than once.

### 1.2 Agentic scope (amends F4/F5)
One-tool-per-turn now binds **mutations only** — one mutation per turn, always confirmed.
Reads and searches chain freely, `MAX_STEPS` around 8, with a loop detector and a budget.
The autonomy grades are untouched: reads free · comms drafts → confirm · CRM writes →
confirm with preview · sends to the client → confirm · destructive never.

**The trap in this change.** B3 built single-call as a property of the *type* — two calls
are unrepresentable. That is the strongest form available and it must not be traded for a
validator that counts calls and raises. The relaxation has to stay structural: a read plan
that may carry a sequence, and a mutation decision that cannot represent more than one.
A construction that cannot lie beats a detector that tries to catch the lie.

The step budget and loop detector are **new guards**, so scar family #3 binds with no
exception: guilt *and* innocence tests. A detector that fires on a legitimate repeated read
— the same client looked up twice for two different practices — is exactly as broken as one
that misses a real loop.

### 1.3 Per-member memory (new requirement)
Three layers in the local state store (sqlite on Mini, replicated to Pro): profile,
episodic, learned patterns. A ~200-token **member card** injectedevery turn, automatic write
after each turn, `"forget X"` honoured. **The memory never reaches the cloud as a blob** —
only the card does.

**Two consequences the lanes must not each answer privately:**

- *"The memory survives failover"* makes this the **second consumer** of the gap B5
  documented in `ops/F6-F9-PENDING-ACTION-EPOCH-GAP.md`: state held outside the leader
  record, acted on under a stale epoch after a takeover. F6's pending actions were the
  first. A fix sized for one consumer is the wrong fix.
- The PII boundary is this feature's *central* constraint, not a footnote. Zero derogated
  for **processing** (documents with consent already collected); the Law 2 **output**
  frontier is unchanged. A per-member memory is literally a persistence layer for facts
  about clients, so every persisted row and every card must be expressible without
  cleartext names, numbers, passport/KTP/NPWP or chat content.

## 2. Lane impact map

| Lane | Was | Is now |
|---|---|---|
| **B3-amend** | F5 registry + single-call `ToolDecision` | Split the type: read chains multi-step, mutation stays structurally singular. Owns `MAX_STEPS`, loop detector, budget. **Blocking** — B4 and the engine consume this contract. |
| **B4-tp1** | Local inference plant | TP1 adapter is the bulk: HTTP client, error taxonomy, breaker, depletion probe. Local plant shrinks to the read-only third lane. |
| **B8-memory** | did not exist | Three-layer per-member memory, member card, `"forget X"`. New lane. |
| **B1b-engine** | one engine, four surfaces | Unchanged in purpose; its assumptions about the local plant and about tool-call shape both moved. |
| **B5-ingress** | F9 ingress + failover | Closed pending one test. Its gap doc now has two consumers, not one. |
| **B7** | control tower | Needs registry entries for the new kill switches: TP1 depletion, breaker state, per-domain flags, memory write, `MAX_STEPS`. |

## 3. What v1 now means (DoD amendment)

v1 was "the F5 tool set". Zero has widened it to **domains 1–4**, with
**documents-in-chat as a first-class citizen, not a stretch goal**:

1. Practices & CRM (the existing F5 set)
2. **Documents in chat** — photo/PDF on WhatsApp → local OCR (qwen2.5vl) → classify →
   attach to practice → update checklist → "missing: X"
3. Deadlines & compliance — KITAS/LKPM/SPT sweep for *my* clients, proactive reminders
4. Knowledge & pricing — via the `nuzantara-knowledge` MCP, **with citations, never from memory**

Domains 5–7 are v2, domain 8 (HR, in Bahasa) is v3. The Definition of Done therefore now
carries the team bot's domains 1–4 alongside "four client surfaces answering through ONE
engine in shadow". Everything still ships dark.

## 4. Open items for Zero — decision packet, not ledger lines

1. **The PII derogation needs one boundary sentence, stated once by Zero, not re-derived per
   lane.** Episodic memory has to resolve *"and for the other client?"*, which needs enough
   stored to disambiguate. `client_id` plus a practice reference is almost certainly
   sufficient and stays inside the Law 2 output frontier — but "almost certainly" is the
   orchestrator guessing at the owner's risk appetite. If a lane concludes a layer cannot do
   its job under the frontier, it reports rather than quietly relaxing it.
2. **The Model Studio key for `qwen3.7-flash`** (~$3.4/month) is a paid per-token API and
   needs explicit authorisation under the standing rule. The directive already gates it
   correctly ("enters when Zero authorises"). It becomes an **8th switchboard item** in
   `OWNER-DECISION-PACKET.md` rather than a thing a lane may arm.

## 5. What did not change

F1, F2, F3, F6, F7, F9, F10, F11 stand. Everything is still born **off**. The seven
switchboard items remain the only human tasks, and no lane may park work behind them.
The Anthropic-SDK ban, the secret-name-not-value rule, and generator≠grader on every unit
are untouched by this directive.
