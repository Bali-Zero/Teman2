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
# Sourced, not executed.

SPALLA_REDACT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPALLA_REDACTOR_PY="${SPALLA_REDACTOR_PY:-${SPALLA_REDACT_LIB_DIR}/_redact_pii.py}"
SPALLA_SUPERVISOR_PY="${SPALLA_SUPERVISOR_PY:-${SPALLA_REDACT_LIB_DIR}/async_review_supervisor.py}"

# Static glob patterns for .gitignore PII path shapes that a plain substring
# fragment can't express (wildcards, or a bare directory name too generic to
# fragment-match safely). Cross-checked against gate 7466's "list provenance"
# findings by scripts/tests/test_pii_path_coverage.sh, which fails when a
# known PII path in .gitignore/the supervisor stops being covered.
PII_PATH_PATTERNS=(
    "research/crm/*" "research/crm-exports/*" "research/compliance/*"
    "research/wa-copilot/*" "research/personal/wa-corpus/*" "research/hr/*"
    "research/*/clients/*" "data/hr/*" "docs/crm/*" "DOSSIER_*.md"
    "research/commercial/*-yield-opportunities.md" "*dq_clients*.csv"
    "*dq_orphan_clients*.csv"
)

_SPALLA_PII_FRAGMENTS_CACHE=""
_SPALLA_PII_FRAGMENTS_LOADED="false"

# Live PII_PATH_FRAGMENTS from scripts/async_review_supervisor.py (substring
# match: "/kb/", "/fixtures/", "/crm/", "research/visa/clients/", "OSINT-
# Nexus/" as of 2026-09-27). Parsed via ast.literal_eval — the module is
# never imported, so any top-level side effect in the supervisor never runs.
# Cached for the life of the process: this is called once per checked path.
_spalla_pii_fragments() {
    if [[ "$_SPALLA_PII_FRAGMENTS_LOADED" != "true" ]]; then
        if [[ -f "$SPALLA_SUPERVISOR_PY" ]]; then
            _SPALLA_PII_FRAGMENTS_CACHE="$(python3 -c '
import ast, sys
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
for node in ast.walk(tree):
    # PII_PATH_FRAGMENTS carries a `tuple[str, ...]` annotation, so this is
    # an AnnAssign (singular .target), not a plain Assign (plural .targets).
    if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "PII_PATH_FRAGMENTS":
        for v in ast.literal_eval(node.value):
            print(v)
        break
' "$SPALLA_SUPERVISOR_PY" 2>/dev/null || true)"
        fi
        _SPALLA_PII_FRAGMENTS_LOADED="true"
    fi
    printf '%s\n' "$_SPALLA_PII_FRAGMENTS_CACHE"
}

pii_path_hit() {
    local f="$1" pat frag
    for pat in "${PII_PATH_PATTERNS[@]}"; do
        # shellcheck disable=SC2053
        [[ "$f" == $pat ]] && return 0
    done
    while IFS= read -r frag; do
        [[ -z "$frag" ]] && continue
        [[ "$f" == *"$frag"* ]] && return 0
    done < <(_spalla_pii_fragments)
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
            if (line != "/dev/null") { sub(/^a\//, "", line); cur = line }
            print; next
        }
        in_header && /^\+\+\+ / {
            line = $0; sub(/^\+\+\+ /, "", line)
            if (line != "/dev/null") { sub(/^b\//, "", line); cur = line }
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
