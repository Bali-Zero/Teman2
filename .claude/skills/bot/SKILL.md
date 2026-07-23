---
name: bot
description: "Zantara WA bot corner — the live shared context for ALL work on the Zantara WhatsApp Meta bot (+62 821-3465-159): outbox/inbox pipeline, agentic RAG brain, answer cache, model routing, prompt chain, team check-in program. Load BEFORE touching any WA-bot code or data, or when Zero says /bot, 'zantara wa', 'il bot', 'meta inbox', 'cache risposte'. Holds: established truths (verified, with method), Zero's rulings, LIVE STATE of the ship chain, blood-bought operating rules."
---

# /bot — Zantara WA Meta bot corner

> Created 2026-07-17 on Zero's order ("il tuo lavoro deve essere focalizzato su zantara Wa Meta").
> This file is the HOT CONTEXT shared by every session working on the bot. It states what is
> PROVEN, what is DECIDED, and what is IN FLIGHT. **Update §1 LIVE STATE whenever it changes —
> this corner is only useful if it stays true.**

## 0. The product (what all of this serves)

WhatsApp Business (Meta Cloud API) number **+62 821-3465-159** = Zantara. Two audiences, one number:

- **Clients**: a perfect consultant on immigration / tax / company / license / real-estate legal.
  Grounded answers with citations, abstains instead of inventing, prices ONLY from PricingTool,
  ONE all-inclusive client-facing price (never PNBP-vs-fee splits — Zero ruling 2026-07-17).
- **Bali Zero team**: work-support assistant. Check-in via WA (opens the free Meta 24h window),
  CRM nudges, PII-light briefings. Persona = "assistente operativo interno", not sales.

## 1. LIVE STATE (last update 2026-07-22 — keep current)

- **🩸 TAC 2026-07-24 (Fable, M5) — full consultant+team audit → SPEC for Opus 4.8** in
  `research/operations/2026-07-24-zantara-bot-consultant-assistant-spec.md` (12-lane workflow +
  3-seat cross-family council + disk re-verification). Headline findings that CORRECT this corner:
  - **🔴 P0-MEM (NEW, disk-confirmed, possibly live): cross-client memory bleed.** Path B auth via
    `X-Internal-Key` → `hybrid_auth.py:380-385` returns a FIXED pseudo-identity
    (`wa-mirror-internal@balizero.com` / `wa-mirror-internal`) for EVERY sender; `agentic_rag.py:398-405`
    discards `whatsapp_{phone}` and substitutes it as `user_id` (`:475`); `memory_handler` skips only
    `user_id=="anonymous"` (`:138`) → long-term client FACTS stored/read under ONE shared key across all
    clients. In-thread history (keyed `wa_session_{phone}`) is fine; the FACT layer is the leak. UU PDP.
    Cure = W-1 CONTAINMENT in the spec (per-phone pseudonymous subject). Recommend contain now (disable
    Path B long-term memory) — autoreply is ON. See memory `discovery_zantara_bot_memory_tenancy_bleed_2026_07_24`.
  - **🔴 P0-ID / P0-ARG: forgeable persona-override + reserved-arg.** `_is_trusted_wa_profile_caller`
    (`agentic_rag.py:298-322`) gates a `profile` override on shared-key `role=internal` + CLIENT-SUPPLIED
    `channel=whatsapp`; `tool_executor.py:346-349` lets an LLM-injected `_caller_profile` survive when the
    server value is falsy. ⇒ **T4 (real per-request identity) MUST precede T1 (arming team CRM tools).**
  - **CORRECTIONS to prior corner claims:** (a) #2872 (team-assistant V1) + #2890 (Phase-2 CRM read tools)
    are **MERGED** (2026-07-20), not in-flight/parked. (b) `WA_TEAM_CRM_TOOLS_ENABLED` is **UNSET in prod
    (default false)** → the 4 read tools are merged-but-NOT-ARMED. (c) **WA team check-in (`timesheet`) +
    `team_knowledge` are DEAD on WA**: `agent_role` is never set on the WA path, so the #2962 SENSITIVE_TOOLS
    deny fires — a silent regression, previously undocumented. (d) **Langfuse tracing is ENABLED in prod**
    (`observability.py:53` default `"true"`, keys deployed, no `LANGFUSE_ENABLED=false` secret live) — the
    "kill-switch active" framing is STALE; verify whether re-enable was intentional. (e) wa-tester LID
    under-match (task #26) is **FIXED** (#2903). (f) `CURATED_QA_INJECTION_ENABLED` default `"true"` → curated
    grounding IS on even though the prod env var is unset.
  - Spec is a PLAN for Opus 4.8 (executing architect); nothing here is shipped as code yet. Sequence:
    W-1 CONTAINMENT (P0s) → W0 safety → W1 reconnect-the-nerves → W2 arm-team (T4 first) → W3 observ → W4 gate.

- **GEMINI PREPAY DEPLETION P0 (2026-07-22) — RESOLVED via top-up + verifier revival PROVEN LIVE**:
  while carrying the RAG verifier revival to prove-live, live prod logs revealed the WHOLE bot was
  degraded — NOT by the verifier but by `429 RESOURCE_EXHAUSTED "prepayment credits are depleted"`
  on BOTH `gemini-3.5-flash` (primary) AND `gemini-2.5-flash` (fallback): the prepay Gemini key's
  balance hit zero (the `discovery_gemini_api_key...2026_07_19` risk realized). Symptom: agentic LLM
  dead → can't drive tool-retrieval → `Chunks retrieved: 0` → **abstain on EVERYTHING** (visa/tax/
  company all `confidence:0.0`); verifier can't run either (also Gemini). Only verbatim FAQ cache
  still served (no Gemini). Embeddings + Qdrant were fine — Gemini-only outage. Zero topped up the
  prepay on project `nuzantara` (AI Studio, operator/billing). **Post-top-up prove-live (fly logs,
  this turn)**: 0× 429, retrieval alive (`Chunks retrieved: 13`, confidence 0.85, real E35/E28
  sources), and the **verifier producing real parsed verdicts** — `🛡️ [Verifier] Status:
PARTIALLY_VERIFIED | Score: 0.75`, `[VerificationStage] ... verdict_available=True`,
  `[self-correct] verify=24.11s` (self-correction fires). **Verifier revival (PR #2973, fence-parse
  → `generate_structured`) = DONE + PROVEN LIVE.** The pre-topup "intermittent ~1/3 schema-fails" was
  the depletion front, NOT strict schema (anyOf/bounds refuted on real Gemini). **OPEN follow-ups
  (non-blocking)**: (a) enable prepay **auto-recharge / low-balance alert** (billing, operator) — the
  only structural cure while Fly arch is "Gemini always"; (b) verifier robustness (round-3
  schema-loosen held unpushed at `8604d7ae96`, ship only with a real before/after schema-fail
  measurement); (c) architectural non-Gemini fallback on Fly so a 429-Gemini never zeroes the bot.
  Detail: memory `discovery_prod_verifier_dead_fence_parse_not_leaked_key_2026_07_21` +
  `discovery_gemini_api_key_project_orphan_ledger_undercount_2026_07_19` (§RESOLVED).
- **🔒 P0 SECURITY — CRM/PII public exposure FIXED + DEPLOYED + PROVEN (PR #2962, 2026-07-21)**: `/api/blog/ask` (+ WA-unknown ReAct) could exfiltrate CRM whole-book PII (`crm_query`) and the full staff roster incl. pin/religion (`team_knowledge`); `/api/team/clock-in`+`/clock-out`+`/my-status` allowed impersonation (identity from body, no auth). Tourniquet (2 Codex red-team rounds, generator≠grader): `SENSITIVE_TOOLS={crm_query,timesheet,team_knowledge}` denied for `agent_role=None` in `tool_authorizer.py`; `_resolve_actor_identity` in `team_activity.py` ignores body identity for non-admin (closes email+user_id); `Depends(get_current_user)` on clock-in/out/my-status. PROVE-LIVE prod: blog/ask → `tool_authz decision=deny role=none tool=team_knowledge` (log) + graceful 0-PII answer; clock-in/out/my-status no-auth → 401; health 200. Staff no-regression + non-admin→own-identity verified by red-team + 13 unit tests (`test_team_activity_clock_identity_tourniquet.py`). Full principal-based rework (unified server-side principal, unconditional reserved-arg strip, clamp `CRMTool.limit`, timesheet email from principal, remove legacy `agent_role=None→allow`) is a SEPARATE non-P0 follow-up. Memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
- **🎫 Collateral finding (open ticket): JWT expiry NOT enforced in prod**: `jwt_enforce_expiry=False` default (`config.py:501`, "Phase 1 audit mode"), no prod override (`JWT_ENFORCE_EXPIRY` absent from fly secrets) → expired JWTs accepted app-wide (`verify_exp` in hybrid_auth.py:473/517, auth.py:126, websocket.py:93, deps/auth.py:70). Flip = ops decision (verify refresh-token works first, blind flip logs out live sessions). Memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
- **🎫 Collateral finding (open ticket): orphan test tree**: `apps/backend-rag/tests/` (top-level, 1189+ lines) is NOT collected by any CI workflow nor the pre-push (both scope `backend/tests/`; `pytest.ini testpaths=backend/tests`) → false coverage (scar #2). Tests there never run in gate.
- **🎚️ VERBATIM FAQ → JELAS-only (Zero 2026-07-21) — DONE+VERIFIED**: refined the 19/7 "all verbatim"; deleted 215 non-JELAS from Redis `notebooklm:qa:*` (AFTER = 139 = 103 JELAS + 36 E33, non-JELAS=0); Qdrant `curated_qa` 808 pts intact (grounding preserved). This PR retires the `--verbatim-all` override so a re-harvest can't undo it. Memory `ops_verbatim_rollback_jelas_only_2026_07_21`.
- **WA OUTBOX P0 (2026-07-19) — FIXED #2812 + DEPLOYED 12:45 UTC + VERIFIED**: the per-thread
  advisory lock passed raw `int thread_id` into `hashtext('wa_outbox_thread_' || $1::text)` —
  asyncpg types `$1` TEXT from the cast and refuses int (`DataError: expected str, got int`),
  so the scheduler crashed EVERY tick and the bot was mute ~4h (2,495 crashes). Fix:
  `str(thread_id)` at lock AND unlock (must hash to the same key). Unit mocks never caught it —
  they don't do asyncpg's client-side type validation. Deploy got lost twice (concurrency-cancel
  - ~2h runner queue); caught by the new fly-logs accumulator (O0-P1). Verified: zero
    occurrences after 12:44 UTC. **Lesson: lock/unlock key args must be same TYPE, and mocks of
    asyncpg conns lie about type checking.** **Client-side PROVE-LIVE**: backlog claimed at
    12:13Z right after deploy; fresh inbound answered in 150ms (row 157); only failures =
    `24h_window_closed` on a thread idle since June (correct Meta-policy behavior) —
    independently confirmed by the wa-tester battery from Zero's own number (bot reply ~36s,
    Meta `read` receipt, all corrected facts verbatim in Bahasa).
- **PR #2825 (injection gap #23) MERGED + DEPLOYED + PROVEN**: overstay/penangkalan/deportation/
  re-entry-ban keywords added to the visa domain classifier — queries previously classed
  "general" never searched curated_qa. Prove-live: probe → log
  `✅ [CuratedQA] Injected 2 curated evidence block(s)`, answer carries 60-day threshold /
  10+10 ban / Rp 90jt pencabutan (PP 45/2024 VI.E).
- **PR #2822 (QdrantClient.get) MERGED + DEPLOYED**: flags moved to JSON body (`with_payload`/
  `with_vector`) — was silently returning empty payloads. Consumer-map finding: sole non-test
  caller is the memory_vector router which is NOT mounted in prod (F29 note in handlers.py) →
  preventive hardening, no live surface.
- **CHATKB cantiere: 21 dossiers GATED (396 Q&A)** across visa/company/tax/property (Waves 1-3,
  Fable gate 7/7+8/8+6/6 PASS). Zero ruling 2026-07-19: **promote ALL answers VERBATIM** (team
  review after, not before) — execution gated on PR #2810 rails (pricing-detector, source
  allowlist, `verbatim_eligible`, still OPEN); PR #2856 (compound-CONFIDENCE degrade at
  harvest) MERGED. Team review packs: 21 batches Bahasa + 21 editable docx in
  `~/Desktop/TEAM-REVIEW-2026-07-20/`.
- **CHATKB review pipeline (2026-07-21)**: corrections dir
  `research/curated-qa-corrections-2026-07-21/` (rounds 1-4 applied+harvested). Dossier 11
  (company-kbli-signed-lots) **round 5 APPLIED TO PROD** batch `company-b02dc5cb2e89`: Q5/Q6
  KBLI 70100 PMA-block fix (no Usaha Besar row in OSS → a PT PMA cannot register under 70100;
  the wrong "register now" answer grounded prod RAG from round 4 until the re-harvest), Q13
  66123 hedged Bali-moratorium caveat (LOW confidence). Adversarial review FIX-THEN-SHIP
  caught the 64200→64210 vintage error. Capture + operator recipe:
  `research/company/2026-07-21-kbli-signed-lots-round5-verification.md` + README Round-5
  section (PR #2989).
- **GARUDA-E23 law_refs delta-harvest LIVE**: Perpres 20/2018 (revoked in full by PP 34/2021)
  re-cited to PP 34/2021 Pasal 19/6 on 2 prod points (Q2/Q6), answers untouched, neighbors
  no-drift.
- **Team-assistant V1 IN FLIGHT (task #29)**: sender-identity wiring into the live meta-inbox
  path (resolve team/owner from `team_members.whatsapp` + env, profile.role into RAG payload →
  TEAM/CREATOR persona finally reachable). Innocence contract: clients/unknown byte-identical.
  Phase 2 (CRM scoped tools per assigned_to) parked pending Zero GO.
- **wa-tester LID under-match (task #26, low-pri)**: isPaired fix PR #2820 live on Pro; the
  battery's receive matcher `remoteJid !== BOT_JID` drops replies syncing under `@lid`
  (WhatsApp LID rollout) → `reply_count:0` false negative even though the bot answered (ground
  truth via Postgres — see the P0 prove-live above). Instrumentation-only, not a bot-behavior
  bug.
- **PR #2586 MERGED**: 4 production bugs of the outbox worker fixed (burst duplicate replies,
  takeover-during-generation send, generating-crash orphan, FAQ prewarm scope mismatch) +
  per-thread advisory lock, claim-token fencing, lease heartbeat, burst coalescing, K workers
  (`WA_OUTBOX_WORKERS=2`), admission semaphore (`WA_BOT_MAX_CONCURRENT_GENERATIONS=3`).
- **PR #2588 (cache F1b) MERGED + DEPLOYED**: FAQ cache wired into the orchestrator the WA bot
  uses, provenance-mandatory cache writes, curated_qa Qdrant collection + grounding injection,
  harvester/converter tooling. **E33 216 loaded and verified live**: Redis 216 keys + Qdrant 216
  points.
- **PR #2611 (Gemini 3.5 Flash) MERGED + DEPLOYED**: PRIMARY/CHANNEL = `gemini-3.5-flash`,
  proven in prod (GA, function calling OK). FALLBACK stays `gemini-2.5-flash`.
- **PROVE-LIVE done** on the real bot path: 200 responses in 1.6–3.9s.
- **LANGFUSE INCIDENT (2026-07-05 → 2026-07-17, bot dead 11 days)**: a dependabot bump
  (langfuse 3.14.6 → 4.x) renamed `Langfuse.start_as_current_span()` to
  `start_as_current_observation(..., as_type="span")` — the old name doesn't exist in v4 at all.
  `_process_query_traced` in `agentic_rag.py` called the v3 name unguarded, so every
  `/api/agentic-rag/query` call raised `AttributeError` before the orchestrator ever ran. Outbox
  outcome: 61 failed sends vs 1 success. Emergency mitigation (still active): Fly secret
  `LANGFUSE_ENABLED=false` (kill-switch in `observability.py::is_enabled`). **Durable fix**: this
  PR — `backend/core/observability.py::start_traced_span()` resolves v4-first/v3-fallback via
  `hasattr` and fails open (no-op span + WARNING log) on any mismatch, applied at both real call
  sites (`agentic_rag.py`, `tone_council.py`). Re-enabling tracing in prod (`fly secrets unset
LANGFUSE_ENABLED` or set back to `true`) is an operator action AFTER this PR merges+deploys —
  not done yet as of this update.
- **Corner PR #2612 MERGED** (prior §1 refresh, superseded by this update).
- **F2 (team check-in) NOT started** — begins after F1 ships. F3 (member profiles) after F2.
- **Prompt v4 + versioned door MERGED (#2629) AND prod FLIPPED `ZANTARA_PROMPT_VERSION=v4` —
  PROVEN-LIVE 2026-07-18.** `zantara_core_v4.py` (deadline-neutral KBLI guidance, phantom KBLI
  codes fixed 55130/55194→55203/55901/55400, `{today_wita}` date injection,
  `_safe_template_fill()` — the WORKED_EXAMPLES `.format()` P0 stays fixed) + `prompt_builder.py`
  imports `ZANTARA_MASTER_TEMPLATE` from `prompt_manager` (the door). Prod log proof:
  `PromptManager: using zantara_core_v4` (clean INFO, no fallback); battery on the door 2/2 PASS.
  **Gotcha that almost shipped**: v4 was drafted BEFORE the #2736 trigger fix and re-listed bare
  visa codes ("C1","C2","D1"⊂"D12") as get_pricing triggers — auto-merge was disarmed, the fix
  folded in (parity commit `9b0e9ac120`), THEN merged. The deploy alone would have REGRESSED
  ask_legal to v3's stale copy — the env flip is part of the ship, not an afterthought. v2/v3's
  stale trigger copies are now dead code behind the door. Design doc:
  `research/operations/2026-07-17-zantara-prompt-v4-design.md`.
- **Bot quality campaign 5 lanes SHIPPED+PROVEN (2026-07-18)** — memory
  `ops_zantara_bot_quality_campaign_4_lanes_2026_07_18` holds full detail: (A) 60s timeouts
  root-caused to a broken verifier minting fake score=0.5 on empty Gemini responses → doomed
  ~23s self-correction loop (#2712 `verdict_available` flag; C1→KITAS 2×timeout→35.3s) + 6
  missing Qdrant `status_vigensi` indexes + `ENABLE_RERANKER` secret unset; (B) Fonti leak
  proven never-reached WA clients; (C) stale WA number purged from 70 prod pricing points
  (#2708); (D) unsolicited price dumps killed (#2707 intent-gated boost, word-boundary); (E)
  zantara_core.py v1 trigger fix (#2736, operator two-key window) — bare visa codes are NOT
  pricing triggers, visa-TYPE questions ground on current codes names-only + one-line cost offer.
- **Full-domain cache lane OPEN** (design pending). Tracked in the main session's task list.

## 2. ESTABLISHED TRUTH (verified — do not re-litigate, do not re-derive)

1. **Two WA code paths exist.** Path B is the live one for this number: Meta webhook →
   `meta_inbox_*` tables → `wa_outbox` ledger → `wa_outbox_worker.py` (claim/fence/coalesce) →
   `wa_inbox_bot.py` → POST `/api/agentic-rag/query` → agentic RAG orchestrator → Gemini.
   Path A (OpenClaw bridge on Pro, gpt-5.5) is LEGACY — not this number's brain.
2. **Bot autoreply is LIVE in prod**: `WA_INBOX_BOT_AUTOREPLY=true` (verified via fly ssh
   printenv). Human takeover/release works from the console (see §6).
3. **Latency (10–50s) comes from the agentic RAG loop, not the model.** The cure is
   cache-first + curated grounding + faster model — never bypassing the abstain gates.
4. **Cache safety contract**: cache hits bypass the abstain gate → ONLY pre-vetted content may
   enter the cache; every entry carries
   `{source_ref, source_date, domain, confidence_class, source_priority}` (enforced by
   `NotebookLMCacheService.set()` — ValueError without them). curated_qa is GROUNDING injection
   (never verbatim serving); abstain gates stay live on that path.
5. **Prompt split-brain (audit 2026-07-17)**: the agentic RAG brain imports prompt **v1
   directly** (`prompt_builder.py:25`) — the `ZANTARA_PROMPT_VERSION=v3` env in prod only arms
   v3 on `zantara_ai_client.py`. v3's worked examples never reach the WA path. Also verified:
   NO current-date injection anywhere; stale "18 June 2026" KBLI deadline announced as future;
   v3 villa example teaches phantom codes (55130/55194 NOT in KBLI 2025 — real code is 55203);
   whatsapp_persona injects the full price list beside the "only get_pricing" rule; few-shots
   carry pre-BKPM-5/2025 capital claims. Cure = **v4 behind the same env flag**, one versioned
   entry point for ALL consumers + parity test. Never edit v1/v2/v3 in place.
   **RESOLVED 2026-07-18**: door merged (#2629) and prod flipped to v4 — see §1. The audit
   findings above are historical context; the split-brain no longer exists. Exception to
   "never edit v1 in place" happened ONCE under operator two-key window (#2736 trigger fix,
   before the door existed in prod) — with the door live, prompt changes go to v4 only.
6. **Meta 24h window**: per-thread, resets on every user message, service replies inside it are
   free. Business-initiated outside it needs a paid approved template — which Zero has REJECTED
   for attendance nudges (reactive-only ruling).
7. **Embedding model FROZEN** `text-embedding-3-small` 1536 dims (curated_qa included) — flat
   payloads only.

## 3. Anatomy (the 10 anelli, with file paths)

| #   | Organ                                   | Where                                                                                                      | State                                                    |
| --- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 1   | Meta webhook (ack<200ms, dedup, replay) | `backend/app/routers/whatsapp_chat.py`                                                                     | solid, untouched                                         |
| 2   | Message ledger                          | `meta_inbox_threads/_messages` tables                                                                      | solid, untouched                                         |
| 3   | Reply queue + send                      | `backend/services/integrations/wa_outbox_worker.py`                                                        | rebuilt #2586                                            |
| 4   | Reply generator                         | `backend/services/integrations/wa_inbox_bot.py`                                                            | semaphore added #2586                                    |
| 5   | RAG brain                               | `backend/services/rag/agentic/` (orchestrator_core, reasoning, llm_gateway)                                | wiring touched (#2588), reasoning/gates INTACT by design |
| 6   | Cache/corpus layer                      | `backend/services/caching/notebooklm_cache_service.py`, `curated_qa` collection, `scripts/curated_qa_*.py` | built #2588                                              |
| 7   | Model                                   | `backend/llm/config.py:12-20` (ModelName)                                                                  | 3.5 Flash PR queued                                      |
| 8   | Persona/prompt                          | `backend/prompts/` chain (v1→v2→v3 + whatsapp_persona + channel_overlays) + `prompt_builder.py` (agentic)  | v4 lane open; files off-limits w/o mandate               |
| 9   | Team check-in (F2)                      | does not exist yet on this path                                                                            | designed in spec v2                                      |
| 10  | Operator console                        | `apps/wa-meta-inbox` (thin proxy → `/api/wa-inbox/*`)                                                      | live on Pro                                              |

## 4. Zero's rulings (business decisions — do not re-open)

1. WA check-in **AFFIANCA** kita clock-in (both write `team_timesheet`), does not replace it.
2. **WA reactive-only**: nudges/briefings only inside an open 24h window; proactive reminders
   stay Telegram/email; NO paid Meta template.
3. Team persona (non-check-in) = **assistente operativo interno**, not sales consultant.
4. clock_in/clock_out MCP RBAC widening beyond admin = OK (partial ruling, only the 2 clock tools).
5. **Gemini 3.5 Flash in prod** = GO ("proviamo 3.5 flash in prod").
6. **Full-domain cache program** = GO (visa/company/tax/property like the E33 216, with
   auto-regeneration + obsolescence archiving, reuse-first).
7. **Prompt SOTA audit + alignment** = AUTHORIZED (v4 additive, flag-gated).
8. **One client-facing price** — never split PNBP vs fee (memory `feedback_single_price_no_pnbp_fee_split`).

## 5. Blood-bought operating rules

- **Provenance beats freshness-illusion (W90)**: no cache entry without source_date; a cache
  answer whose source predates a regulatory change is a lie with a citation.
- **The abstain gates are the product**: any "optimization" that serves un-vetted content past
  them is a safety regression, not a speedup (cf. 5 named gates SSOT `_abstain_policy.py`).
- **Generator≠grader everywhere**: the diff author never gates its own diff; corpus loads get
  blind verification (KBLI-filiera method) before serving clients.
- **Prices**: PricingTool is the ONLY source. The prompt chain currently violates this in
  spirit (injected price list) — do not copy that pattern into new code.
- **PII**: team briefings are PII-light (counts + practice codes, never client names on WA).
  Client PII never enters cache keys, logs, or this corner file.
- **Waiter-pollers stall**: background-task completion notifications to subagents are
  unreliable — probe objective state (git ls-remote, gh pr view, ps with EXACT patterns) and
  nudge with proof. A wrong ps pattern refutes YOU, not the agent (lived twice on 2026-07-17).
- **Push discipline (M5)**: pre-push gate 11–32 min > Bash cap → `run_in_background` + prove
  with `git ls-remote`; push at low honest load (`sysctl -n vm.loadavg` < 8).

## 6. Artifacts & access

- **Spec v2 (design contract)**: session scratchpad `zantara-wa-spec-v2.md` (panel-corrected,
  P1–P14; content summarized in memory + this corner survives it).
- **Decision memory**: `~/.claude/projects/-Users-balizero-nuzantara/memory/decision_zantara_wa_team_checkin_go_2026_07_17.md`.
- **Console (read/reply/takeover)**: live on Pro, LaunchAgent `com.balizero.wa-meta-inbox`,
  `http://localhost:7791` (loopback-only; from M5: `ssh -L 7791:localhost:7791 pro`).
- **Env knobs**: `WA_INBOX_BOT_AUTOREPLY`, `WA_OUTBOX_WORKERS`,
  `WA_BOT_MAX_CONCURRENT_GENERATIONS`, `ZANTARA_PROMPT_VERSION`, `CURATED_QA_INJECTION_ENABLED`,
  `DOMAIN_ABSTAIN_THRESHOLDS`.
- **Corpora**: `data/curated_qa/*.jsonl` (E33 216 via `curated_qa_convert_e33.py`; golden 28).
- **Team phone SSOT**: `team_members.whatsapp` (F2 detection key).
- **Team-assistant V1 (task #29) IN FLIGHT since 2026-07-19**: upstream identity plumbing for
  F2 (team check-in) — sender-identity resolution into the live meta-inbox path (see §1). A PR
  for this track may already be open (or merging) by the time this note is read — a sibling
  recovery lane was pushing it in parallel; check `gh pr list` for the current state rather
  than trusting this line's snapshot.

## 7. Collaboration protocol (the TRACK)

- Load this corner FIRST on any bot theme. `mem query "zantara wa"` for history.
- Whoever changes state (merges a PR, deploys, loads a corpus, flips an env) **updates §1 in the
  same PR/turn** — a stale corner is worse than no corner.
- Every build lane runs in its own worktree via `scripts/agent_start.py` (lane `backend-rag`);
  main checkout is read-only for agents.
- Fable sessions orchestrate + final-gate; edits/commits/pushes go to Sonnet implementers
  (hook-enforced). Adversarial review before merge on client-facing surfaces.
- Off-limits without a fresh mandate: `zantara_core.py` (+ prompt chain in place), `fly.toml`,
  `.env*`. The prompt v4 lane has Zero's mandate but is ADDITIVE ONLY (new file + flag).
