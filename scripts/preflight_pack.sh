#!/usr/bin/env bash
# preflight_pack.sh — the BLOCKING local preflight. Owed since 2026-09-12
# (PENDING-ARMS "owed mechanism (6a)"); built 2026-09-17.
#
# WHY IT EXISTS, measured and not assumed. In the window #6633 -> #6682
# (7.96h, 47 PR attempts) SEVEN PRs were closed on a DETERMINISTIC red and
# re-opened as successors carrying byte-identical content: 15% of all attempts,
# 33.7% of PR-open time. Two of them (#6664, #6665) died after 6 and 4 minutes
# on a MISSING YAML FRONTMATTER LINE, and the checker that would have named it
# — scripts/check_adversarial_review.py — was already on disk, runnable, and
# selftested in 0.21s. Nothing ran it before the push.
#
# WHY NOT quickcheck.sh. quickcheck is ADVISORY BY DESIGN (S12 C4) and its
# exit code is unconditionally 0; that is deliberate, documented, and NOT a
# defect to be "fixed" — decapitating it would recreate the W101 shape. It also
# checks the wrong OBJECT for this class: its check_r1_heading() looks for the
# literal '## Adversarial review' in the PR BODY, while the CI gate that
# actually killed #6664/#6665 requires `adversarial_review:` in the FILE's YAML
# frontmatter. Two different objects. This script sits ABOVE quickcheck in the
# hook, blocks, and leaves quickcheck's `|| true` exactly as it is.
#
# WHAT IT RUNS (slice 2, contract_verify): nothing of its own. The predicate is
# DATA — scripts/ci/contract_checks.yml, one row per REQUIRED CI context that
# has killed a PR, each naming the script CI itself runs — executed by
# scripts/contract_verify.py --local. A row runs ONLY when the push carries the
# files it governs; a floor-1 push touching nothing governed exits 0 in silence.
# The replay fixture (scripts/tests/fixtures/contract_replay_expected.yml) pins
# that table to what CI actually judged on the closed heads.
#
# FAIL-OPEN ON INFRASTRUCTURE, FAIL-CLOSED ON VERDICTS — declared, not implied.
# A check that RUNS and FAILS refuses the push. A check that CANNOT run (no
# python3, no actionlint, no git) prints INCONCLUSIVE and exits 0. Rationale: a
# brand-new gate that refuses pushes on an offline laptop gets switched off
# within a day, and a gate everyone disables protects nothing. The kill switch
# is PREFLIGHT_PACK_SKIP=1 and it is named in the output so nobody has to go
# looking for it in anger.
#
# STDIN: this script NEVER reads stdin. The pre-push hook slurps git's ref
# protocol into a file once (.husky/pre-push, PREPUSH_REFS) precisely because a
# stream serves exactly one reader; this script is the THIRD reader of that
# FILE, after the path-aware gate and the tip-drift check.
#
# Testability seam: PREFLIGHT_PACK_LIB=1 sources the functions without running
# main, so scripts/tests/test_preflight_pack.sh can drive them with a crafted
# file list (guilt + innocence, superscar #3).

set -uo pipefail

PREFLIGHT_ROOT="${PREFLIGHT_PACK_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}"

preflight_changed_files() {
    # $1 = path to the captured pre-push refs file (may be empty/missing).
    # Emits the union of files this push contributes over origin/main, one per
    # line. Falls back to origin/main...HEAD when the refs file is unusable —
    # declared as a fallback, never silently.
    local refs_file="${1:-}" zero="0000000000000000000000000000000000000000"
    local seen=0 base

    if [ -n "$refs_file" ] && [ -s "$refs_file" ]; then
        while read -r local_ref local_sha remote_ref remote_sha; do
            [ -z "${local_ref:-}" ] && continue
            [ "${local_sha:-}" = "$zero" ] && continue   # ref deletion
            [ -z "${local_sha:-}" ] && continue
            seen=$((seen + 1))
            base="$(git -C "$PREFLIGHT_ROOT" merge-base origin/main "$local_sha" 2>/dev/null)" || base=""
            [ -z "$base" ] && continue
            git -C "$PREFLIGHT_ROOT" diff --name-only --diff-filter=d "$base" "$local_sha" 2>/dev/null
        done < "$refs_file"
    fi

    if [ "$seen" -eq 0 ]; then
        git -C "$PREFLIGHT_ROOT" diff --name-only --diff-filter=d origin/main...HEAD 2>/dev/null
    fi
}

preflight_span() {
    # $1 = refs file. Echoes "BASE HEAD" when the push carries exactly ONE ref
    # (the normal case), so contract_verify gets a numstat-bearing diff and the
    # floor's SIZE term is asserted; echoes nothing for a multi-ref or unusable
    # push, and the caller falls back to the file union with a path-only floor.
    local refs_file="${1:-}" zero="0000000000000000000000000000000000000000"
    local n=0 sha="" base
    if [ -n "$refs_file" ] && [ -s "$refs_file" ]; then
        while read -r local_ref local_sha remote_ref remote_sha; do
            [ -z "${local_ref:-}" ] && continue
            [ "${local_sha:-}" = "$zero" ] && continue
            [ -z "${local_sha:-}" ] && continue
            n=$((n + 1)); sha="$local_sha"
        done < "$refs_file"
    fi
    [ "$n" -eq 0 ] && sha="HEAD" && n=1
    [ "$n" -ne 1 ] && return 0
    base="$(git -C "$PREFLIGHT_ROOT" merge-base origin/main "$sha" 2>/dev/null)" || return 0
    [ -n "$base" ] && printf '%s %s' "$base" "$sha"
}

preflight_run_checks() {
    # Reads the changed-file list on STDIN (one path per line) and hands it to
    # the ONE predicate: scripts/contract_verify.py --local over the table in
    # scripts/ci/contract_checks.yml. Returns 0 when nothing is wrong or nothing
    # applies, 1 when a check ran and FAILED. This function owns no check of its
    # own any more (slice 2): a check hard-coded here would be a second predicate,
    # and two predicates drift — the replay fixture pins the table to CI, it
    # cannot pin a bash function.
    local files out rc=0
    files="$(cat)"
    [ -z "$files" ] && return 0

    if ! command -v python3 >/dev/null 2>&1; then
        echo "   ⚠️  preflight_pack INCONCLUSIVE — no python3 on PATH; the contract table cannot run."
        return 0
    fi
    if [ ! -f "$PREFLIGHT_ROOT/scripts/contract_verify.py" ]; then
        echo "   ⚠️  preflight_pack INCONCLUSIVE — scripts/contract_verify.py is not in this tree."
        return 0
    fi

    if [ -n "${PREFLIGHT_SPAN:-}" ]; then
        # shellcheck disable=SC2086
        out="$(CONTRACT_VERIFY_ROOT="$PREFLIGHT_ROOT" python3 "$PREFLIGHT_ROOT/scripts/contract_verify.py" --local --span $PREFLIGHT_SPAN 2>&1)"; rc=$?
    else
        out="$(printf '%s\n' "$files" | CONTRACT_VERIFY_ROOT="$PREFLIGHT_ROOT" python3 "$PREFLIGHT_ROOT/scripts/contract_verify.py" --local --files-from - 2>&1)"; rc=$?
    fi

    if [ -n "$out" ]; then
        echo "🛡  preflight_pack — scripts/ci/contract_checks.yml against this push (skip: PREFLIGHT_PACK_SKIP=1)"
        printf '%s\n' "$out"
    fi

    if [ "$rc" -ne 0 ]; then
        echo ""
        echo "   ⛔ PUSH REFUSED. Every red above is DETERMINISTIC: CI runs the same script on the same files."
        echo "      Fix it here — it is one commit. After arming, the branch is frozen and the"
        echo "      same fix costs a closed PR and a successor (7 of 47 attempts in the audited window)."
        echo "      Override, if you know why: PREFLIGHT_PACK_SKIP=1 git push ..."
        return 1
    fi
    return 0
}

[ "${PREFLIGHT_PACK_LIB:-0}" = "1" ] && return 0 2>/dev/null

main() {
    [ "${PREFLIGHT_PACK_SKIP:-0}" = "1" ] && { echo "🛡  preflight_pack SKIPPED (PREFLIGHT_PACK_SKIP=1)"; return 0; }
    command -v git >/dev/null 2>&1 || { echo "⚠️  preflight_pack INCONCLUSIVE — no git on PATH."; return 0; }
    PREFLIGHT_SPAN="$(preflight_span "${1:-}")"
    preflight_changed_files "${1:-}" | sort -u | preflight_run_checks
}

main "$@"
