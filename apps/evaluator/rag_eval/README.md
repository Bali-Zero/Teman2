# S18 — Zantara RAG truth-eval harness

A real RAG evaluation harness for Zantara prod. Measures **retrieval** (recall@k)
and **generation** (faithfulness / correctness) against a *verified* golden set.

> **This directory now holds TWO harnesses.** This file documents the original
> single-turn one (`rag_eval.py`). The multi-turn conversational baseline
> (`multi_turn_eval.py`) is documented in full below, under
> **"Multi-turn eval — the bot's golden conversation baseline"**.

## Directory map

| File | Turns | Target endpoint | Scores |
|---|---|---|---|
| `rag_eval.py` + `golden_set.json` | single-turn | `/api/oracle/query` (RBAC dashboard API) | recall@k, must_contain, optional LLM judge |
| `multi_turn_eval.py` + `multi_turn_golden.json` | multi-turn | `/api/agentic-rag/query` (the LIVE WhatsApp bot's actual endpoint) | four-outcome gate (SEND/CLARIFY/ABSTAIN/ESCALATE), key-fact coverage, optional LLM judge |
| `scripts/rag_canary.py` (repo root) | n/a | Qdrant direct | liveness probe only (embedding drift + top-k score) — no generation, not duplicated by either harness above |

## Why this exists (scar S2)

The previous audit (`research/operations/2026-05-31-rag-truth-vs-nlm-oracle.md`)
could **not** measure Zantara accuracy: `/api/oracle/query` is RBAC-walled
(requires a JWT bound to a `team_members` row; an MCP/unknown caller gets 401).
This harness is built so it is **provably runnable even while that arm is
blocked** (`--offline`), and runs a full paired eval the moment a JWT is
provisioned (`--jwt`).

## Golden set

`golden_set.json` — 13 Q&A pairs across `kbli / company / tax / property`. Every
`ground_truth` and `must_contain` fact is sourced from artifacts **committed on
`origin/main`** and is grep-verifiable:

- KBLI codes: `apps/backend-rag/scripts/generated_guides/company/kbli_2025_catalogo_completo.txt` (BPS Reg 7/2025)
- Company/capital/nominee: `research/legal/2026-06-02-pt-pma-nominee-ban-bkpm-oss.md`
- Positive list: `research/legal/2026-06-02-positive-investment-list-kbli-foreign-ownership.md`
- Tax: `research/tax/2026-06-02-corporate-withholding-but-coretax.md` + `fact_pmk_131_2024_ppn_effective_rate`
- Property: `research/property/2026-06-02-foreign-property-rights-hak-pakai-hgb-leasehold.md`

No NotebookLM live calls — the golden set is fully self-contained and auditable.

## Metrics

- **recall@k** — fraction of `expected_sources` basenames that appear in the
  top-k `sources` the RAG returns. Pure retrieval signal.
- **must_contain coverage** — fraction of the ground-truth key facts the answer
  asserts (cheap, always runs, no LLM).
- **LLM faithfulness** (`--judge`) — a 0–1 score from a strict judge prompt run
  over the **Claude Max-plan OAuth CLI** (`CLAUDE_CODE_OAUTH_TOKEN`). The judge
  subprocess strips `ANTHROPIC_API_KEY` (Golden Rule: never the paid endpoint).
  If the CLI is missing, the judge degrades to the lexical scorer — it never
  reaches for a paid SDK.
- **asserts_stale_as_current** — guard that flags answers presenting a legacy
  code (e.g. `55193`) as the current 2025 villa code.

The embedding model is **FROZEN** to `text-embedding-3-small` / 1536 dim. The
harness never embeds anything itself; it consumes the prod RAG's own retrieval,
so the frozen embedding is honoured by construction. `load_golden()` asserts the
golden set declares the frozen model/dim.

## Usage

```bash
cd apps/evaluator/rag_eval

# 1. Offline self-check (no prod, no creds) — proves the harness runs.
python rag_eval.py --offline

# 2. Full eval vs prod once a JWT is granted (NEEDS-ANTONELLO).
python rag_eval.py --jwt "$RAG_EVAL_JWT" --k 5 --report report.json

# 3. Add the LLM faithfulness judge.
python rag_eval.py --jwt "$RAG_EVAL_JWT" --judge --report report.json

# 4. Against a local backend.
python rag_eval.py --jwt "$RAG_EVAL_JWT" --local
```

## NEEDS-ANTONELLO

To unblock the prod arm: provision a JWT for a `team_members` row with a service
role (`visa_specialist` / `tax_consultant` / `company_setup`), or authorize the
eval to run from inside the backend venv against `services/rag/query_service`.
Pass it via `--jwt` or env `RAG_EVAL_JWT`. Until then the harness runs
`--offline` and exits 0.

## Tests

```bash
python -m pytest test_rag_eval.py -v
```

No network / no LLM — pins golden-set integrity, the villa verdict (55203), and
the metric functions.

## Villa KBLI verdict

**55203** is correct (`AKTIVITAS VILA`, KBLI 2025 / BPS Reg 7/2025). `55193` is a
legacy KBLI-2020/PP28 source code that maps to 55203; it is absent from the
canonical KBLI 2025 catalog. See `research/operations/S18-rag-eval-FROZEN.json`.

---

# Multi-turn eval — the bot's golden conversation baseline

Built 2026-07-25 (`agent/air-m5/backend-rag/eval-baseline`) per the Zero-ratified
spec's own Verdict (`research/operations/2026-07-24-zantara-bot-consultant-
assistant-spec.md`): *"there is no golden multi-turn eval baseline yet ... the
first executable step is to establish that baseline."* This is that baseline.

## Reuse-first: why extend `rag_eval/`, not `cep/` or `zantara_persona_eval/`

Three existing eval assets were inventoried before writing anything (per the
mandate for this lane):

- **`apps/evaluator/cep/`** — domain-organized golden queries + a grading
  prompt, but the grader is **DeepSeek V4 Pro via a raw paid HTTP call**
  (`run_cep.py::grade_with_deepseek`). DeepSeek was **RETIRED 2026-07-19**
  (CLAUDE.md §5 — pre-authorization revoked, never top up). Its evaluator is
  dead weight; reusing this chassis would mean re-plumbing the grader before
  reusing anything else, so it was not the best fit.
- **`apps/evaluator/zantara_persona_eval/`** — the closest in *spirit*: a
  50-scenario, 3-language, sourced BEHAVIORAL corpus for this exact
  client-facing persona, with an `expected_behavior` taxonomy
  (`state_directly` / `state_then_team` / `defer` / `guarded_canonical`) that
  maps loosely onto SEND/ABSTAIN/ESCALATE. But it is **single-turn per
  language** (one question per scenario per language) and has **no runner** —
  `validate_corpus.py` only does schema + freshness lint, it never calls a
  target. It supplied the single richest source of pre-vetted, sourced facts
  used to build the new golden set below (see per-fact citations).
- **`apps/evaluator/rag_eval/` (this dir)** — **chosen**. It already has a
  real runner with the right shape: `--offline` self-check / `--local` /
  prod modes, a JSON report, and — critically — an LLM-judge pattern that
  correctly shells out to the Claude Max-plan OAuth CLI (never the banned
  paid SDK). It is also the literal asset the spec's Verdict names as *"the
  generation-faithfulness eval, built + golden set, unrun for 7 weeks"* — the
  officially-recognized harness this baseline was asked to complete. `rag_eval.llm_judge`
  is imported and reused as-is by `multi_turn_eval.py` (no forked copy).

`scripts/rag_canary.py` (repo root, currently armed, green every 6h) was read
and is **not** duplicated: it is a pure retrieval/embedding-drift liveness
probe (top-k score against Qdrant directly) with zero generation and zero
conversation — a different sensor for a different failure mode.

**No fourth parallel harness was created.**

## Findings (discovered while building this, not fixed — out of scope for this PR)

1. **The multi-turn harness targets a different endpoint than the single-turn
   one, on purpose.** `rag_eval.py` hits `/api/oracle/query` — RBAC-walled,
   and (per a repo-wide grep of `backend/channels/` and
   `backend/services/integrations/`) **not on the WhatsApp bot's live call
   path at all**. The bot's actual endpoint, confirmed straight from the
   production code that calls it
   (`backend/services/integrations/wa_inbox_bot.py:14,:273`,
   `backend/app/routers/whatsapp_chat.py`), is `/api/agentic-rag/query`. This
   harness targets that endpoint so its numbers describe the bot, not a
   legacy dashboard API.
2. **CLARIFY has no structural signal on `/api/agentic-rag/query`.** The
   orchestrator computes `CoreResult.is_ambiguous` /
   `clarification_question` (`backend/services/rag/agentic/schema.py`) and
   the *other* live endpoint (`/api/oracle/query`, via
   `oracle_service.py:419-420`) forwards them as `clarification_needed`/
   `clarification_question` — but `AgenticQueryResponse`
   (`backend/app/routers/agentic_rag.py:387-404`) never includes them. A
   CLARIFY-expected turn is therefore **ungraded** by this harness
   (`grade_turn` returns `None`, never a fake PASS/FAIL) — see
   `classify_outcome`'s docstring and `_looks_like_clarifying_question`'s
   advisory-only heuristic.
3. **The `[ESCALATE]` marker contract is currently dead code.** Two call
   sites check for it and strip it (`wa_inbox_bot.py:288-289`,
   `whatsapp_chat.py:549-553`), but a repo-wide grep of every
   `backend/prompts/*.py` file (including `channel_overlays.py`, the
   WhatsApp-specific overlay) found **zero instructions telling the LLM to
   ever emit it**. `classify_outcome` still checks for the marker first (it
   is the documented contract and may be reconnected), but ESCALATE-expected
   turns also accept a **phrase-based fallback** — one of
   `ESCALATION_PROTOCOL`'s own canonical strings
   (`backend/prompts/zantara_core.py:383-385`) appearing in the answer — and
   the aggregate report separately counts
   `n_escalate_passed_via_phrase_fallback_only` so this dead-marker fact
   stays visible in every run rather than silently masked by the fallback.
4. **`/api/agentic-rag/query` DOES expose `abstain`/`abstain_reason`**
   structurally (`agentic_rag.py:398-399`) — this is the one outcome the
   endpoint gets right, and matches exactly what `wa_inbox_bot.py:277-282`
   itself reads to decide whether to send a reply at all.
5. **Local `.env`'s `GOOGLE_API_KEY` is revoked** ("Your API key was reported
   as leaked. Please use another API key.", 403 on every Gemini model —
   confirmed live, see "Baseline run status" below). This is a genuine
   security-hygiene finding (the key sat in a local dotfile and got flagged
   by Google) as well as the reason the actual baseline numbers could not be
   produced in this build.

## Golden set (`multi_turn_golden.json`)

11 scenarios / 22 turns. Every `key_facts[].fact` is sourced from an
already-verified, committed artifact — `golden_set.json` (S18), the
`zantara_persona_eval` corpus, or `zantara_core.py::ESCALATION_PROTOCOL`
itself (grep-verified against the live file by
`test_escalation_phrases_are_grounded_in_the_live_prompt`). **No fact was
invented from model memory.**

| id | domain | turns | what it tests |
|---|---|---|---|
| `visa-b211-kitas-distinction` | visa | 2 | SEND x2, turn-2 pronoun ("it") resolution |
| `visa-overstay-then-escalate` | visa | 2 | SEND then red-flag/high-stakes **ESCALATE** (explicit ask to evade enforcement) |
| `visa-duration-ambiguous-clarify` | visa | 2 | deliberately ambiguous **CLARIFY**, then SEND once disambiguated |
| `company-pma-capital-vs-investment` | company | 2 | paid-up capital (2.5bn) vs total investment (>10bn) confusion trap |
| `company-kbli-beachclub-villa-compound` | company | 2 | **compound question** (2 sub-asks in one message) + incidental-villa follow-up |
| `company-kbli-villa-crosswalk` | company | 2 | S18 villa 55193→55203 pair, extended to a follow-up ownership question |
| `tax-vat-then-coretax` | tax | 2 | two unrelated facts, checks no blending |
| `tax-lkpm-then-fictional-regulation-abstain` | tax | 2 | grounded SEND, then a fabricated "2027 draft tax reform bill" — **no-grounding ABSTAIN** |
| `property-hak-milik-then-hak-pakai` | property | 2 | context-retention trap (individual-foreigner framing must not collapse into the PT-PMA/HGB route) |
| `cross-pt-pma-then-explicit-escalate` | company | 2 | SEND then explicit-request **ESCALATE** (the verbatim trigger from the system prompt) |
| `persona-payment-status-defer` | persona | 2 | client-specific status question — **ABSTAIN or ESCALATE** both accepted (spec has not disambiguated these for this case; forcing one would be false precision), SEND is never acceptable |

### Facts this build could NOT source in-repo (left out, not invented)

- `apps/backend-rag/data/curated_qa/` is **empty** in this repo (only a
  README; see its own table: *"none committed by this build — see
  PENDING-ARMS for the E33/golden/prewarm conversion runs"*) — so no facts
  were drawn from it, contrary to the original brief's expectation that it
  would be a source.
- No B211A/C2/C12 exact validity-day figures beyond the ones already in
  `zantara_persona_eval` (VISA-012's "60+60+60=180 days" is *legacy* B211A
  only, explicitly flagged retired nomenclature) were added — the *current*
  short-stay route's exact day-count was not independently verified in this
  build and is deliberately absent from any scenario.

## Grading design

- **Outcome** — structural-first (`classify_outcome`): `abstain` field ->
  ABSTAIN, `[ESCALATE]` marker -> ESCALATE, else SEND. CLARIFY is never
  structurally derivable (see Findings #2) and is reported as an advisory
  heuristic only, never gated. ESCALATE has one disclosed fallback path
  (Findings #3). See `multi_turn_eval.py` module docstring and
  `classify_outcome`/`grade_turn` docstrings for the full contract.
- **Key-fact coverage** — cheap, always-on, no-LLM lexical substring check
  (`key_facts_coverage`), same spirit as S18's `mustcontain_coverage`. A
  floor signal, not a semantic grader.
- **Optional LLM judge** (`--judge`) — reuses `rag_eval.llm_judge` verbatim
  (Claude Max-plan OAuth CLI, `ANTHROPIC_API_KEY` stripped from the
  subprocess env) on SEND-expected turns only. A judge failure (`score:
  None`) is never scored as a content failure — same contract as S18.
- **Never a fake verdict.** `grade_turn` returns `None` (not `True`/`False`)
  when the only expected outcome is CLARIFY — the aggregate report tracks
  `n_ungraded_clarify` separately from `n_passed`/`n_graded` so an ungraded
  turn can never quietly inflate or deflate the pass rate.

## TDD contract (`test_multi_turn_eval.py`, 32 tests, no network/LLM)

Every outcome class has both a **guilt** test (a wrong answer must FAIL) and
an **innocence** test (a correct answer must not be flagged by an
over-eager matcher) — the mandate's explicit requirement, generalized past
just ABSTAIN:

- `test_grade_turn_abstain_expected_but_got_send_is_a_hard_fail` — the exact
  fixture the mandate named ("a scenario that should ABSTAIN and does NOT
  must FAIL the run").
- `test_classify_escalate_phrase_innocence_generic_team_mention` — a normal
  sentence containing the word "team" must NOT be misclassified as an
  escalation signal (guard-over-match regression per
  `.claude/rules/cicatrix-superscar.md` family #3 — matches on the FULL
  canonical phrase, never a short fragment).
- `test_classify_clarify_heuristic_innocence_long_substantive_answer` — a
  long, correct, content-bearing answer is never flagged as a clarifying
  question.
- `test_escalation_phrases_are_grounded_in_the_live_prompt` — anti-
  hallucination: every phrase this harness matches is grep-verified,
  verbatim, against the actual `zantara_core.py` (mirrors S18's
  `test_golden_facts_are_grounded_in_committed_sources`).

```bash
cd apps/evaluator/rag_eval
python -m pytest test_multi_turn_eval.py -v   # 32 passed, <1s, no network
```

## Cost-safety (the Gemini prepay balance hit ZERO on 2026-07-22)

- Sequential only — no `asyncio.gather`, one HTTP call at a time.
- Bounded by the golden set (22 turns) + an explicit `--limit N` /
  `--max-calls N`.
- The cost estimate is **printed before any network call, every run**:
  `turns x ~2 LLM calls/turn (max_steps cap) = ~N LLM calls total`.
- `--prod` alone is refused (exit 2) — a second explicit
  `--confirm-prod-run` flag is required before a single request reaches
  `nuzantara-rag.fly.dev`.
- **Not wired to a cron by this PR.** Manual invocation only.

## Usage

```bash
cd apps/evaluator/rag_eval

# 1. Offline self-check (no network) — proves the harness runs.
python multi_turn_eval.py --offline

# 2. Against a local backend (default http://localhost:8000; override with --api-url).
#    /api/agentic-rag/query sits behind HybridAuthMiddleware — provide ONE of:
export AGENTIC_RAG_API_KEY=<a local-only throwaway key you add to API_KEYS in your local .env>
#    or, to mirror production's actual auth mechanism:
export WA_MIRROR_INTERNAL_KEY=<value of the Fly secret, for a prod-realistic local run>
python multi_turn_eval.py --local --limit 3          # small bounded run first
python multi_turn_eval.py --local --report report.json

# 3. Add the LLM faithfulness judge on SEND turns.
python multi_turn_eval.py --local --judge --report report.json

# 4. Against prod — DOUBLE opt-in, read the cost estimate first.
python multi_turn_eval.py --prod --confirm-prod-run --limit 3
```

## Baseline run status (2026-07-25) — NOT YET a real quality baseline

**The harness is built, tested (32/32 green), and proven to work
mechanically end-to-end** against a live local server (4 real HTTP round
trips, JSON report produced, conversation history threaded correctly across
turns — raw report committed as
`smoke-test-2026-07-25-local-revoked-key.json`). **The numbers from that run
are NOT the quality baseline** and must not be read as one — the filename
and the `_NOT_THE_BASELINE` field inside it say so explicitly:

Every turn came back `abstain=true, abstain_reason="no_relevant_context"`
because the LOCAL `.env`'s `GOOGLE_API_KEY` is revoked by Google:

```
Error with gemini-3.5-flash: 403 PERMISSION_DENIED. {'error': {'code': 403,
'message': 'Your API key was reported as leaked. Please use another API key.'}}
Error with gemini-2.5-flash: 403 PERMISSION_DENIED. {...same message...}
⚠️ LLMGateway: All Gemini models failed, attempting OpenRouter fallback
```

(OpenRouter is not configured either — "OpenRouter API key not configured".)
Qdrant retrieval itself is healthy in this same environment (`/health` -> 15
collections, 122,326 documents) — this is purely an LLM-generation-side
credential failure, not a retrieval problem, confirmed by reading the full
local server log line-by-line rather than inferring it from the abstain
flag alone.

**To produce the real baseline, one of:**
1. Rotate/replace the local `.env`'s `GOOGLE_API_KEY` (it is already dead —
   revoked, so rotating it costs nothing extra) and re-run
   `python multi_turn_eval.py --local --report BASELINE-<date>.json`, or
2. Run against prod with `--prod --confirm-prod-run` (prod's key is live —
   the bot answers real customers today) — recommended to get an explicit
   go-ahead first given the 2026-07-22 Gemini-outage history, even though
   this harness's own cost footprint (22 turns x ~2 calls) is negligible
   against the monthly cap.

Local Postgres (`backend_rag_v2` on `127.0.0.1:15432`) also failed to
authenticate in this environment — harmless for this harness specifically
(`/api/agentic-rag/query` is DB-independent when `conversation_history` is
supplied directly, which this harness always does), but it degrades KG/
analytics features inside the orchestrator and is a separate, pre-existing
local-dev-environment issue outside this PR's scope.
