"""DeepSeek V4 Pro harness — Bali Zero Nuzantara vendor addition.

This module is NOT part of upstream EvoSkill v1.1.0. It was added in
PR #721 (Phase 0 skeleton) after the 3-LLM panel review of 2026-05-18
caught a CRITICAL gap: `evolver.toml` selects `provider=deepseek` but
upstream has no DeepSeek dispatcher (only anthropic/openai/openrouter/
google in `cli/shared.py:call_llm` and only claude/opencode/openhands/
codex/goose in `harness/agent.py:_execute_query`).

Rationale: per v2 Codex panel finding #2 HIGH, autonomous loops cannot
use Claude SDK (CLAUDE.md hard rule) or Codex CLI (ChatGPT Pro
rate-limit risk). DeepSeek V4 Pro API (~$0.10-0.30/run) is the
sanctioned executor for proposer + skill-builder + synthesis.

Phase 0 status: STUB ONLY. `execute_query` and `parse_response` raise
`NotImplementedError` with a clear "wire in Phase 1" message. The
dispatcher in `harness/agent.py` no longer raises `Unknown SDK`
ValueError — it routes to this stub and the stub raises a meaningful
error. Phase 1 wires the actual DeepSeek V4 Pro Chat Completions
adapter (HTTP POST to api.deepseek.com/v1, BUDGET_USD enforced via
usage.total_cost_usd in response, retry-with-exponential-backoff).

See: vendor/evoskill/UPSTREAM.md §5 (DeepSeek harness addition) and
docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md
§"LLM routing".
"""

from .options import build_deepseek_options
from .executor import execute_query, parse_response

__all__ = ["build_deepseek_options", "execute_query", "parse_response"]
