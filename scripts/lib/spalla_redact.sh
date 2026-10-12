#!/usr/bin/env bash
# spalla_redact.sh — shared diff-sanitization helpers for external-seat
# wrappers (codex-spalla.sh and any sibling that embeds a diff or file
# content in a prompt sent to an external LLM). Two responsibilities, both
# fail-closed:
#
#   1. strip_data_file_deletes — never embed a DELETED line of a .jsonl/
#      .csv/.xlsx file: a PII-removal diff is the most PII-dense diff there
#      is, the deleted lines ARE the data (cicatrix W140, 2026-09-26 — a
#      client plan.jsonl's 959 deleted full_name lines went to Codex in
#      cleartext because the wrapper embedded the raw diff unfiltered).
#
#   2. redact_for_external — pipe non-empty text through the ONE canonical
#      redactor, scripts/_redact_pii.py (the same module the agent-library-
#      evolver's DeepSeek/Gemini/NotebookLM egress path already trusts),
#      before it leaves the machine. Empty/whitespace-only input passes
#      through unchanged — that redactor refuses empty input by design, and
#      an empty diff section (e.g. no uncommitted changes) is normal, not an
#      error. Returns 1 (with detail on stderr) on a genuine redactor
#      failure; the CALLER decides how to fail closed (telemetry, exit
#      code, message) — this lib never exits the caller's process.
#
# Sourced, not executed.

SPALLA_REDACT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPALLA_REDACTOR_PY="${SPALLA_REDACTOR_PY:-${SPALLA_REDACT_LIB_DIR}/_redact_pii.py}"

# PII-classed paths (Builder Contract rule 4): sourced from .gitignore's
# client-PII rules (research/crm-exports/, research/hr/, research/*/clients/,
# research/compliance/*clients*.csv, research/compliance/*passport*.csv) plus
# the two dirs named in the W140 incident (research/crm/, research/wa-copilot/)
# and research/personal/wa-corpus/. A diff touching any of these is refused
# by the caller unless the caller's own --allow-pii-paths override is set.
PII_PATH_PATTERNS=(
    "research/crm/*" "research/crm-exports/*" "research/compliance/*"
    "research/wa-copilot/*" "research/personal/wa-corpus/*" "research/hr/*"
    "research/*/clients/*"
)

pii_path_hit() {
    local f="$1" pat
    for pat in "${PII_PATH_PATTERNS[@]}"; do
        # shellcheck disable=SC2053
        [[ "$f" == $pat ]] && return 0
    done
    return 1
}

strip_data_file_deletes() {
    awk '
        /^diff --git a\// {
            for (i = 1; i <= NF; i++) { if ($i ~ /^b\//) cur = substr($i, 3) }
            print; next
        }
        /^--- / || /^\+\+\+ / { print; next }
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
    # Blank means only tab, CR, LF and space, the same four bytes as ever, judged byte by byte in the C locale
    # (in a subshell, so the caller's locale is untouched): under a UTF-8 locale an invalid byte fails any
    # bracket match, and [^[:space:]] would read such a body as blank and skip the redactor (Codex, 2026-10-10).
    # The caller's attributes are shed first (an integer LC_ALL turns "C" into 0) and every step is chained:
    # a step that fails — a readonly LC_ALL — makes the body non-blank, so it goes to the redactor. The C
    # locale is proven by what it does (a two-byte character counts as two), not by how LC_ALL reads (a
    # bash >= 4.3 nameref spells C while the locale stays UTF-8); only a regex status of exactly 1 (no
    # match) is blank, never an error. A regex match, never ${input//[class]/}: bash 3.2 (macOS /bin/bash)
    # rewrites that substitution in quadratic time — 8 KB took 58 s, 70 KB never reached the seat (2026-10-10).
    if ( unset LC_ALL nonblank probe status 2>/dev/null
         LC_ALL=C && probe=$'\xc3\xa9' && [[ ${#probe} -eq 2 ]] && nonblank=$'[^\t\r\n ]' && status=0 &&
             { [[ "$input" =~ $nonblank ]] || status=$?; } && [[ "$status" -eq 1 ]] ); then
        printf '%s' "$input"
        return 0
    fi
    local out rc=0 errfile
    errfile="$(mktemp "${TMPDIR:-/tmp}/spalla-redact.XXXXXX")"
    out="$(printf '%s' "$input" | python3 "$SPALLA_REDACTOR_PY" 2>"$errfile")" || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        cat "$errfile" >&2
        rm -f "$errfile"
        return 1
    fi
    rm -f "$errfile"
    printf '%s' "$out"
}
