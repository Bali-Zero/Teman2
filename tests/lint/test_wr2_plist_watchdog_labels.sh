#!/usr/bin/env bash
# Validate wr2_plist_watchdog.sh uses the plist Label key, not the filename.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WATCHDOG="$REPO_ROOT/scripts/wr2_plist_watchdog.sh"

TMP="$(mktemp -d -t wr2_plist_watchdog_labels.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP/home"
export WR2_REPO_ROOT="$TMP/repo"
mkdir -p "$HOME/Library/LaunchAgents" "$WR2_REPO_ROOT/infra/launchagents" "$TMP/bin"

CALLS="$TMP/launchctl.calls"
cat > "$TMP/bin/launchctl" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "$LAUNCHCTL_CALLS"
if [[ "${1:-}" == "print" ]]; then
  case "${2:-}" in
    */com.balizero.wr2.canva-token-watchdog|*/com.balizero.wr2.canva-lease-watchdog)
      exit 0
      ;;
    *)
      exit 9
      ;;
  esac
fi
if [[ "${1:-}" == "bootstrap" ]]; then
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/launchctl"

export PATH="$TMP/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export LAUNCHCTL_CALLS="$CALLS"

write_plist() {
  local path="$1" label="$2"
  cat > "$path" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/echo</string>
    <string>ok</string>
  </array>
</dict>
</plist>
EOF
}

write_plist \
  "$WR2_REPO_ROOT/infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist" \
  "com.balizero.wr2.canva-token-watchdog"
write_plist \
  "$WR2_REPO_ROOT/infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist" \
  "com.balizero.wr2.canva-lease-watchdog"

cp "$WR2_REPO_ROOT/infra/launchagents/"*.plist "$HOME/Library/LaunchAgents/"

"$WATCHDOG" >/tmp/wr2_plist_watchdog_labels.out 2>/tmp/wr2_plist_watchdog_labels.err

if grep -q 'canva-token-watchdog.daily' "$CALLS"; then
  echo "FAIL: launchctl was called with filename-derived token label" >&2
  cat "$CALLS" >&2
  exit 1
fi

if grep -q 'canva-lease-watchdog.10min' "$CALLS"; then
  echo "FAIL: launchctl was called with filename-derived lease label" >&2
  cat "$CALLS" >&2
  exit 1
fi

grep -q 'com.balizero.wr2.canva-token-watchdog' "$CALLS"
grep -q 'com.balizero.wr2.canva-lease-watchdog' "$CALLS"

echo "PASS: wr2 plist watchdog uses Label keys for launchctl checks"
