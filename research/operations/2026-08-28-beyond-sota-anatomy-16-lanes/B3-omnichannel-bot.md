---
date: 2026-08-28
domain: operations
part: B3 omnichannel-bot
scope: WhatsApp (Meta Cloud API) / Telegram / Instagram / web channels, channel router + formatters, wa_outbox pipeline + codex broker leg, answer caches, language detection, human handoff, wa-mirror / wa-meta-inbox / wa-dashboard-m1, conversations + meta_inbox tables
sources:
  - https://developers.facebook.com/docs/graph-api/webhooks/getting-started
  - https://developers.facebook.com/docs/whatsapp/cloud-api/typing-indicators
  - https://developers.facebook.com/docs/whatsapp/pricing
  - https://developers.facebook.com/docs/whatsapp/messaging-limits
  - https://developers.facebook.com/docs/whatsapp/flows/reference/flowjson
  - https://developers.facebook.com/docs/whatsapp/cloud-api/calling/
  - https://github.com/sierra-research/tau2-bench
  - https://fin.ai/
  - https://decagon.ai/product/aop
  - https://www.klarna.com/international/press/klarna-ai-assistant-handles-two-thirds-of-customer-service-chats-in-its-first-month/
  - https://github.com/chatwoot/chatwoot
  - https://github.com/pemistahl/lingua-py
  - https://github.com/zilliztech/GPTCache
  - https://elevenlabs.io/docs/agents-platform/overview
  - https://www.twilio.com/docs/conversations
  - https://rasa.com/docs/learn/concepts/dialogue-understanding/
  - https://www.zendesk.com/blog/ai/workflow-automation/automated-resolution-rate/
  - https://techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/
  - https://clonedesk.ai/blog/intercom-fin-limitations
status: DONE 2026-08-28T23:40:00+08:00
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B3 — omnichannel-bot: anatomy, honest state, world benchmark, recommendations

Read-only lane. Every `file:line` below was read in this session on `origin/main @ 11a3c89a2e`
(worktree `.worktrees/ops-beyond-sota-0828`); every external claim carries the URL that was
actually fetched. Where a page could not be fetched, the claim is marked **(search-derived)** or
**(unverified)**. No client data, no phone numbers, no secrets — config is named by variable only.

## 1. Anatomy (as measured)

### 1.1 Size

| Organ | Files | LOC | Notes |
|---|---|---|---|
| `backend/channels/` | 25 `.py` | 4,105 | `router.py` 477 · `optimizations.py` 672 · `base.py` 276 · adapters: telegram 416, web 299, whatsapp 273 (+ `media_download.py` 252, `media_webhook_parse.py` 162), instagram 186 · `format.py` 241 · `source_filter.py` 109 · `formatters/` is an empty package (0 LOC) |
| B3 routers (`backend/app/routers/`) | 17 | 7,451 | `whatsapp_chat.py` **1,955** · `conversations.py` 829 · `voice.py` 799 · `omnichannel.py` 515 · `wa_inbox.py` 428 · `wa_actions.py` 398 · `instagram_chat.py` 360 · `wa_broker.py` 317 · `websocket.py` 309 · `whatsapp_conversations.py` 308 · `messaging_identity.py` 276 · `wa_mirror_messages.py` 271 · `admin_conversation_cleanup.py` 240 · `wa_package.py` 163 · `telegram.py` 110 · `webhooks.py` 107 · `audio.py` 66 |
| WA pipeline services (`services/integrations/`) | 4 | 3,653 | `wa_outbox_worker.py` 1,399 · `wa_broker.py` 1,192 · `wa_codex_daemon.py` 651 · `wa_inbox_bot.py` 411 (+ `wa_codex_leg.py`, `wa_finalize.py`) |
| `services/wa_copilot/` | 11 | 6,653 | local-only fact extraction over the 77k-message team corpus (`extraction_pipeline.py:1-30`: qwen3.5:9b via Ollama, "UU PDP compliance forbids sending message bodies to cloud LLMs") |
| `services/communication/` | 9 | 1,460 | `language_detector.py`, `emotion_analyzer.py`, `routing_engine.py` (`classify_intent` :87, `score_priority` :130, `suggest_assignment` :191, `route_message` :216), `thread_manager.py` |
| `services/channels/` | 3 | 555 | `inbound_webhook_repo.py` + `webhook_processor.py` (PG LISTEN + 5 s poll fallback; 5 attempts, linear 5-min backoff, `:33-34`) |
| `apps/wa-mirror` | 26 | 6,062 | Node 22 + Baileys, runs on Mini, captures team members' *personal* WhatsApp into `whatsapp_message_context` on the **local** `nuzantara_dev` DB — explicitly "NOT a reply bot" (`README.md`) |
| `apps/wa-meta-inbox` | 2 | — | `server.cjs` + `viewer.html`: loopback-only proxy on Pro (:7791) to `/api/wa-inbox/*` with Keychain key + ephemeral CSRF (`README.md`) |
| `apps/wa-dashboard-m1` | 9 | — | cjs analysis/metrics viewer; `apps/wa-dashboard` and `-local` no longer exist |
| Tests | 101 files | 41,410 | test files whose name matches wa/whatsapp/telegram/instagram/omnichannel/webhook/conversation/voice/audio/channels; 19 under `tests/channels/` |

### 1.2 Data model (migrations read)

- `inbound_webhooks` (145): `UNIQUE(channel, dedup_key)` on the Meta `wamid`, `processed_at`, `attempts`, `next_retry_at` — the ack-first durability ledger.
- `meta_inbox_threads` / `meta_inbox_messages` / `wa_outbox` / `wa_status_pending` (206): thread has `human_handling` + `handling_version` (CAS), `last_customer_at` (the 24 h window clock); message has `direction`, `sender_role ∈ {customer,bot,human}`, status ladder `received→queued→generating→sending→sent→delivered→read|failed`; outbox has `claim_token`/`claim_expires_at` fencing, `attempts`, `next_retry_at`. Later migrations add `ack_sent_at`/`apology_sent_at` (260), `generation_route` (270), `generation_fall_off_reason` (290) — read via the worker docstrings, not the SQL.
- `broker_jobs` + `wa_broker_gauge` (270): the ChatGPT/Codex leg's durable offer/consume queue and the heartbeat gauge.
- `whatsapp_message_context` + `whatsapp_team_sessions` (173): the personal-mirror tables (wa-mirror), a *different* product from the bot.
- `conversations` (143, legacy web chat: `user_id`, `messages TEXT`, `rating`, `feedback`) — write-dead since the W38 NOSUPERUSER demotion per PENDING-ARMS (`.claude/skills/modus/PENDING-ARMS.md:126`).
- `conversation_threads` / `conversation_messages` / `messaging_users`: the `omnichannel.py` and `messaging_identity.py` model (9 references to `conversation_threads` in `omnichannel.py`). **Two thread models coexist** (`meta_inbox_threads` for the live bot, `conversation_threads` for the omnichannel API) with no join between them in the routers read.

### 1.3 Data flow of the flagship surface (Path B, the live public number)

```
Meta POST /webhook/whatsapp  (whatsapp_chat.py:1710)
  ├─ HMAC X-Hub-Signature-256 via verify_meta_hmac (:1659-1707)
  │     fail-open ONLY if secret unset AND meta_webhook_require_signature=false;
  │     default flipped to fail-closed 2026-08-26 (docstring :1676-1680)
  ├─ persist inbound_webhooks, dedup on wamid (:1760-1789)   ← ack <200 ms
  ├─ team-bot number branch (:1832-1840) — kill switch TEAM_BOT_INGRESS_ENABLED, born OFF (:1049-1058)
  ├─ meta-inbox branch (:1795-1813) → background process_meta_inbox_payload + media ingest
  └─ legacy inline triage for any other number (:1851-1900) → process_whatsapp_message (:199)

wa_outbox_worker.py  (claim → fence → coalesce bursts :576 → human_handling re-check
  → ack "manners" :306 [WA_OUTBOX_MANNERS_ENABLED, default OFF]
  → generation: WA_GENERATION_PROVIDER=codex → wa_codex_leg → broker_jobs → Pro daemon (wa_codex_daemon)
     Gemini leg RETIRED 2026-08-27 (wa_codex_leg.py docstring) — no second generator
  → Meta 24 h window check → send → retry ladder MAX_ATTEMPTS=5, 30 s·2^n (:169-170, :1122)
  → terminal apology :394 [WA_OUTBOX_TERMINAL_APOLOGY_ENABLED, default ON]
  → _tell_a_human (wa_inbox_bot.py:79-145): Telegram ping, 30-min per-thread dedup)
```

The reply generator (`wa_inbox_bot.py:312-390`) calls `POST /api/agentic-rag/query` over HTTP with a 120 s timeout (`:254`) into B1's orchestrator; abstain handling is delegated to `wa_finalize._abstain_answer_worth_sending` (`wa_finalize.py:177`). Human takeover is a flag flip through `/api/wa-inbox/threads/{id}/takeover|release|send` (`wa_inbox.py:267-410`), consumed by the loopback console on Pro.

Telegram, Instagram and web go through a *different* spine: `ChannelRouter.route_message` (`channels/router.py:78-140`, in-memory `MessageDeduplicator`, 300 s sha256 window, `optimizations.py:191`) → `ConversationEngine` streaming. Adapters are registered conditionally in `service_initializer.py:1153-1197`. Production Telegram is actually the OpenClaw bridge on Pro (`CLAUDE.md` §12), so the backend Telegram adapter is a second, config-gated path. `ChannelRouter._resolve_client_id` has no `instagram` branch (PENDING-ARMS `:77`).

### 1.4 Key invariants and knobs (from `.claude/skills/bot/SKILL.md` §2/§4 and code)

- Cache hits bypass the abstain gate ⇒ only pre-vetted content may enter a serving cache; every entry needs `{source_ref, source_date, domain, confidence_class, source_priority}` (SKILL.md §2.4). The abstain gates "are the product" (§5).
- Prices only from `PricingTool`; one client-facing price (§4.8). Meta 24 h window: reactive-only, no paid templates (§2.6, §4.2).
- Never clone the WA `api` process (SQLite split-brain); deploys outside 08–20 WITA (`research/operations/2026-08-25-wa-webhook-api-redundancy.md`).
- Zero's rulings: ChatGPT is the bot, Gemini is not (memory `MEMORY_BOT_AND_LLM_LANES.md` §4); subscription path only, never `OPENAI_WA_PROVIDER_API_KEY`.

### 1.5 Live state that frames everything (measured by prior sessions, cited, not re-measured)

- The product **served nobody from 2026-07-30 to 2026-08-23 (24 days) while every gauge read green**; 325 outbox rows lifetime, 217 failed, of which 94 `24h_window_closed` (answers generated, then discarded at the window check) — SKILL.md §1 (2026-08-23 entry). The throughput sentinel that would have fired at +1.5 h now exists (`scripts/wa_bot_throughput_sentinel.py`, PENDING-ARMS `:74` closed 2026-08-28).
- Traffic is ~4 messages/day (memory `project_live_bot_test_loop_2026_08_27.md`); the 2026-08-20 caching audit put background LLM traffic at 3–17 calls/day.
- Handoff reality: 40 threads, 32 with at least one bot give-up, **4 ever touched by a human** (`wa_inbox_bot.py:113-120` docstring, measured on live tables).
- `WHATSAPP_APP_SECRET`/`META_APP_SECRET` were **unset in prod on 2026-08-23** (SKILL.md §1) while the require-signature default became fail-closed on 08-26 and is "Staged" on the next deploy (memory `project_wa_lane_residuals_2026_08_26.md`). **(unverified today)** whether the secret has since been set: if not, the first deploy carrying the knob makes every Meta POST answer 401 and the channel goes deaf — Meta retries "with decreasing frequency over the next 36 hours" then drops (source 1).
- Three language detectors touch the WA path: `communication/language_detector.py:20` (regex markers, 5 languages + `"auto"`, used by the outbox worker `:377,:493` and `response_processor.py:50`), `whatsapp_context_builder.py:152` (history-aware regex, default `"en"`, legacy path `:319`), `rag/agentic/query_helpers.py:456` (`detect_query_language`, uppercase names, orchestrator path). Memory: DE/ES were degraded to EN; the divergence (D2b) is declared and not fixed.
- Typing indicator: `channels/whatsapp/adapter.py:194-197` says "WhatsApp doesn't support typing indicators" — **stale**: the Cloud API supports `typing_indicator` (source 2). The substitute — a text "checking…" pre-message — ships dark (`wa_outbox_worker.py:205-206`).
- Answer caches: `services/caching/semantic_cache.py` (L1 LRU + L2 Redis, domain TTLs 1 h/2 h/4 h/6 h, `:36-41`), `services/search/semantic_cache.py` (embedding/result cache), `NotebookLMCacheService` (exact-match FAQ with provenance) and the `curated_qa` Qdrant grounding collection. On `origin/main`, `apps/backend-rag/data/curated_qa/` contains only `README.md` — the corpora are not in git. The 2026-08-20 audit deferred a semantic-cache/local-intent tier "to go-public, not built quietly" (SKILL.md §1).
- Voice: `voice.py:30,33` wires local whisper.cpp STT + Chatterbox TTS ("voice concierge lab"); `audio.py` → `app/services/audio_service.py:6-33` is Pollinations (free) with an **OpenAI API-key fallback** (`from openai import AsyncOpenAI`) — a paid per-token path that, if a key is set, needs Zero's authorization under the cost rule **(unverified whether a key is configured)**.
- Prior research the lane must not re-propose: the due-bot 7-lens study already benchmarked Sierra/Decagon/Fin/Ada/Zendesk, WhatsApp Flows, "one brain, many surfaces", containment/handoff metrics and NeMo Guardrails (`research/operations/2026-08-25-due-bot-7-lens-research.md` LENS 2); the latency root cause is the 3-step ReAct loop + verification, not the model (`2026-07-20-wa-bot-latency.md`); the full-domain curated-cache program is designed (`2026-07-17-full-domain-cache-design.md`); the KBLI grounding battery went from 3/25 abstain and 5/25 silence to **24/25 abstain, 0/25 silence** (`2026-08-11-zantara-wa-kbli-grounding-benchmark.md` "After" table); the webhook-redundancy question is priced and left to Zero (`2026-08-25-wa-webhook-api-redundancy.md`).

## 2. Honest state vs. SOTA

The transport layer is unusually solid for a one-owner shop: ack-first persistence with wamid dedup, a durable outbox with fenced claims and burst coalescing, 24 h-window awareness, human-handling CAS, an idempotent apology, a webhook drain with backoff, a throughput sentinel with business-hours semantics. Much of this exceeds what small vendors ship.

The *conversation* layer is pre-SOTA on every axis the sector actually scores:

1. **No outcome metric.** `app/metrics.py` exposes `webhook_requests_total` and cache counters; nothing named resolution, containment, handoff, abandonment or CSAT matched a grep across the B3 routers/services, and the only `rating`/`feedback` columns live on the write-dead legacy `conversations` table. The organism cannot say what fraction of clients were helped.
2. **Refusal counts as success.** The 2026-08-11 battery was "cured" by moving from 3/25 to 24/25 abstains. That is honest, and it is also a bot that answers 1 of 25 KBLI questions.
3. **Handoff is a flag plus a Telegram ping.** No assignee, no SLA, no context summary, no "a consultant will answer by …" message; 4 of 40 threads ever taken over.
4. **Single-legged generation through a laptop-class daemon.** After the Gemini cut, the only generator is the Codex CLI on Pro; a crash-loop of that daemon went unnoticed ~70 h in August (SKILL.md §1).
5. **No dialogue state.** No slots, no flows, no structured intake; every turn is a fresh RAG call with the last N messages as context (`wa_inbox_bot.py:146`).
6. **Three language detectors, two thread models, two WA paths, three caches** — each locally correct.
7. **Latency 33–94 s** measured in July; the 25 s typing indicator the platform now offers is unused.

## 3. Deep research: the world's best

| Reference system | What they do that matters here | Technique / number | Evidence |
|---|---|---|---|
| **Meta WhatsApp Cloud API** | Retries failed webhooks "immediately, then a few more times with decreasing frequency over the next 36 hours"; batches up to 1,000 updates; unacknowledged drops after 36 h | dedup is mandatory; ordering not guaranteed | source 1 |
| | Typing indicator: `POST …/messages` with `status:"read"`, `message_id`, `typing_indicator:{type:"text"}`; dismissed on reply or after **25 s**; also marks read; "only display a typing indicator if you are going to respond" | replaces text acks | source 2 |
| | Per-message pricing since **2025-07-01**; "All non-template messages are free" inside the customer-service window; "Utility templates delivered within an open customer service window are free"; Click-to-WhatsApp free-entry window **72 h** | window = 24 h from the user's last message | source 3 |
| | Messaging limits are unique users messaged *outside* a customer-service window per rolling 24 h: tiers 250 → 2,000 → 10,000 → 100,000 → unlimited; poor quality can deny increases | reactive bots are unaffected by tiers | source 4 |
| | Flows: `TextInput`, `TextArea`, `Dropdown`, `DatePicker`, `RadioButtonsGroup`, `CheckboxGroup`, `OptIn`, `PhotoPicker`, `DocumentPicker`, `Footer`; `navigate` works without an endpoint, `data_exchange` needs the Data Endpoint (`data_api_version` 3.0); Flow JSON up to 5.1 | in-chat structured intake and consent | source 5 |
| | Calling API: user-initiated calls global; business-initiated limited to "1 per day and 2 per week" permission per user pair, revoked after 5 unanswered; WebRTC (ICE+DTLS+SRTP) or SIP/TLS, OPUS; `calls` webhook field | voice inside WhatsApp | source 6 |
| | Meta Business Agent (global June 2026): answers, books, qualifies leads, routes to humans, "$2.00 per million tokens" from 2026-08-01 | the platform now ships a generic competitor | source 18 (search-derived) |
| **Intercom Fin** | "averaging 76% across 12,000+ customers", "resolution rate increases 1% every month"; Apex 1.0/Apex Flash custom models; handoff "maintaining full customer context" | resolution is *the* KPI and the billing unit | source 8; production reality 45–53% per an independent write-up, source 19 (search-derived) |
| **Sierra τ²-bench** | Dual-control simulation: agent + simulated user each with tools; per-domain **policy + tools + tasks**; text half-duplex and voice full-duplex modes; reward gated on `evaluation_criteria.actions` | the test harness the sector converged on | source 7 (papers arXiv 2406.12045, 2506.07982) |
| **Decagon AOP** | Behaviour written in natural language and compiled into workflows; "Set rules for brand voice, escalations, and hallucinations"; "version with Git-based tracking"; test/simulate before deploy | policy-as-text under version control, tested like code | source 9 |
| **Klarna** | 2.3 M conversations, two-thirds of chats, resolution "less than 2 mins compared to 11 mins", "25% drop in repeat inquiries", 35 languages, CSAT parity | repeat-inquiry rate as the honest resolution proxy | source 10 |
| **Zendesk** | "automated resolution" = solved with no human help, verified by an LLM check; splitting into **Contained vs Verified** resolutions from 2026-05-18 | resolution is judged, not assumed | source 17 (search-derived; the help-center article sits behind a login) |
| **Rasa CALM** | LLM emits commands — `StartFlow`, `SetSlot`, `CorrectSlot`, `Clarify`, `ChitChat`, `KnowledgeAnswer`, `HumanHandoff` — against declarative flows; built-in repair patterns for corrections, digressions, clarification | dialogue state without brittle intents | source 16 (search-derived) |
| **Chatwoot** | 36.3k★, MIT, Rails/Vue; WhatsApp/IG/Telegram/web; auto-assignment on availability, agent capacity management; Captain AI | the OSS reference for inbox semantics (assignment, capacity, status) | source 11 |
| **Lingua** | 75 languages, rule-based alphabet pass + 1–5-gram Naive Bayes, offline; ~74% on single words, 94% on word pairs, 99.7% on sentences | short WhatsApp openers are exactly the hard case | source 12 |
| **GPTCache** | modular semantic cache: embedding → vector store → similarity evaluator → post-processor; eviction LRU/FIFO/LFU; Qdrant/pgvector supported | verify-then-cache architecture | source 13 |
| **ElevenLabs Agents** | ASR → LLM (bring-your-own) → TTS (70+ languages) + turn-taking model; SIP trunk/Twilio; RAG knowledge base; tools | a reference pipeline that can be rebuilt sovereign | source 14 |
| **Twilio Conversations** | one conversation object across Voice/SMS/WhatsApp/RCS/Chat; Conversation Memory + Orchestrator layers | one thread model across surfaces | source 15 (overview page only) |

## 4. Gap table

| Capability | Nuzantara today | World best | Gap |
|---|---|---|---|
| Webhook durability / dedup | ack-first, wamid-unique, drain with 5×5-min backoff | same class (source 1 requires exactly this) | none — keep |
| Signature security | fail-closed default since 08-26, **secret unset on 08-23** | mandatory HMAC | P0 config gap (see §8) |
| Time-to-first-signal | text ack OFF; no typing indicator (adapter says unsupported) | typing indicator ≤25 s, re-armable (source 2) | small code change, large UX gain |
| Reply latency | 33–94 s (July), 3-step ReAct + verify | Fin "0.6 s faster TTFT" marketing; sector <10 s | B1 owns the loop; B3 owns what the client sees while waiting |
| Outcome metrics | none (webhook counter only) | resolution judged by LLM, contained vs verified (sources 8, 17) | **largest gap** |
| Handoff | flag + Telegram ping; 4/40 threads | assignee, capacity, full context carry-over (sources 8, 11) | large |
| Dialogue state / intake | none | CALM flows/slots; WhatsApp Flows forms (sources 5, 16) | large |
| Evaluation harness | 25-case corpus, 28 golden, 25-question battery, no simulated user | τ²-bench policy+tools+simulated user, pass^k (source 7) | medium |
| Language handling | 3 regex detectors, divergent | Lingua-class offline detector with confidence (source 12) | small, high-leverage |
| Generator resilience | one leg (Codex on Pro), no fallback by ruling | multi-model with fallback | medium; constrained by Legge 5 |
| Answer cache | 3 caches, serving cache gated by provenance, deferred | verify-then-cache (source 13) | correct to defer at 4 msg/day |
| Voice | local STT/TTS lab; no WhatsApp voice | Calling API + agents pipeline (sources 6, 14) | beyond-SOTA opportunity |
| Consent / lawful basis | fail-closed doctrine, no per-client proof (SYMBIOSIS Law 2 §3) | Flows `OptIn` component (source 5) | turn a constraint into a feature |

## 5. Recommendations — reach SOTA

Each: what · why · how · effort · risk · dependencies · falsifiable acceptance.

**R1 (P0) — Outcome telemetry: judge every thread, locally.**
*What:* a nightly job on Mini labels every thread idle >24 h as `resolved | contained_unverified | escalated | abandoned | out_of_scope` with a one-line reason, using `qwen3.5:9b` via Ollama (transcripts never leave the fleet), and exposes counters (`zantara_wa_thread_outcome_total{outcome}`), p50/p95 webhook→send latency, and repeat-inquiry rate (same counterpart returning within 7 days with the same intent — Klarna's proxy).
*Why:* the two systems that lead the sector bill and steer on judged resolution (sources 8, 17); Nuzantara cannot currently distinguish "answered" from "helped", and the last outage was invisible for 24 days for the same reason.
*How:* new migration `wa_thread_outcomes(thread_id, judged_at, outcome, reason, judge_model, prompt_version)`; `scripts/wa_thread_outcome_judge.py` reusing the `wa_copilot/extraction_pipeline.py` Ollama pattern; counters in `app/metrics.py` beside `webhook_requests_total`; feed the existing throughput sentinel a fourth condition (`abandonment_rate > 30% over 7d → digest`).
*Effort:* M. *Risk:* judge drift — mitigate with a 30-thread human-labelled sample per month (generator≠grader). *Deps:* Mini Ollama (present per CLAUDE.md), one new launchd job or a slot in an existing nightly (avoid a new daemon: hang it off `wa_corpus_daily_run.sh`).
*Acceptance:* ≥95% of closed threads labelled within 36 h; judge/human agreement ≥80% on the monthly sample; the weekly report shows containment, escalation, abandonment and repeat-inquiry as numbers. Falsified if agreement <80% two months running.

**R2 (P0) — Handoff v2: named assignee, context card, SLA.**
*What:* escalation carries (a) an assignee resolved by `routing_engine.suggest_assignment` (`:191`) from `team_members.whatsapp`/role, (b) a PII-light context card (intent, language, last 3 turns summarised locally, open questions) in the Telegram ping, (c) an in-window client message "a consultant will follow up within N hours" (free — source 3), (d) an SLA timer that re-pages at 30 min business time.
*Why:* Fin's differentiator is handoff "maintaining full customer context" (source 8); Chatwoot's is availability-based assignment and capacity (source 11); the measured 4/40 takeover rate says the current ping is not a handoff.
*How:* `wa_inbox_bot._tell_a_human` (`:79`) gains `assignee`, `summary`; add `assigned_to`, `escalated_at`, `sla_due_at` to `meta_inbox_threads`; the summary is produced by the same local model as R1; the client-facing line goes through the outbox (24 h check already there).
*Effort:* M. *Risk:* pinging the wrong person — mitigate by falling back to Zero, never to nobody (the SYMBIOSIS "no fallback recipient" rule applies to client PII digests, not to an internal escalation with a `client_id`). *Deps:* R1's local summariser.
*Acceptance:* 100% of escalations carry assignee + summary; median human first reply <30 min in business hours over 4 weeks; the R1 judge's "re-explain" flag (client repeats context to the human) → 0.

**R3 (P0) — Ingress hardening before the knob lands.**
*What:* startup assertion: if `meta_webhook_require_signature` is true and `whatsapp_app_secret` is empty, log CRITICAL and page (do not silently 401 the world); a `scripts/wa_webhook_probe.py` that POSTs an unsigned payload to prod expecting 401 and a signed canary expecting 200; restore the `subscribed_apps` diagnostic.
*Why:* source 1 — after 36 h of 401s Meta drops the notifications; the bot would be deaf with a green health check, the exact shape of the July outage.
*How:* `app/core/config.py:700-704` validator; probe script modelled on `wa_codex_seat_probe.py`.
*Effort:* S. *Risk:* none. *Deps:* the App Secret itself (§8).
*Acceptance:* unsigned POST → 401, signed canary → 200 and a row in `inbound_webhooks` within 10 s; both proven after the next deploy, in the deploy window (outside 08–20 WITA).

**R4 (P1) — Typing indicator instead of text acks.**
*What:* on `generating`, call `status:read + typing_indicator` (source 2) and re-arm every 20 s until send or fail; delete the "manners" text ack; keep the terminal apology.
*How:* `channels/whatsapp/adapter.py:194-197` (currently a no-op) and `wa_outbox_worker._maybe_send_ack` (`:306`) — reuse the `"status": "read"` call already in `services/integrations/whatsapp_service.py:259`.
*Effort:* S. *Risk:* Meta's guidance "only display a typing indicator if you are going to respond" — never arm it before the human_handling check.
*Acceptance:* typing visible within 2 s of inbound on a handset canary; zero ack text rows in `meta_inbox_messages` after cut-over.

**R5 (P1) — One language detector, thread-sticky.**
*What:* replace the three regex detectors on the WA path with one `detect_language(text, history) → (iso, confidence)` backed by Lingua (offline, 75 languages, confidence values — source 12), persist `thread_language` on `meta_inbox_threads`, and make generation, apology and formatter read it.
*How:* new `services/communication/lid.py`; adapters at `language_detector.py:20`, `whatsapp_context_builder.py:152`, `query_helpers.py:456` delegate to it (keep their return vocabularies for callers); parity test with 200 short openers in ID/EN/IT/RU/UK/DE/ES/FR.
*Effort:* S–M. *Risk:* the `test_reasoning_stubs_language_coverage` AST guard (`query_helpers.py` comment) constrains how `detect_query_language` returns — keep literal returns.
*Acceptance:* ≥95% on the 200-opener corpus; `grep -c "def detect_language"` on the WA path = 1 delegating shim per legacy name; DE/ES no longer degrade to EN (memory case).

**R6 (P1) — Generator resilience inside the ruling.**
*What:* an active/standby second Codex seat on Mini (already designed: due-bot research §4.2) plus a *local honest fallback*: when no codex leg is available, the outbox sends a language-correct "received, a consultant will reply" line and escalates via R2 — never a domain answer from a small local model.
*Why:* a single daemon on one Mac is in the client path; Zero has ruled ChatGPT-only for answers, so resilience must come from seats and from honest acknowledgement, not from Gemini.
*How:* `wa_codex_leg.py` route decision + `wa_broker` offer to a second `broker_jobs` consumer identity; fallback text through the existing apology plumbing (`wa_outbox_worker.py:271`).
*Effort:* M. *Risk:* split-brain between two daemons — the durable offer/consume in `broker_jobs` (migration 270) is designed for exactly this; prove with a kill test. *Deps:* `codex login` on the Mini seat (§8).
*Acceptance:* kill the Pro daemon for 60 min in business hours → 100% of inbound get an acknowledgement <60 s and an escalation ping; `generation_fall_off_reason` explains every non-served row.

**R7 (P1) — WhatsApp Flows for structured intake.**
*What:* a qualification Flow (nationality dropdown, purpose radio, dates, `DocumentPicker`) sent when the R1 judge or intent classifier sees an eligibility question; results feed B6's visa engine and the thread context.
*Why:* source 5 components cover the whole intake; the due-bot lens already recommended Flows (choice 4) — this lane adds the acceptance metric and the wiring point, not the idea.
*How:* interactive `flow` message from the outbox; `data_exchange` endpoint under `routers/webhooks.py` with the Flows encryption requirement; the flow's `complete` payload becomes a `meta_inbox_messages` row with `media_type='flow'`.
*Effort:* M–L. *Deps:* Business Manager flow creation + keys (§8).
*Acceptance:* ≥50% of eligibility threads complete the flow within one session; abstain rate on flow-completed threads <20% versus the 24/25 baseline.

**R8 (P2) — τ-style simulation harness as a merge gate.**
*What:* simulated user (local model) × policy × tools over the existing 25-case corpus and 28 golden answers; report pass^3.
*How:* `apps/backend-rag/backend/tests/channels/test_wa_simulated_user.py` driving `generate_bot_reply` with a stubbed RAG client; policies as YAML in `data/wa_policies/` (Decagon-style versioned text, source 9).
*Effort:* M. *Acceptance:* pass^3 ≥0.8 on the frozen corpus; a PR that drops it below blocks merge.

**R9 (P2) — One thread model.** Fold `conversation_threads`/`omnichannel.py` onto `meta_inbox_threads` (or the reverse) so assignment, status and stats have one source; `_resolve_client_id` gains the instagram branch. *Acceptance:* one table answers `/api/omnichannel/stats` and `/api/wa-inbox/threads`.

## 6. Recommendations — beyond SOTA

**B1 (P1) — Sovereign quality analytics as a client promise.** Fin/Zendesk judge resolution in *their* cloud; in Indonesia that judging is itself processing under UU PDP. R1's judge and R2's summariser run on the Mini with `qwen3.5:9b`, so Nuzantara can publish "your conversation is analysed only on our own machines, never sent to a third party for scoring" — and prove it with the `judge_model` column. *Acceptance:* 0 cloud calls in the outcome pipeline (assert in CI that the judge imports only the Ollama client); the statement appears in the consent text of B3.

**B2 (P1) — Signed-provenance answers.** Every eligibility answer carries B6's rule-pack id + hash + `source_date` in a one-line footer (short link), and the regulatory-watcher delta re-judges cached/curated entries — Harvey-style "is this still good law", cryptographically anchored rather than vendor-asserted. *How:* `wa_finalize.py` appends the footer from the orchestrator's `pack_ref`; the regeneration trigger is already designed (`2026-07-17-full-domain-cache-design.md` §2). *Acceptance:* 100% of eligibility answers carry a pack id; answers citing a pack older than the newest signed pack for that domain = 0.

**B3 (P1) — Consent as a 20-second Flow.** SYMBIOSIS Law 2 §3 says cloud generation on PII text must fail closed until a per-transfer basis is provable; today nothing records it. A Flow with the `OptIn` component (source 5) collects DPA acknowledgement + consent on first contact, stored as `consent_basis`, `consented_at`, `flow_version` on `meta_inbox_threads`; the outbox refuses the cloud leg for threads without it and answers with the honest fallback from R6. This turns the organism's hardest constraint into the only WhatsApp bot in the market that can show the client its own lawful basis. *Acceptance:* 0 codex-leg generations on threads without a consent row (SQL assertion in the sentinel); consent completion ≥80% of new threads.

**B4 (P2, traffic-gated) — Two-speed brain.** A local FAQ tier (`NotebookLMCacheService` exact + `caching/semantic_cache.py` similarity, both provenance-gated) answers the top-N verified questions in <3 s on the fleet; the ChatGPT leg handles the long tail. The bot corner correctly deferred this at ~4 msg/day; arm it when inbound >50/day. *Acceptance:* cache-served answers are a subset of the curated set (`source_ref` non-null on 100%); p50 latency of cache hits <3 s.

**B5 (P2) — Client-side SLO in the homeostasis loop.** Extend `wa_bot_throughput_sentinel.py` from freshness to experience: p95 webhook→send latency, escalation SLA misses, abandonment; scars get a `client_impact` field. *Acceptance:* the sentinel pages on p95 >60 s during business hours within one tick; the July-class outage replays as P0 at +1.5 h (already) and a "slow but alive" week replays as digest.

**B6 (P2/L) — Sovereign voice on WhatsApp.** Calling API user-initiated calls are global (source 6); `voice.py` already has whisper.cpp + Chatterbox. A voice concierge that never ships audio to a cloud (ElevenLabs-class pipeline rebuilt local, source 14) is something no US vendor can offer under UU PDP. Business-initiated calls are rate-limited (1/day, 2/week) — reactive only, which matches the standing ruling. *Deps:* WABA calling enablement, a media path on Pro/Mini. *Acceptance:* a user-initiated call answered <3 s with STT→RAG→TTS round trip <6 s, 0 external audio egress.

**B7 — The agentic team bot** exists on branches (`apps/team-bot`, due-bot F1–F11) and is not re-proposed here; B3's only note is that R2's assignee routing and B3's consent store should be shared with it rather than re-implemented.

## 7. §Meta-pattern

**Every organ measures itself; nothing measures the client.** The generating belief is "a correct component is a correct product": breaker closed = alive (24-day silence), `abstain=true` = pass (24/25 refusals booked as a cure), answer written to the ledger = delivered (94 answers generated then discarded at the window), Telegram accepted = handed off (4/40 takeovers), each detector correct on its own corpus (three of them). Every fix in the lane's history strengthened a component's self-report; none added a sensor on the client's side of the chat. R1 is therefore not one recommendation among nine — it is the one that makes the other eight falsifiable.

## 8. §Solo-operatore

Only Zero can do or decide these; the sessions can build everything around them.

1. **App Secret** from Business Manager → `fly secrets set WHATSAPP_APP_SECRET` (`operator[gui]`+`[secret]`) — before or in the same window as the deploy that arms `META_WEBHOOK_REQUIRE_SIGNATURE`; then R3's probe proves it.
2. **`subscribed_apps` / messages subscription** re-check in Business Manager (the 500 on `GET /{WABA}/subscribed_apps` is still open per SKILL.md §1) and the handset canary (`operator[physical]`).
3. **Codex login on the Mini standby seat** (`operator[gui]`) — prerequisite for R6.
4. **Flows creation, Data-Endpoint keys, Calling enablement** in Business Manager (`operator[gui]`) — R7, B3, B6.
5. **Business decisions (Legge 5):** (a) whether to generate before the 24 h check (keeps drafts for the human queue, costs a call) — SKILL.md frames it as an owner trade-off; (b) whether a free in-window **utility template** (source 3) changes the "no templates" ruling for the "a consultant will follow up" line — it does not reopen a closed window, so the ruling likely stands, but it is Zero's; (c) whether the OpenAI Whisper/TTS fallback in `audio_service.py` may hold a key at all (cost rule) — if not, remove it; (d) how to position against Meta Business Agent at "$2.00 per million tokens" (source 18): the defensible edge is domain depth, signed provenance and sovereignty, not generic answering.
6. **Consent text and DPA status** for B3 (`operator[business]`, G-P2 "non ora" per SKILL.md).

## 9. Sources

Accessed 2026-08-28 unless noted.

1. Meta — Graph API Webhooks, getting started: https://developers.facebook.com/docs/graph-api/webhooks/getting-started
2. Meta — WhatsApp Cloud API typing indicators: https://developers.facebook.com/docs/whatsapp/cloud-api/typing-indicators
3. Meta — WhatsApp Business Platform pricing: https://developers.facebook.com/docs/whatsapp/pricing
4. Meta — WhatsApp messaging limits: https://developers.facebook.com/docs/whatsapp/messaging-limits
5. Meta — WhatsApp Flows, Flow JSON reference: https://developers.facebook.com/docs/whatsapp/flows/reference/flowjson (the Flows overview page returned no body)
6. Meta — WhatsApp Cloud API Calling: https://developers.facebook.com/docs/whatsapp/cloud-api/calling/
7. Sierra Research — τ²-bench (README; papers arXiv:2406.12045, arXiv:2506.07982): https://github.com/sierra-research/tau2-bench
8. Intercom — Fin: https://fin.ai/
9. Decagon — Agent Operating Procedures: https://decagon.ai/product/aop
10. Klarna — AI assistant press release (2024-02-27): https://www.klarna.com/international/press/klarna-ai-assistant-handles-two-thirds-of-customer-service-chats-in-its-first-month/
11. Chatwoot — repository: https://github.com/chatwoot/chatwoot
12. Lingua-py — repository: https://github.com/pemistahl/lingua-py
13. GPTCache — repository: https://github.com/zilliztech/GPTCache
14. ElevenLabs — Agents Platform overview: https://elevenlabs.io/docs/agents-platform/overview
15. Twilio — Conversations overview (positioning page only; API reference not fetched): https://www.twilio.com/docs/conversations
16. Rasa — Dialogue Understanding / patterns (search-derived; docs page not fetched directly): https://rasa.com/docs/learn/concepts/dialogue-understanding/ , https://rasa.com/docs/reference/primitives/patterns/
17. Zendesk — automated resolution rate (search-derived; the help-center article is behind a login wall): https://www.zendesk.com/blog/ai/workflow-automation/automated-resolution-rate/ , https://support.zendesk.com/hc/en-us/articles/10677925692698-Announcing-changes-to-AI-agent-reporting
18. TechCrunch — Meta Business Agent global availability, 2026-06-03 (search-derived): https://techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/
19. CloneDesk — Intercom Fin resolution 45–53% in production (search-derived, third-party): https://clonedesk.ai/blog/intercom-fin-limitations

Internal ground (read this session): `.claude/skills/bot/SKILL.md` (§0–§7), `SYMBIOSIS.md` §LE LEGGI, `.claude/rules/cicatrix-scars.md` (W68/W72/W73/W77 WhatsApp guard family, W104), `.claude/skills/modus/PENDING-ARMS.md`, `research/operations/2026-08-25-due-bot-7-lens-research.md`, `2026-08-25-wa-webhook-api-redundancy.md`, `2026-07-20-wa-bot-latency.md`, `2026-08-15-adr-wa-runtime-openai-provider.md`, `2026-07-17-full-domain-cache-design.md`, `2026-08-11-zantara-wa-kbli-grounding-benchmark.md`, `2026-08-06-telegram-messaging-study.md`, `2026-07-24-zantara-bot-consultant-assistant-spec.md`, `2026-06-14-mythos-m2-whatsapp-brain.md`; memory `MEMORY_BOT_AND_LLM_LANES.md`, `project_live_bot_test_loop_2026_08_27.md`, `project_wa_lane_residuals_2026_08_26.md`.
