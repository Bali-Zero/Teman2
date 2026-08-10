#!/usr/bin/env bash
# Corpus for scripts/ci/docs_sync_gate.sh — guilt AND innocence (superscar #3).
#
# GUILT: the judge (or its corpus) is missing => the gate must FAIL. This is the
# defect that existed until 2026-08-10: the inline YAML answered `exit 0`, so a
# PR deleting scripts/docs_sync.py passed the required check green.
#
# INNOCENCE: with the judge present the gate must not invent a failure, and it
# must PROPAGATE the judge's own exit code rather than flattening it — a gate
# that turns 3 into 1, or 3 into 0, is a different lie.
#
# Every case runs in a temp cwd (W96/W110: a corpus must not write into the
# repo, and must leave no residue).

set -uo pipefail

GATE="$(cd "$(dirname "$0")/../.." && pwd)/scripts/ci/docs_sync_gate.sh"
[ -x "$GATE" ] || { echo "FATAL: gate not executable at $GATE"; exit 1; }

PASS=0
FAIL=0

run_case() {
  # run_case <name> <expected_rc> <setup_fn> <mode>
  local name="$1" expected="$2" setup="$3" mode="$4"
  local tmp
  tmp="$(mktemp -d)"
  ( cd "$tmp" && "$setup" ) || { echo "FATAL: setup failed for $name"; rm -rf "$tmp"; exit 1; }
  local rc
  ( cd "$tmp" && PYTHON="$tmp/fakepython" "$GATE" "$mode" >/dev/null 2>&1 )
  rc=$?
  if [ "$rc" -eq "$expected" ]; then
    echo "  PASS  $name (rc=$rc)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (expected rc=$expected, got rc=$rc)"
    FAIL=$((FAIL + 1))
  fi
  rm -rf "$tmp"
}

# --- fixtures -----------------------------------------------------------------

_fakepython() {
  # $1 = exit code the fake interpreter should return
  cat > fakepython <<EOF
#!/bin/sh
exit $1
EOF
  chmod +x fakepython
}

setup_no_judge() {            # guilt: judge deleted
  mkdir -p scripts/tests
  _fakepython 0
}

setup_no_corpus() {           # guilt: judge's unit tests deleted
  mkdir -p scripts/tests
  printf '#\n' > scripts/docs_sync.py
  _fakepython 0
}

setup_judge_green() {         # innocence: everything present, docs in sync
  mkdir -p scripts/tests
  printf '#\n' > scripts/docs_sync.py
  printf '#\n' > scripts/tests/test_docs_sync_atlas.py
  _fakepython 0
}

setup_judge_red() {           # innocence-of-verdict: judge says stale
  mkdir -p scripts/tests
  printf '#\n' > scripts/docs_sync.py
  printf '#\n' > scripts/tests/test_docs_sync_atlas.py
  _fakepython 3
}

setup_bare() {                # usage error
  _fakepython 0
}

# --- cases --------------------------------------------------------------------

echo "docs-sync gate — fail-closed corpus"

# GUILT — absence must be a failure, on BOTH targets (symmetry clause, W101-recidiva:
# a fix that covers only the branch that bit you is half a fix).
run_case "guilt: judge absent            -> check FAILS" 1 setup_no_judge  check
run_case "guilt: corpus absent           -> test  FAILS" 1 setup_no_corpus test

# INNOCENCE — present and green must stay green.
run_case "innocence: all present, green  -> check PASSES" 0 setup_judge_green check
run_case "innocence: all present, green  -> test  PASSES" 0 setup_judge_green test

# The gate must not flatten the judge's verdict into its own.
run_case "propagates judge rc=3          -> check returns 3" 3 setup_judge_red check
run_case "propagates pytest rc=3         -> test  returns 3" 3 setup_judge_red test

# Misuse is neither guilt nor innocence — it is a caller bug and must be loud.
run_case "usage: no mode                 -> rc 2" 2 setup_bare ""

echo "----"
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
