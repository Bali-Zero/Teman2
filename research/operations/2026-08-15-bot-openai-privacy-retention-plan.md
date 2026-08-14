---
date: 2026-08-15
domain: operations
client_case: zantara-wa-provider
sources:
  - https://developers.openai.com/api/docs/guides/your-data (fetched this turn — retention/ZDR/MAM/residency/training-use facts)
  - https://openai.com/policies/data-processing-addendum/ (found via WebSearch this turn — DPA effective 2026-01-01)
  - CLAUDE.md (project) §14 PII/OSINT output boundary — Art. 56 cascade, fail-closed doctrine, existing undischarged consent gap
  - .agents/skills/bot/SKILL.md §1 LIVE STATE — WA_HISTORY_TURNS=12, meta_inbox tables, existing memory-bleed containment (P0-MEM)
  - apps/backend-rag/backend/services/integrations/wa_inbox_bot.py (re-read this turn — payload shape sent to the orchestrator)
  - research/operations/2026-08-15-bot-openai-provider-threat-model.md (companion document, same session)
adversarial_review: n/a (design/policy document — no code diff to review; recommend the same Kimi pass before this becomes an execution plan)
---

# Zantara WA bot — OpenAI provider privacy & retention plan

## Scope and posture

This is a **planning document**, not an implementation. It answers: what would have to be true
before real client WhatsApp traffic is allowed to touch OpenAI's API. It does not authorize
sending anything — CLAUDE.md §14's fail-closed doctrine is the default state and stays the default
state until every item below is closed with **evidence**, not a claim.

---

## 1. Data flow — what transits, what never does

```
Client WA message
   │
   ▼
Meta Cloud API (webhook, WhatsApp Business number +62 821-3465-159)
   │  raw text, phone number, media metadata, WAMID
   ▼
backend/app/routers/whatsapp_chat.py  (webhook ack <200ms, dedup, meta_inbox_* tables)
   │
   ▼
wa_outbox_worker.py → wa_inbox_bot.py::generate_bot_reply
   │  builds payload: {query, user_id: "whatsapp_<phone>", session_id, conversation_history
   │  (up to 12 prior turns, _HISTORY_TURNS), channel: "whatsapp", max_steps: 2}
   ▼
POST /api/agentic-rag/query  (X-Internal-Key, X-WA-Bot-Profile-Key headers)
   │
   ▼
[TODAY: Gemini via llm_gateway.py]  [PROPOSED: OpenAI Responses API]
```

### Fields that reach the LLM provider today (Gemini) and WOULD reach OpenAI under the proposal

- The client's raw free-text query — **unfiltered**. This is the field of highest concern: a WA
  client can and does type passport numbers, KITAS numbers, full names, dates of birth, overstay
  details, and case specifics directly into the chat (the corner's own probe evidence: the
  FOLLOW_UP_STATUS class of question is answered by the bot **asking the client for** "full name,
  passport number or application ID" — i.e. the existing prompt already invites exactly this).
- Up to 12 turns of `conversation_history` for the SAME thread — compounds the above; a fact
  disclosed 3 turns ago rides along on every subsequent call for the life of that history window.
- `user_id: "whatsapp_<phone>"` — a phone number, direct identifier, sent as a plain request field
  (not just logged — this is a field IN the payload OpenAI's API would receive as part of context/
  metadata if the adapter forwards it, e.g. as a `user` parameter for its own abuse-monitoring
  attribution, which OpenAI's API supports and by default USES for exactly that purpose).
- Retrieved KB/curated_qa snippets, PricingTool output, CRM tool results **for team/creator callers
  only** (client callers do not get CRM tool access per the SENSITIVE_TOOLS gate) — non-PII by
  design for the client path, but the team path is broader and any OpenAI-provider decision that
  also serves team queries needs this scoped in.

### Fields that must NEVER transit to OpenAI (or any cloud LLM) under current doctrine

**CORRECTED post-Kimi-refutation of the companion threat model, verified this turn against the
code**: OpenAI is not a "second destination" being newly introduced — `orchestrator_core.py:498`
already sends the raw client query text to OpenAI's embeddings API on every WA RAG query today
(`embedding_provider` default `"openai"`, `config.py:35`), on the Gemini-only path, before this PR.
OpenAI is already processor #2 in this system. The framing below is corrected accordingly.

- Anything the existing PII boundary already prohibits from leaving the org for cloud LLM
  processing without a demonstrated legal basis (CLAUDE.md §14): KTP, passport, NPWP, akta,
  credentials, raw OSINT data. **This document's contribution is not a new list — it is the
  observation that the CURRENT client free-text path already fails to enforce this list against
  BOTH Gemini AND OpenAI's embeddings endpoint**, and a conversational OpenAI adapter does not add a
  new vendor relationship — it expands what OpenAI receives (full 12-turn history, tool results,
  generated answers) beyond today's query-string-only embedding call, and adds a different
  retention/statefulness surface (§2 below). The consent/Art. 56 analysis should be scoped to
  "expanded data sent to an already-present processor," not "a new processor," or it understates
  what is already live.
- Team CRM data reachable via `crm_query`/`timesheet`/`team_knowledge` for `agent_role`-scoped
  callers — if/when an OpenAI path also serves the team assistant surface, this is a SEPARATE and
  larger PII surface (client rows, not just the asking employee's own text) that this document does
  not attempt to clear; team-path traffic should stay on Gemini (or local) until scoped separately.

---

## 2. Retention — planning assumption and what would change it

**Default planning assumption (per OpenAI's own documentation, fetched this session):**

> The Responses API retains "Application State" for **30 days by default** (or when `store=true`
> is set); Chat Completions stores no Application State by default but both API surfaces retain
> **abuse-monitoring logs for up to 30 days** regardless of the `store` setting. Data sent to the
> API is **not used for model training by default** (no opt-in given) as of the standing 2023
> policy, unchanged per the docs fetched this session.

So: **assume 30 days of retention for anything an OpenAI-backed adapter sends**, full stop, as the
baseline for every downstream decision (consent language, breach-notification exposure, "how long
does a client's passport number sit on a third party's server if it leaks through the existing
prompt-injection gap"). Do not plan against a shorter number without the evidence in §2.1 below.

### 2.1 ZDR / Modified Abuse Monitoring — what would have to be TRUE, and how to prove it

OpenAI's own documentation (fetched this session, quoted in the threat model's sources) is explicit
that both **Zero Data Retention (ZDR)** and **Modified Abuse Monitoring (MAM)** are:

- **Not self-service.** They require prior written approval from OpenAI (sales/enterprise process),
  configured afterward at the **organization or project level** in the OpenAI dashboard
  (Settings → Organization → Data controls).
- **Not independently verifiable via the API.** There is no documented response header, API field,
  or attestation endpoint that proves a given request was actually processed under ZDR/MAM terms —
  the control is administrative (a dashboard toggle OpenAI applies on their side), not
  cryptographic or programmatically checkable per-request.

**What constitutes PROOF, defined here so nobody downstream treats a claim as a fact:**

1. A **written approval artifact from OpenAI** naming the specific OpenAI Project (not "the org")
   as ZDR- or MAM-approved — an email/portal confirmation, dated, kept alongside this document.
2. The **dashboard setting itself, screenshotted or exported**, showing ZDR/MAM enabled on that
   Project at the time of the traffic in question — because OpenAI can revoke or the setting can
   drift, this is a point-in-time proof, not a permanent one; re-verify before any volume increase
   (ties to the rollout plan's dwell-and-verify gates, V6).
3. **No claim of ZDR/MAM status is acceptable as "verified" on the strength of documentation
   alone** — documentation says the FEATURE exists and how to request it; it does not say THIS
   project has it. Treat "we read that ZDR exists" and "our project has ZDR" as two different
   facts, and never let a PR/report conflate them (this is the same discipline CLAUDE.md's
   anti-hallucination rules already demand of tool output — apply it to vendor claims too).

**Until items 1-2 above exist and are dated, plan against 30-day default retention with FULL
abuse-monitoring logging (i.e. OpenAI staff/automated systems may review flagged content, per their
own documented "Eyes Off" carve-outs and the standing CSAM-detection exception that overrides ZDR
unconditionally).**

### 2.2 Data residency

OpenAI supports regional processing in a subset of its data-residency regions — as of the docs
fetched this session, live inference (not just storage) is limited to US, EU, and a partial UAE
rollout; other listed regions (India, Singapore, South Korea, Japan, Australia, Canada, UK) are
storage-only, meaning inference still happens outside that region. **Indonesia is not a listed
OpenAI data-residency region at all.** Any client-facing traffic from this bot processed via OpenAI
will physically leave Indonesia and, most likely, be processed in the US (the default region absent
explicit EU routing configuration) — this is the fact that grounds the Art. 56 analysis below; it
is not a hypothetical.

---

## 3. DPA / legal basis — what must exist before real client traffic touches OpenAI

**This section restates and applies CLAUDE.md §14 (already-established doctrine) — it does not
re-derive the doctrine.** Quoting the load-bearing sentence: *"Il gateway chat non prova oggi
clausola, base Art. 56, revoca o consenso per-cliente: finché la base non è dimostrabile prima
dell'invio, il testo con PII cliente deve restare locale/off-cloud oppure la richiesta deve essere
bloccata/astenersi."* That gap is about the EXISTING path — and, corrected above (§1), OpenAI is
already inside that gap via embeddings, not a hypothetical future addition. A conversational OpenAI
adapter does not create a new species of gap — it expands the SAME undischarged gap's blast radius
(more data, to a processor already receiving some), so:

### 3.1 What OpenAI itself offers (useful, not sufficient on its own)

- **A Data Processing Addendum, effective 2026-01-01** (found via WebSearch this session), under
  which OpenAI acts as processor and processes customer data only to deliver the service —
  standard SaaS-vendor DPA shape.
- **Standard Contractual Clauses (SCCs) for EU transfers**, supplemented by a UK IDTA for UK
  transfers, and **EU-US Data Privacy Framework certification** — these are EU/UK-specific transfer
  safeguards. **They are not an Indonesia-UU-PDP-specific safeguard.** UU PDP's Art. 56 cascade
  (adequacy → binding & adequate safeguard → explicit consent, per CLAUDE.md §14) requires its OWN
  adequacy/safeguard determination for an Indonesia→US transfer; the existence of EU SCCs does not
  automatically satisfy that — it is evidence a *contractual mechanism exists and can likely be
  extended/mirrored*, not evidence the ID-specific leg is already covered.

### 3.2 What Bali Zero must additionally have before the first real client message reaches OpenAI

1. **A signed DPA with OpenAI** naming Bali Zero / PT [entity] as the customer and covering the
   specific Project the WA adapter will use (ties to threat-model A3 — a dedicated Project, not a
   shared one, matters here too: the DPA's scope should match the credential's scope).
2. **An Art. 56 basis determination for the ID→US leg specifically** — since no Indonesia-specific
   adequacy finding for the US is asserted anywhere in the sources gathered this session, the
   live path is: binding-and-adequate safeguard (a bespoke contractual clause layered onto the
   OpenAI DPA, or reliance on the OpenAI DPA's own transfer mechanism if PT PMA legal counsel signs
   off that it qualifies) **or**, failing that, explicit per-transfer consent. This is a legal
   determination, not an engineering one — flagged here as a precondition, not resolved here.
3. **Per-client consent capture at first contact**, already named as an open item in the corner's
   gap matrix (C16: "no UU PDP consent capture on first contact for storing `wa_session_{phone}`
   and processing passport/visa docs") — that gap is currently open for the EXISTING Gemini path
   and is a **shared precondition**, not something the OpenAI provider decision can route around.
   A consent flow built for "we send your message to an AI" should be written providerless (i.e.
   cover whichever LLM is active) rather than re-derived per vendor.
4. **The retention default from §2.1 reflected in whatever the consent language says.** If ZDR/MAM
   is not yet proven per the standard in §2.1, the consent/privacy notice must say "up to 30 days,
   subject to abuse-monitoring review" — not "not retained," which would be false absent proof.

### 3.3 Explicit non-recommendation

**Do not authorize OpenAI-backed processing of real client WA traffic based on this document
alone.** This document defines what proof would look like; it does not supply that proof. The
decision to proceed is a Zero Legge-5 call per CLAUDE.md §2/§14, gated on: (a) the credential/
adapter passing the Gate V2 spec in the companion threat-model document, (b) items 1-2 in §3.2
existing as dated artifacts, (c) the consent-capture gap (C16) closing for whichever LLM sits behind
the endpoint, providerless.

---

## 3.4 Live diff finding — the current shadow implementation has zero code-level enforcement of §3

Cross-checked against the implementer worktree (`.worktrees/bot-openai-adapter`,
`_shadow_provider.py`/`openai_responses_client.py`) this session, alongside the companion threat
model's §Live diff review (Finding 7 there, restated here because it is the load-bearing fact for
this document specifically): the shadow branch's ONLY precondition to sending live request content
(current turn + system prompt — real client free-text when armed on prod traffic) to OpenAI is a
bare boolean env flag (`OPENAI_SHADOW`) plus a configured API key. **There is no code-level check
for anything in §3.2** — no DPA-signed marker, no ZDR/MAM proof artifact reference, no consent-capture
gate, no synthetic/de-identified-corpus allowlist. The payload also never sets `"store": false`
(verified this session — `openai_responses_client.py::generate()`'s payload dict has no `store` key
at all), meaning the §2.1 default-retention assumption in this plan is not just a policy baseline —
it is what the code, as written, actually does by omission. **This document's §3.3
non-recommendation is not currently backed by any technical control**: today, the only thing
preventing real client traffic from reaching OpenAI is that `OPENAI_SHADOW` defaults to and stays
`false` in this PR. Recommend V2's gate spec include an explicit policy-gate check (not just the
env flag) before this branch is ever considered safe to arm outside a non-prod environment.

## 4. Open items handed to downstream lanes

- **V3 (failure matrix)**: whether an OpenAI outage/rate-limit needs the SAME fail-closed posture
  Zero already ruled for Gemini SPOF (C6: "fail-closed permanent, no external fallback egress") —
  recommend yes, by default, since the ruling's rationale (no safe redaction pass for free-text WA
  PII before any cross-provider failover) applies identically to an OpenAI↔Gemini failover in
  EITHER direction.
- **V6 (rollout plan)**: the dwell-and-verify gates should include a re-check of the ZDR/MAM proof
  artifact's currency (§2.1 item 2) at each traffic-percentage increase, not just once at shadow
  start — OpenAI's dashboard setting is administrative and can drift without code changing.
- **Business/legal (Zero, not session-armable)**: items 1-2 in §3.2 (signed DPA scoped to the right
  Project; Art. 56 basis determination for ID→US) are credential/consent/business-decision
  categories per CLAUDE.md §2's operator taxonomy — flagged, not actioned, here.
