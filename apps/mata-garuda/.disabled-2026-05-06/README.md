# Quarantined: Council "Consiglio v1" — 2026-05-06

Multi-LLM deliberation system (SYMBIOSIS Pillar 4), introduced 2026-04-16 in
PR #68. Quarantined here on 2026-05-06 because it never produced a single
deliberation:

- `council.db` (SQLite store) was never created on Pro nor Mini → zero rows
- No log file in `~/logs/` ever matched council
- The weekly LaunchAgent it dispatched to (`com.matagaruda.council.weekly.plist`,
  Sun 10:00 WITA) was meant for Air, but Air was decommissioned 2026-05-05
  before any cron was installed
- `shared/escalations.json` (one of the two intended Council inputs) stayed at
  `{"pending": [], "resolved": []}` from creation through quarantine

The 5 multi-LLM consultation patterns the system actually uses today
(wave-orchestrator parallel, tri-LLM panel review on PRs, NotebookLM-as-
ground-truth bipolar verifier, ad-hoc cross-LLM brainstorm, MOS auto-save)
all overlap with what the Council promised, and none of them route through
this code.

## What's here

| Path | Origin |
|---|---|
| `council/` | `apps/mata-garuda/mata_garuda/council/` (10 files: agents, consensus, delivery, models, moderator, orchestrator, prompts, store, topics, `__init__`) |
| `tests-council/` | `apps/mata-garuda/tests/council/` (10 test files including `__init__.py`) |
| `council_weekly.py` | `apps/mata-garuda/scripts/council_weekly.py` (cron entrypoint, never wired) |
| `escalations.json` | `shared/escalations.json` (Council input #1, never populated) |

Also removed in the same commit (not moved here, just deleted from
`apps/mata-garuda/mata_garuda/cli.py`):

- 7 subcommand functions (`cmd_council_topic`, `_show`, `_list`, `_approve`,
  `_reject`, `_stats`, `_auto`)
- The `council` subparser registration in `build_parser()`
- 7 `python -m mata_garuda.cli council …` lines in the module docstring

## How to revive

If a future sprint (Sprint 5+ self-evolving organism, or any other) needs
multi-LLM deliberation, restore via:

```bash
cd apps/mata-garuda
git mv .disabled-2026-05-06/council mata_garuda/council
git mv .disabled-2026-05-06/tests-council tests/council
git mv .disabled-2026-05-06/council_weekly.py scripts/council_weekly.py
git mv .disabled-2026-05-06/escalations.json ../../shared/escalations.json
# then re-add the CLI surface in mata_garuda/cli.py — see git history at
# the commit immediately preceding this quarantine for the exact diff
```

The package was self-contained at the moment of quarantine — no external
imports of `mata_garuda.council` existed in production code. Reviving is a
pure mechanical move + CLI re-stitch; no consumer needs updating.

## What was deliberately kept outside this directory

- Memory file `~/.claude/projects/-Users-nuzantara/memory/consiglio-v1.md` —
  not in this repo, separate cleanup if/when desired
- Two references in `~/.claude/CLAUDE.md` (global) — not in this repo,
  separate cleanup
- `apps/cell/cell/sensors/ollama_sensor.py` and `apps/cell/cell/slow/reasoner.py`
  — they hard-code `gemma4:26b` as a model string but don't import the Council
  package; left alone

Pattern follows `apps/backend-rag/backend/channels/.disabled-2026-04-30/`
(Twitter/Slack/gchat) — same "quarantine instead of delete" convention used
elsewhere in this monorepo for code that's structurally complete but not
operationally active.
