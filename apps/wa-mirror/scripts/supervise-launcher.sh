#!/usr/bin/env bash
# Supervisor entrypoint for com.balizero.wa-mirror-launcher.
#
# The LaunchAgent calls this repo path; the single-account launcher operational
# scripts live under ~/scripts/wa-mirror-launcher. This stays a thin, versioned
# entrypoint that does NOT duplicate launcher logic.
#
# WHY THIS IS A LOOP (do not revert to `exec start-all.sh`):
# start-all.sh is a ONE-SHOT — it spawns the per-employee node bridges (nohup &)
# then exits 0. With the LaunchAgent's KeepAlive=true, an exec-passthrough made
# launchd cycle the job every ~ThrottleInterval seconds. Each cycle tore down
# the job's process group and SIGTERM-killed the nohup'd node bridges, so HEALTHY
# WhatsApp sessions died roughly every 22s -> endless reconnect storm
# (reconnect_attempt climbing into the hundreds). See memory
# discovery_wa_mirror_reconnect_storm_2026_06_06 and cicatrix W67.
#
# FIX: stay alive as a real supervisor. Run the launcher once, then re-run it on
# an interval. start-all.sh already skips accounts whose pidfile points at a live
# process and relaunches only dead ones, so a single long-lived supervisor means
# launchd never cycles the job and the node bridges keep running uninterrupted.
# (This does NOT fix accounts logged out on the phone side — 401 logged_out needs
# a manual QR re-link via start-one.sh <name> --qr.)

# NOTE: intentionally NOT `set -e` — a long-lived supervisor must survive a
# non-zero launcher iteration instead of dying and handing the churn back to
# launchd KeepAlive.
set -uo pipefail

export HOME="${HOME:-/Users/nuzantara}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LAUNCHER="${WA_MIRROR_LAUNCHER_START_ALL:-${HOME}/scripts/wa-mirror-launcher/start-all.sh}"
INTERVAL="${WA_MIRROR_SUPERVISE_INTERVAL:-60}"

if [[ ! -f "$LAUNCHER" ]]; then
  echo "wa-mirror launcher missing: $LAUNCHER" >&2
  exit 127
fi

echo "[supervise-launcher] starting: launcher=$LAUNCHER interval=${INTERVAL}s pid=$$"

while true; do
  if ! /bin/bash "$LAUNCHER" "$@"; then
    echo "[supervise-launcher] launcher iteration exited non-zero; continuing" >&2
  fi
  sleep "$INTERVAL"
done
