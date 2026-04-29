#!/usr/bin/env bash
# audit_httpx_violations.sh — Phase 1 inventory for Golden Rule #10.
#
# Scans apps/backend-rag/backend/ for every `httpx.AsyncClient(`
# instantiation and classifies each match into one of these buckets:
#
#   CRITICAL_LOOP_BODY        — instantiated inside for/while → leaks
#                               every iteration (worst case).
#   VIOLATION_FUNCTION_BODY   — bare instantiation in def/async def
#                               body, no context manager, no singleton
#                               guard. Per-call leak.
#   VIOLATION_INSTANCE_INIT   — assigned to self.* in __init__. Borderline:
#                               needs manual review of close() registration.
#   OK_LAZY_SINGLETON_GETTER  — instantiated inside a getter guarded by
#                               an `is_closed` check (within preceding 5 lines).
#   OK_MODULE_SCOPE_SINGLETON — assignment at column 0 (rare without getter).
#   OK_CONTEXT_MANAGER        — `async with httpx.AsyncClient(...) as ...`.
#                               Auto-closed; no leak.
#   OK_TEST_FIXTURE           — file under tests/, conftest.py, or
#                               *_test.py / test_*.py.
#   OK_SCRIPT_ONESHOT         — file under backend/scripts/. Run-once CLI
#                               scripts that exit; not server hot-path.
#
# OUTPUT
#   docs/audits/2026-04-29-zero-crash-audit/p0-5-httpx-audit-report.md
#
# DETERMINISM
#   Sorted by (severity DESC, file ASC, line ASC). No timestamps in body.
#   Re-running the script after committing produces zero git diff.
#
# DEPENDENCIES
#   bash, ripgrep (rg), awk, sort. No Python.
#
# Refs:
#   docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-5_httpx_dependencies_audit.md
#   apps/backend-rag/backend/services/notifications/email_http.py (reference pattern)
#
set -euo pipefail

# Resolve repo root (two parents up from scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_DIR="${1:-apps/backend-rag/backend}"
REPORT_PATH="${2:-docs/audits/2026-04-29-zero-crash-audit/p0-5-httpx-audit-report.md}"

cd "$REPO_ROOT"

if ! command -v rg >/dev/null 2>&1; then
    echo "ERROR: ripgrep (rg) not found in PATH." >&2
    exit 2
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "ERROR: target directory not found: $TARGET_DIR" >&2
    exit 2
fi

# -----------------------------------------------------------------------
# Step 1 — collect raw matches: file:line:text
# -----------------------------------------------------------------------
RAW_MATCHES="$(rg --type py --no-heading --line-number 'httpx\.AsyncClient\(' "$TARGET_DIR" | LC_ALL=C sort)"

# -----------------------------------------------------------------------
# Step 2 — classify each match by reading the source line + context.
#
# For each match we:
#   1. Read the matched line.
#   2. Strip out false positives (line is comment-only, line is inside a
#      docstring or a string literal containing the pattern).
#   3. Look up to 8 lines back for indicators (for/while loops at lower
#      indent, `def __init__`, `is_closed` guards).
#   4. Emit a TSV row: severity\tfile\tline\tbucket\tsnippet
#
# Severity ordinal (for sort):
#   0 = CRITICAL, 1 = VIOLATION, 9 = OK
# -----------------------------------------------------------------------

# Awk classifier — reads file content via getline of the file path. Run
# once per match; small N (~140) so the inefficiency is acceptable for
# phase 1 inventory.
classify() {
    local file="$1" line="$2"
    awk -v target_line="$line" '
    BEGIN {
        # Sliding context window. Sized large enough to span typical
        # __init__ bodies (most are <30 lines) so the enclosing-function
        # detector can see the def line.
        ctx_size = 60
        for (i = 0; i < ctx_size; i++) ctx[i] = ""
    }
    {
        cur_line = NR
        # Capture the matched line.
        if (cur_line == target_line) {
            line_text = $0
            # Compute indentation (leading whitespace count).
            indent = match($0, /[^ \t]/) - 1
            if (indent < 0) indent = 0

            # ---- Step A: strip false positives ----
            stripped = $0
            # Trim leading whitespace.
            sub(/^[ \t]+/, "", stripped)
            # Comment-only line (false positive):  # text including httpx.AsyncClient(
            if (substr(stripped, 1, 1) == "#") {
                print "FALSE_POSITIVE_COMMENT"; classified = 1; exit 0
            }
            # Triple-quoted docstring delimiter on this line is rare;
            # rely on the in_docstring tracker computed below.
            if (in_docstring) {
                print "FALSE_POSITIVE_DOCSTRING"; classified = 1; exit 0
            }
            # String literal mention: the call substring is wrapped in
            # quotes. Heuristic: count quotes before "httpx.AsyncClient(".
            # If odd number of un-escaped " or '\'' before the match, it is
            # inside a string literal.
            pre = $0
            sub(/httpx\.AsyncClient\(.*$/, "", pre)
            n_dq = gsub(/"/, "&", pre)
            n_sq = gsub(/'\''/, "&", pre)
            if ((n_dq % 2) == 1 || (n_sq % 2) == 1) {
                print "FALSE_POSITIVE_STRING_LITERAL"; classified = 1; exit 0
            }

            # ---- Step B: classify the real instantiation ----
            # OK_CONTEXT_MANAGER — `async with [_]?httpx.AsyncClient(`
            # Allow alias prefix (e.g. `_httpx`) for renamed imports.
            if (line_text ~ /async[ \t]+with[ \t]+[a-zA-Z_]*httpx\.AsyncClient\(/) {
                print "OK_CONTEXT_MANAGER"; classified = 1; exit 0
            }

            # OK_MODULE_SCOPE_SINGLETON — match at column 0
            # Pattern: "_var = httpx.AsyncClient(" with no leading space.
            if (indent == 0 && line_text ~ /^[a-zA-Z_][a-zA-Z0-9_]*[ \t]*=[ \t]*httpx\.AsyncClient\(/) {
                print "OK_MODULE_SCOPE_SINGLETON"; classified = 1; exit 0
            }

            # Walk backwards through the ring buffer. Stop the moment we
            # cross the def/async def header of the enclosing function:
            # signals beyond that point belong to a sibling scope.
            saw_closed_guard = 0
            saw_loop_lower_indent = 0
            saw_init_method = 0
            stop = 0
            for (k = 0; k < ctx_size && !stop; k++) {
                slot = (cur_line - 2 - k) % ctx_size
                if (slot < 0) slot += ctx_size
                ctx_line = ctx[slot]
                if (ctx_line == "") continue

                # Indent of context line.
                c_indent = match(ctx_line, /[^ \t]/) - 1
                if (c_indent < 0) c_indent = 0
                c_stripped = ctx_line
                sub(/^[ \t]+/, "", c_stripped)

                # is_closed guard within preceding 5 lines.
                if (k < 5 && c_stripped ~ /is_closed/) {
                    saw_closed_guard = 1
                }

                # When we cross the enclosing-function header (def/async def
                # at strictly-lower indent than the match), record whether
                # it was __init__ and stop the rewind — anything farther
                # back is in a sibling function and irrelevant.
                if (c_indent < indent && c_stripped ~ /^(async[ \t]+)?def[ \t]+/) {
                    if (c_stripped ~ /^(async[ \t]+)?def[ \t]+__init__\(/) {
                        saw_init_method = 1
                    }
                    stop = 1
                    continue
                }

                # Loop header at strictly-lower indent than the match —
                # only counts when we are still inside the same function.
                if (c_indent < indent && c_stripped ~ /^(for[ \t]|while[ \t])/) {
                    saw_loop_lower_indent = 1
                }
            }

            # Order matters: a guarded singleton getter takes precedence
            # over loop/init detection (the loop heuristic can otherwise
            # match a for-loop earlier in the same class but in a
            # different method).
            if (saw_closed_guard) {
                print "OK_LAZY_SINGLETON_GETTER"; classified = 1; exit 0
            }
            if (saw_loop_lower_indent) {
                print "CRITICAL_LOOP_BODY"; classified = 1; exit 0
            }
            # self.something = httpx.AsyncClient(  inside __init__
            if (saw_init_method && line_text ~ /self\.[a-zA-Z_][a-zA-Z0-9_]*[ \t]*=[ \t]*httpx\.AsyncClient\(/) {
                print "VIOLATION_INSTANCE_INIT"; classified = 1; exit 0
            }
            # Default: function body.
            print "VIOLATION_FUNCTION_BODY"; classified = 1; exit 0
        }

        # Track docstring state up to the target line. Toggle on each
        # standalone """ or '\'''\'''\'' delimiter line.
        # Heuristic: any line containing exactly """ (possibly with whitespace
        # only around it) toggles the flag. Imperfect for inline """text"""
        # cases, but for our scan space these are rare.
        if ($0 ~ /"""/) {
            # Count occurrences; odd => toggle.
            occ = gsub(/"""/, "&", $0)
            if (occ % 2 == 1) in_docstring = !in_docstring
        }

        # Push current line into the context ring.
        ctx[(NR - 1) % ctx_size] = $0
    }
    END {
        # Reached only if the target_line was past EOF or the matched
        # row was somehow not seen — surface as UNCLASSIFIED_EOF.
        if (!classified) print "UNCLASSIFIED_EOF"
    }
    ' "$file"
}

# -----------------------------------------------------------------------
# Step 3 — drive classification across all matches; build TSV stream.
# -----------------------------------------------------------------------
TSV="$(mktemp)"
trap 'rm -f "$TSV"' EXIT

# echo each match through classifier, emit:
#   severity_ord<TAB>file<TAB>line<TAB>bucket<TAB>raw_line
while IFS= read -r match; do
    [ -z "$match" ] && continue
    file="${match%%:*}"
    rest="${match#*:}"
    line="${rest%%:*}"
    raw_line="${rest#*:}"

    # File-path-based OK buckets (cheaper than awk for these).
    if [[ "$file" == */tests/* ]] || [[ "$file" == *conftest.py ]] \
       || [[ "$file" =~ /test_[^/]+\.py$ ]] || [[ "$file" =~ /[^/]+_test\.py$ ]]; then
        bucket="OK_TEST_FIXTURE"
    elif [[ "$file" =~ /scripts/ ]]; then
        bucket="OK_SCRIPT_ONESHOT"
    else
        bucket="$(classify "$file" "$line")"
    fi

    # Skip false positives — they represent strings, comments, docstrings.
    case "$bucket" in
        FALSE_POSITIVE_*) continue ;;
    esac

    # Severity ordinal for sort order.
    case "$bucket" in
        CRITICAL_*) sev=0 ;;
        VIOLATION_INSTANCE_INIT) sev=1 ;;
        VIOLATION_FUNCTION_BODY) sev=2 ;;
        OK_*) sev=9 ;;
        *) sev=8 ;;
    esac

    # Pad line to 6 digits so numeric sort by string works cleanly.
    printf '%d\t%s\t%06d\t%s\t%s\n' "$sev" "$file" "$line" "$bucket" "$raw_line" >> "$TSV"
done <<< "$RAW_MATCHES"

# Deterministic sort: severity asc, file asc, line asc.
SORTED="$(LC_ALL=C sort -t$'\t' -k1,1n -k2,2 -k3,3 "$TSV")"

# -----------------------------------------------------------------------
# Step 4 — render markdown report.
# -----------------------------------------------------------------------

# Count per bucket.
count_for() { awk -F'\t' -v b="$1" '$4 == b {n++} END {print n+0}' "$TSV"; }

C_LOOP=$(count_for "CRITICAL_LOOP_BODY")
V_INIT=$(count_for "VIOLATION_INSTANCE_INIT")
V_FUNC=$(count_for "VIOLATION_FUNCTION_BODY")
OK_GETTER=$(count_for "OK_LAZY_SINGLETON_GETTER")
OK_MOD=$(count_for "OK_MODULE_SCOPE_SINGLETON")
OK_CTX=$(count_for "OK_CONTEXT_MANAGER")
OK_TEST=$(count_for "OK_TEST_FIXTURE")
OK_SCRIPT=$(count_for "OK_SCRIPT_ONESHOT")
TOTAL=$(wc -l < "$TSV" | tr -d ' ')

mkdir -p "$(dirname "$REPORT_PATH")"

{
cat <<EOF
# P0-5 Phase 1 — \`httpx.AsyncClient\` audit report

> **Generated by:** \`scripts/audit_httpx_violations.sh\`
> **Scope:** \`$TARGET_DIR\`
> **Phase:** 1 of 2 — inventory only, no rewrites. Phase 2 (per-callsite
> rewrite) waits for P0-1 to land in \`main\` to avoid conflict on
> \`backend/app/dependencies.py\`.

This report enumerates every \`httpx.AsyncClient(\` instantiation under
the audit target and classifies each into a severity bucket per
**Golden Rule #10** (CLAUDE.md §4):

> **Async HTTP Clients** — NEVER \`httpx.AsyncClient()\` in methods/loops.
> Persistent \`_get_client\`, close in \`lifespan\`.

The reference of the correct pattern is
[\`apps/backend-rag/backend/services/notifications/email_http.py\`](../../../apps/backend-rag/backend/services/notifications/email_http.py).

---

## Summary

| Bucket                      | Count | Severity     |
| --------------------------- | ----: | ------------ |
| CRITICAL_LOOP_BODY          | $C_LOOP | **critical** |
| VIOLATION_INSTANCE_INIT     | $V_INIT | violation    |
| VIOLATION_FUNCTION_BODY     | $V_FUNC | violation    |
| OK_LAZY_SINGLETON_GETTER    | $OK_GETTER | ok           |
| OK_MODULE_SCOPE_SINGLETON   | $OK_MOD | ok           |
| OK_CONTEXT_MANAGER          | $OK_CTX | ok           |
| OK_TEST_FIXTURE             | $OK_TEST | ok           |
| OK_SCRIPT_ONESHOT           | $OK_SCRIPT | ok           |
| **Total**                   | **$TOTAL** |              |

Phase 2 must address every entry in the **critical** and **violation** buckets.
\`OK_*\` buckets are documented for completeness and a baseline against
which the CI guardrail (planned in P0-5 step 5) can be calibrated.

---

## Bucket definitions and suggested fix patterns

### CRITICAL_LOOP_BODY

A fresh \`httpx.AsyncClient\` is constructed inside a \`for\` or \`while\`
loop. Every iteration leaks one TCP connection until process exit.

**Fix:** hoist a module-level lazy singleton outside the loop (see
\`email_http.py\`).

### VIOLATION_FUNCTION_BODY

\`httpx.AsyncClient(\` appears inside a function body without any guard
(no \`is_closed\` re-use, no \`async with\`). Each call leaks a client.

**Fix:** extract a module-level \`_client\` global with a \`_get_client()\`
helper guarded by \`is_closed\`; register a \`close_*_client()\` coroutine
in \`app_factory.lifespan()\`.

### VIOLATION_INSTANCE_INIT

\`self.<attr> = httpx.AsyncClient(...)\` inside \`__init__\`. Borderline:
safe ONLY if the owning class is itself a process-wide singleton AND its
\`close()\` is wired into the FastAPI lifespan. Most callsites in this
bucket need manual review of how the class is constructed and torn down.

**Fix:** for adapters that are app-singletons (registered in
\`app.state\`), wire \`adapter.close()\` into \`app_factory.lifespan()\`
shutdown. For ephemeral instances, switch to a module-level singleton.

### OK_LAZY_SINGLETON_GETTER

The instantiation appears inside a getter method/function and is
guarded by an \`is_closed\` check within the preceding 5 lines (the
canonical \`if _client is None or _client.is_closed: ...\` pattern).
**Safe** assuming a paired \`close_*_client()\` is registered in
\`app_factory.lifespan()\`.

### OK_MODULE_SCOPE_SINGLETON

Assignment at column 0 (module scope). Rare without a getter; included
for completeness.

### OK_CONTEXT_MANAGER

\`async with httpx.AsyncClient(...) as ...:\`. The context manager closes
the client deterministically. Not a leak, but creates a TCP/TLS handshake
on every call — phase 2 may still convert hot paths to lazy singletons
for performance, but they are NOT a Golden Rule #10 violation.

### OK_TEST_FIXTURE

File lives under \`tests/\`, \`conftest.py\`, \`test_*.py\` or \`*_test.py\`.
Test scope; excluded from the rule.

### OK_SCRIPT_ONESHOT

File lives under \`backend/scripts/\`. These are CLI run-once tools that
exit; the leak class does not apply.

---

## Findings (sorted: severity, file, line)

| # | File | Line | Bucket | Snippet |
| -: | ---- | ---: | ------ | ------- |
EOF

idx=0
while IFS=$'\t' read -r sev file line bucket raw_line; do
    [ -z "$file" ] && continue
    idx=$((idx + 1))
    # Strip leading zeros from padded line.
    line_disp=$((10#$line))
    # Escape pipe and trim long snippets.
    snippet="$(printf '%s' "$raw_line" | sed 's/|/\\|/g' | awk '{gsub(/^[ \t]+|[ \t]+$/, ""); print}' | cut -c1-100)"
    printf '| %d | `%s` | %d | %s | `%s` |\n' "$idx" "$file" "$line_disp" "$bucket" "$snippet"
done <<< "$SORTED"

cat <<'EOF'

---

## Notes for phase 2

- Fix order: tackle CRITICAL_LOOP_BODY first, then VIOLATION_FUNCTION_BODY,
  then VIOLATION_INSTANCE_INIT (each instance-init entry needs a manual
  trace of how the owning class is registered and torn down).
- For each rewritten file, register the new \`close_*_client\` coroutine
  in \`apps/backend-rag/backend/app/app_factory.py\` lifespan shutdown.
- After phase 2, add the CI guardrail described in
  [\`docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-5_httpx_dependencies_audit.md\`](11_brainstorms/P0-5_httpx_dependencies_audit.md)
  step 5 to prevent regression.

## Caveats and known false-positive risk

The classifier is regex-driven, not AST-driven. Known limits:

- Inline triple-quoted docstrings (\`""" ... httpx.AsyncClient( ... """ \`
  on a single line) are NOT detected as in-docstring; multi-line
  docstrings ARE.
- Loop detection uses an 8-line lookback; a deeply nested
  instantiation (>8 lines below the \`for\`/\`while\` line) is reported
  as VIOLATION_FUNCTION_BODY rather than CRITICAL_LOOP_BODY.
- \`async with\` detection requires the \`async with\` keywords on the
  same line as \`httpx.AsyncClient(\`. Multi-line \`async with\` (rare in
  this codebase) is misclassified.
- \`OK_LAZY_SINGLETON_GETTER\` requires the \`is_closed\` guard within
  the preceding 5 lines. A getter that uses an alternative idiom
  (e.g. \`if _c is None\` only, no \`is_closed\`) is misclassified as
  VIOLATION_FUNCTION_BODY. Phase 2 should review these manually.

For a 5% misclassification budget, manual review of the 10-15 top
entries (sorted by severity) is the recommended workflow.
EOF
} > "$REPORT_PATH"

echo "[audit] $TOTAL real instantiations classified"
echo "[audit]   CRITICAL_LOOP_BODY        $C_LOOP"
echo "[audit]   VIOLATION_INSTANCE_INIT   $V_INIT"
echo "[audit]   VIOLATION_FUNCTION_BODY   $V_FUNC"
echo "[audit]   OK_LAZY_SINGLETON_GETTER  $OK_GETTER"
echo "[audit]   OK_MODULE_SCOPE_SINGLETON $OK_MOD"
echo "[audit]   OK_CONTEXT_MANAGER        $OK_CTX"
echo "[audit]   OK_TEST_FIXTURE           $OK_TEST"
echo "[audit]   OK_SCRIPT_ONESHOT         $OK_SCRIPT"
echo "[audit] report: $REPORT_PATH"
