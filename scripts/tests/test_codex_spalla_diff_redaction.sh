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

# ── blank means tab, CR, LF and space only, in every locale: everything else reaches the redactor ──
#    A stub redactor makes the path visible (a clean body comes back identical either way). Under a UTF-8
#    locale an invalid byte fails a [^[:space:]] match, so a body starting with one read as blank and its
#    email left the machine unredacted (Codex, 2026-10-10); \v, \f and NBSP are not blank either. Each case
#    runs in a child bash started in the locale; the UTF-8 leg uses a locale this host really activates.
# every child runs the interpreter the consumer runs on macOS (bash 3.2), whatever bash is first on PATH
TEST_BASH=/bin/bash
STUB_DIR="$(mktemp -d "${TMPDIR:-/tmp}/spalla-stub.XXXXXX")"
printf 'import sys\nsys.stdin.buffer.read()\nsys.stdout.write("REDACTOR-RAN")\n' > "$STUB_DIR/stub.py"
in_child() {   # in_child <env assignments...> -- <shell prelude> <body>
    local -a envs=()
    while [[ "$1" != -- ]]; do envs+=("$1"); shift; done
    shift
    env ${envs[@]+"${envs[@]}"} SPALLA_REDACTOR_PY="$STUB_DIR/stub.py" "$TEST_BASH" -c "$1"'
. "$1/scripts/lib/spalla_redact.sh"; redact_for_external "$2"' _ "$REPO_ROOT" "$2"
}
UTF8_LOC=""
for L in en_US.UTF-8 C.UTF-8; do
    # a locale is active when a two-byte character counts as one
    if [[ "$(LC_ALL="$L" "$TEST_BASH" -c 'x=$'"'"'\xc3\xa9'"'"'; echo ${#x}' 2>/dev/null)" == 1 ]]; then UTF8_LOC="$L"; break; fi
done
LOCALES=(C)
if [[ -n "$UTF8_LOC" ]]; then LOCALES+=("$UTF8_LOC"); else echo "SKIP: no UTF-8 locale is active on this host; the matrix runs in C only" >&2; fi
for LOC in "${LOCALES[@]}"; do
    for CASE in empty spaces tab-cr-lf vt ff nbsp invalid-byte text; do
        case "$CASE" in
            empty) BODY="" WANT=blank ;;
            spaces) BODY="     " WANT=blank ;;
            tab-cr-lf) BODY=$'\t\r\n \t' WANT=blank ;;   # no trailing newline: $(...) would strip it
            vt) BODY=$'\v' WANT=redactor ;;
            ff) BODY=$'\f' WANT=redactor ;;
            nbsp) BODY=$'\xc2\xa0' WANT=redactor ;;
            invalid-byte) BODY=$'\xff'"someone@example.org" WANT=redactor ;;
            text) BODY="x" WANT=redactor ;;
        esac
        GOT="$(in_child LC_ALL="$LOC" -- '' "$BODY")"
        if [[ "$WANT" == blank ]]; then
            assert_eq "$GOT" "$BODY" "redact_for_external [$LOC]: the $CASE body is blank and comes back as is"
        else
            assert_eq "$GOT" "REDACTOR-RAN" "redact_for_external [$LOC]: the $CASE body goes through the redactor"
        fi
    done
done
# a caller's attributes on LC_ALL: an integer one turned "C" into 0 and let an invalid byte through (Codex,
# 2026-10-10); a readonly one makes every body go to the redactor (fail-closed), blank ones included
if [[ -n "$UTF8_LOC" ]]; then
    GOT="$(in_child LANG="$UTF8_LOC" -- 'unset LC_ALL; declare -i LC_ALL;' $'\xff'"someone@example.org")"
    assert_eq "$GOT" "REDACTOR-RAN" "redact_for_external: an integer LC_ALL in the caller does not make an invalid byte blank"
    GOT="$(in_child -- "readonly LC_ALL=$UTF8_LOC;" $'\xff'"someone@example.org" 2>/dev/null)"
    assert_eq "$GOT" "REDACTOR-RAN" "redact_for_external: a readonly LC_ALL in the caller sends an invalid byte to the redactor"
    # a shadowed unset keeps the integer attribute: only the behavioural locale probe stops the invalid byte (Opus gate)
    GOT="$(in_child LANG="$UTF8_LOC" -- 'unset() { :; }; declare -i LC_ALL;' $'\xff'"someone@example.org" 2>/dev/null)"
    assert_eq "$GOT" "REDACTOR-RAN" "redact_for_external: a shadowed unset with an integer LC_ALL cannot make an invalid byte blank"
fi
# in any locale: a judgement that cannot be made (here LC_ALL cannot be set) is not "blank"
GOT="$(in_child -- "readonly LC_ALL=${UTF8_LOC:-C};" "   " 2>/dev/null)"
assert_eq "$GOT" "REDACTOR-RAN" "redact_for_external: a readonly LC_ALL in the caller sends even a blank body to the redactor"
rm -f "$STUB_DIR/stub.py" && rmdir "$STUB_DIR"
# the real redactor on such a body: refused (fail-closed) or redacted, never returned with the email
set +e
INVALID_OUT="$(LC_ALL="${UTF8_LOC:-C}" "$TEST_BASH" -c '. "$1/scripts/lib/spalla_redact.sh"; redact_for_external "$2"' _ "$REPO_ROOT" $'\xff'"someone@example.org $(printf 'filler line %03d\n' $(seq 1 40))" 2>/dev/null)"
INVALID_RC=$?
set -e
if [[ "$INVALID_RC" -ne 0 || "$INVALID_OUT" != *"someone@example.org"* ]]; then
    echo "ok: redact_for_external [${UTF8_LOC:-C}]: an invalid-byte body never leaves with its email (rc=$INVALID_RC)"
else
    echo "FAIL: redact_for_external returned an invalid-byte body with its email unredacted" >&2
    FAIL=1
fi
# the library never goes back to the substitution that was quadratic on bash 3.2 (a Linux bash 5 would not show
# it): no ${var//...} — named, positional, array or indirect — on a line that is not a comment
if grep -n -E '^[[:space:]]*[^#[:space:]].*\$\{!?([A-Za-z_][A-Za-z0-9_]*|[0-9]+|[@*])(\[[^]]*\])?//' "$REPO_ROOT/scripts/lib/spalla_redact.sh" >&2; then
    echo "FAIL: spalla_redact.sh uses a \${var//...} substitution in code (quadratic on bash 3.2)" >&2
    FAIL=1
else
    echo "ok: spalla_redact.sh has no \${var//...} substitution in code"
fi

# ── large bodies, in /bin/bash (macOS: 3.2, the affected interpreter) under a 60 s watchdog that kills the
#    probe's whole process group, so a quadratic regression fails here instead of hanging (2026-10-10:
#    bash 3.2's ${var//[class]/} was quadratic — an 8 KB diff took 58 s and a 70 KB one never reached the
#    seat). 200 KB of whitespace comes back as is; 200 KB of clean text byte-identical; and in a 200 KB
#    body with one email every other line comes back unchanged, the email is gone, and every call exits 0.
SPEED_PROBE='. "$1/scripts/lib/spalla_redact.sh"
blank="$(printf "%*s" 200000 "")"
text="$(printf "line %06d of a large clean diff\n" $(seq 1 6000))"
pii="$(printf "line %06d of a large diff\n" $(seq 1 3750))
contact someone@example.org for the plan
$(printf "line %06d of a large diff\n" $(seq 3751 7500))"
[[ ${#pii} -ge 200000 ]] || echo "pii-body-too-small"
a="$(redact_for_external "$blank")" || echo "blank-rc"
b="$(redact_for_external "$text" 2>/dev/null)" || echo "text-rc"
c="$(redact_for_external "$pii" 2>/dev/null)" || echo "pii-rc"
[[ "$a" == "$blank" ]] || echo "blank-not-identical"
[[ "$b" == "$text" ]] || echo "text-not-identical"
[[ "$c" != *someone@example.org* ]] || echo "pii-not-redacted"
lines() { printf "%s\n" "$1" | sed -n "$2"; }
[[ "$(lines "$c" 1,3750p)" == "$(lines "$pii" 1,3750p)" && "$(lines "$c" "3752,\$p")" == "$(lines "$pii" "3752,\$p")" ]] || echo "pii-body-changed"
echo PROBE-DONE'
WATCHDOG='my $pid = fork; die "fork: $!" unless defined $pid;
if (!$pid) { setpgrp(0, 0); exec @ARGV or exit 127 }
$SIG{ALRM} = sub { kill "KILL", -$pid; waitpid($pid, 0); exit 142 };
alarm 60; waitpid($pid, 0); exit($? & 127 ? 128 + ($? & 127) : $? >> 8)'
SPEED_START=$SECONDS
set +e
if command -v perl >/dev/null 2>&1; then
    SPEED_OUT="$(perl -e "$WATCHDOG" /bin/bash -c "$SPEED_PROBE" probe "$REPO_ROOT")"
    SPEED_RC=$?
elif command -v timeout >/dev/null 2>&1; then   # coreutils timeout signals the command's whole process group
    SPEED_OUT="$(timeout -s KILL 60 /bin/bash -c "$SPEED_PROBE" probe "$REPO_ROOT")"
    SPEED_RC=$?
else
    SPEED_OUT="no watchdog (neither perl nor timeout)" SPEED_RC=127
fi
set -e
SPEED_S=$((SECONDS - SPEED_START))
if [[ "$SPEED_RC" -eq 0 && "$SPEED_OUT" == "PROBE-DONE" ]]; then
    echo "ok: redact_for_external: three 200 KB bodies (blank, clean, one email) right in ${SPEED_S} s under /bin/bash $(/bin/bash -c 'echo $BASH_VERSION')"
else
    echo "FAIL: redact_for_external on three 200 KB bodies: rc=$SPEED_RC (142 or 137 = the 60 s watchdog fired: quadratic blank check?) out='${SPEED_OUT//$'\n'/ }'" >&2
    FAIL=1
fi

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
