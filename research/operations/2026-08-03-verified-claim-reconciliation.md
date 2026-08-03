---
date: 2026-08-03
domain: operations
client_case: none (internal engineering — megatopic 0 of the organism-wide R&D program)
sources:
  - Live web research via Codex GPT-5.6-sol (verified live search: Kubernetes controller docs, Temporal.io docs, Ragas, W3C PROV-O / Web Annotation)
  - Training-knowledge synthesis via Gemini 3.1 Pro (`agy`, no live search grounding confirmed — treat concepts as stable/well-established, not freshly-cited)
  - GLM 5.2 (`claude-glm`, z.ai endpoint) — final adversarial pass
  - Internal: 5-fork Gear-3 GROUND survey of the Nuzantara organism, 2026-08-03 (this session), which independently surfaced the 6 instances in §1
  - research/operations/2026-08-01-multi-session-multi-llm-strategies.md §4 (salvaged principle: "where a deterministic arbiter exists, the arbiter wins and the panel is redundant")
adversarial_review: codex+glm
adversarial_review_note: >-
  Sequential, not parallel: Codex GPT-5.6-sol (xhigh) red-teamed the first
  draft (a single universal "VCR" reconciler) and returned DO-NOT-SHIP with
  10 concrete conditions. Gemini 3.1 Pro was then given Codex's critique
  cold and asked to design a v2 satisfying all 10 conditions. GLM 5.2 then
  red-teamed Gemini's v2 against the same 10 conditions and returned SHIP
  WITH CHANGES (5 concrete fixes, applied below). See "Adversarial review"
  at the end for the full objection/outcome table.
---

# Verified Claim Reconciliation (VCR) — a family of fixes, not one universal cure

> **Status: pilot spec, post-council.** This document is the outcome of a
> 3-seat sequential review (Codex red-team → Gemini constructive rebuild →
> GLM refuter), not a first draft. The original "one universal reconciler"
> framing was explicitly rejected by the council and is NOT what this spec
> proposes — see §1.

## 1. The disease, restated precisely (and reframed per the council)

A Gear-3 GROUND survey of 5 independent anatomical areas of the Nuzantara
organism (infra/ops, product verticals, bot+intake, WR2 editorial, the LLM
arsenal itself) found the same STRUCTURAL PATTERN recurring, discovered
independently by 5 separate forks that never saw each other's output: **a
system treats a proxy signal as if it were the thing itself, without a
fresh, independently-observed check that the proxy still tracks reality.**

Six concrete instances, already measured on disk (not hypothetical):

| # | System | The proxy trusted | The reality it stopped tracking |
|---|---|---|---|
| 1 | `PENDING-ARMS.md` ledger | A hand-written status line ("dead", "open") | 3 Codex seats marked dead were alive; resolved items stayed marked open |
| 2 | LLM fleet health (`arsenal_probe.py` → `last.json`) | A cached probe result, read by any later consumer | GLM PONG'd alive this session while the cached report said `UNKNOWN_ERR` 77h old — context-dependent (interactive vs SSH Keychain unlock), read as absolute |
| 3 | E33 Second Home Day-90 monitor | Cron exit code 0, every day | Nobody ever writes to `e33_cases` — the cron has nothing to monitor and never did |
| 4 | Zantara WA bot evidence score | `tool_call succeeded` → confidence fixed at 0.85 | Whether the tool's returned data was actually relevant to the answer |
| 5 | KBLI Navigator content (1,559 codes) | The presence of a published verdict | 1,544/1,559 (99%) assert a foreign-ownership % with no citable regulatory source |
| 6 | WR2 editorial fact-checker | "Consistent with the brief" | The brief was written by the SAME composer being checked — `research_json` is never populated in production |

**Correction from the council (Codex, upheld by GLM):** the first draft of
this spec argued these 6 instances share ONE disease and therefore need ONE
universal reconciler. **That argument does not survive review.** The
*shape* of the mistake repeats (proxy trusted over primary source), but the
*mechanism* of failure differs materially per instance — a stale hand
projection (#1), a context-collapsed cache (#2), a monitor with no
population (#3), a miscalibrated surrogate metric (#4), absent editorial
governance (#5), and circular verification with contaminated evidence
selection (#6) are not the same engineering problem wearing different
clothes. What DOES generalize, and is worth building once: a shared
**vocabulary and record shape** for "what is claimed, what was actually
observed, and how stale/trustworthy is that observation" (§3) — not a
shared reconciler *engine*. Building the engine now, before a second
concrete domain has actually needed it, is exactly the speculative
infrastructure Codex's condition 10 warns against.

## 2. What the external research contributed

Two independent research passes (Gemini, training-knowledge; Codex, live
search confirmed against Kubernetes/Temporal/Ragas/W3C docs) converged with
a principle already salvaged from this org's own retracted internal
doctrine:

> **"Where a deterministic arbiter exists, the arbiter wins and the panel is
> redundant. Spend the panel on what the suite cannot judge."**
> — `research/operations/2026-08-01-multi-session-multi-llm-strategies.md §4`

This still holds after the council round, in a narrower form: wherever
ground truth CAN be mechanically re-derived (a live probe, a row count, a
file hash), a code-level check does it — no LLM judgment. The Tier-2
"isolated LLM judgment" idea from the first draft is **deferred entirely**
(condition 10) — the pilot chosen below needs none of it, and building an
isolation wrapper before a real Tier-2 case exists would itself be an
unverified claim of "handles bias" dressed as infrastructure.

## 3. The shared record shape (not a "reconciler" — a vocabulary)

Every claim this pattern applies to, regardless of domain, is described by
**4 orthogonal state axes** (Codex condition 2 — this is the part of the
original schema that survived unchanged, because collapsing these into one
`status` field was the single largest defect in the first draft):

- `truth_state` — is the claim factually correct against its authoritative
  source, right now? (`TRUE | FALSE | UNVERIFIED | INCONCLUSIVE`)
- `freshness_state` — how old is the last actual re-derivation, against an
  explicit domain-specific TTL? (`CURRENT | STALE | EXPIRED`)
- `coverage_state` — does an expected claim exist AT ALL, or is something
  that should have been observed simply missing? (`PRESENT | MISSING |
  PARTIAL | UNEXPECTED`) — this is what catches the E33 failure mode (#3),
  which no single-`status` field can express: there is no wrong *value* to
  flag, only an absent one.
- `verifier_state` — is the thing that produced this observation itself
  healthy, or has ITS code/config drifted from what's certified to run?
  (`HEALTHY | DEGRADED | FAILED | DRIFTED`)

Observations are **append-only** (Codex condition 3) — never a single
overwritten `observed_value`. A `ClaimObservation` record is written once
per probe run and never mutated; the "current state" consumers see is a
**materialized view**, derived on read by folding the observation log
against an explicit expected-claim registry and the current verifier
identity — never hand-set to `verified` by a human or an LLM asserting it.

```
ClaimObservation:
  observation_id, claim_id, claim_type, subject_id, observed_at
  evaluator_identity: {verifier_id, version_hash, config_hash}
  context: {host, user, session_type, auth_state, target_model,
            invocation_path, latency_budget_ms}
  raw_evidence: {...domain-specific fields, INCLUDING any capacity/quota
                 signal if one exists — see §5.2, this is where the first
                 pilot design left a field captured-but-unused}
  evaluation: {truth_state, truth_reason, canary_verification_passed}
```

`claim_type` is load-bearing (Codex condition 4): there is no one generic
schema serving every domain identically. Seat-health and, eventually,
regulatory-citation-freshness will each define their own authoritative
source, TTL policy, and truth-derivation logic under this shared shape —
the shape is universal, the semantics of `truth_state` for a given
`claim_type` are not.

## 4. Scope for this effort: ONE pilot, not a rollout (Codex condition 9)

**Pilot: LLM seat-health, scoped to 2–3 real seats, not the full arsenal.**
GLM's review of Gemini's first v2 attempt caught that "12 registered seats,
uniform HTTP probe" hides weeks of hidden complexity: this org's seats are
not uniform HTTP endpoints. They are CLI tools with genuinely distinct auth
flows — Claude MAX OAuth via `claude` CLI subprocess
(`CLAUDE_CODE_OAUTH_TOKEN`, no API key), a separate Claude Team seat, Codex
GPT-5.6 via ChatGPT Pro OAuth (with a **documented silent-failure mode**:
`401 token_revoked | refresh_token_reused`, per CLAUDE.md §5), Gemini via
`agy` CLI, Kimi via device-code OAuth, GLM via a Keychain-stored token
proxied to a z.ai endpoint. Each needs its own probe adapter and failure
catalog; writing 6+ correct adapters is a multi-week effort, not "a quick
first pilot."

**Corrected scope: 2–3 seats for the actual pilot build** —
`claude` CLI (MAX OAuth, the baseline/simplest case) + Codex GPT-5.6-sol
(the seat with a KNOWN, documented, non-hard-down failure mode — the one
worth proving the design actually catches) + one more (Kimi, for a third
distinct auth mechanism: device-code). E33 coverage and PENDING-ARMS
line-typing are explicitly deferred to a later, separate pass once this
pilot's `ClaimObservation`/materializer code exists to be reused — they are
NOT built in this effort, only designed-for at the schema level (§3).

## 5. Concrete pilot design (with the council's fixes applied)

### 5.1 Authoritative source & claim definition (condition 4)

A claim is never a boolean `"alive": true`. Per seat:

> *"Seat `[subject_id]` (model `[target_model]`) is capable of completing a
> real dispatch — not just a liveness ping — under `[auth_context]` within
> `[latency_budget_ms]`, with quota headroom above a minimum threshold."*

Authoritative source = a direct, uncached probe invocation run in the exact
user/session/auth context the real caller would use. Any existing cached
file (`last.json`) is demoted to an unverified secondary projection and is
never read directly by a consumer (§5.4).

### 5.2 The canary gap GLM found, closed

Gemini's first v2 canary set (an unreachable-port negative canary + a
mock-endpoint positive canary) proves the daemon can detect **hard-down**.
It does *not* prove the daemon catches the actual failure mode that started
this whole investigation: **a report that says "alive: true" while being
subtly, not catastrophically, wrong** — exactly the Codex
401-token-revoked case, or a seat authenticated-but-out-of-quota. Fixed
canary set, per seat adapter:

- **Negative-hard canary** — unreachable endpoint/bad credential path; must
  fail closed.
- **Negative-subtle canary** — a seat probe that returns HTTP 200 (or CLI
  exit 0) but with zero quota/credit remaining, or an auth token in a
  revoked-but-not-yet-expired state. Must NOT score `truth_state: TRUE`.
- **Positive canary** — a real, minimal 1-token dispatch to a known-good
  seat; must return `TRUE` within budget.

Concretely, this means `raw_evidence.quota_remaining` (or the seat's
equivalent capacity signal) is a **required** field, and truth evaluation
is `TRUE` only if BOTH the dispatch succeeded AND quota/capacity is above a
declared floor — not dispatch-success alone. (Gemini's first v2 captured a
`quota_remaining_tokens` field but never used it in the truth decision —
exactly the "deterministic check that only proves presence" Codex's
condition 8 forbids. This pilot's truth-evaluation logic must reference
that field or the field should not exist.)

### 5.3 Verifier auditability (condition 6)

The probe daemon hashes its own code + config before each run; a mismatch
against the last-certified hash flags every observation from that run
`verifier_state: DRIFTED`. Canary failures (either negative canary passing
when it shouldn't, or the positive canary failing) flag
`verifier_state: FAILED` and the materializer refuses to report `TRUE` for
anything observed in that run, regardless of what the raw probe returned.

### 5.4 Enforced access — no direct file reads

Consumers (the arsenal dispatcher / cascade-fallback wrapper scripts) call
a small client function that returns the materialized 4-axis state; they
never read `last.json` or any raw observation file directly. The client
fails CLOSED — any axis outside {truth=TRUE, freshness=CURRENT,
coverage=PRESENT, verifier=HEALTHY} raises, it does not silently degrade.
This closes Codex's "every consumer must check, by convention" objection —
convention is not enforcement; a single accessor function is.

## 6. Explicitly deferred (do not build in this pass)

- **Tier-2 / LLM-as-judge machinery** — condition 10. This pilot needs zero
  semantic judgment; building the isolation wrapper now, before a real
  Tier-2 case (WR2 fact-checking, KBLI citation semantics) is in front of
  us, would itself be an unfalsifiable claim of "this generalizes."
- **PENDING-ARMS line reconciliation** — needs per-line claim typing first
  (each ledger line is a different `claim_type`: seat-alive, PR-merged,
  cron-green...); reuses this pilot's record shape once it exists, is not
  part of this build.
- **E33 coverage pilot** — the cleanest demonstration of `coverage_state`
  catching a fully-absent claim, and cheap to add once the materializer
  exists, but is a second, separate pilot, not bundled into this one
  (bundling two domains was exactly what Codex's condition 9 rejected in
  the first draft).
- **KBLI citation backfill and WR2 evidence-independence** — real
  megatopics of their own (from the earlier organism survey), each needs
  its own authoritative-source and truth-semantics definition; they should
  reuse §3's shape, not reinvent it, when their turn comes.

## 7. Pilot success criteria (Codex's condition 5 gap, closed by GLM)

Before this pilot's design is trusted enough to extend to a second domain,
over a 14-day trial:

1. **Bypass rate = 0%** — zero instances of a consumer reading a raw
   observation/cache file directly instead of the enforced accessor.
2. **Detection latency < 5 min** — a simulated seat failure (credential
   lock, network partition, binary/version upgrade, OR quota exhaustion)
   must flip the relevant axis to non-healthy within one probe cycle.
3. **False-positive rate < 0.1%** — fewer than 1 in 1,000 valid dispatch
   attempts rejected due to canary flakiness or verifier-state drift.
4. **The 401-token-revoked case is caught** — this is the one concrete,
   already-documented real failure this pilot exists to catch; if a
   simulated revoked-token Codex seat still reports `truth_state: TRUE`,
   the pilot has not solved the problem it was built for, regardless of
   what the other metrics say.

## 8. Open questions carried forward (not resolved by this council round)

1. Whether `claim_type`-specific truth semantics (§3) should live in one
   shared library with per-type plugins, or as fully separate modules per
   domain — deferred until a second `claim_type` (E33 or PENDING-ARMS)
   is actually built and this stops being a one-example question.
2. Whether the 14-day trial window (§7) is long enough to catch flapping
   verifier drift, versus a shorter or longer window — no principled basis
   yet, flagged as a guess.
3. What the actual alerting/ownership path is when a claim goes `DRIFTED`
   or `MISSING` for an extended period — this spec defines detection, not
   incident response; that is a separate, smaller design question to close
   before the pilot ships to production use.

## §Solo-operatore

None at this stage — this is a design spec ready to move into a build task
under the normal ship-lifecycle (session builds, tests, ships, arms,
proves-live; no operator gate on any of it per CLAUDE.md §2). The only
future operator-only items would be credential/infra actions if a new
seat's auth flow needs a fresh OAuth login — not anticipated for the 2–3
seats scoped in §4.

---

## Adversarial review

**Seats, sequential (not parallel — each built on the prior seat's
output):** Codex GPT-5.6-sol (`xhigh`, `--sandbox read-only`) red-teamed the
first draft (a single universal reconciler across all 6 instances) and
returned **DO-NOT-SHIP** with 10 conditions. Gemini 3.1 Pro (`agy`, no live
search) was then given Codex's full critique cold and asked to design a v2
satisfying all 10 conditions, scoped to one pilot (seat-health) with zero
Tier-2 machinery. GLM 5.2 (`claude-glm`, cross-family, generator≠grader)
then red-teamed Gemini's v2 against the same 10 conditions and returned
**SHIP WITH SPECIFIC CHANGES** (5 fixes).

**Surviving objections, and what each changed:**

| Objection | Outcome |
|---|---|
| "6 problems = 1 disease" doesn't hold — the failure *types* differ materially (manual projection vs context-collapsed cache vs vacuous monitor vs miscalibrated metric vs absent governance vs circular verification) | **ACCEPTED** — §1 rewritten to reject the universal-disease framing; only a shared vocabulary (§3) survives, not a shared engine |
| `valid_until`/freshness was conflated with truth in a single `status` field | **ACCEPTED** — 4 orthogonal axes (§3), unchanged from Gemini's v2, this was the one part that survived Codex's critique intact |
| `proof_ref`/`verified_at` alone only prove a process wrote those fields, never that it checked the right thing | **ACCEPTED** — verifier auditability via code/config hashing + canaries (§5.3) |
| Tier-2 "isolated context" doesn't solve evidence-selection bias, only chat-history bias | **ACCEPTED** — Tier-2 deferred entirely (§6), not attempted in this pilot |
| Proposed pilot (PENDING-ARMS + seat-health bundled) looked cheap only because artifacts already existed; not actually the cheapest or most representative | **ACCEPTED** — single pilot only (seat-health), PENDING-ARMS deferred (§4, §6) |
| Gemini's v2 §5 explicitly *reasserted* "6 problems, 1 root cause" rather than accepting Codex's reframing | **ACCEPTED (GLM catch)** — reworded in §1 above; the shared-root-cause language is now scoped to "shape of the mistake repeats," not "therefore one engine" |
| Gemini's v2 canary design (hard-down negative + mock positive) only proves detection of catastrophic failure, not the subtle "200-but-actually-broken" case that motivated the whole investigation | **ACCEPTED (GLM catch)** — negative-subtle canary added (§5.2), tied to pilot success criterion #4 (§7) |
| `quota_remaining_tokens` was captured in Gemini's schema but never used in the truth-evaluation logic — a presence-only check mislabeled deterministic | **ACCEPTED (GLM catch)** — truth evaluation now requires quota/capacity above floor, not dispatch-success alone (§5.2) |
| "12 registered seats, uniform HTTP probe" understates real complexity — this org's seats are CLI tools with genuinely distinct OAuth/Keychain flows, not uniform endpoints; Gemini's example even cited a nonexistent model (`gpt-4o`) | **ACCEPTED (GLM catch)** — pilot scope cut to 2–3 real, named seats (§4), matching this org's actual arsenal (`claude` CLI, `gpt-5.6-sol`, Kimi device-code) |
| No pilot success criteria were defined (detection latency, bypass rate, false-positive rate) | **ACCEPTED** — §7 added, including a criterion specific to the documented 401-revoked failure mode |

**Known remaining weakness:** this spec has NOT been built or tested; §7's
metrics are targets, not measurements. The claim-type-plugin architecture
question (§8.1) and incident-ownership path (§8.3) are open. No seat other
than the 3 scoped in §4 has been designed for yet, and extending this
pattern to KBLI/WR2/E33 will each require the same council rigor applied
here — this spec explicitly does not pre-approve those extensions.
