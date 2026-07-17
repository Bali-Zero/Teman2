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

## 1. LIVE STATE (last update 2026-07-17 ~20:20 WITA — keep current)

- **PR #2586 MERGED**: 4 production bugs of the outbox worker fixed (burst duplicate replies,
  takeover-during-generation send, generating-crash orphan, FAQ prewarm scope mismatch) +
  per-thread advisory lock, claim-token fencing, lease heartbeat, burst coalescing, K workers
  (`WA_OUTBOX_WORKERS=2`), admission semaphore (`WA_BOT_MAX_CONCURRENT_GENERATIONS=3`).
- **PR #2588 (cache F1b) MERGED** (2026-07-17 ~21:00 WITA): FAQ cache wired into the orchestrator
  the WA bot uses (was cache-less), provenance-mandatory cache writes, curated_qa Qdrant collection +
  grounding injection, harvester/converter tooling. On main, NOT yet deployed.
- **Model swap IN FLIGHT**: Gemini **3.5 Flash** primary (Zero GO 2026-07-17). Slug
  `gemini-3.5-flash` double-verified (GA, function calling OK). PR opened right after #2588:
  `backend/llm/config.py` ModelName.PRIMARY + CHANNEL; consumer-map also
  `verification_service.py:68`, `pricing.py` cost table, `token_estimator.py` + provider defaults.
  FALLBACK stays `gemini-2.5-flash`. Rollback = revert. Check `gh pr list` for its status.
- **Then, in order**: fly deploy rolling → run converters+harvester (216 E33 + 28 golden) into
  prod FAQ cache + curated_qa → PROVE-LIVE (real WA question, metrics `faq_cache_hits_total`,
  `curated_qa_injections_total`) → tell Zero to test from his phone.
- **F2 (team check-in) NOT started** — begins after F1 ships. F3 (member profiles) after F2.
- **Prompt v4 lane SHIPPED, PR #<PR_NUMBER_PENDING> — unified versioned prompt door + v4
  template (split-brain cure) — auto-merge armed.** `zantara_core_v4.py` (deadline-neutral KBLI
  guidance, phantom KBLI codes fixed 55130/55194→55203/55901/55400, `{today_wita}` date
  injection) + `prompt_builder.py` now imports `ZANTARA_MASTER_TEMPLATE` from
  `prompt_manager` (the versioned door) instead of hardcoding v1 — `ZANTARA_PROMPT_VERSION`
  finally reaches the WA bot. **Prod stays on v3 (unchanged) until an operator/session flips
  the env var** — this PR ships the capability, does not flip it. **P0 caught in verification**:
  v3's (and v4's) `WORKED_EXAMPLES` embed illustrative JSON (`{"price_idr": ...}`) that crashed
  `.format()` — dormant only because the split-brain kept prompt_builder.py on v1; would have
  hard-crashed all 4 channels the moment this PR's own fix reached prod (prod's
  `ZANTARA_PROMPT_VERSION` Fly secret is confirmed SET to v3 today). Fixed via
  `_safe_template_fill()` (substring replace, not `str.format()`) — see design doc §9. Full
  detail: `research/operations/2026-07-17-zantara-prompt-v4-design.md`.
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
