#!/usr/bin/env bash
# Guilt + innocence for scripts/lib/spalla_redact.sh and the PII-classed-path
# guard in .claude/scripts/codex-spalla.sh (cicatrix W140, 2026-09-26): a
# PII-removal PR was reviewed by codex-spalla.sh, which embedded the raw
# diff — 959 deleted lines of a client plan.jsonl (full_name records) — in
# the prompt sent to Codex/OpenAI in cleartext. Fixed by (1) redacting every
# body through the canonical scripts/_redact_pii.py before it leaves the
# machine, (2) never embedding a deleted line of a .jsonl/.csv/.xlsx file at
# all, (3) refusing outright when the diff touches a PII-classed path.
#
# Every name/phone/email here is invented (the email fixture is the same
# "someone@example.org" already used by scripts/tests/test_nb_title_redaction.py);
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

# ── pii_path_hit: guilt + innocence ──────────────────────────────────────
pii_path_hit "research/crm/fake-client.txt" && R1=0 || R1=1
assert_eq "$R1" "0" "pii_path_hit: research/crm/ is PII-classed"
pii_path_hit "research/visa/clients/fake.md" && R2=0 || R2=1
assert_eq "$R2" "0" "pii_path_hit: research/*/clients/ is PII-classed"
pii_path_hit "apps/backend-rag/main.py" && R3=0 || R3=1
assert_eq "$R3" "1" "pii_path_hit: ordinary app code is innocent"

# ── redact_for_external: guilt (fake email + fake ID-local phone) ───────
SYNTH_EMAIL="someone@example.org"
SYNTH_PHONE="081234567890"
FIXTURE="Client contact for the fake case: ${SYNTH_EMAIL} or ${SYNTH_PHONE}. Nothing else in this line is PII-shaped so the gate has enough remaining chars."
REDACTED="$(redact_for_external "$FIXTURE")"
assert_contains "$REDACTED" "[CLIENT-EMAIL-REDACTED]" "redact_for_external: fake email redacted"
assert_contains "$REDACTED" "[PHONE-ID-LOCAL-REDACTED]" "redact_for_external: fake phone redacted"
assert_not_contains "$REDACTED" "$SYNTH_EMAIL" "redact_for_external: raw fake email absent from output"
assert_not_contains "$REDACTED" "$SYNTH_PHONE" "redact_for_external: raw fake phone absent from output"

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
CLEAN_REDACTED="$(redact_for_external "$CLEAN_OUT")"
assert_eq "$CLEAN_REDACTED" "$CLEAN_OUT" "redact_for_external: PII-free diff is byte-identical"

# ── speed: the blank check is linear (2026-10-10: bash 3.2's ${var//[class]/} was quadratic — an 8 KB
#    diff took 58 s in it and a 70 KB one never reached the seat). 200 KB of whitespace (the blank path,
#    returned as is) and 200 KB of text (the redactor path) must both finish well inside 30 s.
BIG_BLANK="$(printf '%*s' 200000 '')"
BIG_TEXT="$(printf 'line %06d of a large clean diff\n' $(seq 1 6000))"
SPEED_START=$SECONDS
BIG_BLANK_OUT="$(redact_for_external "$BIG_BLANK")"
BIG_TEXT_OUT="$(redact_for_external "$BIG_TEXT")"
SPEED_S=$((SECONDS - SPEED_START))
assert_eq "${#BIG_BLANK_OUT}" "${#BIG_BLANK}" "redact_for_external: 200 KB of whitespace comes back as is"
assert_eq "$BIG_TEXT_OUT" "$BIG_TEXT" "redact_for_external: a 200 KB clean diff comes back byte-identical"
if [[ "$SPEED_S" -lt 30 ]]; then echo "ok: redact_for_external: 400 KB in ${SPEED_S} s"; else echo "FAIL: redact_for_external took ${SPEED_S} s on 400 KB (quadratic blank check?)" >&2; FAIL=1; fi

# ── end-to-end guilt: the wrapper itself refuses on a PII-classed path ──
# Skipped (not failed) when the codex CLI isn't installed/logged in on this
# host — the refusal below fires before any `codex exec` call, so running
# it is safe even though this is the real wrapper against the real repo.
if command -v codex >/dev/null 2>&1 && codex login status 2>&1 | grep -qi "Logged in using ChatGPT"; then
    TESTFILE="research/crm/fake-test-pii-guard-$$.txt"
    printf 'synthetic test artifact — spalla-pii-guard-0927, safe to delete\n' > "$REPO_ROOT/$TESTFILE"
    trap 'rm -f "$REPO_ROOT/$TESTFILE"' EXIT
    set +e
    E2E_OUT="$(cd "$REPO_ROOT" && "$REPO_ROOT/.claude/scripts/codex-spalla.sh" review main "spalla-pii-guard-0927 self-test" 2>&1)"
    E2E_RC=$?
    set -e
    rm -f "$REPO_ROOT/$TESTFILE"
    trap - EXIT
    assert_eq "$E2E_RC" "7" "wrapper: exit 7 when diff touches research/crm/"
    assert_contains "$E2E_OUT" "REFUSED" "wrapper: refusal message present"
    assert_contains "$E2E_OUT" "$TESTFILE" "wrapper: refusal names the matched path"
else
    echo "SKIP: codex CLI not installed/logged in — skipping end-to-end refusal test" >&2
fi

if [[ "$FAIL" -ne 0 ]]; then
    echo "FAILED" >&2
    exit 1
fi
echo "ALL OK"
