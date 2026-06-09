#!/bin/bash
# review_gate_run.sh — Pro-side autonomous tri-LLM review gate (REVIEW-ONLY).
#
# Observes open agent/* PRs and posts a 3-LLM review COMMENT on each PR whose
# current head SHA has not yet been reviewed. It NEVER labels, approves, or
# merges — merging stays the operator's decision (Legge 5). The auto-merge half
# is a separate, deferred phase (GitHub App check-run; see the deferred spec).
#
# Design (modeled on the FASE-0 governance wrappers — same conventions):
#   - StartInterval cron via com.nuzantara.review-gate.plist (KeepAlive false).
#   - NO secrets in the plist. `gh` uses its own Pro auth; the DeepSeek key for
#     the panel is sourced by codex_tri_llm_review.py itself (.env.master /
#     .nuzantara-secrets.env). This wrapper sources nothing secret.
#   - fcntl.flock (a single non-overlapping run at a time — three LLM calls take
#     ~2min; macOS /bin/bash 3.2 has no GNU flock, so we use a Python guard).
#   - Idempotency per (pr, head_sha): a state file records the last reviewed SHA
#     per PR; a PR whose head still matches is SKIPPED (no duplicate comment).
#   - Air-gap: the untrusted branch is NEVER checked out on the Pro — the script
#     fetches the diff via `gh pr diff` only (no post-checkout hooks / .env load).
#
# Usage:
#   bash scripts/review_gate_run.sh            # one sweep over open agent/* PRs
#   REVIEW_GATE_DRY_RUN=1 bash scripts/review_gate_run.sh   # log, do not comment
#
# Falsifiable acceptance (the wrapper's own gates):
#   - posts a comment carrying the 3-LLM verdict on a real agent/* PR;
#   - idempotent per head-SHA (a second sweep on an unchanged PR = no 2nd comment);
#   - fail-closed on a truncated diff (delegated to the script's diff_complete);
#   - flock prevents two overlapping sweeps;
#   - zero secrets in the plist.

set -uo pipefail

REPO="Balizero1987/Teman2"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$HOME/.agent/decisions/state"
STATE_FILE="$STATE_DIR/review_gate_seen.json"
LOCK_FILE="${TMPDIR:-/tmp}/review-gate.lock"
LOG_PREFIX="[review-gate]"
SCRIPT="$REPO_ROOT/scripts/codex_tri_llm_review.py"
DRY_RUN="${REVIEW_GATE_DRY_RUN:-0}"
# Cap reviews per sweep so a cold-start backlog (N open agent/* PRs × 3 LLMs)
# does not stampede quota/cost in one tick. The rest are picked up next sweep.
# Set 0 for unlimited. Steady-state has ~0-1 new SHAs/sweep so this only bites
# on the first armed run.
MAX_PER_SWEEP="${REVIEW_GATE_MAX_PER_SWEEP:-3}"

mkdir -p "$STATE_DIR"

log() { echo "$LOG_PREFIX $*"; }

# ── single-run lock (fcntl.flock via Python — robust, releases on exit) ───────
# Re-exec self under a held lock. If the lock is busy, exit 0 (another sweep is
# already running — this is a cron, not a one-shot, so skipping is correct).
if [[ "${_REVIEW_GATE_LOCKED:-}" != "1" ]]; then
    exec /usr/bin/python3 - "$LOCK_FILE" "$0" "$@" <<'PYLOCK'
import fcntl, os, sys
lock_path, script, *rest = sys.argv[1], sys.argv[2], *sys.argv[3:]
fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print("[review-gate] another sweep holds the lock — skipping", flush=True)
    sys.exit(0)
env = dict(os.environ, _REVIEW_GATE_LOCKED="1")
os.execve("/bin/bash", ["/bin/bash", script, *rest], env)
PYLOCK
fi

# ── from here on we hold the lock ─────────────────────────────────────────────

if [[ ! -f "$SCRIPT" ]]; then
    log "ERROR: review script not found at $SCRIPT — refusing to no-op (W64)"
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    log "ERROR: gh CLI not found on PATH"
    exit 1
fi

# Ensure the state file is valid JSON (init to {} once).
if [[ ! -s "$STATE_FILE" ]] || ! /usr/bin/python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$STATE_FILE" 2>/dev/null; then
    echo '{}' > "$STATE_FILE"
fi

# ── enumerate open agent/* PRs (number + current head SHA) ────────────────────
# `--search 'head:agent/'` filters to broker-shaped branches; one line per PR:
#   "<number>\t<headRefOid>".
PRS="$(gh pr list --repo "$REPO" --state open --search 'head:agent/' \
        --json number,headRefOid --jq '.[] | "\(.number)\t\(.headRefOid)"' 2>/dev/null)"

if [[ -z "$PRS" ]]; then
    log "no open agent/* PRs — nothing to review"
    exit 0
fi

reviewed=0
skipped=0
failed=0

while IFS=$'\t' read -r pr head_sha; do
    [[ -z "$pr" ]] && continue

    # Idempotency: skip if this PR's current head SHA was already reviewed.
    seen_sha="$(/usr/bin/python3 -c \
        "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" \
        "$STATE_FILE" "$pr" 2>/dev/null)"
    if [[ "$seen_sha" == "$head_sha" ]]; then
        log "PR #$pr @ ${head_sha:0:8} already reviewed — skip"
        skipped=$((skipped + 1))
        continue
    fi

    # Per-sweep cap (cold-start backlog guard). Counts only PRs that would be
    # reviewed this sweep — skipped (already-seen) PRs don't consume the budget.
    if [[ "$MAX_PER_SWEEP" -gt 0 && "$reviewed" -ge "$MAX_PER_SWEEP" ]]; then
        log "per-sweep cap ($MAX_PER_SWEEP) reached — deferring PR #$pr to next sweep"
        skipped=$((skipped + 1))
        continue
    fi

    log "reviewing PR #$pr @ ${head_sha:0:8} ..."
    if [[ "$DRY_RUN" == "1" ]]; then
        log "DRY_RUN — would run: $SCRIPT --pr $pr --comment"
        reviewed=$((reviewed + 1))
        continue
    fi

    # Run the panel and post the comment. The script fail-closes on a truncated
    # diff (diff_complete=False → inconclusive). NEVER checkout the branch.
    if /usr/bin/python3 "$SCRIPT" --pr "$pr" --comment >/dev/null 2>>"$HOME/logs/review-gate.err.log"; then
        rc=0
    else
        rc=$?
    fi

    # Record the head SHA as reviewed (any terminal verdict — green/yellow/red/
    # inconclusive — counts as "reviewed this SHA": we posted a comment, and a
    # re-run would just re-post the same. A NEW push changes head_sha → re-review).
    # rc==3 is inconclusive (env-down / truncated): we still posted a comment, so
    # mark it seen to avoid spamming; the next PUSH re-triggers, the next SWEEP won't.
    /usr/bin/python3 - "$STATE_FILE" "$pr" "$head_sha" <<'PYSAVE'
import json, sys
path, pr, sha = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.load(open(path))
except Exception:
    d = {}
d[pr] = sha
json.dump(d, open(path, "w"), indent=2)
PYSAVE

    if [[ "$rc" -le 3 ]]; then
        log "PR #$pr reviewed (rc=$rc)"
        reviewed=$((reviewed + 1))
    else
        log "PR #$pr review FAILED (rc=$rc) — see ~/logs/review-gate.err.log"
        failed=$((failed + 1))
    fi
done <<< "$PRS"

log "sweep done: reviewed=$reviewed skipped=$skipped failed=$failed"
exit 0
