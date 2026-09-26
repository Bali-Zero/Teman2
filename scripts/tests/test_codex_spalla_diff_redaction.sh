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
# Every name/phone/email here is invented (the email fixture is the same
# "someone@example.org" already used by scripts/tests/test_nb_title_redaction.py,
# the name fixtures are the same "Sofia Mueller"/"Jane Placeholder" already
# used by scripts/test_redact_pii.py and scripts/tests/test_nb_title_redaction.py);
# no real client appears in this file.

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

# ── strip_data_file_deletes: guilt, gate 7466 S6 — a path containing a
# space (the "diff --git a/X b/X" header is genuinely ambiguous for a
# space-bearing path; the fix reads the unambiguous "--- "/"+++ " lines
# instead, which take the whole rest of the line, not an NF-split field). ──
SPACE_DIFF='diff --git a/archive/data file.csv b/archive/data file.csv
index 3333333..4444444 100644
--- a/archive/data file.csv
+++ b/archive/data file.csv
@@ -1,2 +1,1 @@
-Jane Placeholder,081234567890
+redacted,redacted'
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
printf '%s\n' "Sofia Mueller"
PSQLEOF
chmod +x "$FAKE_PSQL_DIR/psql"
SYNTH_EMAIL="someone@example.org"
SYNTH_PHONE="081234567890"
FIXTURE="Client contact for Sofia Mueller: ${SYNTH_EMAIL} or ${SYNTH_PHONE}. Padding padding padding padding padding."
REDACTED="$(PATH="$FAKE_PSQL_DIR:$PATH" DATABASE_URL="postgresql://fake:fake@localhost/fake" redact_for_external "$FIXTURE")"
assert_contains "$REDACTED" "[CLIENT-NAME-REDACTED]" "redact_for_external: fake CRM name redacted"
assert_contains "$REDACTED" "[CLIENT-EMAIL-REDACTED]" "redact_for_external: fake email redacted"
assert_contains "$REDACTED" "[PHONE-ID-LOCAL-REDACTED]" "redact_for_external: fake phone redacted"
assert_not_contains "$REDACTED" "Sofia Mueller" "redact_for_external: raw fake name absent from output"
assert_not_contains "$REDACTED" "$SYNTH_EMAIL" "redact_for_external: raw fake email absent from output"
assert_not_contains "$REDACTED" "$SYNTH_PHONE" "redact_for_external: raw fake phone absent from output"

if [[ "$FAIL" -ne 0 ]]; then
    echo "FAILED" >&2
    exit 1
fi
echo "ALL OK"
