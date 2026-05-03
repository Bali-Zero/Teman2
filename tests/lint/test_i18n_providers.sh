#!/usr/bin/env bash
# test_i18n_providers.sh — TDD harness for scripts/lint_i18n_providers.sh.
#
# Builds synthetic mini-trees that mimic apps/mouth/src/app/ shape,
# runs the lint at them, and asserts the exit code + violation count.
# All scratch state lives under a temp dir that is removed on exit.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LINT="$REPO_ROOT/scripts/lint_i18n_providers.sh"

if [[ ! -x "$LINT" ]]; then
  echo "FAIL: lint script not executable at $LINT" >&2
  exit 2
fi

TMP="$(mktemp -d -t lint_i18n_test.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0

assert_exit() {
  local name="$1"
  local expected="$2"
  local root="$3"
  local actual=0
  local out
  out="$(bash "$LINT" --root "$root" 2>&1)" || actual=$?
  if [[ "$actual" -eq "$expected" ]]; then
    pass=$((pass + 1))
    printf 'PASS  %s (exit=%d)\n' "$name" "$actual"
  else
    fail=$((fail + 1))
    printf 'FAIL  %s: expected exit=%d, got exit=%d\n' "$name" "$expected" "$actual"
    printf '      output:\n%s\n' "$out" | sed 's/^/      /'
  fi
}

# --- case 1: provider in route group layout, descendant uses hook -- OK ---
case1="$TMP/case1"
mkdir -p "$case1/(blog)"
cat > "$case1/(blog)/layout.tsx" <<'EOF'
import { I18nProvider } from "@/i18n";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <I18nProvider>{children}</I18nProvider>;
}
EOF
cat > "$case1/(blog)/page.tsx" <<'EOF'
"use client";
import { useTranslation } from "@/i18n";
export default function Page() {
  const { t } = useTranslation();
  return <div>{t("hello")}</div>;
}
EOF
assert_exit "case1: ancestor layout has provider"  0  "$case1"

# --- case 2: descendant uses hook, no provider in chain -- VIOLATION ------
case2="$TMP/case2"
mkdir -p "$case2/(broken)"
cat > "$case2/(broken)/layout.tsx" <<'EOF'
export default function Layout({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}
EOF
cat > "$case2/(broken)/page.tsx" <<'EOF'
"use client";
import { useTranslation } from "@/i18n";
export default function Page() {
  const { t } = useTranslation();
  return <div>{t("hello")}</div>;
}
EOF
assert_exit "case2: missing provider triggers VIOLATION"  1  "$case2"

# --- case 3: page self-wraps in <I18nProvider> -- OK ----------------------
case3="$TMP/case3"
mkdir -p "$case3/portal/login"
cat > "$case3/portal/login/page.tsx" <<'EOF'
"use client";
import { I18nProvider, useTranslation } from "@/i18n";
function Inner() {
  const { t } = useTranslation();
  return <div>{t("hi")}</div>;
}
export default function Page() {
  return <I18nProvider><Inner /></I18nProvider>;
}
EOF
assert_exit "case3: self-provided page is OK"  0  "$case3"

# --- case 4: type-only import is NOT a call -- OK -------------------------
case4="$TMP/case4"
mkdir -p "$case4/(group)"
cat > "$case4/(group)/page.tsx" <<'EOF'
import type { useTranslation } from "@/i18n";
export default function Page() {
  return <div>noop</div>;
}
EOF
assert_exit "case4: type-only import is ignored"  0  "$case4"

# --- case 5: commented-out useTranslation call -- OK ----------------------
case5="$TMP/case5"
mkdir -p "$case5/(group)"
cat > "$case5/(group)/page.tsx" <<'EOF'
export default function Page() {
  // const { t } = useTranslation();
  return <div>noop</div>;
}
EOF
assert_exit "case5: commented-out call is ignored"  0  "$case5"

# --- case 6: nested groups, ancestor (not direct parent) has provider -----
case6="$TMP/case6"
mkdir -p "$case6/portal/(authenticated)/dashboard"
cat > "$case6/portal/layout.tsx" <<'EOF'
import { I18nProvider } from "@/i18n";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <I18nProvider>{children}</I18nProvider>;
}
EOF
cat > "$case6/portal/(authenticated)/layout.tsx" <<'EOF'
export default function Layout({ children }: { children: React.ReactNode }) {
  return <section>{children}</section>;
}
EOF
cat > "$case6/portal/(authenticated)/dashboard/page.tsx" <<'EOF'
"use client";
import { useTranslation } from "@/i18n";
export default function Page() {
  const { t } = useTranslation();
  return <div>{t("hi")}</div>;
}
EOF
assert_exit "case6: deep ancestor provides — chain walk reaches it"  0  "$case6"

# --- case 7: deep descendant in route group with NO provider --- VIOLATION
case7="$TMP/case7"
mkdir -p "$case7/(marketing)/section/sub"
cat > "$case7/(marketing)/layout.tsx" <<'EOF'
export default function Layout({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}
EOF
cat > "$case7/(marketing)/section/sub/page.tsx" <<'EOF'
"use client";
import { useTranslation } from "@/i18n";
export default function Page() {
  const { t } = useTranslation();
  return <div>{t("hi")}</div>;
}
EOF
assert_exit "case7: deep descendant w/o provider — VIOLATION"  1  "$case7"

# --- case 8: empty tree -- OK ---------------------------------------------
case8="$TMP/case8"
mkdir -p "$case8/(empty)"
cat > "$case8/(empty)/layout.tsx" <<'EOF'
export default function Layout({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}
EOF
assert_exit "case8: tree without any useTranslation is OK"  0  "$case8"

# --- summary --------------------------------------------------------------
total=$((pass + fail))
printf '\n--------\n%d/%d passed\n' "$pass" "$total"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
exit 0
