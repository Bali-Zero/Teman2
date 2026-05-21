---
spec_id: T-2
title: Executor state manifest — persistent JSON tracker survive compaction/crash/restart
tier: pre-execution
priority: P0 (MUST RUN AFTER T-1, BEFORE Wave 0)
effort_estimate: 30 min
status: DRAFT
basis: Gemini 3.1 Pro Deep Think panel 2026-05-21 new_spec recommendation
---

# T-2 — Executor state manifest

## Problem

Gemini panel execution_failure_modes:

> _"Mid-Wave Halt Amnesia: If the executor errors out or hits a rate limit mid-wave, there is no persistent state-tracking manifest. The agent relies entirely on its context window to know where to resume."_

Plan ha 31 spec eseguibili in sequenza waves. Senza state manifest persistente:

- Context compaction → executor amnesia su quali spec già eseguite
- Crash/restart Claude Code → re-esecuzione duplicate
- Rate limit pausa → ripresa errata
- Manual interruption → no checkpoint

T-2 = JSON file `~/.claude/state/orchestration-execution-manifest.json` aggiornato dopo OGNI spec done.

## Context

Differenza vs T2.5 PreCompact Mnemos:

- **T2.5** = handoff strutturato a compaction time (objective/attempts/next)
- **T-2** = atomic spec completion tracker (which-spec-done flag)

Combination: T-2 source of truth per "where are we", T2.5 fornisce context per "what was just done before compaction".

## Acceptance criteria

- [ ] `~/.claude/state/orchestration-execution-manifest.json` esiste post-init
- [ ] Schema include: spec_id, status (pending/in_progress/completed/failed), started_at, completed_at, panel_review_blockers_addressed (list), checksum_after
- [ ] CLI helper `~/scripts/exec-state.sh` (init, set, get, list)
- [ ] All Wave executors MUST update manifest before/after each spec
- [ ] Manifest survives compaction (referenced by T2.5 handoff)
- [ ] Validation hook: refuse to start spec if manifest says already completed

## Implementation

### Step 1 — Schema design

> ⚠️ **DEPRECATED in iteration-2**: the original schema below lists `G1` as a single gate. Iteration-2 splits this into per-wave gates `G1.0`, `G1.1`, `G1.2`, `G1.3`, `G1.4` (see complete 31-spec schema in iteration-2 heredoc below at "Fix 3"). Do NOT init the executor from this table — use the iter-2 heredoc as authoritative. ~~`G1` (single gate)~~ → `G1.0` / `G1.1` / `G1.2` / `G1.3` / `G1.4` (see iter-2 schema).

```json
{
  "version": "1.0",
  "plan_id": "orchestration-fix-2026-05-21",
  "started_at": "2026-05-21T22:00:00",
  "current_wave": "0",
  "current_spec": null,
  "completed_specs": [],
  "failed_specs": [],
  "panel_review_integrated": {
    "deepseek_v4_pro": true,
    "gemini_31_pro_deep_think": true,
    "gpt55_xhigh_codex": true
  },
  "specs": {
    "T-1": { "status": "pending", "wave": "pre", "p": 0 },
    "T-2": { "status": "pending", "wave": "pre", "p": 0 },
    "T0.1": { "status": "pending", "wave": "0", "p": 0 },
    "T0.2": { "status": "pending", "wave": "0", "p": 0 },
    "T2.5": {
      "status": "pending",
      "wave": "0",
      "p": 0,
      "promoted_by": "gemini"
    },
    "T1.1": { "status": "pending", "wave": "1", "p": 0 },
    "T1.2": { "status": "pending", "wave": "1", "p": 0 },
    "T1.3": { "status": "pending", "wave": "1", "p": 1 },
    "T1.4": { "status": "pending", "wave": "1", "p": 1 },
    "T1.5": { "status": "pending", "wave": "1", "p": 1 },
    "T2.1": { "status": "pending", "wave": "2", "p": 1 },
    "T2.2": { "status": "pending", "wave": "2", "p": 1 },
    "T2.3": { "status": "pending", "wave": "2", "p": 1 },
    "T2.4": { "status": "pending", "wave": "2", "p": 1 },
    "T2.6": { "status": "pending", "wave": "2", "p": 2 },
    "T3.2": { "status": "pending", "wave": "3", "p": 2 },
    "T3.3": { "status": "pending", "wave": "3", "p": 2 },
    "T3.4": { "status": "pending", "wave": "3", "p": 3 },
    "T3.5": { "status": "pending", "wave": "3", "p": 2 },
    "T3.6": { "status": "pending", "wave": "3", "p": 3 },
    "T2.7": { "status": "pending", "wave": "4", "p": 1 },
    "G0": { "status": "pending", "wave": "gate", "p": 0 },
    "_DEPRECATED_G1_SEE_ITER2_HEREDOC": "Do not init from this legacy block. Use iter-2 31-entry heredoc at 'Fix 3' below as authoritative. G1 is now split into G1.0/G1.1/G1.2/G1.3/G1.4. An executor accidentally calling `check _DEPRECATED_G1_SEE_ITER2_HEREDOC` against a real manifest returns exit 2 (unknown) and halts loudly.",
    "G2": { "status": "pending", "wave": "gate", "p": 0 },
    "G3": { "status": "pending", "wave": "gate", "p": 0 },
    "G4": { "status": "pending", "wave": "gate", "p": 2 },
    "R1": { "status": "pending", "wave": "research", "p": 4 },
    "R2": { "status": "pending", "wave": "research", "p": 3 },
    "R3": { "status": "killed", "wave": "research", "killed_by": "deepseek" },
    "R4": { "status": "pending", "wave": "research", "p": 5 }
  }
}
```

### Step 2 — Init manifest script

```bash
mkdir -p ~/.claude/state

cat > ~/scripts/exec-state.sh << 'EOF'
#!/bin/bash
# T-2 executor state manifest CLI
# Usage:
#   exec-state.sh init         — create manifest if not exists
#   exec-state.sh start <id>   — mark spec as in_progress
#   exec-state.sh done <id>    — mark spec as completed
#   exec-state.sh fail <id> <msg> — mark spec as failed
#   exec-state.sh status       — print current state
#   exec-state.sh next         — print next pending spec id by wave/priority
#   exec-state.sh check <id>   — exit 0 if pending, 1 if in_progress/completed/failed

set -euo pipefail

MANIFEST=~/.claude/state/orchestration-execution-manifest.json
CMD="${1:-status}"

init_manifest() {
    if [ -f "$MANIFEST" ]; then
        echo "Manifest exists: $MANIFEST"
        return 0
    fi
    cat > "$MANIFEST" << 'INIT'
{
  "version": "1.0",
  "plan_id": "orchestration-fix-2026-05-21",
  "started_at": "",
  "current_wave": "pre",
  "current_spec": null,
  "completed_specs": [],
  "failed_specs": [],
  "specs": {}
}
INIT
    jq --arg ts "$(date -Iseconds)" '.started_at = $ts' "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"
    echo "Initialized: $MANIFEST"
}

case "$CMD" in
    init) init_manifest ;;
    start)
        SPEC="${2:?spec_id required}"
        TS=$(date -Iseconds)
        jq --arg id "$SPEC" --arg ts "$TS" \
            '.current_spec = $id | .specs[$id].status = "in_progress" | .specs[$id].started_at = $ts' \
            "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"
        echo "Started: $SPEC"
        ;;
    done)
        SPEC="${2:?spec_id required}"
        TS=$(date -Iseconds)
        jq --arg id "$SPEC" --arg ts "$TS" \
            '.specs[$id].status = "completed" | .specs[$id].completed_at = $ts | .completed_specs += [$id] | .current_spec = null' \
            "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"
        echo "Done: $SPEC"
        ;;
    fail)
        SPEC="${2:?spec_id required}"
        MSG="${3:-unspecified}"
        TS=$(date -Iseconds)
        jq --arg id "$SPEC" --arg ts "$TS" --arg msg "$MSG" \
            '.specs[$id].status = "failed" | .specs[$id].failed_at = $ts | .specs[$id].error = $msg | .failed_specs += [$id]' \
            "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"
        echo "Failed: $SPEC ($MSG)"
        ;;
    status)
        jq '{wave: .current_wave, current: .current_spec, completed: (.completed_specs|length), failed: (.failed_specs|length), pending: ([.specs | to_entries[] | select(.value.status == "pending")] | length)}' "$MANIFEST"
        ;;
    next)
        # Return id of next pending spec by wave order (pre, 0, 1, 2, 3, 4, gate, research) then priority
        jq -r '.specs | to_entries
            | map(select(.value.status == "pending"))
            | sort_by([.value.wave == "pre" | not, .value.wave == "0" | not, .value.wave == "1" | not, .value.wave == "2" | not, .value.wave == "3" | not, .value.wave == "4" | not, .value.p // 99])
            | .[0].key // "ALL_DONE"' "$MANIFEST"
        ;;
    check)
        SPEC="${2:?spec_id required}"
        STATUS=$(jq -r --arg id "$SPEC" '.specs[$id].status // "unknown"' "$MANIFEST")
        if [ "$STATUS" = "pending" ]; then
            echo "PENDING — ok to start"
            exit 0
        else
            echo "Status: $STATUS — DO NOT re-run"
            exit 1
        fi
        ;;
    *)
        echo "Unknown command: $CMD"
        exit 2
        ;;
esac
EOF
chmod +x ~/scripts/exec-state.sh

# Initialize
~/scripts/exec-state.sh init
```

### Step 3 — Wave executor integration pattern

Every Wave executor MUST call exec-state.sh:

```bash
# Pseudo-code for each spec execution:
SPEC_ID="T1.1"

# Check before
if ! ~/scripts/exec-state.sh check "$SPEC_ID"; then
    echo "Skip $SPEC_ID (not pending)"
    exit 0
fi

# Mark in_progress
~/scripts/exec-state.sh start "$SPEC_ID"

# Execute spec implementation...
# (...code from T1.1...)

# Mark done if successful
if [ $SUCCESS -eq 1 ]; then
    ~/scripts/exec-state.sh done "$SPEC_ID"
else
    ~/scripts/exec-state.sh fail "$SPEC_ID" "$ERROR_MSG"
fi
```

### Step 4 — Integration with T2.5 PreCompact handoff

T2.5 hook reads manifest to populate Mnemos handoff:

```python
# In ~/.claude/hooks/precompact_mnemos.py — add to parsed dict:
manifest_path = pathlib.Path.home() / ".claude/state/orchestration-execution-manifest.json"
if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text())
        parsed["execution_manifest"] = {
            "current_spec": manifest.get("current_spec"),
            "completed": manifest.get("completed_specs", []),
            "failed": manifest.get("failed_specs", []),
            "current_wave": manifest.get("current_wave"),
        }
    except json.JSONDecodeError:
        parsed["execution_manifest"] = {"error": "manifest_unreadable"}
```

### Step 5 — Validation gate (T1.2 guardrails extension)

Add to PreToolUse hook (T1.2 extended):

- If Bash contains "execute spec T1.X" patterns, verify manifest says pending
- Block if status != pending → prevents accidental re-run

## Verification

### Test 1 — manifest init

```bash
~/scripts/exec-state.sh init
ls -la ~/.claude/state/orchestration-execution-manifest.json
# Expected: file exists, valid JSON
jq . ~/.claude/state/orchestration-execution-manifest.json
```

### Test 2 — start + done flow

```bash
~/scripts/exec-state.sh start "T1.1"
~/scripts/exec-state.sh status
# Expected: current: T1.1

~/scripts/exec-state.sh done "T1.1"
~/scripts/exec-state.sh status
# Expected: completed: 1
```

### Test 3 — next selection

```bash
~/scripts/exec-state.sh next
# Expected: returns next pending spec id by wave/priority order
```

### Test 4 — check prevents re-run

```bash
~/scripts/exec-state.sh start "T1.2"
~/scripts/exec-state.sh done "T1.2"
~/scripts/exec-state.sh check "T1.2"
echo "exit=$?"
# Expected: "Status: completed — DO NOT re-run", exit=1
```

### Test 5 — survives compaction simulation

```bash
# Manually compact a session, verify T2.5 handoff includes manifest data
cat ~/.claude/state/precompact-handoff-*.json | jq '.execution_manifest'
# Expected: shows current_spec, completed, failed
```

## Rollback

```bash
rm ~/scripts/exec-state.sh
rm ~/.claude/state/orchestration-execution-manifest.json
```

## Open questions

1. **Atomicity**: jq `tmp + mv` is atomic on POSIX. OK for concurrent waves? Default = single-execution model.
2. **Manifest backup**: copy to git? Default = no (state, not source).
3. **Recovery from corrupted manifest**: backup snapshot in G3 already captures `~/.claude/state/`. Manual restore.

## Estimated breakdown

| Step                 | Tempo      |
| -------------------- | ---------- |
| Schema design        | 5 min      |
| exec-state.sh script | 15 min     |
| Test 1-5             | 7 min      |
| Documentation        | 3 min      |
| **Total**            | **30 min** |

---

## Fix WAVE -1 (2026-05-21): flock + pre-populate 30-spec schema

> **Status**: VALIDATED empirically via WAVE -1 smoke test (Test 4 — 10 parallel workers).
> **Source**: Opus 4.7 BLOCKER B5 closure. Empirical evidence captured in `WAVE-MINUS-1-FINAL-REPORT.md` and validated reference script at `/tmp/wave-minus-1/exec-state-flock.sh`.
> **Severity**: P0 (without these fixes, the executor manifest is unsafe under concurrent waves and `next` returns `ALL_DONE` immediately).

### Why two fixes are required

The original spec body above (Steps 1-5) shipped with two latent failures that WAVE -1 smoke testing surfaced:

1. **No cross-process locking** on manifest mutations. `jq … > tmp && mv tmp $MANIFEST` is atomic for a _single_ writer but the wave executors are explicitly designed to fan out to parallel sub-agents. Under contention the last-writer-wins, and worse: an interrupted `mv` between two siblings can truncate the JSON to 0 bytes.
2. **`init_manifest` writes `{"specs": {}}`** (empty map). The Step 3 wave executor reads `next` to pick the next pending spec; `jq` against an empty `specs` returns `"ALL_DONE"` immediately, so every concrete spec (T-1, T-2, T0.1 … R4) is _skipped_. The executor reports success without doing any work.

### WAVE -1 empirical confirmation

Test 4 ran:

```bash
for i in $(seq 1 10); do
    ( exec-state.sh start "SMOKE-$i" && sleep 0.05 && exec-state.sh done "SMOKE-$i" ) &
done
wait
jq '.completed_specs | length' $MANIFEST
```

| Variant                                                        | `completed_specs` length | Manifest integrity                                              | Verdict                   |
| -------------------------------------------------------------- | ------------------------ | --------------------------------------------------------------- | ------------------------- |
| Without flock (Step 2 above as-shipped)                        | **0/10**                 | manifest truncated to **0 bytes**                               | catastrophic — fails open |
| With `flock -x 200 200>$MANIFEST.lock` wrapping every mutation | **10/10**                | `jq .` parses cleanly, all 10 ids present in `.completed_specs` | accepted                  |

Reference impl that produced the 10/10 result: `/tmp/wave-minus-1/exec-state-flock.sh` (validated 2026-05-21 during WAVE -1 smoke test).

### Fix 1 — flock cross-process locking on every mutation

Wrap every command that _writes_ the manifest (`init`, `start`, `done`, `fail`) in an exclusive flock against a dedicated lock file. Read-only commands (`status`, `next`, `check`) do **not** acquire the lock — they tolerate snapshot-of-now semantics and shouldn't block writers.

Replace the `case "$CMD"` block in Step 2 above with this validated pattern:

```bash
MANIFEST=~/.claude/state/orchestration-execution-manifest.json
LOCK="$MANIFEST.lock"

acquire_lock() {
    # fd 200 → exclusive advisory lock; auto-released when subshell exits
    exec 200>"$LOCK"
    flock -x 200
}

case "$CMD" in
    init|start|done|fail)
        acquire_lock
        # … existing jq … > tmp && mv tmp $MANIFEST logic …
        ;;
    status|next|check)
        # read-only — no lock required
        ;;
    *)
        echo "Unknown command: $CMD"
        exit 2
        ;;
esac
```

**Invariants:**

- `flock -x 200` blocks (no timeout) until the lock is acquired. For the smoke-test workload (10 workers × ~50ms hold time) the worst-case wait is ~500ms — acceptable.
- `exec 200>"$LOCK"` creates the lock file if absent (mode 0644 by default; the file content is empty and never read).
- The lock is automatically released when the shell exits, including on `set -e` failure mid-`jq`.
- `mv tmp $MANIFEST` remains atomic on POSIX — flock prevents the _write_ race, atomic mv prevents the _replace_ race.

### Fix 2 — pre-populate the full 30-spec schema in `init_manifest`

Replace the `INIT` heredoc in Step 2 above. The new version enumerates every spec the plan will execute, with `status: "pending"` so that `check <id>` distinguishes:

- `unknown` — id is **not in the schema** → exit 2 (executor error, fail loudly)
- `pending` — id is in schema, never started → exit 0, ok to start
- `in_progress` — currently held by another worker → exit 0, status returned
- `completed` — already done → exit 0, status returned

Concrete `init_manifest` snippet (T-1, T-2, T0.1, T0.2 shown — every remaining spec follows the same pattern):

```bash
init_manifest() {
    acquire_lock
    if [ -f "$MANIFEST" ]; then
        echo "Manifest exists: $MANIFEST"
        return 0
    fi
    cat > "$MANIFEST" << 'INIT'
{
  "version": "1.1",
  "plan_id": "orchestration-fix-2026-05-21",
  "started_at": "",
  "current_wave": "pre",
  "current_spec": null,
  "completed_specs": [],
  "failed_specs": [],
  "specs": {
    "T-1":  {"status": "pending", "wave": "pre",      "deps": []},
    "T-2":  {"status": "pending", "wave": "pre",      "deps": ["T-1"]},
    "T0.1": {"status": "pending", "wave": "0",        "deps": ["T-2"]},
    "T0.2": {"status": "pending", "wave": "0",        "deps": ["T-2"]}
    /* … 26 more entries follow identical shape, see full list below … */
  }
}
INIT
    jq --arg ts "$(date -Iseconds)" '.started_at = $ts' "$MANIFEST" > "$MANIFEST.tmp" \
        && mv "$MANIFEST.tmp" "$MANIFEST"
    echo "Initialized with 30-spec schema: $MANIFEST"
}
```

**`check <id>` semantics (revised):**

```bash
check)
    SPEC="${2:?spec_id required}"
    STATUS=$(jq -r --arg id "$SPEC" '.specs[$id].status // "unknown"' "$MANIFEST")
    case "$STATUS" in
        unknown)
            echo "UNKNOWN — spec '$SPEC' not in manifest schema (typo? add to init_manifest?)"
            exit 2
            ;;
        pending)
            echo "PENDING — ok to start"
            exit 0
            ;;
        in_progress|completed|failed)
            echo "Status: $STATUS"
            exit 0
            ;;
    esac
    ;;
```

Note the contract change: `check` no longer returns exit 1 for already-started specs. Callers that want a guardrail ("refuse if not pending") test the printed STATUS string instead. This makes `check` safe to call from `status`-style probes that just want to read state without crashing the executor.

### The 30 specs (full enumeration)

> ⚠️ **DEPRECATED in iteration-2**: this table lists `G1` as a single gate row. Iteration-2 splits `G1` into per-wave gates `G1.0`, `G1.1`, `G1.2`, `G1.3`, `G1.4` (5 distinct gates, one per wave transition). Do NOT init the executor from this table — use the iter-2 heredoc at "Fix 3" below as authoritative. ~~`G1` (single gate)~~ → `G1.0` / `G1.1` / `G1.2` / `G1.3` / `G1.4` (see iter-2 schema).

Wave order per `00-INDEX.md`: `pre → 0 → 1 → 2 → 3 → 4 → gate → research`. Within a wave, the executor follows `00-INDEX.md` priority. R3 is killed and stays out of the schema.

| Wave                       | Specs                                                                 | Count                             |
| -------------------------- | --------------------------------------------------------------------- | --------------------------------- |
| `pre` (pre-execution)      | T-1, T-2                                                              | 2                                 |
| `0` (Wave 0)               | T0.1, T0.2, T2.5 _(promoted by Gemini B3)_                            | 3                                 |
| `1` (Wave 1)               | T1.1, T1.2, T1.3, T1.4, T1.5                                          | 5                                 |
| `2` (Wave 2)               | T2.1, T2.2, T2.3, T2.4, T2.6 _(T2.5 lives in wave 0, T2.7 in wave 4)_ | 5                                 |
| `3` (Wave 3)               | T3.2, T3.3, T3.4, T3.5, T3.6                                          | 5                                 |
| `4` (Wave 4)               | T2.7 _(CLAUDE.md project refactor, last)_                             | 1                                 |
| `gate` (validation gates)  | G0, ~~G1~~ → G1.0/G1.1/G1.2/G1.3/G1.4 _(see iter-2)_, G2, G3, G4      | 5                                 |
| `research` (parallel/post) | R1, R2, R4 _(R3 killed)_                                              | 3                                 |
| **Total**                  |                                                                       | **29 active + 1 killed = 30 ids** |

Each entry in the `specs` map of `init_manifest` MUST be present so that:

1. The executor's `next` command can route through wave-then-priority sort order without missing a spec.
2. `check <id>` exits 2 (not 0) when an unknown id is passed — protects against typos that previously fell through as "pending".
3. The G3 rollback script can hash-compare expected vs actual schema before restoring (compatible with the manifest-pointer pattern documented in T-1 + G3 — those specs use their own `~/backups/manifest-*.txt`; nothing here changes that contract).

The `deps` array is purely advisory at this stage (executors still use wave/priority order from `00-INDEX.md` as source of truth). It is included so a future scheduler can switch to DAG-driven execution without re-shaping the manifest.

### Verification (additive to Tests 1-5 above)

#### Test 6 — flock prevents concurrent-mutation corruption

```bash
~/scripts/exec-state.sh init
for i in $(seq 1 10); do
    (
        ~/scripts/exec-state.sh start "SMOKE-$i" >/dev/null
        sleep 0.05
        ~/scripts/exec-state.sh done  "SMOKE-$i" >/dev/null
    ) &
done
wait
COUNT=$(jq '.completed_specs | length' "$HOME/.claude/state/orchestration-execution-manifest.json")
[ "$COUNT" = "10" ] && echo "PASS Test 6: 10/10 writes preserved" || { echo "FAIL Test 6: $COUNT/10"; exit 1; }
jq . "$HOME/.claude/state/orchestration-execution-manifest.json" >/dev/null \
    && echo "PASS Test 6: manifest valid JSON" \
    || { echo "FAIL Test 6: manifest corrupted"; exit 1; }
```

Note: Test 6 uses transient ids (`SMOKE-1` … `SMOKE-10`) NOT in the pre-populated schema, so it exercises the write path without colliding with the real spec ids. The test asserts `.completed_specs` length, which `done` appends to even for unknown ids (existing behaviour). For a stricter version, pre-seed those ids in the schema before running.

#### Test 7 — pre-populated schema lets `next` find work

```bash
~/scripts/exec-state.sh init
NEXT=$(~/scripts/exec-state.sh next)
[ "$NEXT" = "T-1" ] && echo "PASS Test 7: first pending = T-1" || { echo "FAIL Test 7: got '$NEXT'"; exit 1; }
```

Before Fix 2 this returned `ALL_DONE` because `specs: {}` had no pending entries.

#### Test 8 — `check unknown_id` exits 2

```bash
~/scripts/exec-state.sh init
# Iter-6: `|| EC=$?` short-circuits set -e. The bare `check; EC=$?` form
# (iter-2 original) dies under `set -euo pipefail` because exit 2 is the
# expected return and set -e kills the script BEFORE the EC capture.
EC=0
~/scripts/exec-state.sh check "NOT-A-REAL-SPEC" || EC=$?
[ "$EC" = "2" ] && echo "PASS Test 8: unknown id → exit 2" || { echo "FAIL Test 8: exit $EC"; exit 1; }
```

### Migration note for already-initialized manifests

If `~/.claude/state/orchestration-execution-manifest.json` was created with the original (pre-WAVE -1) script and has `specs: {}`, run:

```bash
mv ~/.claude/state/orchestration-execution-manifest.json \
   ~/.claude/state/orchestration-execution-manifest.pre-wave-minus-1.json
~/scripts/exec-state.sh init   # re-seeds with the 30-spec schema
```

G3 backup snapshot (per T-1 + G3) already captures `~/.claude/state/` so this is reversible.

### Compatibility with T-1 and G3

- T-1 stores its backup id pointer at `~/backups/last-backup-id.txt` and a hash manifest at `~/backups/manifest-<id>.txt`. These are **independent** of the execution manifest — names are similar but the file contracts don't overlap.
- G3's `rollback-orchestration-fix.sh <backup_id>` restores both the T-1 backup _and_ the entire `~/.claude/state/` directory, so the post-WAVE -1 30-spec schema is preserved across rollback cycles.
- No changes are required to T-1 or G3 to consume this fix.

---

## Fix WAVE -1 Iteration 2 (2026-05-21): check exit semantics + flock timeout + complete heredoc

> **Status**: SUPERSEDES the "Fix WAVE -1" section above for the three areas it covers (`check` exit codes, lock-acquisition timeout, init heredoc completeness). All other contracts from iteration-1 (flock-on-mutations, read-only-no-lock, the 30-spec enumeration table) remain unchanged.
> **Source**: devils-advocate gate findings on iteration-1 commit `f2ecbe0ea`. Three CRITICAL/HIGH/MEDIUM regressions identified and fixed in this iteration.
> **Severity**: P0 (CRITICAL fix 1 breaks executor idempotency; HIGH fix 2 enables silent deadlock; MEDIUM fix 3 forces implementor to hand-write 26 entries).

### Why iteration-1 was rejected

Iteration-1 shipped three latent defects on top of the original flock + pre-populate fixes:

1. **CRITICAL — `check <id>` exit-code inversion.** Iteration-1 returned `exit 0` for every non-`unknown` status (`pending` / `in_progress` / `completed` / `failed`) and `exit 2` for unknown. This **silently inverts** the documented Step 3 guard `if ! check "$SPEC_ID"; then exit 0; fi`: under the new semantics `check` returns 0 for a `completed` spec, so `! check` is false, and the executor proceeds to **re-run the completed spec**. Catastrophic loss of idempotency.
2. **HIGH — `flock -x 200` has no timeout.** A worker that dies while holding the lock (SIGKILL, OOM, crash mid-`jq`) keeps the lockfile descriptor open in the parent shell until the entire process tree exits. Wave 2 parallel executors would block forever on the next `start`/`done` call. Symptom: stuck PID with no log advance, no Telegram alert.
3. **MEDIUM — `init_manifest` heredoc shows 4 example entries + a prose table for the remaining 26.** A human implementor running the spec must hand-type 26 lines of JSON, copying ids from the wave-grouping table. Drift between the spec and the runtime schema is guaranteed within one or two iterations.

### Fix 1 (CRITICAL) — revert `check <id>` exit contract

The original (pre-iteration-1) contract treats `check` as a "runnable?" probe. Iteration-2 restores that contract verbatim and makes it the only contract:

- exit `0` **only if** status is `pending` (the spec has never been started → safe to run)
- exit `1` if status is in {`in_progress`, `completed`, `failed`} (already handled or in-flight by another worker → skip, do not re-run)
- exit `2` if status is `unknown` (id not in schema → fail loudly, halt the executor — almost certainly a typo or a missing entry in `init_manifest`)

**BEFORE (iteration-1, WRONG — every non-unknown returns 0):**

```bash
check)
    SPEC="${2:?spec_id required}"
    STATUS=$(jq -r --arg id "$SPEC" '.specs[$id].status // "unknown"' "$MANIFEST")
    case "$STATUS" in
        unknown)
            echo "UNKNOWN — spec '$SPEC' not in manifest schema"
            exit 2
            ;;
        pending)
            echo "PENDING — ok to start"
            exit 0
            ;;
        in_progress|completed|failed)
            echo "Status: $STATUS"
            exit 0   # <-- BUG: this makes `if ! check; then skip` always false
            ;;
    esac
    ;;
```

**AFTER (iteration-2, partial — exit 0 only for `pending`):**

> ⚠️ **ITER-2 CONFLATED `completed` + `failed` + `in_progress` UNDER A SINGLE `exit 1`** — silent fail mask. A `failed` spec returned exit 1, making the Step 3 guard `if ! check; then echo "Skip"; exit 0; fi` fire on a real failure, so the executor reported SUCCESS and the orchestrator continued the dependency chain past a broken prerequisite. **Iter-5 (Gemini Deep Think GDT-2) fixes this by differentiating the failure modes into distinct exit codes.** The block below is preserved for historical context; the iter-5 case statement at "Fix Iteration 5" supersedes it for every executor and integration callsite.

```bash
check)
    SPEC="${2:?spec_id required}"
    STATUS=$(jq -r --arg id "$SPEC" '.specs[$id].status // "unknown"' "$MANIFEST")
    case "$STATUS" in
        pending)
            echo "PENDING — ok to start"
            exit 0   # runnable
            ;;
        in_progress)
            echo "IN_PROGRESS — held by another worker, skip"
            exit 1   # in-flight, skip  -- ITER-2 BUG: conflated with completed/failed
            ;;
        completed|failed)
            echo "Status: $STATUS — already handled, skip"
            exit 1   # ITER-2 BUG: `failed` MUST NOT exit 1 — operator-must-investigate, see iter-5
            ;;
        unknown|*)
            echo "UNKNOWN — spec '$SPEC' not in manifest schema (typo? add to init_manifest?)" >&2
            exit 2   # error — halt the executor
            ;;
    esac
    ;;
```

#### Step 3 documentation under iteration-2 semantics

> ⚠️ **SUPERSEDED BY ITER-5.** The `if ! ~/scripts/exec-state.sh check "$SPEC_ID"; then echo "Skip"; exit 0; fi` guard below was iter-2's intended integration pattern, but because iter-2 mapped `failed` to `exit 1` (alongside `completed`/`in_progress`), the guard collapses a genuine prior failure into a silent "Skip … exit 0" — orchestrator concludes SUCCESS and proceeds, breaking the dependency chain. The iter-5 integration pattern uses an explicit `case $?` against five distinct exit codes; see "Fix Iteration 5 / Step 3 integration pattern (iter-5)" below for the corrected wave-executor block. The block here is preserved for historical context only.

```bash
SPEC_ID="T1.1"

# ITER-2 GUARD (DEPRECATED): exit 1 conflates completed/failed/in_progress,
# so a FAILED prior run is silently skipped and the executor reports SUCCESS.
# Use the iter-5 `case $?` pattern instead — it halts on failed/in_progress/unknown.
if ! ~/scripts/exec-state.sh check "$SPEC_ID"; then
    echo "Skip $SPEC_ID (not pending)"
    exit 0
fi

~/scripts/exec-state.sh start "$SPEC_ID"
# … run spec implementation …
if [ "$SUCCESS" = 1 ]; then
    ~/scripts/exec-state.sh done "$SPEC_ID"
else
    ~/scripts/exec-state.sh fail "$SPEC_ID" "$ERROR_MSG"
fi
```

The `exit 2` path for unknown ids was intentionally separated from the `exit 1` skip path: under `set -euo pipefail` (the script's own preamble) an unknown id makes the executor abort instead of silently skipping. Iter-5 retains this `exit 2` semantics for `unknown` and adds `exit 3` (failed) and `exit 4` (in_progress) as additional halt-loudly codes so `failed` and `in_progress` can no longer hide behind a generic skip.

#### Test case — guard correctly skips completed specs (regression test for iteration-1 inversion)

```bash
~/scripts/exec-state.sh init
~/scripts/exec-state.sh start "T-1"
~/scripts/exec-state.sh done  "T-1"

# Re-run guard: must skip, must NOT re-execute.
if ! ~/scripts/exec-state.sh check "T-1"; then
    echo "PASS: completed spec correctly skipped"
    exit 0
else
    echo "FAIL: iteration-1 regression — completed spec would have been re-run"
    exit 1
fi
# Expected stdout: "Status: completed — already handled, skip"
#                  "PASS: completed spec correctly skipped"
```

### Fix 2 (HIGH) — `flock -w 10 -x 200` with fail-loud recovery procedure

Replace every `flock -x 200` call with `flock -w 10 -x 200`. The 10-second timeout is long enough to ride out the 10-worker × 50ms-hold smoke-test workload (worst-case ~500ms) while still failing loudly on a stale writer (e.g. crashed sibling holding the lock for the lifetime of the parent shell).

```bash
acquire_lock() {
    # fd 200 → exclusive advisory lock; auto-released when subshell exits.
    # -w 10  → wait at most 10 seconds before giving up.
    exec 200>"$LOCK"
    if ! flock -w 10 -x 200; then
        echo "FATAL: failed to acquire manifest lock within 10s — stale writer?" >&2
        echo "Run: lsof '$LOCK' to find the holder. If no process is listed," >&2
        echo "manually: rm -f '$LOCK'" >&2
        exit 3
    fi
}
```

**Recovery procedure when fix 2 fires** (documented inline so an operator sees it without digging through scars):

1. `lsof "$LOCK"` — if a PID is listed, the holder is alive but wedged (likely a stuck `jq`). `kill -TERM <pid>` first, `kill -KILL <pid>` if that fails.
2. If `lsof` shows nothing, the lock is orphaned (POSIX `flock` releases on process exit, so this only happens if the file itself is corrupt or held by a vanished namespace). `rm -f "$LOCK"` is safe — the next `acquire_lock` re-creates it.
3. `exit 3` is reserved for "lock acquisition timeout" and is distinct from `exit 2` (unknown spec id) and `exit 1` (generic skip). Callers may inspect `$?` to decide between retry vs Telegram alert.

The 10-second value is empirical: WAVE -1 Test 4 (10 workers × ~50ms hold) saturated around 500ms worst-case wait; iteration-2 leaves a 20× safety margin without making the executor hang noticeably on a real wedge.

### Fix 3 (MEDIUM) — `init_manifest` heredoc embeds all 31 spec entries

Replace the iteration-1 heredoc (4 example entries + prose table) with a single self-contained JSON document covering every spec the plan will execute. No more drift between the spec body and the runtime schema.

The schema models the wave/gate structure documented in `00-INDEX.md`:

- 2 pre-execution specs (T-1, T-2)
- 4 wave-0 specs (T0.1, T0.2, T2.5, T3.1)
- 5 wave-1 specs (T1.1 – T1.5)
- 5 wave-2 specs (T2.1, T2.2, T2.3, T2.4, T2.6)
- 5 wave-3 structural specs: T3.2, T3.3, T3.4, T3.5, T3.6. (T3.1 was promoted to Wave 0 per WAVE -1 final report — fixes 115 MCP tools currently DEAD due to DNS lookup failure before Wave 1 hook installation.)
- 1 wave-4 spec (T2.7)
- 5 inter-wave validation gates (G1.0, G1.1, G1.2, G1.3, G1.4)
- 4 cross-cutting gates (G0 disaster-recovery, G2 post-fix, G3 disaster-recovery, G4 post-fix)

Total = **31 entries** in the `specs` map (2 + 4 + 5 + 5 + 5 + 1 + 5 + 4 = 31). R3 stays killed and out of the schema. R1/R2/R4 are parallel-research specs and remain out of the executor manifest — they are scheduled by a separate pipeline.

```bash
init_manifest() {
    acquire_lock
    if [ -f "$MANIFEST" ]; then
        echo "Manifest exists: $MANIFEST"
        return 0
    fi
    cat > "$MANIFEST" << 'INIT'
{
  "version": "1.2",
  "created_at": "",
  "completed_specs": [],
  "specs": {
    "T-1":  {"wave": "pre",      "status": "pending", "deps": []},
    "T-2":  {"wave": "pre",      "status": "pending", "deps": ["T-1"]},
    "T0.1": {"wave": 0,          "status": "pending", "deps": ["T-2"]},
    "T0.2": {"wave": 0,          "status": "pending", "deps": ["T-2"]},
    "T2.5": {"wave": 0,          "status": "pending", "deps": ["T-2"]},
    "G1.0": {"wave": "gate",     "status": "pending", "deps": ["T0.1","T0.2","T2.5"]},
    "T1.1": {"wave": 1,          "status": "pending", "deps": ["G1.0"]},
    "T1.2": {"wave": 1,          "status": "pending", "deps": ["G1.0"]},
    "T1.3": {"wave": 1,          "status": "pending", "deps": ["G1.0"]},
    "T1.4": {"wave": 1,          "status": "pending", "deps": ["G1.0"]},
    "T1.5": {"wave": 1,          "status": "pending", "deps": ["G1.0"]},
    "G1.1": {"wave": "gate",     "status": "pending", "deps": ["T1.1","T1.2","T1.3","T1.4","T1.5"]},
    "T2.1": {"wave": 2,          "status": "pending", "deps": ["G1.1"]},
    "T2.2": {"wave": 2,          "status": "pending", "deps": ["G1.1"]},
    "T2.3": {"wave": 2,          "status": "pending", "deps": ["G1.1"]},
    "T2.4": {"wave": 2,          "status": "pending", "deps": ["G1.1"]},
    "T2.6": {"wave": 2,          "status": "pending", "deps": ["G1.1"]},
    "G1.2": {"wave": "gate",     "status": "pending", "deps": ["T2.1","T2.2","T2.3","T2.4","T2.6"]},
    "T3.1": {"wave": 0,          "status": "pending", "deps": ["T-2"]},
    "T3.2": {"wave": 3,          "status": "pending", "deps": ["G1.2"]},
    "T3.3": {"wave": 3,          "status": "pending", "deps": ["G1.2"]},
    "T3.4": {"wave": 3,          "status": "pending", "deps": ["G1.2"]},
    "T3.5": {"wave": 3,          "status": "pending", "deps": ["G1.2"]},
    "T3.6": {"wave": 3,          "status": "pending", "deps": ["G1.2"]},
    "G1.3": {"wave": "gate",     "status": "pending", "deps": ["T3.2","T3.3","T3.4","T3.5","T3.6"]},
    "T2.7": {"wave": 4,          "status": "pending", "deps": ["G1.3"]},
    "G1.4": {"wave": "gate",     "status": "pending", "deps": ["T2.7"]},
    "G0":   {"wave": "disaster", "status": "pending", "deps": []},
    "G2":   {"wave": "post-fix", "status": "pending", "deps": ["G1.4"]},
    "G3":   {"wave": "disaster", "status": "pending", "deps": []},
    "G4":   {"wave": "post-fix", "status": "pending", "deps": ["G2"]}
  }
}
INIT
    jq --arg ts "$(date -Iseconds)" '.created_at = $ts' "$MANIFEST" > "$MANIFEST.tmp" \
        && mv "$MANIFEST.tmp" "$MANIFEST"
    echo "Initialized with 31-spec schema: $MANIFEST"
}
```

#### Validity of the embedded JSON

The heredoc body is valid JSON. To verify in-line (the test belongs in `Test 9` below):

```bash
JSON=$(sed -n '/^INIT$/,/^INIT$/ { /^INIT$/d; p; }' <<'WHOLE_SCRIPT'
… paste init_manifest body …
WHOLE_SCRIPT
)
jq empty <<< "$JSON" && echo "PASS: heredoc is valid JSON"
```

Practically, the simpler test is to run `init_manifest` itself and `jq .` the result:

```bash
~/scripts/exec-state.sh init
jq empty ~/.claude/state/orchestration-execution-manifest.json \
    && echo "PASS Test 9: 31-spec init heredoc parses cleanly" \
    || { echo "FAIL Test 9: heredoc emitted invalid JSON"; exit 1; }
COUNT=$(jq '.specs | length' ~/.claude/state/orchestration-execution-manifest.json)
[ "$COUNT" = "31" ] && echo "PASS Test 9: 31 specs in schema" \
    || { echo "FAIL Test 9: expected 31, got $COUNT"; exit 1; }
```

#### Reconciliation with the iteration-1 enumeration table

The iteration-1 "30 specs" table grouped specs by wave including R1/R2/R4 (3 research specs) and excluded the per-wave validation gates G1.0–G1.4 (because iteration-1 collapsed them into a single `G1` row). Iteration-2 inverts that trade-off: research specs leave the executor manifest (they have their own scheduler), and the per-wave gates enter as five distinct rows. Plus T3.1 lives in wave 0 (per the brief's prescribed schema), not wave 3 — an early-wave invariant inherited from `00-INDEX.md`. The net count is 31 (vs 29 active in iteration-1).

### Verification (additive to Tests 1-8)

#### Test 9 — init heredoc emits valid JSON with 31 entries

See block above.

#### Test 10 — `check completed` correctly returns exit 1 (iteration-1 regression test)

```bash
~/scripts/exec-state.sh init
~/scripts/exec-state.sh start "T-1"
~/scripts/exec-state.sh done  "T-1"
# Iter-6: `|| EC=$?` short-circuits set -e. The bare `check; EC=$?` form
# (iter-2 original) dies under `set -euo pipefail` for any non-zero exit
# code BEFORE the EC capture, so this test would false-fail on the very
# behavior it intends to verify (completed → exit 1).
EC=0
~/scripts/exec-state.sh check "T-1" || EC=$?
[ "$EC" = "1" ] && echo "PASS Test 10: completed → exit 1" \
    || { echo "FAIL Test 10: expected 1, got $EC (iteration-1 regression)"; exit 1; }
```

#### Test 11 — flock timeout fires within 10s when lock is held

```bash
LOCK=~/.claude/state/orchestration-execution-manifest.json.lock
(
    exec 201>"$LOCK"
    flock -x 201
    sleep 30
) &
HOLDER=$!
sleep 0.5  # let the holder grab the lock

START=$(date +%s)
~/scripts/exec-state.sh start "TIMEOUT-TEST" || EC=$?
END=$(date +%s)
kill "$HOLDER" 2>/dev/null
ELAPSED=$((END - START))

[ "$EC" = "3" ] && [ "$ELAPSED" -ge 9 ] && [ "$ELAPSED" -le 12 ] \
    && echo "PASS Test 11: timeout fired at ${ELAPSED}s, exit=3" \
    || { echo "FAIL Test 11: exit=$EC elapsed=${ELAPSED}s"; exit 1; }
```

### Migration note for already-deployed iteration-1 manifests

If the manifest on disk was created by iteration-1 (will have `version: "1.1"` and only 4 specs in `specs`), drop and re-init:

```bash
mv ~/.claude/state/orchestration-execution-manifest.json \
   ~/.claude/state/orchestration-execution-manifest.iter1.bak
~/scripts/exec-state.sh init   # re-seeds with the 31-spec iteration-2 schema
```

The G3 rollback contract is unchanged — `~/.claude/state/` continues to be snapshotted as a whole, so iteration-2 manifests roll back identically to iteration-1.

---

## Fix Iteration 5 (Gemini Deep Think GDT-2, CRITICAL): differentiate completed vs failed exit codes

> **Status**: SUPERSEDES iteration-2 Fix 1 (`check <id>` exit contract) and the Step 3 integration pattern. All other contracts from iteration-1 + iteration-2 (flock-on-mutations, read-only-no-lock, `flock -w 10` timeout, 31-spec init heredoc, G1 halt sentinel) remain unchanged.
> **Source**: Gemini 3.1 Pro Deep Think panel review finding **GDT-2 (CRITICAL)** — silent fail-mask in the iter-2 `check` contract.
> **Severity**: P0 (CRITICAL — iter-2 conflated `completed` + `failed` + `in_progress` under a single `exit 1`, so a FAILED prior run was indistinguishable from a SAFE idempotent skip; the Step 3 guard `if ! check; then echo "Skip"; exit 0; fi` then reported SUCCESS to the orchestrator, breaking the dependency chain without warning).

### Why iteration-2 was rejected (GDT-2 finding)

Iteration-2 Fix 1 (the "AFTER" block in the section above) said:

```bash
case "$STATUS" in
    pending)                  exit 0 ;;   # runnable
    in_progress)              exit 1 ;;   # in-flight, skip
    completed|failed)         exit 1 ;;   # already handled, skip
    unknown|*)                exit 2 ;;   # error — halt
esac
```

Treating `failed` as "already handled, skip" is **the fail mask**:

- A prior failed run leaves `status=failed` in the manifest with an `.error` field documenting what broke.
- Step 3 integration guard: `if ! ~/scripts/exec-state.sh check "$SPEC_ID"; then echo "Skip"; exit 0; fi`.
- `check` returns exit 1 (because iter-2 mapped `failed` → 1) → the `! check` branch fires → executor prints "Skip" and exits 0 → **orchestrator sees `exit 0` and reports SUCCESS for this spec**.
- The next spec in the wave depends on this one. It proceeds. The dependency chain is now built on a silent failure that no operator ever investigated.

`completed` is genuinely safe to skip (the spec is idempotent — re-running it is fine, but unnecessary). `failed` is **NEVER** safe to skip blindly: the operator must read `.specs[id].error`, decide whether the failure is transient (retry — reset to `pending`) or permanent (genuinely give up — leave as `failed` and halt the wave). Conflating the two was the iter-2 hallucination.

`in_progress` is a third distinct case: another worker is currently executing this spec. The orchestrator must halt and investigate (parallel-executor race, missed `done`/`fail` call after crash, or stale state from a SIGKILL'd worker).

### Fix (CRITICAL) — five distinct exit codes

Replace the iteration-2 `case "$STATUS"` block in the `check` subcommand of `exec-state.sh` with this five-state version:

```bash
check)
    SPEC="${2:?spec_id required}"
    STATUS=$(jq -r --arg id "$SPEC" '.specs[$id].status // "unknown"' "$MANIFEST")
    case "$STATUS" in
        pending)
            echo "PENDING — runnable"
            exit 0   # runnable — proceed
            ;;
        completed)
            echo "COMPLETED — idempotent skip (orchestrator MAY proceed)"
            exit 1   # safe skip
            ;;
        in_progress)
            echo "IN_PROGRESS — race detected (parallel executor or stale state); orchestrator MUST halt + investigate" >&2
            exit 4   # halt loudly
            ;;
        failed)
            echo "FAILED — prior run errored; operator MUST read .specs[$SPEC].error, decide retry vs skip, then halt" >&2
            exit 3   # halt loudly
            ;;
        unknown|*)
            echo "UNKNOWN — spec '$SPEC' not in manifest schema (typo? add to init_manifest?); orchestrator MUST halt + investigate" >&2
            exit 2   # halt loudly
            ;;
    esac
    ;;
```

**Exit code contract (iter-5 canonical):**

| Status        | Exit | Semantics                                                                 |
| ------------- | ---- | ------------------------------------------------------------------------- |
| `pending`     | 0    | Runnable — orchestrator proceeds with `start` + run.                      |
| `completed`   | 1    | Idempotent skip — orchestrator MAY proceed to the next spec.              |
| `unknown`     | 2    | Schema mismatch — orchestrator MUST halt and investigate.                 |
| `failed`      | 3    | Prior failure — orchestrator MUST halt; operator inspects error, decides. |
| `in_progress` | 4    | Race detected — orchestrator MUST halt; investigate parallel executor.    |

Rationale (per GDT-2):

- `completed` (exit 1) is a **SAFE skip** — the spec ran to success previously, re-running is at worst a no-op (specs are designed idempotent).
- `failed` (exit 3) is **UNSAFE to skip blindly** — the operator must read `.specs[id].error` from the manifest, decide whether to (a) reset `status=pending` and retry, or (b) genuinely accept the failure (leave as `failed`) and halt the wave manually. Auto-skipping is what made iter-2 a silent fail mask.
- `in_progress` (exit 4) is **always a halt signal** — either a parallel executor is currently running this spec (concurrent-wave bug), or a previous executor crashed mid-spec without calling `fail` (stale state). Either way the orchestrator cannot safely proceed; the operator must reconcile.
- `unknown` (exit 2) retains its iter-2 semantics — schema mismatch, halt loudly.

The "halt loudly" exit codes (2, 3, 4) all route stderr to the operator log (note the `>&2` redirect) so a tail-following dashboard surfaces the failure mode visibly.

#### Reuse of exit-code 3 across `check` and `acquire_lock`

Iter-2 Fix 2 reserved `exit 3` for "manifest lock acquisition timeout" (in `acquire_lock()`). Iter-5 reuses `exit 3` for "prior spec failed" (in `check`). These are not in conflict in practice because:

- `check` is a read-only command (per iter-2 Fix 1) and does **not** acquire the lock — it cannot fire the `acquire_lock` exit 3.
- `acquire_lock` is only called by mutation subcommands (`init`, `start`, `done`, `fail`) — none of which is a check probe.

Both `exit 3` cases share the same operational meaning ("operator must investigate"), so callers' `case $?` blocks that handle exit 3 as "halt + investigate" remain correct regardless of the producer. Callers that need to disambiguate can inspect the captured stderr line (`FAILED — …` vs `FATAL: failed to acquire manifest lock …`).

### Step 3 integration pattern (iter-5)

Replace every iter-1/iter-2 wave-executor guard of the form `if ! ~/scripts/exec-state.sh check "$SPEC_ID"; then echo "Skip"; exit 0; fi` with this explicit `case $?` pattern:

```bash
SPEC_ID="T1.1"

# Iter-6: read check exit code via `|| SPEC_CODE=$?` short-circuit. Under
# `set -euo pipefail` a bare non-zero exit kills the script BEFORE the
# `case $?` dispatch ever runs (iter-5 bug B5-NEW-1). The `|| VAR=$?` form
# is one of the constructs `set -e` explicitly allows (POSIX: a command in
# an `||` list is not "checked"), so the non-zero exit is captured into
# SPEC_CODE and the case dispatch is reached for every status.
SPEC_CODE=0
~/scripts/exec-state.sh check "$SPEC_ID" || SPEC_CODE=$?
case ${SPEC_CODE} in
    0)
        echo "Run $SPEC_ID"
        # Mark in_progress, run spec, mark done/fail.
        ~/scripts/exec-state.sh start "$SPEC_ID"
        if run_spec "$SPEC_ID"; then
            ~/scripts/exec-state.sh done "$SPEC_ID"
        else
            ~/scripts/exec-state.sh fail "$SPEC_ID" "$ERROR_MSG"
            exit 3   # propagate failure to orchestrator — do NOT silently continue
        fi
        ;;
    1)
        echo "Skip $SPEC_ID (completed) — idempotent re-run, safe"
        exit 0   # orchestrator continues with next spec
        ;;
    2)
        echo "FATAL: $SPEC_ID unknown — schema mismatch (typo? missing entry in init_manifest?)" >&2
        exit 2   # halt orchestrator
        ;;
    3)
        echo "FATAL: $SPEC_ID previously FAILED — operator must read \$MANIFEST .specs[\"$SPEC_ID\"].error and decide retry vs skip" >&2
        exit 3   # halt orchestrator
        ;;
    4)
        echo "FATAL: $SPEC_ID in_progress — race detected (parallel executor? crashed worker without fail-update?)" >&2
        exit 4   # halt orchestrator
        ;;
    *)
        # Defensive: any other code is a contract drift — halt loudly.
        echo "FATAL: $SPEC_ID check returned unexpected exit code ${SPEC_CODE} — contract violation" >&2
        exit 5
        ;;
esac
```

Key differences vs the iter-1/iter-2 `if ! check` form:

- **No silent skip on failure**: exit 3 (failed) propagates upward via `exit 3` instead of collapsing to `exit 0`. The orchestrator's `set -e` (or its own `case $?` against the wave executor) sees the failure.
- **No silent skip on race**: exit 4 (in_progress) propagates upward. Operator investigates whether a parallel executor exists.
- **Explicit unknown handling**: exit 2 propagates with a "schema mismatch" diagnostic. The iter-2 guard had this implicitly via `set -e` killing the executor on a non-pending → non-zero — but it conflated _which_ non-pending state caused the kill.
- **Idempotent re-run survives**: exit 1 (completed) → orchestrator continues normally.

Callers that need a softer probe (e.g. dashboard "what's the manifest state right now?" without halting on failed/in_progress) should call `jq -r --arg id "$SPEC" '.specs[$id].status' "$MANIFEST"` directly and inspect the string, bypassing the strict exit-code contract of `check`.

### Verification (additive to Tests 1-11)

#### Test 12 — five distinct status values produce five distinct exit codes

```bash
~/scripts/exec-state.sh init

# Seed five specs into the manifest, one per status. T-1 already exists as `pending`
# in the init heredoc, so we exercise it for the pending case and create transient
# ids for the other four (using a small jq mutation since the public CLI only sets
# in_progress/completed/failed, not arbitrary status values).
MANIFEST=~/.claude/state/orchestration-execution-manifest.json

# Helper: directly inject a status without going through start/done/fail.
inject_status() {
    local id="$1" status="$2"
    jq --arg id "$id" --arg status "$status" \
        '.specs[$id] = {status: $status, wave: "test", deps: []}' \
        "$MANIFEST" > "$MANIFEST.tmp" && mv "$MANIFEST.tmp" "$MANIFEST"
}

inject_status "ITER5-COMPLETED"   "completed"
inject_status "ITER5-IN-PROGRESS" "in_progress"
inject_status "ITER5-FAILED"      "failed"
# ITER5-UNKNOWN deliberately NOT injected — left as schema-absent for exit-2 path.

declare -A EXPECTED=(
    ["T-1"]=0                  # pending
    ["ITER5-COMPLETED"]=1
    ["ITER5-UNKNOWN"]=2
    ["ITER5-FAILED"]=3
    ["ITER5-IN-PROGRESS"]=4
)

PASS=0
FAIL=0
for id in "${!EXPECTED[@]}"; do
    expected="${EXPECTED[$id]}"
    # Iter-6: `|| actual=$?` short-circuits set -e. A bare
    # `check "$id"; actual=$?` would die under `set -e` for any non-zero
    # exit BEFORE the dispatch — the test would never observe codes 1/2/3/4.
    actual=0
    ~/scripts/exec-state.sh check "$id" >/dev/null 2>&1 || actual=$?
    if [ "$actual" = "$expected" ]; then
        echo "PASS Test 12: $id → exit $actual (expected $expected)"
        PASS=$((PASS+1))
    else
        echo "FAIL Test 12: $id → exit $actual (expected $expected)"
        FAIL=$((FAIL+1))
    fi
done

[ "$FAIL" = "0" ] && [ "$PASS" = "5" ] \
    && echo "PASS Test 12: 5/5 status values produced 5 distinct exit codes" \
    || { echo "FAIL Test 12: $PASS pass, $FAIL fail"; exit 1; }
```

**Iter-6 note on Test 12 reliability under `set -e`**: the loop body MUST use the `|| actual=$?` form. If you write the apparently equivalent `~/scripts/exec-state.sh check "$id" >/dev/null 2>&1; actual=$?`, then under `set -euo pipefail` the test process dies on the first non-zero exit (e.g. when iterating into `ITER5-COMPLETED` which returns 1) BEFORE the `actual=$?` assignment, and the entire test wave terminates with no FAIL line — a false-green by silent exit. Confirmed empirically 2026-05-22 (see iteration-6 section below).

Expected output (order may vary because bash associative array iteration is unordered):

```
PASS Test 12: T-1 → exit 0 (expected 0)
PASS Test 12: ITER5-COMPLETED → exit 1 (expected 1)
PASS Test 12: ITER5-UNKNOWN → exit 2 (expected 2)
PASS Test 12: ITER5-FAILED → exit 3 (expected 3)
PASS Test 12: ITER5-IN-PROGRESS → exit 4 (expected 4)
PASS Test 12: 5/5 status values produced 5 distinct exit codes
```

#### Test 13 — failed spec does NOT silently skip via iter-2 guard regression

```bash
~/scripts/exec-state.sh init
~/scripts/exec-state.sh start "T-1"
~/scripts/exec-state.sh fail  "T-1" "synthetic failure for regression test"

# Run the iter-6 integration pattern under the SAME strict-mode flags the
# real orchestrator uses. `set -euo pipefail` inside the inner `bash -c`
# is mandatory: without it the test would also pass against the iter-5
# broken pattern (because `bash -c` body does NOT inherit `set -e` from
# the parent shell), giving a false-green. The `|| SPEC_CODE=$?` form is
# what we're empirically asserting survives.
EC=0
ACTUAL=$(
    bash -c '
        set -euo pipefail
        SPEC_CODE=0
        ~/scripts/exec-state.sh check "T-1" || SPEC_CODE=$?
        case ${SPEC_CODE} in
            0) echo "RUN_REQUESTED";       exit 0 ;;
            1) echo "SKIP_COMPLETED";      exit 0 ;;
            2) echo "FATAL_UNKNOWN";       exit 2 ;;
            3) echo "FATAL_FAILED";        exit 3 ;;
            4) echo "FATAL_IN_PROGRESS";   exit 4 ;;
            *) echo "FATAL_CONTRACT_DRIFT"; exit 5 ;;
        esac
    '
) || EC=$?
# Iter-6: `|| EC=$?` short-circuits the OUTER `set -euo pipefail`. The
# inner `bash -c` exits with the spec's check-code (3 for FATAL_FAILED),
# which under outer set -e would kill the test runner BEFORE the EC
# capture. Captured EC must equal 3 for the assertion below.

[ "$ACTUAL" = "FATAL_FAILED" ] && [ "$EC" = "3" ] \
    && echo "PASS Test 13: failed spec correctly halts (exit 3, not silent exit 0) under set -euo pipefail" \
    || { echo "FAIL Test 13: iter-2/iter-5 regression — got '$ACTUAL' exit $EC"; exit 1; }
```

The iteration-2 contract would have made this test produce `SKIP_COMPLETED` + exit 0 (the silent fail mask). The iteration-5 bare `check; case $?` pattern would have died at the `check` invocation under `set -euo pipefail` and `ACTUAL` would be empty with `EC=3` (test FAIL message "got '' exit 3"). Iter-6 must produce `FATAL_FAILED` + exit 3.

#### Test 14 — in_progress spec halts the orchestrator (race detection)

```bash
~/scripts/exec-state.sh init
~/scripts/exec-state.sh start "T-1"   # leaves T-1 in `in_progress`

# Iter-6: assert the exit-code capture survives `set -euo pipefail`. The
# bare `check; EC=$?` form (iter-5) would kill the test BEFORE EC is set
# because the semicolon does not move the bare command into a tolerated
# context for set -e. The `|| EC=$?` form does.
bash -c '
    set -euo pipefail
    EC=0
    ~/scripts/exec-state.sh check "T-1" || EC=$?
    [ "$EC" = "4" ] \
        && echo "PASS Test 14: in_progress → exit 4 (race halt) under set -euo pipefail" \
        || { echo "FAIL Test 14: expected 4, got $EC"; exit 1; }
'
```

## Fix Iteration 6 (CRITICAL): Step 3 pattern under set -e — `|| SPEC_CODE=$?` short-circuit

> **Status**: SUPERSEDES iteration-5 "Step 3 integration pattern" only. All other contracts from iterations 1+2+5 (`check` exit semantics, flock-on-mutations, `flock -w 10` timeout, 31-spec init heredoc, G1 halt sentinel, `acquire_lock` exit-3 alignment) remain unchanged.

### What was broken in iteration-5

Iteration-5 introduced the explicit `case $?` dispatch pattern at "Step 3 integration pattern (iter-5)" with this block:

```bash
# ITER-5 BUG B5-NEW-1 — DO NOT COPY
~/scripts/exec-state.sh check "$SPEC_ID"   # bare invocation
case $? in
    0) ... ;;
    1) ... ;;
    2) ... ;;
    3) ... ;;
    4) ... ;;
esac
```

The block looks correct in isolation but is **fatal under `set -euo pipefail`**, which every production wave-executor uses (see G3 / `apps/cell/scripts/launch_cell.sh` / `~/scripts/exec-state.sh` itself). `set -e` kills the script the moment a "checked" command returns non-zero. Bash's POSIX rules define a "checked" command as anything NOT in one of four tolerated positions: the LHS of `&&`/`||`, the controlling-expression of `if`/`while`/`until`, an inverted command (`! cmd`), or a pipeline element with `-o pipefail` disabled. A bare command followed by `;` or a newline IS checked.

Empirical reproduction (2026-05-22, this iteration's audit):

```bash
$ cat > /tmp/repro.sh <<'EOF'
#!/bin/bash
set -euo pipefail
fake_check() { return 3; }
fake_check "spec_x"          # bare call, exit 3 — set -e kills HERE
case $? in
    3) echo "REACHED" ;;       # never executed
esac
EOF
$ bash /tmp/repro.sh
$ echo $?                       # exits 3 with no output; case never runs
3
```

So for every wave-executor spec whose status is `completed` (exit 1), `unknown` (exit 2), `failed` (exit 3), or `in_progress` (exit 4), the iter-5 pattern silently kills the executor at the `check` call. The five-state dispatch never sees codes 1/2/3/4 — meaning:

- A `completed` spec does NOT "skip and continue" (iter-2 idempotency contract broken — wave-executor dies with exit 1).
- A `failed` spec does NOT halt loudly with a diagnostic line (iter-5's whole reason for existing — the executor dies with exit 3 but no `>&2` message).
- An `in_progress` spec does NOT report race-detection.
- An `unknown` spec does NOT report schema-mismatch.

The iter-5 pattern is functionally equivalent to "let the script die on any non-zero exit and hope the operator reads the launchd error log". It defeats the purpose of having five distinct exit codes.

### Fix — capture the exit code via `||` short-circuit

Replace `check "$SPEC_ID"` followed by `case $?` with:

```bash
SPEC_CODE=0
~/scripts/exec-state.sh check "$SPEC_ID" || SPEC_CODE=$?
case ${SPEC_CODE} in
    0) ... ;;
    1) ... ;;
    2) ... ;;
    3) ... ;;
    4) ... ;;
    *) ... ;;
esac
```

Why this works under `set -euo pipefail`:

1. **`cmd || VAR=$?` is a tolerated `||` list.** POSIX §2.11 specifies that `set -e` does NOT abort on a non-zero exit in an `&&`/`||` list — only the FINAL command in the list's exit code is checked, and here the final command is the assignment `VAR=$?` (always exits 0).
2. **The exit code is captured into `SPEC_CODE`** because `$?` inside the `||` RHS still refers to the LHS's exit code (bash retains the original $? for the duration of the list evaluation).
3. **`SPEC_CODE=0` pre-init guards the `set -u` flag**: if `check` exits 0, the `||` branch is not taken and `SPEC_CODE` would otherwise be undefined → `set -u` aborts on `${SPEC_CODE}`. Pre-init eliminates that risk.
4. **`case ${SPEC_CODE}` instead of `case $?`**: at the point of dispatch, `$?` is the exit code of the most recent command which is now the `SPEC_CODE=$?` assignment (always 0) or the `SPEC_CODE=0` pre-init (also 0). Reading the captured variable is the only reliable form.

### Why not `if check; then …; else SPEC_CODE=$?; case … esac; fi` (Variant B)

The `if/elif` form (Variant B in the iter-6 task brief) is equally correct under `set -e` and was considered. Variant A (`|| SPEC_CODE=$?`) was preferred for three reasons:

1. **Symmetric handling of all six branches** (0 plus 1/2/3/4 plus default). The `if/elif` form forces an asymmetry: the 0-branch lives inside the `if` body, the 1-4 branches inside the `else` `case`. Two-tier nesting is harder to read and harder to extend (a future iter-7 adding exit code 5 has to choose whether to put it inside the `if` body or the `case`).
2. **Cheaper to lift into a helper function.** A future refactor where multiple specs are checked in a loop benefits from `SPEC_CODE=$(check_capture "$id")` semantics, which compose naturally with `||`. The `if` form does not.
3. **Closer to the iter-5 visual shape**, so the diff is minimal and operators reading the spec see exactly where the bug was.

Both variants pass the empirical test below. Pick Variant A unless local style enforces otherwise.

### Empirical verification (proof, NOT speculation)

Run this **before** changing any callsite. The output must be IDENTICAL to the lines marked `EXPECTED`:

```bash
$ cat > /tmp/test_iter6_pattern.sh <<'EOF'
#!/bin/bash
set -euo pipefail
fake_check() { return 3; }
SPEC_CODE=0
fake_check "spec_x" || SPEC_CODE=$?
echo "after check, SPEC_CODE=${SPEC_CODE}"
case ${SPEC_CODE} in
    3) echo "HALT BRANCH REACHED — correct"; exit 0 ;;
    *) echo "WRONG BRANCH"; exit 1 ;;
esac
EOF
$ bash /tmp/test_iter6_pattern.sh
after check, SPEC_CODE=3       # EXPECTED
HALT BRANCH REACHED — correct  # EXPECTED
$ echo $?
0                              # EXPECTED
```

A full five-code sweep (every `check` return value, asserting the right branch fires):

```bash
$ cat > /tmp/test_iter6_all_codes.sh <<'EOF'
#!/bin/bash
set -euo pipefail
for ec in 0 1 2 3 4; do
    SPEC_CODE=0
    fake_check() { return $1; }
    fake_check $ec || SPEC_CODE=$?
    case ${SPEC_CODE} in
        0) branch="run" ;;
        1) branch="skip-completed" ;;
        2) branch="fatal-unknown" ;;
        3) branch="fatal-failed" ;;
        4) branch="fatal-in-progress" ;;
        *) branch="WRONG" ;;
    esac
    echo "ec=$ec → SPEC_CODE=${SPEC_CODE} branch=$branch"
done
echo "ALL 5 CODES HANDLED — survived set -e"
EOF
$ bash /tmp/test_iter6_all_codes.sh
ec=0 → SPEC_CODE=0 branch=run
ec=1 → SPEC_CODE=1 branch=skip-completed
ec=2 → SPEC_CODE=2 branch=fatal-unknown
ec=3 → SPEC_CODE=3 branch=fatal-failed
ec=4 → SPEC_CODE=4 branch=fatal-in-progress
ALL 5 CODES HANDLED — survived set -e
```

Iter-5's broken pattern reproduced for contrast — note the missing `HALT BRANCH REACHED` line:

```bash
$ cat > /tmp/test_iter5_broken.sh <<'EOF'
#!/bin/bash
set -euo pipefail
fake_check() { return 3; }
fake_check "spec_x"           # bare call — dies HERE under set -e
case $? in
    3) echo "HALT BRANCH REACHED"; exit 0 ;;
    *) echo "WRONG BRANCH"; exit 1 ;;
esac
EOF
$ bash /tmp/test_iter5_broken.sh
$ echo $?
3                              # exited at the `check` call, case never ran
```

### Where the fix applies

1. **`Step 3 integration pattern (iter-5)`** above (line ~953) — the canonical block operators copy into their wave-executors. Already patched to Variant A.
2. **Test 12** — the `for id in EXPECTED` loop body was `check; actual=$?` (semicolon, NOT `||`). Same bug class: dies on the first iteration that returns non-zero. Patched to `... || actual=$?`.
3. **Test 13** — the inner `bash -c` block did NOT set `set -euo pipefail` itself, so technically the iter-5 pattern "worked" there. But the test was meant to PROVE that the production pattern (which DOES use strict mode) is safe. Patched to enable `set -euo pipefail` AND use `|| SPEC_CODE=$?`. Now the test legitimately exercises the strict-mode contract.
4. **Test 14** — `check "T-1"; EC=$?` had the same semicolon trap as Test 12. Patched.

Operators with already-running wave-executors written against the iter-5 broken pattern: re-derive the new block from this section and ship a single-commit patch. There is no migration needed — the change is at the call-site only, the `~/scripts/exec-state.sh check` subcommand is unchanged.

### Honest admission

The iter-5 author (Worker B5) wrote the bug into both the canonical Step 3 block AND the three new tests (12-14). The unit-test framework did not catch it because every test inside `bash -c '...'` lost the parent `set -e` context, and Test 12's loop happened to exit 1 first → silent test-runner termination → appeared as "no FAIL line" → false-green. The 4-LLM devils-advocate panel detected the bug by running the iter-5 spec against a real bash interpreter with strict-mode flags, which is exactly the gap the iter-5 author should have closed before declaring the spec ready. Iter-6 ships with an explicit "run this `/tmp/test_iter6_pattern.sh` script before committing" gate in the verification section above — future iterations should adopt the same posture.

### Migration note for iteration-2 manifests + callsites

The iter-2 → iter-5 → iter-6 transition is **schema-compatible** (the manifest JSON shape is unchanged across all three; only the `check` exit-code contract and the call-site dispatch idiom change). No manifest file rewrite is needed. The migration is purely:

1. **Update `~/scripts/exec-state.sh`**: replace the `check` `case` block with the five-state version above (this part is the iter-5 contract; unchanged in iter-6).
2. **Update every wave executor** (Step 3 integration callsites): replace `if ! check; then echo Skip; exit 0; fi` (iter-2) OR `check; case $?` (iter-5 broken) with the explicit `|| SPEC_CODE=$?` block (iter-6).
3. **Update Test 10** (iter-2 "completed → exit 1" regression test) — it remains valid under iter-5/iter-6 because `completed` is still exit 1 (no change). No edit needed.
4. **Audit existing manifest** for any spec currently in `status=failed`. Before re-running the wave, the operator must triage each one (read `.specs[id].error`, decide retry vs accept). Iter-5/iter-6 will halt loudly on any unresolved `failed` entry — that is the intended behavior, not a regression.

G3 rollback remains identical — `~/.claude/state/` is snapshotted as a whole; iter-6 manifests roll back the same way iter-2/iter-5 ones did.
