#!/usr/bin/env bash
# scripts/hermetic_verify.sh — hermetic environment for measurement instruments.
#
# WHY THIS EXISTS (cicatrix-scars.md W121, "mutation testing on poisoned
# bytecode"). Python validates a `.pyc` against its source by comparing
# mtime + size ONLY. A mutation-testing cycle of the shape "mutate -> run
# tests -> restore" is silently corrupted whenever (a) the mutation does not
# change the source's byte length (`return 1` -> `return 0` is the textbook
# case — this exact instrument mutates operators the same way) and (b) the
# mutate-and-restore happens inside the same one-second mtime resolution.
# Both conditions are the NORM for a fast mutation loop, not the exception.
# When they hold, a source file can be mutated and restored while its `.pyc`
# on disk keeps the OLD mtime+size pair recorded at compile time, and Python
# reuses that stale bytecode without recompiling — silently, in EITHER
# direction: a survivor gets reported as a kill (a corpus that never saw the
# fix printed as evidence it caught a bug), or a real kill gets reported as
# a survivor (a healthy corpus gets "strengthened" against a mutation that
# never actually ran). Measured on this repo, 2026-08-21: a mutation run's
# reported kill-count was a filesystem artifact, not a measurement.
#
# `scripts/mutation_incremental.py` (this repo's INCREMENTAL mutation
# driver, `.github/workflows/p1s2-mutation-incremental.yml`) mutates and
# restores source files in exactly this shape and, at the time this wrapper
# was written, carried ZERO occurrences of PYTHONDONTWRITEBYTECODE,
# dont_write_bytecode, __pycache__, or cacheprovider (grepped, not assumed)
# — i.e. every number it has ever produced was exposed to this trap.
#
# WHAT THIS DOES, in order:
#   1. Exports PYTHONDONTWRITEBYTECODE=1 (no .pyc is ever WRITTEN — the
#      structural fix: nothing can go stale if nothing is ever cached) and
#      unsets PYTHONPYCACHEPREFIX (an inherited redirect target would make
#      the write-suppression above meaningless for whatever path it points
#      at). Also exports PYTEST_ADDOPTS with `-p no:cacheprovider` PREPENDED
#      (never rewrites the caller's command line — a command that is not
#      pytest simply ignores the env var).
#   2. Removes any `__pycache__` directory already sitting under scripts/ or
#      apps/ in THIS checkout — a stale cache from a PRIOR run (before this
#      wrapper existed, or from a process that bypassed it) is exactly the
#      poisoned state the self-canary below exists to prove is now
#      impossible, and leaving it on disk would let it silently satisfy
#      that proof for the wrong reason.
#   3. Runs a SELF-CANARY that reproduces W121's exact shape in a throwaway
#      temp dir: write a probe module returning 11111, import it fresh,
#      mutate it to return 22222 PRESERVING BYTE LENGTH, restore its mtime
#      to the pre-mutation value with `touch -r`, then import it again in a
#      fresh interpreter. Under a genuinely hermetic environment nothing was
#      ever cached in step 1's dir, so the second import MUST recompile from
#      source and print 22222; printing 11111 means bytecode is being reused
#      despite PYTHONDONTWRITEBYTECODE, and NO number produced downstream of
#      that state is trustworthy — this is what earns the environment the
#      word "hermetic" rather than merely "configured".
#   4. If --self-test-only, exits 0 here (canary passed; no command to run).
#   5. Otherwise runs the given command with the hermetic environment
#      exported into it, and propagates its exit code EXACTLY — captured
#      via `set +e; "$@"; rc=$?; set -e` (never a bare assignment under
#      `set -e`, which would abort ON the very failure it exists to report
#      — cicatrix W101, "pre-push fail-closed decapitated by sh -e").
#
# Usage:
#   scripts/hermetic_verify.sh --self-test-only
#   scripts/hermetic_verify.sh -- <command...>
#   scripts/hermetic_verify.sh --self-test-only -- <command...>   (canary only; command ignored)
#
# Exit codes:
#   0  canary passed (and, unless --self-test-only, the given command exited 0)
#   2  usage error — no `--` / no command given (an empty command is never a pass)
#   3  SELF-CANARY FAILED — bytecode reuse detected; the measurement
#      environment is compromised and any number produced under it is a
#      filesystem artifact, not a measurement (W121)
#   *  whatever the given command exited with, propagated exactly
set -euo pipefail

_prog="hermetic_verify.sh"

usage() {
  cat >&2 <<'USAGE_EOF'
Usage: hermetic_verify.sh [--self-test-only] -- <command...>
       hermetic_verify.sh --self-test-only          (canary only, no command)
USAGE_EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ------------------------------------------------------------- arg parsing
# No arrays for the command: `--self-test-only` alone leaves ZERO command
# words, and a bash-3.2 array with zero elements throws "unbound variable"
# under `set -u` when later expanded as "${arr[@]}" (measured on this exact
# bash — 3.2.57, macOS system default). "$@" / "$#" do NOT have this defect
# (also measured) — the remaining positional parameters ARE the command.
self_test_only=0
dashdash_seen=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --self-test-only)
      self_test_only=1
      shift
      ;;
    --)
      dashdash_seen=1
      shift
      break
      ;;
    -h|--help)
      usage
      exit 2
      ;;
    *)
      echo "$_prog: unexpected argument '$1' (expected --self-test-only and/or -- <command...>)" >&2
      usage
      exit 2
      ;;
  esac
done
# From here, "$@" is whatever followed `--` (possibly nothing).

# ------------------------------------------------------------- 1. hermetic env
export PYTHONDONTWRITEBYTECODE=1
unset PYTHONPYCACHEPREFIX 2>/dev/null || true
export PYTEST_ADDOPTS="-p no:cacheprovider${PYTEST_ADDOPTS:+ $PYTEST_ADDOPTS}"

# ------------------------------------------------------------- 2. pre-flight sweep
pycache_count=0
for _tree in scripts apps; do
  _target="$REPO_ROOT/$_tree"
  [ -d "$_target" ] || continue
  _n="$(find "$_target" -type d -name '__pycache__' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$_n" -gt 0 ]; then
    pycache_count=$((pycache_count + _n))
    find "$_target" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  fi
done
if [ "$pycache_count" -gt 0 ]; then
  echo "$_prog: removed $pycache_count stale __pycache__ dir(s) under scripts/ and apps/ before running — a cache left from before this wrapper existed is unverifiable, not merely undesirable (W121)" >&2
fi

# ------------------------------------------------------------- 3. self-canary
_probe_dir="$(mktemp -d "${TMPDIR:-/tmp}/hermetic-verify-canary.XXXXXX")"
_cleanup_probe() { rm -rf "$_probe_dir" 2>/dev/null || true; }
trap _cleanup_probe EXIT

_probe_py="$_probe_dir/probe.py"
printf '%s\n' 'def v():' '    return 11111' > "$_probe_py"

_run1_out="$(cd "$_probe_dir" && python3 -c 'import probe; print(probe.v())' 2>&1)" || {
  echo "$_prog: SELF-CANARY setup failed — could not import a fresh probe module: $_run1_out" >&2
  exit 3
}
if [ "$_run1_out" != "11111" ]; then
  echo "$_prog: SELF-CANARY setup failed — expected 11111 from the unmutated probe, got: $_run1_out" >&2
  exit 3
fi
_n_after_run1="$(find "$_probe_dir" -type d -name '__pycache__' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$_n_after_run1" -gt 0 ]; then
  echo "$_prog: SELF-CANARY FAILED — a __pycache__ appeared in the canary temp dir after the FIRST import; PYTHONDONTWRITEBYTECODE did not reach the child interpreter, so any number produced under this environment is a filesystem artifact, not a measurement (W121)" >&2
  exit 3
fi

# Mutate PRESERVING BYTE LENGTH ("11111" -> "22222", both 5 chars) and
# restore the EXACT pre-mutation mtime — this is the poisoning condition
# W121 measured: neither signal Python's staleness check looks at changes.
_mtime_ref="$_probe_dir/.mtime-ref"
touch -r "$_probe_py" "$_mtime_ref"
python3 - "$_probe_py" <<'PYEOF'
import sys
path = sys.argv[1]
text = open(path, "r").read()
mutated = text.replace("11111", "22222")
if mutated == text:
    raise SystemExit("hermetic_verify.sh: canary source did not contain the expected literal to mutate")
open(path, "w").write(mutated)
PYEOF
touch -r "$_mtime_ref" "$_probe_py"

_run2_out="$(cd "$_probe_dir" && python3 -c 'import probe; print(probe.v())' 2>&1)" || {
  echo "$_prog: SELF-CANARY setup failed — could not re-import the mutated probe module: $_run2_out" >&2
  exit 3
}
if [ "$_run2_out" = "11111" ]; then
  echo "$_prog: SELF-CANARY FAILED — probe.py was mutated (same byte length) and restored to its exact pre-mutation mtime, yet a fresh interpreter still returned the OLD value. Stale bytecode is being reused; any mutation-testing number produced under this environment is a filesystem artifact, not a measurement (cicatrix-scars.md W121). Refusing to proceed." >&2
  exit 3
fi
if [ "$_run2_out" != "22222" ]; then
  echo "$_prog: SELF-CANARY FAILED — expected 22222 from the mutated probe, got: $_run2_out" >&2
  exit 3
fi
_n_after_run2="$(find "$_probe_dir" -type d -name '__pycache__' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$_n_after_run2" -gt 0 ]; then
  echo "$_prog: SELF-CANARY FAILED — a __pycache__ appeared in the canary temp dir; PYTHONDONTWRITEBYTECODE did not reach the child interpreter even though the printed value happened to be correct — the environment is not hermetic (W121)" >&2
  exit 3
fi

_cleanup_probe
trap - EXIT

# ------------------------------------------------------------- 4. self-test-only exit
if [ "$self_test_only" -eq 1 ]; then
  echo "$_prog: SELF-CANARY passed — environment is hermetic (no stale bytecode reuse possible)"
  exit 0
fi

# ------------------------------------------------------------- 6. refuse an empty command
if [ "$dashdash_seen" -ne 1 ] || [ "$#" -eq 0 ]; then
  echo "$_prog: no command given — an empty command must never read as success" >&2
  usage
  exit 2
fi

# ------------------------------------------------------------- 5. run + propagate
set +e
"$@"
rc=$?
set -e
exit "$rc"
