#!/bin/sh
# test_organism_digest_sessionstart_cap.sh — B4 output cap (2026-09-04, context diet).
#
# scripts/hooks/organism_digest_sessionstart.sh injects into EVERY session
# start on every machine. Its content is entirely rendered by
# scripts/organism_digest.py (768 lines, its own selftest asserts the exact
# shape of arsenal_card()) — this cap is a POST-FILTER over that already-
# rendered text, applied inside the .sh wrapper only, so organism_digest.py
# and its existing test suite (test_organism_digest_pending_arms.py) are
# untouched and stay green.
#
# Fixtures use organism_digest.py's own ORGANISM_DIGEST_HOME / _REPO env
# overrides (the same mechanism its own _selftest() uses) so this drives the
# REAL hook + the REAL renderer against a throwaway world, never the tracked
# ~/.organism state or this repo's real regulatory deltas.
#
# Three rules under test:
#   (a) the arsenal card's per-seat rollup + "doors:" line ALWAYS collapse
#       into one "not ok: ..." (or "all seats ok") line — fixed reshape, not
#       conditional on the cap.
#   (b) under budget pressure, low/unknown-severity regulatory lines and the
#       main-landing line drop before any red item (seat TIMEOUT/dead,
#       silent organ, medium+/high regulatory) is touched.
#   (c) SESSIONSTART_HOOK_MAX_BYTES caps the WHOLE stdout; when even (a) and
#       (b) are not enough, a line-boundary truncation adds one trailer line
#       naming the real full-board command.
#
# Run:  sh scripts/tests/test_organism_digest_sessionstart_cap.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/scripts/hooks/organism_digest_sessionstart.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

[ -f "$HOOK" ] || { echo "FAIL - hook not found at $HOOK"; exit 1; }

byte_len() { printf '%s' "$1" | wc -c | tr -d ' '; }

# build_world WORLD_DIR PY_SNIPPET — PY_SNIPPET receives `home` and `repo`
# (both already created as directories) and populates them.
build_world() {
  world="$1"
  home="$world/home"
  repo="$world/repo"
  mkdir -p "$home/.organism/arsenal" "$home/.organism/last_seen" \
           "$repo/research/regulatory" "$repo/scripts"
  python3 - "$home" "$repo" <<PYEOF
import json, os, sys, time
home, repo = sys.argv[1], sys.argv[2]
$2
PYEOF
  # a real git repo with an origin/main ref, or merged_on_main() errors out
  ( cd "$repo" && git init -q \
      && git -c user.name=t -c user.email=t@e commit -q --allow-empty -m "seed" \
      && git update-ref refs/remotes/origin/main HEAD ) >/dev/null 2>&1
}

run_hook() {
  # $1=world dir, $2=max_bytes override (optional)
  CLAUDE_PROJECT_DIR="$REPO_ROOT" \
    ORGANISM_DIGEST_ENABLED=true \
    ORGANISM_ARSENAL_REFRESH_ENABLED=false \
    ORGANISM_DIGEST_HOME="$1/home" \
    ORGANISM_DIGEST_REPO="$1/repo" \
    SESSIONSTART_HOOK_MAX_BYTES="${2:-1500}" \
    bash "$HOOK"
}

# ---------------------------------------------------------------------------
# Case 1 (guilt, stress): 30 synthetic seats all TIMEOUT (arsenal_seats() has
# no internal cap — organism_digest.py prints one line per not-LIVE seat) +
# 5 regulatory deltas spanning high/medium/low/unknown severity. Deliberately
# past what even the priority-drop stage can absorb, to exercise BOTH (b) and
# the hard line-boundary fallback (c) in one fixture.
# ---------------------------------------------------------------------------
w1="$TMPDIR/w1"
build_world "$w1" '
seats = [{"seat": f"synthetic_seat_{i}", "status": "TIMEOUT"} for i in range(30)]
with open(os.path.join(home, ".organism", "arsenal", "last.json"), "w") as f:
    json.dump({"seats": seats}, f)
deltas = [
    {"citation": "PMK 1/2026", "severity": "high", "service_line": "tax",
     "title_en": "High severity change to tax filings and consultant registration procedure"},
    {"citation": "PMK 2/2026", "severity": "medium", "service_line": "tax",
     "title_en": "Medium severity change to reporting deadlines for corporate taxpayers"},
    {"citation": "PMK 3/2026", "severity": "low", "service_line": "tax",
     "title_en": "Low severity administrative clarification on invoice numbering formats"},
    {"citation": "PMK 4/2026", "severity": "low", "service_line": "tax",
     "title_en": "Another low severity clarification on filing portal navigation steps"},
    {"citation": "PMK 5/2026", "severity": "?", "service_line": "tax",
     "title_en": "Unclassified regulatory change pending severity triage"},
]
with open(os.path.join(repo, "research", "regulatory", "2026-09-01-delta.json"), "w") as f:
    json.dump({"deltas": deltas}, f)
'
out1="$(run_hook "$w1")"
n1="$(byte_len "$out1")"
if [ "$n1" -le 1500 ]; then
  note_pass "guilt/stress — 30 TIMEOUT seats + mixed-severity regulatory fits the default cap ($n1 bytes)"
else
  note_fail "guilt/stress — output exceeds 1500 bytes: $n1"
fi
if printf '%s\n' "$out1" | grep -q 'TIMEOUT'; then
  note_pass "guilt/stress — red seat (TIMEOUT) lines survive"
else
  note_fail "guilt/stress — all red seat lines lost: $out1"
fi
if printf '%s\n' "$out1" | grep -q '\[high\]' && printf '%s\n' "$out1" | grep -q '\[medium\]'; then
  note_pass "guilt/stress — high and medium severity regulatory lines survive"
else
  note_fail "guilt/stress — a medium/high regulatory line was lost: $out1"
fi
if printf '%s\n' "$out1" | grep -q '\[low\]' || printf '%s\n' "$out1" | grep -q '\[?\]'; then
  note_fail "guilt/stress — a low/unknown severity regulatory line survived a budget crunch"
else
  note_pass "guilt/stress — low/unknown severity regulatory lines dropped first"
fi
if printf '%s\n' "$out1" | grep -q '^… (+[0-9]* lines, run: python3 scripts/organism_digest.py)$'; then
  note_pass "guilt/stress — hard-truncation trailer present and names the real full-board command"
else
  note_fail "guilt/stress — expected a truncation trailer, got: $out1"
fi

# ---------------------------------------------------------------------------
# Case 2 (innocence): a small, mostly-healthy world — well under budget, no
# truncation should occur, but the arsenal card's rollup+doors collapse is a
# FIXED reshape (not conditional on the cap) so it must still collapse here.
# ---------------------------------------------------------------------------
w2="$TMPDIR/w2"
build_world "$w2" '
seats = [{"seat": "claude", "status": "LIVE"}, {"seat": "kimi", "status": "TIMEOUT"}]
with open(os.path.join(home, ".organism", "arsenal", "last.json"), "w") as f:
    json.dump({"seats": seats}, f)
'
out2="$(run_hook "$w2")"
n2="$(byte_len "$out2")"
if [ "$n2" -le 1500 ] && ! printf '%s\n' "$out2" | grep -q 'lines, run:'; then
  note_pass "innocence — a small world fits comfortably, no truncation trailer ($n2 bytes)"
else
  note_fail "innocence — small world unexpectedly truncated: $out2"
fi
if printf '%s\n' "$out2" | grep -q '  doors: '; then
  note_fail "innocence — the uncollapsed doors: line leaked through"
else
  note_pass "innocence — the doors: line never reaches the injected output"
fi
if printf '%s\n' "$out2" | grep -q 'not ok: kimi'; then
  note_pass "innocence — the collapsed line names the one NOT-ok seat"
else
  note_fail "innocence — collapsed not-ok line missing or wrong: $out2"
fi

# ---------------------------------------------------------------------------
# Case 3 (env override): a tight SESSIONSTART_HOOK_MAX_BYTES must be honored
# and the header + at least one red seat line must still make it through.
# ---------------------------------------------------------------------------
out3="$(run_hook "$w1" "500")"
n3="$(byte_len "$out3")"
if [ "$n3" -le 500 ]; then
  note_pass "env override — SESSIONSTART_HOOK_MAX_BYTES=500 honored ($n3 bytes)"
else
  note_fail "env override — output exceeds the overridden cap: $n3 bytes"
fi
if printf '%s\n' "$out3" | grep -q '📰 ORGANISMO' && printf '%s\n' "$out3" | grep -q 'TIMEOUT'; then
  note_pass "env override — header and at least one red seat line survive a tight cap"
else
  note_fail "env override — header or red line lost under a tight cap: $out3"
fi

echo ""
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
