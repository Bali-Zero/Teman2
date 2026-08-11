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
MARKER="$HOME/.nuzantara-sos-inbound-2026-08-11.delivered"
LOG_FILE="$HOME/logs/mini-sos-report.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

# Guard 1 — node. This file ships to every machine in the repo; only the
# patient runs it. mini-git-pull.sh has no node guard of its own, and its
# test harness runs it with a synthetic HOME, so the guard must live here.
if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "$SOS_HOST" ]; then
    exit 0
fi

# Guard 2 — expiry. A probe nobody removed must stop on its own.
if [ "$(date +%Y-%m-%d)" \> "$SOS_DEADLINE" ]; then
    log "past deadline $SOS_DEADLINE — probe retired, doing nothing"
    exit 0
fi

# Guard 3 — deliver once. The marker is written only after a report actually
# lands on the Pro, so a failed exfiltration retries on the next pull instead
# of going quiet (a probe whose silence is indistinguishable from success is
# worse than no probe).
if [ -f "$MARKER" ]; then
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
