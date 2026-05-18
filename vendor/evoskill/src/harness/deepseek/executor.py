"""DeepSeek V4 Pro executor — Phase 0 stub.

Phase 1 will implement:
    - `execute_query(options, query)` — POST to
      https://api.deepseek.com/v1/chat/completions with the options dict
      (model, messages [{role:system, content:...}, {role:user, content:query}],
      max_tokens, reasoning_effort, response_format), wait for response,
      return as `messages` list compatible with the upstream parse_response
      contract.
    - `parse_response(messages, response_model, get_options)` — extract
      structured output via Pydantic response_model.model_validate_json on
      the assistant content. Return AgentTrace-compatible dict (uuid,
      session_id, model, duration_ms, total_cost_usd from response.usage,
      num_turns=1, usage={input_tokens, output_tokens, total_cost_usd},
      result, is_error, output, parse_error, raw_structured_output, messages).
    - Retry with exponential backoff (30s → 60s → 120s) on transient errors,
      identical pattern to harness/agent.py:_run_with_retry.

Phase 0: both functions raise NotImplementedError. They are reachable
ONLY via `sdk == "deepseek"` dispatch in `harness/agent.py`, so the only
way to hit them is to explicitly call `set_sdk("deepseek")` + `.run()` —
which would be an integration test in Phase 1, never in Phase 0 smoke.

See vendor/evoskill/UPSTREAM.md §5 + spec §"LLM routing" + spec
§"Verification & rollout — Phase 1".
"""

from __future__ import annotations

from typing import Any, Callable


async def execute_query(options: dict[str, Any], query: str) -> list[Any]:
    """Phase 0 stub for the DeepSeek query executor.

    Phase 1 will POST to api.deepseek.com/v1/chat/completions and return
    the response.choices list as the upstream-compatible messages payload.
    """
    raise NotImplementedError(
        "DeepSeek executor.execute_query is a Phase 0 stub. "
        "Phase 1 wires the actual DeepSeek V4 Pro Chat Completions adapter. "
        "See vendor/evoskill/UPSTREAM.md §5 and "
        "docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md "
        "§'Verification & rollout — Phase 1'."
    )


def parse_response(
    messages: list[Any],
    response_model: type,
    get_options: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Phase 0 stub for the DeepSeek response parser.

    Phase 1 will extract the assistant content, validate against
    response_model (Pydantic), and return AgentTrace fields including
    total_cost_usd from response.usage.
    """
    raise NotImplementedError(
        "DeepSeek executor.parse_response is a Phase 0 stub. "
        "Phase 1 wires the actual Pydantic response_model parser. "
        "See vendor/evoskill/UPSTREAM.md §5."
    )
