---
date: 2026-08-18
domain: operations
client_case: zantara-wa-provider
discovered_by: "Fable/Sonnet session (M5), dispatched to advance the /bot OpenAI-provider lane after Zero's 2026-08-18 route reconfirmation"
sources:
  - "memory: decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15 (owner ruling: ChatGPT Pro subscription via codex exec, never OPENAI_WA_PROVIDER_API_KEY)"
  - "memory: project_bot_openai_lane_governance_codex_orchestrator_2026_08_15 (fence + close-gate sequence)"
  - "PR #4216 body (frozen head b7b2d6652, base 6a8ab5180, 11-file fence, 28-round cross-family review) — read this turn via `gh pr view`"
  - "PR #4194 body + doc content on branch agent/air-m5/ops/bot-provider-verifier (research/operations/2026-08-15-bot-openai-provider-threat-model.md, read via `git show` this turn) — §Fence compliance, §Freeze re-review, §Refutation log"
  - "PR #4197 body + doc content on branch agent/air-m5/ops/bot-failure-matrix (research/operations/2026-08-15-bot-provider-failure-matrix.md, read via `git show` this turn) — §1 Failure matrix, §2 Idempotency, §3 Rollback proof"
  - ".agents/skills/bot/SKILL.md (this session's own update, §1 LIVE STATE 2026-08-18 entry) — Anatomy §3, blood-bought rules §5, wa-mirror PII posture (CLAUDE.md §14)"
adversarial_review: "NONE YET — this is a first-draft PROPOSAL for the orchestrator's gate, explicitly not a closed deliverable. It has not been through the lane's Kimi K3 / Google-agy review pass and must not be cited as verified until it has."
---

# BOT-V — OpenAI provider: shadow-first wiring plan (proposal, not authorization)

## 0. What this document is, and is not

This is a **proposal** for whoever runs the /bot OpenAI-lane orchestrator's close gate (per
`project_bot_openai_lane_governance_codex_orchestrator_2026_08_15`: freeze diff → lead net-diff
check → final Kimi K3 + Google/agy Gemini review of the frozen diff → only then a PR). It is
**not** a design that has cleared that gate, and it does **not** authorize any code change. No
file in this repo that selects a provider, sets a runtime flag, or touches `config.py` /
`llm_gateway.py` was modified to write this document. The live WA channel is unaffected by
anything below; today's mandate (2026-08-18) explicitly does not authorize a cutover.

**Scope**: how the ALREADY-SELECTED provider (`codex_exec_client.py`, ChatGPT Pro subscription
via headless `codex exec`, per the 2026-08-15 owner ruling) should eventually be wired into the
live reply path, if and when the orchestrator's gate clears it — in a way that never risks a
client-facing regression and that can be reversed in one config edit. It deliberately does not
re-litigate the route (Zero closed that) or re-derive the threat model (#4194 owns that,
pending its own freeze re-review).

## 1. Why "shadow-first", not "flip and watch"

Two pieces of prior art in this exact lane say why a flag-flip-to-primary is the wrong first
step:

1. **The vetoed shadow-provider design already found a context-parity defect the hard way.**
   Per #4197's failure matrix (finding on `_shadow_provider.py`, since reworked away per commit
   `b36fc9521`): the first shadow-dispatch attempt forwarded only `input_text` + `system_prompt`
   to the OpenAI client — no conversation history, no tools — so any comparison it logged was
   confounded from the start: the shadow side was answering a strictly poorer-context question.
   A comparison harness that isn't fed the same context as the live path measures nothing.
2. **The existing OpenRouter fallback is the pattern to imitate, not the trap to repeat.**
   `Settings.openrouter_enabled` (default `False`, `app/core/config.py:130`) already gates a
   real, committed, code-live third provider tier behind a single boolean — #4194's own
   Refutation log flags the risk explicitly: "the most likely way an OpenAI adapter gets wired
   in practice is by imitating the ALREADY-PRESENT `_call_openrouter` fallback block" without a
   discrete arming decision, exactly as a Gemini quota exhaustion (4 real occurrences per this
   corner) can flip traffic today for a different vendor with nobody deciding to. This plan's
   flag is deliberately **not** a fallback-on-failure switch — see §3.

## 2. Flag — default OFF, single switch, fail-closed

- **New setting, name TBD by the implementer lane** (e.g. `WA_OPENAI_SHADOW_ENABLED`), boolean,
  **default `False`** in every environment including prod, per the same pattern as
  `openrouter_enabled`.
- Fail-closed on every dimension already named in #4194's Gate V2 spec and #4216's ADR: no
  `codex` binary / no auth → `available=False`, never silently degrade to "try anyway"; no flag
  → the code path is not entered at all (not merely "returns nothing" — dead code until armed).
- The flag governs **shadow dispatch only** (§3). A **separate**, explicitly named flag would be
  required to ever make OpenAI a *candidate* for serving a real answer (§5) — the two must never
  share one boolean, or a single flip both starts comparison logging and starts answering
  clients, which is exactly the "arms real-traffic dispatch on nothing but a bool" risk #4194's
  Finding 7 already named against the earlier design.

## 3. Dry-run on the mirror, not on live traffic

"The mirror" = `apps/wa-mirror`'s captured message stream, **not** the live inbound webhook
path. Two tiers, cheapest-first:

1. **Offline replay against the de-identified corpus** (`scripts/bot/build_deid_corpus.py` +
   the blind bench harness, both already built per #4216's fence deliverables). This is the
   first and default tier: no real client text ever reaches the provider, PII boundary is
   satisfied by construction (de-identification happens before any network call), and it can run
   as many times as needed without touching production state.
2. **Shadow dispatch on live-shaped-but-discarded traffic, gated separately from tier 1.** If
   the orchestrator's gate wants a closer-to-production signal before any real answer is ever
   served, the design that failed context-parity in §1 can be rebuilt correctly — full
   conversation history + tools, matching what the live Gemini call receives — but the OUTPUT is
   **never** returned to the client, only logged for comparison (mirrors the original intent of
   `_shadow_provider.py`, this time with parity). **This tier sends real client message text to
   OpenAI's cloud endpoint** — that is a PII/transit decision under CLAUDE.md §14 (Art. 56
   cascade: adequacy → binding safeguard → explicit consent), separate from and in addition to
   the ToS risk Zero already ruled on for the credential itself. This plan does not resolve that
   gap; it names it as a **precondition**, not a detail to fill in later: tier 2 must not run
   against real WA-mirror content until that basis is demonstrable, per the existing corner rule
   ("the gateway chat proves no clause, Art. 56 basis, revocation or per-client consent today").
   Tier 1 has no such precondition and is sufficient to validate context-parity, tool-calling
   shape, and the failure-matrix rows from #4197 before tier 2 is even proposed as a next step.
3. Both tiers write to a **dedicated comparison log**, never to `wa_outbox` or any table a
   client-facing surface reads — same "no shared format changed from one side" discipline as
   cicatrix family #9 (state-schema mutation drift): this is a new sink, not a repurposed one.

## 4. PROVE-LIVE criteria — what "ready to even consider serving an answer" means

Before any second flag (§2) is proposed to exist at all, tier-1 + (if cleared) tier-2 dry-runs
must show, over a stated sample size (not a single run — this corner's own probes have been
burned by N=1 verdicts more than once, e.g. the abstain-rate and language-drift findings):

- **Context parity, verified not assumed**: the shadow call receives the identical assembled
  context (history, tools-available, system prompt) as the live Gemini call for the same
  message — a repeat of #4197's context-parity finding is disqualifying on its own.
- **Failure-matrix coverage for the ACTUAL provider**, not the dormant one. #4197 as currently
  written analyzes `openai_responses_client.py`'s HTTP failure modes; the codex-exec provider's
  failure modes are process/subprocess-shaped (auth-death via stderr vocabulary, sandbox
  rejection, stdin timeout, ChatGPT Pro seat rate limits) and are a **precondition for this
  gate**, not an afterthought — see the corner entry above (#4197 currently has zero coverage of
  `codex_exec_client.py`).
- **Abstain/evidence-gate equivalence**: the shadow path must not bypass or weaken any of the 5
  named abstain gates (`_abstain_policy.py`, CLAUDE.md §9 SSOT) — a provider swap is not grounds
  to revisit thresholds that are panel-ruled.
- **PII log-leak parity**: whatever discipline protects WhatsApp phone numbers from cleartext
  logging on the Gemini path today (an OPEN P0 per this corner's own history, `tool_authorizer.py`
  `_audit()`) must not have a second, unaudited log line on the OpenAI comparison path.
- **A declared sample size and pass bar**, set by whoever runs the gate — this document does not
  set a number; it names what the number must be measured against.

## 5. Rollback is config-only, by construction — because nothing is wired yet

The honest state today (per #4197 §3, re-confirmed by this document): "rollback to Gemini" has
no meaningful answer yet because nothing routes to OpenAI to roll back FROM. This plan is
written so that stays true through every stage:

- **Stage 0 (today)**: no flag exists. Nothing to roll back.
- **Stage 1 (tier-1 dry-run armed)**: the new flag defaults OFF; flipping it OFF again is the
  entire rollback — no code path outside the shadow dispatcher is touched, no client-facing
  behavior changes at any point, because tier-1 never reaches a client-facing code path at all.
- **Stage 2 (tier-2 shadow-on-live-shaped-traffic, IF the PII precondition in §3 is cleared)**:
  same single-flag rollback; the output is discarded before it reaches any send path, so even a
  crash mid-comparison cannot degrade the served answer (would need to be built as fire-and-
  forget with its own exception boundary, same as the reworked design's stated intent).
  Stage 2 remains disqualified for any real WA-mirror content until §3's precondition is met.
- **A future "OpenAI may answer" stage is explicitly OUT OF SCOPE of this document.** It would
  need its own ADR, its own gate, and — per §2 — its own separate flag, never inherited from the
  shadow flag. Naming it here is only to be explicit about where this plan's authority ends: it
  proposes a path to *observe* the new provider safely, not a path to *serve* it.

## 6. What this plan explicitly hands back to the orchestrator's gate

- The precise flag name, module boundaries, and file list for tier-1 wiring (implementation
  detail, belongs to whichever lane the orchestrator assigns it to, under the same NO-WIRING
  fence discipline that governed #4216).
- The PII/Art. 56 basis for tier 2 (§3) — a business/legal precondition, not an engineering one.
- The sample size and pass/fail bar for §4's PROVE-LIVE criteria.
- Updating #4197 to cover `codex_exec_client.py`'s actual failure taxonomy before that document
  is treated as complete gate-prep (flagged in the corner entry this session added,
  `.agents/skills/bot/SKILL.md` §1, 2026-08-18).
