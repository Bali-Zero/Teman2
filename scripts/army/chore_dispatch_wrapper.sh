#!/bin/bash
# chore_dispatch_wrapper.sh — thin bash shim so cron-runner.sh (which execs
# `/bin/bash "$SCRIPT"`) can invoke the Python chore dispatcher. All logic
# lives in scripts/chore_dispatch.py; this file exists only to satisfy that
# bash-only invocation contract (superscar #1: repo-canonical, no HOME-fork
# copy) — same shape as jules_lane_dispatch_wrapper.sh.
#
# Genes G2_heartbeat and G5_kill_switch live in chore_dispatch.py, one level
# below this shim (the organ-conformance gate only scans this file's own
# text, not what it execs into): heartbeat(paths, status, note) writes the
# sidecar to ~/.organism/last_seen/<ORGAN_ID>.json on every --dispatch-next
# exit path, and the CHORE_DISPATCH_ENABLED kill switch is checked before
# any dispatch work.
#
# Daily tick: dispatches AT MOST ONE pending chore (its own declared seat).
# Repeat calls on later days work through the backlog one at a time — this
# mirrors the Jules lane's own daily-cap discipline (verification bandwidth,
# not dispatch throughput, is the bottleneck for a generator-only seat).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$DIR/../chore_dispatch.py" --dispatch-next
