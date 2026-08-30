#!/bin/zsh
# voa-deadman-wrapper.sh — cron wrapper for scripts/probes/voa_deadman.py
# LaunchAgent: com.nuzantara.voa-deadman (StartInterval 300s / 5min)
#
# Mirrors infra/launchagents/wrappers/voa-probe-wrapper.sh's shape (the house
# reference for this class of organ) — same three traps avoided, same
# organism-genes plumbing — plus the traps specific to THIS organ:
#
#   W101/W108 — never `set -e`. This script only ever sets `-uo pipefail`;
#   the payload's exit code is captured explicitly with `|| RC=$?`, never
#   inferred from "did the previous line survive".
#
#   W108 — the wrapper resolves its interpreter to an ABSOLUTE path
#   (/usr/bin/python3 first — the interpreter this repo's own test corpus
#   proved works, see scripts/tests/test_voa_deadman.py; /opt/homebrew/bin/
#   python3 as fallback), never bare `python3` off ambient PATH, which a
#   launchd job's environment does not guarantee resolves at all.
#
#   superscar#2 — never redirect the payload's output to /dev/null. Its
#   prose (the full blast-radius enumeration on a fire tick) and its
#   `DEADMAN_RESULT` trailer line are the evidence a human AND the organism
#   both need; swallowing them is cron-theater — green on the outside, mute
#   on the inside.
#
# ---------------------------------------------------------------------------
# THE LOCK DEFECT THIS WRAPPER DOES NOT REPEAT (found the same session this
# organ was built, in the ADJACENT wrapper bali-zero-magazine-publish.sh):
# `zsystem flock -f FD "$LOCKFILE"` does NOT create its lockfile — it OPENS
# an existing path for writing and FAILS (rc=1, read as "lock unavailable
# for an unrelated reason") if the path does not already exist. Any wrapper
# that takes this lock without `touch "$LOCKFILE"` first (and a guard that
# the path is a regular file, not a directory/device/symlink-to-nowhere) is
# armed to fail its VERY FIRST run on a fresh install, before the lock ever
# does its job even once. See bali-zero-magazine-publish.sh lines ~98-110
# for the fixed pattern, if this organ ever needs the lock (see below).
#
# ---------------------------------------------------------------------------
# WHY THIS ORGAN DELIBERATELY TAKES NO LOCK (G10, decided NOT taken)
# ---------------------------------------------------------------------------
# voa-probe-wrapper.sh takes an advisory lock because an overlapping run
# would race a real CREATE/DELETE journey against production. This organ's
# every action is read-only or dry-run:
#   (1) reading the probe's heartbeat file is a plain, idempotent file read
#       — two overlapping reads of the same JSON cannot corrupt anything or
#       race each other into a bad state;
#   (2) the ONLY mutating action a fire condition could ever cause —
#       `gh workflow run garuda-arm.yml` — DOES NOT EXIST anywhere in
#       scripts/probes/voa_deadman.py (see that file's own docstring: no
#       code path invokes it, real-fire requires Zero's explicit go per
#       Needs-ruling item 2). There is nothing here for two overlapping
#       runs to double-fire;
#   (3) the one real side effect two overlapping fire-condition ticks COULD
#       both attempt — sending a Telegram P0 — is already deduplicated by
#       scripts/tg_notify.py's own dedup-key + mute-ladder (both ticks pass
#       the SAME `voa-deadman-fire` dedup key), so a second overlapping
#       alert reads as "deduped", not as a double-send.
# If this organ ever grows a real mutating action (a future real-fire PR),
# reconsider this decision and take the lock THEN, using the touch-first +
# non-regular-path-guard pattern above from day one.
#
# ---------------------------------------------------------------------------
# ORGANISM GENES (this organ is mini.voa_deadman in
# apps/organism/organism/organs_registry.yaml)
# ---------------------------------------------------------------------------
#
# G2_heartbeat — every run reports its own liveness to the ORGANISM
#   (scripts/lib/heartbeat.sh -> ~/.organism/last_seen/mini.voa_deadman.json).
#   Status is derived from the payload's `DEADMAN_RESULT` trailer line, NOT
#   from exit code alone: exit 0/1 alone cannot distinguish "healthy,
#   verdict=pass" from "healthy, verdict=dark" from "healthy, verdict=
#   unknown" from "fire because verdict=fail" from "fire because the
#   heartbeat went silent" — and a human reading the organism dashboard
#   deserves to know WHICH of those happened, not just pass/fail.
#     state=healthy_*         -> ok       (no fire — includes healthy_dark,
#                                           which is the pre-launch NORMAL
#                                           state, not a degraded one)
#     state=fire_fail         -> error    an attributable break, dry-run
#                                          fired + Telegram alerted
#     state=fire_silence_*    -> error    the probe's heartbeat is silent/
#                                          unreadable — dry-run fired +
#                                          Telegram alerted
#   Wrapper could not even run the payload at all (missing file / missing
#   interpreter) -> error, with the reason named in the note (never
#   silently ok — superscar#2 exists precisely to name this class of green
#   lie). If the payload's own trailer line cannot be found/parsed at all,
#   the organism status is `error` naming that, never silently assumed ok.
#
# G5_kill_switch — VOA_DEADMAN_ENABLED (default true) is the RUNTIME
#   switch: an operator can silence a specific tick without touching
#   launchd at all. Distinct from VOA_DEADMAN_CRON_ENABLED, read only by
#   infra/launchagents/install_voa_deadman.sh at INSTALL time (whether to
#   render+load the plist in the first place). When VOA_DEADMAN_ENABLED=
#   false: write status=disabled to the organism (a healer must never
#   resurrect an intentionally-stopped organ) and exit 0 without ever
#   invoking the payload.
#
# NOTE ON HEARTBEAT.SH AND ZSH — same house pattern as voa-probe-wrapper.sh:
# this wrapper never `source`s scripts/lib/heartbeat.sh directly (that
# library is authored/tested against bash); it invokes it as a subprocess
# via `bash "$HEARTBEAT_LIB" <id> <status> <note>`.

set -uo pipefail

SCRIPT_PATH="${0:A}"
REPO_ROOT="$(cd "${SCRIPT_PATH:h}/../../.." && pwd)"
PAYLOAD="$REPO_ROOT/scripts/probes/voa_deadman.py"
HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
LOG="${HOME}/logs/voa-deadman.log"
ORGAN_ID="mini.voa_deadman"

mkdir -p "$(dirname "$LOG")"

echo "" >> "$LOG"
echo "=== VOA Dead-Man — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

# G2_heartbeat plumbing. `heartbeat` is best-effort by design (a missing/
# unreadable library must never abort the actual tick, which is the
# priority): it silently no-ops if $HEARTBEAT_LIB is absent. The EXIT trap
# is the safety net for any path that exits WITHOUT calling `heartbeat`
# itself, so a run that dies unexpectedly still leaves the organism a
# verdict (`error`) instead of no sidecar at all, which reads as "never
# scheduled" rather than "died" (cicatrix-superscar.md #2).
HB_EMITTED=0
heartbeat() {  # heartbeat <status> [note]
    HB_EMITTED=1
    [ -f "$HEARTBEAT_LIB" ] || return 0
    bash "$HEARTBEAT_LIB" "$ORGAN_ID" "$1" "${2:-}" || true
}
_hb_on_exit() {
    local rc=$?
    if [ "$HB_EMITTED" -eq 0 ]; then
        heartbeat error "aborted before verdict (rc=$rc)"
    fi
    return 0
}
trap _hb_on_exit EXIT

# --- G5 kill switch (RUNTIME) --------------------------------------------
# Distinct from VOA_DEADMAN_CRON_ENABLED (install.sh, install-time only —
# see the header block above).
if [ "${VOA_DEADMAN_ENABLED:-true}" = "false" ]; then
    echo "[voa-deadman] VOA_DEADMAN_ENABLED=false — skipping this tick" >> "$LOG"
    heartbeat "disabled" "kill switch VOA_DEADMAN_ENABLED=false"
    exit 0
fi

# Signature guard (W105 class): if the derived REPO_ROOT does not contain
# the payload, either the derivation is wrong or the organ was never
# deployed here — proceeding would mean invoking `python3` on a nonexistent
# file and reporting a bare 2/127, not the FATAL/CANNOT-VERIFY this deserves.
if [ ! -f "$PAYLOAD" ]; then
    echo "[voa-deadman] FATAL: payload not found at $PAYLOAD (REPO_ROOT derived: $REPO_ROOT)" >> "$LOG"
    heartbeat "error" "payload file not found at $PAYLOAD"
    exit 2
fi

if [ -x /usr/bin/python3 ]; then
    PY_BIN=/usr/bin/python3
elif [ -x /opt/homebrew/bin/python3 ]; then
    PY_BIN=/opt/homebrew/bin/python3
else
    PY_BIN="$(command -v python3 2>/dev/null || true)"
fi

if [ -z "${PY_BIN:-}" ] || [ ! -x "$PY_BIN" ]; then
    echo "[voa-deadman] FATAL: python3 interpreter not found (checked /usr/bin/python3, /opt/homebrew/bin/python3, and PATH)" >> "$LOG"
    heartbeat "error" "python3 interpreter not found (checked /usr/bin/python3, /opt/homebrew/bin/python3, and PATH)"
    exit 3
fi

echo "[voa-deadman] python3=$PY_BIN payload=$PAYLOAD" >> "$LOG"

# --- G10 single instance: DELIBERATELY NOT TAKEN. See header block above. -

# Fix the heartbeat path ONCE and export it, matching the probe-side
# default so the two agree without either re-deriving it independently.
HEARTBEAT_JSON="${VOA_PROBE_HEARTBEAT:-${HOME}/logs/voa-probe-heartbeat.json}"
export VOA_PROBE_HEARTBEAT="$HEARTBEAT_JSON"
echo "[voa-deadman] watching heartbeat=$HEARTBEAT_JSON" >> "$LOG"

OUT="$(mktemp "${TMPDIR:-/tmp}/voa-deadman-out.XXXXXX")"
RC=0
"$PY_BIN" "$PAYLOAD" >> "$OUT" 2>&1 || RC=$?
cat "$OUT" >> "$LOG"

echo "[voa-deadman] rc=$RC" >> "$LOG"

# --- Map the payload's DEADMAN_RESULT trailer line to an organism status -
# Read from that structured line, never the exit code alone: exit 0/1
# alone cannot distinguish healthy_pass from healthy_dark from
# healthy_unknown, or fire_fail from fire_silence_stale — see the header
# comment's mapping table for why that granularity matters to a human
# reading the organism dashboard.
STATE=""
TRAILER_LINE="$(grep '^DEADMAN_RESULT ' "$OUT" | tail -1 || true)"
if [ -n "$TRAILER_LINE" ]; then
    STATE="$(printf '%s' "$TRAILER_LINE" | sed -n 's/.*state=\([^ ]*\).*/\1/p')"
fi
rm -f "$OUT"

case "$STATE" in
    healthy_*)
        heartbeat "ok" "deadman state=$STATE rc=$RC"
        ;;
    fire_fail)
        heartbeat "error" "FIRE (dry-run): state=$STATE probe verdict=fail rc=$RC"
        ;;
    fire_silence_*)
        heartbeat "error" "FIRE (dry-run): heartbeat silent/unreadable ($STATE) rc=$RC"
        ;;
    *)
        heartbeat "error" "deadman trailer line unreadable (log=$LOG) rc=$RC"
        ;;
esac

exit "$RC"
