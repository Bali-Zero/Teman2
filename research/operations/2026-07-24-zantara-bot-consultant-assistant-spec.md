---
date: 2026-07-24
domain: bot
title: Zantara WA bot — spec for the perfect client consultant + agentic team assistant
status: FINAL (council-reviewed; ready for Opus 4.8 as executing architect)
author: Fable 5 (M5)
method: TAC over a 12-lane workflow (8 audit + 4 reuse-first research) → draft → 3-seat cross-family adversarial council (Codex red-team, Gemini costruttivo, Kimi refuter) → disk re-verification of every P0 → this synthesis
sources:
  - 8 audit-lane outputs + 4 research-lane outputs (scratchpad/tac/*.json)
  - council verdicts (scratchpad/tac/council-*.json)
  - independent disk re-verification (agentic_rag.py, hybrid_auth.py, tool_executor.py, wa_outbox_worker.py, team_crm_tools.py, observability.py, orchestrator_core.py)
client_case: n/a (infrastructure/product)
consumers: Opus 4.8 (architect, executes), Zero (Legge-5 gates)
---

# Zantara WA bot — the perfect client consultant + agentic team assistant

> **Reader's contract.** Verdicts from the council are LEADS, not facts (W65). Every 🔴 P0 in
> this spec was re-grepped on disk THIS synthesis and carries its file:line. Where the council
> was wrong (Gemini's BKPM "correction"), this spec keeps the org's verified fact and says so.

## 0. Verdict

The bot has a **safe, correct brain** and a **hardened transport**. Two things are NOT true of it
today, and they are different in kind:

- **(A) The live path lost its manners and its instruments.** Almost every "good consultant"
  reflex (ack, chunked send, read receipt, error message) and every ops organ (abstain dashboard,
  golden-set eval, regulatory-obsolescence trigger, fallback provider) *already exists in code*,
  wired to the DEAD legacy path or gated behind an unset flag, and never reaches the live client.
  This is the **dominant class by count** — cheap to cure (connect + arm + schedule), reuse-first.
- **(B) Two identity/data-contract boundaries are broken.** These are **fewer but P0**, and the
  "just wiring" framing of (A) actively hides them: the live path collapses every WhatsApp sender
  to ONE shared internal identity (cross-client memory bleed, disk-confirmed), and the persona-
  override + reserved-arg trust boundaries are forgeable. **No feature may be built on top of these
  until they are contained.**

**Readiness is impressionistic, not measured** (the council was right to flag it): there is no
golden multi-turn eval baseline yet, so treat "brain live / manners disconnected / team half-armed"
as the shape, not "65%/40%". **The first executable step is to establish that baseline** (§8, W-1).

---

## 1. The two meta-patterns (Gear-3 mandatory — corrected by council)

The draft claimed one disease. The council (Codex + Kimi) correctly refused it: one pattern explains
the wiring gaps but **cannot** explain identity trust, tenant isolation, or provider sovereignty.
There are **two**, and conflating them is itself the most dangerous error:

### Pattern A — Esiste ≠ Armato (superscar #2), dominant by count
*One defective belief: "if the capability is in a module, the behavior is live."* The question never
asked was **"which code PATH actually calls it?"** (`feedback_merged_is_not_live_consumer_map_first`).
The live number runs **Path B** (`whatsapp_chat.py` → `meta_inbox_*` → `wa_outbox_worker.py` →
`wa_inbox_bot.py` → `/api/agentic-rag/query`), rebuilt fast for correctness + safety. It inherited
the brain but not the manners — those live in the legacy `process_whatsapp_message` path (Path A,
"not this number's brain"). Every row below is a built, tested capability that does not reach the live client:

| Capability | Exists in | Live on Path B? |
|---|---|---|
| "working on it" ack (`whatsapp_ack.py`, tested) | legacy path only | ❌ client waits 10-50s blind |
| multi-message chunking (`message_chunker.chunk_message`) | legacy path only | ❌ answers cut at 4096 chars |
| read receipt (`mark_message_read`) | legacy path only | ❌ no blue tick |
| error/apology on failure | legacy path only | ❌ terminal failure = silence |
| team CRM read tools (#2890 merged+tested) | orchestrator, flag-gated | ❌ `WA_TEAM_CRM_TOOLS_ENABLED` unset (default false) |
| `RetrievalQualityMonitor` (abstain/latency dashboard) | built + REST | ❌ `record_*()` never called → dashboard always zero |
| generation-faithfulness eval (`apps/evaluator/rag_eval/`) | built + golden set | ❌ no cron → 7 weeks unrun |
| curated-QA regulatory obsolescence (`curated_qa_regen_trigger.py`, W90 antidote) | built + tested | ❌ no schedule → stale answers up to 30d |
| inbound rate-limit (`ChannelRateLimiter`) | built | ❌ not wired to WA ingress |
| abstain-rate Prometheus counters | fire live | ❌ no alert consumer |

**Inverted twin (still armed on the wrong path):** `whatsapp_persona.py` injects the full hardcoded
price list into the system prompt (violating PricingTool-only) and fires the instant a second
`phone_number_id` is onboarded. The dead path kept its landmine while the live path lost its manners.

### Pattern B — Broken identity & data-contract boundaries (the dangerous minority)
Not wiring — *design*. On Path B the caller authenticates with a **shared** internal key that resolves
to a **fixed pseudo-identity**, and trust decisions read **client-settable body fields**. These are the
P0s that Pattern A's optimism masks. They are enumerated as W-1 below and MUST be contained before any
Pattern-A wiring widens the surface.

**Why the split matters for Opus:** most of the plan is connect/arm/schedule (Pattern A, low risk,
high leverage). But the *first* work is containing Pattern B — arming team tools or memory-dependent
features on a forgeable principal / shared memory namespace turns a latent leak into an active one.

---

## 2. What is REALLY ready and live (proven — evidence on disk)

**Transport (solid, keep):** ack-first HMAC webhook (`whatsapp_chat.py:1171-1200`), double dedup
(`inbound_webhooks` UNIQUE + `meta_message_id` ON CONFLICT), per-thread advisory lock with the
str-typed-key P0 fixed (`wa_outbox_worker.py:303-306,344-347`), burst coalescing, claim-token fencing,
lease heartbeat, takeover-during-generation re-check, 24h-window enforcement, K workers + admission
semaphore. Media handed off metadata-only to the sovereign Pro-side intake — Fly never stores client PII.

**Brain (safe, live):** Gemini 3.5-flash / 2.5-flash (`llm/config.py:16-18`); 5 named abstain gates
via one SSOT (`_abstain_policy.py`); ReAct cap 2 on WA (`wa_inbox_bot.py:267`, `whatsapp_chat.py:537`);
`CURATED_QA_INJECTION_ENABLED` default `"true"` → grounding injection **is on** in prod.

**Prompt (governed, live):** the versioned door (`prompt_manager.py`) is the source for Path B; prod
pinned `ZANTARA_PROMPT_VERSION=v4` (probed live); v4 carries `{today_wita}`, deadline-neutral KBLI
triage, escalation + identity-lock worked examples, `_safe_template_fill`. WA overlay forces plain-text/short.

**Team identity wiring (merged):** `resolve_sender_identity` (owner>team>client>unknown, fail-closed)
wired into Path B (#2872); `WHATSAPP_OWNER_NUMBERS` (2) + `WHATSAPP_TEAM_NUMBERS` (20-person roster)
SET in prod; TEAM/CREATOR persona reachable; team answers excluded from shared cache.

**Cache/corpus (built, mostly live):** provenance contract enforced `ValueError` (5 keys); Redis
verbatim JELAS-only + Qdrant curated_qa grounding; `--verbatim-all` retired; class TTL (JELAS 30d/else
7d); pricing-content detector is a currency+digit regex (scar-#3-safe); 396 curated Q&A / 21 files;
PR #2810 rails MERGED; 51 curated_qa unit tests pass.

**Security (post-tourniquet #2962):** SENSITIVE_TOOLS `{crm_query,timesheet,team_knowledge}` denied
for `agent_role=None` **before** the no-principal passthrough (`tool_authorizer.py:79-90`); streaming
CRM prefetch gated on `agent_role is not None`; clock-in/out ignore body identity for non-admin.

**Observability — corner CORRECTIONS (verified this synthesis):**
- Langfuse tracing is **ENABLED** in prod (default `"true"` when keys present, keys deployed, no
  `LANGFUSE_ENABLED=false` secret — `observability.py:53`). The corner's "kill-switch active" is **STALE**.
- `llm_cost_events` recorder FIXED and landing rows (#2845). `rag_canary.py` armed + green every 6h
  (15/15 golden queries). wa-tester LID under-match FIXED (#2903). Operator console = hardened loopback proxy.

---

## 3. W-1 — CONTAINMENT (Pattern B — the P0s, disk-confirmed, block everything)

> **These are not in a gap matrix with the rest because they gate the rest.** Each was re-verified
> on disk this synthesis. Opus must treat W-1 as the first stage and, for P0-MEM, as a possible
> **active prod incident** (autoreply is ON, traffic is currently low — contain before it grows).

| id | Finding (verified) | Evidence | Cure |
|---|---|---|---|
| **P0-MEM** | **Cross-client memory bleed.** Path B authenticates via `X-Internal-Key` → `hybrid_auth.py:380-385` returns a **fixed** pseudo-identity `{role:internal, email:"wa-mirror-internal@balizero.com", user_id:"wa-mirror-internal"}` for EVERY sender. `agentic_rag.py:398-405` **discards** the per-phone `whatsapp_{phone}` and substitutes `authenticated_user_id = current_user.email`; `:475` passes it as `user_id`. `memory_handler.save_conversation_memory` skips only `user_id=="anonymous"` (`:138`) → the shared id is NOT skipped. Long-term client facts are stored under ONE key and read back mixed across clients. | file:line above, all re-grepped | **Disable Path B long-term memory immediately** until a **server-derived stable pseudonymous subject** (per-phone, non-PII) replaces the shared identity. Investigate + quarantine existing `wa-mirror-internal` facts. `context_manager.py` also logs sample personal facts directly — audit it. (In-thread history keyed on `wa_session_{phone}` is per-phone and OK; the FACT layer is the leak.) |
| **P0-ID** | **Forgeable persona-override.** `_is_trusted_wa_profile_caller` (`agentic_rag.py:298-322`) allows a `profile` override on (`role=="internal"` from the **shared** key) AND (`channel=="whatsapp"` from the **client-supplied body**). Any holder of the shared internal key (incl. Pro-side scripts) can set `channel=whatsapp` + `profile={role:creator}` and get the creator persona. The code comment candidly admits this. | `agentic_rag.py:298-322,383-397` | A per-request **typed identity envelope** (authenticated service + stable subject + audience mode + channel + msg/thread id + profile provenance + nonce), OR re-resolve phone identity server-side. This is **T4** and it must precede T1. |
| **P0-ARG** | **Reserved-arg forge.** `tool_executor.py:346-349` injects `_caller_profile`/`_user_id` only when the SERVER value is truthy; the `arguments` dict is LLM-supplied. On the client path (no server profile), an injected `_caller_profile={role:creator}` in a tool-call survives into `tool.execute(**arguments)`. Harmless until a team tool reads it AND team tools are registered (T1) — then it is a client→creator CRM-scope escalation. | `tool_executor.py:346-349` | **Never expose these keys in the LLM-facing JSON schema**; strip/reject ALL reserved keys (incl. nested/alias) BEFORE authorization AND before execution; build a fresh args mapping; inject context out-of-band. Test all team tools with forged fields. |
| **P0-FLOOD** | **No inbound rate-limit / length cap** on the WA ingress reaching the LLM+tool loop — cost-bomb / flood (`ChannelRateLimiter` exists, unwired). | audit-security S3 | Wire `ChannelRateLimiter` (per-phone) + inbound text length cap at webhook ingest. Move into containment (precedes new acks/tools). |

**W-1 acceptance:** two different phone numbers get **isolated** memory (A's facts never surface for B —
proven by a runtime test, not code-reading); a request with a forged `profile`/`channel`/`_caller_profile`
is rejected (test); flood/oversize inbound is throttled/capped. A **multi-tenant security test suite**
(two phones, forged profiles, shared-key caller, unknown sender, takeover, duplicate webhook, memory/cache
isolation) is the durable regression.

---

## 4. Gap matrix — the CLIENT CONSULTANT (Pattern A + domain gaps)

Sev 🔴/🟡/🟢. Type WIRE / ARM / BUILD / DECISION / CONTENT.

| # | Gap | Sev | Type | Cure (council-hardened) |
|---|---|---|---|---|
| C1 | Media/PDF/voice/location/contact inbound → **zero reply, ever** | 🔴 | WIRE | Correlated state machine (received→accepted/rejected→processing→ready/failed); ack only what's accepted; classify no-text as **permanent, not retried**. **Fetch+persist media binary BEFORE ack** — Meta media_id URLs expire ~5 min (Gemini). Add media security lifecycle: type/size allowlist, retention, consent, deletion, failure reconciliation. |
| C2 | Long answers **silently truncated at 4096** (`whatsapp_service.py:92`); worker sends once | 🔴 | BUILD | **Durable chunk ledger FIRST** (per-chunk idempotency + WAMID persistence + partial-success recovery + takeover/24h-window fence before each chunk) — a naive loop is a duplicate-send regression on crash (Codex+Gemini). Then syntax-aware split at paragraph/tag boundaries, sequential rate-limited send. |
| C3 | Client waits **10-50s blind** — no "working on it" | 🟡 | WIRE | Wire `whatsapp_ack` into `_process_claimed_row` after `generating`; ledger+coalesce acks per burst; suppress after takeover. |
| C4 | Terminal failure → **pure silence** | 🟡 | WIRE | Best-effort language-aware apology in the 5-retry-exhausted branch. Idempotent, takeover-aware. |
| C5 | **No read receipt** | 🟢 | WIRE | `mark_message_read(wamid)` from `_handle_meta_inbox_message`; no RAG dep. |
| C6 | **Gemini is a single point of failure** — 429/prepay-depletion zeroes the bot (recurred 2026-07-22) | 🔴 | DECISION | **Default fail-closed**: queue/retry + neutral "having trouble, a team member will follow up" + human handoff. External fallback is NOT "classify non-PII pre-failover" (unsafe on free-text WA — names/passport/KITAS appear anywhere; UU PDP Art. 56). Any fallback needs a deterministic redaction pass EXCLUDING attachments/history/memory/retrieval/tool-outputs, or a dedicated endpoint — a Zero Legge-5 ruling. Until ruled, `openrouter_enabled` stays off; the mitigation is the **Gemini-429 alert (O1)**. |
| C7 | `classify_query_domain` **bare substring**, missing English "vat"; colloquial aliases (Investor KITAS/B211A) miss official terms (`reasoning_utils.py:607-633`) | 🟡 | BUILD | Add `vat`; build an **alias dictionary** (colloquial→official) + move toward intent classification; guard-conformance guilt+innocence test (scar #3). **Correctness bug — sequence in W1/W4, not last** (Kimi). |
| C8 | **ReAct cap 2** truncates compound first-contact questions | 🟡 | BUILD | Question-count heuristic → `max_steps=3` for compound only. **Only after W3 telemetry + W4 baseline exist** (Codex). |
| C9 | **No general clarify-before-answer policy** | 🟡 | BUILD | Domain-agnostic `CLARIFYING_QUESTION_POLICY` in v5 (Sierra/Intercom/agy converge). |
| C10 | **No escalation-to-human UX** | 🟡 | BUILD | Escalation-trigger matrix (explicit ask / repeated-abstain loop / red-flags: overstay>60d, nominee, active audit / high-stakes) → structured warm-handoff payload. **Plus the operating contract**: owner, hours, SLA, queue, stale-escalation handling, client-facing message when no human available (Codex+Kimi) — else a dead-end. |
| C11 | **No follow-up/CTA** on WA | 🟢 | BUILD | WA overlay: after N exchanges on a concrete case, suggest formalizing ("already talking to us"). Requires inbound interactive-payload parsing if buttons used (Gemini). |
| C12 | Curated corpus **thin** (396 rows, some 14) | 🟡 | CONTENT | Grow via existing pipeline; feeds the promotion loop (O4). |
| C13 | Curated **regulatory-obsolescence unarmed** → stale JELAS up to 30d (reintroduces W90) | 🔴 | ARM | Schedule `curated_qa_regen_trigger.py` in **dry-run/proposal mode first** (promotion needs a review gate — Codex). Add an **emergency delta path** for Surat Edaran that change faster than 30d (Gemini). Can ride early (one-line cron) ahead of W3's other items. |
| C14 | No ru/uk business phrases (active Ukraina segment); **cross-lingual retrieval recall drop** for ru/it queries vs EN/ID vectors | 🟢/🟡 | BUILD | Add ru/uk to `business_rules_i18n`; add query translation / cross-lingual dense retrieval (Gemini). |
| C15 | Stale **10-miliar** PT PMA capital in a few-shot reachable via `gemini_service.py` | 🟡 | WIRE | **Our verified fact stands: BKPM 5/2025 baseline = 2.5 miliar; >10 miliar survives per-KBLI/location only** (`fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16`). Gemini's council "correction" to 10 miliar is **stale training data — DO NOT apply**; cite the regulation directly. Refresh/remove the few-shot; route `zantara_persona.py` through `prompt_manager`. |
| C16 | **No advocate-license disclaimer** (UU Advokat 18/2003) on legal/tax/visa answers; **no UU PDP consent capture** on first contact for storing `wa_session_{phone}` + processing passport/visa docs | 🟡 | BUILD | Add a "general regulatory info, not formal legal counsel" disclaimer to the relevant answer classes; add a first-contact consent capture gate (Gemini). |

---

## 5. Gap matrix — the AGENTIC TEAM ASSISTANT

| # | Gap | Sev | Type | Cure |
|---|---|---|---|---|
| T4 | **Two parallel auth systems** — `whatsapp_identity._caller_profile` (reaches WA) vs VASSAL `agent_role` (set only on workspace-stream); the WA principal is forgeable (P0-ID) | 🔴 | BUILD | **Unified server-side principal** for Path B satisfying BOTH the SENSITIVE_TOOLS gate and `_caller_profile`. **This is a W-1/W2 prerequisite, not a mid-sequence item** — all three seats: activating tools on a forgeable principal is unacceptable. |
| T1 | 4 read-only CRM tools (#2890, merged+tested) **not armed** | 🔴 | ARM | `WA_TEAM_CRM_TOOLS_ENABLED=true` + redeploy — **only AFTER T4**. Prove-live from a real team number. |
| T-VIS | Client callers still **receive team tool declarations** (deny at execution ≠ absence) → the "byte-identical client" criterion is invalid as written (Codex) | 🔴 | BUILD | **Per-request tool minimization**: team tools ABSENT (not just denied) from the registry for client/unknown callers. Replace the innocence criterion with schema-absence + semantic-regression tests. |
| T2 | **WA check-in dead**: `timesheet` ∈ SENSITIVE_TOOLS and `agent_role` never set on WA → hard DENY (silent regression of #2962) | 🔴 | BUILD | 5th `team_timesheet` tool authorized by the **unified principal** (T4), writing via `team_timesheet_service`, through the unified authorizer + **confirmation + immutable audit + idempotency/timezone/duplicate-check-in handling**. WRITE → Zero GO + own flag. |
| T3 | **`team_knowledge` (handbook/SOP) dead on WA** (same agent_role=None deny) | 🟡 | BUILD | `_caller_profile`-scoped knowledge tool beside the CRM tools, not the VASSAL gate. Data-minimized output (read-only ≠ PII-light). |
| T5 | **No draft-a-client-reply tool** | 🟡 | BUILD | Composes PricingTool + KG/RAG into a draft, unified-principal-scoped, **never auto-sends** (Legge 5). Guard against **indirect injection** (CRM notes/memory content reaching the draft — Kimi). |
| T6 | **No reactive briefing** ("cosa ho oggi?") | 🟡 | BUILD | `team_my_deadlines` has the data; add a greeting/briefing intent (reactive, in-window). Proactive push stays Telegram/email (ruling 2). |
| T7 | No task/reminder capture, no lead-notification pull | 🟢 | BUILD | Scoped write-tool (own Zero GO — breaks read-only invariant) + "new assignments?" pull-tool. |
| T8 | `team_members.whatsapp` **completeness unverified** — drift risk (new hires missed / leavers kept) | 🟡 | ARM | Read-only count; backfill; roster-vs-env drift check. |
| T9 | **Team persona CONTENT unaudited** (`zantara_core.py` not read this pass) | 🟢 | VERIFY | Opus reads it; confirm runtime client/team/owner branch. |
| T10 | **Same person is team AND personal client** — precedence owner>team>client denies them client-mode history separation for their own case (Kimi) | 🟢 | BUILD | Design note / acceptance criterion for the role-collision. |

---

## 6. Observability gap matrix (the O-items — defined, per Kimi)

| id | Gap | Sev | Type | Cure |
|---|---|---|---|---|
| O1 | **No Gemini-429/prepay-depletion alert** — the 2026-07-22 outage was found by accident | 🔴 | BUILD | Catch the google-genai exhausted/429 class at the `llm_gateway.py` raw call sites → `alert_service.send_alert` (Telegram), not just `logger.warning`. This is C6's mitigation. |
| O2 | **No outbox-failure-spike alert** | 🟡 | BUILD | Counter + thresholded alert in the worker failure path. |
| O3 | **Generation-faithfulness eval unarmed** (`apps/evaluator/rag_eval/`, 7 wks) | 🟡 | ARM | Cron mirroring `rag_canary.py`; post pass-rate. **Recognize CLARIFY/ESCALATE as valid outcomes — align with W4's taxonomy or it scores them as failures** (Gemini). |
| O4 | **Curated promotion loop** — abstain/low-confidence → expert-review queue → promote with provenance (compounding asset — Kimi+Decagon) | 🟡 | BUILD | Queue + review gate + harvest (operator-gated per corner). |
| O5 | `RetrievalQualityMonitor.record_*` **never called from live path** → dashboard always zero; `query_analytics` has no confidence/abstain columns | 🟡 | WIRE+BUILD | Wire `record_abstain/record_query` at the `emit_strict_abstain_metrics` sites; migration adds `confidence_score`/`abstained`/`abstain_reason` (Codex sandbox: upgrade+downgrade). |
| O6 | **No synthetic end-to-end channel canary** — the 11-day Langfuse outage was invisible to the API-only canary | 🟡 | BUILD | A low-frequency synthetic outbox-insert (or off a staging `phone_number_id`) walking the real ledger path; needs a **staging WABA/test number** with a home in a workstream (Kimi). Balanced scorecard (Klarna 20-F): automation + resolution + repeat-contact + escalation + CSAT — never deflection alone. |

---

## 7. Cross-cutting security (beyond W-1)

| # | Risk | Sev | Cure |
|---|---|---|---|
| S1 | **`CRMTool.limit` unclamped** — an authenticated team session (or in-session injection) can dump the clients/practices PII table in one call (`tools.py` CRMTool.execute, no clamp) | 🔴 | `limit = max(1, min(int(limit), 50))`. **General hardening — NOT the T1 gate** (the 4 team tools clamp at 30 independently; the T1 gate is T4+P0-ARG). Do it in W0. |
| S2-indirect | **Second-order prompt injection**: guard items cover live client free-text, NOT injected content sitting in CRM notes / memory / curated-QA that a team draft/tool later reads (Kimi) | 🟡 | Sanitize/scope CRM + memory content before it reaches team-tool/draft context. |
| S4 | **JWT expiry not enforced in prod** (`config.py:501` default false, no override) — leaked JWT valid forever app-wide | 🔴 | DECISION+ARM: verify refresh-token flow, then `JWT_ENFORCE_EXPIRY=true` (blind flip logs out live sessions — ops window). |
| S5 | **Orphan test tree** `apps/backend-rag/tests/` (276 files incl. auth + CRM-integration) not collected by CI | 🟡 | Merge into `backend/tests/` (dedup) or add a CI step; prove with a deliberately-broken assert. **NB: W-1/W0 acceptance must not reference this until it lands — forward-dependency (Kimi).** |
| S6 | **Phone-number recycling** (telco reassignment inherits case-file access) — root-of-trust risk, no re-verification | 🟡 | Low-trust/re-verify dormant identities; a workstream item, not just a named risk. |
| S7 | **Double-send residual** — accepted-but-unmitigated window, no reconciliation job (Kimi) | 🟡 | Idempotency/dedup reconciliation sweep in the transport workstream. |

---

## 8. Target architecture — the destination

The research converges on a shape the stack is already ~70% toward. **Do not re-architect; complete
it — after W-1 contains Pattern B.**

**Client consultant — Query → Evidence → Answer → GATE → (Send | Clarify | Abstain | Escalate):**
1. **Input rail** (missing): prompt-injection/jailbreak + length/rate check before the LLM (NeMo 5-rail
   taxonomy — our gates are retrieval+output-side only). Covers direct AND indirect (CRM/memory) injection.
2. **Retrieve** approved sources only — live.
3. **Generate** — live.
4. **Pre-send supervisor grade** (partially live): four-outcome fail-closed SEND/CLARIFY/ABSTAIN(explained)/
   ESCALATE; **per-claim grounding decomposition** for KBLI/visa/tax/deadline numbers (generator≠grader).
5. **Deliver with manners** (the disconnected nerves): ack → durable-ledger chunked send → read receipt →
   error fallback.
6. **Govern memory** (Decagon dual-layer + write-gate): raw history + structured facts carrying
   provenance/timestamp/consent/expiry (UU PDP-native) — **keyed on a per-phone pseudonymous subject, never
   the shared internal identity** (W-1); CRM/PricingTool always authoritative over memory. Retention/expiry
   is an OWNED item, not a claim (Kimi).

**Team assistant — same number, server-side sender-RBAC persona switch (never prompt-inferred):**
unified principal (T4) → satisfies gate AND `_caller_profile`; per-request tool minimization (T-VIS);
read tools armed (T1); check-in (T2) + knowledge (T3) via the principal; draft-reply (T5, never auto-send);
reactive briefing (T6). **Manager topology** (OpenAI): one conversational face, invisible delegation to
visa/company/tax/property specialists — split to true multi-agent ONLY on measured routing failures (ties to O5).

---

## 9. Reuse-first adoption (OSS — re-verify each LICENSE on the exact repo/commit before vendoring)

| Brick | Adopt | Label | License |
|---|---|---|---|
| Voice-note transcription (C1) | `faster-whisper` | INSTALLA-LIB | MIT |
| WhatsApp interactive (buttons/lists/Flows) + inbound interactive-payload parsing (C11) | `pywa` | FORKA-E-ADATTA | MIT (verify) |
| Golden-set regression in CI (O3) | `DeepEval` (pytest-native) | INSTALLA-LIB | Apache-2.0 (verify) |
| Offline corpus-tuning eval | `Ragas` | INSTALLA-LIB | Apache-2.0 |
| Prompt A/B + red-team | `promptfoo` | INSTALLA-LIB | MIT |
| Governed per-phone memory (W-1/O4) | `mem0` (lib) / `Graphiti` temporal-fact pattern | INSTALLA-LIB / STUDIA-PATTERN | Apache-2.0 |
| Input rail (§8.1) | NeMo Guardrails 5-rail taxonomy | STUDIA-PATTERN | Apache-2.0 |
| Handoff state machine (C10) | Chatwoot open/pending/resolved | STUDIA-PATTERN | MIT core (NOT enterprise/) |

All public OSS research (no PII). Graphiti's fact-validity-interval pattern directly fights scar #9
(stale reg served as current). Multi-turn dual-control eval (τ²-Bench) over single-turn QA for the harness.

---

## 10. Workstreams — sequenced (council-corrected order)

Every build workstream ships through §11. Order is **containment → safety → nerves → identity → arm →
observe → gate → richer**. Rationale for each move is the council seat that demanded it.

- **W-1 · CONTAINMENT** 🔴 — P0-MEM, P0-ID (=T4 identity contract), P0-ARG, P0-FLOOD (=S3). Disable shared
  Path B memory; per-phone pseudonymous subject; typed identity envelope; reserved-arg strip + schema-hide;
  rate/length cap. **+ establish the golden multi-turn eval baseline** (Kimi — readiness is unmeasured).
  *All three seats: this precedes everything.*
- **W0 · SAFETY PRE-ARM** 🔴 — S1 (clamp CRMTool.limit), S2-indirect scoping, T-VIS (per-request tool
  minimization). Defuse the **`whatsapp_persona.py` price-list landmine** (Kimi — it had no owner).
- **W1 · RECONNECT THE NERVES** 🔴 — C1 (media state machine + fetch-before-ack + lifecycle), C2 (durable
  chunk ledger THEN chunked send), C3, C4, C5, C15, C7-vat. Pure Pattern-A wiring + the chunk-ledger build.
  Highest leverage/effort ratio. *Codex: chunk ledger before replacing truncation.*
- **W2 · ARM THE TEAM ASSISTANT** 🔴 — **only after W-1/T4**: T1 (flip flag, post-T4+S1), T8 (roster). Then
  T2/T3 (check-in, knowledge) on the unified principal. *All seats: T4 before T1.*
- **W3 · OBSERVABILITY SPINE** 🔴/🟡 — O1 (Gemini-429 alert), O2 (outbox alert), O5 (wire monitor +
  analytics migration), O3 (arm rag_eval), C13 (regen dry-run + emergency delta), O6 (E2E canary + staging
  number). *Codex+Kimi: security telemetry (tool allow/deny, cross-scope attempts) must be visible BEFORE/
  WITH W2 arming — pull O1/O2 + deny-metrics forward to sit with W2.*
- **W4 · THE GATE + FOUR OUTCOMES** 🟡 (design-heavy → Opus owns) — C9, C10 (+ operating contract), C16
  (disclaimer + consent), per-claim grounding, input rail (§8.1). v5 behind the door, additive/flag-gated,
  parity test extended for the alias-reexport blind spot. NLM ground-truth on any regulatory claim.
- **W5 · RICHER UX + REACH** 🟡/🟢 — C8 (adaptive cap, after W3/W4 baseline), C11 (CTA + interactive), C14
  (ru/uk + cross-lingual retrieval), pywa Flows for intake, voice-note. **Second-number/Flow onboarding may
  proceed only after the price-list landmine is defused (W0).**
- **W6 · SECURITY HARDENING (ops-gated)** 🔴/🟡 — S4 (JWT flip), S5 (orphan tree into CI), S6 (recycling
  re-verify), S7 (double-send reconciliation).
- **W7 · CONTENT + PROMOTION LOOP** 🟡 (continuous) — C12 corpus growth, O4 promotion loop.

---

## 11. The agentic ship workflow (deterministic — internal powers + LLM)

Per `/workflow`. Fable orchestrates + final-gates; Sonnet builds; externals grade (generator≠grader,
cross-family). **This change class = security/PII/migrations/write-tools/identity ⇒ AUTO-MERGE OFF.**

```
For each workstream Wn (Opus selects order — W-1 → W0 → W1 → W2/W3 first):
  1. GROUND     — re-grep exact file:line THIS turn (this spec's line refs are LEADS, W65).
                  Consumer-map: which PATH calls the helper? (the Pattern-A gate)
  2. DESIGN     — spec delta on disk; L2/L3 → Zero GO (AUTONOMOUS_OPS preflight).
                  W-1/W2/W4/W6 touch identity/PII/migrations → design gets a Codex red-team pass.
  3. BUILD      — worktree via scripts/agent_start.py (lane backend-rag); Sonnet implementer;
                  TDD (guilt+innocence for any guard, scar #3); karpathy-discipline; leave-dirty to siblings.
  4. VERIFY     — verify-template.js (gather→adversarial-refute→synthesize): Codex sol xhigh red-team ·
                  GLM→Kimi K3 refuter · Gemini agy costruttivo/normativa · NLM ground-truth on reg claims.
                  Multi-tenant security suite for W-1/W2 (two phones, forged fields, isolation).
                  Fable does the last on-disk grep — never delegated/cascaded. Pattern-fix ⇒ class-audit
                  ALL sibling call-sites incl. test asserts (W89).
  5. SHIP       — atomic commit + co-author + docs_sync in-commit if a DOCSYNC surface moved (W86).
                  ★ AUTO-MERGE OFF for this class ★ — PR opened, an INDEPENDENT adversarial gate
                  (generator≠grader; a session that did NOT author the diff) must pass BEFORE merge.
                  The SESSION still merges (ship-lifecycle ownership — the codeowner does not); sensitivity
                  raises the gate's rigor, it does not move the merge to a human. Migrations → Squawk +
                  Codex upgrade+downgrade. Per-principal canary/rollback allowlist + kill switch, not a
                  single global env flag (Codex).
  6. PROVE-LIVE — deploy from post-merge main (nuzantara-deploy); prove on the PUBLIC surface by CONTENT:
                  real WA probe from a bot-allowlisted number (wa-tester), fly-logs delta vs baseline, prod
                  DB aggregate (pg.sh, no PII). Prove on EVERY consuming surface. Probe fails → STOP-THE-LINE
                  + rollback.
  7. ALIGN-FLEET— M5/Pro/Mini main ff-only; restart consumers; skill liveness.
  8. CLEAN      — reap worktree at 3-AND; branch delete only after PROVE-LIVE + blob-on-main.
  9. CAPTURE    — mem save; update /bot corner §1 SAME turn; scar if trauma; AMENDMENTS if the loop misfired.
```

Ollama-local (`qwen2.5vl:7b` vision, `faster-whisper`) for any transform touching client PII —
redaction-before-egress is the gate, never a cloud prompt with raw PII.

---

## 12. §Solo-operatore — Zero's Legge-5 / credential / GUI decisions

Cannot be session-armed. Opus surfaces, does not implement around:

1. **P0-MEM incident call**: contain now (disable Path B long-term memory) vs. accept-and-fix-in-W-1. Given
   autoreply is ON, recommend **contain immediately** even before the full W-1 design lands.
2. **C6 — Gemini SPOF ruling**: fail-closed (recommended) vs. authorize a redaction-gated dedicated-endpoint
   fallback (COS-LAW-013 territory). Do NOT flip `openrouter_enabled` without the ruling.
3. **T2/T5/T7 write-tool GOs**: each breaks the read-only invariant → individual Zero GO + own flag.
4. **24h-window reachability / Meta template**: 81% of outbound "failures" are `24h_window_closed` (policy,
   not bug). Whether to adopt an approved Utility Template for outside-window re-engagement is a business call
   (ruling 2 currently rejects paid templates). **Quantify weekly dropped-client count first** (Gemini+Kimi).
5. **S4 — JWT expiry flip**: logs out live sessions → ops window + refresh-token verification.
6. **Credential/infra** (all operator): `fly secrets set` for T1/W3 arming, secret rotation, Actions secrets,
   prod-DB writes, provisioning a staging WABA/test `phone_number_id` (O6).
7. **Publishing/external**: no auto-send to any client (Legge 5) — draft-reply is draft-only by construction.

---

## 13. Acceptance criteria (falsifiable)

- **W-1**: two phone numbers → isolated memory (A's facts never surface for B — runtime test); forged
  `profile`/`channel`/`_caller_profile`/nested variants → rejected (multi-tenant suite); flood/oversize →
  throttled/capped; a golden multi-turn eval baseline exists and is recorded.
- **W0**: `CRMTool(limit=10**6)` returns ≤50 (test); client/unknown callers see team tools ABSENT from the
  registry (schema test); the `whatsapp_persona` price-list cannot enter any live prompt (test).
- **W1**: from a bot-allowlisted number — PDF → ack (not silence); >4096-char answer → ≥2 messages, none cut
  mid-sentence, no duplicate on induced crash (ledger test); read receipt observed; forced failure → apology.
- **W2**: `WA_TEAM_CRM_TOOLS_ENABLED=true` live behind T4; team number "quali sono le mie pratiche?" → only
  `assigned_to` matches; a client number is byte-identical to pre-change (and never saw the tool schema).
- **W3**: `curated_qa_regen_trigger` proven by a state-delta not its own log (W89); simulated Gemini-429 →
  Telegram alert; `/api/monitoring/abstain-rate` shows real non-zero signal; E2E canary walks the ledger path.
- **W4**: multi-turn adversarial set — bot CLARIFIES an ambiguous visa question, ESCALATES on a red-flag term
  with the operating contract, strips an unsupported KBLI code (per-claim grounding) rather than hedging.
- **Fleet**: `git rev-parse HEAD` identical on all reachable main checkouts; consumers show fresh heartbeats.

---

## 14. Open questions for Opus 4.8 (architect)

1. **P0-MEM containment** — contain in-prod immediately (disable Path B long-term memory), or bundle into
   the first W-1 PR? (Recommend: contain first, design the pseudonymous subject second.)
2. **T4 shape** — full typed identity envelope now, or a narrow "re-resolve phone server-side + drop client
   channel from the trust decision" first, envelope later? (Recommend narrow-first to unblock W2, envelope
   in the same quarter to kill the two-auth-system trap.)
3. **Manager vs single-agent** for the four service lines — split only on measured routing failures; is there
   instrumentation yet? (Ties to O5.)
4. **Corpus growth (C12)** — WR2/editorial lane or bot lane?
5. **Baseline eval** — is the τ²-Bench-style multi-turn set built inside W-1, or a prerequisite lane of its own?
