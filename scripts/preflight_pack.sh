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
# SCOPE, deliberately narrow. It runs a check ONLY when the push actually
# carries the files that check governs. A push touching none of them exits 0
# in silence, so existing traffic is untouched.
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

preflight_run_checks() {
    # Reads the changed-file list on STDIN (one path per line). Returns 0 when
    # nothing is wrong or nothing applies, 1 when a check ran and FAILED.
    local files research workflows packs rc=0 out
    files="$(cat)"

    research="$(printf '%s\n' "$files" | grep -E '^research/.*\.md$' || true)"
    workflows="$(printf '%s\n' "$files" | grep -E '^\.github/workflows/' || true)"
    packs="$(printf '%s\n' "$files" | grep -E '^evidence/.*/pack\.ya?ml$' || true)"

    if [ -z "$research" ] && [ -z "$workflows" ] && [ -z "$packs" ]; then
        return 0   # silence: this push carries nothing these checks govern
    fi

    echo "🛡  preflight_pack — checking what CI would red on (skip: PREFLIGHT_PACK_SKIP=1)"

    if [ -n "$research" ]; then
        if ! command -v python3 >/dev/null 2>&1; then
            echo "   ⚠️  [R1] INCONCLUSIVE — no python3 on PATH; cannot check research frontmatter."
        else
            # shellcheck disable=SC2086
            if out="$(cd "$PREFLIGHT_ROOT" && printf '%s\n' "$research" | xargs python3 scripts/check_adversarial_review.py --files 2>&1)"; then
                echo "   ✅ [R1] research frontmatter OK ($(printf '%s\n' "$research" | grep -c .) file(s))"
            else
                echo "   ❌ [R1] adversarial-review frontmatter — this push would red the REQUIRED check 'R1 gate — adversarial review present':"
                printf '%s\n' "$out" | sed 's/^/        /'
                rc=1
            fi
        fi
    fi

    if [ -n "$packs" ]; then
        if ! command -v python3 >/dev/null 2>&1; then
            echo "   ⚠️  [BITES] INCONCLUSIVE — no python3 on PATH."
        else
            while IFS= read -r pack; do
                [ -z "$pack" ] && continue
                if out="$(cd "$PREFLIGHT_ROOT" && python3 scripts/ci/bites_parse.py --pack "$pack" 2>&1)"; then
                    echo "   ✅ [BITES] $pack parses"
                else
                    echo "   ❌ [BITES] $pack — this push would red the Harness floor pack lint:"
                    printf '%s\n' "$out" | sed 's/^/        /'
                    rc=1
                fi
            done <<< "$packs"
        fi
    fi

    if [ -n "$workflows" ]; then
        if ! command -v actionlint >/dev/null 2>&1; then
            echo "   ⚠️  [actionlint] INCONCLUSIVE — actionlint not installed."
        elif out="$(cd "$PREFLIGHT_ROOT" && actionlint 2>&1)"; then
            echo "   ✅ [actionlint] .github/workflows/ clean"
        else
            echo "   ❌ [actionlint] .github/workflows/ — this push would red the workflow lint:"
            printf '%s\n' "$out" | sed 's/^/        /'
            rc=1
        fi
    fi

    if [ "$rc" -ne 0 ]; then
        echo ""
        echo "   ⛔ PUSH REFUSED. Every red above is DETERMINISTIC: CI will reproduce it exactly."
        echo "      Fix it here — it is one commit. After arming, the branch is frozen and the"
        echo "      same fix costs a closed PR and a successor (7 of 47 attempts in the audited window)."
        echo "      Override, if you know why: PREFLIGHT_PACK_SKIP=1 git push ..."
    fi
    return "$rc"
}

[ "${PREFLIGHT_PACK_LIB:-0}" = "1" ] && return 0 2>/dev/null

main() {
    [ "${PREFLIGHT_PACK_SKIP:-0}" = "1" ] && { echo "🛡  preflight_pack SKIPPED (PREFLIGHT_PACK_SKIP=1)"; return 0; }
    command -v git >/dev/null 2>&1 || { echo "⚠️  preflight_pack INCONCLUSIVE — no git on PATH."; return 0; }
    preflight_changed_files "${1:-}" | sort -u | preflight_run_checks
}

main "$@"
