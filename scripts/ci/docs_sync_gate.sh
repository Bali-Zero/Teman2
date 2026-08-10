#!/usr/bin/env bash
# Fail-closed existence gate for the `check-docs-sync` required check.
#
# WHY THIS IS NOT INLINE YAML ANY MORE (2026-08-10, found by the Merge-OS v2
# refutation round, Codex F4 — see research/operations/2026-08-10-merge-os-v2-submission-system.md §8.2):
# both branches of the inline version ended in `exit 0` when their target file
# was missing:
#
#     if [ ! -f scripts/docs_sync.py ]; then
#       echo "scripts/docs_sync.py is absent — skipping docs-sync check."
#       exit 0
#     fi
#
# `scripts/docs_sync.py` and `scripts/tests/test_docs_sync_atlas.py` are both in
# this workflow's `paths:` filter, so a PR that DELETES them triggers the gate —
# and the gate waved it through green. A required check that can be removed by
# the same diff it exists to stop is not a gate. Absence is now a FAILURE.
#
# A legitimate retirement of docs_sync removes this workflow in the SAME PR;
# `.github/workflows/` is CODEOWNERS-TIER1 and actionlint-gated, so that path
# stays reviewed by construction. There is no state in which the judge is gone
# and the verdict should still be green.
#
# Logic lives here rather than in a `run:` block because an `exit 0` inside YAML
# has no guilt test and no innocence test. Corpus:
# scripts/tests/test_docs_sync_gate_failclosed.sh
#
# Usage: docs_sync_gate.sh check|test     (run from the repo root)
#   check — the docs are in sync (judge: scripts/docs_sync.py)
#   test  — the judge's own unit tests pass (corpus: scripts/tests/test_docs_sync_atlas.py)
#
# PYTHON may override the interpreter (absolute path in CI contexts — W108:
# an alarm must not share the failure mode of the thing it reports).

set -uo pipefail

MODE="${1:-}"
PYTHON="${PYTHON:-python}"

require_file() {
  local target="$1"
  if [ ! -f "$target" ]; then
    echo "docs-sync gate FAILED: ${target} is ABSENT." >&2
    echo "  This check is required, so its judge cannot be deleted while it is armed." >&2
    echo "  If retiring docs-sync is intentional, remove .github/workflows/docs-sync.yml" >&2
    echo "  in the SAME pull request. Skipping here would let a diff delete its own gate." >&2
    return 1
  fi
  return 0
}

case "$MODE" in
  check)
    require_file "scripts/docs_sync.py" || exit 1
    "$PYTHON" scripts/docs_sync.py --check
    exit $?
    ;;
  test)
    require_file "scripts/tests/test_docs_sync_atlas.py" || exit 1
    "$PYTHON" -m pytest scripts/tests/test_docs_sync_atlas.py -q
    exit $?
    ;;
  *)
    echo "usage: $0 check|test" >&2
    exit 2
    ;;
esac
