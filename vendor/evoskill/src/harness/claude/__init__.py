"""Stub for the upstream src/harness/claude package.

Bali Zero Nuzantara vendor strip (CLAUDE.md hard rule):
the upstream `executor.py` + `options.py` modules were physically
removed because they `import anthropic` / `from claude_agent_sdk
import ...` at module top level, which would silently re-enable the
paid Anthropic per-token API. The stub stays in place so that any
legacy `from src.harness.claude import ...` raises a loud, grep-able
ImportError instead of a silent ModuleNotFoundError that downstream
code could try to except-swallow.

Configure `provider=deepseek` (DeepSeek V4 Pro API) for proposer /
skill-builder, or `provider=google` (Gemini 3.1 Pro free OAuth) for
entailment verification. See `vendor/evoskill/UPSTREAM.md` for the
full diff list vs upstream tag v1.1.0 (SHA 5ae91616...).
"""

raise ImportError(
    "src.harness.claude is disabled per Bali Zero Nuzantara CLAUDE.md "
    "hard rule (no paid Anthropic API). Use provider=deepseek in "
    "agent-library/config/evolver.toml instead."
)
