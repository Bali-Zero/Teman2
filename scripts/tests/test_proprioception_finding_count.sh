#!/bin/sh
# test_proprioception_finding_count.sh — a probe line must not report 1 of N as 1.
#
# THE DEFECT (measured live on Pro, 2026-08-26)
#
# scripts/hooks/proprioception_sessionstart.sh printed, per DIVERGED probe:
#
#     ev = p["evidence"][0] if p.get("evidence") else f"{n} findings"
#
# — so the finding COUNT reached the reader only when there was no evidence at
# all. With evidence present it printed the first item and said nothing about
# the rest. On Pro at the time:
#
#     launchagent_canon    55 findings -> 1 line
#     launchd_liveness     22 findings -> 1 line
#     organs_heartbeat      7 findings -> 1 line
#     worktree_gate_shim    4 findings -> 1 line
#
# The last one is the damage, not the illustration: that line was read as "one
# worktree pushes with no gate", the one named path was repaired, and THREE
# worktrees kept pushing with core.hooksPath pointing at a directory that does
# not exist — no hooks at all — until a hand census found them.
#
# This is W97 (a truncated list read downstream as complete) at a depth BELOW
# where W97 was already cured here: the receptor's [:4] cap over PROBES was
# fixed on 2026-07-26 (see test_proprioception_receptor_ranking.sh) while the
# per-probe truncation over FINDINGS was left. Same defect, two depths.
#
# WHAT WOULD MAKE THIS TEST RED: reverting either print site to the bare
# evidence[0] form. Case 1 is the guilt case and fails on the pre-fix code.
#
# Run:  sh scripts/tests/test_proprioception_finding_count.sh
# Exit: 0 all pass, 1 any failure.

fail=0
pass=0

note_pass() { pass=$((pass + 1)); echo "PASS - $1"; }
note_fail() { fail=$((fail + 1)); echo "FAIL - $1"; }

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
HOOK="$REPO_ROOT/scripts/hooks/proprioception_sessionstart.sh"
CLI="$REPO_ROOT/scripts/proprioception.py"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

[ -f "$HOOK" ] || { echo "FAIL - hook not found at $HOOK"; exit 1; }
[ -f "$CLI" ]  || { echo "FAIL - cli not found at $CLI"; exit 1; }

# Same fixture contract as test_proprioception_receptor_ranking.sh: ts and mtime
# are computed from a FRESH "now", never a hardcoded date that rots (W129).
build_report() {
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
os.utime(out_path, (ts_epoch, ts_epoch))
PYEOF
}

run_hook() {
  PROPRIOCEPTION_REPORT_PATH="$1" PROPRIOCEPTION_RECEPTOR_ENABLED=true bash "$HOOK"
}

# ---------------------------------------------------------------------------
# Case 1 (GUILT): a probe carrying 55 findings, of which evidence holds 5.
# The printed line must say it is showing one of fifty-five. RED on pre-fix.
# ---------------------------------------------------------------------------
r1="$TMPDIR/case1.json"
build_report "$r1" "0.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "pro", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 1, "probes_run": 1,
    "unwatched_classes": [],
    "summary": "proprioception: 1 probe on pro — 1 DIVERGED, 0 unprobeable, 0 reconciled",
    "probes": [
        {"id": "launchagent_canon", "boundary": "plist<->repo", "class": "plist<->repo",
         "status": "DIVERGED", "severity": "P1", "n_findings": 55,
         "evidence": ["{\"label\": \"com.balizero.first\"}",
                      "{\"label\": \"com.balizero.second\"}",
                      "{\"label\": \"com.balizero.third\"}",
                      "{\"label\": \"com.balizero.fourth\"}",
                      "{\"label\": \"com.balizero.fifth\"}"],
         "fix_hint": "reconcile the plists", "duration_ms": 9},
    ],
}
'
out1="$(run_hook "$r1")"
if printf '%s\n' "$out1" | grep -q '\[1 of 55\]'; then
  note_pass "guilt — a 55-finding probe announces it is showing 1 of 55"
else
  note_fail "guilt — 55 findings printed with no count: $out1"
fi
# The count must not have COST us the evidence or the re-verify framing.
if printf '%s\n' "$out1" | grep -q 'com.balizero.first'; then
  note_pass "guilt — the evidence itself still prints alongside the count"
else
  note_fail "guilt — evidence lost when the count was added: $out1"
fi
if printf '%s\n' "$out1" | grep -q 're-verify before acting'; then
  note_pass "guilt — the re-verify framing (2026-07-26 fix) survives this change"
else
  note_fail "guilt — re-verify framing was clobbered: $out1"
fi

# ---------------------------------------------------------------------------
# Case 2 (INNOCENCE): a probe with exactly one finding must NOT grow a count.
# "[1 of 1]" on every single-finding line would be pure noise on a report that
# is injected into every session on three machines.
# ---------------------------------------------------------------------------
r2="$TMPDIR/case2.json"
build_report "$r2" "0.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "pro", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 1, "probes_run": 1,
    "unwatched_classes": [],
    "summary": "proprioception: 1 probe on pro — 1 DIVERGED, 0 unprobeable, 0 reconciled",
    "probes": [
        {"id": "home_fork_scripts", "boundary": "home<->repo", "class": "home<->repo",
         "status": "DIVERGED", "severity": "P1", "n_findings": 1,
         "evidence": ["DIVERGED: live != repo"],
         "fix_hint": "diff the pair", "duration_ms": 5},
    ],
}
'
out2="$(run_hook "$r2")"
if printf '%s\n' "$out2" | grep -q '\[1 of'; then
  note_fail "innocence — a single-finding probe grew a needless count: $out2"
else
  note_pass "innocence — a single-finding probe prints no count"
fi
if printf '%s\n' "$out2" | grep -q 'DIVERGED: live != repo'; then
  note_pass "innocence — the single-finding line is otherwise unchanged"
else
  note_fail "innocence — single-finding line lost its evidence: $out2"
fi

# ---------------------------------------------------------------------------
# Case 3 (INNOCENCE): a probe with NO evidence keeps the pre-existing
# "N findings" fallback. That branch was already correct and must not be
# swallowed by the new one.
# ---------------------------------------------------------------------------
r3="$TMPDIR/case3.json"
build_report "$r3" "0.0" '
report = {
    "schema": 1, "runner_version": "1.0.0",
    "machine": "pro", "repo_head": "abc123", "config_source": "embedded",
    "config_sha": "x", "probes_expected": 1, "probes_run": 1,
    "unwatched_classes": [],
    "summary": "proprioception: 1 probe on pro — 1 DIVERGED, 0 unprobeable, 0 reconciled",
    "probes": [
        {"id": "some_probe", "boundary": "a<->b", "class": "a<->b",
         "status": "DIVERGED", "severity": "P1", "n_findings": 12,
         "evidence": [],
         "fix_hint": "look at it", "duration_ms": 5},
    ],
}
'
out3="$(run_hook "$r3")"
if printf '%s\n' "$out3" | grep -q '12 findings'; then
  note_pass "innocence — the empty-evidence fallback still reports the count"
else
  note_fail "innocence — empty-evidence fallback broken: $out3"
fi

# ---------------------------------------------------------------------------
# Case 4 (BEHAVIOURAL): the shared renderer scripts/proprioception.py exposes.
#
# The first draft of this case was a grep over the source — and its first
# assertion matched NOTHING, so it was green on the fixed code AND on the
# pre-fix code. A check that cannot go red is not a check. Caught by running
# this file against the reverted source before shipping it.
#
# The cure was structural, not a better regex: the two render sites INSIDE
# proprioception.py (this CLI and the per-host fleet summary) now call one
# function, `finding_label`, which can simply be called. Fixing the pattern
# instead of the structure would ALSO have hidden the second of them: the grep,
# once it actually matched, is what revealed that the fleet summary at
# proprioception.py:~1121 carried the same defect uncured.
#
# HONEST LIMIT, raised by an adversarial reviewer against the first draft of
# this file, which claimed all THREE sites "share one function":
# scripts/hooks/proprioception_sessionstart.sh does NOT import proprioception.py.
# It is a standalone python heredoc inside a shell hook, run at SessionStart
# under a latency budget measured in single-digit seconds; importing that module
# for one six-line function would be the wrong trade. So the rule genuinely lives
# in TWO places and is kept in sync by hand.
#
# That is a defensible design and an indefensible thing to leave unguarded. Case
# 5 below therefore does not merely observe that they happen to agree on one
# fixture — it drives BOTH implementations across the same matrix of counts and
# fails on the first disagreement. Drift is now detectable rather than
# coincidental, which is what the original comment falsely implied was true by
# construction.
# ---------------------------------------------------------------------------
cli_out="$(python3 - "$REPO_ROOT" <<'PYEOF'
import sys, types
from pathlib import Path

# W121 — compile from SOURCE TEXT, never through importlib's bytecode cache.
# Caught on this very corpus 2026-08-26: mutating the threshold `n > 1` to
# `n > 4` changes ONE character, so the file's SIZE is unchanged, and the
# rewrite plus the restore landed inside the same wall-clock second, so the
# MTIME matched too. Python validates a .pyc on exactly (mtime, size), so
# `spec.loader.exec_module` happily executed the MUTATED bytecode while
# `inspect.getsource` printed the RESTORED source — the mutation proof read as
# a genuine failure of correct code. compile(read_text()) has no cache to
# poison and makes this corpus immune to its own mutation harness.
_src_path = Path(sys.argv[1]) / "scripts" / "proprioception.py"
mod = types.ModuleType("proprioception")
mod.__file__ = str(_src_path)
exec(compile(_src_path.read_text(encoding="utf-8"), str(_src_path), "exec"), mod.__dict__)
fl = mod.finding_label

cases = [
    # (probe, must_contain, label)
    ({"id": "launchagent_canon", "n_findings": 55, "evidence": ["a", "b"]},
     "[1 of 55]", "guilt-many"),
    ({"id": "home_fork_scripts", "n_findings": 1, "evidence": ["a"]},
     None, "innocence-one"),
    ({"id": "some_probe", "n_findings": 12, "evidence": []},
     None, "innocence-no-evidence"),
    ({"id": "odd_probe", "n_findings": None, "evidence": ["a"]},
     None, "innocence-null-count"),
]
for probe, must, label in cases:
    got = fl(probe)
    if must is None:
        ok = "[1 of" not in got and probe["id"] in got
    else:
        ok = must in got and probe["id"] in got
    print(("OK " if ok else "NO ") + label + " -> " + repr(got))
PYEOF
)"
for label in guilt-many innocence-one innocence-no-evidence innocence-null-count; do
  if printf '%s\n' "$cli_out" | grep -q "^OK $label"; then
    note_pass "cli — finding_label $label"
  else
    note_fail "cli — finding_label $label: $(printf '%s\n' "$cli_out" | grep "$label")"
  fi
done

# The receptor and the CLI must not drift into two different opinions of the
# same line: whatever the shared function returns is what the receptor prints.
if printf '%s\n' "$out1" | grep -q "launchagent_canon \[1 of 55\]"; then
  note_pass "cli — the receptor line matches finding_label's exact rendering"
else
  note_fail "cli — receptor and finding_label disagree on the rendering: $out1"
fi

# ---------------------------------------------------------------------------
# Case 5 (DRIFT): the receptor's hand-written copy of the rule and
# proprioception.py's finding_label must agree across a MATRIX of counts, not
# on the single n=55 fixture case 1 happens to use.
#
# The receptor cannot import the module (standalone heredoc in a SessionStart
# hook, single-digit-second latency budget), so the rule is duplicated on
# purpose. This case is the thing that makes the duplication safe: change the
# threshold in one and this goes red naming the count that diverged.
# ---------------------------------------------------------------------------
drift_fail=0
for n in 0 1 2 5 55 999; do
  rn="$TMPDIR/drift-$n.json"
  build_report "$rn" "0.0" "
report = {
    \"schema\": 1, \"runner_version\": \"1.0.0\",
    \"machine\": \"pro\", \"repo_head\": \"abc123\", \"config_source\": \"embedded\",
    \"config_sha\": \"x\", \"probes_expected\": 1, \"probes_run\": 1,
    \"unwatched_classes\": [],
    \"summary\": \"s\",
    \"probes\": [
        {\"id\": \"drift_probe\", \"boundary\": \"a<->b\", \"class\": \"a<->b\",
         \"status\": \"DIVERGED\", \"severity\": \"P1\", \"n_findings\": $n,
         \"evidence\": [\"e0\"],
         \"fix_hint\": \"f\", \"duration_ms\": 1},
    ],
}
"
  # what the receptor actually printed, between "] " and " (as of"
  # NB: anchored to the FIRST ']' — a greedy 's/^.*] //' eats the "[1 of N]"
  # marker itself and makes this case fail on a correct receptor. Cost one
  # false red before shipping; kept as a comment so the next reader does not
  # re-derive it.
  recv="$(run_hook "$rn" | grep -m1 '^  !!' | sed -e 's/^  !! \[[^]]*\] //' -e 's/ (as of .*$//')"
  # what the module says for the identical probe
  modl="$(python3 - "$REPO_ROOT" "$n" <<'PYEOF'
import sys, types
from pathlib import Path
# same W121 reasoning as the case-4 loader: source text, never bytecode.
# (No apostrophe in this comment on purpose: a lone quote inside a heredoc
# nested in $( ) makes the bash lexer lose the closing paren.)
_p = Path(sys.argv[1]) / "scripts" / "proprioception.py"
mod = types.ModuleType("proprioception")
mod.__file__ = str(_p)
exec(compile(_p.read_text(encoding="utf-8"), str(_p), "exec"), mod.__dict__)
print(mod.finding_label({"id": "drift_probe", "n_findings": int(sys.argv[2]), "evidence": ["e0"]}))
PYEOF
)"
  if [ "$recv" = "$modl" ]; then
    :
  else
    drift_fail=$((drift_fail + 1))
    note_fail "drift — n=$n: receptor printed '$recv', finding_label says '$modl'"
  fi
done
if [ "$drift_fail" -eq 0 ]; then
  note_pass "drift — receptor and finding_label agree on n in {0,1,2,5,55,999}"
fi

# ---------------------------------------------------------------------------
# Case 6 (CALL SITES): the Gear-3 gate measured that this corpus proved the
# FUNCTION and not its two CALLERS — it reverted `finding_label(r)` back to
# `r['id']` at the CLI print site and the whole corpus stayed 12/0 GREEN. A
# corpus that cannot see its own subject being unplugged is the same
# over-declared-coverage shape the adversarial round caught in a comment.
#
# Closing it behaviourally is not available at a proportionate cost: both call
# sites live inline in functions that first run a live probe sweep against this
# machine (main()) or ssh to a peer (fleet_probe()), so exercising them for real
# would assert about Pro rather than about the code.
#
# So this is an AST check, and its limit is stated rather than implied: it
# proves the two call sites CALL finding_label, not that they render correctly.
# AST and not grep, because a grep for the name also matches the definition, the
# docstring and this very comment — it would pass on a file where both callers
# were unplugged. Mutation-proved: reverting either call site reddens it.
# ---------------------------------------------------------------------------
callsites="$(python3 - "$REPO_ROOT" <<'PYEOF'
import ast, sys
from pathlib import Path

src = (Path(sys.argv[1]) / "scripts" / "proprioception.py").read_text(encoding="utf-8")
tree = ast.parse(src)

def calls_finding_label(fn_name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                        and sub.func.id == "finding_label":
                    return True
            return False
    return None  # function itself is gone

for fn in ("main", "fleet_probe"):
    got = calls_finding_label(fn)
    if got is None:
        print("NO " + fn + " -> function not found in proprioception.py")
    elif got:
        print("OK " + fn)
    else:
        print("NO " + fn + " -> does not call finding_label (call site unplugged)")
PYEOF
)"
for fn in main fleet_probe; do
  if printf '%s\n' "$callsites" | grep -q "^OK $fn$"; then
    note_pass "callsite — $fn() calls finding_label"
  else
    note_fail "callsite — $(printf '%s\n' "$callsites" | grep "$fn")"
  fi
done

echo
echo "passed: $pass  failed: $fail"
[ "$fail" -eq 0 ] || exit 1
