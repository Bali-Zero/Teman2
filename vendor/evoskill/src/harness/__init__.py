"""Harness layer — SDK executors, options builders, and the Agent abstraction.

This package handles HOW to talk to different agent SDKs (Claude, OpenCode,
future Goose/OpenHands). It knows nothing about specific agent roles
(that's agent_profiles/).

Key exports:
    Agent[T]        — generic wrapper that delegates to the active SDK
    AgentTrace[T]   — SDK-agnostic result from an agent run
    set_sdk/get_sdk — global SDK toggle
    build_claudecode_options/build_opencode_options — option builders
"""

from .agent import Agent, AgentTrace, OptionsProvider
from .sdk_config import set_sdk, get_sdk, is_claude_sdk, is_opencode_sdk, is_codex_sdk, is_goose_sdk, is_openhands_sdk, is_deepseek_sdk
from .utils import build_options, resolve_project_root, resolve_data_dirs
# Bali Zero Nuzantara vendor strip: claude/codex options imports removed.
# Top-level import would fail with ImportError after physical deletion of
# src/harness/claude/ and src/harness/codex/ directories. The two
# is_claude_sdk/is_codex_sdk feature flags stay accessible via sdk_config
# for backwards-compatible detection in untouched call sites, but the
# executors raise ImportError on actual invocation (see __init__.py stub
# inside src/harness/claude/ and src/harness/codex/).
# See vendor/evoskill/UPSTREAM.md for the full diff list vs upstream
# tag v1.1.0 (SHA 5ae91616...).
from .opencode.options import build_opencode_options
from .goose.options import build_goose_options
from .openhands.options import build_openhands_options
# Bali Zero Nuzantara vendor addition (panel 2026-05-18 CRITICAL):
# DeepSeek harness was missing — evolver.toml provider=deepseek would
# trigger Unknown SDK ValueError. See vendor/evoskill/UPSTREAM.md §5
# and harness/deepseek/ (Phase 0 stub).
from .deepseek.options import build_deepseek_options

__all__ = [
    "Agent",
    "AgentTrace",
    "OptionsProvider",
    "set_sdk",
    "get_sdk",
    "is_claude_sdk",
    "is_opencode_sdk",
    "is_codex_sdk",
    "is_goose_sdk",
    "is_openhands_sdk",
    "is_deepseek_sdk",
    "build_options",
    "build_opencode_options",
    "build_goose_options",
    "build_openhands_options",
    "build_deepseek_options",
    "resolve_project_root",
    "resolve_data_dirs",
]
