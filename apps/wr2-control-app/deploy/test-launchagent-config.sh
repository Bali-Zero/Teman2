#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h}"

assert_plist_value() {
  local plist="$1"
  local key_path="$2"
  local expected="$3"
  local actual
  actual="$(/usr/libexec/PlistBuddy -c "Print :${key_path}" "$plist")"
  if [[ "$actual" != "$expected" ]]; then
    print -u2 "FAIL: ${plist:t} ${key_path} expected '${expected}', got '${actual}'"
    exit 1
  fi
}

validate_common() {
  local plist="$1"
  plutil -lint "$plist" >/dev/null
  assert_plist_value "$plist" "Label" "com.balizero.wr2control"
  assert_plist_value "$plist" "RunAtLoad" "true"
  assert_plist_value "$plist" "KeepAlive:SuccessfulExit" "false"
}

AIR="$ROOT/com.balizero.wr2control.air.plist"
PRO="$ROOT/com.balizero.wr2control.pro.plist"
MINI="$ROOT/com.balizero.wr2control.plist"

for plist in "$AIR" "$PRO" "$MINI"; do
  [[ -f "$plist" ]] || { print -u2 "FAIL: missing ${plist:t}"; exit 1; }
  validate_common "$plist"
done

assert_plist_value "$AIR" "ProgramArguments:0" "/Users/balizero/Applications/WR2 Control.app/Contents/MacOS/WR2Control"
assert_plist_value "$AIR" "EnvironmentVariables:WR2_WARROOM_ROOT" "/Users/balizero/nuzantara/apps/war-room/output"

assert_plist_value "$PRO" "ProgramArguments:0" "/Users/nuzantara/Applications/WR2 Control.app/Contents/MacOS/WR2Control"
assert_plist_value "$PRO" "EnvironmentVariables:WR2_WARROOM_ROOT" "/Users/nuzantara/nuzantara/apps/war-room/output"

assert_plist_value "$MINI" "ProgramArguments:0" "/Users/nuzantara/Applications/WR2 Control.app/Contents/MacOS/WR2Control"
assert_plist_value "$MINI" "ProgramArguments:1" "--ambient"
assert_plist_value "$MINI" "EnvironmentVariables:WR2_WARROOM_ROOT" "/Users/nuzantara/.wr2-warroom-sync/output"

print "PASS: launch-agent configurations"
