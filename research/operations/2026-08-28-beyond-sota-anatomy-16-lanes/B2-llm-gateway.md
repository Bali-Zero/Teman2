---
date: 2026-08-28
domain: operations
part: B2 llm-gateway
scope: LLM gateway — apps/backend-rag/backend/llm/* (providers, adapters, OAuth CLI client, registry, retry, token estimator, metrics), services/{llm_clients,routing,response}, prompts/zantara_core.py (SSOT, read-only), router llm_costs, the multi-provider cascade (backend + cron wrappers) and cost accounting
sources:
  - https://docs.litellm.ai/docs/routing
  - https://docs.litellm.ai/docs/proxy/users
  - https://portkey.ai/docs/product/ai-gateway/configs
  - https://openrouter.ai/docs/features/provider-routing
  - https://github.com/maximhq/bifrost
  - https://github.com/lm-sys/RouteLLM
  - https://arxiv.org/abs/2506.16655
  - https://docs.helicone.ai/features/advanced-usage/caching
  - https://langfuse.com/docs/prompt-management/get-started
  - https://www.braintrust.dev/docs/guides/evals
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - https://platform.claude.com/docs/en/build-with-claude/effort
  - https://platform.claude.com/docs/en/build-with-claude/structured-outputs
  - https://platform.claude.com/docs/en/api/handling-stop-reasons
  - https://developers.openai.com/api/docs/guides/prompt-caching
  - https://github.com/zilliztech/GPTCache
  - https://github.com/NVIDIA/NeMo-Guardrails
  - https://ai.google.dev/gemini-api/docs/caching
  - https://code.claude.com/docs/en/cli-reference
  - https://www.anthropic.com/research/constitutional-classifiers
  - https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html
  - https://opentelemetry.io/docs/specs/semconv/gen-ai/ (redirect notice only)
  - https://dspy.ai/learn/optimization/optimizers/ (redirect only, unverified)
status: DONE 2026-08-28T15:05:00Z
adversarial_review: kimi-k3
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


# B2 — LLM gateway: anatomy, honest state, world's best, and the road beyond

Measured on `origin/main` @ `11a3c89a2e` in `.worktrees/ops-beyond-sota-0828`, static reading only
(grep/wc/sed; no code executed, no tests run). Every `file:line` below was read in this session;
external claims carry the URL they were fetched from (access date 2026-08-28). Where I could not
verify, it says **(unverified)**. Neighbours not covered: B1 retrieval (the *retrieval* half of
`services/rag`), B3 channel logic, X3 session-level arsenal doctrine.

## 1. Anatomy (as measured)

**Size.** `backend/llm/` = 26 Python files, **9,010 LOC**; `services/llm_clients/` 1,281;
`services/routing/` 3,714; `services/response/` 1,020; `prompts/` 3,276 (of which `zantara_core.py`
508 + four sibling versions `_v2.._v5` 1,692); router `llm_costs.py` 103. Tests touching the part:
**47 files, 15,153 LOC** (`find tests -path "*llm*"`). Non-test importers of `backend.llm`: **58
files** — the busiest targets are the package root (44 import statements), `genai_client` (33),
`claude_oauth_langchain` (19), `zantara_ai_client` (13), `retry_handler` (13).

**What the "gateway" actually is — five layers that do not share a spine.**

| Layer | Where | What it does (measured) |
|---|---|---|
| Provider ABC + registry | `llm/base.py:14-95`, `llm/provider_registry.py:57-85` | `LLMProvider.generate/stream`; registry auto-registers `gemini`, `openrouter`, `ollama`, `mlx` only. `LLMResponse` has `content/model/tokens_used/finish_reason/provider` — **no refusal, no cache, no cost field**. |
| Prompt "adapters" | `llm/adapters/registry.py:1-40` | Every model name resolves to `GeminiAdapter` (even the string-match fallback). Gemini-only by construction. |
| Production answering path | `services/rag/agentic/llm_gateway.py` (1,285 LOC; B1 territory by path, gateway by function) | Docstring `:208-236`: "Flash → Flash-Lite → OpenRouter". Reality `:263-265`: all three tiers are `ModelName.PRIMARY`/`FALLBACK` (Gemini); the chain `:575-588` is Gemini→Gemini; OpenRouter is a lazy client `:344-365` behind a kill switch that is **disabled by default** (`openrouter_client.py:95-114`, COS-LAW-013). A stale comment `:272-274` still promises "Tier 2: claude-3-5-haiku / Tier 3: gpt-4o-mini". Circuit breaker per model, threshold 5 `:279-282`. Quota classification is *structured* (`.code`/`.status`, `:111-158`) with text only as a secondary hint — the one place this is done right. |
| Claude Max OAuth CLI client | `llm/claude_oauth_client.py` (984 LOC) | Shells out to `claude -p` (`:1-17`). Seat loop over `CLAUDE_CODE_OAUTH_TOKEN_1..4` + legacy + keychain (`:194-218`); **seats 5-6 are deliberately out of the hot path** (`tests/unit/llm/test_claude_oauth_client.py:104` labels slot 5 "team-slot-not-in-hot-path"; `FLEET_TOPOLOGY.json` names 6). `_build_env` strips `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, Bedrock/Vertex selectors (`:126-144, 221-240`) — the defense-in-depth the mandate mentions, verified. Three regex classes (`:72-124`) separate durable quota (15-min seat cooldown, `:308`) from transient 429. `--json-schema` structured path feature-probed once per process (`:424`), real `usage` parsed from the envelope (`:469-545`); **text calls do not use the JSON envelope**, so their token counts are `len(prompt)//4` (`:606`). Tools denied by allowlist-inverse (`:157-170`). No `--effort` is ever passed (grep: zero hits). |
| Channel client | `llm/zantara_ai_client.py:52-130` | Gemini via `google-genai`, model `ModelName.CHANNEL`; fallbacks are **canned messages** (`fallback_messages.py`), not other providers. |

**Dormant or dead providers still in the tree.** `openai_responses_client.py` (1,706 LOC) and
`codex_exec_client.py` (1,268 LOC) both open with "THIS FILE HAS ZERO WIRING" (`:1-28` each) —
kept by the 2026-08-15 ADR; the live ChatGPT leg is the *pull-broker on Pro* (`research/operations/
2026-08-19-bot-chatgpt-provider-broker-spec.md` §0-1: Fly is not a Codex host, C1). `deepseek_client.py`
documents a provider **retired 2026-07-19** yet is still imported by 4 non-test modules
(`app_factory.py`, `routers/article_composer.py`, `article_composer/{claude_client,error_handler}.py`).
`providers/mlx.py` (213 LOC) has no production caller I could find.

**Configuration.** `llm/config.py:21-76`: Gemini model slugs are env-overridable (`PRIMARY_MODEL_NAME`,
`FALLBACK_MODEL_NAME`, `CHANNEL_MODEL_NAME`) against an allowlist — a typo keeps the default and logs
(`:44-52`). `GenerationConfig:97-107` still carries `temperature/top_p/top_k` defaults (fine for
Gemini; irrelevant for the CLI path, which never sends sampling params). The prompt SSOT is selected
by `ZANTARA_PROMPT_VERSION`, default **v1** (`llm/prompt_manager.py:46-49`), five versions on disk
as file copies.

**Cost accounting.** One ledger, triple-written: Prometheus + Postgres `llm_cost_events` (migration
`117_llm_cost_events.sql:26-40`: provider, model, in/out/cache_hit tokens, cost_usd, endpoint,
request_id, success, error_class, latency_ms) + daily JSONL on `/data`
(`services/observability/llm_cost_recorder.py:1-27`). Remote agents POST to
`/api/admin/llm-costs/record` behind an admin/founder role check (`routers/llm_costs.py:27-73`). A weekly
`CostAdvisor` mines it and asks Claude for cheaper substitutions (`cost_advisor.py:1-17`). Pricing
table `services/llm_clients/pricing.py:75-150` covers Gemini/DeepSeek/OpenRouter — **no `claude-*`
row exists** (grep: 0 hits); what `calculate_cost` charges an unknown slug is **(unverified)**. A
second, separate metrics sink — Redis Stream `llm:metrics`, MAXLEN 10,000 (`llm/metrics_emitter.py:20-21`)
— is written by `ollama_client`, `genai_client` and `llm_gateway` and **read by nothing** in
`apps/`, `scripts/`, `infra/` (grep). Two token estimators coexist: 1.3 tokens/word
(`token_estimator.py:15,26`) and `len//4` (`claude_oauth_client.py:606`).

**Observability.** Langfuse POC with OpenInference auto-instrumentors for Anthropic/Google GenAI/OpenAI
(`core/observability.py:59-79`), initialised at app start (`app/setup/app_factory.py:105-109`);
default host is Langfuse **US cloud** (`core/observability.py:107`). OTEL `gen_ai.*` attributes are
emitted only on the manual Claude-CLI span (`claude_oauth_client.py:37-70`, attribute `gen_ai.system`).

**Routing that is not model routing.** `services/routing/query_router.py:1-17` routes *queries to
Qdrant collections*; `surface_router.py:1-11` adds a Haiku 4.5 classifier layer (`:427`) behind
`SURFACE_ROUTER_ENABLED=false` (shadow, `:35`). `services/response/` is post-processing:
identity/filler regex validator (`validator.py:16-30`), multilingual out-of-domain detector
(`cleaner.py:1-30`). Guardrails are **prompt text** (`prompts/zantara_core.py:16-40` SECURITY_BOUNDARY)
plus those regexes — no classifier rail on input or output.

**The cron cascade.** `infra/launchagents/wrappers/claude-cascade.sh` (894 lines): Claude seats →
`agy` (Gemini 3.1 Pro) → Kimi K3 → `codex exec` → `ollama run qwen3.5:9b` (`:4-12`), quota detection
by grep (`:173-181`), with a framed-diagnostic gate because "some Claude CLI auth/quota failures
incorrectly return exit 0" (`:381-384`) and a special case for agy's "lying success" (`:455-460`).
The quota phrase `out of extra usage` is hand-copied into **19 non-test files** (grep list in
session: wrappers, `scripts/*.py`, `scripts/army/*`, `kbli_triangle/editorial_writer.py`, both backend
CLI clients, `apps/backend-rag/scripts/{auto_verifier,verified_generator}.py`).

**Constraints the part lives under** (`SYMBIOSIS.md` §LE LEGGI, read `:174-277`): Law 1 "CLI-only
for LLM — never HTTP API Anthropic/Google/OpenAI, DeepSeek API the only exception"; Law 2 PII
output boundary, with the explicit admission that *cloud inference on chat text with PII has no
per-client Art. 56 basis today and the required conduct is fail-closed — an open enforcement gap*;
Law 4 graceful degradation; Law 6 offline is a natural state; Law 7 numbers first.

**Scars that already touch this part.** W92 (bare `429` in a quota regex matched KBLI codes 42911-42919
→ infinite backoff on valid output; `cicatrix-scars.md:589-599`, family #3); W104 (judge the reply,
never the exit code; `:799-816`); the family-#3 note that the cascade regex "è COPIATO in N wrapper"
(`:597`). Prior research already on this part, not re-proposed here: the measured 30-day Gemini bill
($51.32, 78% on `rag.gateway.chat`; ledger 2,587 rows vs 6,390 real requests because four live Gemini
lanes never call the recorder — `2026-08-09-llm-model-cost-quality-comparison.md` §0, §5); the
verdict that semantic caching for the bot is *skipped with numbers* and implicit Gemini caching is
already healthy (`2026-08-20-token-cost-lanes-disposition.md` Lane 1); the panel finding that a single
egress gateway is "the lever we're missing whole" (`2026-08-12-frontier-llm-token-cost-practices.md`
§5, cure X2 broker); the ADR NO-GO on the ChatGPT subscription as a Fly-side runtime credential and
the pull-broker that replaced it (`2026-08-15-adr-wa-runtime-openai-provider.md` §2; broker spec §1).

## 2. Honest state vs. SOTA

- **Doctrine and code disagree in four places, in both directions.** Law 1 says CLI-only and bans
  HTTP APIs for Google; production answers clients through the Google HTTP SDK with an API key
  (`genai_client.py:427-491`, Vertex path "TEMPORARILY DISABLED" `:461`). Three docstrings say the
  Claude CLI "hangs inside the Fly container" (`deepseek_client.py:4-5`, `llm_cost_recorder.py:26-27`,
  `article_composer/claude_client.py:9-10`) while the Dockerfile now bakes a Node 22 donor stage
  *because* `claude_oauth_client.py` shells out to it (`apps/backend-rag/Dockerfile:70-86`); whether
  the OAuth path actually works live on Fly is **(unverified)**. `scripts/cost_baseline.py:27-40` prices
  Opus 4.7. A newcomer reading doctrine builds the wrong system.
- **The cascade is a pattern, not a component.** At least seven independent fallback loops
  (Gemini gateway, seat loop, `gemini_service` OpenRouter fallback, `zantara_ai_client` canned
  fallbacks, `retry_handler` keyword classifier `retry_handler.py:20-52`, `claude-cascade.sh`,
  `multi_ai_adapter.py:240-355`), each with its own quota grammar. This is exactly the shape the
  frontier moved away from (§3: LiteLLM/Portkey/Bifrost centralise routing, budgets and retries).
- **Cost is tracked, not governed.** Triple-write ledger is SOTA-grade *recording*; there is no
  admission control. The v2 design declared "real-time spending caps / rate-limiting" out of scope
  (`docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md` §3). Since then the Gemini
  prepay balance hit zero four times and the WhatsApp bot went silent each time (memory
  `MEMORY_BOT_AND_LLM_LANES.md` §1; the sentinel `services/hardening/llm_credit_sentinel.py:1-9`
  records ~34h of mute bot on 2026-07-28). Detection exists; prevention does not.
- **The ledger measures the wrong unit for most of the arsenal.** Four of the five Claude seats and
  the Codex/Kimi/agy seats are flat subscriptions: their scarce resource is a rolling 5-hour window
  and weekly caps, not USD. Nothing in the part models window headroom; seat choice is fixed order
  first-available (`claude_oauth_client.py:194-218`). `scripts/claude_seat_quota.py:1-30` proves
  headroom *is* readable (only from interactive Keychain profiles; cron tokens get 403) and Pro
  publishes it, but no router consumes it.
- **Modern provider controls are unused on the Claude path.** `--effort` (CLI supports
  `low..max`, source 19), `--max-budget-usd`, always-on `--output-format json` with real `usage` and
  `total_cost_usd` (source 19) — none used; every CLI call runs at the default `high` effort.
  Structured output is native on Gemini (`genai_client.py:676-743`) and on the CLI when a schema is
  passed, but the LangChain shim still emulates JSON by prompt + regex (`claude_oauth_langchain.py:9-11,
  251, 330`) for 19 importers.
- **Refusal is handled per provider, not per gateway.** Gemini `prompt_feedback/finish_reason`
  handled (`genai_client.py:225-243`); the dormant OpenAI client models refusal explicitly
  (`openai_responses_client.py:68-75, 461-462`); the Claude CLI envelope check is `is_error` only
  (`:469-545`) — a family-5 refusal (HTTP 200, `stop_reason: refusal`, source 14) has no
  representation in `LLMResponse`.
- **Prompts are versioned by file copy, evaluated by hand.** Five versions, env-selected, no prompt
  hash in the ledger, no registry labels, no CI eval; golden sets exist (`apps/backend-rag/scripts/
  golden_answers_questions.yaml`, `scripts/bot/wa_blind_bench.py`) but the 2026-08-09 measurement
  found the verifier "accepts almost everything" (26/30 false accepts) — the judge is not yet a gate.
- **Where the part is already at or above SOTA:** the `_build_env` credential-stripping and
  argv-smuggling guards; the structured 429 classification in the gateway; durable-vs-transient
  quota separation with per-seat cooldown; the indestructible triple-write ledger; the framed
  diagnostic gate that refuses to scan successful content for "quota" (a lesson LiteLLM-style
  keyword retries do not encode).

## 3. Deep research: the world's best

**LiteLLM (proxy/router)** — strategies `simple-shuffle`, latency-based, usage-based-v2 (Redis TPM),
least-busy, cost-based, custom; cooldown after `allowed_fails` (default 3/min) for `cooldown_time`
(default 5 s); `RetryPolicy` per error *class* (e.g. `AuthenticationErrorRetries=0`); pre-call
context-window and region filtering; weighted failover within a group before cross-group fallback
(source 1). Budgets at proxy/team/member/key/model/end-user/agent level with `budget_duration`
resets, **budget reservation** (estimate max cost before the call) and `fail_closed_budget_enforcement`;
exceeding returns a clean `400/429` with a typed `budget_exceeded` error; DB-less deployments fail
open silently (source 2). *Technique to steal:* typed error classes + budget reservation + a clean
429 the caller can catch.

**Portkey (gateway configs)** — one declarative JSON config: `strategy.mode ∈ {fallback, loadbalance,
conditional, single}`, weighted `targets`, and per-target `default_params / override_params /
drop_params` to shape requests without touching callers (source 3; retry/cache/guardrail schemas were
not on the fetched page). *Technique:* routing as data, not code.

**OpenRouter (provider routing)** — default price-based load balancing with inverse-square weighting
(a $1 provider gets 9× the traffic of a $3 one), and a `provider` preference object with `order`,
`allow_fallbacks`, `require_parameters`, `data_collection: allow|deny`, `zdr` (zero-data-retention
only), `only/ignore`, `quantizations`, `sort`, `max_price` (source 4). *Technique:* **data-handling
policy as a routing filter** — the closest public analogue to what UU PDP needs, but per provider,
not per message.

**Bifrost (Maxim)** — Go gateway claiming 11 µs added latency at 5k RPS on a t3.xlarge, semantic
caching, governance/rate limits, Prometheus + tracing, MCP tool support, 23+ providers; the "50×
faster than LiteLLM" header has no published benchmark (source 5). *Lesson:* the gateway can be
near-zero overhead; the cost is in the policy, not the hop.

**RouteLLM (LMSYS)** — routers (matrix factorisation, BERT, similarity-weighted Elo, causal LLM)
predict the strong-model win rate per prompt; a calibrated threshold (e.g. 0.11593 for 50% strong
routing) trades cost for quality; reported up to 85% cost reduction while keeping 95% of GPT-4
quality on MT-Bench/MMLU/GSM8K; served as an OpenAI-compatible endpoint with `router-<name>-<thr>`
in the model field (source 6). **Arch-Router** — a 1.5B model that maps queries to *user-defined
domain/action policies*, adding models without retraining (source 7; abstract only, no numbers
extracted). *Technique:* difficulty routing with a small local router — feasible at $0 on the Macs.

**Helicone (edge cache)** — cache key = hash(seed, URL, body, headers, bucket index); `Cache-Control:
max-age` (default 7 d, max 365 d), bucket size up to 20 variants, seeds for namespaces,
`Ignore-Keys` to exclude volatile JSON fields (source 8). **GPTCache** — embedding → vector store →
similarity evaluator → cache manager with LRU/LFU eviction; claims "10× cost, 100× speed"; explicitly
warns about semantic false positives/negatives (source 16). *Lesson:* the bot corner's decision to
skip semantic cache (hits bypass the abstain gate) is aligned with GPTCache's own caveat.

**Langfuse (prompt management)** — prompts versioned automatically, labels `production/latest`,
SDK-side caching so the app survives Langfuse downtime, prompts linked to traces to compare versions,
experiments on datasets before promotion (source 9). **Braintrust (evals)** — `Eval(data, task,
scores)`, LLM-as-judge + deterministic scorers, immutable experiments, CI regression detection on PRs,
online scoring of production traces asynchronously (source 10). *Technique:* prompt hash on every
trace + eval gate in CI.

**Anthropic platform controls** — prompt caching: min cacheable prompt 512 tokens on Opus 5/Fable 5,
1,024 on Sonnet 5/Opus 4.8, 4,096 on Haiku 4.5; writes 1.25× (5 min) / 2× (1 h), reads 0.1×; 4
breakpoints, 20-block lookback; strict `tools → system → messages` prefix; thinking-parameter changes
invalidate messages cache (source 11). `effort` in `output_config`, five levels, default `high`; on
Opus 5 "use low and medium liberally as your primary control for token cost" and *thinking cannot be
disabled at xhigh/max*; changing effort mid-conversation breaks the cache (source 12). Structured
outputs via `output_config.format` json_schema + `strict` tools; refusals still return schema-valid
JSON with `stop_reason: refusal`; compiled grammars cached 24 h (source 13). Stop reasons: `refusal`
is **HTTP 200 with `stop_details`**, recommended handling is fallback to another model;
`model_context_window_exceeded` = truncated (source 14). **Claude Code CLI** headless: `--print`,
`--output-format json|stream-json`, `--json-schema`, `--effort low|medium|high|xhigh|max`,
`--max-turns`, `--max-budget-usd`, `--disallowedTools`; JSON envelope carries `result, usage,
is_error, total_cost_usd, num_turns, session_id` (source 19). Constitutional Classifiers: jailbreak
success 86% → 4.4%, +0.38% refusals on production traffic, +23.7% compute (source 20).

**OpenAI prompt caching** — automatic; min 1,024 visible tokens on GPT-5.6+ (2,048 earlier); reads
0.1× and writes 1.25× the uncached input rate; 30-min retention on GPT-5.6+; `prompt_cache_key`
steers routing; `usage.input_tokens_details.cached_tokens` (source 15). **Gemini** — implicit caching
on by default, minimum 4,096 tokens for a hit on 3.x Flash / 3.1 Pro (2,048 on 2.5); usage field
`total_cached_tokens`; "put large common content first" (source 18; discount % not on the page).

**Guardrails** — NeMo Guardrails: five rail types (input, dialog, retrieval, execution, output),
Colang flows, integrations for jailbreak/injection detection and fact-checking; every rail is an
extra model call (source 17). **Local serving** — vLLM automatic prefix caching reuses KV blocks for
shared prefixes (`enable_prefix_caching=True`); it speeds prefill only, not decode (source 21) —
relevant as a concept for the Macs, where the serving stack is Ollama/MLX, not vLLM.

**OpenTelemetry GenAI semconv** — the spec moved to `github.com/open-telemetry/semantic-conventions-genai`;
attribute names/stability could not be verified in this session (sources 22-23 returned redirects).
DSPy optimisers likewise **(unverified)**.

## 4. Gap table

| Capability | Nuzantara today (measured) | World best (source) | Gap |
|---|---|---|---|
| Single egress gateway | ≥7 hand-rolled cascades; quota phrase copied in 19 files | One router with typed errors, per-class retry, cooldowns (1, 3, 5) | Structural — the panel's #1 lever (2026-08-12 §5) still unbuilt |
| Budget admission | Ledger only; caps declared out of scope; 4 prepay depletions → mute bot | Budget reservation + fail-closed + clean 429 (2) | Missing entirely |
| Seat/quota-aware routing | Fixed seat order; 15-min cooldown after failure; seats 5-6 idle | Usage-based routing on TPM/RPM (1); price-weighted balancing (4) | No public product schedules *subscription windows* — open field |
| Effort / thinking control | Never set on CLI path (default `high`) | `effort` is the primary cost lever on Opus 5 (12); CLI `--effort` (19) | One parameter away |
| Real token accounting | Text CLI calls `len//4`; 1.3/word estimator; 4 Gemini lanes unrecorded; no `claude-*` price row | Usage from envelope/SDK on every call (11, 15, 19) | Ledger undercounts; unit is USD even for flat seats |
| Refusal semantics | Gemini yes; Claude CLI `is_error` only; no field in `LLMResponse` | `stop_reason: refusal` + `stop_details`, fallback model (13, 14) | Silent mis-classification risk on family 5 |
| Structured outputs | Native Gemini; CLI `--json-schema` probed; LangChain shim regex-parses | Grammar-constrained, schema-valid even on refusal (13) | Partial |
| Prompt caching | Gemini implicit verified healthy (2026-08-20); Claude CLI: not applicable to caller | Breakpoints/TTL/usage fields (11, 15, 18) | Already right where it matters; do not build |
| Semantic cache | Skipped with numbers; hits bypass abstain gate | GPTCache warns of false positives (16) | Correctly deferred; revisit only post-abstain at go-public |
| Prompt registry + evals | 5 file copies, env-selected, default v1; human-run bench; judge unmeasured | Versions/labels/trace links (9); CI eval gates + online scoring (10) | Missing |
| Guardrails | Prompt text + regex validator/out-of-domain | Classifier rails, input+output (17, 20) | No model-based rail; cost/latency budget unset |
| Data-policy routing | Cloud egress ungated per message (Law 2 gap admitted) | `data_collection`/`zdr` provider filters (4) | Beyond-SOTA opportunity: per-message class |
| Observability | Langfuse POC (US cloud host default), OTEL attrs on one path, Prometheus counters, dead `llm:metrics` stream | OTEL GenAI semconv (22, unverified), online scoring (10) | Partial; PII posture of traces unverified |
| Doctrine ↔ code | Law 1 vs HTTP SDK; 3 "CLI hangs on Fly" docstrings vs Dockerfile Node 22 stage | — | Drift; needs Zero for Law 1 |

## 5. Recommendations — reach SOTA

Effort S = ≤1 session, M = 2-4 sessions, L = a lane. All actionable by one owner + sessions;
none needs a paid Anthropic key. Every metric is falsifiable on disk or in the ledger.

**R1 (P0, S) — Real usage on every Claude CLI call.** *What:* always run `claude -p --output-format json`
(text calls too), parse `result`/`usage`/`total_cost_usd` through the existing `_parse_json_envelope`
(`claude_oauth_client.py:469-545`), and persist `usage_source` by adding a nullable column to
`llm_cost_events` (superscar #9: both writer and readers in one PR). *Why:* today every text call
books `len//4` (`:606`); the CLI already reports real counts (source 19). *Risk:* envelope shape drift
— guarded by the existing NDJSON fallback. *Metric:* share of `provider='claude_oauth'` ledger rows
with `usage_source='cli_envelope'` ≥ 95% over 7 days (today ≈ only schema calls).

**R2 (P0, M) — Budget admission gate with a clean typed failure.** *What:* `backend/llm/budget.py`:
Redis rolling counters per `(provider, endpoint)` (hourly + daily USD caps for Gemini; call caps for
seats), checked *before* `llm_gateway._call_model` and `claude_oauth_client.complete_async`; on breach
raise `LLMBudgetExceeded` (typed, no retry) which `wa_outbox_worker` maps to the existing
`get_fallback_message("service_unavailable")` instead of five retries and silence; alert via the
existing dedup path (`llm_gateway.py:160-200`). Mirrors LiteLLM reservation + fail-closed (source 2).
*Why:* four depletions → mute bot; caps were out of scope in April. *Risk:* false halts — caps
default to 3× the measured 30-day peak; kill switch `LLM_BUDGET_ENFORCE=false`. *Dependencies:* Redis
(already the cache backend). *Metric:* chaos test with cap=$0.01 → next call raises within one
request, client receives the fallback text, ledger shows `error_class='budget_exceeded'`, zero retries.

**R3 (P0, M) — One error taxonomy, one quota grammar.** *What:* `backend/llm/errors.py` with
`LLMError{RateLimited(transient), QuotaExhausted(durable), AuthDead, Refused, Truncated, Budget}`;
`retry_handler.py` gets a `RetryPolicy` per class (LiteLLM pattern, source 1) and drops the substring
sets at `:20-22`; the framed regexes from `claude_oauth_client.py:72-124` become the single Python SSOT
and a generated `infra/llm-quota-pattern.sh` that `claude-cascade.sh:173-181` sources, with the W92
guard `(?<![\d/])429(?![\d/])`. Add each pattern to `infra/guard-conformance/` with guilt + innocence
corpora (family #3: "42911" and "quota di mercato" must pass). *Metric:* `grep -rl "out of extra
usage"` non-test count 19 → ≤ 2, enforced by a CI lint; conformance corpus green.

**R4 (P0, S×4) — Close the ledger blind spots already named.** *What:* wire `record_llm_call` into
the four live Gemini lanes listed in the 2026-08-09 report §5 (`legal_ingestion_service`,
`zantara_ai_client.py:393/532`, `gemini_service.py:249`, `chat_session.py`), and add a `claude-*`
family row to `pricing.py` (value irrelevant for flat seats but `cost_usd` must not silently be
"unknown"). *Metric:* 30-day `count(*)` in `llm_cost_events` for `provider='gemini'` within 15% of
Cloud Monitoring `request_count` (was 2,587 vs 6,390).

**R5 (P0, S) — Refusal and truncation as first-class outcomes.** *What:* add `refusal: bool`,
`refusal_reason`, `truncated: bool` to `LLMResponse` (`llm/base.py:23-30`); Gemini fills them from
`finish_reason/prompt_feedback` (`genai_client.py:225-243`), the CLI path from the envelope (the
exact `stop_reason` exposure in the CLI JSON is **(unverified)** — first task is a 10-line probe on
Pro), OpenAI from its typed items; callers never fold a refusal into a success (source 14). *Metric:*
a fixture with a refusal envelope yields `refusal=True` and `error_class='refusal'` in the ledger,
never a client-facing answer.

**R6 (P1, S) — Effort routing on the Claude path.** *What:* `effort: Literal[...] | None` on
`complete_async` → `--effort`; set `low` for the surface classifier (`surface_router.py:427`) and
`medium` for coreference; keep `high/xhigh` for composers. Hold effort constant per prompt family
(cache rule, source 12). *Metric:* classifier output tokens per call −40% at equal pass rate on the
existing `test_surface_router` fixtures; seat cooldown events/day not increased.

**R7 (P1, M) — Routes as data.** *What:* `backend/llm/routes.yaml` keyed by `endpoint`: chain
`[primary, fallback…]`, effort, `max_tokens`, `allowed_data_classes`, budget id — consumed by both
`llm_gateway` and `claude_oauth_client`; CI lint that every `endpoint=` string passed to
`record_llm_call` exists in the table. Portkey's config model (source 3) is the shape; `FLEET_TOPOLOGY.json`
stays the account SSOT and is referenced, not duplicated. *Metric:* zero `endpoint IS NULL` ledger rows
(30 d; today 276 rows in the 2026-08-09 snapshot).

**R8 (P1, M) — Prompt registry without touching the SSOT.** *What:* `prompt_manager` computes
`sha256(rendered template)` per version and channel overlay; the hash rides in `request_id`/`extra`
into Langfuse spans and a new nullable `prompt_hash` ledger column; labels (`production`, `candidate`)
replace the bare env var. `zantara_core.py` stays read-only. *Metric:* every gateway row carries a
`prompt_hash`; a prompt change is attributable to a quality delta in the eval of R9.

**R9 (P1, L) — Eval gate for the answering path.** *What:* promote `wa_blind_bench.py` + golden sets to a
Braintrust-shaped `Eval(data, task, scorers)` run nightly on Pro with a local judge (deepseek-r1:32b)
and weekly cross-family judges, results as an artifact; PRs touching `prompts/`, `llm/`, `routes.yaml`
run the deterministic subset in CI. First step, per the 2026-08-09 finding: measure the judge against
the adjudicated 30-case set before it gates anything. *Metric:* judge false-accept ≤ 3/30 on the
adjudicated set; a deliberately degraded prompt (remove the pricing rule) fails the gate.

**R10 (P1, S) — Observability hygiene.** *What:* emit OTEL GenAI attributes on Gemini and Ollama
spans too (attribute names to be re-verified against the moved semconv repo — **unverified**);
either give `llm:metrics` a consumer (Grafana panel on p50/p95 per route) or delete the emitter
(superscar #2). *Metric:* a Grafana panel shows p95 latency per `endpoint×model`; no write-only sink
remains.

**R11 (P2, S) — Doctrine sync.** Fix the three "CLI broken on Fly" docstrings, the `llm_gateway.py:272-274`
tier comment, `cost_baseline.py`'s 4.7 table; draft the Law 1 rewrite for Zero (§8).

## 6. Recommendations — beyond SOTA

**B1 (P0, M) — Subscription-seat scheduler.** No commercial gateway routes *OAuth subscription
windows*; they balance API keys by price/TPM (sources 1, 4). Nuzantara has five MAX seats plus a Team
seat that is last-resort by ruling, a 5-hour rolling window each, and a measured way to read headroom
(`scripts/claude_seat_quota.py`, published from Pro). *How:* `backend/llm/seat_scheduler.py` picks the
seat with the largest remaining window from `seat-quota.json` (age ≤ 1 h; fall back to today's fixed
order when stale — Law 6), projects burn from the ledger, and pre-emptively rotates before a window
dies; seats 5-6 join only under the ruling's conditions. *Risk:* stale quota file → wrong pick;
mitigated by the existing cooldown. *Dependencies:* X2's publish job. *Metric:* over 14 days, zero
`quota` cooldown events on a seat while any other seat had ≥ 30% window remaining at that minute
(today: unmeasurable, seats 5-6 never used).

**B2 (P0, L) — Sovereignty-aware routing: data class as a routing dimension.** SYMBIOSIS Law 2 admits
the gap: no ingress control links client text to a demonstrable Art. 56 basis before a cloud call,
and the required conduct is fail-closed. OpenRouter's `data_collection: deny`/`zdr` filters show the
idea per provider (source 4); nobody does it per message with a legal-basis registry. *How:* the
local PII detector (`services/pii`, B4's organ) tags each request `data_class ∈ {public, pii}`;
`routes.yaml` (R7) declares `allowed_data_classes` per provider — Ollama on Pro/Mini and the
codex broker leg on Pro can carry `pii` only when a `consent_basis(client_id)` row exists (a new
table, written by the portal when the clause is signed — Zero's decision in §8); otherwise the gateway
routes local or returns the abstain stub. Cloud providers are chosen on quality/cost as the 2026-08-09
ruling demands — the gate is the basis, not the vendor. *Metric:* a synthetic corpus of 200 messages
with PII markers produces zero ledger rows with `data_class='pii'` and a cloud provider absent a
consent row; the same corpus with consent rows routes normally. This turns the UU PDP obligation into a
product property a competitor cannot claim.

**B3 (P1, L) — Local-first difficulty router on the Macs.** RouteLLM shows 85% cost cuts at 95%
quality when a router predicts the strong model's win rate (source 6); Arch-Router shows a 1.5B model
can route by declared policy (source 7). Nuzantara's local tier is $0 and PII-safe, and the pull-broker
already executes on Pro where Ollama lives (broker spec C1). *How:* reuse `surface_router` layer 1
(keyword/confidence) plus a calibrated threshold learned from the golden set to send "easy, public"
turns to `qwen3.5:9b` via `providers/ollama.py`, escalating to the subscription seat on low confidence;
abstain gates keep running on Fly (broker constraint C6). *Risk:* quality; Ollama latency in the
30-120 s class for heavy models (rule: never on the critical path) — restrict to the 9B class.
*Metric:* ≥ 40% of broker turns answered locally with ≤ 2-point drop on the R9 eval and p95 < 4 s.

**B4 (P1, M) — Cost per outcome, not per call.** Gateways meter calls; the 2026-08-12 research asked
for per-outcome metering as the KPI. *How:* `request_id` already exists in the ledger; propagate
`conversation_id` and join to the funnel/order events (B5/F2 tables) in a nightly view
`llm_cost_per_outcome`. *Metric:* a dashboard tile "USD and seat-minutes per qualified lead", computed
for ≥ 90% of leads in the window.

**B5 (P2, S) — Degradation as an organism signal.** Map `LLMBudgetExceeded`, durable quota, auth-dead
and refusal storms onto the EventBus (`PG_CHANNEL_MAP`, Law 3) so self-healing can switch the bot to an
"assisted mode" stub and the healer can tick, instead of each caller improvising (Law 4). *Metric:*
an injected budget breach produces one `llm_degraded` event and one Telegram alert within 60 s, and the
channel recovers automatically on the next successful call.

## 7. §Meta-pattern

**The gateway is copied into its callers instead of being a component, because doctrine frames an
LLM call as a subprocess to wrap rather than a request to submit.** Law 1's "CLI-only" made every
script and service grow its own seat loop, quota regex, retry set, token estimate and price table:
seven cascades, nineteen copies of one phrase, two estimators, four lanes that bypass the ledger, five
prompt versions by file copy. Every scar in this area is a copy diverging (W92 a stricter regex fixed
in one file, W104 exit-code judging, the 34-hour mute bot). The same belief explains why USD is the
ledger's unit when the arsenal is mostly flat subscriptions: a subprocess has an exit code, not a
budget. Cure the belief and R1-R7 and B1-B2 become one object — a small sovereign broker — instead of
seven patches.

## 8. §Solo-operatore

- **Law 1 rewrite (Legge 5).** Text says CLI-only and bans Google HTTP; production runs on the Google
  HTTP SDK by design. Zero decides the wording ("subscription-first; metered HTTP only where ruled,
  today Gemini; paid Anthropic banned") — sessions cannot ratify doctrine.
- **Consent basis registry (business + legal).** B2 is fail-closed until the contract clause, the
  per-client proof record and the revocation path exist (SYMBIOSIS Law 2, point 3). Zero owns the
  clause and the DPA status record.
- **Langfuse posture (spend + PII).** If `LANGFUSE_*` keys are set in prod, traces of client chat go
  to the US cloud host (`core/observability.py:107`) — **(unverified whether keys are set)**. Zero
  chooses: self-host on Mini, input masking, or keep it a local-only POC.
- **Gemini prepay policy.** Whether the Gemini fallback leg keeps a prepaid balance and at what
  cap (the R2 default caps need a ruling); top-ups are `operator[business]`.
- **Seat rulings.** B1 respects "Team seat last resort"; any change to seat order or to putting
  seats 5-6 in the backend hot path is Zero's.
- **GUI-only:** `codex login` per broker seat (done 2026-08-26 per memory), any Google Cloud console
  change for Vertex if the SA path is ever re-enabled.

## 9. Sources

Accessed 2026-08-28.

1. https://docs.litellm.ai/docs/routing
2. https://docs.litellm.ai/docs/proxy/users
3. https://portkey.ai/docs/product/ai-gateway/configs (config schema only; retry/cache details not on page)
4. https://openrouter.ai/docs/features/provider-routing
5. https://github.com/maximhq/bifrost
6. https://github.com/lm-sys/RouteLLM
7. https://arxiv.org/abs/2506.16655 — Arch-Router (abstract only)
8. https://docs.helicone.ai/features/advanced-usage/caching
9. https://langfuse.com/docs/prompt-management/get-started
10. https://www.braintrust.dev/docs/guides/evals
11. https://platform.claude.com/docs/en/build-with-claude/prompt-caching
12. https://platform.claude.com/docs/en/build-with-claude/effort
13. https://platform.claude.com/docs/en/build-with-claude/structured-outputs
14. https://platform.claude.com/docs/en/api/handling-stop-reasons
15. https://developers.openai.com/api/docs/guides/prompt-caching
16. https://github.com/zilliztech/GPTCache
17. https://github.com/NVIDIA/NeMo-Guardrails
18. https://ai.google.dev/gemini-api/docs/caching
19. https://code.claude.com/docs/en/cli-reference
20. https://www.anthropic.com/research/constitutional-classifiers
21. https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html
22. https://opentelemetry.io/docs/specs/semconv/gen-ai/ — redirect notice to github.com/open-telemetry/semantic-conventions-genai; attributes unverified
23. https://dspy.ai/learn/optimization/optimizers/ — redirect only; unverified

Internal (read this session): `SYMBIOSIS.md` §LE LEGGI; `.claude/rules/cicatrix-scars.md` (W92, W104);
`research/operations/2026-08-09-llm-model-cost-quality-comparison.md`;
`…/2026-08-12-frontier-llm-token-cost-practices.md`; `…/2026-08-20-token-cost-lanes-disposition.md`;
`…/2026-08-15-adr-wa-runtime-openai-provider.md`; `…/2026-08-19-bot-chatgpt-provider-broker-spec.md`;
`docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md`; `MODEL_ROSTER.md`;
`FLEET_TOPOLOGY.json`; memory `MEMORY_BOT_AND_LLM_LANES.md`.

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** Two findings. The spend section is a repeatable denial-of-wallet recipe (the prepay balance reaching zero **four times** is recalled from memory, not sourced from the repo), and possible egress of client chat to a US cloud (Langfuse) is asserted without a measurement. An internal inconsistency was also noted: this file gives a seat count in one place that does not agree with the count it gives elsewhere.
