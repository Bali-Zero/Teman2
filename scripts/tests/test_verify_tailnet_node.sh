#!/usr/bin/env bash
# Corpus for scripts/verify_tailnet_node.sh — guilt AND innocence.
#
# A guard merged with only guilt tests is half a guard: the laptop-handoff runbook's check was
# "guilty-only" in spirit (it could report success, never failure) and that is precisely how
# it certified the wrong machine for three months. So every case below states which side it
# pins.
#
# Fixtures are captured-shape `tailscale status --json` documents injected via
# TAILNET_STATUS_JSON — the CLI boundary — so the script's real DNSName-vs-HostName selection
# runs underneath them. Field names and the awkward values (HostName "localhost" on iOS
# nodes, Self.HostName "Air-M5" against DNSName "air-m5-2") are copied from the live tailnet
# measured on 2026-08-11, not invented: a fixture that speaks a vocabulary the wire never
# emits proves only that the fixture agrees with the test (W114).

set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SUT="$HERE/../verify_tailnet_node.sh"
[ -x "$SUT" ] || { echo "FATAL: $SUT is not executable"; exit 2; }

TMP=$(mktemp -d) || exit 2
# Run from a scratch cwd and require zero residue at the end (W110: a corpus that litters the
# checkout is a corpus that can pass while writing somewhere it must not).
#
# The residue check compares a BEFORE and AFTER set of json filenames, not mtimes. The first draft
# used `find -newer "$SUT"` as a stand-in for "written by this run" and that proxy lied immediately:
# `.docs_sync_cache.json` — written by the docs-sync gate and by the pre-commit hook — is newer than
# the SUT on any normal working copy, so the check reported "the corpus wrote json into the invoking
# directory" when the corpus had written nothing. A false accusation is worse than no check: it sends
# the next reader hunting in the wrong place (cicatrix #9 — a state signal read through a proxy).
ORIG_PWD=$PWD
RESIDUE_BEFORE=$(find "$ORIG_PWD" -maxdepth 1 -name '*.json' 2>/dev/null | sort)
cd "$TMP" || exit 2
cleanup() { cd "$ORIG_PWD" || true; rm -rf "$TMP"; }
trap cleanup EXIT

PASS=0
FAIL=0

check() {
    local name="$1" want_rc="$2" fixture="$3" node="$4"
    local out rc
    out=$(TAILNET_STATUS_JSON="$fixture" bash "$SUT" "$node" 2>&1)
    rc=$?
    if [ "$rc" -eq "$want_rc" ]; then
        PASS=$((PASS + 1))
        printf 'ok   %-58s rc=%s\n' "$name" "$rc"
    else
        FAIL=$((FAIL + 1))
        printf 'FAIL %-58s want rc=%s got rc=%s\n' "$name" "$want_rc" "$rc"
        printf '     output: %s\n' "$(printf '%s' "$out" | tr '\n' '|')"
    fi
}

# --- the live-shaped tailnet: 6 nodes, no team laptop ------------------------------------
cat > fleet.json <<'JSON'
{
  "Self": {
    "ID": "nHuomUZGaZ11CNTRL",
    "HostName": "Air-M5",
    "DNSName": "air-m5-2.tail461666.ts.net.",
    "OS": "macOS",
    "TailscaleIPs": ["100.110.186.116"],
    "Online": true
  },
  "Peer": {
    "k1": {
      "ID": "nZhgzPm3WD11CNTRL",
      "HostName": "Nuzantara",
      "DNSName": "nuzantara.tail461666.ts.net.",
      "OS": "macOS",
      "TailscaleIPs": ["100.107.22.111"],
      "Online": true
    },
    "k2": {
      "ID": "nJ43a7iLbB21CNTRL",
      "HostName": "Mini-Pro2",
      "DNSName": "mini-pro2.tail461666.ts.net.",
      "OS": "macOS",
      "TailscaleIPs": ["100.93.236.6"],
      "Online": true
    },
    "k3": {
      "ID": "nQWUYmgncc11CNTRL",
      "HostName": "localhost",
      "DNSName": "iphone175.tail461666.ts.net.",
      "OS": "iOS",
      "TailscaleIPs": ["100.77.16.7"],
      "Online": false,
      "LastSeen": "2026-08-03T23:17:20.1Z"
    }
  }
}
JSON

# --- GUILT: the states the old runbook could not express ----------------------------------

# 1. Today's true state for the team laptop: the node simply is not there.
check "guilt: absent node is ABSENT, not pass" 3 fleet.json team-laptop-01

# 2. THE SCAR. Asking for the name that happens to be this machine must be its own verdict —
#    not a pass (as `ssh air 'tailscale status'` gave) and not a bare absence.
check "guilt: name resolving to self is exit 4, not 0" 4 fleet.json air-m5-2

# 3. Enrolled but offline is not "verified reachable".
check "guilt: enrolled-but-offline is exit 5" 5 fleet.json iphone175

# 4. The HostName trap: a peer whose device-reported HostName is exactly the name we want,
#    while its MagicDNS identity is a different machine. Keying on HostName would return a
#    triumphant pass here. Keying on DNSName must call it absent.
python3 - <<'PY'
import json
d = json.load(open("fleet.json"))
d["Peer"]["k9"] = {
    "ID": "nDECOY0000011CNTRL",
    "HostName": "team-laptop-01",              # decoy: the device claims the name we want
    "DNSName": "air-m5-3.tail461666.ts.net.",  # its identity says it is another M5
    "OS": "macOS",
    "TailscaleIPs": ["100.110.186.200"],
    "Online": True,
}
json.dump(d, open("decoy.json", "w"))
PY
check "guilt: HostName decoy does not satisfy the name" 3 decoy.json team-laptop-01

# 5. Unreadable status must be CANNOT-VERIFY (2), never folded into absent (3). Offline is a
#    natural state (Law 6); a healer told "absent" when the truth is "I could not look" acts
#    on a false premise.
printf 'not json at all' > garbage.json
check "guilt: unparseable status is exit 2, not 3" 2 garbage.json nuzantara
check "guilt: unreadable path is exit 2, not 3" 2 /nonexistent/no.json nuzantara

# --- INNOCENCE: the guard must not cry wolf on the legitimate cases -----------------------

# 6. A real, online peer passes.
check "innocence: live peer passes" 0 fleet.json nuzantara
check "innocence: second live peer passes" 0 fleet.json mini-pro2

# 7. A node whose HostName is useless ("localhost") is still identifiable by DNSName. This is
#    the mirror of case 4: DNSName keying must not only reject decoys, it must find the nodes
#    HostName cannot name. Two of six live nodes are in this state.
python3 - <<'PY'
import json
d = json.load(open("fleet.json"))
d["Peer"]["k3"]["Online"] = True
d["Peer"]["k3"].pop("LastSeen", None)
json.dump(d, open("ios_online.json", "w"))
PY
check "innocence: HostName=localhost node found by DNSName" 0 ios_online.json iphone175

# 8. Trailing dot and case are presentation, not identity.
check "innocence: name given with trailing dot" 0 fleet.json nuzantara.
check "innocence: name given in upper case" 0 fleet.json NUZANTARA

# --- residue check (W110) ----------------------------------------------------------------
RESIDUE_AFTER=$(find "$ORIG_PWD" -maxdepth 1 -name '*.json' 2>/dev/null | sort)
NEW_FILES=$(comm -13 <(printf '%s\n' "$RESIDUE_BEFORE") <(printf '%s\n' "$RESIDUE_AFTER"))
if [ -n "$NEW_FILES" ]; then
    FAIL=$((FAIL + 1))
    echo "FAIL residue: the corpus created json in the invoking directory:"
    printf '%s\n' "$NEW_FILES" | sed 's/^/       /'
else
    PASS=$((PASS + 1))
    echo "ok   residue: created nothing outside the scratch dir"
fi

echo "----"
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
