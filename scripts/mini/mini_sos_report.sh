#!/bin/bash
# mini_sos_report.sh — read-only probe carried INTO the Mini by its own git-pull.
#
# WHY THIS EXISTS (2026-08-11)
# Since 2026-08-10 between 13:48 and 14:06 WITA every INBOUND connection to
# Mini-Pro2 completes the TCP handshake and is then reset ~250 ms later —
# sshd, screensharingd (VNC), redis, ollama and ARD alike, i.e. five unrelated
# services failing the same way, which points at one shared ingress mechanism
# rather than five coincidences. Meanwhile OUTBOUND works perfectly: the very
# `git fetch` that delivers this file drained ~90 KB from the Pro, so cron,
# fork/exec, disk writes and the Tailscale tunnel are all healthy. A physical
# power-cycle changed nothing, so the cause is persistent state (a setting),
# not a crash. Nobody can reach the machine's keyboard.
#
# That leaves exactly one code path into this host — its own 5-minute pull —
# and exactly one direction out — the SSH it opens to the Pro. This script
# rides the former and reports through the latter.
#
# IT CURES NOTHING AND RESTARTS NOTHING, DELIBERATELY. Tailscale is the last
# remaining channel to this machine; a restart that failed to come back would
# turn a reachability outage into a site visit. Round 1 measures, a later round
# acts on what it finds.
#
# Everything here is read-only, bounded, and fail-open: it can neither block
# nor fail the pull that invokes it. No secrets and no client data are read or
# transmitted — only host/network/service state.
#
# Self-expiring: after SOS_DEADLINE it does nothing. Delete this file and its
# four-line caller in mini-git-pull.sh once the Mini is reachable again.

set -u

SOS_DEADLINE="2026-08-25"
SOS_HOST="mini-pro2"
MARKER="$HOME/.nuzantara-sos-inbound-2026-08-11.delivered-v2"
CURE_MARKER="$HOME/.nuzantara-sos-inbound-2026-08-11.cure-attempted-v2"
LOG_FILE="$HOME/logs/mini-sos-report.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

# Guard 1 — node. This file ships to every machine in the repo; only the
# patient runs it. mini-git-pull.sh has no node guard of its own, and its
# test harness runs it with a synthetic HOME, so the guard must live here.
# The hostname is a NAME and names drift; the Tailscale address is the identity
# this whole rescue is addressed to, and it is the one I can verify from the
# outside (the Pro reads it from `tailscale status --json`). Accept either, so a
# machine renamed at some point in its life is still recognised as the patient.
# It cannot misfire elsewhere: the Pro and M5 hold different Tailscale IPs.
SOS_TSIP="100.93.236.6"
_is_patient=0
[ "$(hostname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" = "$SOS_HOST" ] && _is_patient=1
ifconfig 2>/dev/null | grep -q "inet $SOS_TSIP\b" && _is_patient=1
if [ "$_is_patient" != "1" ]; then
    exit 0
fi

# Guard 2 — expiry. A probe nobody removed must stop on its own.
if [ "$(date +%Y-%m-%d)" \> "$SOS_DEADLINE" ]; then
    log "past deadline $SOS_DEADLINE — probe retired, doing nothing"
    exit 0
fi

# Guard 3 — do the work once each, and track the two halves SEPARATELY. The
# report marker is written only after a report actually lands on the Pro (a
# probe whose silence is indistinguishable from success is worse than no
# probe); the cure marker is written when the cure has been ATTEMPTED, acted
# or not. Two markers rather than one because the halves arrived on different
# days: a single marker set by the first delivery would have made the cure
# added afterwards permanently unreachable — dead code on the only path it
# exists for, which is a mistake this repo has made often enough to name.
if [ -f "$MARKER" ] && [ -f "$CURE_MARKER" ]; then
    exit 0
fi

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null

# Guard 4 — wall-clock. Nothing below may outlive this, whatever hangs.
( sleep 150; kill -9 $$ 2>/dev/null ) &
WATCHDOG=$!
trap 'kill -9 "$WATCHDOG" 2>/dev/null' EXIT

OUT="$(mktemp -t mini-sos)" || exit 0

section() { printf '\n===== %s =====\n' "$1" >> "$OUT"; }
probe() { # $1 label, rest: argv
    local label="$1"; shift
    section "$label"
    "$@" >> "$OUT" 2>&1 || echo "(command failed, rc=$?)" >> "$OUT"
}

{
    echo "MINI-PRO2 SOS REPORT — inbound-dead diagnostic"
    echo "generated: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "whoami: $(whoami)  hostname: $(hostname)"
} > "$OUT"

# --- is the machine itself healthy? (the disk-full hypothesis died on the
#     evidence, but measure it here rather than keep believing the autopsy)
probe "uptime / boot"            uptime
probe "os version"               sw_vers
probe "disk: data volume"        df -h /System/Volumes/Data
probe "disk: root"               df -h /
probe "file descriptors"         sysctl kern.maxfiles kern.num_files
probe "process count"            sh -c 'ps ax | wc -l'
probe "power state"              pmset -g

# --- the ingress mechanisms, in order of suspicion.
# The application firewall's "block all incoming" produces exactly the
# observed signature: the kernel completes the handshake, the filter then
# terminates the session, uniformly, for every listening service, surviving
# reboots and leaving outbound untouched.
probe "app firewall state"       /usr/libexec/ApplicationFirewall/socketfilterfw \
                                     --getglobalstate --getblockall \
                                     --getallowsigned --getstealthmode
probe "firewall per-app list"    sh -c '/usr/libexec/ApplicationFirewall/socketfilterfw --listapps 2>&1 | head -40'
probe "packet filter"            sh -c 'pfctl -s info 2>&1 | head -20'
probe "network extensions"       systemextensionsctl list
probe "vpn profiles"             scutil --nc list
probe "third-party net/security" sh -c 'ls /Library/LaunchDaemons /Library/LaunchAgents 2>/dev/null | grep -iE "nord|vpn|lulu|snitch|eset|sophos|crowd|jamf|zscaler|cisco|proton|mullvad" || echo "(none matched)"'

# --- are the services actually up, or is launchd holding empty sockets?
probe "sharing services"         sh -c 'launchctl list 2>/dev/null | grep -iE "ssh|screensharing|ard|vnc|remotedesktop|screen" || echo "(no matching jobs)"'
probe "disabled jobs"            sh -c 'launchctl print-disabled system 2>&1 | grep -iE "ssh|screensharing|ard" || echo "(none / not permitted)"'
probe "listening sockets"        sh -c 'netstat -an | grep LISTEN | head -40'
probe "sshd config drop"         sh -c 'ls -la /etc/ssh/sshd_config.d/ 2>&1 | head'

# --- the transport itself
probe "tailscale version"        sh -c 'tailscale version 2>&1 | head -5'
probe "tailscale status"         sh -c 'tailscale status 2>&1 | head -20'
probe "tailscale netcheck"       sh -c 'tailscale netcheck 2>&1 | head -25'
probe "tunnel interfaces"        sh -c 'ifconfig 2>/dev/null | grep -A4 "^utun" | head -40'

# --- what the machine itself saw when a connection was refused. This is the
#     one place that can name the mechanism outright.
probe "recent sshd log"          sh -c 'log show --last 20m --predicate '"'"'process == "sshd" OR process == "sshd-session" OR process == "screensharingd" OR process == "socketfilterfw"'"'"' 2>&1 | tail -40'

# --- what round 2 is allowed to do: any cure for a firewall or a system
#     daemon needs root, and a repo-shipped script must never carry a
#     password. So ask the only question that matters — is root available
#     without one? — and never the secret itself.
section "passwordless sudo available?"
if sudo -n true 2>/dev/null; then
    echo "YES — round 2 may use sudo -n" >> "$OUT"
else
    echo "NO — round 2 is limited to unprivileged actions" >> "$OUT"
fi

# --- THE MEASUREMENT THAT SEPARATES THE TWO REMAINING CAUSES.
# Watched from the Pro, an inbound connection to this host completes the
# three-way handshake and then never ACKs a byte (send-queue frozen at 57
# across 20+ seconds, then FIN_WAIT_2). Two mechanisms produce that and they
# need opposite cures:
#
#   (a) the application firewall accepts and then terminates -> cure is local,
#       and the section above already took it if the measurement agreed;
#   (b) tailscaled terminates the TCP connection in userspace and then fails
#       to hand it to the local service -- e.g. the network extension lost the
#       macOS Local Network grant. Then the firewall is innocent and flipping
#       it changes nothing.
#
# One test tells them apart, and only this host can run it: dial the SAME port
# two ways. Over loopback the packet never touches tailscaled; over this host's
# OWN Tailscale address it goes through the userspace path that a remote peer
# uses. loopback OK + tailscale-IP FAIL is (b), proven from the inside, and no
# amount of firewall work would have fixed it. Both failing points back at the
# host. This costs four seconds and is the difference between curing the cause
# and curing the first thing that looked plausible.
section "self-test: loopback vs own tailscale IP"
for PORT in 22 5900; do
    for ADDR in 127.0.0.1 100.93.236.6; do
        if nc -z -G 3 -w 3 "$ADDR" "$PORT" </dev/null >/dev/null 2>&1; then
            echo "  $ADDR:$PORT  OPEN" >> "$OUT"
        else
            echo "  $ADDR:$PORT  FAIL (rc=$?)" >> "$OUT"
        fi
    done
done
probe "tailscale prefs (netstack/userspace?)" sh -c 'tailscale debug prefs 2>&1 | head -30'
probe "tailscaled process"                    sh -c 'ps ax -o pid,etime,command | grep -i "[t]ailscale" | head -5'

# --- CONDITIONAL CURE -------------------------------------------------------
# The header still says the probe cures nothing; that was true of round 1 and
# is now narrowed rather than repealed. It restarts nothing — Tailscale is the
# only remaining channel into this host and a restart that failed to come back
# turns a reachability outage into a site visit. What it may do is flip ONE
# setting, and only when the measurement taken seconds earlier in this same run
# says that setting is the disease. That is not a blind cure: if the condition
# does not hold, nothing happens and the report says so.
#
# Why only the firewall's block-all, when three plausible causes exist: the
# other two are already contradicted by the evidence. A port scan of this host
# distinguishes listening ports (22, 5900, 6379, 11434 — handshake completes,
# then reset) from non-listening ones (5432, 8000, 60000 — refused outright).
# So sshd and screensharingd ARE running and ARE bound; "the service is off"
# cannot be the cause, and enabling it would be acting against measurement.
# Block-all is the only candidate that produces exactly this signature:
# accept, then terminate, uniformly, for every listening service, outbound
# untouched, surviving reboots.
section "cure attempt"
if [ -f "$CURE_MARKER" ]; then
    echo "already attempted at $(cat "$CURE_MARKER" 2>/dev/null) — not repeating" >> "$OUT"
elif ! sudo -n true 2>/dev/null; then
    echo "SKIPPED — no passwordless root; every cure for a firewall needs it," >> "$OUT"
    echo "and a repo-shipped script must never carry a password." >> "$OUT"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$CURE_MARKER" 2>/dev/null
else
    FW=/usr/libexec/ApplicationFirewall/socketfilterfw
    BLOCKALL_BEFORE="$(sudo -n "$FW" --getblockall 2>&1)"
    echo "measured before: $BLOCKALL_BEFORE" >> "$OUT"
    # Three-way, and the ORDER is load-bearing: DISABLED contains ENABLED as a
    # substring, so a naive *ENABLED* test reads "off" as "on" and would flip
    # a setting that was already correct. Test the negative first, and treat
    # anything we do not recognise as UNKNOWN — never as consent to act.
    case "$BLOCKALL_BEFORE" in
        *DISABLED*|*disabled*)
            echo "VERDICT: block-all is already off — it is NOT the cause." >> "$OUT"
            echo "No action taken. The cause is elsewhere; read the sections above." >> "$OUT"
            ;;
        *ENABLED*|*enabled*)
            echo "VERDICT: block-all is ON — this is the disease. Turning it off." >> "$OUT"
            echo "(Only 'block all incoming' is cleared; the firewall itself stays" >> "$OUT"
            echo " on, per-app rules intact. Reverse with: socketfilterfw --setblockall on)" >> "$OUT"
            sudo -n "$FW" --setblockall off >> "$OUT" 2>&1 || \
                echo "(--setblockall off failed, rc=$?)" >> "$OUT"
            echo "measured after: $(sudo -n "$FW" --getblockall 2>&1)" >> "$OUT"
            ;;
        *)
            echo "VERDICT: UNRECOGNISED output — taking no action deliberately." >> "$OUT"
            echo "Acting on a string I cannot parse is how a cure breaks a healthy host." >> "$OUT"
            ;;
    esac
    date -u +%Y-%m-%dT%H:%M:%SZ > "$CURE_MARKER" 2>/dev/null
fi

# --- did it work? Ask the OTHER side. This host cannot test its own inbound
#     path — from in here every port looks open — so the proof has to come
#     from a machine that is actually blocked, and the Pro is both blocked and
#     reachable outbound. This is the difference between "I ran the fix" and
#     "the fix worked": a command's exit code reports the command, a connect
#     from outside reports the machine.
section "inbound proof, measured FROM the Pro"
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new pro \
    'for p in 22 5900; do nc -z -G 5 -w 5 100.93.236.6 $p </dev/null >/dev/null 2>&1; echo "port $p from pro: rc=$?"; done' \
    >> "$OUT" 2>&1 || echo "(could not reach the Pro to run the proof)" >> "$OUT"

# --- exfiltrate over the direction that still works.
REMOTE_NAME="mini-sos-$(date +%Y%m%d-%H%M%S).txt"
DELIVERED=0
for TARGET in pro nuzantara@100.107.22.111; do
    if ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
           "$TARGET" "cat > /tmp/$REMOTE_NAME && cp /tmp/$REMOTE_NAME /tmp/mini-sos-latest.txt" \
           < "$OUT" 2>>"$LOG_FILE"; then
        log "report delivered to $TARGET:/tmp/$REMOTE_NAME"
        DELIVERED=1
        break
    fi
    log "delivery to $TARGET failed, trying next target"
done

# Keep a local copy either way — if every route out is dead, whoever reaches
# the console eventually still finds the answer sitting in the log dir.
cp "$OUT" "$HOME/logs/mini-sos-report-latest.txt" 2>/dev/null
rm -f "$OUT" 2>/dev/null

if [ "$DELIVERED" = "1" ]; then
    date -u +%Y-%m-%dT%H:%M:%SZ > "$MARKER" 2>/dev/null
else
    log "NO route out — will retry on the next pull"
fi
