#!/bin/bash
# jules_lane_dispatch_wrapper.sh — thin bash shim so cron-runner.sh (which
# execs `/bin/bash "$SCRIPT"`) can invoke the Python lane. All logic lives
# in jules_lane.py; this file exists only to satisfy that bash-only
# invocation contract (superscar #1: repo-canonical, no HOME-fork copy).
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /usr/bin/env python3 "$DIR/jules_lane.py" --dispatch
