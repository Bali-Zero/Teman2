#!/usr/bin/env bash
# test_detect_secrets_diff_scope.sh — guilt+innocence corpus for audit lever
# L3 (research/operations/2026-08-21-token-ceremony-ci-system-audit.md §7):
# the `detect-secrets` job in security.yml scans only a PR's changed files
# on pull_request/merge_group, and the full tree on every other event
# (schedule, workflow_dispatch, push).
#
# This does NOT execute the workflow YAML — it re-derives the exact same two
# commands the job runs (hotzone_changed_files.sh for the file list,
# `detect-secrets scan` with explicit paths vs no paths) against a synthetic
# git repo, on a fresh throwaway baseline so detect-secrets' default plugin
# set decides, independent of this repo's real .secrets.baseline / auto-
# triage rules.
#
# Fixture: two commits.
#   commit A: unchanged.py, carrying a fake AWS-key-shaped secret. Stands in
#             for "a secret already on main, in a file this PR never touches".
#   commit B (head): changed.py, carrying a DIFFERENT fake secret. Stands in
#             for "what this PR's diff actually adds".
#
# Both fixtures use the obviously-fake pattern AKIAFAKEFAKEFAKE000N — matches
# detect-secrets' AWSKeyDetector shape (AKIA + 16 alnum) without resembling a
# real credential (never plant a real-looking one, per this file's own
# mandate).
#
# Assertions:
#   1. GUILT   (PR path):      changed.py's secret is scanned and unaudited.
#   2. INNOCENCE (PR path):    unchanged.py's secret is NOT in that scan's
#                               results at all — the PR-path baseline never
#                               even looked at the file.
#   3. GUILT   (nightly path): a full-tree scan (no path args, the "else"
#                               branch of "Run detect-secrets scan") finds
#                               BOTH secrets — the file the PR never touched
#                               IS caught by the nightly net.
#   4. hotzone_changed_files.sh itself reports exactly [changed.py] for this
#      fixture (merge-base = commit A, head = commit B) — the same
#      enumerator "Decide scan scope" calls.
#
# Run: bash scripts/tests/test_detect_secrets_diff_scope.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOTZONE="${REPO_ROOT}/scripts/ci/hotzone_changed_files.sh"

PASS=0
FAIL=0
ok()  { PASS=$((PASS + 1)); printf '  \xe2\x9c\x93 %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  \xe2\x9c\x97 %s\n' "$1"; }

if ! command -v detect-secrets >/dev/null 2>&1; then
  echo "SKIP: detect-secrets CLI not installed in this environment"
  exit 0
fi

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

cd "${WORKDIR}" || exit 1
git init -q
git config user.email "test@example.com"
git config user.name "test"

echo "print('base')" > base.py
git add base.py
git commit -q -m base

printf 'AWS_KEY = "AKIAFAKEFAKEFAKE0001"\n' > unchanged.py
git add unchanged.py
git commit -q -m "add unchanged.py (pre-existing secret)"
A_SHA="$(git rev-parse HEAD)"

printf 'AWS_KEY = "AKIAFAKEFAKEFAKE0002"\n' > changed.py
git add changed.py
git commit -q -m "add changed.py (this PR's diff)"
HEAD_SHA="$(git rev-parse HEAD)"

echo "── enumerator: hotzone_changed_files.sh must report exactly [changed.py]"
ENUM_OUT="$(bash "${HOTZONE}" "${A_SHA}" "${HEAD_SHA}" 2>/dev/null || true)"
if [ "${ENUM_OUT}" = "changed.py" ]; then
  ok "hotzone reports exactly changed.py"
else
  bad "hotzone reported [${ENUM_OUT}], expected [changed.py]"
fi

echo "── PR path: scan only changed.py (mirrors 'Run detect-secrets scan' diff branch)"
detect-secrets scan changed.py > pr_baseline.json 2>pr_scan.err || true
PR_FILES="$(python3 -c "import json;print(sorted(json.load(open('pr_baseline.json'))['results'].keys()))" 2>/dev/null || echo ERROR)"

if printf '%s' "${PR_FILES}" | grep -q "'changed.py'"; then
  ok "GUILT (PR path): changed.py's planted secret is scanned"
else
  bad "GUILT (PR path) missed: changed.py absent from PR-scoped results (${PR_FILES})"
fi

if printf '%s' "${PR_FILES}" | grep -q "'unchanged.py'"; then
  bad "INNOCENCE (PR path) violated: unchanged.py appeared in a PR-scoped scan that never named it (${PR_FILES})"
else
  ok "INNOCENCE (PR path): unchanged.py never entered the PR-scoped baseline"
fi

echo "── nightly path: full-tree scan (mirrors the 'else' branch, no path args)"
detect-secrets scan --exclude-files '\.git/.*' > full_baseline.json 2>full_scan.err || true
FULL_FILES="$(python3 -c "import json;print(sorted(json.load(open('full_baseline.json'))['results'].keys()))" 2>/dev/null || echo ERROR)"

if printf '%s' "${FULL_FILES}" | grep -q "'changed.py'" && printf '%s' "${FULL_FILES}" | grep -q "'unchanged.py'"; then
  ok "GUILT (nightly path): full-tree scan catches BOTH changed.py and unchanged.py"
else
  bad "GUILT (nightly path) missed a file: got ${FULL_FILES}, expected both changed.py and unchanged.py"
fi

echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
if [ "${FAIL}" -gt 0 ]; then
  exit 1
fi
exit 0
