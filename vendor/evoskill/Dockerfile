# EvoSkill container image — Bali Zero Nuzantara vendored fork.
#
# Phase 0 + Phase 1 + Codex panel R5 BLOCKING #7 fix (2026-05-19):
# Upstream Dockerfile installed `@anthropic-ai/claude-code` npm package
# + `claude-agent-sdk` + `openai-codex-sdk` + `openhands-tools` pip
# packages. ALL of these reintroduce the banned dependency chain that
# Phase 0 physically stripped from pyproject.toml and src/ (panel R3
# BLOCKING #1 traced `anthropic` 0.94.0 entering the venv transitively
# via openhands-tools → browser-use → anthropic).
#
# Allowing `evoskill run --docker` to silently re-install the banned
# packages would violate CLAUDE.md hard rule "no anthropic anywhere in
# the dependency tree" even though the local venv is clean.
#
# Resolution: Docker mode is DISABLED in this fork. Phase 1 runs use
# the local uv venv only (see scripts/agent-library-evolver-run.sh
# step §6: `uv run evoskill run --config ...`).
#
# If a future need emerges for Docker mode, this Dockerfile MUST be
# rewritten to install ONLY: opencode-ai, openhands-sdk (NOT -tools),
# goose, click, rich, pandas, pydantic, pyyaml, questionary, tqdm,
# httpx, hatchling, daytona. NO @anthropic-ai/claude-code npm, NO
# claude-agent-sdk pip, NO openai-codex-sdk pip, NO openhands-tools
# pip (transitive anthropic via browser-use).

FROM python:3.12-slim

# Disable Docker mode entirely — building succeeds (image exists) but
# the CMD raises ImportError when invoked, mirroring the
# src/harness/{claude,codex}/__init__.py stub pattern from Phase 0.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Defensive: if anyone runs `evoskill run --docker`, the image starts
# and immediately exits with a clear ImportError message rather than
# silently downloading the banned SDKs.
CMD ["python3", "-c", "raise ImportError('Docker mode disabled in Bali Zero Nuzantara vendored fork — Phase 0 strip + Codex panel R5 BLOCKING #7 fix. Use local `uv run evoskill run` instead. See vendor/evoskill/UPSTREAM.md.')"]
