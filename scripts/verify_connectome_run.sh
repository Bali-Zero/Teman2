#!/bin/bash
# verify_connectome_run.sh — cron wrapper for scripts/verify_connectome.py
#
# Runs the connectome drift-verifier against docs/connectome/edges/*.yaml,
# writes an alive-signal state JSON (deadman-family convention), and sends
# ONE Telegram alert when any edge REGRESSED (declared healthy, probe fails).
#
# Runtime homes (REPO_ROOT, overridable via env):
#   Pro : ~/nuzantara-deploy   (hourly-synced to origin/main — W71 rule)
#   M5  : ~/nuzantara          (main checkout; NEVER mutated here)
#
# Exit codes: 0 = no REGRESSED · 1 = REGRESSED (alert sent) · 2 = setup error.
# /bin/bash 3.2-compatible (macOS): no declare -A, no mapfile.
set -uo pipefail

LOG_PREFIX="[verify-connectome]"
STATE_DIR="$HOME/.agent/decisions/state"
STATE_FILE="$STATE_DIR/verify_connectome.json"
mkdir -p "$STATE_DIR"

# ── resolve repo root per machine ────────────────────────────────────────────
if [[ -z "${REPO_ROOT:-}" ]]; then
    if [[ "$(whoami)" == "balizero" ]]; then
        REPO_ROOT="$HOME/nuzantara"
    else
        REPO_ROOT="$HOME/nuzantara-deploy"
    fi
fi
if [[ ! -d "$REPO_ROOT/docs/connectome/edges" ]]; then
    echo "$LOG_PREFIX ERROR: edges dir missing under $REPO_ROOT (wrong branch or stale checkout?)" >&2
    exit 2
fi

# Read-only staleness note — never pull/checkout from a cron (scar:
# evolver/deploy-puller shared-worktree family).
BRANCH="$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo '?')"
if [[ "$BRANCH" != "main" && "$BRANCH" != "deploy/main" ]]; then
    echo "$LOG_PREFIX WARN: $REPO_ROOT on branch '$BRANCH' (not main) — verifier may be stale" >&2
fi

# Being ON main says nothing about being CURRENT with it, and that gap is not
# hypothetical: on 2026-07-29 the M5 checkout sat 248 commits behind while the
# census fix that cleared 5 false REGRESSED was already merged — so this cron
# would have kept reporting cured edges as regressions, with no line anywhere
# saying the map was old. The branch check above could never catch it: the
# branch was main the whole time. Read the DISTANCE, not the name.
#
# Report-only by construction. It never fetches (a cron that reaches the network
# to decide its own freshness is a new failure mode) and never pulls (the scar
# above). So the count is measured against the last-known origin/main in the
# local object store, which is itself a lower bound — say so rather than imply
# precision the measurement does not have.
#
# FRESHNESS_NOTE carries the same caveat to the ALERT. Writing it only to stderr
# put it in a log nobody reads, while the Telegram message — the one surface a
# human actually sees — stayed identical whether the census was today's or 258
# commits old: a confident P0 judged on an old map, with nothing saying so. The
# caveat has to travel with the verdict, not sit next to it.
BEHIND=""
FRESHNESS_NOTE=""
if [[ "$BRANCH" == "main" || "$BRANCH" == "deploy/main" ]]; then
    BEHIND="$(git -C "$REPO_ROOT" rev-list --count HEAD..origin/main 2>/dev/null || echo "")"
fi
if [[ -z "$BEHIND" ]]; then
    # No origin/main ref locally, or git failed. CANNOT-VERIFY is not CLEAN:
    # never let "I could not check" read as "nothing to report" (W106b).
    echo "$LOG_PREFIX WARN: could not measure checkout distance from origin/main — verdicts below are of UNKNOWN freshness" >&2
    FRESHNESS_NOTE="⚠️ checkout freshness UNKNOWN (could not compare to origin/main) — these verdicts may be stale
"
elif (( BEHIND > 0 )); then
    echo "$LOG_PREFIX WARN: $REPO_ROOT is >= $BEHIND commits behind origin/main — every verdict below is judged against THAT vintage of the census, not today's. Do NOT pull here (sibling-race): refresh the checkout from an interactive session on this machine." >&2
    FRESHNESS_NOTE="⚠️ judged on a census >= $BEHIND commits behind origin/main — a cured edge can still show here
"
fi

# ── python: backend venv first (PyYAML guaranteed), else system if yaml works ─
PYBIN="$REPO_ROOT/apps/backend-rag/.venv/bin/python3"
if [[ ! -x "$PYBIN" ]]; then
    if python3 -c "import yaml" >/dev/null 2>&1; then
        PYBIN="python3"
    else
        echo "$LOG_PREFIX ERROR: no venv at $PYBIN and system python3 lacks PyYAML" >&2
        exit 2
    fi
fi

# ── run the verifier ─────────────────────────────────────────────────────────
cd "$REPO_ROOT" || exit 2
OUT="$("$PYBIN" scripts/verify_connectome.py --json "$STATE_FILE" 2>&1)"
RC=$?
echo "$OUT"

if [[ $RC -eq 2 ]]; then
    echo "$LOG_PREFIX ERROR: verifier setup failure (exit 2)" >&2
    exit 2
fi

# ── alert on REGRESSED — through the ONE gateway, never a bare curl ──────────
#
# What the bare curl got wrong, beyond duplicating the token chain:
#   * it judged DELIVERY BY EXIT CODE. `curl -sS` (no --fail) exits 0 whenever
#     the server answers at all — including HTTP 200 carrying
#     {"ok":false,"description":"chat not found"} and 401 after a token
#     rotation. A REFUSED alert read as a delivered one; the alarm was, by
#     construction, unable to report its own silence (W104).
#   * a weekly guardian that stays red re-sends the identical message every
#     Monday until nobody reads any of them. tg_notify dedups by key.
# The gateway judges the reply body, spools an unsendable P0 as `p0_unsent` for
# the next digest, and is contracted never to fail its caller.
if [[ $RC -eq 1 ]]; then
    # `head` is a DISPLAY cap. Printing 10 of 23 with nothing saying so is how a
    # truncated list gets read as a complete one (W97) — so count first, cap
    # second, and declare the gap when there is one.
    REGRESSED_ALL="$(printf '%s\n' "$OUT" | grep -a 'REGRESSED ')"
    N_REGRESSED="$(printf '%s\n' "$REGRESSED_ALL" | grep -ac . || true)"
    SHOWN=10
    REGRESSED_LINES="$(printf '%s\n' "$REGRESSED_ALL" | head -"$SHOWN")"
    TRUNC_NOTE=""
    if (( N_REGRESSED > SHOWN )); then
        TRUNC_NOTE=" (showing $SHOWN of $N_REGRESSED)"
    fi

    MSG="connectome REGRESSED on $(hostname -s) $(date '+%Y-%m-%d %H:%M')${TRUNC_NOTE}
${FRESHNESS_NOTE}${REGRESSED_LINES}
state: ~/.agent/decisions/state/verify_connectome.json"

    # The alarm must not run on the interpreter whose breakage it may have to
    # report: PYBIN above can BE the venv under test, and resolving `python3`
    # from PATH after touching it is how an alarm inherits the failure mode of
    # the thing it reports (W108). Absolute, system-first, stdlib is all the
    # gateway needs.
    NOTIFY_PY=""
    for _cand in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if [[ -x "$_cand" ]]; then NOTIFY_PY="$_cand"; break; fi
    done
    NOTIFY="$REPO_ROOT/scripts/tg_notify.py"

    if [[ -z "$NOTIFY_PY" || ! -f "$NOTIFY" ]]; then
        # Armed to nothing is worse than unarmed if it is silent about it (W81):
        # say WHICH half is missing, and put the alert in the log at least.
        echo "$LOG_PREFIX WARN: REGRESSED but the alert gateway is unusable (python3=${NOTIFY_PY:-NOT-FOUND} gateway=$NOTIFY) — log-only below" >&2
        printf '%s\n' "$MSG" >&2
    else
        "$NOTIFY_PY" "$NOTIFY" --tier p0 --source verify-connectome \
            --dedup-key "connectome-regressed-$(hostname -s)" "$MSG" \
            || echo "$LOG_PREFIX WARN: tg_notify exited non-zero, which its contract forbids — treat the alert as possibly lost" >&2
    fi
fi

exit $RC
