# MANDATE — I DUE BOT (client bot multi-surface + agentic team bot)

> ⚡ **AMENDED 2026-08-25 by owner directive #1** (Zero). Verbatim: `DIRECTIVE-1-owner.md`.
> Integration into the lane plan, with the impact map: `DIRECTIVE-1-INTEGRATION.md`.
> It overrides **F8-primary** (the team bot's brain is `qwen3.7-plus` via the TP1 door, with a
> fallback chain ending in a read-only local Qwen) and **F4/F5 scope** (one-tool-per-turn now
> binds MUTATIONS only; reads chain multi-step), and adds a **new requirement**: three-layer
> per-member memory. v1 grows from the F5 tool set to **domains 1-4**, with documents-in-chat
> first-class. Everything else in this file stands frozen. Where this file and the directive
> disagree, the directive wins — do not reconcile by editing the frozen decisions below.

> Home machine: **Mini** (H24, office). Integration branch: **`feature/due-bot`** — LOCAL-FIRST per
> `docs/factory/ASSEMBLY-LINE.md`: no per-commit PR ceremony, tests local, nightly push of the
> integration branch, final landing as a short PR train. PRs to main mid-race ONLY for: live
> surfaces outside this perimeter, doctrine/scars, the final train. Ledger-only PRs are banned.
> Orchestrator: **Opus 5** (this mandate's owner session on Mini). Implementers: task-shaped
> across the full roster (`MODEL_ROSTER.md`); Sonnet 5 default for well-specified BUILD units.
> No duration estimates anywhere — work is done when its gate is green.
>
> Research base (read before building): `research/operations/2026-08-25-due-bot-7-lens-research.md`
> — 7-lens deep research (repo ground, 2 SOTA sweeps, Sol architecture, Gemini serving/Meta,
> Kimi refutation, Qwen family verdict + tool schemas). The architecture below is the SYNTHESIS;
> where a seat disagreed the resolution is recorded here and is FROZEN.

## The product (business picture)

**BOT A — client bot**: one brain, four surfaces (WhatsApp public number, Instagram DM, portal
chat, kbli-navigator widget). RAG-grounded on the Indonesian immigration/company/tax KB,
PricingTool-only prices, citation-or-abstain on every regulatory claim, human handoff with full
context carry-over (the KPI that matters — not vendor-style containment claims). Brain is STAGED:
Gemini (with cured auto-reload billing) is the working spine today; the ChatGPT-subscription leg
(codex broker on our Macs) arms as shadow → owner-only → 5% → 25% → surface-by-surface, gated by
tripwires. A metered key is stage 2, owner decision, triggered only by measured quota walls.

**BOT B — team bot**: an AGENTIC operator for ~10 staff on a dedicated second WhatsApp number.
Not Q&A — it executes CRM actions through existing backend endpoints (never raw SQL): practice
status, client lookup, document-received, reminders, open-practice (preview→confirm→commit).
Brain is LOCAL (UU PDP: client PII never to cloud): Qwen3-14B on the Mini primary, Qwen3-32B on
the Pro for failover and high-risk mixed-language mutations. Per-member RBAC via the WhatsApp
identity, server-side confirmation state machine, audit on every action.

## Frozen architectural decisions (the panel synthesis)

**F1 — No second client-bot pipeline.** Generalize the seams that already exist:
`channels/router.py` (ChannelRouter), `channels/base.py` (ChannelMessage → compatibility wrapper
around a new `CanonicalMessage`), `llm/provider_registry.py`, the dark
`services/integrations/wa_broker.py` queue (add `surface`/`job_kind`/`output_schema_version`
fields — do NOT create a second jobs table), `wa_finalize.py` (becomes a WA-specific wrapper
around the new `FinalPolicyGate`). Persona stays in `backend/prompts/zantara_core.py` — one
prompt-policy source. Module layout, `CanonicalMessage`/`SurfaceProfile`/`BrainCandidate`
contracts, and the 11-step ordered `FinalPolicyGate` are specified in the research capture
(Sol §1) — implement from there.

**F2 — Four frozen SurfaceProfiles** (`client-wa-v1`, `client-ig-v1`, `client-portal-v1`,
`client-kbli-v1`): profile carries length/format/citation-style/history/deadlines/handoff-queue;
NEVER a provider name. KBLI widget answers KBLI only. Portal requires auth. Final content is
atomic — no token-streaming before the gate ALLOWs (progress events only).

**F3 — Codex broker leg** reuses the existing dark implementation (queue depth 1, lease 20s,
breaker 3-fail/5-min). One daemon per seat on Pro/Mini, dedicated unprivileged macOS user,
outbound-only HTTPS claim/complete, `codex exec --sandbox read-only --ephemeral
--output-schema client_brain_candidate_v1.json`, stdin package, process-group kill on timeout.
Closed wire error vocabulary: AUTH_DEAD | QUOTA | TIMEOUT | HOST_OFFLINE | OUTPUT_INVALID |
POLICY_BLOCKED | INTERNAL — auth and quota MUST be distinct (today they collapse; split before
arming). Tripwire table + promotion ladder: research capture Sol §2.5. Secret-canary hit =
global leg kill switch. A quota-fallback ratio >5%/7d produces an owner decision packet for
stage 2 — never an auto-provisioned key.

**F4 — Team bot is a hand-rolled typed tool loop, not a framework.** Kimi's refutation and
Sol's design agree: at 14B the LLM is a slot-filler behind deterministic structure, not a free
agent. `apps/team-bot/` standalone app on the Mini (127.0.0.1:8765): MAX_STEPS=4,
MAX_READ_CALLS=3, single tool per turn (`parallel_tool_calls=false`), temperature ≤0.2,
structured output validated server-side (schema validation AFTER generation is the primary
control; grammar constraints only if measured necessary — Qwen seat ruling). Confirmation
parser runs BEFORE the LLM. Tool results are marked untrusted; the action lane never reads
free-text CRM fields (lane separation — injection defense is architectural, not filtered).

**F5 — Tool registry v1 (ten tools, risk-tiered).** R0 reads: `client.lookup`,
`practice.list_assigned`, `practice.status_get`, `document.required_list`, `reminder.list`,
`practice.open_preview` (R1). R2 confirmed writes: `practice.status_change`,
`document.mark_received`, `reminder.create` (R1, no confirm, undo). R3 always-confirm:
`practice.open_commit` (commits a server-stored preview — accepts NO mutable business fields).
Schemas: enums not free text, IDs not names (`^PR-`, `^CL-`, `^USR-` patterns),
`additionalProperties:false`, one mutation per tool, common envelope with `audit_ref`. Full
JSON schemas: research capture Qwen §4 — use them verbatim as the starting contract.
Reuse `services/rag/agentic/team_crm_tools.py` (4 RBAC-scoped read tools already exist) and
`crm_access.py` filters; complete or bypass the no-op `_check_client_scope` in
`tool_authorizer.py` before any mutation arms (Sol disagreement #3 — accepted as a gate).

**F6 — Confirmation is a server-side state machine, never a prompt convention.**
`PendingAction` (short_code, canonical args encrypted, args_sha256, 5-min expiry, one pending
mutation per actor, leader_epoch): PROPOSED → CONFIRMED → EXECUTED with idempotency keys; the
executor calls the CRM with the STORED payload — post-confirmation text never touches the
arguments. Meta interactive buttons (opaque payloads `confirm:<code>`) preferred; numbered/code
fallback (`CONFERMA 7F3K`) where buttons unavailable. Replay returns the existing receipt.
Steal the shape from `review_handler.py` and the wa_broker CAS — both already in the repo.

**F7 — Identity: wa_id → HMAC → enrolled team mapping → 60s principal ticket.** Unknown /
unverified / wrong-phone_number_id numbers never reach the LLM (fixed refusal copy). The model
cannot supply actor or scope; CRM routes independently enforce `assigned_to` (endpoint
authorization is the boundary; the local authorizer is early-deny only). Raw phone never in
logs — extend `messaging_identity_service.py` but fix its raw-phone logging first.

**F8 — Local inference plant.** Mini primary: **Qwen3-14B, Q6_K** (Q5_K_M floor), served with
the NATIVE Qwen tool template. Pro: **Qwen3-32B Q6_K** for failover + high-risk mixed-language
mutations (routing rule: mutation request with mixed-language ambiguity or R3 tier MAY route to
32B; the 32B never gains broader permissions and never overrides the deterministic runtime).
Serving layer gate (Qwen seat, binding): the server MUST round-trip native `tools` /
`tool_calls` / `role:"tool"` messages without flattening to text — verify empirically on the
chosen stack (llama.cpp `llama-server` with `--jinja -np 4 -cb --flash-attn -ctk q8_0 -ctv
q8_0` is the reference config; Ollama acceptable ONLY if the round-trip test passes). KV cache
never below Q8. Pin model tags AND digests after the goldens pass. Multilingual discipline:
enums stay English ASCII, backend rejects translated variants, dates ISO-8601 server-normalized,
read-before-write to resolve names→IDs, IT/ID/EN golden suite (code-switching cases) gates the
model choice. bge-m3 local for CRM retrieve-not-dump entity cards (~450 token budget/turn).

**F9 — Ingress: Tailscale Funnel on the Mini, Fly OUT of the team-bot path** (owner ruling).
Meta webhook → `https://<mini>.ts.net/webhooks/team-wa` → local FastAPI: raw-body HMAC verify →
durable insert (UNIQUE wamid) → 200 → async processing. Failover = WABA callback override
(`POST /{WABA-ID}/subscribed_apps` with `override_callback_uri`) driven by `team-bot-failoverd`
on the Pro: leader-epoch CAS so a stale node cannot mutate, no automatic failback, and
AUTO-failover stays DARK until a staging-WABA drill proves Meta's retry semantics (Sol
disagreement #2 — accepted as a gate). **Recorded dissent (Kimi)**: Funnel is relay-proxied,
log-less, and a flapping Mini can get the webhook disabled by Meta; the reversible fallback if
Funnel proves flaky in practice is a 30-line verified dumb-forwarder on Fly over the tailnet
(reusing the `inbound_webhooks` ack-first pattern). Ship Funnel; keep the dissent alive as a
one-day pivot, decision to the owner on evidence.

**F10 — Client-bot handoff is a first-class module** (`services/client_bot/handoff.py`): the
bot may say "l'ho passato al team" only AFTER the handoff row is durably created; otherwise the
copy says "puoi richiedere". Context carry-over to the consultant is the product bar.

**F11 — Metrics are first-class or the bot "works" unfalsifiably**: containment, resolution,
handoff rate + latency p95 per surface; codex-leg tripwires (F3); team-bot tool-degradation
tripwires (JSON parse fail rate, schema fail rate, repeated-call rate, enum-translation rate,
confirm-timeout rate, p95). One kill switch per side-effect plane: client send (per surface),
broker generation, team replies, team mutations, failover automation.

## Lanes (parallel sessions; the orchestrator dispatches and gates)

- **B1 — Client-bot core**: CanonicalMessage + profiles + engine + provider router +
  FinalPolicyGate, generalizing the existing seams (F1/F2/F10). Compatibility wrappers keep WA
  live throughout.
- **B2 — Codex broker leg**: daemon, error split, tripwires, schema, promotion machinery (F3).
  Ships dark behind `CLIENT_BOT_CODEX_BROKER_ENABLED=false`.
- **B3 — Team-bot runtime**: `apps/team-bot/` — webhook, identity, typed loop, confirmations,
  registry, audit, sqlite state + Mini→Pro replication (F4-F7).
- **B4 — Inference plant**: llama-server plists on Mini+Pro, model pull + digest pin,
  round-trip serving gate, IT/ID/EN golden eval that selects the final model tag (F8).
- **B5 — Ingress + failover**: Funnel setup, webhook plumbing, failoverd + epoch CAS + WABA
  override (dark), staging-drill harness (F9).
- **B6 — Test harness**: golden conversation fixtures (both bots, the full defect classes in
  research capture Sol §5), webhook replay + signer, fake-codex broker suite, synthetic
  failover suite. No test touches graph.facebook.com.
- **B7 — Control tower**: metrics, tripwires, kill switches, owner switchboard doc, decision
  packets (quota-wall → stage-2 packet; Funnel-evidence → pivot packet).

Cross-lane law: B1's contracts (CanonicalMessage, BrainCandidate schema, GateVerdict) freeze
first and land on the integration branch before B2 consumes them; B3/B4 share only the
ToolDecision schema and the serving endpoint contract. One PR-train concern per PR at landing,
≤~400 net lines where the nature of the work permits.

## Owner switchboard (the ONLY human tasks — nothing here blocks the build; everything ships dark)

| #   | Task                                                                                                                                                     | Kind                   | Unblocks                                 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------- |
| 1   | Second WA number (SIM/eSIM) + WABA "Bali Zero Operations" in Meta Business Manager; webhook verify + secret                                              | operator[gui]          | team bot live traffic                    |
| 2   | `WHATSAPP_APP_SECRET` fetched from Meta into Fly secrets (client bot fail-open scar)                                                                     | operator[gui]+[secret] | client-bot webhook signature enforcement |
| 3   | Test message from your phone to the public WA number (+62 821-3465-159)                                                                                  | operator[physical]     | confirms/refutes the 24-day-silence cure |
| 4   | Codex seat OAuth logins on the broker Macs (interactive)                                                                                                 | operator[credential]   | B2 arming                                |
| 5   | Gemini billing auto-reload + alert                                                                                                                       | operator[business]     | client-bot spine reliability             |
| 6   | Team roster: staff WhatsApp numbers → user_id enrollment (verified mapping)                                                                              | operator[business]     | F7 identity table                        |
| 7   | Ignition, in the promotion order (client: shadow→owner-only→5%→25%→per-surface; team: ingress/audit→shadow→owner replies→staff read→R2→R3→auto-failover) | operator[business]     | live                                     |

## Definition of done

Both bots fully built, tested (B6 suites green locally), instrumented (F11), shipped dark on
main via the final PR train, with: the four client surfaces answering through ONE engine in
shadow, the codex leg passing synthetic+shadow tripwires, the team bot executing a full
preview→confirm→commit practice-open against staging CRM from a golden fixture, the failover
drill green synthetically, and the owner switchboard presented as a single decision packet.
Owner flips switches; the session proves live per surface after each flip (PROVE-LIVE).

## Kill criterion (lane B7 — ASSEMBLY-LINE §0 requires one; the mandate did not carry one)

ASSEMBLY-LINE's Gate G0 requires a falsifiable kill criterion per product. This mandate did not
originally state one; the text below is B7's addition, additive to F1-F11 (nothing here reopens
a frozen architectural decision) and reviewable by the owner at the same time as the switchboard
packet.

KILL that leg (revert to shadow-only or fully dark), do not keep iterating on it, if ANY of the
following holds, scoped to AFTER the leg in question has moved past shadow. Each row below
carries its OWN window — there is no single blanket window across rows; an earlier draft of this
section stated "2 consecutive weeks" as a preamble covering all four, which directly contradicted
every row's own stated window (48h, 3 digests, a single occurrence, 3 separate weeks) and would
have let a safety-tier breach (row 3) persist for two weeks before mutations froze — the exact
opposite of what that row requires. Read each row's window as authoritative; the only thing every
row shares is the shadow-scoping above.

- **Client bot — correctness.** `client_policy_unsupported_claim_escape_total` or
  `client_bot_citation_integrity_fail_total` fires even once against REAL production traffic
  (not golden/shadow) and stays uninvestigated/unfixed past **48h**. Per the mandate's own framing
  ("answers fast and wrongly is worse than down"), a bot producing regulatory harm faster than
  it is caught is not a bot to iterate on live — kill client-send for that surface back to
  shadow first, fix, then re-promote through the full ladder again.
- **Client bot — the stated product KPI.** `client_bot_handoff_context_carryover_total /
client_bot_handoff_created_total` measured under 80% for **3 consecutive weekly digests**. The
  mandate's own words: "context carry-over to the consultant is the product bar." A bot that
  cannot clear its own stated bar for 3 straight weeks is failing on its own terms, not an
  external one — all containment/resolution numbers upstream of this are the "unfalsifiable"
  metrics ASSEMBLY-LINE's inversion warns against if this one is failing. **This ratio can go
  quiet instead of red**: if `client_bot_handoff_created_total` is zero (or below a floor of 5)
  for a week, the ratio is undefined, not "100% healthy" — a digest week with fewer than 5
  handoffs reports INSUFFICIENT DATA for that week and does not count toward, or reset, the
  3-week clock either way. Silence is not a passing grade; the class this guards against is
  "green because nothing was measured," the same family the repo's own cicatrix rules name.
- **Team bot — safety invariants.** Any confirmed occurrence — **not a rate** — of
  `team_bot_mutation_without_confirmation_total`, `team_bot_rbac_scope_leak_total`, or
  `team_bot_idempotency_double_execution_total` (tripwires.py). These are exactly the classes
  UU PDP and Legge 5 exist to prevent; a single unrecovered incident is measured proof the
  typed-loop/local-inference containment does not hold as designed. **Why a single occurrence,
  never a threshold**: a confirmation bypass or an RBAC scope leak is not a quality metric with
  an acceptable rate — one occurrence already proves the containment does not hold as designed.
  Rates are the right instrument for things that degrade gradually; this is a thing that either
  holds or does not, and a rate-based version of this row would be measuring how often it is
  allowed to fail rather than whether it is safe. Response is not a patch on the same
  architecture — mutations (F5/F6) revert to Q&A-only (`TEAM_BOT_MUTATIONS_ENABLED` frozen
  false) pending a redesign, and the redesign itself needs a fresh owner ruling before mutations
  re-arm.
- **Codex leg — an ignored decision packet.** `codex.quota_fallback_ratio` fires **3 separate
  times across 3 separate weeks** with the resulting owner packet
  (`ops/packets/QUOTA-WALL-STAGE2-PACKET.template.md`) never acted on. **Why an ignored packet
  un-winds the leg rather than just re-alerting**: this is the deliberate inverse of the
  mandate's own rule that nothing may be parked behind an owner decision — the build never
  waits on the owner, and the trade for that is that a leg nobody decides about does not get to
  sit indefinitely at whatever owner-only/5%/25% rung it was on when the first packet fired.
  Fail-safe, not fail-open: three ignored packets is not the product being punished for a human's
  inaction, it is the one place in this mandate where an undecided state has a default, and the
  default is "step back," not "keep going." A later reader who sees this as an oversight should
  read this sentence before removing it.

Reviewed monthly alongside the switchboard, per ASSEMBLY-LINE §7 ("Monthly: kill criterion
checked — alive / narrowed / killed"). "Narrowed" is the expected middle outcome for most of
these (drop a promotion rung, not the whole product) — full kill is reserved for the safety-tier
row above recurring at all, since it is defined as a single occurrence rather than a repeated one.
