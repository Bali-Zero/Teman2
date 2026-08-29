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
#   2. Removes every `__pycache__` directory already sitting under this
#      checkout's first-party Python trees (SWEPT_TREES, below; vendored and
#      virtualenv trees are pruned — see PRUNED_DIRS for the measurement that
#      forced that) and VERIFIES the removal. A stale cache from a PRIOR run
#      (from before this wrapper existed, or from a process that bypassed it)
#      is exactly the poisoned state the self-canary exists to prove is now
#      impossible, and leaving it on disk would let it satisfy that proof for
#      the wrong reason. Critically: PYTHONDONTWRITEBYTECODE suppresses
#      WRITES, never READS — so the env var alone does not make an
#      already-poisoned checkout safe. THE SWEEP IS WHAT DOES, and it is only
#      as good as SWEPT_TREES.
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
#      exported into it, and propagates its exit code — captured via
#      `set +e; "$@"; rc=$?; set -e` (never a bare assignment under `set -e`,
#      which would abort ON the very failure it exists to report — cicatrix
#      W101, "pre-push fail-closed decapitated by sh -e").
#   6. POST-RUN, re-checks SWEPT_TREES for `__pycache__`. The canary proves
#      the environment was hermetic BEFORE the command; only this proves the
#      command did not defeat it (`env -u PYTHONDONTWRITEBYTECODE`, a
#      conftest setting `sys.dont_write_bytecode = False`, `python -E`, a
#      different interpreter, a subprocess that rebuilds its env). A green
#      produced under a defeated environment exits 3 instead of 0; a red
#      keeps its own exit code and gets a loud warning, because its code
#      carries more information than a generic 3.
#
# WHAT THIS CANNOT DO, stated because a wrapper that overclaims is the same
# failure as the one it guards against:
#   - It cannot stop a hostile command from defeating the environment; it can
#     only DETECT that one did, after the fact, via step 6.
#   - It cannot see bytecode read from outside SWEPT_TREES (a stale cache in
#     an instrument's own dependency tree, say). The corpus pins SWEPT_TREES
#     against the one instrument declared today; a future instrument that
#     imports from elsewhere needs the list extended, and the corpus is what
#     will say so.
#   - Exit-code propagation is "whatever bash reports as the command's exit
#     status", not a faithful re-raise: a command killed by SIGTERM surfaces
#     as a NORMAL exit 143 from this wrapper, not as the same wait-status.
#     The distinction matters only to a caller inspecting wait-status
#     directly; no caller in this repo does.
#
# Usage:
#   scripts/hermetic_verify.sh --self-test-only
#   scripts/hermetic_verify.sh -- <command...>
#   scripts/hermetic_verify.sh --self-test-only -- <command...>   (canary only; command ignored)
#
# Exit codes:
#   0  canary passed (and, unless --self-test-only, the given command exited 0)
#   2  usage error — no `--` / no command given (an empty command is never a pass)
#   3  ENVIRONMENT NOT HERMETIC — one of: the pre-flight sweep could not
#      remove a stale cache; the self-canary detected bytecode reuse; or the
#      post-run check found the command wrote bytecode despite the export
#      (i.e. it defeated the environment) while exiting 0. Any number
#      produced under this state is a filesystem artifact, not a measurement
#      (W121)
#   *  whatever the given command exited with (see the propagation caveat above)
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
#
# SWEPT_TREES is the load-bearing constant of this whole script, and it was
# WRONG on first write: it listed `scripts apps` while
# scripts/mutation_incremental.py mutates `("apps/", "scripts/", "packages/")`
# (its `include_glob` default). PYTHONDONTWRITEBYTECODE forbids WRITING a
# .pyc; it does NOT forbid READING one that is already on disk. So a stale
# cache under packages/ survived the sweep, was reused by the measurement, and
# the canary — which runs in its own temp dir — passed anyway: the wrapper
# reported a hermetic environment over a poisoned one. That is this script's
# own disease, inside its cure. Found by the cross-family refuter on the
# finished diff, verified here against the driver's source before believing it.
#
# The list is NOT derived from any one instrument (this wrapper is generic —
# it wraps whatever measurement instrument it is handed). It is this repo's
# first-party importable Python, and scripts/tests/test_hermetic_census.py
# pins it as a SUPERSET of mutation_incremental.py's include_glob, so an
# instrument that grows a tree this sweep does not cover fails the corpus
# instead of silently measuring on stale bytecode.
SWEPT_TREES="scripts apps packages infra"

# PRUNED_DIRS is not tidiness, it is correctness, and the number is why.
# Measured on the main checkout 2026-08-29: `apps/` holds 3679 __pycache__
# dirs, of which 3216 (87%) live inside a virtualenv or node_modules. A sweep
# that deletes those costs minutes of pointless recompilation on every single
# invocation and buys nothing — the instruments mutate FIRST-PARTY source
# only (mutation_incremental.py's include_glob is apps/, scripts/, packages/),
# so a site-packages .pyc cannot be stale with respect to a mutation that
# never touches its source. It also widens the failure surface of the
# verified-removal check below, where one undeletable vendor cache would abort
# a legitimate run. This prune predates nothing: the ORIGINAL `for _tree in
# scripts apps` had exactly this behaviour, and hardening the sweep without
# measuring first would have amplified it.
PRUNED_DIRS=".venv venv node_modules site-packages .git"

_find_pycache() {
  # Prints, NUL-separated, every __pycache__ dir under $1 outside PRUNED_DIRS.
  _root="$1"
  set -- "$_root"
  for _pd in $PRUNED_DIRS; do
    set -- "$@" -name "$_pd" -o
  done
  # Drops the trailing -o and closes the group; the result is
  #   find <root> \( -name .venv -o ... -name .git \) -prune -o -type d -name __pycache__ -print0
  # built without arrays (bash 3.2 is the floor here — see the arg-parsing note).
  find "$_root" \( "${@:2:$(($#-2))}" \) -prune -o -type d -name '__pycache__' -print0 2>/dev/null
}

_count_pycache() {
  # Echoes the number of __pycache__ dirs currently under SWEPT_TREES.
  _c=0
  for _t in $SWEPT_TREES; do
    _d="$REPO_ROOT/$_t"
    [ -d "$_d" ] || continue
    _k="$(_find_pycache "$_d" | tr -dc '\0' | wc -c | tr -d ' ')"
    _c=$((_c + _k))
  done
  echo "$_c"
}

_sweep_pycache() {
  for _t in $SWEPT_TREES; do
    _d="$REPO_ROOT/$_t"
    [ -d "$_d" ] || continue
    _find_pycache "$_d" | xargs -0 rm -rf 2>/dev/null || true
  done
}

pycache_count="$(_count_pycache)"
if [ "$pycache_count" -gt 0 ]; then
  _sweep_pycache
  # VERIFY the removal. `rm -rf ... || true` reports success whether or not the
  # directory is gone: a cache that cannot be deleted (permissions, a
  # read-only mount, a concurrent writer) would otherwise leave the same false
  # green this script exists to make impossible.
  _left="$(_count_pycache)"
  if [ "$_left" -gt 0 ]; then
    echo "$_prog: SWEEP FAILED — $_left __pycache__ dir(s) under [$SWEPT_TREES] survived removal, so a stale .pyc can still be READ by the measurement below (PYTHONDONTWRITEBYTECODE suppresses writes, never reads). Refusing to certify this environment as hermetic (W121)." >&2
    exit 3
  fi
  echo "$_prog: removed $pycache_count stale __pycache__ dir(s) under [$SWEPT_TREES] before running — a cache left from before this wrapper existed is unverifiable, not merely undesirable (W121)" >&2
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

# ------------------------------------------------------------- 6. post-run proof
# The canary proves the environment was hermetic BEFORE the command; it cannot
# prove the command kept it that way. Every one of these defeats it, and none
# is exotic: `env -u PYTHONDONTWRITEBYTECODE python3 ...`, a conftest.py
# setting `sys.dont_write_bytecode = False`, `python -E`, a different
# interpreter, or a subprocess that rebuilds its own environment. The refuter
# raised this as an accepted limitation; a limitation that can be MEASURED
# should be measured instead of declared. If any __pycache__ exists under
# SWEPT_TREES after the command, bytecode was written while the wrapper was
# supposedly forbidding it, so the environment was defeated during the run.
_after="$(_count_pycache)"
if [ "$_after" -gt 0 ]; then
  _sweep_pycache
  if [ "$rc" -eq 0 ]; then
    # A PASS produced under a defeated environment is exactly the artifact this
    # script exists to stop. Do not let it read as success.
    echo "$_prog: POST-RUN CHECK FAILED — the command exited 0, but $_after __pycache__ dir(s) appeared under [$SWEPT_TREES] while PYTHONDONTWRITEBYTECODE=1 was exported. Something in the command re-enabled bytecode writing (env -u, python -E, a nested interpreter, or sys.dont_write_bytecode), so its output was NOT produced under the hermetic environment this wrapper certified. Refusing to report success (W121)." >&2
    exit 3
  fi
  # The command already failed. Its exit code carries more information than a
  # generic 3 would, so propagate it and make the second fact loud rather than
  # overwriting the first.
  echo "$_prog: WARNING — $_after __pycache__ dir(s) appeared under [$SWEPT_TREES] during a command that exited $rc; the environment was defeated mid-run, so this failure may itself be a filesystem artifact (W121)." >&2
fi

exit "$rc"
