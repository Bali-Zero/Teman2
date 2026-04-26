# OSS Injection Sprint — 2026-04-26 → 2026-04-27

Three open-source tools landed in production over a single sprint. This page is the
single source of truth: what each one buys you, how to use it, what it does **not**
cover, and how to disable it if it misbehaves.

Each tool was chosen via independent brainstorms with Gemini 3.1 Pro and DeepSeek R1
(both converged on **ADOPT-PARTIAL**); see [`brainstorms/2026-04-26-oss-injections/`](./brainstorms/2026-04-26-oss-injections/)
for the full reasoning artifacts.

| Sprint | Tool                                                              | PR                                                                   | Live?                                                |
| ------ | ----------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------- |
| 1      | **Squawk** — Postgres migration linter (CI gate)                  | [#306](https://github.com/Balizero1987/Teman2/pull/306) (`935e61a7`) | ✅ active in GitHub Actions                          |
| 2      | **Instructor pattern** — schema-validated LLM outputs             | [#311](https://github.com/Balizero1987/Teman2/pull/311) (`a41cdc35`) | ✅ deployed on `nuzantara-rag`                       |
| 3      | **OpenLLMetry** — auto-instrumentation for Gemini + OpenAI-compat | [#312](https://github.com/Balizero1987/Teman2/pull/312) (`d6db73c1`) | ✅ deployed, **dormant** until Langfuse keys are set |

---

## 1. Squawk migration lint (PR #306)

### What it does

Catches dangerous Postgres operations at **PR-check time** rather than at the
pre-deploy gate (~2-hour shift left). Triggers on every PR touching
`apps/backend-rag/backend/db/migrations_v2/*.sql`.

### What it catches

- `ALTER TABLE ... ADD NOT NULL` without `DEFAULT` (locks table during backfill)
- `CREATE INDEX` / `DROP INDEX` without `CONCURRENTLY` (acquires `ACCESS EXCLUSIVE`)
- `DROP COLUMN` (silent data loss)
- Statements without `IF EXISTS`/`IF NOT EXISTS` (non-rerunnable on partial failure)
- ~30 other Postgres-specific anti-patterns (see [Squawk rules](https://squawkhq.com/docs/rules/))

### What it does NOT replace

The runtime rollback-marker validation in
[`apps/backend-rag/backend/db/migration_manager.py`](../apps/backend-rag/backend/db/migration_manager.py)
stays as-is. That gate (which caught PR #302) catches a different class of issue
(missing `-- === ROLLBACK ===` block) and runs at deploy time, not PR time.
The two checks are **complementary**, not redundant.

### How to bypass on a legitimate destructive change

Add a Squawk-ignore comment on the offending statement:

```sql
-- squawk-ignore: ban-drop-column — column is unused, audited 2026-04-27
ALTER TABLE clients DROP COLUMN obsolete_field;
```

The full rule list available for `squawk-ignore` is at
<https://squawkhq.com/docs/rules/>.

### Where it lives

- Workflow: [`.github/workflows/migration-lint.yml`](../.github/workflows/migration-lint.yml)
- Action: [`sbdchd/squawk-action@v2`](https://github.com/sbdchd/squawk-action)
- Pinned PG version for analysis: 15.0 (matches `tests.yml` and `fly-deploy.yml`)

### Verified live (2026-04-27)

Canary PR #313 introduced a deliberately bad migration (NOT NULL no DEFAULT +
non-CONCURRENT index). Squawk flagged 8 violations within 90s, blocked merge.
PR closed without merging.

---

## 2. Instructor pattern — schema-validated LLM outputs (PR #311)

### What it does

Adds `GenAIClient.generate_structured(prompt, schema)` for **Pydantic-validated
LLM outputs** instead of prompt-engineered JSON + `try/except json.JSONDecodeError`.
Uses google-genai's native `response_schema` so we get the guarantee without
adding the `instructor` dependency.

### When to use

Use `generate_structured` instead of `generate_content` whenever the LLM is
expected to return structured data (a list, a dict, an enum, a yes/no judgement).
The signature mirrors `generate_content` plus a `response_schema` argument:

```python
from pydantic import BaseModel
from backend.llm.genai_client import get_genai_client, LLMStructuredOutputError

class GraderVerdict(BaseModel):
    relevant: bool
    reasoning: str
    confidence: float  # 0.0 - 1.0

client = get_genai_client()
try:
    verdict = await client.generate_structured(
        contents="Is this passage relevant to the query 'KITAS'?",
        response_schema=GraderVerdict,
        endpoint="rag.grader.kitas",  # cost attribution label
    )
    if verdict.relevant and verdict.confidence > 0.7:
        ...
except LLMStructuredOutputError:
    # Model failed schema after 1 retry. Fall back to your default heuristic.
    ...
```

### Pilot in production

[`backend/services/rag/query_expansion._llm_translate`](../apps/backend-rag/backend/services/rag/query_expansion.py)
uses `TranslationResult` to translate user queries between Italian / English /
Indonesian before retrieval. This path runs ~3000+ times per day in production.

### What is OUT of scope (deferred)

- **Knowledge-graph entity extraction** (`services/rag/kg_*`) — both Gemini and
  DeepSeek brainstorms flagged it: nested schemas + qwen3.5 = high failure rate.
  Stays prompt-engineered for now.
- **Claude OAuth CLI** (`backend/llm/claude_oauth_client.py`) — shells out to a
  subprocess; cannot be patched by `instructor` or by google-genai's native
  schema. Stays in legacy `try/except` pattern.
- **OpenAI-compatible backends** (DeepSeek, Ollama) — follow-up PR can add
  `instructor.from_openai()` wrapping for parity. Not blocking for this sprint.

### Tip from the brainstorm

**Put `reasoning: str` as the FIRST field** of any non-trivial schema. It forces
the model to "think out loud" before committing to the structured answer, which
drastically reduces validation failures (Gemini 3.1 Pro insight, confirmed in
practice).

### Observability hooks

`generate_structured` mirrors `generate_content`'s observability pipeline
(Prometheus, Postgres `llm_cost_events`, JSONL ledger). Cost-tracked rows have
the `endpoint` label you pass at call time. Use a `dotted.path.tag` style for
easy filtering in the dashboard later.

### Verified live (2026-04-27)

Two real RAG queries (English + Italian) returned 200 OK with `expansion_count=3`
and `evidence_score=0.85`, exercising the new path end-to-end.

---

## 3. OpenLLMetry — auto-instrumentation expansion (PR #312)

### What it does

Auto-traces every LLM call we make via OpenInference instrumentors over the
already-installed Langfuse SDK. **Behaviour-zero in production** until you set
the Langfuse keys.

| Backend                       | Instrumentor                                                | Attribute                                          |
| ----------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| Anthropic SDK                 | `openinference-instrumentation-anthropic` (already shipped) | `gen_ai.system=anthropic` (legacy, unused in prod) |
| Gemini (google-genai)         | `openinference-instrumentation-google-genai`                | `gen_ai.system=gemini`                             |
| OpenAI / DeepSeek / Ollama    | `openinference-instrumentation-openai`                      | `gen_ai.system=openai`                             |
| Claude OAuth CLI (subprocess) | manual OTEL span                                            | `gen_ai.system=claude-cli`                         |

### How to activate

On Fly.io, set the secrets and the rolling restart picks them up:

```bash
fly secrets set -a nuzantara-rag \
  LANGFUSE_PUBLIC_KEY="<your-public-key>" \
  LANGFUSE_SECRET_KEY="<your-secret-key>" \
  LANGFUSE_HOST="https://us.cloud.langfuse.com"
```

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are both present, the
[`init_observability()`](../apps/backend-rag/backend/core/observability.py) call
in `app/setup/app_factory.py:_background_init()` registers the global OTEL
provider and every LLM call starts emitting spans automatically.

### Privacy posture (UU PDP / GDPR)

**By default, prompts and completions are NOT captured.** Only metadata: model,
token counts, latency, status, schema name. Bali Zero queries routinely contain
NPWP, NIB, passport numbers, names — keeping content out of traces is the safe
default.

To opt in (e.g. for debugging a specific bug, in a non-prod environment):

```bash
fly secrets set -a nuzantara-rag-staging LANGFUSE_TRACE_LLM_MESSAGES=true
```

The flag is read on init and applied uniformly across all four instrumentors
via the shared [`_build_trace_config()`](../apps/backend-rag/backend/core/observability.py)
helper.

### Per-provider kill-switch

If a single instrumentor misbehaves (silent crash on import, latency spike,
attribute pollution), disable just that one without redeploying:

```bash
fly secrets set -a nuzantara-rag LANGFUSE_INSTRUMENT_GOOGLE_GENAI=false
# or LANGFUSE_INSTRUMENT_OPENAI=false
# or LANGFUSE_INSTRUMENT_ANTHROPIC=false
```

The flag is enforced at [`_instrument_enabled()`](../apps/backend-rag/backend/core/observability.py)
on top of the kwarg gate. The `instrumentor.instrument()` call simply never
runs for that provider.

### Full kill-switch

To disable Langfuse entirely (matches today's behaviour before any keys were set):

```bash
fly secrets set -a nuzantara-rag LANGFUSE_ENABLED=false
# OR
fly secrets unset -a nuzantara-rag LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY
```

`is_enabled()` returns `False` if either condition holds, and the entire
`init_observability()` body short-circuits to a logged no-op.

### What is OUT of scope (deferred)

- **LangSmith removal**: `langsmith>=0.4.0` and the `@traceable` decorators
  (in `kg_graph_nodes.py`, `agentic/orchestrator_core.py`) keep running in
  parallel. Phase 3 cutover happens after a 2-week soak with both running side-by-side.
- **Self-hosted Langfuse**: the POC config currently points at
  `us.cloud.langfuse.com`. Switching to a Fly-hosted Langfuse instance is
  a one-line `fly secrets set LANGFUSE_HOST=...` change at deploy time, no
  code change needed. Phase 4.
- **Custom Presidio `SpanProcessor`**: the `hide_*_messages` flags already
  give baseline UU PDP coverage. A future PR can add granular field-level
  scrubbing if/when `LANGFUSE_TRACE_LLM_MESSAGES=true`.

### What this enables, in plain words

After activation, when a Bali Zero client says "Zantara was slow" or "she
gave me a wrong answer," you can open the Langfuse dashboard, search by
`user_email` or timestamp, and see the full timeline:

1. Which LLM was called (Gemini? DeepSeek? Ollama?)
2. How long each step took (retrieval, KG, grading, answer)
3. Token cost per step
4. Whether validation retries happened on `generate_structured`
5. The retrieval chunks the answer was based on

Without prompt/completion text leaking — only the operational picture.

### Verified live (2026-04-27)

PR #312 deploy completed: success on `nuzantara-rag`. `/health` returns 200,
`/health/detailed` returns valid JSON with services in expected lazy-init
state. No crash on the new imports. Codice OTEL dormant as designed.

---

## How they compose

The three sprints reinforce each other:

```
PR opens with new SQL migration
    └─ Squawk lints in 90s (PR #306) — blocks if dangerous
       └─ on green, merge & deploy

LLM call from RAG retrieval
    └─ generate_structured(schema) (PR #311) — Pydantic-validated output
       └─ auto-traced via OpenInference (PR #312) — visible in Langfuse
          └─ when keys are set; else dormant
```

Sprint 2 added `generate_structured`. Sprint 3 ensured those calls become
**visible in dashboards** with model/tokens/latency. The net effect: when
a `_llm_translate` retry fires due to validation error, you see it in
Langfuse as `attempts=2` on the same trace — operational signal you didn't
have before.

## Cost summary

| Item                                                   | Cost                                              |
| ------------------------------------------------------ | ------------------------------------------------- |
| Squawk (OSS, MIT)                                      | $0                                                |
| Instructor pattern (uses google-genai native schema)   | $0 — no new package                               |
| OpenInference instrumentors (`google-genai`, `openai`) | $0 (~60 KB Docker image)                          |
| Langfuse cloud (when activated)                        | depends on tier; free tier covers ~10k traces/day |
| Self-hosted Langfuse on Fly.io (Phase 4)               | ~$15/month if you go that route                   |

## Pivots taken during the sprint

- **Atlas → Squawk**: original sprint 1 plan was Atlas, but `ariga/atlas v0.38`
  (Oct 2025) moved `migrate lint` behind the Atlas Pro paywall. Pivoted to
  Squawk (also OSS, also Postgres-specific, MIT, ~600K downloads/month).
  Documented in [`.claude/rules/cicatrix-scars.md`](../.claude/rules/cicatrix-scars.md).
- **`instructor` package not added**: explored, but `GenAIClient` is a custom
  wrapper that emits cost metrics; `instructor.from_genai()` patches the raw
  google-genai client and would skip our observability. We use google-genai's
  **native** `response_schema` instead. Same Pydantic guarantee, zero new
  dependency.

## Cross-references

- Brainstorm artifacts (Gemini 3.1 Pro + DeepSeek R1, 2 of 3 tools each):
  [`docs/brainstorms/2026-04-26-oss-injections/`](./brainstorms/2026-04-26-oss-injections/)
- Squawk PR: [#306](https://github.com/Balizero1987/Teman2/pull/306) — `935e61a7`
- Instructor pilot PR: [#311](https://github.com/Balizero1987/Teman2/pull/311) — `a41cdc35`
- OpenLLMetry PR: [#312](https://github.com/Balizero1987/Teman2/pull/312) — `d6db73c1`
- Squawk canary verification: [#313](https://github.com/Balizero1987/Teman2/pull/313)
  (closed, do-not-merge — was the live test)
- Atlas-paywall scar: [`.claude/rules/cicatrix-scars.md`](../.claude/rules/cicatrix-scars.md)
