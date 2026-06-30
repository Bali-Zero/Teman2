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


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 (2026-06-30): the 7 remaining mata_garuda crons that used per-cron
# HOME-fork SHELL wrappers in ~/scripts/. Those cannot be promoted as repo shell
# scripts (launchd /bin/zsh can't open ~/Desktop under TCC → exit 127, verified
# A/B). Instead route each through the repo cron-tcc-safe.sh, which execs venv
# PYTHON (TCC-bypassing) and now carries the per-cron logic via flags
# (--module / --flock / --window / --source-env). One TCC-safe wrapper, in git.
#
# Format: "label-suffix|ProgramArguments after the wrapper path"
WRAPPED7=(
  "bridge.adaptive|--module mata_garuda.bridge.nerve --source-env .cell-bridge-state/wa-media.env"
  "classifier.adaptive|--flock classifier-worker $REPO/apps/mata-garuda/scripts/run_classifier_worker.py"
  "consumer-lag.check|$REPO/apps/mata-garuda/scripts/check_consumer_lag.py"
  "gap.consumer|--module mata_garuda.workers.gap_consumer --window 6-22"
  "ner.adaptive|--flock ner-worker $REPO/apps/mata-garuda/scripts/run_ner_worker.py"
  "nlm-feeder-stream.hourly|$REPO/apps/mata-garuda/scripts/run_nlm_feeder_stream.py"
  "pel-cleaner.weekly|--flock pel-cleaner $REPO/apps/mata-garuda/scripts/pel_cleaner.py"
)

for entry in "${WRAPPED7[@]}"; do
  suffix="${entry%%|*}"
  argstr="${entry#*|}"
  P="$LA/com.matagaruda.$suffix.plist"
  [ -f "$P" ] || { echo "  skip $suffix (no plist)"; continue; }
  L=$(/usr/libexec/PlistBuddy -c "Print :Label" "$P" 2>/dev/null)
  cur=$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments:0" "$P" 2>/dev/null || true)
  if [ "$cur" = "$REPO_WRAPPER" ]; then echo "  ok   $suffix (already repo wrapper)"; continue; fi
  cp -p "$P" "$P.bak-repowrapper-$(date +%Y%m%d-%H%M%S)"
  # rebuild ProgramArguments: [wrapper, <argstr tokens...>]
  /usr/libexec/PlistBuddy -c "Delete :ProgramArguments" "$P" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c "Add :ProgramArguments array" "$P"
  /usr/libexec/PlistBuddy -c "Add :ProgramArguments: string $REPO_WRAPPER" "$P"
  for tok in $argstr; do
    /usr/libexec/PlistBuddy -c "Add :ProgramArguments: string $tok" "$P"
  done
  # gap.consumer carried a dead-.worktrees MATA_GARUDA_REPO override — drop it so
  # the wrapper's self-locating REPO_ROOT wins (cicatrix #1 dead-worktree).
  /usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:MATA_GARUDA_REPO" "$P" 2>/dev/null || true
  plutil -lint "$P" >/dev/null
  launchctl bootout "gui/$(id -u)/$L" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$P" 2>/dev/null || echo "    (reload deferred — picks up next run)"
  echo "  migrated $suffix → repo wrapper ($argstr)"
done

echo "done. HOME-fork wrappers in $HOME/scripts/ are now unused (keep as fallback or rm after a clean cycle)."
