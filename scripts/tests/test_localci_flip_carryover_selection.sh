#!/usr/bin/env bash
# The flip runbook's carry-over command (scripts/localci/README.md) selects only user arms that lack the label.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
filter=$(grep -m1 '^gh pr list .*--limit 500' "$ROOT/scripts/localci/README.md" | sed -E "s/.*--jq '([^']*)' \\|.*/\\1/")
[ -n "$filter" ] || { echo "FAIL: carry-over jq filter not found in README"; exit 1; }
fixture='[
 {"number":1,"labels":[],"autoMergeRequest":{"enabledBy":{"login":"alice","is_bot":false}}},
 {"number":2,"labels":[],"autoMergeRequest":{"enabledBy":{"login":"github-actions","is_bot":true}}},
 {"number":3,"labels":[{"name":"localci:merge-shadow-ok"}],"autoMergeRequest":{"enabledBy":{"login":"alice","is_bot":false}}},
 {"number":4,"labels":[],"autoMergeRequest":null}
]'
got=$(printf '%s' "$fixture" | jq -r "$filter")
[ "$got" = "1 alice" ] || { echo "FAIL: expected '1 alice', got '$got'"; exit 1; }
echo "PASS"
