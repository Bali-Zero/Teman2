#!/bin/sh
# trampoline.sh — shared W84 TCC-fail-fast + ssh-localhost re-exec lib.
#
# Deployed copy lives at ~/scripts/lib/trampoline.sh — OUTSIDE the
# TCC-protected ~/Desktop (same reasoning as ~/scripts/lib/heartbeat.sh:
# superscar #1's antidote is "relocate the payload out of Desktop" — a lib
# that itself lived under ~/Desktop would need the very grant it exists to
# route around). Declared pair: infra/home-fork/declared-pairs.json.
#
# WHAT / WHY (scar W84, extracted from the regulatory-watcher-run.sh
# reference implementation 2026-07-06/07-13): on Pro, the launchd execution
# context can silently lose the TCC/Full-Disk-Access grant to ~/Desktop
# after a reboot — no code, plist, or permission changed, only the
# per-process TCC row. A job whose payload lives under
# ~/Desktop/nuzantara dies with "Operation not permitted" (sometimes
# swallowed/masked by the job's own error handling), while the SAME job
# invoked from an interactive shell or ssh session (sshd has a separate,
# intact FDA grant) works fine. Two cures are wired here:
#   1. FAIL FAST: probe with a REAL READ before doing any other work, so a
#      dead-TCC run aborts in <1s instead of burning an LLM tier / a batch
#      job / minutes of work only to discover at write-time that the
#      contract is unfulfillable.
#   2. TRAMPOLINE: before giving up, re-exec the SAME wrapper through
#      `ssh localhost` — the sshd context carries its own TCC identity
#      (Full Disk Access), independent of whichever per-binary launchd row
#      macOS silently revoked at the last reboot.
#
# WHY THE PROBE MUST BE A REAL READ (not `[ -r ]` / `test -r`):
# TCC denies at open(2) time, not at access(2)/stat(2) time — `[ -r file ]`
# can report "yes, readable" via access(2) while the actual open() a real
# reader performs is denied. A probe built on access(2) is itself a proxy
# that can lie (cf. superscar #9 "state read via proxy, not content").
# `head -c 1 <file>` forces a real open+read and surfaces the true TCC
# verdict.
#
# GUARD VAR / ANTI-LOOP: the trampoline sets W84_TRAMPOLINED=1 on the
# re-exec'd command. If the ssh-localhost context ALSO fails the probe
# (e.g. sshd itself lost FDA, or the file genuinely doesn't exist), the
# guard prevents an infinite re-exec loop — the second pass falls through
# to the FATAL branch and exits 78 instead of re-trampolining forever.
#
# IMPORTANT CAVEAT — ENV IS NOT INHERITED ACROSS THE RE-EXEC:
# `ssh localhost "W84_TRAMPOLINED=1 '<wrapper>'"` starts a FRESH login/
# non-interactive shell on the target end. It does NOT inherit the
# launchd plist's <EnvironmentVariables> dict (PATH, PYTHONPATH,
# GARUDA_CANONICAL_REDIS_HOST, etc.) — those were set by launchd for the
# ORIGINAL process, not for the ssh session spawned from within it. Every
# wrapper that sources this lib MUST set its own PATH/PYTHONPATH/etc.
# internally (after sourcing secrets), rather than relying on plist
# EnvironmentVariables to survive a trampolined run. See
# infra/launchagents/wrappers/regulatory-watcher-run.sh for the canonical
# pattern (PATH export near the top, secrets sourced explicitly).
#
# USAGE (zsh AND bash — source, don't exec):
#   TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
#   [ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
#   [ -f "$TRAMPOLINE_LIB" ] && . "$TRAMPOLINE_LIB" && w84_trampoline_or_die "$LOG"
#
# w84_trampoline_or_die LOGFILE [WRAPPER_PATH]
#   LOGFILE       — path to append the FATAL/trampoline breadcrumb to.
#   WRAPPER_PATH  — defaults to $0 (the sourcing script's own invocation
#                   path); pass explicitly if $0 would resolve wrong
#                   (e.g. sourced from an unusual context).
#   Returns 0 if ~/Desktop is readable in THIS context (caller continues).
#   Never returns otherwise: either re-execs via ssh (exec replaces the
#   process) or exits 78 (config error, per launchd_liveness_detector
#   convention — distinguishes "TCC-blocked" from a generic crash).
w84_trampoline_or_die() {
    local _w84_log="$1"
    local _w84_wrapper="${2:-$0}"

    if head -c 1 "$HOME/Desktop/nuzantara/CLAUDE.md" >/dev/null 2>&1; then
        return 0
    fi

    if [ -z "${W84_TRAMPOLINED:-}" ] && [ -f "$HOME/.ssh/id_local_trampoline" ]; then
        echo "[$(date)] W84: TCC denies ~/Desktop in this launchd context — re-exec via ssh-localhost trampoline" >> "$_w84_log"
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i "$HOME/.ssh/id_local_trampoline" localhost "W84_TRAMPOLINED=1 '$_w84_wrapper'"
    fi

    echo "[$(date)] FATAL: TCC denies ~/Desktop/nuzantara in this launchd context (W84) and no trampoline key — re-grant Full Disk Access to the job's interpreter. Aborting before any further work." >> "$_w84_log"
    exit 78
}
