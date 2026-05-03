# PR-D3 — Cell Critic JSON parse resilience (2026-04-30)

Phase D (self-learning chains) of the Pro automations renaissance.
Sblocca self-learning chain #2 (cell-organism Cortex/Critic loop).

## Bug

`apps/cell/cell/cortex/critic.py:317` does `parsed = json.loads(text)`
on raw Ollama output. When the small Ollama model
(`qwen3:4b` by default) wraps its JSON in a markdown code fence
("`json\n{...}\n`") or prefixes it with prose ("Here is the JSON:
{...}"), `json.loads` raises `JSONDecodeError`, the outer
`except Exception` catches it, and `_expectation_via_llm` returns
`None`.

`None` from `_expectation_via_llm` means the Critic skipped this
expectation — Cortex/Critic loop degraded silently. Audit
2026-04-29 row "com.cell.organism" notes:

> Health=red is concerning: stuck reusing 'check_health' action with
> outcome=partial.

That sticks because Critic can't form fresh expectations to drive new
actions, so the agent retries the same action expecting the same
outcome.

## Fix

Use the same regex extraction pattern that
`apps/cell/cell/cortex/strategy_mutator.py:180-185` already uses —
find the outermost `{...}` block in the response, parse only that:

```python
json_match = re.search(r"\{.*\}", text, re.DOTALL)
if not json_match:
    logger.info("Critic LLM returned no JSON object for '%s': %s", action, text[:200])
    return None
parsed = json.loads(json_match.group())
```

`re.DOTALL` makes `.` match newlines, so multi-line JSON survives.
`{.*}` greedy-matches the outermost block, tolerating prefix prose
and markdown fences.

The log level for "no JSON found" is `info` (not `warning`) — this is
expected operational noise for small models, not a real error.

## Why not `client.generate_structured` (CLAUDE.md §14)?

§14 applies to `genai_client` (Gemini SDK). Cell uses raw httpx against
Ollama's `/api/chat` endpoint — there is no SDK to wrap. The mature
pattern in this codebase for Ollama JSON output is the regex extract
already used by `strategy_mutator.py`. PR-D3 just brings `critic.py`
in line with `strategy_mutator.py`.

A bigger architectural change (introduce an `ollama_structured_output`
helper, retry on parse fail with feedback prompt) would be appropriate
for a separate PR. Out of scope here.

## Verification

- `python3 -m py_compile apps/cell/cell/cortex/critic.py` → OK
- `cd apps/cell && PYTHONPATH=. python3 -m pytest tests/test_critic_agent.py -q` → **25/25 passed**

## Test plan

- [x] py_compile critic.py
- [x] Existing critic test suite passes (25/25)
- [ ] (Post-merge, next 24h) cell-organism `health` field
      in `~/.agent/decisions/state/cell.json` should flip from `red` to
      at least `yellow` once Critic starts forming valid expectations
- [ ] (Post-merge, next 24h) Cortex episodes count
      in `~/.cell/cortex.db` should resume incrementing past the current
      21,316 plateau

## Out of scope

- Wider Ollama JSON-output cleanup (`skill_library.py`,
  `goal_generator.py`, `curiosity_engine.py` may have similar
  issues — none are reported broken by the audit)
- Pydantic v2 validation (CLAUDE.md §14) — not applicable to raw httpx
  Ollama calls

## Related

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md` (PR-D3 row)
- Audit SSOT:
  `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- Predecessors: PR #367 (C5), #368 (C3), #369 (C4), #371 (E1), #372 (D1)
- Same pattern: `apps/cell/cell/cortex/strategy_mutator.py:180-185`
