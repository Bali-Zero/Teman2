#!/usr/bin/env bash
# Guilt + innocence for scripts/lib/spalla_redact.sh (cicatrix W140,
# 2026-09-26 + gate 7466 rework): a PII-removal PR was reviewed by
# codex-spalla.sh, which embedded the raw diff — 959 deleted lines of a
# client plan.jsonl (full_name records) — in the prompt sent to Codex/OpenAI
# in cleartext.
#
# Wrapper-level scenarios (dispatch refusal, --allow-pii-paths, renames,
# artifact permissions, required-dynamic-names guilt/innocence) live in
# scripts/tests/test_codex_spalla.py against a FAKE `codex` and a FAKE
# `psql` — never the real network. This file tests the pure lib functions
# in isolation (no git repo, no subprocess dispatch needed).
#
# Every name/phone/email here is invented. The email fixture is the same
# "someone@example.org" already used by scripts/tests/test_nb_title_redaction.py;
# the name fixture is "Jane Placeholder", ALSO already used by
# scripts/tests/test_nb_title_redaction.py. NEVER scripts/test_redact_pii.py's
# fixture list: gate 7470 blocker 1 found one of its names paired with a real
# client_id in scripts/crm_guardian_phase15_pilot.py on origin/main — that
# file's own fixtures are not a safe source to copy from. No real client
# appears in this file.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
. "$REPO_ROOT/scripts/lib/spalla_redact.sh"

FAIL=0
assert_eq() {
    if [[ "$1" != "$2" ]]; then
        echo "FAIL: $3 (got '$1', want '$2')" >&2
        FAIL=1
    else
        echo "ok: $3"
    fi
}
assert_contains() {
    if [[ "$1" != *"$2"* ]]; then
        echo "FAIL: $3 (missing '$2')" >&2
        FAIL=1
    else
        echo "ok: $3"
    fi
}
assert_not_contains() {
    if [[ "$1" == *"$2"* ]]; then
        echo "FAIL: $3 (should not contain '$2')" >&2
        FAIL=1
    else
        echo "ok: $3"
    fi
}

# ── pii_path_hit: static list (gate 7466 blocker 2 additions) ───────────
for p in \
    "research/crm/fake-client.txt" \
    "research/crm-exports/fake.csv" \
    "research/compliance/fake.pdf" \
    "research/wa-copilot/fake.txt" \
    "research/personal/wa-corpus/fake.txt" \
    "research/hr/fake.pdf" \
    "data/hr/fake.jpg" \
    "docs/crm/fake.csv" \
    "DOSSIER_fake-client.md" \
    "research/commercial/fake-yield-opportunities.md" \
    "some/path/dq_clients_2026.csv" \
    "research/visa/clients/fake.md"
do
    pii_path_hit "$p" && R=0 || R=1
    assert_eq "$R" "0" "pii_path_hit static: $p is PII-classed"
done

# ── pii_path_hit: LIVE fragments from scripts/async_review_supervisor.py
# (gate 7466 blocker 2 — union, not a hand-typed guess; a real drift in the
# supervisor's own PII_PATH_FRAGMENTS tuple changes this test's outcome too,
# since both read the same source at runtime). ──────────────────────────
for p in \
    "apps/some/kb/fake.md" \
    "tests/fixtures/fake.json" \
    "OSINT-Nexus/fake.json"
do
    pii_path_hit "$p" && R=0 || R=1
    assert_eq "$R" "0" "pii_path_hit dynamic (supervisor fragment): $p is PII-classed"
done

# ── pii_path_hit: innocence ──────────────────────────────────────────────
for p in "apps/backend-rag/main.py" "docs/README.md" "scripts/lib/codex_seat.sh"
do
    pii_path_hit "$p" && R=0 || R=1
    assert_eq "$R" "1" "pii_path_hit: $p is innocent"
done

# ── pii_path_hit: guilt, gate 7470 defect 3 — the dynamic fragment source
# cannot be read at all (missing/moved supervisor module). The previous
# version swallowed this under `2>/dev/null || true` and silently treated it
# as "zero fragments", so an innocent path stayed innocent even though the
# list it was checked against was actually broken. Must now fail CLOSED:
# every path is treated as PII-classed until the source loads again. Run in
# a subshell so the induced failure state (_SPALLA_PII_FRAGMENTS_STATE) and
# the redirected SPALLA_SUPERVISOR_PY never leak into the tests that follow.
(
    SPALLA_SUPERVISOR_PY="/nonexistent/spalla-fragments-test-$$.py"
    _SPALLA_PII_FRAGMENTS_STATE=""
    pii_path_hit "docs/completely/innocent/path.md"
) >/dev/null 2>&1 && FRAGMENT_FAILOPEN_RC=0 || FRAGMENT_FAILOPEN_RC=$?
assert_eq "$FRAGMENT_FAILOPEN_RC" "0" "pii_path_hit: fails closed (treats the path as PII-classed) when the dynamic fragment source cannot be read"

# ── pii_path_hit: innocence, gate 7470 defect 3 — a plain `Assign` (no type
# annotation) for PII_PATH_FRAGMENTS must still be found. The previous parser
# only matched `ast.AnnAssign`, so dropping the `: tuple[str, ...]` annotation
# in a harmless supervisor refactor silently turned every dynamic fragment
# from HIT to MISS. ─────────────────────────────────────────────────────
PLAIN_ASSIGN_PY="$(mktemp "${TMPDIR:-/tmp}/spalla-plain-assign-test.XXXXXX.py")"
cat > "$PLAIN_ASSIGN_PY" <<'PYEOF'
PII_PATH_FRAGMENTS = ("/kb/", "/fixtures/", "/crm/", "research/visa/clients/", "OSINT-Nexus/")
PYEOF
(
    SPALLA_SUPERVISOR_PY="$PLAIN_ASSIGN_PY"
    _SPALLA_PII_FRAGMENTS_STATE=""
    pii_path_hit "apps/some/kb/fake.md"
) >/dev/null 2>&1 && R=0 || R=1
rm -f "$PLAIN_ASSIGN_PY"
assert_eq "$R" "0" "pii_path_hit: dynamic fragments still parse from a plain 'Assign' (no type annotation)"

# ── strip_data_file_deletes: guilt (deleted jsonl line never embedded) ──
SYNTH_DIFF='diff --git a/research/crm/fake-plan.jsonl b/research/crm/fake-plan.jsonl
index 1111111..2222222 100644
--- a/research/crm/fake-plan.jsonl
+++ b/research/crm/fake-plan.jsonl
@@ -1,2 +1,1 @@
-{"full_name": "Jane Placeholder", "phone": "081234567890"}
+{"full_name": "[redacted upstream]"}'
STRIPPED="$(printf '%s\n' "$SYNTH_DIFF" | strip_data_file_deletes)"
assert_not_contains "$STRIPPED" "Jane Placeholder" "strip_data_file_deletes: deleted jsonl line content absent"
assert_not_contains "$STRIPPED" "081234567890" "strip_data_file_deletes: deleted jsonl phone absent"
assert_contains "$STRIPPED" "DELETED-LINE-SUPPRESSED" "strip_data_file_deletes: suppression marker present"
assert_contains "$STRIPPED" '"full_name": "[redacted upstream]"' "strip_data_file_deletes: added/context lines untouched"

# ── strip_data_file_deletes: guilt, gate 7466 S6 / gate 7470 defect 2 — a
# path containing a space. The "diff --git a/X b/X" header is genuinely
# ambiguous for a space-bearing path; the fix reads the unambiguous
# "--- "/"+++ " lines instead, which take the whole rest of the line, not an
# NF-split field. gate 7470 found the PREVIOUS hand-typed fixture here was
# wrong: real git appends a trailing TAB after the path on these two header
# lines when the path contains a space, which a hand-typed fixture omitted,
# so the test passed even though the trailing tab broke the file-extension
# match in production. Build the fixture from a REAL `git diff` this time,
# not by hand, so this test can't drift from git's actual output again. ──
SPACE_TESTREPO="$(mktemp -d "${TMPDIR:-/tmp}/spalla-space-testrepo.XXXXXX")"
git -C "$SPACE_TESTREPO" init -q
git -C "$SPACE_TESTREPO" config user.email "test@example.org"
git -C "$SPACE_TESTREPO" config user.name "test"
mkdir -p "$SPACE_TESTREPO/archive"
printf 'Jane Placeholder,081234567890\n' > "$SPACE_TESTREPO/archive/data file.csv"
git -C "$SPACE_TESTREPO" add "archive/data file.csv"
git -C "$SPACE_TESTREPO" commit -q -m "seed"
printf 'redacted,redacted\n' > "$SPACE_TESTREPO/archive/data file.csv"
SPACE_DIFF="$(git -C "$SPACE_TESTREPO" -c core.quotePath=false diff)"
rm -rf "$SPACE_TESTREPO"
assert_contains "$SPACE_DIFF" "$(printf '\t')" "strip_data_file_deletes fixture: real git diff header carries the trailing TAB this test exists to cover"
SPACE_STRIPPED="$(printf '%s\n' "$SPACE_DIFF" | strip_data_file_deletes)"
assert_not_contains "$SPACE_STRIPPED" "Jane Placeholder" "strip_data_file_deletes: space-bearing path — deleted content absent"
assert_contains "$SPACE_STRIPPED" "DELETED-LINE-SUPPRESSED" "strip_data_file_deletes: space-bearing path — suppression marker present"

# ── strip_data_file_deletes: guilt, gate 7466 S6 — a deleted line whose
# CONTENT starts with "-- " (SQL/Lua comment syntax) becomes the diff line
# "--- ..." which is NOT a new file header once we're past the real one. ──
DASHDASH_DIFF='diff --git a/research/crm/fake.csv b/research/crm/fake.csv
index 5555555..6666666 100644
--- a/research/crm/fake.csv
+++ b/research/crm/fake.csv
@@ -1,2 +1,1 @@
--- Jane Placeholder row, see above
+-- redacted row'
DASHDASH_STRIPPED="$(printf '%s\n' "$DASHDASH_DIFF" | strip_data_file_deletes)"
assert_not_contains "$DASHDASH_STRIPPED" "Jane Placeholder" "strip_data_file_deletes: '-- ' deleted content absent"
assert_contains "$DASHDASH_STRIPPED" "DELETED-LINE-SUPPRESSED" "strip_data_file_deletes: '-- ' suppression marker present"

# ── innocence: a clean, non-data-file diff passes through unchanged ─────
CLEAN_DIFF='diff --git a/scripts/example.py b/scripts/example.py
index 3333333..4444444 100644
--- a/scripts/example.py
+++ b/scripts/example.py
@@ -1,2 +1,2 @@
-def f():
-    return 1
+def f():
+    return 2'
CLEAN_OUT="$(printf '%s\n' "$CLEAN_DIFF" | strip_data_file_deletes)"
assert_eq "$CLEAN_OUT" "$CLEAN_DIFF" "strip_data_file_deletes: non-data-file diff is byte-identical"

# ── redact_for_external: guilt — no DATABASE_URL/psql at all fails closed
# (gate 7466 blocker 5: --require-dynamic-names is now unconditional). ──
FAKE_PSQL_DIR=""
cleanup_fake_psql() { [[ -n "$FAKE_PSQL_DIR" ]] && rm -rf "$FAKE_PSQL_DIR"; }
trap cleanup_fake_psql EXIT

(unset DATABASE_URL PGURL; redact_for_external "some non-empty text over the min length gate padding padding padding" >/dev/null 2>/tmp/spalla-guilt-err.$$) && RC=0 || RC=$?
assert_eq "$RC" "1" "redact_for_external: no DB at all fails closed"
rm -f /tmp/spalla-guilt-err.$$

# ── redact_for_external: innocence — a fake psql fixture list redacts a
# fixture name, plus the static email/phone patterns keep working. ──────
FAKE_PSQL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/spalla-fake-psql.XXXXXX")"
cat > "$FAKE_PSQL_DIR/psql" <<'PSQLEOF'
#!/usr/bin/env bash
printf '%s\n' "Jane Placeholder"
PSQLEOF
chmod +x "$FAKE_PSQL_DIR/psql"
SYNTH_EMAIL="someone@example.org"
SYNTH_PHONE="081234567890"
FIXTURE="Client contact for Jane Placeholder: ${SYNTH_EMAIL} or ${SYNTH_PHONE}. Padding padding padding padding padding."
REDACTED="$(PATH="$FAKE_PSQL_DIR:$PATH" DATABASE_URL="postgresql://fake:fake@localhost/fake" redact_for_external "$FIXTURE")"
assert_contains "$REDACTED" "[CLIENT-NAME-REDACTED]" "redact_for_external: fake CRM name redacted"
assert_contains "$REDACTED" "[CLIENT-EMAIL-REDACTED]" "redact_for_external: fake email redacted"
assert_contains "$REDACTED" "[PHONE-ID-LOCAL-REDACTED]" "redact_for_external: fake phone redacted"
assert_not_contains "$REDACTED" "Jane Placeholder" "redact_for_external: raw fake name absent from output"
assert_not_contains "$REDACTED" "$SYNTH_EMAIL" "redact_for_external: raw fake email absent from output"
assert_not_contains "$REDACTED" "$SYNTH_PHONE" "redact_for_external: raw fake phone absent from output"

# ── pii_path_hit: .gitignore drift guard (blocker 2, finished) ──────────
# The static half of the refusal list (PII_PATH_PATTERNS) was hand-typed
# against .gitignore's PII-marked entries at write time, with no mechanism
# to notice when .gitignore later GAINS a new PII path shape the list
# doesn't cover — gate 7470 found exactly this gap already live
# ("compliance_report_*.pdf", added to .gitignore for a client compliance
# report, was never added here). Rather than hand-typing a second list to
# compare against (the same failure mode, one file removed), this reads
# .gitignore itself at test time: every non-comment line matching a PII
# keyword becomes ONE representative concrete path (wildcards replaced with
# a literal token, a bare directory gets a synthetic filename appended), and
# pii_path_hit must classify that path as PII. A future .gitignore line that
# matches the keyword regex and ISN'T covered by PII_PATH_PATTERNS or the
# supervisor's dynamic fragments fails this test — the same drift-by-
# construction guarantee scripts/async_review_supervisor.py's fragments
# already have, extended to the hand-typed half.
#
# Deliberately excludes .py entries (scripts/company_crm_extract.py etc. are
# gitignored as one-off local tooling, not because their SOURCE is PII data)
# and one unrelated screenshot-folder name that happens to contain the word
# "Client" — this list is about data-holding paths, the same scope
# PII_PATH_PATTERNS already targets.
GITIGNORE_PII_LINES="$(grep -viE '^\s*#|^\s*$' "$REPO_ROOT/.gitignore" \
    | grep -iE 'crm|/hr/|client|passport|dossier|compliance|dq_clients|dq_orphan|yield-opportunities|wa-corpus|wa-copilot' \
    | grep -v '\.py$' \
    | grep -v '^"Client Portal')"
while IFS= read -r gi_pattern; do
    [[ -z "$gi_pattern" ]] && continue
    candidate="$(printf '%s' "$gi_pattern" | sed 's/\*\*/X/g; s/\*/X/g')"
    if [[ "$candidate" == */ ]]; then
        candidate="${candidate}Xfile"
    fi
    pii_path_hit "$candidate" && R=0 || R=1
    assert_eq "$R" "0" "pii_path_hit: .gitignore drift guard — '$gi_pattern' -> '$candidate' is PII-classed"
done <<< "$GITIGNORE_PII_LINES"

if [[ "$FAIL" -ne 0 ]]; then
    echo "FAILED" >&2
    exit 1
fi
echo "ALL OK"
