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

## 1. LIVE STATE (last update 2026-07-19 ~21:00 WITA — keep current)

- **WA OUTBOX P0 (2026-07-19) — FIXED #2812 + DEPLOYED 12:45 UTC + VERIFIED**: the per-thread
  advisory lock passed raw `int thread_id` into `hashtext('wa_outbox_thread_' || $1::text)` —
  asyncpg types `$1` TEXT from the cast and refuses int (`DataError: expected str, got int`),
  so the scheduler crashed EVERY tick and the bot was mute ~4h (2,495 crashes). Fix:
  `str(thread_id)` at lock AND unlock (must hash to the same key). Unit mocks never caught it —
  they don't do asyncpg's client-side type validation. Deploy got lost twice (concurrency-cancel
  - ~2h runner queue); caught by the new fly-logs accumulator (O0-P1). Verified: zero
    occurrences after 12:44 UTC. **Lesson: lock/unlock key args must be same TYPE, and mocks of
    asyncpg conns lie about type checking.**

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
