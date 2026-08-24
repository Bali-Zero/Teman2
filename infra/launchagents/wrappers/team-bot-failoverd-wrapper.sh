#!/bin/sh
# team-bot-failoverd-wrapper.sh — launchd payload for
# com.balizero.team-bot-failoverd (F9, lane B5).
#
# Runs as a dedicated login-less user on Pro ONLY (F9 §4.2: "Pro is the
# only node holding the Meta WABA-management token" — a Mini copy of
# this daemon would be a second writer against the same CAS record and
# a structural split-brain risk, not a redundancy feature). Modeled
# directly on infra/launchagents/wrappers/wa-codex-broker-wrapper.sh —
# same shape, same reasoning, different payload:
#
# - `exec` into the daemon's REAL blocking loop under KeepAlive (scar
#   family #7: launchd monitors the python process itself, no restart
#   cycling on a one-shot exit).
# - Guarded env-file source — never a bare `. file || true` under
#   errexit (W108: sh treats a failed `.` as a special-builtin exit;
#   the guard must come BEFORE the source, as an if).
# - Absolute interpreter path (W108: a PATH-resolved python is the
#   failure mode the daemon would then have to report on).
# - The env file carries TEAM_BOT_WABA_ACCESS_TOKEN and
#   TEAM_BOT_FAILOVER_DATABASE_URL: 0600, never echoed, never on argv
#   (superscar family #4 / W115).
#
# LIVE copy path is declared by whatever provisioning script installs
# this (scripts/provision_team_bot_failoverd.sh, not yet run — this is
# the SOURCE this repo tracks; the deployed copy must be declared in
# infra/home-fork/declared-pairs.json once provisioning actually
# happens, per superscar family #1 — a change here does not reach a
# running daemon until re-provisioned).

set -u

HOME_DIR="/Users/team-bot-failoverd"
RUNTIME_DIR="/usr/local/lib/team-bot-failoverd"
ENV_FILE="$HOME_DIR/.team-bot-failoverd.env"
VENV_PY="$RUNTIME_DIR/.venv/bin/python3"
TAG="team-bot-failoverd-wrapper"
ORGAN_ID="pro.team_bot_failoverd"
SIDECAR_DIR="$HOME_DIR/.organism/last_seen"

# G2_heartbeat — sidecar at start and on every refusal exit, same
# pattern as wa-codex-broker-wrapper.sh: the RUNNING daemon's own
# liveness ground truth is its structured log output (one INFO line per
# tick once TEAM_BOT_FAILOVER_AUTO_ENABLED is armed; a "not wired yet"
# WARNING line otherwise), not this sidecar file — it exists only so a
# refusal-to-start exit is distinguishable from never-having-run.
heartbeat() { # $1 status, $2 note
    mkdir -p "$SIDECAR_DIR" 2>/dev/null || return 0
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$SIDECAR_DIR/$ORGAN_ID.json"
}

if [ ! -f "$ENV_FILE" ]; then
    echo "$TAG: env file missing: $ENV_FILE - refusing to start (run provisioning)" >&2
    heartbeat "refused" "env file missing"
    exit 78 # EX_CONFIG
fi
if grep -q "__FILL_ME__" "$ENV_FILE"; then
    echo "$TAG: env file still carries __FILL_ME__ placeholders - refusing to start" >&2
    heartbeat "refused" "env placeholders unfilled"
    exit 78
fi

set -a
. "$ENV_FILE"
set +a

# G5_kill_switch — operator stop without uninstall. Deliberately a
# SEPARATE variable from TEAM_BOT_FAILOVER_AUTO_ENABLED: this one stops
# the PROCESS (no health polling, no logging, nothing); that one gates
# whether a running process is allowed to actually PROMOTE. A daemon
# that is merely disabled-from-promoting should still keep running and
# logging shadow decisions (F11) — only this switch should stop it
# outright. Clean exit 0 stays DOWN under KeepAlive.SuccessfulExit=false.
if [ "${TEAM_BOT_FAILOVERD_PROCESS_ENABLED:-true}" = "false" ]; then
    echo "$TAG: TEAM_BOT_FAILOVERD_PROCESS_ENABLED=false - kill switch active, exiting clean" >&2
    heartbeat "disabled" "kill switch"
    exit 0
fi

if [ ! -x "$VENV_PY" ]; then
    echo "$TAG: venv python missing or not executable: $VENV_PY - run provisioning" >&2
    heartbeat "refused" "venv python missing"
    exit 78
fi

cd "$RUNTIME_DIR" || { heartbeat "refused" "cd failed"; exit 78; }
export PYTHONPATH="$RUNTIME_DIR"

heartbeat "starting" "exec daemon"
exec "$VENV_PY" -m backend.services.team_bot_ingress.failoverd
