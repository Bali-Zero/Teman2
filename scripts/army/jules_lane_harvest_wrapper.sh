#!/bin/bash
# jules_lane_harvest_wrapper.sh — thin bash shim so cron-runner.sh (which
# execs `/bin/bash "$SCRIPT"`) can invoke the Python lane. All logic lives
# in jules_lane.py; this file exists only to satisfy that bash-only
# invocation contract (superscar #1: repo-canonical, no HOME-fork copy).
#
# Genes G2_heartbeat and G5_kill_switch live in jules_lane.py, one level
# below this shim (the organ-conformance gate only scans this file's own
# text, not what it execs into): heartbeat(paths, status, note) writes the
# sidecar to ~/.organism/last_seen/<ORGAN_ID>.json on every exit path, and
# the ARMY_JULES_ENABLED kill switch is checked before any harvest work.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$DIR/jules_lane.py" --harvest
