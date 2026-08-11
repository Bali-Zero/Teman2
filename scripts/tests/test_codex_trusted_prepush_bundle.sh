#!/bin/bash
# Guilt + innocence for the trusted pre-push bundle used by unattended Codex.
#
# The nightly runner deliberately checks out a failed branch before its outer
# `git push`.  A normal relative .husky/_ dispatcher would then execute that
# branch's tracked .husky/pre-push and helpers.  This test proves the runner
# uses a bundle copied from a pinned trusted commit instead, and refuses a
# changed bundle before it can be used.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LIB="$REPO_ROOT/scripts/codex_automation_lib.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/codex-trusted-prepush.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0
note_pass() { echo "  ok   $1"; PASS=$((PASS + 1)); }
note_fail() { echo "  FAIL $1" >&2; FAIL=$((FAIL + 1)); }
expect_file() { [ -e "$2" ] && note_pass "$1" || note_fail "$1"; }
expect_absent() { [ ! -e "$2" ] && note_pass "$1" || note_fail "$1"; }

PRIMARY="$TMP/primary"
RUNTIME="$TMP/runtime"
STATE="$TMP/state"
REMOTE="$TMP/remote.git"
TRUSTED_MARKER="$TMP/trusted-hook-ran"
TRUSTED_HELPER_MARKER="$TMP/trusted-helper-ran"
MALICIOUS_MARKER="$TMP/malicious-hook-ran"
MALICIOUS_HELPER_MARKER="$TMP/malicious-helper-ran"

git init -q -b main "$PRIMARY"
git -C "$PRIMARY" config user.name "Codex test"
git -C "$PRIMARY" config user.email "codex-test@example.invalid"
mkdir -p "$PRIMARY/.husky" "$PRIMARY/scripts/ci"
cat > "$PRIMARY/.husky/pre-push" <<'EOF'
#!/bin/sh
set -eu
: "${NUZ_PREPUSH_TRUST_ROOT:?trusted pre-push root required}"
"$NUZ_PREPUSH_TRUST_ROOT/scripts/prepush_classify.py"
touch "$TRUSTED_MARKER"
EOF
cat > "$PRIMARY/scripts/prepush_classify.py" <<'EOF'
#!/bin/sh
set -eu
touch "$TRUSTED_HELPER_MARKER"
EOF
cat > "$PRIMARY/scripts/prepush_suite_lock.sh" <<'EOF'
#!/bin/sh
# trusted suite-lock fixture
exit 0
EOF
cat > "$PRIMARY/scripts/ci/prepush_tip_drift.sh" <<'EOF'
#!/bin/sh
# trusted tip-drift fixture
exit 0
EOF
chmod +x "$PRIMARY/.husky/pre-push" "$PRIMARY/scripts/prepush_classify.py" \
    "$PRIMARY/scripts/prepush_suite_lock.sh" "$PRIMARY/scripts/ci/prepush_tip_drift.sh"
git -C "$PRIMARY" add .
git -C "$PRIMARY" commit -qm "trusted hook bundle fixture"
git init -q --bare "$REMOTE"
git -C "$PRIMARY" remote add origin "$REMOTE"
git -C "$PRIMARY" push -q -u origin main
git -C "$PRIMARY" worktree add -q --detach "$RUNTIME" HEAD

# Checked-out failed branch supplies malicious copies.  A normal Husky
# dispatcher would run these on push; a trusted bundle must not.
cat > "$RUNTIME/.husky/pre-push" <<'EOF'
#!/bin/sh
touch "$MALICIOUS_MARKER"
EOF
cat > "$RUNTIME/scripts/prepush_classify.py" <<'EOF'
#!/bin/sh
touch "$MALICIOUS_HELPER_MARKER"
EOF
chmod +x "$RUNTIME/.husky/pre-push" "$RUNTIME/scripts/prepush_classify.py"

# shellcheck source=/dev/null
source "$LIB"

echo "== GUILT: a branch-controlled hook is not used for unattended push =="
BUNDLE="$(codex_auto_prepare_trusted_prepush "$PRIMARY" "$STATE" HEAD)"
expect_file "trusted pre-push wrapper exists" "$BUNDLE/pre-push"

TRUSTED_MARKER="$TRUSTED_MARKER" \
TRUSTED_HELPER_MARKER="$TRUSTED_HELPER_MARKER" \
MALICIOUS_MARKER="$MALICIOUS_MARKER" \
MALICIOUS_HELPER_MARKER="$MALICIOUS_HELPER_MARKER" \
git -C "$RUNTIME" -c core.hooksPath="$BUNDLE" push -q origin HEAD:refs/heads/autofix-test
expect_file "trusted branch-independent hook ran" "$TRUSTED_MARKER"
expect_file "trusted helper was resolved from the bundle" "$TRUSTED_HELPER_MARKER"
expect_absent "runtime branch hook did not run" "$MALICIOUS_MARKER"
expect_absent "runtime branch helper did not run" "$MALICIOUS_HELPER_MARKER"

echo "== GUILT: every transitive gate artifact is pinned and verified =="
for artifact in \
    .husky/pre-push \
    scripts/prepush_classify.py \
    scripts/prepush_suite_lock.sh \
    scripts/ci/prepush_tip_drift.sh; do
    chmod u+w "$BUNDLE/tree/$artifact"
    printf '%s\n' '#!/bin/sh' 'exit 0' > "$BUNDLE/tree/$artifact"
    if codex_auto_verify_trusted_prepush "$PRIMARY" "$BUNDLE" >/dev/null 2>&1; then
        note_fail "tampered $artifact was accepted"
    else
        note_pass "tampered $artifact is rejected"
    fi
    git -C "$PRIMARY" show "HEAD:$artifact" > "$BUNDLE/tree/$artifact"
    chmod a-w "$BUNDLE/tree/$artifact"
done

echo "== GUILT: the generated wrapper itself is pinned and verified =="
chmod u+w "$BUNDLE/pre-push"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$BUNDLE/pre-push"
if codex_auto_verify_trusted_prepush "$PRIMARY" "$BUNDLE" >/dev/null 2>&1; then
    note_fail "tampered wrapper was accepted"
else
    note_pass "tampered wrapper is rejected"
fi

echo
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
