# Opus 4.7 Routing Audit + Cost Baselines

> §7 of `~/.claude/plans/in-vista-di-questo-hashed-newell.md` — read-only audit.
> Generated 2026-04-17 on branch `opus47-routing-audit`. No code behavior changed.

## TL;DR

1. **Backend is mostly Gemini, not Claude.** `LLMGateway` primary is `gemini-3-flash-preview`
   (`backend/llm/config.py:16`); only 4 services actually call the Anthropic SDK.
2. **No `cache_control` anywhere** in `apps/backend-rag/`. Anthropic's largest single lever
   is unused. Grep matches only in `docs/` and in unrelated cache-invalidation code.
3. **Stale model IDs in production paths** — risk of silent breakage post-Opus-4.7
   tokenizer + API changes. See §3.
4. **Current steady-state cost estimate ≈ $7.7/day ($230/mo).** Moving Claude paths
   to Opus 4.7 blindly would 4×–5× that. A hybrid routing (Gemini hot path + Claude
   critical only, with cache) keeps it ≈ $9.4/day — +22% for HD vision + Opus-grade
   council/KG. See §4.
5. **KG reasoning silently uses OpenAI GPT-4o-mini.** Comment at
   `backend/services/rag/kg_langgraph_orchestrator.py:95` says "Anthropic key is
   invalid in this project" — worth a human decision before §7 closes.

---

## 1. Routing inventory (what's actually running)

Scanned `apps/backend-rag/backend/**` on `origin/main@8d84e1d64`.

| Path | Model used | Effort / tier | Cache? | Notes |
|---|---|---|---|---|
| `llm/config.py:16-18` | `gemini-3-flash-preview` / `gemini-2.5-flash` fallback | n/a | no | SSOT for Gemini (class `ModelName`). |
| `services/rag/agentic/llm_gateway.py:58-60` | Single Gemini tier (`TIER_FLASH=TIER_PRO=TIER_LITE`) | n/a | no | All four tier constants point to `ModelName.PRIMARY`. Claude not wired. |
| `app/routers/kbli_notebook_chat.py` | Gemini via `LLMGateway` | FLASH | no | Dispatches through gateway → Gemini only. |
| `services/knowledge_graph/coreference.py:122` | `claude-sonnet-4-20250514` | n/a | no | Direct `anthropic.Anthropic()` sync call. |
| `services/knowledge_graph/pipeline.py:38` | `claude-sonnet-4-20250514` | n/a | no | Default ctor arg. |
| `services/article_composer/claude_client.py:160` | `claude-sonnet-4-20250514` | n/a | no | Tenacity retry wrapper around sync `messages.create`. |
| `app/routers/article_composer.py:378` | `claude-sonnet-4-20250514` | n/a | no | Hardcoded in 3 places (`:374`, `:378`, `:530`). |
| `services/rag/kg_langgraph_orchestrator.py:96-109` | **OpenAI `gpt-4o-mini`** primary, `claude-sonnet-4-5-20250929` fallback | `temperature=0.2` | no | Comment: "Anthropic key is invalid in this project". |
| `services/rag/multi_agent_coordinator.py` | `ChatAnthropic` (if lib) | n/a | no | Model chosen by caller; no default Opus. |
| `agents/services/multi_ai_adapter.py:136` | `claude-3-opus-20240229` | n/a | no | **Stale Opus 3 default** — called by `ClaudeAdapter`. |
| `channels/optimizations.py` | (utility) | — | — | Uses the word `ephemeral` in a caching context but NOT Anthropic `cache_control`. |
| `services/misc/autonomous_scheduler.py` | (utility) | — | — | Same — non-Anthropic cache. |
| `services/crm/enrichment.py:169` | `qwen3.5:9b` (Ollama local) | n/a | n/a | Pro-only fallback chain. |

Models *not* referenced anywhere in `backend/` on current `main`:

- `claude-opus-4-7`, `claude-opus-4-6`
- `claude-sonnet-4-6`
- `claude-haiku-4-5-20251001`

CLAUDE.md advertises a Claude-tiered routing in §13, but that table currently has
no consumers in `backend/`.

## 2. Prompt-caching survey

```
grep -rnE "cache_control" apps/backend-rag/backend/ → 0 matches outside docs/
```

No Anthropic ephemeral-cache markers. The only `cache_control`-adjacent strings
are in `channels/optimizations.py` and `memory/memory_fallback.py`, both local
Redis/in-memory caches unrelated to LLM provider-side caching.

**Measured** hit rate: N/A (nothing to measure).
**Estimated** opportunity: the system prompt (`zantara_core.py`) is ~4–8k tokens
and stable per request class. A 70% ephemeral-cache hit rate on the Claude paths
cuts their `input` cost ≈ 60% (see §4).

## 3. Stale model IDs / migration risks

| Where | Stale value | Why it matters post-4.7 |
|---|---|---|
| `agents/services/multi_ai_adapter.py:136` | `claude-3-opus-20240229` | Opus 3 is 2.5× more expensive than Opus 4.7. Default kicks in if no model arg passed. |
| `services/article_composer/claude_client.py:160` and 3 other `:*` literals | `claude-sonnet-4-20250514` | Sonnet 4.0, not 4.6. Migrate to `claude-sonnet-4-6` to pick up adaptive thinking. |
| `services/knowledge_graph/coreference.py:122` | `claude-sonnet-4-20250514` | Same. |
| `services/knowledge_graph/pipeline.py:38` | `claude-sonnet-4-20250514` | Same. |
| `services/rag/kg_langgraph_orchestrator.py:106` | `claude-sonnet-4-5-20250929` | Fine as-is but code path is dead (OpenAI wins). |
| `services/article_composer/claude_client.py:187` | sync `client.messages.create` | 4.7 breaks `temperature`/`top_p`/`budget_tokens` — confirm this call path doesn't pass any. Current code is clean; add a regression test before bumping model. |

The plan's §3 sweep (`grep -rE "temperature\|top_p\|top_k\|budget_tokens"`) is still
required before bumping any Claude model here.

## 4. Cost scenarios ($/day → $/month)

Generated by `scripts/cost_baseline.py` — raw output at
`docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2-baseline.json`.

Token shapes are order-of-magnitude estimates based on observed prompt sizes and
the 5 scenarios from the task spec (pricing / KG / vision / CRM / council).
`metrics.py` has the fields populated (input_tokens, output_tokens,
cache_hit) — real values should replace these estimates once we have a week
of 4.7 traffic.

| Variant | $/day | $/month | Δ vs current |
|---|---:|---:|---:|
| **current_no_cache** (today) | 7.68 | 230.51 | baseline |
| current_with_cache (if we added cache_control) | 5.69 | 170.56 | **-26%** |
| all_opus_4_7_with_cache | 32.75 | 982.60 | +326% |
| tiered_4_7_with_cache (Opus/Sonnet/Haiku split) | 13.37 | 401.05 | +74% |
| **hybrid_recommended_with_cache** (§5) | 9.41 | 282.29 | +22% |

**Per-scenario, current routing, no cache:**

| Scenario | Model | $/call | $/day @ N calls |
|---|---|---:|---:|
| pricing (350/day) | `gemini-3-flash-preview` | $0.000578 | $0.20 |
| kg (120/day) | `claude-sonnet-4-20250514` | $0.032 | $3.87 |
| vision (40/day) | `gemini-3-flash-preview` | $0.001 | $0.04 |
| crm (800/day) | `gemini-2.5-flash` | $0.000300 | $0.24 |
| council (60/day) | `claude-sonnet-4-20250514` | $0.056 | $3.33 |

**Observation.** Current spend is dominated by the two Claude paths (KG coref +
council = 94% of cost despite 6% of traffic). That's where caching + model
selection pay back.

## 5. Recommendations (prioritized)

P0 — **do before §7 is called done**

1. **Add `cache_control` to the two Claude call sites** (`services/article_composer/claude_client.py`, `services/knowledge_graph/coreference.py`). Mark `zantara_core.py` + the KB snippet as `{"type": "ephemeral"}`. Expected saving: -26% on current Claude spend with no quality change.
2. **Fix the stale Opus 3 default** in `agents/services/multi_ai_adapter.py:136`. Change to `claude-sonnet-4-6` (Sonnet is the right tier for that adapter's "multi-AI council" role; Opus 3 was a copy/paste from 2024).
3. **Decide on KG Anthropic key.** `kg_langgraph_orchestrator.py:95` has a comment that deserves a human call: either enable Anthropic (loses Gemini fallback chain) or remove the `ChatAnthropic` branch (dead code). Currently we pay OpenAI for KG reasoning while CLAUDE.md says Claude. State mismatch.

P1 — **Migrate to 4.7 + tiered routing**

4. **Bump the 4 `claude-sonnet-4-20250514` call sites to `claude-sonnet-4-6`** (same price tier, gains adaptive thinking). Sweep for removed params first (`temperature`, `top_p`, `budget_tokens` — plan §3).
5. **Introduce Haiku 4.5 for the CRM enrichment path** (`services/crm/enrichment.py` Ollama fallback → Haiku when off-Pro). 800 calls/day × $0.0003 is noise, but it validates the Haiku wiring end-to-end cheaply.
6. **Wire Opus 4.7 for the new vision pipeline only** (§6 of the plan). Don't backfill existing paths — the cost curve doesn't justify it.

P2 — **Telemetry**

7. **Populate `metrics.py` cache_hit columns** so cost_baseline.py can be re-run against real data instead of estimates. Fields already exist (`metrics.py:903`, `:1014`, `:1401`).
8. **Add `model_used` to every structured log** emitted from `LLMGateway.send_message` so we can attribute spend by scenario from logs alone. Hooks in place, just need consistent field naming.

P3 — **Tidy**

9. **Delete the unused `TIER_PRO`/`TIER_LITE` aliases** in `llm_gateway.py:58-60`. They all point to the same Gemini model — misleading to readers. If/when we actually add tiers, reintroduce them.

## 6. Non-changes (scope NO)

Per the task spec we did not:

- Change any default model ID.
- Touch `fly.toml`, `zantara_core.py`, Alembic, or cron schedules.
- Modify the new vision pipeline (it isn't committed on `main` yet).
- Merge or push the branch.

## 7. Artifacts

- This report: `docs/opus47-routing-audit.md`
- Cost script: `scripts/cost_baseline.py`
- Baseline JSON: `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2-baseline.json`
- Session log: `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-2.log`

---

## 8. Addendum 2026-04-17 — OAuth-only policy

After the audit landed the operator clarified a **binding project policy**
(see `~/.claude/projects/-Users-nuzantara/memory/feedback_claude_oauth_only.md`):

> **Mai ANTHROPIC_API_KEY. Sempre e solo Claude Max OAuth token.**

The Max plan is already paid flat-rate. Any Claude call that goes via API key
double-bills (flat-rate + pay-as-you-go). This reshapes the recommendations:

### What this changes

- **P0.1 `cache_control` saving is NOT monetary.** $–26% in §4 assumes
  pay-as-you-go billing. On Max flat-rate the dollar saving is 0. The real
  benefits of caching are now **latency** + **rate-limit headroom** against
  the Max token bucket. `cache_control` is still worth doing — just for a
  different reason.
- **P0.3 "Decide on KG Anthropic key" is resolved.** The answer is neither
  "rinnova la key" nor "lascia OpenAI". The answer is **migrate the KG
  reasoning path to Claude-via-OAuth**, same way `scripts/cron-agent.sh`
  does it for Tier 2 cron jobs (`CLAUDE_CODE_OAUTH_TOKEN_{1,2,3}` + `claude
  -p` subprocess with 3-token fallback). Until that migration lands,
  OpenAI GPT-4o-mini remains the de-facto LLM for KG reasoning, as
  documented in code comments.
- **P1.4/P1.5/P1.6 model-bump items are unblocked** only *after* OAuth
  migration. Bumping `claude-sonnet-4-20250514` → `claude-sonnet-4-6` today
  just bumps the wrong billing path.

### The 3 Anthropic-SDK call sites

All three currently instantiate `anthropic.Anthropic(...)` directly and
**cannot** accept a Max OAuth token (SDK requires API key). They are:

| File | Instantiation |
|---|---|
| `services/article_composer/claude_client.py:135` | `anthropic.Anthropic(api_key=api_key)` with explicit `ValueError` if no key. |
| `services/knowledge_graph/coreference.py:122` | `anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()` (picks up env). |
| `agents/services/multi_ai_adapter.py:144` | Same dual-mode pattern as coreference. |

Plus the LangChain wrapper `ChatAnthropic(..., api_key=anthropic_key)` in
`services/rag/kg_langgraph_orchestrator.py:106` (currently a dead branch
because OpenAI wins the `if`).

### Applied in this session (commits on `opus47-routing-audit`)

1. **`23673a89a` — `feat(claude): cache_control ephemeral on 2 active Claude paths`**
   Adds `cache_control: {"type": "ephemeral"}` to the two hot `messages.create`
   calls in `claude_client.py` and `coreference.py`. Pure latency/headroom win.
2. **(this commit) — `chore(claude): policy guard + OAuth-migration markers`**
   - Loud `logger.error` every time the 3 API-key paths execute.
   - `TODO(OAuth):` markers on the 3 SDK call sites + the LangChain branch.
   - `ClaudeAdapter` docstring rewritten to point at the OAuth migration.
   - Legacy "Anthropic key is invalid in this project" comment in
     `kg_langgraph_orchestrator.py` replaced with an accurate "OAuth
     migration pending" note.

### What's NOT applied in this session

Full OAuth migration (replacing `anthropic.Anthropic` with `claude -p`
subprocess + LangChain `BaseLLM` adapter wrapping the same) is a larger
refactor with:

- new test surface (subprocess mocking, 3-token fallback matrix)
- behavior changes (no streaming from `claude -p --output-format=text`,
  need to check `--output-format=json` + parse)
- security implications (token file handling, stderr scrubbing)

It belongs in a dedicated session, tracked as a follow-up.
