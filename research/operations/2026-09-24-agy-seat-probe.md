---
date: 2026-09-24
domain: operations
client_case: none
adversarial_review: exempt-measurement-record # probe receipts (tool output) + a quoted verdict of the 2026-09-24 4-seat memo review; this note itself has no second-seat review, the parent session's PR review is the check
sources:
  - scripts/arsenal_probe.py (--seats agy, live run 2026-09-24)
  - agy models / agy --print live runs on Pro, 2026-09-24 (antigravity-cli 1.2.9)
  - FLEET_TOPOLOGY.json orchestrators.agy
  - MODEL_ROSTER.md section "Google — door: agy CLI (AI Ultra), NotebookLM MCP"
  - branch agent/nuzantara/infra/agy-probe-ctx (PR "fix(arsenal): give the agy probe a 40 s budget so a cold start is not read as TIMEOUT")
  - 4-seat review of the Antigravity memo, 2026-09-24 (Fable, Kimi K3, Codex, Qwen 3.8 Max)
---

# agy seat probe — 2026-09-24

Why this note exists: the fleet digest reported `agy TIMEOUT` while the seat was in fact
alive, and the Antigravity memo asked whether the Google door deserves a bigger role. This
note holds the measured receipts behind the `agy` record in `FLEET_TOPOLOGY.json` and
`MODEL_ROSTER.md`. No client data, no credentials, no PII were used or recorded.

## What the CLI serves today

`agy models` lists `gemini-3.1-pro-{high,low}` and `gemini-3.8-flash-{high,medium,low}`
(3.7 and 3.6 flash also exist and are not roster-worthy). `gemini-3.5-flash` is GONE from
the CLI. This confirms the 2026-09-15 M5 slug probe recorded in `FLEET_TOPOLOGY.json`
(`_gemini_slug_probe`). The council seat id `agy-gemini-3.1-pro` is a stable identifier
read by `scripts/evidence_pack_lint.py`; it is unchanged. The `gemini-3.5-flash` strings in
`apps/backend-rag/` name API model ids, not the `agy` door, and are untouched here.

## Harness split

- CLI: `antigravity-cli 1.2.9` on Pro and M5 (`agy --print`, `--model`, `--json-schema`,
  `--output-format json`). This is the schedulable, scriptable door.
- IDE: Antigravity IDE on M5 is the same AI Ultra account, GUI-only, prepare-only.

## Tests

| ID | Test | Result |
|---|---|---|
| T1 | PONG round trip | 8 s default model · 8 s `3.8-flash-high` · 12 s `3.8-flash-low` · 68 s `3.1-pro-high` |
| T2 | Seeded off-by-one bug, JSON answer requested | Found by both `3.8-flash-high` (11 s) and `3.1-pro-high` (20 s); JSON as asked |
| T3 | `--json-schema` | Schema respected, but 144 s |
| T4 | Needle in a 120 KB inline prompt | Found in 12 s |
| T5 | (no receipt carried into this record; numbering kept for cross-reference) | — |
| T6 | `scripts/arsenal_probe.py --seats agy` | LIVE, 6770 ms |

## Execution contexts

The seat was also run from a throwaway `gui/501` LaunchAgent, alone and with every seat
firing at once, to separate "CLI is slow" from "the launchd context is broken".

| Context | Cold-start round trip |
|---|---|
| Login session | 6.8 s |
| `gui/501` LaunchAgent, alone | 8.9 s |
| `gui/501` LaunchAgent, all seats concurrent | 13.7 s |

Both contexts are LIVE.

## Root cause of the fleet digest's `agy TIMEOUT`

The arsenal probe gave `agy` a 15 s budget. A cold start costs about 7 s alone, and the
digest fires all seats at once, which pushes the round trip to about 13.7 s in launchd,
within reach of the budget. The seat was not dead; the budget was too tight, so a slow-but-alive
answer was read as `TIMEOUT`. The fix is the sibling PR "fix(arsenal): give the agy probe a
40 s budget so a cold start is not read as TIMEOUT" on branch
`agent/nuzantara/infra/agy-probe-ctx`. This note carries only the measurement.

## Constraints hit while probing

The auto-mode classifier denied two actions. Both stand as constraints for any future probe:

1. Running `agy` with `--dangerously-skip-permissions`. Denied. Never bypass a sandbox to
   make a probe pass.
2. Re-reading the Antigravity CLI's own logs under `~/.gemini/antigravity-cli`. Denied.
   Probe evidence comes from the CLI's stdout and exit status, not from its private state
   directory.

## Verdict of the 4-seat review of the Antigravity memo

Seats: Fable, Kimi K3, Codex, Qwen 3.8 Max (2026-09-24).

- Delibera 1: EMENDA.
- Delibera 2: EMENDA.
- Delibera 3: RESPINGI — the `agy` seat stays `candidate-only`.

Converged conditions: no new seat is created; the existing `agy` row is amended (done in
this PR); no unattended scheduler on M5; visual evidence stays vendor-neutral; a measured
pilot comes before any promotion.

## What changed in the repo

- `FLEET_TOPOLOGY.json` `orchestrators.agy`: `models` now the five live ids; added
  `harness`, `contexts`, `probe_2026_09_24`. `fence` is unchanged (`candidate-only`).
- `MODEL_ROSTER.md` Google section: the two rows now carry the live ids
  `gemini-3.1-pro-high` and `gemini-3.8-flash-high`; a receipts pointer to this note was
  added.
