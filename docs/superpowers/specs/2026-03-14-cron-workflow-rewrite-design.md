# Cron & Workflow Rewrite

**Date:** 2026-03-14
**Status:** IMPLEMENTED
**Sub-project:** 4 of 4 (OpenClaw + Nuzantara Optimization)

---

## Problem

OpenClaw cron jobs had a split quality problem:

- **Business chains** (daily-ops, compliance, practice-lifecycle, client-health) worked well — deterministic MCP chains, real CRM data, Telegram delivery
- **Dev workflows** (nightly-code-quality, autofix-loop, weekly-dep-audit) were broken — used Lobster pipelines with hardcoded Air paths, wrong venv paths, missing Python modules, hallucinated summary outputs
- **Two weekly jobs** (weekly-report, weekly-dep-audit) never executed
- **Delivery gap**: 3 dev jobs used `channel: "last"` with `bestEffort: true`, silently dropping Telegram reports

## Root Cause

Lobster workflows (`.lobster` files) had:

1. Hardcoded Air paths (`/Users/antonellosiano/Projects/nuzantara/`) — fail on Pro
2. Wrong venv path (`venv/` vs `.venv/`)
3. Missing Python modules (`backend.scripts.classify_test_failures` etc.)
4. Hardcoded JSON summaries — reports contained static data, not actual results
5. Undefined `coder` agent for autofix-loop

## Solution: Eliminate Lobster, Use MCP Tools Directly

Replace all Lobster workflow references with direct `mcporter call nuzantara-mcp-advanced.*` tool calls in cron prompts. The MCP-advanced server already provides:

- `run_linting` (with auto_fix)
- `run_type_checking`
- `run_backend_tests`
- `check_deployment_readiness`
- `check_system_health`

These tools have built-in error handling, structured JSON output, and work on any machine where mcporter is configured.

## Changes Made

### All 11 active jobs now use:

- Explicit `mcporter call` syntax in prompts
- `delivery.channel: "telegram"` (not "last")
- Structured output instructions (parse result, format report)

### Specific rewrites:

**health-check** (was disabled, systemEvent)
→ Now uses 3 MCP tools: `check_health`, `check_system_health`, `check_fly_status`

**nightly-code-quality** (was lobster)
→ 5-step pipeline: lint (auto-fix) → type check → backend tests → git commit → Telegram report
→ Uses `run_linting`, `run_type_checking`, `run_backend_tests`

**nightly-autofix-loop** (was lobster with missing modules)
→ 4-phase pipeline: SCAN → FIX → VERIFY → REPORT
→ SCAN uses `run_backend_tests scope=full`
→ FIX: reads failing test + source, fixes atomically (max 5 per run)
→ VERIFY: re-runs tests, reverts if regression
→ No missing Python modules needed — agent does analysis directly

**weekly-dep-audit** (was lobster, never executed)
→ Uses `check_deployment_readiness` + `pip list --outdated` + `npm audit`
→ Fixed delivery: `channel: "telegram"` with `lastRunAtMs: 0`

**weekly-report** (never executed)
→ Uses `chain_weekly_report` + `git log --since='7 days ago'` + `check_system_health`
→ Fixed state: added `lastRunAtMs: 0` for scheduler

**daily-ops, compliance, practice-lifecycle, client-health** (already working)
→ Prompts upgraded from "Use the MCP tool" to explicit `mcporter call nuzantara-mcp.chain_*` syntax
→ Added structured output instructions for Telegram formatting

### Jobs unchanged:

- `kbli-indexing-daily` — uses local Python script (Google Indexing API)
- `articles-indexing-daily` — same

## Before/After

| Metric                      | Before           | After              |
| --------------------------- | ---------------- | ------------------ |
| Jobs using Lobster          | 3                | 0                  |
| Jobs using mcporter         | 0                | 9/11               |
| Jobs with Telegram delivery | 7                | 11                 |
| Jobs never executed         | 2                | 0 (fixed triggers) |
| Jobs with hardcoded paths   | 3                | 0                  |
| Missing dependencies        | 4 Python modules | 0                  |

## Rollback

Lobster files still exist in `~/.openclaw/workspace/workflows/` — revert job prompts to reference them if needed. No code changes required.
