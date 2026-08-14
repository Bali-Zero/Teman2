#!/bin/bash
# nuzantara-fw-guard — keeps the macOS application firewall OFF on Mini-Pro2.
#
# Genesis: 2026-08-10→12 outage — the application firewall turned itself on
# (stealth mode + block-all incoming, enabler never identified) and made the
# machine unreachable from EVERY site, including its own LAN. An on-site hand
# was required. This guard removes that class of outage: it runs as root every
# 5 minutes (pre-login too, it is a LaunchDaemon) and forces all three
# switches off, logging every intervention.
#
# Canon: infra/launchagents/mini/nuzantara-fw-guard.sh
# Live:  /usr/local/bin/nuzantara-fw-guard.sh (root:wheel 755, Mini only)
# Plist: /Library/LaunchDaemons/com.nuzantara.fw-guard.plist (StartInterval 300)
#
# Exit codes: 0 ok (clean or fixed) · 4 CANNOT-VERIFY (probe itself failed —
# never reported as "clean", per W106b).

set -u

LOG="/var/log/nuzantara-fw-guard.log"
HB="/var/db/nuzantara-fw-guard.heartbeat"   # /var/db survives reboot (unlike /var/run)
LASTFIX="/var/db/nuzantara-fw-guard.lastfix"
SFW="/usr/libexec/ApplicationFirewall/socketfilterfw"

ts() { date "+%Y-%m-%d %H:%M:%S"; }

# Judge the REPLY, never the exit code alone (W104) — but a failing probe is
# CANNOT-VERIFY, not clean (W106b).
gs=$("$SFW" --getglobalstate 2>&1); rc1=$?
ba=$("$SFW" --getblockall 2>&1); rc2=$?
sm=$("$SFW" --getstealthmode 2>&1); rc3=$?

if [ "$rc1" -ne 0 ] || [ "$rc2" -ne 0 ] || [ "$rc3" -ne 0 ]; then
    echo "$(ts) CANNOT-VERIFY rc=$rc1/$rc2/$rc3 gs='$gs' ba='$ba' sm='$sm'" >> "$LOG"
    date +%s > "$HB"
    exit 4
fi

fixed=""

# Guilt patterns are the exact strings socketfilterfw prints today:
#   "Firewall is disabled. (State = 0)" / enabled (State = 1|2)
#   "Firewall has block all state set to disabled" / "... to enabled"
#   "Firewall stealth mode is off" / "... is on"
case "$gs" in
    *"State = 0"*) : ;;
    *) "$SFW" --setglobalstate off >> "$LOG" 2>&1; fixed="$fixed globalstate" ;;
esac
case "$ba" in
    *disabled*) : ;;
    *) "$SFW" --setblockall off >> "$LOG" 2>&1; fixed="$fixed blockall" ;;
esac
case "$sm" in
    *off*) : ;;
    *) "$SFW" --setstealthmode off >> "$LOG" 2>&1; fixed="$fixed stealthmode" ;;
esac

if [ -n "$fixed" ]; then
    echo "$(ts) FIXED:$fixed (was: gs='$gs' ba='$ba' sm='$sm')" >> "$LOG"
    echo "$(date +%s)$fixed" > "$LASTFIX"
    # Re-probe after the cure: the fix is judged by the new state, not by
    # having run the command.
    gs2=$("$SFW" --getglobalstate 2>&1)
    ba2=$("$SFW" --getblockall 2>&1)
    sm2=$("$SFW" --getstealthmode 2>&1)
    case "$gs2$ba2$sm2" in
        *"State = 0"*disabled*off*) echo "$(ts) VERIFIED all-off after fix" >> "$LOG" ;;
        *) echo "$(ts) FIX-FAILED still: gs='$gs2' ba='$ba2' sm='$sm2'" >> "$LOG"; date +%s > "$HB"; exit 1 ;;
    esac
fi

date +%s > "$HB"
exit 0
