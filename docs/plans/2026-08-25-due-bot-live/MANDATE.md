# MANDATE — I DUE BOT (client bot multi-surface + agentic team bot)

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

| #   | Task                                                                                                                                                                                                                                                                                                                                                                                                                           | Kind                                  | Unblocks                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- | ---------------------------------------- |
| 1   | Second WA number (SIM/eSIM) + WABA "Bali Zero Operations" in Meta Business Manager; webhook verify + secret                                                                                                                                                                                                                                                                                                                    | operator[gui]                         | team bot live traffic                    |
| 2   | ~~`WHATSAPP_APP_SECRET` fetched from Meta into Fly secrets (client bot fail-open scar)~~ **DONE — verified live 2026-08-25**: the secret is `Deployed`, an unsigned POST answers 401 `Invalid signature`, and real webhooks landed at 10:17-10:19Z under the current release. Proof in the PENDING-ARMS closure. Residual is a session task, not an operator one: arm `META_WEBHOOK_REQUIRE_SIGNATURE=true` on the next deploy | ~~operator[gui]+[secret]~~ **closed** | client-bot webhook signature enforcement |
| 3   | Test message from your phone to the public WA number (+62 821-3465-159)                                                                                                                                                                                                                                                                                                                                                        | operator[physical]                    | confirms/refutes the 24-day-silence cure |
| 4   | Codex seat OAuth logins on the broker Macs (interactive)                                                                                                                                                                                                                                                                                                                                                                       | operator[credential]                  | B2 arming                                |
| 5   | Gemini billing auto-reload + alert                                                                                                                                                                                                                                                                                                                                                                                             | operator[business]                    | client-bot spine reliability             |
| 6   | Team roster: staff WhatsApp numbers → user_id enrollment (verified mapping)                                                                                                                                                                                                                                                                                                                                                    | operator[business]                    | F7 identity table                        |
| 7   | Ignition, in the promotion order (client: shadow→owner-only→5%→25%→per-surface; team: ingress/audit→shadow→owner replies→staff read→R2→R3→auto-failover)                                                                                                                                                                                                                                                                       | operator[business]                    | live                                     |

## Definition of done

Both bots fully built, tested (B6 suites green locally), instrumented (F11), shipped dark on
main via the final PR train, with: the four client surfaces answering through ONE engine in
shadow, the codex leg passing synthetic+shadow tripwires, the team bot executing a full
preview→confirm→commit practice-open against staging CRM from a golden fixture, the failover
drill green synthetically, and the owner switchboard presented as a single decision packet.
Owner flips switches; the session proves live per surface after each flip (PROVE-LIVE).
