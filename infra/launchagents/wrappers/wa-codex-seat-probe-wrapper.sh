#!/bin/sh
# wa-codex-seat-probe-wrapper.sh — launchd payload for
# com.balizero.wa-codex-seat-probe (S3, Piece A of the seat sentinel pair).
#
# Runs as the login-less user `zantara-codex` on Pro, SAME identity as
# com.balizero.wa-codex-broker (spec §4.1,
# research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md). The
# LIVE copy is /usr/local/libexec/wa-codex-seat-probe-wrapper.sh —
# ROOT-OWNED, outside any user-writable $HOME, same fw-guard precedent
# (2026-08-14) as the broker wrapper: the process runs AS zantara-codex, so
# a compromised zantara-codex identity gains no privilege by editing a
# home-dir wrapper, but a root-owned payload denies it PERSISTENCE. Placed
# by scripts/provision_zantara_codex.sh; the pair is declared in
# infra/home-fork/declared-pairs.json (superscar #1 — re-run provisioning
# after changing this file, the merge alone leaves the live copy stale).
#
# Shape notes (scar-family antidotes, load-bearing — same discipline as
# wa-codex-broker-wrapper.sh):
# - `exec` into the ONE-SHOT probe under NO KeepAlive (family #7: this is a
#   cron-shaped payload, not a long-running server — StartInterval owns the
#   cadence, launchd must never restart-storm a one-shot that exits 0/2).
# - Guarded env-file source — never a bare `. file || true` under errexit
#   (W108: sh treats a failed `.` as a special-builtin exit; the guard
#   must come BEFORE the source, as an if).
# - Absolute interpreter path (W108: a PATH-resolved python is the failure
#   mode the probe would then have to report on).
# - The env file may still carry WA_BROKER_KEY (this probe never reads it,
#   but the file is shared with the broker) — 0600, never echoed, never on
#   argv (family #4 / W115). This probe only consumes WA_CODEX_BIN and
#   CODEX_HOME from it.

set -u

HOME_DIR="/Users/zantara-codex"
RUNTIME_DIR="/usr/local/lib/wa-codex-broker"
ENV_FILE="$HOME_DIR/.wa-codex-broker.env"
VENV_PY="$RUNTIME_DIR/.venv/bin/python3"
PROBE_SCRIPT="$RUNTIME_DIR/seat_probe.py"
TAG="wa-codex-seat-probe-wrapper"

if [ ! -f "$ENV_FILE" ]; then
    echo "$TAG: env file missing: $ENV_FILE - refusing to run (run provisioning)" >&2
    exit 78 # EX_CONFIG
fi

# Extract ONLY the two keys this probe consumes. A `set -a` source would
# hand WA_BROKER_KEY to the probe and, through it, into the `codex`
# subprocess environment — a secret delivered to a process with no use for
# it (scar 2026-08-18: dispatching an external CLI delivers the ENVIRONMENT,
# not just the prompt). Each extraction sources in a SUBSHELL so nothing
# else leaks into this process; a failed source yields an empty value, and
# empty degrades safely (binary falls back to PATH, CODEX_HOME to $HOME).
WA_CODEX_BIN="$(. "$ENV_FILE" >/dev/null 2>&1; printf '%s' "${WA_CODEX_BIN:-}")"
CODEX_HOME="$(. "$ENV_FILE" >/dev/null 2>&1; printf '%s' "${CODEX_HOME:-}")"
# Export only NON-EMPTY values (Kimi r1 m7): an exported empty string is
# NOT "unset" to the child — codex would receive CODEX_HOME= verbatim and
# may treat it as a literal empty path instead of falling back to $HOME.
# unset + absent key is the only shape that truly degrades to the default.
if [ -n "$WA_CODEX_BIN" ]; then export WA_CODEX_BIN; else unset WA_CODEX_BIN; fi
if [ -n "$CODEX_HOME" ]; then export CODEX_HOME; else unset CODEX_HOME; fi

if [ ! -x "$VENV_PY" ]; then
    echo "$TAG: venv python missing or not executable: $VENV_PY - run provisioning" >&2
    exit 78
fi
if [ ! -f "$PROBE_SCRIPT" ]; then
    echo "$TAG: probe script missing: $PROBE_SCRIPT - run provisioning" >&2
    exit 78
fi

cd "$RUNTIME_DIR" || exit 78
export PYTHONPATH="$RUNTIME_DIR"

exec "$VENV_PY" "$PROBE_SCRIPT"
