# Anthropic API — Best Practices for Nuzantara

> Extracted from CLAUDE.md (pre-T2.7 §13) on 2026-03-31 to reduce context window load.
> Post-T2.7 refactor 2026-05-23: only tombstone "Anthropic SDK BANNED" remains in root CLAUDE.md §5. Anthropic SDK direct use is BANNED — use `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` via `apps/backend-rag/backend/llm/claude_oauth_client.py`.
> **Refreshed 2026-07-25 to the Claude 5 roster** (Opus 5 + Sonnet 5). The request shapes below describe the API our CLI path speaks — they are NOT a licence to instantiate the paid SDK.

## Current roster (use these IDs verbatim — never invent a date suffix)

| Model               | ID                          | Context / max output | $ per MTok (in/out)                          |
| ------------------- | --------------------------- | -------------------- | -------------------------------------------- |
| Claude Fable 5      | `claude-fable-5`            | 1M / 128K            | $10 / $50                                    |
| **Claude Opus 5**   | `claude-opus-5`             | 1M / 128K            | $5 / $25                                     |
| Claude Opus 4.8     | `claude-opus-4-8`           | 1M / 128K            | $5 / $25                                     |
| **Claude Sonnet 5** | `claude-sonnet-5`           | 1M / 128K            | $3 / $15 (intro $2 / $10 through 2026-08-31) |
| Claude Sonnet 4.6   | `claude-sonnet-4-6`         | 1M / 128K            | $3 / $15                                     |
| Claude Haiku 4.5    | `claude-haiku-4-5-20251001` | 200K / 64K           | $1 / $5                                      |

Opus 4.8 and Sonnet 4.6 are **still active** — a pin to either is valid, not deprecated. Fable 5 is the most capable tier but is priced above Opus: it is **not** the default upgrade (see root `CLAUDE.md` §5 "non voglio pagare" contingency).

## Thinking & effort (5-family)

`budget_tokens` is **removed** on Fable 5 / Opus 5 / Opus 4.8 / Sonnet 5 — sending it returns **400**. So are `temperature`, `top_p`, `top_k`. Steer with prompting and `output_config.effort`.

```python
response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=16000,
    thinking={"type": "adaptive"},              # display defaults to "omitted"
    output_config={"effort": "high"},           # low | medium | high | xhigh | max
    messages=[...],
)
```

- **`xhigh` is the sweet spot for coding/agentic work**; `high` is the API default. `max` only when correctness outranks cost — it can overthink.
- **Opus 5 thinks by default**: omitting `thinking` now _thinks_ (on 4.8/4.7 it meant no thinking). `max_tokens` caps thinking **plus** answer, so a route sized tightly around its answer can truncate mid-response — re-check `max_tokens` on every path that never set `thinking`.
- **`thinking:{type:"disabled"}` on Opus 5 is accepted only at effort ≤ `high`** — pairing it with `xhigh`/`max` returns 400. Prefer lowering `effort` over disabling thinking: with thinking off, Opus 5 occasionally writes a tool call as **plain visible text** (the call silently never runs, no error raised) and can leak `<thinking>` tags into output.
- **`display` defaults to `"omitted"`** on Fable 5 / Opus 5 / Opus 4.8 / Sonnet 5 — thinking blocks stream with empty text, which reads as a long pause. Set `thinking={"type":"adaptive","display":"summarized"}` if reasoning is surfaced to a user or a log.
- **Sonnet 5 ships a new tokenizer: ~30% more tokens for the same text.** Per-token price is unchanged, so the cost of an equivalent request moves. Re-run `count_tokens` against `claude-sonnet-5` — never apply a blanket multiplier to counts measured on 4.6.

## Refusals — check `stop_reason` before reading `content`

Fable 5 and Opus 5 carry elevated cybersecurity safeguards. A declined request returns **HTTP 200** with `stop_reason: "refusal"` and a `stop_details` category — `content` is empty (pre-output, unbilled) or partial (mid-stream, billed). Code that reads `response.content[0]` unconditionally breaks:

```python
if response.stop_reason == "refusal":
    handle_refusal()          # stop_details.category: "cyber" | "bio" | ... | None
else:
    text = response.content[0].text
```

## Prompt Caching (-90% on reads)

For KBLI knowledge base, large system prompts, or unchanging tool definitions:

```python
system=[
    {
        "type": "text",
        "text": KBLI_SYSTEM_PROMPT_OR_KNOWLEDGE,
        "cache_control": {"type": "ephemeral"},        # or {"type": "ephemeral", "ttl": "1h"}
    }
]

print(response.usage.cache_read_input_tokens)
print(response.usage.cache_creation_input_tokens)
```

Caching is a **prefix match** — one changed byte anywhere in the prefix invalidates everything after it. Keep the frozen system prompt first, put timestamps/session IDs _after_ the last breakpoint, serialize tools deterministically. Cache reads ≈ 0.1× base input; writes 1.25× (5-min TTL) or 2× (1-hour TTL).

**Minimum cacheable prefix is per-model and NOT monotonic** — a 700-token prompt caches on Opus 5 and silently won't on Sonnet 4.6:

| Model                          |        Minimum |
| ------------------------------ | -------------: |
| Opus 5, Fable 5                | **512 tokens** |
| Opus 4.8, Sonnet 5, Sonnet 4.6 |    1024 tokens |
| Haiku 4.5                      |    4096 tokens |

Below the minimum there is no error — just `cache_creation_input_tokens: 0`.

## Batch API (50% discount)

For test suites, bulk KBLI analysis, evaluations:

```python
batch = client.messages.batches.create(requests=[...])
# Stacking: Batch 50% off + cache reads 90% off = minimal cost
```

Results arrive in **any order** — key by `custom_id`, never by position.

## Tool Use Patterns

```python
# Strict schema for production
tools = [{"name": "...", "strict": True, "input_schema": {...}}]

# Fine-grained streaming for large tool output (no beta header — set on the tool)
tools = [{"name": "kbli_search", "eager_input_streaming": True, ...}]

# Tool result caching for large documents
{"type": "tool_result", "content": [{"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}]}
```

Parallel tool use is on by default: return **all** `tool_result` blocks in a **single** user message — splitting them trains the model to stop calling tools in parallel. Tool descriptions should be prescriptive about _when_ to call ("Call this when the user asks about current prices"), not just what the tool does — recent Opus models reach for tools conservatively, and an explicit trigger condition measurably lifts the call rate.

## Models for Nuzantara

| Use                                    | Model                       | Why                                                                                   |
| -------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------- |
| RAG, reasoning, standard workflow      | `claude-sonnet-5`           | Near-Opus quality on agentic/coding at Sonnet cost; re-baseline tokens (+~30% vs 4.6) |
| Routing / classification               | `claude-haiku-4-5-20251001` | $1/$5 MTok, fast                                                                      |
| Critical tasks, architecture, red-team | `claude-opus-5`             | 1M ctx, effort `xhigh`/`max`, 128K output                                             |
| KBLI explanations                      | `claude-haiku-4-5-20251001` | Configured in `kbli_notebook.py`                                                      |

> ⚠️ `scripts/cost_baseline.py` still carries the 4.x price table and scenario mapping. Re-baselining it against the 5-family is deliberately **not** bundled with this doc refresh: the numbers move both from prices and from Sonnet 5's tokenizer, so it needs a measured pass, not a find-and-replace.
