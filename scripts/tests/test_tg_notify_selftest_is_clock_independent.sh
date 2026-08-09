#!/usr/bin/env bash
# test_tg_notify_selftest_is_clock_independent.sh
#
# WHY THIS EXISTS (measured 2026-08-08 on M5 and Pro)
#   `tg_notify.py --selftest` — the notification gateway proving itself — was
#   GREEN at 19:40 UTC and RED at 03:41 WITA, on byte-identical code (same
#   sha256 on Pro, M5 and origin/main). Six checks failed, all on the p0 send
#   path.
#
#   Cause: the first selftest block set P0_BUDGET=2 but did not pin the
#   day/night window, so it inherited the real local hour. At night
#       effective = max(0, P0_BUDGET - DAY_RESERVE) = max(0, 2 - 5) = 0
#   so the very first p0 overflowed instead of sending. The two blocks AFTER it
#   already pinned the window, with the comment "deterministic at any hour CI
#   happens to run" — the discipline existed and simply did not reach upward.
#
#   Why that matters more than a flaky test: `tg-gateway.yml` is path-filtered,
#   so the selftest runs only when the gateway's own files change, at whatever
#   hour that lands. The one window in which it was reliably red — Bali night —
#   is exactly when the cron fleet runs and when a session debugging a missing
#   alert would reach for it. A guard that lies at the hour it is needed is
#   worse than no guard.
#
# WHAT IT PINS
#   The selftest's verdict must not depend on when it runs. This is asserted
#   WITHOUT faking a clock: the day-window knobs are env-driven at import, so
#   forcing "always night" through them is deterministic at any real hour.
#   A properly pinned block overrides them and passes; an unpinned one obeys
#   them and fails — which is precisely the defect.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
GW="$REPO_ROOT/scripts/tg_notify.py"

[ -f "$GW" ] || { echo "FAIL: gateway not found at $GW"; exit 2; }
command -v python3 >/dev/null || { echo "SKIP: no python3"; exit 0; }

failures=0
# `case ... in *x*)` inline inside $( ) trips the parser on the unbalanced ')'.
passed() { case "$1" in *"SELFTEST PASS"*) return 0 ;; *) return 1 ;; esac; }
yesno()  { if "$@"; then echo 1; else echo 0; fi; }
check() {
  if [ "$2" = "1" ]; then printf '  ok   %s\n' "$1"
  else printf '  FAIL %s\n' "$1"; failures=$((failures + 1)); fi
}

run_selftest() {  # $@ = env assignments
  env "$@" python3 "$GW" --selftest 2>&1 | tail -1
}

echo "the gateway's selftest must reach the same verdict at every hour:"

# "Always night" — the condition under which the unpinned block failed. No clock
# faking: the knobs are read from env at import, so this is the same forcing the
# code's own later blocks use (DAY_START_H = DAY_END_H = 25 -> no hour qualifies).
night="$(run_selftest TG_P0_DAY_START_HOUR=25 TG_P0_DAY_END_HOUR=25)"
check "forced NIGHT -> PASS (got: ${night})" \
      "$(yesno passed "$night")"

# "Always day" — the innocence side: pinning must not have simply hardcoded a
# pass, so the same block must also be green with the opposite forcing.
day="$(run_selftest TG_P0_DAY_START_HOUR=0 TG_P0_DAY_END_HOUR=24)"
check "forced DAY -> PASS (got: ${day})" \
      "$(yesno passed "$day")"

# Unforced, whatever the wall clock says right now — the shape a human runs.
plain="$(run_selftest TZ="${TZ:-UTC}")"
check "unforced at the real local hour -> PASS (got: ${plain})" \
      "$(yesno passed "$plain")"

# And the verdicts must AGREE. A future block that reintroduces clock-sensitivity
# in the other direction (green at night, red by day) is caught here even if the
# two absolute checks above were somehow both satisfied.
check "the three verdicts agree" \
      "$([ "$night" = "$day" ] && [ "$day" = "$plain" ] && echo 1 || echo 0)"

# Bali night specifically, since that is the fleet's cron window and the exact
# timezone in which this was first observed red.
wita="$(TZ=Asia/Makassar python3 "$GW" --selftest 2>&1 | tail -1)"
check "TZ=Asia/Makassar (the cron fleet's clock) -> PASS (got: ${wita})" \
      "$(yesno passed "$wita")"

if [ "$failures" -eq 0 ]; then echo "PASS (5 checks)"; exit 0; fi
echo "FAIL ($failures check(s))"; exit 1
