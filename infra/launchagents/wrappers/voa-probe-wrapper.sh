#!/bin/zsh
# voa-probe-wrapper.sh — cron wrapper for scripts/probes/voa_journey_probe.mjs
# LaunchAgent: com.nuzantara.voa-probe (StartInterval 900s / 15min)
#
# Mirrors infra/launchagents/wrappers/garuda-consumer.sh's shape (absolute
# interpreter, guarded payload, appended timestamped log), ported from python
# to node, plus the three traps this class of wrapper is written to avoid:
#
#   W101/W108 — never `set -e`. Under errexit a naked pipeline aborts ON the
#   pipeline itself, and any exit-code capture written after it becomes dead
#   code on the one path it exists for (measured: 16 of 20 NLM alert wrappers
#   had exactly this shape and never spoke). This script only ever sets
#   `-uo pipefail`; the node run's exit code is captured explicitly with
#   `|| RC=$?`, never inferred from "did the previous line survive".
#
#   W108 — the wrapper that reports on prod health must not itself depend on
#   an interpreter resolved by ambient PATH (a launchd job's PATH is not a
#   login shell's PATH, and a corrupted/absent interpreter is one of the
#   plausible reasons the job would need to alarm in the first place). Node
#   is resolved to an ABSOLUTE path: `/opt/homebrew/bin/node` first (the
#   Homebrew location on both fleet Macs), `command -v node` as fallback,
#   FATAL with a distinct exit code if neither resolves.
#
#   W104/superscar#2 — never redirect the probe's output to /dev/null. The
#   probe's own tri... four-state verdict (pass/dark/fail/unknown — see the
#   .mjs header) and its heartbeat JSON are the evidence a dead-man watcher
#   and a human both need; a wrapper that swallows them is cron-theater —
#   green on the outside, mute on the inside.
#
# Exit code: whatever the probe itself returned (0 = pass/dark/unknown, 1 =
# fail), or a distinct FATAL code (2/3) if this wrapper could not even start
# it, or 0 if the kill switch skipped the tick, or 0 if an overlapping run
# held the lock.
#
# ---------------------------------------------------------------------------
# ORGANISM GENES (infra/organ-conformance/genes.json — this organ is
# mini.voa_probe in apps/organism/organism/organs_registry.yaml)
# ---------------------------------------------------------------------------
#
# G2_heartbeat — every run reports its own liveness to the ORGANISM
#   (scripts/lib/heartbeat.sh -> ~/.organism/last_seen/mini.voa_probe.json).
#   This is a SEPARATE contract from the probe's OWN heartbeat
#   (VOA_PROBE_HEARTBEAT, read by L07-PR3's funnel dead-man): one answers
#   "did the cron run at all and what did it see", the other answers "what
#   did the funnel look like on this specific tick". Conflating the two was
#   the mistake this split exists to prevent — a probe that crashed before
#   writing its own heartbeat must still tell the ORGANISM it ran (and how),
#   or an operator watching organism dashboards sees nothing while the
#   probe's own JSON just goes stale in silence (superscar #2/#9).
#
#   Verdict -> organism status, read from the PROBE's heartbeat JSON, never
#   inferred from the wrapper's own exit code alone: the probe's exit code
#   is 0 for BOTH pass/dark/unknown (see the .mjs header's "Exit code"
#   section), so exit code alone cannot tell `unknown` (should be warning)
#   apart from `pass`/`dark` (should be ok).
#     pass    -> ok       funnel confirmed working end to end
#     dark    -> ok       flag deliberately off pre-launch is HEALTHY, not
#                          degraded — mapping it to degraded would nag the
#                          organism forever over an intentional state
#                          (scar W104: an intentionally-off switch is
#                          healthy, not degraded)
#     unknown -> warning  a transport-level failure this probe could not
#                          attribute to production — cannot-verify is its
#                          own state, never folded into failure (scar
#                          W106/W106b)
#     fail    -> error    an attributable break
#   Wrapper could not even run the probe at all (missing file / missing
#   node) -> error, with the reason named in the note (never silently ok —
#   superscar #2 exists precisely to name this class of green lie).
#   If the probe's heartbeat JSON cannot be read/parsed at all, the organism
#   status is `error` with a note saying the verdict was unreadable — never
#   silently assumed ok.
#
# G5_kill_switch — VOA_PROBE_ENABLED (default true) is the RUNTIME switch: an
#   operator can silence a specific tick without touching launchd at all.
#   This is DISTINCT from VOA_PROBE_CRON_ENABLED, read only by
#   infra/launchagents/install_voa_probe.sh at INSTALL time (whether to
#   render+load the plist in the first place — see that script's own
#   comment). Do not "unify" the two into one variable: one decides whether
#   the job EXISTS on this host, the other whether a given tick RUNS. When
#   VOA_PROBE_ENABLED=false: write status=disabled to the organism (a healer
#   must never resurrect an intentionally-stopped organ) and exit 0 without
#   ever invoking the probe.
#
# G10_single_instance (advisory for a plain cron organ; done anyway) — a
#   native zsh advisory lock (`zsystem flock`, the SAME primitive
#   infra/launchagents/wrappers/bali-zero-magazine-publish.sh already uses —
#   macOS ships no flock(1) binary by default, and this script is zsh, so
#   this is the house-matching choice over a homebrew-only GNU flock or a
#   bash-only `mkdir`-lock idiom) guards the probe invocation so two
#   overlapping ticks (a manual `launchctl kickstart` racing the 15-min
#   timer) cannot both hit production and both race to write the probe's own
#   heartbeat file. Non-blocking: a busy lock means a SKIPPED tick
#   (status=warning), never a failure — losing one tick out of every 900s is
#   harmless for a health probe. If the zsh/system module itself is
#   unavailable, this wrapper WARNs and proceeds WITHOUT lock protection
#   rather than refusing to probe at all — unlike the magazine publisher
#   (where a duplicate run corrupts shared publish state), an overlapping
#   probe run here is merely redundant network traffic against an idempotent
#   create/read/delete/verify journey, so degrading the advisory feature is
#   the right trade, not hard-failing the health check over it.
#
# NOTE ON HEARTBEAT.SH AND ZSH — this wrapper never `source`s
# scripts/lib/heartbeat.sh directly. That library declares locals such as
# `local status=…`-shaped internals guarded by a caller-readonly detector,
# but it is still authored and tested against bash, and every OTHER `#!/bin/
# zsh` wrapper in this repo that reports to the organism
# (translate-articles-cron-wrapper.sh, bali-zero-magazine-publish.sh) invokes
# it as a SUBPROCESS via `bash "$HEARTBEAT_LIB" <id> <status> <note>`, never
# by sourcing it into the zsh interpreter — that is the load-bearing,
# still-current house pattern this wrapper follows, not a shortcut.

set -uo pipefail

SCRIPT_PATH="${0:A}"
REPO_ROOT="$(cd "${SCRIPT_PATH:h}/../../.." && pwd)"
PROBE="$REPO_ROOT/scripts/probes/voa_journey_probe.mjs"
HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
LOG="${HOME}/logs/voa-probe.log"
LOCKFILE="${HOME}/logs/voa-probe.flock"
ORGAN_ID="mini.voa_probe"

mkdir -p "$(dirname "$LOG")"

echo "" >> "$LOG"
echo "=== VOA Journey Probe — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

# G2_heartbeat plumbing. `heartbeat` is best-effort by design (a missing/
# unreadable library must never abort the actual probe run, which is the
# priority): it silently no-ops if $HEARTBEAT_LIB is absent. The EXIT trap
# is the safety net for any path that exits WITHOUT calling `heartbeat`
# itself — an unset-variable typo under `set -u`, a `cd` failure before the
# first explicit call — so a run that dies unexpectedly still leaves the
# organism a verdict (`error`) instead of no sidecar at all, which reads as
# "never scheduled" rather than "died" (cicatrix-superscar.md #2).
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
# Distinct from VOA_PROBE_CRON_ENABLED (install.sh, install-time only — see
# the header block above).
if [ "${VOA_PROBE_ENABLED:-true}" = "false" ]; then
    echo "[voa-probe] VOA_PROBE_ENABLED=false — skipping this tick" >> "$LOG"
    heartbeat "disabled" "kill switch VOA_PROBE_ENABLED=false"
    exit 0
fi

# Signature guard (W105 class): if the derived REPO_ROOT does not contain the
# probe, either the derivation is wrong or the probe was never deployed here
# — proceeding would mean invoking `node` on a nonexistent file and reporting
# a bare 127, not the FATAL/CANNOT-VERIFY this deserves.
if [ ! -f "$PROBE" ]; then
    echo "[voa-probe] FATAL: probe not found at $PROBE (REPO_ROOT derived: $REPO_ROOT)" >> "$LOG"
    heartbeat "error" "probe file not found at $PROBE"
    exit 2
fi

if [ -x /opt/homebrew/bin/node ]; then
    NODE_BIN=/opt/homebrew/bin/node
else
    NODE_BIN="$(command -v node 2>/dev/null || true)"
fi

if [ -z "${NODE_BIN:-}" ] || [ ! -x "$NODE_BIN" ]; then
    echo "[voa-probe] FATAL: node interpreter not found (checked /opt/homebrew/bin/node and PATH)" >> "$LOG"
    heartbeat "error" "node interpreter not found (checked /opt/homebrew/bin/node and PATH)"
    exit 3
fi

echo "[voa-probe] node=$NODE_BIN probe=$PROBE" >> "$LOG"

# --- G10 single instance (advisory) ---------------------------------------
LOCK_ACQUIRED=1
if zmodload zsh/system 2>/dev/null; then
    zsystem flock -t 0.001 -i 0.001 -f VOA_PROBE_LOCK_FD "$LOCKFILE" 2>/dev/null
    lock_rc=$?
    case "$lock_rc" in
        0) LOCK_ACQUIRED=0 ;;
        2)
            echo "[voa-probe] overlapping run detected (lock busy: $LOCKFILE) — skipping this tick" >> "$LOG"
            heartbeat "warning" "skipped: overlapping run held the advisory lock"
            exit 0
            ;;
        *)
            echo "[voa-probe] WARN: advisory lock unavailable (rc=$lock_rc, lock=$LOCKFILE) — proceeding WITHOUT single-instance protection" >> "$LOG"
            ;;
    esac
else
    echo "[voa-probe] WARN: zsh/system module unavailable — proceeding WITHOUT single-instance protection" >> "$LOG"
fi

# Fix the probe-heartbeat path ONCE and export it, rather than letting the
# wrapper and the probe each independently re-derive the same default (two
# copies of a default are a drift waiting to happen — see the .mjs header's
# own defaultHeartbeatPath()). An explicit VOA_PROBE_HEARTBEAT from the
# caller (tests, an operator) is preserved untouched.
HEARTBEAT_JSON="${VOA_PROBE_HEARTBEAT:-${HOME}/logs/voa-probe-heartbeat.json}"
export VOA_PROBE_HEARTBEAT="$HEARTBEAT_JSON"
echo "[voa-probe] probe-heartbeat=$HEARTBEAT_JSON" >> "$LOG"

RC=0
"$NODE_BIN" "$PROBE" "$@" >> "$LOG" 2>&1 || RC=$?

echo "[voa-probe] rc=$RC" >> "$LOG"

if [ "$LOCK_ACQUIRED" -eq 0 ]; then
    zsystem flock -u VOA_PROBE_LOCK_FD 2>/dev/null || true
fi

# --- Map the probe's OWN four-state verdict to an organism status --------
# Read from the JSON, never the exit code alone (see the header comment's
# verdict table for why: exit code cannot distinguish unknown from ok).
VERDICT=""
if [ -r "$HEARTBEAT_JSON" ]; then
    VERDICT="$("$NODE_BIN" -e '
        try {
            const obj = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"));
            console.log(typeof obj.verdict === "string" ? obj.verdict : "");
        } catch (e) {
            console.log("");
        }
    ' "$HEARTBEAT_JSON" 2>/dev/null || true)"
fi

case "$VERDICT" in
    pass|dark)
        heartbeat "ok" "probe verdict=$VERDICT rc=$RC"
        ;;
    unknown)
        heartbeat "warning" "probe verdict=unknown (cannot attribute to production) rc=$RC"
        ;;
    fail)
        heartbeat "error" "probe verdict=fail rc=$RC"
        ;;
    *)
        heartbeat "error" "probe heartbeat verdict unreadable (path=$HEARTBEAT_JSON) rc=$RC"
        ;;
esac

exit "$RC"
