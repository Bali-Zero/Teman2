#!/bin/sh
# test_proprioception_output_cap.sh — B4 output cap (2026-09-04, context diet).
#
# scripts/hooks/proprioception_sessionstart.sh injects into EVERY session
# start on every machine. Before this cap, a report carrying several DIVERGED
# P1s each with a long fix_hint, plus a mix of P1 and P2 findings, could push
# the injected block well past a couple KB (measured live on Pro pre-fix:
# 2261 bytes with just 4 findings — see git history of this file). Two rules
# under test:
#   (a) a fix_hint longer than 160 chars is truncated (with an ellipsis),
#       never printed whole.
#   (b) when at least one P1 finding is present, other-severity findings
#       collapse into a single count line instead of printing in full.
#   (c) SESSIONSTART_HOOK_MAX_BYTES caps the WHOLE stdout, truncating at a
#       line boundary and naming the real full-board command when even (a)
#       and (b) are not enough.
#
# Run:  sh scripts/tests/test_proprioception_output_cap.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/scripts/hooks/proprioception_sessionstart.sh"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

[ -f "$HOOK" ] || { echo "FAIL - hook not found at $HOOK"; exit 1; }

build_report() {
  # $1 = output path, $2 = python snippet defining `report` (ts/mtime
  # injected relative to a FRESH "now", never a hardcoded date — W129).
  python3 - "$1" <<PYEOF
import json, os, sys, time
out_path = sys.argv[1]
now = time.time()
report_ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now))
$2
report["ts"] = report_ts
with open(out_path, "w") as fh:
    json.dump(report, fh)
os.utime(out_path, (now, now))
PYEOF
}

run_hook() {
  PROPRIOCEPTION_REPORT_PATH="$1" PROPRIOCEPTION_RECEPTOR_ENABLED=true \
    SESSIONSTART_HOOK_MAX_BYTES="${2:-1500}" bash "$HOOK"
}

byte_len() {
  printf '%s' "$1" | wc -c | tr -d ' '
}

# ---------------------------------------------------------------------------
# Case 1 (guilt): 3 P1 findings each carrying a 400-char fix_hint, plus 1 P2.
# Pre-fix this alone (4 findings, uncapped fix_hint) measured 2261 bytes live
# with SHORTER hints than this fixture uses — this fixture is worse than the
# live incident on purpose.
# ---------------------------------------------------------------------------
long_hint="$(python3 -c 'print("x" * 400)')"
r1="$TMPDIR/case1.json"
build_report "$r1" "
report = {
    \"schema\": 1, \"runner_version\": \"1.0.0\",
    \"machine\": \"pro\", \"repo_head\": \"abc123\", \"config_source\": \"embedded\",
    \"config_sha\": \"x\", \"probes_expected\": 4, \"probes_run\": 4,
    \"unwatched_classes\": [],
    \"summary\": \"s\",
    \"probes\": [
        {\"id\": \"probe_p1_a\", \"boundary\": \"b\", \"class\": \"a<->b\",
         \"status\": \"DIVERGED\", \"severity\": \"P1\", \"n_findings\": 1,
         \"evidence\": [\"evidence a\"], \"fix_hint\": \"$long_hint\", \"duration_ms\": 1},
        {\"id\": \"probe_p1_b\", \"boundary\": \"b\", \"class\": \"a<->b\",
         \"status\": \"DIVERGED\", \"severity\": \"P1\", \"n_findings\": 1,
         \"evidence\": [\"evidence b\"], \"fix_hint\": \"$long_hint\", \"duration_ms\": 1},
        {\"id\": \"probe_p1_c\", \"boundary\": \"b\", \"class\": \"a<->b\",
         \"status\": \"DIVERGED\", \"severity\": \"P1\", \"n_findings\": 1,
         \"evidence\": [\"evidence c\"], \"fix_hint\": \"$long_hint\", \"duration_ms\": 1},
        {\"id\": \"probe_p2\", \"boundary\": \"b\", \"class\": \"a<->b\",
         \"status\": \"DIVERGED\", \"severity\": \"P2\", \"n_findings\": 1,
         \"evidence\": [\"evidence p2\"], \"fix_hint\": \"low priority context\", \"duration_ms\": 1},
    ],
}
"
out1="$(run_hook "$r1")"
n1="$(byte_len "$out1")"
if [ "$n1" -le 1500 ]; then
  note_pass "guilt — output with 3 long-fix_hint P1s + 1 P2 fits the default cap ($n1 bytes)"
else
  note_fail "guilt — output exceeds 1500 bytes: $n1"
fi
if printf '%s\n' "$out1" | grep -q 'probe_p1_a' && printf '%s\n' "$out1" | grep -q 'probe_p1_b' && printf '%s\n' "$out1" | grep -q 'probe_p1_c'; then
  note_pass "guilt — all 3 P1 findings survive the cap"
else
  note_fail "guilt — a P1 finding was lost to the cap: $out1"
fi
if printf '%s\n' "$out1" | grep -q 'probe_p2'; then
  note_fail "guilt — the P2 finding printed in full instead of collapsing to a count line"
else
  note_pass "guilt — the P2 finding collapsed away (a P1 is present)"
fi
if printf '%s\n' "$out1" | grep -q '1 lower-severity finding'; then
  note_pass "guilt — the collapsed P2 is named as a count, not silently dropped"
else
  note_fail "guilt — no lower-severity count line found: $out1"
fi
# No single fix: line may exceed FIX_HINT_MAX(160)+prefix by more than a
# couple chars of slack for the ellipsis.
long_fix_line="$(printf '%s\n' "$out1" | grep '     fix: xxx' | head -1)"
if [ -n "$long_fix_line" ] && [ "$(byte_len "$long_fix_line")" -le 175 ]; then
  note_pass "guilt — a 400-char fix_hint was truncated, not printed whole"
else
  note_fail "guilt — fix_hint truncation missing or too loose: '$long_fix_line'"
fi

# ---------------------------------------------------------------------------
# Case 2 (innocence): a single short P1, well under budget — the cap must
# not trim content that already fits (mirrors the pre-existing behavioural
# tests in test_proprioception_receptor_ranking.sh, kept green by this fix).
# ---------------------------------------------------------------------------
r2="$TMPDIR/case2.json"
build_report "$r2" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "pro", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 1, "probes_run": 1,
    "unwatched_classes": [],
    "summary": "s",
    "probes": [
        {"id": "small_probe", "boundary": "b", "class": "a<->b",
         "status": "DIVERGED", "severity": "P1", "n_findings": 1,
         "evidence": ["short evidence"], "fix_hint": "short fix", "duration_ms": 1},
    ],
}
'
out2="$(run_hook "$r2")"
if printf '%s\n' "$out2" | grep -q 'short fix' && ! printf '%s\n' "$out2" | grep -q 'lines,'; then
  note_pass "innocence — a small report is not over-trimmed (no truncation trailer, hint intact)"
else
  note_fail "innocence — a small report was needlessly trimmed: $out2"
fi

# ---------------------------------------------------------------------------
# Case 3 (env override): a tight SESSIONSTART_HOOK_MAX_BYTES must be honored
# and must still surface at least the header + one P1 line.
# ---------------------------------------------------------------------------
out3="$(run_hook "$r1" "300")"
n3="$(byte_len "$out3")"
if [ "$n3" -le 300 ]; then
  note_pass "env override — SESSIONSTART_HOOK_MAX_BYTES=300 honored ($n3 bytes)"
else
  note_fail "env override — output exceeds the overridden cap: $n3 bytes"
fi
if printf '%s\n' "$out3" | grep -q 'PROPRIOCEZIONE'; then
  note_pass "env override — the header line survives even a tight cap"
else
  note_fail "env override — header lost under a tight cap: $out3"
fi

echo ""
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
