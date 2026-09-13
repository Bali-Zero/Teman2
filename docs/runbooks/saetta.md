# SAETTA operator runbook

SAETTA runs BLUE repository missions through the native Claude Workflow tool.
The launcher and `infra/workflows/saetta.js` ship together. It uses existing
subscription CLI seats; there is no vendor API, daemon or scheduled job.

## Start a mission

Use a dedicated worktree created by `scripts/agent_start.py` from the reviewed
revision. Keep its template and briefs immutable while a mission is running.
Resolve the manifest before launch:

```sh
python3 scripts/saetta.py prepare /absolute/path/to/mission.json --repo "$PWD"
python3 scripts/saetta.py preflight --repo "$PWD"
python3 scripts/saetta.py smoke --repo "$PWD"
python3 scripts/saetta.py run /absolute/path/to/mission.json --repo "$PWD" --timeout 86400
```

The last limit is a whole-invocation wall-clock abort. It does not measure the
Dux active-time budget: declare that budget and child/attempt caps in the briefs.
Do not mistake an authenticated CLI, an exit code or a launch acknowledgement
for a completed mission. Read the launcher's verified native receipt and the
mission receipt before reporting PASS.

The primary Codex profile must have the installed context hooks and 0.6 thresholds
for imperator, Dux and builder. A native smoke is a real subscription invocation;
it creates one read-only child and returns `SAETTA_NATIVE_SMOKE`.

Passing smoke on Pro, M5 and Mini proves native Workflow invocation and receipt
transport on those installed revisions. It does not validate a complete fleet
mission. The upcoming pilot must prove the full gate → CI recovery → merge →
consumer path on the released revision.

## Host seats

Paths are resolved on the launch host. The 2026-09-14 execution checks used:

| Host | Explicit options                           | Native smoke run  |
| ---- | ------------------------------------------ | ----------------- |
| Pro  | Default existing OAuth seat                | `wf_c12ffce3-e16` |
| M5   | `--claude "$HOME/.local/bin/claude-acct3"` | `wf_5d2fef70-429` |
| Mini | `--claude-config "$HOME/.claude-acct3"`    | `wf_a8c9d72e-cfb` |

Pass the selected options to both preflight and smoke/run. These are observed
working seats, not permanent account assumptions: repeat smoke after account or
CLI changes. Mini's default profile authenticated but its real model call was
organization-blocked during this check. Do not silently substitute credentials
or a different model family. M5 remains a thin client; briefs route heavy work
to Pro. `--heavy` refuses an explicitly heavy local invocation on M5.

## Mission contract

A manifest has `mission`, `colour: BLUE`, `maxParallel: 1..3` and up to twelve
tasks. Each task supplies a unique lowercase key, durable brief, literal
repository-relative file/directory scope and `dependsOn` keys. Relative brief
paths resolve against the manifest directory; output defaults below
`output/saetta/<mission>` in the launch worktree. Cycles, unknown dependencies
and unordered overlapping product scopes are rejected before dispatch.

Each brief defines a consumer outcome, acceptance checks, active-time/child
budgets and an authorized release/prove-live procedure. Required per-PR evidence
may be written only inside the canonical directory emitted by
`scripts/ci/evidence_paths.py`; this does not permit shared-ledger edits.

The Claude Dux prepares, obtains cross-family review, opens/arms the PR and
freezes its head. A fresh Opus gate commissioned by the imperator independently
checks that head, signs and reads back its receipts. It cannot edit, merge, arm,
rerun CI or deploy the candidate, and returns without waiting for merge. An
exact signed PASS dispatches the Claude release owner while the PR may still
be open. That owner diagnoses red checks and observes the normal merge queue.
Only a proven missing-gate failure on the original `pull_request` Harness run
permits one rerun per target, after reading back the matching posted PASS and
verifying the same frozen head. Record the cause and run ID before
`gh run rerun <original-run-id>`; a different cause, changed head or failed
retry is BLOCK. Never substitute a workflow dispatch, rerun a merge-group run,
manually merge or re-arm the candidate. The release owner records every actual
merge commit and reviewed head, then executes the brief's authorized consumer
proof. Both `merged: true` and a verified live receipt are required before any
dependent slice starts. External builder seats
remain prepare-only. The scheduler checks structured attestations; filesystem
and GitHub read-back are performed by the independent gate/release seats.

BLOCK keeps dependants closed while unrelated slices continue. A failed or
missing close cannot turn BLOCK into PASS. If the merge queue completes after
the release owner's deadline, the mission remains BLOCK until the imperator
reconciles the frozen target and its live proof. Do not blindly relaunch the
builder or resume a window with a live successor.

## Verify and update

Run the Node scheduler tests and Python bootstrap/receipt tests in the same
candidate. Boundary tests under `infra/codex-hooks/` cover the 60% context edge.
Behavioral fixtures do not prove native execution; retain both forms of evidence.
After independent BLUE gate and merge, fetch the reviewed revision on each host
and create a new broker worktree. Verify template/launcher hashes and run
preflight plus native smoke there. Never overwrite an active session script.
Rollback selects the previous reviewed revision for new missions only.
