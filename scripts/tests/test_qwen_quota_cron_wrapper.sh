#!/usr/bin/env bash
# Guilt + innocence for scripts/qwen_quota_watch_cron.sh.
#
# The defect this pins (found by prove-live on Mini, 2026-08-21, before the
# cron was armed): the wrapper hardcoded `--hosts mini,air`, which is Pro's
# complement. Run on Mini it therefore never even ATTEMPTED Pro and reported
# 71,411,936 tokens as a complete reading against the true 79,556,338 — with
# no "MISSED:" line, because a host absent from the list is never missed, it
# is simply never asked about. That is a silent coverage hole in the one tool
# whose entire contract is to declare its coverage.
#
# Guilt   : narrowing the host list, or hardcoding a machine-specific repo
#           path, must fail.
# Innocence: the shipped wrapper passes.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$REPO_ROOT/scripts/qwen_quota_watch_cron.sh"
fails=0

check() {  # check <label> <expect-pass|expect-fail> <file>
    local label="$1" expect="$2" file="$3" rc=0
    # The wrapper must ask for all three fleet aliases; the watcher self-skips
    # whichever one names the running host, so this is the only list that is
    # correct from every machine.
    grep -Eq -- '--hosts[[:space:]]+pro,mini,air' "$file" || rc=1
    # And it must not carry a literal checkout path: Mini is ~/nuzantara,
    # Pro is ~/Desktop/nuzantara, so any literal is wrong on some host.
    grep -Eq 'REPO="?/Users/' "$file" && rc=1
    if [ "$expect" = "expect-pass" ] && [ "$rc" -ne 0 ]; then
        echo "FAIL[$label]: shipped wrapper rejected (rc=$rc)"; fails=$((fails+1))
    elif [ "$expect" = "expect-fail" ] && [ "$rc" -eq 0 ]; then
        echo "FAIL[$label]: mutant accepted — the check does not bite"; fails=$((fails+1))
    else
        echo "ok[$label]"
    fi
}

[ -f "$WRAPPER" ] || { echo "FAIL: wrapper missing at $WRAPPER"; exit 1; }

# innocence — the real file
check innocence expect-pass "$WRAPPER"

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# guilt 1 — the exact historical defect: Pro's complement, run anywhere else
sed 's/--hosts pro,mini,air/--hosts mini,air/' "$WRAPPER" > "$tmp/narrowed.sh"
check guilt-narrowed-host-list expect-fail "$tmp/narrowed.sh"

# guilt 2 — a machine-specific checkout path
sed 's#^REPO=.*#REPO="/Users/nuzantara/nuzantara"#' "$WRAPPER" > "$tmp/hardcoded.sh"
check guilt-hardcoded-repo-path expect-fail "$tmp/hardcoded.sh"

# the wrapper must also still be valid bash
bash -n "$WRAPPER" || { echo "FAIL: wrapper is not valid bash"; fails=$((fails+1)); }

[ "$fails" -eq 0 ] && { echo "PASS (1 innocence, 2 guilt)"; exit 0; }
echo "FAILED: $fails"; exit 1
