#!/usr/bin/env bash
# Repoint the 10 mata_garuda wrapper-crons from the HOME-fork wrapper
# (~/scripts/matagaruda-cron-tcc-safe.sh) to the REPO-tracked, path-aware copy.
#
# cicatrix #1 (HOME-fork drift): the live split-brain of 2026-06-30 happened
# because the wrapper lived outside git and hardcoded the Mini Redis host. This
# moves every cron onto the repo wrapper so `git pull` keeps them correct, and the
# test_cron_wrapper_no_homefork lint stops re-drift.
#
# Idempotent. Run on Pro (where these 10 LaunchAgents live).
set -euo pipefail

REPO="$HOME/Desktop/nuzantara"
REPO_WRAPPER="$REPO/apps/mata-garuda/scripts/matagaruda-cron-tcc-safe.sh"
HOMEFORK="$HOME/scripts/matagaruda-cron-tcc-safe.sh"
LA="$HOME/Library/LaunchAgents"

[ -x "$REPO_WRAPPER" ] || { echo "[ERROR] repo wrapper missing/not-exec: $REPO_WRAPPER" >&2; exit 1; }

CRONS=(daily-briefing kg-linker kita-feed.daily nlm-expander.weekly public-channel
       reg-alert.30min sentinel.hourly weekly-digest wr-topic wr2-bridge.hourly)

for c in "${CRONS[@]}"; do
  P="$LA/com.matagaruda.$c.plist"
  [ -f "$P" ] || { echo "  skip $c (no plist)"; continue; }
  # the real label (some plists drop the schedule suffix)
  L=$(/usr/libexec/PlistBuddy -c "Print :Label" "$P" 2>/dev/null)
  cur=$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments:0" "$P" 2>/dev/null || true)
  if [ "$cur" = "$REPO_WRAPPER" ]; then echo "  ok   $c (already repo wrapper)"; continue; fi
  cp -p "$P" "$P.bak-repowrapper-$(date +%Y%m%d-%H%M%S)"
  /usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 $REPO_WRAPPER" "$P"
  plutil -lint "$P" >/dev/null
  # reload under the REAL label
  launchctl bootout "gui/$(id -u)/$L" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$P" 2>/dev/null || echo "    (reload deferred — picks up next run)"
  echo "  migrated $c → repo wrapper (label $L)"
done

echo "done. HOME-fork wrapper $HOMEFORK is now unused (keep as fallback or rm after a clean cycle)."
