#!/usr/bin/env bash
# test_deploy_lifecycle_doc.sh — pins that `apps/backend-rag/CLAUDE.md` §11
# names `.github/workflows/fly-deploy.yml` as the deploy SSOT and says a merge
# to main already deploys (PENDING-ARMS L1471, opened 2026-08-25).
#
# THE DEFECT: §11 gave a manual `fly deploy` as THE deploy lifecycle and never
# mentioned that pushing to main already triggers the same deploy via CI — so
# following the doc after merging fires a second, racing deploy. This test
# fails on the pre-fix doc (no mention of the workflow / auto-deploy) and
# passes once §11 names it and calls the manual path break-glass-only.
#
# Run:  bash scripts/tests/test_deploy_lifecycle_doc.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOC="$REPO_ROOT/apps/backend-rag/CLAUDE.md"
WORKFLOW="$REPO_ROOT/.github/workflows/fly-deploy.yml"
PASS=0
FAIL=0

ok()  { PASS=$((PASS + 1)); printf '  ✅ %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  ❌ %s\n' "$1"; }

if [ ! -f "$DOC" ]; then
    echo "❌ $DOC not found"
    exit 1
fi

SECTION="$(sed -n '/^## 11\. Deploy Lifecycle/,/^## 12\./p' "$DOC")"
if [ -z "$SECTION" ]; then
    echo "❌ could not extract §11 Deploy Lifecycle from $DOC"
    exit 1
fi

case "$SECTION" in
    *"fly-deploy.yml"*) ok "§11 names fly-deploy.yml as the deploy workflow" ;;
    *) bad "§11 never mentions .github/workflows/fly-deploy.yml" ;;
esac

case "$SECTION" in
    *"already deploys"*) ok "§11 states a merge to main already deploys" ;;
    *) bad "§11 does not say a merge to main already deploys" ;;
esac

case "$SECTION" in
    *"break-glass"*) ok "§11 marks the manual fly deploy as break-glass, not routine" ;;
    *) bad "§11 does not demote the manual fly deploy to break-glass" ;;
esac

# Cross-check the doc's claim against the live workflow trigger — a stale doc
# that merely says the right words with a workflow that no longer matches
# would still be a phantom (scar #6).
if [ -f "$WORKFLOW" ] && grep -q 'branches: \[main\]' "$WORKFLOW" && grep -q 'apps/backend-rag/\*\*' "$WORKFLOW"; then
    ok "fly-deploy.yml still triggers on push to main scoped to apps/backend-rag/**"
else
    bad "fly-deploy.yml no longer matches the doc's claim (trigger drifted) -> re-check §11"
fi

echo "────────────────────────────────────────────────────────────────────────"
echo "  passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
