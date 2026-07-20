#!/usr/bin/env bash
# fly-pg-proxy-wrapper.sh — keep `fly proxy 15432:5432` alive for nuzantara-postgres.
#
# Why this wrapper exists:
#   fly CLI v0.4.49 (build 2026-05-07) regressed: it no longer reads
#   `access_token:` from ~/.fly/config.yml. `fly auth whoami` and `fly proxy`
#   both fail with "no access token available" even though the token in
#   config.yml is API-valid. This wrapper extracts the token and injects it
#   via FLY_ACCESS_TOKEN so it does not appear in process argv.
#
# Used by: LaunchAgent com.balizero.wr2.pg-proxy (KeepAlive=true)
# Logs:    ~/.openclaw/workspace/logs/war-room-v2/pg-proxy.{log,error.log}
#          (plist StandardOut/ErrorPath — wrapper writes to stdout/stderr)

set -uo pipefail

FLY_BIN="/opt/homebrew/bin/fly"
CONFIG="${HOME}/.fly/config.yml"
APP="nuzantara-postgres"
LOCAL_PORT=15432
REMOTE_PORT=5432

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [[ ! -x "$FLY_BIN" ]]; then
  echo "[$(ts)] FATAL: fly binary not found at $FLY_BIN" >&2
  sleep 30  # slow the KeepAlive respin
  exit 2
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "[$(ts)] FATAL: fly config not found at $CONFIG — run 'fly auth login'" >&2
  sleep 30
  exit 2
fi

# Extract access_token (first line, strip 'access_token: ' prefix).
TOKEN=$(grep '^access_token:' "$CONFIG" | head -1 | sed 's/^access_token: *//')
if [[ -z "$TOKEN" ]]; then
  echo "[$(ts)] FATAL: no access_token in $CONFIG" >&2
  sleep 30
  exit 2
fi

# Validate the token before binding the port — fail fast with a clear message
# instead of letting `fly proxy` half-start.
if ! FLY_ACCESS_TOKEN="$TOKEN" "$FLY_BIN" auth whoami >/dev/null 2>&1; then
  echo "[$(ts)] FATAL: token in $CONFIG rejected by Fly API — re-run 'fly auth login'" >&2
  sleep 60  # token rotation needs human action; don't hammer
  exit 3
fi

echo "[$(ts)] token OK — starting fly proxy ${LOCAL_PORT}:${REMOTE_PORT} -a ${APP}"

# Prefix every child output line with a timestamp and route to STDERR so the
# plist's StandardErrorPath captures correlation-friendly logs.
#
# Why Perl, not awk:
#   macOS BSD /usr/bin/awk does NOT support strftime() (Codex panel 2026-05-23
#   empirical: "/usr/bin/awk: calling undefined function strftime"). gawk and ts
#   are not installed on this host. /usr/bin/perl ships with macOS and POSIX
#   core module is always available.
#
# Why no `exec` before the pipeline:
#   `exec foo | bar` is bash undefined behavior (Gemini panel 2026-05-23 — needs
#   subshell for pipeline). KeepAlive=true + ThrottleInterval=30 in the plist
#   handle respawn cleanly when the wrapper exits with the child's status.
#
# Why STDERR not STDOUT in the prefixer:
#   `2>&1 | prefix` redirects child stderr into the pipeline; if the prefixer
#   prints to STDOUT, errors silently migrate from pg-proxy.error.log to
#   pg-proxy.log. Writing to STDERR preserves the existing log-stream split.
prefix_child_output() {
  /usr/bin/perl -MPOSIX=strftime -ne '
    $| = 1;
    print STDERR "[" . strftime("%Y-%m-%d %H:%M:%S", localtime) . "] " . $_;
  '
}

export FLY_ACCESS_TOKEN="$TOKEN"
"$FLY_BIN" proxy "${LOCAL_PORT}:${REMOTE_PORT}" -a "$APP" 2>&1 | prefix_child_output
status=${PIPESTATUS[0]}
echo "[$(ts)] fly proxy exited status=${status}" >&2
exit "$status"
