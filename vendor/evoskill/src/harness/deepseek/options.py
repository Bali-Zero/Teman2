"""DeepSeek V4 Pro harness options builder — Phase 0 stub.

Phase 1 will implement the actual options dict compatible with the
DeepSeek V4 Pro Chat Completions API: model, reasoning_effort
(low|high|max), max_tokens, temperature, system + user message
construction with optional Pydantic response_format JSON schema.

Phase 0: module loads without ImportError so `harness/__init__.py`
top-level `from .deepseek.options import build_deepseek_options`
succeeds; the function raises NotImplementedError on first call.

See vendor/evoskill/UPSTREAM.md §5 + spec §"LLM routing".
"""

from __future__ import annotations

from typing import Any


def build_deepseek_options(
    system: str,
    schema: dict[str, Any] | None = None,
    tools: list[str] | None = None,
    project_root: str | None = None,
    model: str = "deepseek-v4-pro",
    data_dirs: list[Any] | None = None,
    reasoning_effort: str = "high",
    **kwargs: Any,
) -> dict[str, Any]:
    """Build options for the DeepSeek V4 Pro Chat Completions adapter.

    Phase 0 stub: signature matches the upstream `build_*_options`
    contract for symmetry with opencode/goose/openhands builders.
    Returns a minimal dict so config_to_options round-trips during
    Phase 1 unit tests, but execute_query will raise on actual use.
    """
    return {
        "sdk": "deepseek",
        "model": model,
        "system": system,
        "schema": schema or {},
        "tools": tools or [],
        "reasoning_effort": reasoning_effort,
        "project_root": project_root,
        "data_dirs": data_dirs or [],
        # Phase 1 will add: api_key (from env), base_url, timeout,
        # retry_max, temperature, max_tokens, response_format (json_schema).
        "phase_0_stub": True,
    }
