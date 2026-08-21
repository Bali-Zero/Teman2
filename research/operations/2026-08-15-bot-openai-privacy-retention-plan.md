---
date: 2026-08-18
domain: operations
client_case: zantara-wa-provider
sources:
  - https://developers.openai.com/api/docs/guides/your-data (fetched this turn — retention/ZDR/MAM/residency/training-use facts)
  - https://openai.com/policies/data-processing-addendum/ (found via WebSearch this turn — DPA effective 2026-01-01)
  - CLAUDE.md (project) §14 PII/OSINT output boundary — Art. 56 cascade, fail-closed doctrine, existing undischarged consent gap
  - .agents/skills/bot/SKILL.md §1 LIVE STATE — WA_HISTORY_TURNS=12, meta_inbox tables, existing memory-bleed containment (P0-MEM)
  - apps/backend-rag/backend/services/integrations/wa_inbox_bot.py (re-read this turn — payload shape sent to the orchestrator)
  - research/operations/2026-08-15-bot-openai-provider-threat-model.md (companion document, same session)
  - https://openai.com/policies/how-your-data-is-used-to-improve-model-performance/ (official individual-vs-business training distinction, checked 2026-08-18)
  - https://help.openai.com/en/articles/5722486-api-data-usage-policies (official API data usage and retention controls, checked 2026-08-18)
  - https://help.openai.com/en/articles/7039943-data-usage-for-consumer-services-faq (official consumer-services FAQ, checked 2026-08-18)
  - https://help.openai.com/en/articles/7730893-data-control (official ChatGPT data controls, checked 2026-08-18)
  - PR #4216 source head 1dcdd670d and its ADR (subscription-backed offline lane)
adversarial_review: kimi-k3
---

# Zantara WA bot — OpenAI provider privacy & retention plan

## R28 subscription-lane correction — 2026-08-18

This section is authoritative for PR #4216. The earlier plan below was written for a dedicated
OpenAI API Project and a discarded live-shadow design. The selected current path is instead a
human-run, local `CodexExecClient` authenticated through the operator's ChatGPT Pro subscription.
It is completely unwired: no real WhatsApp export, client row, runtime flag, worker, deploy, or
cutover is in scope.

The API retention controls described in §2 below cannot be projected onto the subscription lane.
In particular:

- the dormant `OpenAIResponsesClient` sets `store:false`, but the selected subscription adapter
  never calls that client or the Responses API directly;
- `codex exec --ephemeral` is evidence about local Codex session-file behavior, not a declaration
  of OpenAI-side retention, training, human-review, or DPA status;
- OpenAI's current official material distinguishes individual ChatGPT/Codex services from business
  products and the API. Individual-service content may be used for model improvement depending on
  account controls, and Codex has controls that are partly separate from ChatGPT controls. The
  effective settings for the operator account were not inspected or recorded by this lane;
- therefore the business/API defaults, project-level ZDR/MAM, and `store:false` analysis below are
  **not evidence** that a ChatGPT Pro/Codex subscription invocation has the same treatment.

### Current data minimization controls

PR #4216 implements only a preparation harness. Default corpus input must be structured JSONL with
canonical `user`/`assistant` roles and a local conversation identifier. The identifier remains
in-memory, only user targets are emitted, history is capped at 12 independently redacted/scanned
turns, and unsafe or unattributable input clears accumulated history. Plain WhatsApp TXT yields no
default fixture. Historical role-blind mode is explicit, builder-comparison-only, rejected by the
benchmark loader, and cannot support promotion.

Blind transcripts and label keys are written separately with private permissions (`0700` run
directory, `0600` files). Those controls reduce local leakage but do not legalize provider egress.
No real export was processed and no client-specific blind benchmark was run.

### Gates before any real client text

1. Independent human privacy/legal review of the de-identified corpus, not just automated regex
   scanning.
2. Live verification of the exact ChatGPT/Codex account's training and Codex environment controls,
   plus a documented retention/human-access basis applicable to that product and account. API
   settings are not substitutes.
3. A defensible UU PDP / Art. 56 basis and consent/disclosure path for the exact processor,
   destination, purpose, data categories, and retention regime. No such artifact is supplied here.
4. Stronger isolation than a read-only coding-agent sandbox before any real client text is passed
   to the CLI.
5. A separate runtime architecture and fresh threat/privacy review. Fly does not inherit this
   Air-M5 user's local CLI or ChatGPT OAuth state, and PR #4216 contains no runtime wiring.
6. The mandatory Fable 5 on-disk gate passed on source head `1dcdd670d`; repository CI and an
   independent merge decision remain separate. No merge, deploy, traffic, or cutover is authorized
   by this plan.

**Privacy verdict:** synthetic, non-PII offline probing only. Real WhatsApp data, even de-identified
by the automated builder, remains BLOCKED until every gate above has evidence.

## ⚠️ Historical snapshot header — SUPERSEDED by R28 above

**Base**: `origin/main` @ `7e66a8b3d003de0327e1ff7669e038b467ee8a94` (verifier and implementer
worktrees share this merge-base). **The implementer worktree (`.worktrees/bot-openai-adapter`) has
ZERO commits on its branch — every change is uncommitted working-tree state**, verified via
`git status --short` this session: `M config.py`, `M llm_gateway.py`, `?? openai_responses_client.py`,
`?? _shadow_provider.py`, `?? backend/tests/llm/`, `?? backend/tests/rag/`, `?? scripts/bot/`.

**This is a moving target by construction.** A code-level observation below (§3.4) was already
found stale once this session — see the correction note there. **This document reviews an UNFROZEN
diff and must be re-executed (fresh Kimi K3 + Google/agy Gemini passes, prompts prepared in the
companion threat model's §Freeze re-review) once the implementer commits and opens a PR.** The
policy/legal analysis (§1-§3's DPA/consent/retention doctrine) does not depend on the exact code
snapshot and stays valid; the code-level "live diff finding" in §3.4 does, and is marked accordingly.

## Scope and posture

The historical body is a **planning document**, not an implementation. It answers what would have
to be true before real client WhatsApp traffic is allowed to touch a dedicated OpenAI API Project.
It does not authorize sending anything. R28 above applies the same fail-closed posture to the later
ChatGPT Pro/Codex subscription choice and identifies the additional product-regime gap: API data
controls are not proof of subscription treatment.

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

**CAVEAT, post-adversarial-review (`## Adversarial review` below, both seats, ACCEPTED):** this
framing is itself asserted from a config DEFAULT, not from confirmed deployed behavior — no check in
this pass that the production environment doesn't override `embedding_provider`, which OpenAI
org/account the embedding calls authenticate to, or whether a DPA already covers that specific flow.
Treat "OpenAI is already processor #2" as a strong, code-grounded hypothesis this document leans on,
not as independently confirmed against production — and do not let it be read as retroactively
discharging the DPA/Art. 56/consent preconditions in §3.2 for the NEW conversational scope this PR
adds, which remain gated on their own evidence regardless of what the embeddings flow's status turns
out to be.

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

**Historical API-path scope:** this section applies to the dormant Responses/API-key design. It is
not the retention contract for the selected ChatGPT Pro/Codex subscription adapter; see R28 above.

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

**CAVEAT, post-adversarial-review (agy seat, ACCEPTED):** the operative risk during that 30-day
abuse-monitoring window is not primarily elapsed storage time — it is that content OpenAI's automated
classifiers flag is subject to **human review** by OpenAI trust & safety personnel or contractors
(the "Eyes Off" carve-outs referenced in §2.1 below exist precisely because that human-review path is
otherwise the default). If a client's KITAS or passport number gets flagged, the confidentiality
breach is a person reading it, not a disk holding it for 30 days. Frame consent language and risk
communication around BOTH facts — duration AND third-party human access — not duration alone.

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

## 3.4 Historical live-diff finding — the deleted shadow design had no §3 enforcement

The `_shadow_provider.py`/`OPENAI_SHADOW` path described in this section was deleted before final
PR #4216. The current subscription adapter has no live call site at all, so the former boolean-only
arming defect is not a property of the final diff. The risk class remains relevant to any future
wiring and is preserved below as archaeology; R28 above is the current disposition.

Cross-checked against the implementer worktree (`.worktrees/bot-openai-adapter`,
`_shadow_provider.py`/`openai_responses_client.py`) this session, alongside the companion threat
model's §Live diff review (Finding 7 there, restated here because it is the load-bearing fact for
this document specifically): the shadow branch's ONLY precondition to sending live request content
(current turn + system prompt — real client free-text when armed on prod traffic) to OpenAI is a
bare boolean env flag (`OPENAI_SHADOW`) plus a configured API key. **There is no code-level check
for anything in §3.2** — no DPA-signed marker, no ZDR/MAM proof artifact reference, no consent-capture
gate, no synthetic/de-identified-corpus allowlist.

**STALE claim, CORRECTED this turn (per team-lead's first-hand catch, same correction as the
companion threat model's row 2):** an earlier pass of this section said the payload "never sets
`store: false`... it is what the code, as written, actually does by omission." **That is false of
the current working-tree snapshot**, re-verified this turn: `openai_responses_client.py:296-306`'s
docstring states *"STATELESS ONLY for this phase (orchestrator veto 2026-08-15 point 2): every
request sends `"store": false`"* and the payload builder at `:325-331` sets `"store": False`
**unconditionally**, on every call; `previous_response_id` is no longer a `generate()` parameter at
all. This does NOT retire this section's underlying point or weaken §2's planning baseline — two
things stay true regardless of `store`: (1) OpenAI's abuse-monitoring logs are retained ~30 days
**regardless of the `store` setting** (per §2's own quoted docs — `store:false` only controls
Application State, not the separate abuse-monitoring retention), so §2.1's 30-day planning
assumption is UNCHANGED by this correction; (2) the code-level-enforcement gap this section's title
names is about the OTHER items in §3.2 (DPA marker, ZDR/MAM proof, consent-capture, de-identified
allowlist) — none of THOSE are checked in code either, and `store:false` being set does not touch
any of them. **This document's §3.3 non-recommendation is not currently backed by any technical
control for those four items**: today, the only thing preventing real client traffic from reaching
OpenAI is that `OPENAI_SHADOW` defaults to and stays `false` in this PR. Recommend V2's gate spec
include an explicit policy-gate check (not just the env flag) before this branch is ever considered
safe to arm outside a non-prod environment. **Re-verify `store:false` again at freeze** — the
implementer worktree is uncommitted and moving (see snapshot header); do not carry "fixed" forward
as fact about the eventual PR without re-reading the frozen diff.

## 4. Open items handed to downstream lanes

**R28 update:** V3's selected-provider matrix now exists in
`research/operations/2026-08-15-bot-provider-failure-matrix.md` and is reconciled to PR #4216 head
`1dcdd670d`. It confirms the lane is offline-only and that there is currently nothing to roll back
from. The historical handoff below remains useful for a future serve-stage, but it is not an open
request to wire the current adapter.

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

## Adversarial review

Two independent seats, run fresh by this session directly (no subagent delegation, per team-lead's
ratified protocol) against the CURRENT content of this document — the frontmatter previously said
"n/a, recommend the same Kimi pass before this becomes an execution plan"; that recommendation is
now discharged. Every objection below was independently re-verified against the actual document text
(quoted, section-anchored) before a verdict was assigned (W65 discipline).

### Kimi K3 (`kimi -m kimi-code/k3`)

1. **ACCEPTED — the "already processor #2" correction rests on an unverified config default, and
   the document doesn't follow its own logic to the conclusion.** §1's central reframe ("OpenAI is
   already processor #2... `embedding_provider` default `"openai"`, `config.py:35`") is inferred from
   a DEFAULT, not confirmed deployed behavior — no check that prod doesn't override it, which OpenAI
   org/account receives the calls, or whether a DPA already covers that flow. This is exactly the
   "code path exists ≠ code path executes in prod" conflation §2.1 item 3 itself forbids for the
   ZDR/MAM claim. Worse: taken at face value, §3.2's DPA/Art.56/consent preconditions ("before the
   first real client message reaches OpenAI") are already breached for the embeddings flow the
   document says is live TODAY, and the document recommends nothing about it — the fail-closed
   doctrine is applied only to the new adapter, silently waived for the flow just declared live.
   **Caveat added to §1** (see the correction paragraph there): the "already processor #2" framing
   is downgraded from a settled fact to "asserted from a config default, not independently confirmed
   against the deployed environment" — the Art. 56/DPA scoping conclusion should not be treated as
   fully discharged by this framing alone.
2. **ACCEPTED — the §2.1 "proof" standard proves a toggle, not retention behavior.** The section's
   own preamble admits ZDR/MAM are "not independently verifiable via the API... administrative, not
   cryptographic or programmatically checkable," then labels a dashboard screenshot "PROOF." A
   screenshot is evidence of a UI state at capture time, not that OpenAI's backend discards data —
   the standard proves attestation, not behavior, and §3.2 item 4 lets client-facing consent language
   soften based on that attestation alone. The standard's own wording ("this is a point-in-time
   proof, not a permanent one") already partially concedes this — the gap is that "PROOF" (capitalized,
   presented as a defined term) oversells what items 1-2 actually establish. Recommend (not applied
   here, downstream for whoever operationalizes this into V6): rename the standard to
   "best-available attestation, requiring continuous re-verification," and tie §3.2 item 4's
   consent-language trigger to an ongoing re-check, not a one-time dated artifact.
3. **PARTIALLY ACCEPTED — providerless consent (§3.2 item 3) is in tension with per-provider
   retention language (§3.2 item 4), and with the specificity valid consent requires.** Item 3
   recommends consent be written providerless ("cover whichever LLM is active"); item 4 requires the
   SAME consent to name provider-specific retention ("up to 30 days, subject to abuse-monitoring
   review" — a fact true of OpenAI, not necessarily of Gemini or a ZDR-proven state). A consent flow
   satisfying item 3's genericity cannot simultaneously satisfy item 4's specificity as literally
   worded. This is a real internal tension worth a business/legal call (flagged to §4's
   business/legal open-items list, not resolved here — consent-flow wording is a Legge-5 decision,
   not a session-armable one), not fully accepted as "the recommendation is wrong": a providerless
   CONSENT SCOPE (which entities may receive data) combined with provider-specific RETENTION
   DISCLOSURE (updated per-vendor at send time) is a coherent design; the document just doesn't spell
   out that distinction, which is what created the apparent contradiction.

### Google/agy Gemini seat (`agy`)

1. **ACCEPTED — the "already processor #2" framing risks legally grandfathering a much larger
   exposure via an existing, narrower one.** Equating a single embeddings query string with 12-turn
   conversational history + direct identifiers (`user_id: "whatsapp_<phone>"`) + tool results treats
   a purpose- and scope-specific consent/processing question as already-answered by the narrower
   existing flow. Overlaps with Kimi objection 1 above (both target §1's framing) but from the legal-
   scope angle rather than the verification angle — both folded into the same §1 caveat.
2. **ACCEPTED — the providerless-consent recommendation is the sharper version of Kimi's objection
   3, focused specifically on the Art. 56 cross-border-transfer angle.** §2.2 establishes that OpenAI
   traffic "will physically leave Indonesia... most likely processed in the US," which under Art. 56's
   cascade requires (absent adequacy/an adequate-and-binding safeguard) EXPLICIT PER-TRANSFER consent
   naming the destination — a generic "we send your message to an AI" cannot satisfy that. Same
   verdict and same disposition as Kimi objection 3: flagged to §4 as a business/legal open item, not
   resolved here (consent-flow copy is Legge-5 territory), the tension is real and should not be
   silently smoothed over by whoever drafts the actual consent text.
3. **ACCEPTED — the 30-day retention baseline frames the threat as storage duration and doesn't
   name the operational reality of abuse-monitoring human review.** §2/§3.4 correctly catch that
   `store:false` doesn't bypass the ~30-day abuse-monitoring retention, but frame the risk purely as
   "how long does a client's passport number sit on a server" — never naming that flagged content is
   subject to HUMAN review by OpenAI personnel/contractors (the "Eyes Off carve-outs" the document
   mentions in §2.1 but never connects to the retention analysis). The primary confidentiality risk in
   the abuse-monitoring window is a human reading the content, not disk-duration. **Caveat added to
   §2** (see the retention-assumption paragraph there): the 30-day baseline note now names human
   review by OpenAI trust & safety personnel/contractors as the operative risk during that window,
   not merely elapsed storage time.

**Not independently re-derived here (both seats, overlapping, noted for completeness rather than
actioned):** missing data-flow coverage — the OpenAI-generated answer's return path into the bot's
own answer cache / `conversation_history` (so provider-derived content loops back to the provider on
later turns), and whether media attachments (passport photos) reach the LLM vs. only "media
metadata" as the diagram states. Both are real gaps in §1's flow diagram; flagged for whoever expands
this into V5/V6 rather than closed in this revision, since resolving them requires re-reading the
channel/media-handling code, which is out of this document's mandate (privacy/retention planning, not
a fresh code audit).
