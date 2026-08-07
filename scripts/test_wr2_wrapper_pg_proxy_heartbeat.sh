#!/usr/bin/env bash
# Runtime Truth case transport for scripts/wr2-cron-wrapper.sh.
#
# This child deliberately emits NO pass/fail evidence. The Python gauntlet is
# the independent observer: it builds one fake world per exact case, invokes
# this transport once, then derives the verdict from the real wrapper's exit
# code and heartbeat sidecar. A child that prints hardcoded PASS receipts or
# exits zero without invoking the wrapper therefore cannot certify itself.
#
# Usage is internal to scripts/runtime_truth_ci_gauntlet.py:
#   bash scripts/test_wr2_wrapper_pg_proxy_heartbeat.sh <exact-case-id>

set -euo pipefail

case_id="${1:-}"
case "$case_id" in
    pg_proxy_unreachable|\
    database_url_local_missing|\
    pg_proxy_reachable|\
    heartbeat_self_heal)
        ;;
    *)
        printf 'unknown Runtime Truth shell case: %s\n' "$case_id" >&2
        exit 64
        ;;
esac

: "${RUNTIME_TRUTH_WRAPPER:?RUNTIME_TRUTH_WRAPPER is required}"
: "${RUNTIME_TRUTH_MODULE:?RUNTIME_TRUTH_MODULE is required}"

exec bash "$RUNTIME_TRUTH_WRAPPER" "$RUNTIME_TRUTH_MODULE"
