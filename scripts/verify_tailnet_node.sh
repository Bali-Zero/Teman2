#!/usr/bin/env bash
# verify_tailnet_node.sh <node-name> [--ssh <user>]
#
# Answers exactly ONE question: is the node called <node-name> present in THIS tailnet,
# and is it a machine OTHER than the one running this script?
#
# WHY THIS EXISTS (cicatrix #1 alias-drift + #2 Esiste≠Armato, measured 2026-08-11):
# the 2026-05 laptop-handoff runbook verified retained access with `ssh air 'tailscale status'`.
# That command answers GREEN — from M5. On Pro, BOTH `air` and `air-ts` resolve to M5
# (`Air-M5.local` / 100.110.186.116), and `infra/fleet/nodes.json` legitimately declares
# ssh_alias "air" for m5. So the runbook's own verification could never fail: it asked
# "does the alias answer?" instead of "is the thing that answered the node I mean?".
# The Air was in fact never in the tailnet at all.
#
# Two design rules follow, and both are load-bearing:
#   1. Identity is the MagicDNS name (`DNSName`) / node ID, never `HostName` and never an
#      ssh alias. Measured: two iOS nodes in this tailnet report HostName "localhost", and
#      even M5 reports HostName "Air-M5" while its DNSName is "air-m5-2" (collision suffix).
#      Keying on HostName would both miss real nodes and match the wrong one.
#   2. "The name resolved to me" is its own verdict (exit 4), never a pass and never a plain
#      absence. That is the exact shape the old runbook mistook for success.
#
# "Cannot verify" (exit 2) is never folded into pass or absent: offline is a natural state
# (SYMBIOSIS Law 6) and a caller acting on "absent" when the truth is "I could not look"
# spends real work on a false premise.
#
# Exit codes:
#   0  verified: present in this tailnet, online, and NOT this machine
#   2  cannot verify (no tailscale CLI, unreadable status)
#   3  absent from this tailnet
#   4  the name resolves to THIS machine — you are measuring yourself, not <node-name>
#   5  present but offline (prints last-seen)
#   6  present, but the --ssh identity assertion failed
#
# Test seam: set TAILNET_STATUS_JSON=<file> to read a captured `tailscale status --json`
# instead of invoking the CLI. The fixture is injected at the CLI boundary so the real
# field-selection logic runs underneath it (W114: a fake placed above the transformation
# proves only that the fake agrees with itself).

set -uo pipefail

usage() {
    echo "usage: $0 <node-name> [--ssh <user>]" >&2
    echo "  <node-name>  first label of the node's MagicDNS name (e.g. 'nuzantara', 'team-laptop-01')" >&2
}

NODE=""
SSH_USER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --ssh) SSH_USER="${2:-}"; [ -z "$SSH_USER" ] && { usage; exit 64; }; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) usage; exit 64 ;;
        *) [ -n "$NODE" ] && { usage; exit 64; }; NODE="$1"; shift ;;
    esac
done
[ -z "$NODE" ] && { usage; exit 64; }

# --- read the tailnet status, or refuse to guess -----------------------------------------
if [ -n "${TAILNET_STATUS_JSON:-}" ]; then
    if [ ! -r "$TAILNET_STATUS_JSON" ]; then
        echo "CANNOT-VERIFY: TAILNET_STATUS_JSON=$TAILNET_STATUS_JSON is not readable" >&2
        exit 2
    fi
    STATUS=$(cat "$TAILNET_STATUS_JSON")
else
    TS=""
    for cand in tailscale /opt/homebrew/bin/tailscale /usr/local/bin/tailscale \
                /Applications/Tailscale.app/Contents/MacOS/Tailscale; do
        if command -v "$cand" >/dev/null 2>&1; then TS="$cand"; break; fi
    done
    if [ -z "$TS" ]; then
        # Pro carries no `tailscale` in PATH — only the app-bundle binary. Measured 2026-08-11.
        echo "CANNOT-VERIFY: no tailscale CLI found (PATH, brew prefixes, or Tailscale.app)" >&2
        exit 2
    fi
    STATUS=$("$TS" status --json 2>/dev/null)
    if [ -z "$STATUS" ]; then
        echo "CANNOT-VERIFY: '$TS status --json' produced no output" >&2
        exit 2
    fi
fi

# --- judge by DNSName, and say which side answered ---------------------------------------
VERDICT=$(printf '%s' "$STATUS" | NODE="$NODE" python3 -c '
import json, os, sys

want = os.environ["NODE"].strip().lower().rstrip(".")

def label(dnsname):
    """First label of a MagicDNS name: 'mini-pro2.tail461666.ts.net.' -> 'mini-pro2'."""
    return (dnsname or "").rstrip(".").split(".")[0].lower()

try:
    d = json.load(sys.stdin)
except Exception as e:
    print("CANNOT_VERIFY\tstatus json is not parseable: %s" % e)
    sys.exit(0)

me = d.get("Self") or {}
if label(me.get("DNSName")) == want:
    print("SELF\t%s\t%s\t%s" % (
        (me.get("DNSName") or "").rstrip("."),
        (me.get("TailscaleIPs") or ["?"])[0],
        me.get("ID") or "?"))
    sys.exit(0)

for peer in (d.get("Peer") or {}).values():
    if label(peer.get("DNSName")) != want:
        continue
    ip = (peer.get("TailscaleIPs") or ["?"])[0]
    dns = (peer.get("DNSName") or "").rstrip(".")
    nid = peer.get("ID") or "?"
    if peer.get("Online"):
        print("ONLINE\t%s\t%s\t%s\t%s" % (dns, ip, nid, peer.get("OS") or "?"))
    else:
        print("OFFLINE\t%s\t%s\t%s\t%s" % (dns, ip, nid, peer.get("LastSeen") or "unknown"))
    sys.exit(0)

# Report what the tailnet DOES contain, so an absence is actionable rather than bare.
names = sorted(
    label(p.get("DNSName")) for p in (d.get("Peer") or {}).values() if p.get("DNSName")
)
print("ABSENT\t%s\t%s" % (label(me.get("DNSName")), ",".join(names)))
')

KIND=$(printf '%s' "$VERDICT" | cut -f1)

case "$KIND" in
    CANNOT_VERIFY)
        echo "CANNOT-VERIFY: $(printf '%s' "$VERDICT" | cut -f2)" >&2
        exit 2
        ;;
    SELF)
        dns=$(printf '%s' "$VERDICT" | cut -f2)
        echo "FAIL: '$NODE' is THIS machine ($dns) — you are measuring yourself, not a peer." >&2
        echo "      This is the shape the laptop-handoff runbook mistook for success. Verify from" >&2
        echo "      another node, or you have the wrong name." >&2
        exit 4
        ;;
    ABSENT)
        selfname=$(printf '%s' "$VERDICT" | cut -f2)
        present=$(printf '%s' "$VERDICT" | cut -f3)
        echo "FAIL: '$NODE' is NOT in this tailnet (asked from '$selfname')." >&2
        echo "      Peers present: ${present:-<none>}" >&2
        exit 3
        ;;
    OFFLINE)
        dns=$(printf '%s' "$VERDICT" | cut -f2)
        ip=$(printf '%s' "$VERDICT" | cut -f3)
        seen=$(printf '%s' "$VERDICT" | cut -f5)
        echo "FAIL: '$NODE' ($dns, $ip) is enrolled but OFFLINE — last seen $seen" >&2
        exit 5
        ;;
    ONLINE)
        dns=$(printf '%s' "$VERDICT" | cut -f2)
        ip=$(printf '%s' "$VERDICT" | cut -f3)
        nid=$(printf '%s' "$VERDICT" | cut -f4)
        os=$(printf '%s' "$VERDICT" | cut -f5)
        echo "OK: '$NODE' is a live peer of this tailnet — $dns  $ip  id=$nid  os=$os"
        ;;
    *)
        echo "CANNOT-VERIFY: unclassified verdict from the status reader: '$VERDICT'" >&2
        exit 2
        ;;
esac

# --- optional second layer: make the node name itself ------------------------------------
# Identity by DNSName already excludes the self-answering trap. This adds the assertion that
# whatever answers on that address is not simply this machine reached by another route.
if [ -n "$SSH_USER" ]; then
    LOCAL_HOST=$(hostname -s 2>/dev/null || hostname)
    REMOTE_HOST=$(ssh -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
                      "${SSH_USER}@${ip}" 'hostname -s 2>/dev/null || hostname' 2>&1 | tail -1)
    rc=$?
    if [ $rc -ne 0 ] || [ -z "$REMOTE_HOST" ]; then
        echo "FAIL: --ssh assertion could not run against $ip (rc=$rc): $REMOTE_HOST" >&2
        exit 6
    fi
    if [ "$REMOTE_HOST" = "$LOCAL_HOST" ]; then
        echo "FAIL: $ip answered with THIS machine's hostname ('$REMOTE_HOST') — the address" >&2
        echo "      is looping back to the verifier. Green here would be the wrong machine." >&2
        exit 6
    fi
    echo "OK: --ssh assertion — $ip answers as '$REMOTE_HOST' (this machine is '$LOCAL_HOST')"
fi

exit 0
