#!/usr/bin/env bash
# spalla_redact.sh — shared diff-sanitization helpers for external-seat
# wrappers (codex-spalla.sh and any sibling that embeds a diff or file
# content in a prompt sent to an external LLM). Three responsibilities, all
# fail-closed:
#
#   1. strip_data_file_deletes — never embed a DELETED line of a .jsonl/
#      .csv/.xlsx file: a PII-removal diff is the most PII-dense diff there
#      is, the deleted lines ARE the data (cicatrix W140, 2026-09-26 — a
#      client plan.jsonl's 959 deleted full_name lines went to Codex in
#      cleartext because the wrapper embedded the raw diff unfiltered).
#      Header-state aware (a deleted SQL/Lua-comment line like "-- foo"
#      becomes the diff line "--- foo", which is NOT a new file header if
#      we're already past one file's "+++" line — gate 7466 S6) and
#      space-safe (path capture reads the whole rest of the "--- "/"+++ "
#      line, never NF-splits it — a `diff --git` header line IS ambiguous
#      for a path containing a space, so it is never used for path capture).
#
#   2. pii_path_hit — refuses on a PII-classed path. The list is the union
#      of a small static glob set (for .gitignore path shapes fragment-
#      matching can't express safely) and the LIVE PII_PATH_FRAGMENTS tuple
#      already declared in scripts/async_review_supervisor.py (the existing
#      "withhold the cloud reviewer" list) — parsed via `ast.literal_eval`
#      on the un-executed module text, so the supervisor's own top-level
#      code never runs and the two lists cannot silently drift apart.
#
#   3. redact_for_external — pipe non-empty text through the ONE canonical
#      redactor, scripts/_redact_pii.py, with `--require-dynamic-names`: PROD
#      CRM full_name/company_name coverage is REQUIRED, not best-effort — a
#      redactor that silently skips pass4 when DATABASE_URL is unset would
#      ship the incident's own data class (full_name) in cleartext for
#      anything not caught by a static shape (gate 7466 blocker 5). Fails
#      closed (returns 1, message on stderr) when the redactor errors OR
#      when the CRM name list can't be loaded. Empty/whitespace-only input
#      passes through unchanged (an empty diff section is normal, not PII).
#
# GIT OUTPUT FORMATS THIS WRAPPER ACTUALLY PARSES, and the two it does NOT
# (gate on PR #7470's final message asked about `--name-status`/`--numstat`
# specifically): `.claude/scripts/codex-spalla.sh` only ever reads plain
# `git diff` bodies, `--name-only`, and `ls-files --others` — never
# `--name-status` or `--numstat`. Those two formats tab-delimit their fields
# UNCONDITIONALLY (status-or-counts, then a literal TAB, then the path,
# regardless of whether the path itself contains a space), which is a
# DIFFERENT mechanism from the one this file's `strip_data_file_deletes` TAB
# fix addresses (git appending a trailing TAB after a space-bearing path on
# a plain diff's own `--- `/`+++ ` header lines, conditional on the space).
# If a future change adds a `--name-status`/`--numstat` call site to the
# wrapper, its tab-delimited fields need their OWN parsing, not reuse of
# this file's header-state machine. `-c core.quotePath=false` on every
# path-producing call — already applied throughout the wrapper — covers
# non-ASCII-path quoting identically across all of these formats.
#
# Sourced, not executed.

SPALLA_REDACT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPALLA_REDACTOR_PY="${SPALLA_REDACTOR_PY:-${SPALLA_REDACT_LIB_DIR}/_redact_pii.py}"
SPALLA_SUPERVISOR_PY="${SPALLA_SUPERVISOR_PY:-${SPALLA_REDACT_LIB_DIR}/async_review_supervisor.py}"

# Static glob patterns for .gitignore PII path shapes that a plain substring
# fragment can't express (wildcards, or a bare directory name too generic to
# fragment-match safely). Cross-checked against .gitignore's own PII-marked
# entries by scripts/tests/test_codex_spalla_diff_redaction.sh's static-list
# block (gate 7466 blocker 2) — this is still a hand-typed list, not a
# runtime-derived one; gate 7470's "finish blocker 2" note tracks turning
# that comparison into an automatic drift check instead of a hand-copied one.
PII_PATH_PATTERNS=(
    "research/crm/*" "research/crm-exports/*" "research/compliance/*"
    "research/wa-copilot/*" "research/personal/wa-corpus/*" "research/hr/*"
    "research/*/clients/*" "data/hr/*" "docs/crm/*" "DOSSIER_*.md"
    "research/commercial/*-yield-opportunities.md" "*dq_clients*.csv"
    "*dq_orphan_clients*.csv"
    # gate 7470 "finish blocker 2": .gitignore's `compliance_report_*.pdf` has
    # no embedded "/", so git's own gitignore semantics match it at ANY
    # depth (not just repo-root) — the leading "*" mirrors that, the same
    # way the two dq_*.csv entries above already do. Found missing by
    # scripts/tests/test_codex_spalla_diff_redaction.sh's gitignore-drift
    # check, which derives its coverage assertions from .gitignore itself
    # instead of a second hand-typed list.
    "*compliance_report_*.pdf"
)

_SPALLA_PII_FRAGMENTS_CACHE=""
# "" = not attempted yet, "ok" = cached and safe to reuse, "failed" = the
# source could not be read/parsed. gate 7470 defect 3: the previous version
# swallowed a missing file, an unreadable file AND a parse error under one
# `2>/dev/null || true`, so a corrupted or renamed supervisor module silently
# fell back to an EMPTY fragment list instead of failing anything — a caller
# checking a path against zero dynamic fragments could not tell "the module
# legitimately declares nothing" from "the load itself broke", and the wrapper
# proceeded either way. A load failure is now cached as "failed" and every
# subsequent pii_path_hit call fails CLOSED (treats the path as a hit) instead
# of silently treating the unreadable list as if it were empty.
_SPALLA_PII_FRAGMENTS_STATE=""

# Live PII_PATH_FRAGMENTS from scripts/async_review_supervisor.py (substring
# match: "/kb/", "/fixtures/", "/crm/", "research/visa/clients/", "OSINT-
# Nexus/" as of 2026-09-27). Parsed via ast.literal_eval — the module is
# never imported, so any top-level side effect in the supervisor never runs.
# Accepts BOTH `NAME: TYPE = (...)` (AnnAssign, singular .target) and plain
# `NAME = (...)` (Assign, plural .targets) — gate 7470 defect 3: a harmless
# refactor of the supervisor's tuple to drop its type annotation turned every
# fragment from HIT to MISS under the AnnAssign-only version. Cached for the
# life of the process on success; a failure is cached too, so a broken source
# is reported once per process, not once per checked path.
_spalla_pii_fragments() {
    if [[ "$_SPALLA_PII_FRAGMENTS_STATE" == "failed" ]]; then
        return 1
    fi
    if [[ "$_SPALLA_PII_FRAGMENTS_STATE" != "ok" ]]; then
        if [[ ! -f "$SPALLA_SUPERVISOR_PY" ]]; then
            echo "spalla_redact: PII fragment source missing: $SPALLA_SUPERVISOR_PY — refusing rather than treating this as zero fragments" >&2
            _SPALLA_PII_FRAGMENTS_STATE="failed"
            return 1
        fi
        local errfile rc
        errfile="$(mktemp "${TMPDIR:-/tmp}/spalla-fragments-err.XXXXXX")"
        _SPALLA_PII_FRAGMENTS_CACHE="$(python3 -c '
import ast, sys

try:
    tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
except Exception as e:
    sys.stderr.write("parse error: %s\n" % e)
    sys.exit(2)

found = False
for node in ast.walk(tree):
    target_id = None
    if isinstance(node, ast.AnnAssign):
        target_id = getattr(node.target, "id", None)
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if getattr(t, "id", None) == "PII_PATH_FRAGMENTS":
                target_id = "PII_PATH_FRAGMENTS"
                break
    if target_id == "PII_PATH_FRAGMENTS":
        found = True
        for v in ast.literal_eval(node.value):
            print(v)
        break

if not found:
    sys.stderr.write("PII_PATH_FRAGMENTS not found in module\n")
    sys.exit(3)
' "$SPALLA_SUPERVISOR_PY" 2>"$errfile")"
        rc=$?
        if [[ "$rc" -ne 0 ]]; then
            cat "$errfile" >&2
            rm -f "$errfile"
            echo "spalla_redact: failed to load dynamic PII fragments from $SPALLA_SUPERVISOR_PY (rc=$rc) — refusing rather than proceeding with a partial list" >&2
            _SPALLA_PII_FRAGMENTS_STATE="failed"
            return 1
        fi
        rm -f "$errfile"
        _SPALLA_PII_FRAGMENTS_STATE="ok"
    fi
    printf '%s\n' "$_SPALLA_PII_FRAGMENTS_CACHE"
    return 0
}

pii_path_hit() {
    local f="$1" pat frag frag_output frag_rc
    for pat in "${PII_PATH_PATTERNS[@]}"; do
        # shellcheck disable=SC2053
        [[ "$f" == $pat ]] && return 0
    done
    frag_output="$(_spalla_pii_fragments)"
    frag_rc=$?
    if [[ "$frag_rc" -ne 0 ]]; then
        # Fail closed (gate 7470 defect 3): the dynamic list could not be
        # verified, so this path cannot be proven innocent — treat it as a hit.
        return 0
    fi
    while IFS= read -r frag; do
        [[ -z "$frag" ]] && continue
        [[ "$f" == *"$frag"* ]] && return 0
    done <<< "$frag_output"
    return 1
}

strip_data_file_deletes() {
    awk '
        BEGIN { in_header = 0; cur = "" }
        /^diff --git / { in_header = 1; print; next }
        in_header && /^(index |old mode |new mode |new file mode |deleted file mode |similarity index |rename from |rename to |copy from |copy to ) / {
            print; next
        }
        in_header && /^--- / {
            line = $0; sub(/^--- /, "", line)
            if (line != "/dev/null") {
                sub(/^a\//, "", line)
                # git appends a trailing TAB after the path itself (not the
                # normal newline) on this header line when the path contains
                # a space, to keep the boundary unambiguous for its own
                # parsers (gate 7470 defect 2) — strip it or `cur` never
                # matches the file-extension test below and a deleted line in
                # a space-bearing "data file.csv" is never suppressed.
                sub(/\t$/, "", line)
                cur = line
            }
            print; next
        }
        in_header && /^\+\+\+ / {
            line = $0; sub(/^\+\+\+ /, "", line)
            if (line != "/dev/null") {
                sub(/^b\//, "", line)
                sub(/\t$/, "", line)
                cur = line
            }
            in_header = 0
            print; next
        }
        {
            if (cur ~ /\.(jsonl|csv|xlsx)$/ && $0 ~ /^-/) {
                print "-[DELETED-LINE-SUPPRESSED: data file, deleted content never leaves this machine]"
                next
            }
            print
        }
    '
}

redact_for_external() {
    local input="$1"
    if [[ -z "${input//[$'\t\r\n ']/}" ]]; then
        printf '%s' "$input"
        return 0
    fi
    local out rc=0 errfile
    errfile="$(mktemp "${TMPDIR:-/tmp}/spalla-redact.XXXXXX")"
    out="$(printf '%s' "$input" | python3 "$SPALLA_REDACTOR_PY" --require-dynamic-names 2>"$errfile")" || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        cat "$errfile" >&2
        rm -f "$errfile"
        return 1
    fi
    rm -f "$errfile"
    printf '%s' "$out"
}
