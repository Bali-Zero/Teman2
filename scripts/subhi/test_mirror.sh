#!/usr/bin/env bash
# scripts/subhi/test_mirror.sh — runs the Subhi memory mirror in dry-run
# mode against synthetic fixtures and verifies 11 invariants.
#
# Per addendum B (option B): the mirror writes to a local staging dir,
# never pushes to a separate GitHub repo. Tests reflect that.
#
# Run: bash scripts/subhi/test_mirror.sh
# Expected: "PASS: all 11 assertions" and exit 0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d -t subhi-mirror-test.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

# ----- Fixtures: synthetic memory dir -----
mkdir -p "$TMP/source"

# Safe content (should be mirrored as-is)
cat > "$TMP/source/feedback_safe.md" <<'EOF'
---
name: safe content
---
This is harmless content that must appear in the mirror.
EOF

# Content with a fake secret (must be redacted, file kept)
cat > "$TMP/source/has_secret.md" <<'EOF'
A line with sk-ant-fakekey1234567890abcdefABCDEF and another normal line.
Not redacted: a normal sentence about Bali.
EOF

# Subhi/ folder (must NOT leak)
mkdir -p "$TMP/source/Subhi"
cat > "$TMP/source/Subhi/private.md" <<'EOF'
This must NEVER appear in the mirror.
EOF

# MEMORY.md index referencing both safe and excluded files
cat > "$TMP/source/MEMORY.md" <<'EOF'
# Index
- [Safe](feedback_safe.md)
- [Subhi private](Subhi/private.md)
- [Token audit](discovery_token_audit.md)
- [Has secret](has_secret.md)
EOF

# Discovery token file (must NOT be copied)
cat > "$TMP/source/discovery_token_audit.md" <<'EOF'
Token plaintext details — must not appear in the mirror.
EOF

# ----- Run the mirror in dry-run mode -----
DRY_RUN=1 \
  CONFIG_OVERRIDE_SOURCE_DIR="$TMP/source" \
  CONFIG_OVERRIDE_DEST_DIR="$TMP/dest" \
  bash "$SCRIPT_DIR/subhi-memory-mirror.sh" \
    --config "$SCRIPT_DIR/subhi-memory-mirror.config.yaml" \
    > "$TMP/run.log" 2>&1 || {
  echo "FAIL: mirror script exited non-zero. Log:"
  cat "$TMP/run.log"
  exit 1
}

# ----- Assertions -----
fail() {
  echo "FAIL: $1"
  echo "--- run.log ---"
  cat "$TMP/run.log"
  echo "--- dest tree ---"
  find "$TMP/dest" -type f 2>/dev/null | head -50 || true
  exit 1
}

# 1. feedback_safe.md exists in dest
test -f "$TMP/dest/feedback_safe.md" || fail "1: feedback_safe.md missing in dest"

# 2. Subhi/ dir does NOT exist in dest
test ! -e "$TMP/dest/Subhi" || fail "2: Subhi/ leaked into dest"

# 3. Subhi/private.md does NOT exist in dest
test ! -e "$TMP/dest/Subhi/private.md" || fail "3: Subhi/private.md leaked"

# 4. discovery_token_audit.md does NOT exist in dest
test ! -e "$TMP/dest/discovery_token_audit.md" || fail "4: discovery_token_audit.md leaked"

# 5. has_secret.md exists in dest (with redaction)
test -f "$TMP/dest/has_secret.md" || fail "5: has_secret.md missing in dest"

# 6. has_secret.md contains "REDACTED-secret" string
grep -q "REDACTED-secret" "$TMP/dest/has_secret.md" || fail "6: REDACTED-secret marker missing in has_secret.md"

# 7. has_secret.md does NOT contain raw sk-ant- token
if grep -q "sk-ant-fakekey" "$TMP/dest/has_secret.md"; then
  fail "7: raw sk-ant- token leaked in has_secret.md"
fi

# 8. MEMORY.md exists in dest
test -f "$TMP/dest/MEMORY.md" || fail "8: MEMORY.md missing in dest"

# 9. MEMORY.md does NOT contain "Subhi/" line refs
if grep -q "Subhi/" "$TMP/dest/MEMORY.md"; then
  fail "9: MEMORY.md still references Subhi/"
fi

# 10. MEMORY.md does NOT contain "discovery_token_" line refs
if grep -q "discovery_token_" "$TMP/dest/MEMORY.md"; then
  fail "10: MEMORY.md still references discovery_token_"
fi

# 11. _AUDIT.txt exists with "Excluded:" section
test -f "$TMP/dest/_AUDIT.txt" || fail "11a: _AUDIT.txt missing"
grep -q "Excluded:" "$TMP/dest/_AUDIT.txt" || fail "11b: _AUDIT.txt missing 'Excluded:' section"

echo "PASS: all 11 assertions"
