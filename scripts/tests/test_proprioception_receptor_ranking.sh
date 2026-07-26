#!/bin/sh
# test_proprioception_receptor_ranking.sh — regression test for #44
# (cicatrix-superscar.md famiglia #2/#9: a snapshot finding read as a current
# fact, and a severity-sort + hard top-4 cap that can hide the ONE line that
# would tell a reader to re-verify before acting).
#
# MEASURED 2026-07-26: a home_fork_scripts P1 was TRUE at the report's own
# snapshot time (09:49:51) and was cured 27 minutes later — well inside the
# receptor's 48h "fresh" gate, so the existing >max_age_h suppression never
# fires. The report's OWN self-cadence finding (probe id guardian_freshness)
# sat in the SAME findings list at P2, ranked below the P1 it could have
# contextualized, and — worse — could be pushed off the printed top-4
# entirely by enough P1s (same shape as W97's truncated-list-read-as-complete).
#
# THE FIX under test (scripts/hooks/proprioception_sessionstart.sh):
#   (a) every printed finding names itself a snapshot claim to RE-VERIFY,
#       not a live fact — "(as of HH:MM:SS, Xh ago — re-verify before
#       acting)" on every line, not just the header's age figure.
#   (b) the guardian_freshness self-cadence finding is exempt from the
#       severity sort AND the top-4 cap: prints first, unconditionally,
#       ONLY when it IS a finding (a fresh guardian emits none — silence,
#       not furniture).
#
# Run:  sh scripts/tests/test_proprioception_receptor_ranking.sh
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

# Fixed "now" the fixtures are built relative to, injected via faketime-less
# arithmetic: python computes mtimes directly, no wall-clock dependency.
build_report() {
  # $1 = output path, $2 = desired age in hours, $3 = python snippet defining
  # `report` (ts/mtime are injected here, relative to a FRESH "now" at build
  # time — never a hardcoded historical string, which would drift further
  # stale every real second this test suite exists).
  python3 - "$1" "$2" <<PYEOF
import json, os, sys, time
out_path, age_h = sys.argv[1], float(sys.argv[2])
now = time.time()
ts_epoch = now - age_h * 3600
report_ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts_epoch))
$3
report["ts"] = report_ts
with open(out_path, "w") as fh:
    json.dump(report, fh)
# mtime == ts, mirroring the real write_report() contract (proprioception.py).
os.utime(out_path, (ts_epoch, ts_epoch))
with open(out_path + ".time", "w") as fh:
    fh.write(time.strftime("%H:%M:%S", time.localtime(ts_epoch)))
PYEOF
}

run_hook() {
  PROPRIOCEPTION_REPORT_PATH="$1" PROPRIOCEPTION_RECEPTOR_ENABLED=true bash "$HOOK"
}

# ---------------------------------------------------------------------------
# Case 1 (guilt): a diverged P1 + a diverged guardian_freshness self-finding.
# The self-finding must print FIRST, and EVERY line must carry the
# re-verify framing — the exact shape of the incident this test guards.
# ---------------------------------------------------------------------------
r1="$TMPDIR/case1.json"
build_report "$r1" "0.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "m5", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 2, "probes_run": 2,
    "unwatched_classes": [],
    "summary": "proprioception: 2 probes on m5 — 2 DIVERGED, 0 unprobeable, 0 reconciled",
    "probes": [
        {"id": "home_fork_scripts", "boundary": "home<->repo", "class": "home<->repo",
         "status": "DIVERGED", "severity": "P1", "n_findings": 1,
         "evidence": ["DIVERGED: live != repo — a fix is stranded on one side"],
         "fix_hint": "diff the pair", "duration_ms": 5},
        {"id": "guardian_freshness", "boundary": "guardian<->cadence", "class": "guardian<->cadence",
         "status": "DIVERGED", "severity": "P2", "n_findings": 1,
         "evidence": ["proprioception (self): guardian last spoke 244.3h ago (max 48h)"],
         "fix_hint": "run it by hand", "duration_ms": 3},
    ],
}
'
out1="$(run_hook "$r1")"
t1="$(cat "$r1.time")"
first_finding_line="$(printf '%s\n' "$out1" | grep -m1 '^  !!')"
case "$first_finding_line" in
  *guardian_freshness*) note_pass "guilt — self-cadence finding prints FIRST, ahead of the P1" ;;
  *) note_fail "guilt — expected guardian_freshness first, got: $first_finding_line" ;;
esac
if printf '%s\n' "$out1" | grep -q "home_fork_scripts (as of $t1, 0.0h ago — re-verify before acting)"; then
  note_pass "guilt — P1 line carries the re-verify framing, not just a bare evidence string"
else
  note_fail "guilt — P1 line missing re-verify framing: $out1"
fi
if printf '%s\n' "$out1" | grep -q "guardian_freshness (as of $t1, 0.0h ago — re-verify before acting)"; then
  note_pass "guilt — self-finding line ALSO carries the re-verify framing (no special-cased bare text)"
else
  note_fail "guilt — self-finding line missing re-verify framing: $out1"
fi

# ---------------------------------------------------------------------------
# Case 2 (innocence, all reconciled): nothing diverged — no per-item lines,
# no self-cadence line, a fresh guardian is silent rather than furniture.
# ---------------------------------------------------------------------------
r2="$TMPDIR/case2.json"
build_report "$r2" "0.1" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "m5", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 2, "probes_run": 2,
    "unwatched_classes": [],
    "summary": "proprioception: 2 probes on m5 — 0 DIVERGED, 0 unprobeable, 2 reconciled",
    "probes": [
        {"id": "home_fork_scripts", "boundary": "home<->repo", "class": "home<->repo",
         "status": "RECONCILED", "severity": "P1", "n_findings": 0, "evidence": [],
         "fix_hint": "diff the pair", "duration_ms": 5},
        {"id": "guardian_freshness", "boundary": "guardian<->cadence", "class": "guardian<->cadence",
         "status": "RECONCILED", "severity": "P2", "n_findings": 0, "evidence": [],
         "fix_hint": "run it by hand", "duration_ms": 3},
    ],
}
'
out2="$(run_hook "$r2")"
if printf '%s\n' "$out2" | grep -q 'all 2 probes reconciled' && ! printf '%s\n' "$out2" | grep -q '!!'; then
  note_pass "innocence — nothing changed since snapshot still reads clean, no finding lines at all"
else
  note_fail "innocence — expected a clean one-liner and zero '!!' lines, got: $out2"
fi

# ---------------------------------------------------------------------------
# Case 3 (innocence, genuinely diverged, guardian fresh): a real P1 with NO
# guardian_freshness finding present still prints normally, with the
# re-verify framing — the fix must not suppress a true positive.
# ---------------------------------------------------------------------------
r3="$TMPDIR/case3.json"
build_report "$r3" "1.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "m5", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 2, "probes_run": 2,
    "unwatched_classes": [],
    "summary": "proprioception: 2 probes on m5 — 1 DIVERGED, 0 unprobeable, 1 reconciled",
    "probes": [
        {"id": "home_fork_scripts", "boundary": "home<->repo", "class": "home<->repo",
         "status": "DIVERGED", "severity": "P1", "n_findings": 1,
         "evidence": ["DIVERGED: live != repo — a fix is stranded on one side"],
         "fix_hint": "diff the pair", "duration_ms": 5},
        {"id": "guardian_freshness", "boundary": "guardian<->cadence", "class": "guardian<->cadence",
         "status": "RECONCILED", "severity": "P2", "n_findings": 0, "evidence": [],
         "fix_hint": "run it by hand", "duration_ms": 3},
    ],
}
'
out3="$(run_hook "$r3")"
t3="$(cat "$r3.time")"
if printf '%s\n' "$out3" | grep -q "home_fork_scripts (as of $t3, 1.0h ago — re-verify before acting)" \
   && ! printf '%s\n' "$out3" | grep -q 'guardian_freshness'; then
  note_pass "innocence — a genuine P1 still reports, and a fresh guardian prints no self-cadence line at all"
else
  note_fail "innocence — expected the P1 to print and guardian_freshness to be entirely absent, got: $out3"
fi

# ---------------------------------------------------------------------------
# Case 4 (guilt, top-4 cap + naming): 5 other P1s beyond the cap must still
# be named in the "+N more" line, not just counted — closing the W97 gap
# team-lead flagged ("the existing +N more counter never says WHICH").
# ---------------------------------------------------------------------------
r4="$TMPDIR/case4.json"
build_report "$r4" "2.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "m5", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 6, "probes_run": 6,
    "unwatched_classes": [],
    "summary": "proprioception: 6 probes on m5 — 6 DIVERGED, 0 unprobeable, 0 reconciled",
    "probes": [
        {"id": f"probe_{i}", "boundary": "b", "class": "home<->repo",
         "status": "DIVERGED", "severity": "P1", "n_findings": 1,
         "evidence": [f"finding {i}"], "fix_hint": "fix", "duration_ms": 1}
        for i in range(6)
    ],
}
'
out4="$(run_hook "$r4")"
n_bang="$(printf '%s\n' "$out4" | grep -c '^  !!')"
more_line="$(printf '%s\n' "$out4" | grep '… +')"
if [ "$n_bang" = "4" ] && printf '%s\n' "$more_line" | grep -q 'probe_4' && printf '%s\n' "$more_line" | grep -q 'probe_5'; then
  note_pass "guilt — top-4 cap holds AND the '+N more' line names the hidden probe ids"
else
  note_fail "guilt — expected 4 printed + '+2 more (probe_4, probe_5)', got n=$n_bang more='$more_line'"
fi

# ---------------------------------------------------------------------------
# Case 5 (tripwire): the live hook must still carry the re-verify framing
# and the self-finding exemption — regression guard against silently
# reverting to the bare severity-sorted rendering this test exists to kill.
# ---------------------------------------------------------------------------
if grep -q 're-verify before acting' "$HOOK" && grep -q 'self_finding' "$HOOK"; then
  note_pass "tripwire — re-verify framing and self-finding exemption both present in the live hook"
else
  note_fail "tripwire — re-verify framing or self-finding exemption missing from $HOOK"
fi

echo ""
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
