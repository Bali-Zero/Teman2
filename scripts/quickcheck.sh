#!/usr/bin/env bash
# scripts/quickcheck.sh — S12 C4 (2026-08-23): kill red CI rounds before they
# reach CI.
#
# WHY THIS EXISTS: measured the same day — red PR rounds whose cause is
# purely MECHANICAL (a prepush-guards miss, the adversarial-review-gate
# missing its heading, a Prettier diff) cost a lane ~30 minutes of
# wall-clock per round. This script names the same failure locally in
# minutes or seconds, wired ADVISORY-ONLY into `.husky/pre-push` (it WARNS,
# it NEVER blocks — see the bottom of this file and the call site in
# `.husky/pre-push`).
#
# SCOPE (four checks, each scoped to what actually changed vs origin/main):
#   1. impact-scoped pytest, via `scripts/ci/impact_map.py` (the SAME engine
#      the PR lane's test-selection uses) — only the backend test modules
#      the diff can actually reach, never the full 17k-test suite.
#   2. `prettier --check` on the changed files only (same extension scope as
#      package.json's own `format`/`format:check` scripts).
#   3. `actionlint` — only when `.github/workflows/` is touched, run with no
#      file args (same auto-discovery scope as `.github/workflows/actionlint.yml`).
#   4. R1 heading presence: if the current branch has an open PR, check its
#      body for the LITERAL line `## Adversarial review` — exact string,
#      anchored, case-sensitive. NOT a substring match on "adversarial":
#      cicatrix-superscar.md #3 catalogs ~20 scars in this repo caused by
#      exactly that shortcut (guard-over-match / under-match).
#
# NON-GOALS (deliberate):
#   - No CI-parity Postgres clone-per-run dance (that's `.husky/pre-push`'s
#     own heavy-suite machinery, opt-in via PREPUSH_FULL=1). A DB-dependent
#     scoped test may error here with a bare connection failure when no
#     local PG is provisioned — that is a known limitation, not a false
#     "your diff broke this" signal (see the note the pytest step itself
#     prints when it can't reach 127.0.0.1:5432).
#   - Never auto-dispatches the heavy suite to another machine. When the
#     impact map can't safely scope the diff, this prints an `ssh mini`
#     suggestion and stops — an M5/Pro scar exists where auto-dispatching
#     >3 heavy suites in a row produced false reds from resource contention.
#   - Never mutates git state, never pushes, never touches GitHub.
#
# GOTCHAS THIS FILE IS DELIBERATELY WRITTEN AROUND:
#   - Requires bash, not sh: the login shell on this fleet is zsh and the
#     production `.husky/pre-push` invocation is `sh -e` — neither has
#     bash's `${PIPESTATUS[@]}` (zsh's is `$pipestatus`, 1-indexed; POSIX
#     sh has neither), and this script needs real arrays. Declared via the
#     shebang; the guard below also fails soft under any interpreter where
#     $BASH_VERSION is unset instead of erroring confusingly mid-script.
#   - A pipe MASKS an exit code (cicatrix-superscar.md #2, W97-class): every
#     place below that needs a command's real exit status captures it into
#     a variable BEFORE piping the output through `sed` for indentation —
#     never `cmd | sed ...; rc=$?` (that would capture sed's own rc, always 0).
#   - `.git` inside a worktree is a FILE, not a directory — this script
#     never does `test -f .git/...`; it uses `git rev-parse --show-toplevel`
#     / `git rev-parse --git-dir` wherever it needs repo-root or git-dir.
#   - Sourcing this file (for `scripts/tests/test_quickcheck.sh`) must be
#     100% side-effect-free: every top-level statement outside `main` is
#     limited to the shebang, the bash-version guard, and the trailing
#     `[[ "${BASH_SOURCE[0]}" == "$0" ]]` dispatch. All repo/git/pytest work
#     lives inside functions, so `source scripts/quickcheck.sh` from a test
#     harness only defines functions — it runs nothing.
#
# Kill switch when wired into `.husky/pre-push`: QUICKCHECK_SKIP=1.
# Override the base ref (rare — testing/CI harness use): QUICKCHECK_BASE_REF.

if [ -z "${BASH_VERSION:-}" ]; then
    echo "quickcheck: requires bash (invoked under a non-bash interpreter) — skipping." >&2
    exit 0
fi

# ---------------------------------------------------------------------------
# R1 heading matcher — guilt+innocence tested in scripts/tests/test_quickcheck.sh
# ---------------------------------------------------------------------------
# Reads text on stdin. Exit 0 iff a line starts with the EXACT literal
# "## Adversarial review" (case-sensitive, anchored at line start). This is
# intentionally NARROWER than the real CI gate (scripts/check_adversarial_review.py's
# `^#{2,}\s+Adversarial review` regex, case-insensitive) — quickcheck is a fast
# local heuristic advising "you're probably about to fail R1", not the gate
# itself; false negatives here just mean "go check the real gate", which is
# always the safe direction for an advisory tool to err in.
check_r1_heading() {
    grep -qE '^## Adversarial review'
}

# ---------------------------------------------------------------------------
# 1. impact-scoped pytest
# ---------------------------------------------------------------------------
run_impact_scoped_pytest() {
    local changed_all="$1"
    local py
    py="$(command -v python3 || command -v python || true)"

    if [ -z "$py" ]; then
        echo "   [pytest] no python3/python on PATH — skipping impact-scoped run."
        return 0
    fi
    if [ ! -f scripts/ci/impact_map.py ]; then
        echo "   [pytest] scripts/ci/impact_map.py not found — skipping."
        return 0
    fi

    local impact_json
    impact_json="$(printf '%s\n' "$changed_all" | "$py" scripts/ci/impact_map.py 2>/dev/null)" || impact_json=""
    if [ -z "$impact_json" ]; then
        echo "   [pytest] impact_map.py produced no output (non-zero exit?) — skipping."
        return 0
    fi

    # Decode the compact JSON without a jq dependency (jq isn't guaranteed on
    # every dev machine; python3 already is, since impact_map.py itself needs
    # it). First stdout line is the summary tuple; subsequent lines (if any)
    # are "TEST\t<repo-relative path>", one per selected test module.
    local parsed
    parsed="$("$py" - "$impact_json" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("PARSE_ERROR")
    raise SystemExit(0)
run_all = "1" if d.get("run_all") else "0"
reason = d.get("reason", "")
changed_count = d.get("changed_file_count", 0)
out_of_scope = d.get("out_of_scope_paths", []) or []
selected = d.get("selected_tests", []) or []
print(f"{run_all}\t{reason}\t{changed_count}\t{len(out_of_scope)}")
for t in selected:
    print(f"TEST\t{t}")
PYEOF
)"

    local first_line
    first_line="$(printf '%s\n' "$parsed" | head -n1)"
    if [ "$first_line" = "PARSE_ERROR" ] || [ -z "$first_line" ]; then
        echo "   [pytest] could not parse impact_map.py output — skipping."
        return 0
    fi

    local run_all reason changed_count oos_count
    IFS=$'\t' read -r run_all reason changed_count oos_count <<< "$first_line"

    local -a tests=()
    local tag path
    while IFS=$'\t' read -r tag path; do
        [ "$tag" = "TEST" ] && [ -n "$path" ] && tests+=("$path")
    done < <(printf '%s\n' "$parsed" | tail -n +2)

    if [ "$run_all" = "1" ]; then
        if [ "$reason" = "out_of_scope_path" ] && [ "${changed_count:-0}" -gt 0 ] && [ "${oos_count:-0}" -eq "${changed_count:-0}" ]; then
            echo "   [pytest] no apps/backend-rag/backend/*.py changes in this diff — nothing to scope, skipped."
        else
            echo "   [pytest] impact map could not safely scope this diff (reason=$reason)."
            echo "            The full backend suite is heavy (11-32min) — this script never runs it"
            echo "            and never auto-dispatches it. If you need it, run it yourself:"
            echo "              ssh mini 'cd ~/nuzantara/apps/backend-rag && source .venv/bin/activate && PYTHONPATH=.:../crm-cell python -m pytest backend/tests --ignore=backend/tests/e2e'"
        fi
        return 0
    fi

    if [ "${#tests[@]}" -eq 0 ]; then
        echo "   [pytest] impact map selected zero test modules — nothing to run."
        return 0
    fi

    if [ ! -f apps/backend-rag/.venv/bin/activate ]; then
        echo "   [pytest] ${#tests[@]} test module(s) impacted but apps/backend-rag/.venv is missing — skipping execution:"
        printf '            %s\n' "${tests[@]}"
        return 0
    fi

    local pg_bin pg_note=""
    pg_bin="$(command -v pg_isready || echo /opt/homebrew/opt/postgresql@17/bin/pg_isready)"
    if [ ! -x "$pg_bin" ] || ! "$pg_bin" -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
        pg_note="no local PostgreSQL on 127.0.0.1:5432 — DB-dependent tests in this scope may error with a connection failure; that is NOT this diff's fault"
    fi

    echo "   [pytest] ${#tests[@]} test module(s) impacted — running scoped:"
    printf '            %s\n' "${tests[@]}"
    [ -n "$pg_note" ] && echo "   [pytest] note: $pg_note"

    local -a rel_tests=()
    local t
    for t in "${tests[@]}"; do
        rel_tests+=("${t#apps/backend-rag/}")
    done

    local out rc
    out="$(
        cd apps/backend-rag \
            && source .venv/bin/activate 2>/dev/null \
            && OLLAMA_URL="http://127.0.0.1:9" \
               PYTHONPATH=.:../crm-cell \
               JWT_SECRET_KEY="${JWT_SECRET_KEY:-test_jwt_secret_key_for_testing_only_min_32_chars_long}" \
               API_KEYS="${API_KEYS:-test_api_key_1,test_api_key_2}" \
               python -m pytest "${rel_tests[@]}" --tb=short 2>&1
    )"
    rc=$?
    printf '%s\n' "$out" | sed 's/^/            /'
    if [ "$rc" -eq 0 ]; then
        echo "   [pytest] scoped suite PASSED."
    else
        echo "   [pytest] scoped suite reported failures (advisory, rc=$rc) — named above."
    fi
    return 0
}

# ---------------------------------------------------------------------------
# 2. prettier --check on changed files only
# ---------------------------------------------------------------------------
run_prettier_changed() {
    local changed_existing="$1"
    if [ -z "$changed_existing" ]; then
        echo "   [prettier] no existing changed files — skipped."
        return 0
    fi

    local -a files=()
    local f
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        case "$f" in
            *.ts|*.js|*.json|*.md|*.yml|*.yaml) files+=("$f") ;;
        esac
    done <<< "$changed_existing"

    if [ "${#files[@]}" -eq 0 ]; then
        echo "   [prettier] no ts/js/json/md/yml/yaml file in this diff — skipped."
        return 0
    fi

    if ! command -v npx >/dev/null 2>&1; then
        echo "   [prettier] npx not found on PATH — skipping (install Node.js to enable)."
        return 0
    fi

    echo "   [prettier] checking ${#files[@]} changed file(s)..."
    local out rc
    out="$(printf '%s\n' "${files[@]}" | xargs npx --no-install prettier --check --ignore-unknown 2>&1)"
    rc=$?
    [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/            /'
    if [ "$rc" -eq 0 ]; then
        echo "   [prettier] OK."
    else
        echo "   [prettier] one or more changed files are NOT prettier-formatted (advisory, rc=$rc)."
        echo "              Fix: npx prettier --write <file>"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# 3. actionlint — only when .github/workflows/ is touched
# ---------------------------------------------------------------------------
run_actionlint_if_touched() {
    local changed_all="$1"
    if ! printf '%s\n' "$changed_all" | grep -q '^\.github/workflows/'; then
        return 0
    fi

    echo "   [actionlint] .github/workflows/ touched — checking..."
    local bin=""
    if command -v actionlint >/dev/null 2>&1; then
        bin="$(command -v actionlint)"
    elif [ -x /opt/homebrew/bin/actionlint ]; then
        bin=/opt/homebrew/bin/actionlint
    elif [ -x /usr/local/bin/actionlint ]; then
        bin=/usr/local/bin/actionlint
    fi

    if [ -z "$bin" ]; then
        echo "   [actionlint] not installed locally — skipping (CI's actionlint.yml is the real, required gate)."
        echo "                Install: brew install actionlint"
        return 0
    fi

    # No file args — same auto-discovery scope as .github/workflows/actionlint.yml
    # (which lints the whole .github/workflows/*.yml corpus, not a per-file diff).
    local out rc
    out="$("$bin" -color -shellcheck= 2>&1)"
    rc=$?
    [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/            /'
    if [ "$rc" -eq 0 ]; then
        echo "   [actionlint] OK."
    else
        echo "   [actionlint] schema/expression issues found (advisory, rc=$rc)."
    fi
    return 0
}

# ---------------------------------------------------------------------------
# 3b. skills-canon — untracked drift between .claude/skills and .agents/skills
#
# Added 2026-08-27 (Q0 correction, team-lead finding): CI can only ever see
# COMMITTED state, so scripts/tests/test_skills_canonical.py's own
# check-skills-canonical.yml workflow can never catch untracked cruft sitting
# in a local checkout. Measured live on the Pro MAIN checkout: 11 Tier-B
# skills (modus, workflow, ...) existed as UNTRACKED real directories under
# `.agents/skills/` — `git status --porcelain` never showed them to anyone
# who only reads diffs — one of them (a stale `.agents/skills/modus/SKILL.md`)
# still routed the Gear-3 gate to "Fable 5 first", contradicting the current
# ruling. Deliberately UNCONDITIONAL (not gated on the diff touching
# .claude/skills or .agents/skills): the failure mode this exists to catch is
# BY DEFINITION untracked, so it never shows up in `changed_all` — gating on
# the diff would exempt exactly the case that matters. Cheap regardless (a
# stat/iterdir pass over ~20 directories).
# ---------------------------------------------------------------------------
run_skills_canonical_check() {
    if [ ! -f scripts/tests/test_skills_canonical.py ]; then
        echo "   [skills-canon] scripts/tests/test_skills_canonical.py not on this branch yet — skipping."
        return 0
    fi
    local py=""
    if command -v python3 >/dev/null 2>&1; then
        py="$(command -v python3)"
    else
        echo "   [skills-canon] no python3 on PATH — skipping."
        return 0
    fi

    local out rc
    out="$(NUZ_SKILLS_ROOT="$(pwd)" "$py" - <<'PYEOF' 2>&1
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "quickcheck_skills_canonical", "scripts/tests/test_skills_canonical.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
violations = mod.find_canonicity_violations(mod.CLAUDE_SKILLS, mod.AGENTS_SKILLS)
for v in violations:
    print(v)
sys.exit(1 if violations else 0)
PYEOF
)"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "   [skills-canon] OK — no untracked drift between .claude/skills and .agents/skills."
    else
        echo "   [skills-canon] local tree has drift NO CI CHECK CAN SEE (untracked files never travel with a commit):"
        printf '%s\n' "$out" | sed 's/^/            /'
        echo "            (advisory — fix: remove the stray .agents/skills/<name> copy, or make .claude/skills/<name> a symlink to it)"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# 4. R1 — literal '## Adversarial review' heading on the branch's open PR
# ---------------------------------------------------------------------------
run_r1_check() {
    if ! command -v gh >/dev/null 2>&1; then
        echo "   [R1] gh CLI not found — skipping PR-body heading check."
        return 0
    fi

    local body
    body="$(gh pr view --json body -q .body 2>/dev/null)" || body=""
    if [ -z "$body" ]; then
        echo "   [R1] no open PR found for this branch (or gh not authenticated) — skipped."
        return 0
    fi

    if printf '%s' "$body" | check_r1_heading; then
        echo "   [R1] PR body has the literal '## Adversarial review' heading. OK."
    else
        echo "   [R1] PR body is MISSING the literal '## Adversarial review' heading."
        echo "        (advisory — the real, required gate is scripts/check_adversarial_review.py)"
    fi
    return 0
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    set -uo pipefail

    local repo_root
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || repo_root=""
    if [ -z "$repo_root" ]; then
        echo "quickcheck: not inside a git repository — skipping."
        return 0
    fi
    cd "$repo_root" || return 0

    local base_ref="${QUICKCHECK_BASE_REF:-origin/main}"
    local merge_base
    merge_base="$(git merge-base "$base_ref" HEAD 2>/dev/null)" || merge_base=""
    if [ -z "$merge_base" ]; then
        echo "quickcheck: could not compute merge-base with $base_ref (offline? unfetched?) — skipping."
        return 0
    fi

    local changed_all changed_existing
    changed_all="$(git diff --no-ext-diff --no-renames --name-only "$merge_base" HEAD 2>/dev/null || true)"
    if [ -z "$changed_all" ]; then
        echo "🩺 quickcheck: no committed changes vs $base_ref — nothing to check."
        return 0
    fi
    changed_existing="$(git diff --no-ext-diff --no-renames --diff-filter=d --name-only "$merge_base" HEAD 2>/dev/null || true)"

    local n
    n="$(printf '%s\n' "$changed_all" | grep -c . || true)"
    echo "🩺 quickcheck (advisory — never blocks the push) — $n changed file(s) vs $base_ref"

    run_impact_scoped_pytest "$changed_all"
    run_prettier_changed "$changed_existing"
    run_actionlint_if_touched "$changed_all"
    run_skills_canonical_check
    run_r1_check

    echo "🩺 quickcheck done (advisory — see .husky/pre-push for the real gates)."
    return 0
}

if [[ "${BASH_SOURCE[0]:-$0}" == "${0}" ]]; then
    main "$@"
    exit 0
fi
