# Codex Best Config Audit - 2026-05-21

## Scope

Read-only audit plus small configuration/doc hardening for Codex operating on the
Nuzantara monorepo. The goal is a stronger default operator setup, not a larger
prompt.

## Live State

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer: Mini reachable through `ssh mini`.
- Git parity: out of sync at audit time.
  - Pro: `9f68f3a89 docs(research): WhatsApp CRM dossier final -- 34/34 clients (qwen3.5 + Claude Haiku fallback)`
  - Mini: `f02ccfdfa docs(research): WR3 Veo Pro Tier 1 rejection panel synthesis + live E2E solid`
- Local main checkout was dirty, so repo edits were made in `.worktrees/codex-best-config-20260521`.
- MCP readiness: sandboxed check produced a false negative for Nuzantara MCP; escalated/live readiness showed `nuzantara-mcp` and `nuzantara-mcp-advanced` healthy.

## Sources Used

- OpenAI Codex CLI: https://developers.openai.com/codex/cli
- OpenAI Codex config basics: https://developers.openai.com/codex/config-basic
- OpenAI Codex config reference: https://developers.openai.com/codex/config-reference
- OpenAI Codex permissions: https://developers.openai.com/codex/permissions
- OpenAI latest model guide: https://platform.openai.com/docs/guides/latest-model
- NotebookLM Deep Research notebook: `6ebae8fd-43d4-4292-a6cf-cd2a04b8dcbd`
- Existing local research under `research/operations/2026-05-21-*` and `research/operations/specs/`.
- Claude MOS brief through `~/.codex/bin/claude-mos-brief`.

## Findings

### P0 - Instruction Drift

Root project docs still described the old Pro/Air topology. Live topology and
`~/.ssh/config` point to Pro/Mini, with `ssh mini` as the reliable peer path.
These stale instructions can cause wrong session prefixes, wrong sync checks,
and stale assumptions about virtualenv layout.

### P0 - Codex Profile Drift

`~/.codex/AGENTS.md` claimed `protected` and `operator` were both `xhigh`.
Actual `~/.codex/config.toml` has:

- Top-level default: `gpt-5.5`, `xhigh`, `workspace-write`, `on-request`.
- `protected`: `gpt-5.5`, `medium`, `workspace-write`, `on-request`.
- `deep` / `xhigh`: `gpt-5.5`, `xhigh`, `workspace-write`, `on-request`.
- `operator`: `gpt-5.5`, `high`, `danger-full-access`, `never`.

The correct operator rule is: use protected for normal implementation, deep/xhigh
for long audits and research, operator only when the user explicitly grants
full-access local operations.

### P0 - Secret Inheritance

Codex config only excluded `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. The official
Codex config reference says `shell_environment_policy.exclude` accepts glob
patterns. The safe default is to also exclude generic API key, token, secret,
database, Redis, Qdrant, Fly, Gemini, Google, and DeepSeek variables from tool
subprocess inheritance.

### P1 - MCP False Negatives

Network-restricted sandbox checks can report MCP/backend reachability failures
that disappear under live checks. For Nuzantara, treat `mcp_readiness_check.py`
as source of truth, but rerun it in the active operator context before turning a
readiness failure into an incident.

### P1 - Prompt Size

NotebookLM and existing local research converged on the same lesson: the best
agent config is not a bigger root prompt. Keep root AGENTS/CLAUDE files short,
route to scoped docs, and use MCP/tool search/progressive disclosure for detail.

## Changes Applied

- Updated root `AGENTS.md`, `CLAUDE.md`, `INDEX.md`, and `docs/AI_ONBOARDING.md`
  in the isolated worktree from Pro/Air to Pro/Mini session guidance.
- Updated `~/.codex/AGENTS.md` to match actual Codex profile values.
- Backed up global Codex config to:
  `/Users/nuzantara/.codex/config.toml.pre-best-config-20260521`
- Hardened `~/.codex/config.toml` `shell_environment_policy.exclude` with
  explicit and globbed secret patterns.

## LLM Review

- Agy sandbox review returned `BLOCKER` on hostname detection. The live Mini
  hostname is lowercase `mini-pro2`, but the shell snippets now normalize
  `hostname` to lowercase before comparing, so a future case change cannot make
  Mini SSH into itself.
- Agy also flagged `shell_environment_policy.exclude` glob entries as
  unsupported. This was rejected after checking the official Codex config
  reference, which documents `exclude` as glob patterns.
- Agy flagged the global Codex AGENTS wrapper sentence as stale for
  GitHub/Postgres/Qdrant. Accepted: the sentence now tells agents to verify the
  active config because those integrations may be plugins, deferred tools, or
  absent.
- Gemini CLI did not produce usable review output due model capacity/rate-limit
  and non-interactive policy approval failures. Claude print review was stopped
  by the explicit USD budget guard before producing findings.
- Claude print review was rerun with a larger guard and returned `MEDIUM`, no
  blockers. Accepted follow-ups: explicit host `case` handling for unknown
  hostnames, `xhigh` cron-pinning note in global Codex AGENTS, and clearer
  separation between legacy `air` filenames and forbidden machine-specific git
  branches. Larger stale root AGENTS sections were deferred to the separate
  consolidation patch.

## Recommended Next Steps

1. Review and merge the repo-doc worktree changes after checking the current
   dirty main checkout.
2. Run an A/B session with `ENABLE_TOOL_SEARCH=auto:5` versus `auto:10` before
   changing the default.
3. Consolidate root AGENTS/CLAUDE into a shorter router document in a separate
   patch. Do not mix that larger rewrite with topology fixes.
4. Retire legacy `air` filenames and docs only after verifying all scripts that
   still reference `shared/escalations_air.jsonl`.
