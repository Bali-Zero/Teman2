#!/usr/bin/env bash
# Corpus for scripts/install-claude-code.sh — the ONE installer behind all three
# places this repo installs the Claude CLI (the production image, the AI-review
# Action, and the Ruslana node provisioner). It lives at fleet level and not under
# apps/backend-rag/ for exactly that reason: the class audit that cured the first
# two call sites left the third on floating latest.
#
# The defect it guards was NOT reproducible on the machine that writes this test:
# on 2026-08-20 the missing platform tarball was `linux-x64` (and its musl
# sibling) while `darwin-arm64` published normally, so a real `docker build` on an
# M-series Mac succeeded while CI and Fly failed. A corpus that needs the real
# registry would be green on the one machine that most needs it red. So the
# registry is FAKED — `npm`, `node` and `ldd` are shadowed on PATH — and every
# world the script must survive is asserted directly.
#
# GUILT    : a pin whose platform build does not exist fails CLOSED and installs
#            NOTHING; a platform with no builds at all likewise; an install that
#            leaves no `claude` on PATH fails closed; an install that leaves a
#            `claude` which does not RUN fails closed and surfaces the CLI's own
#            reason; a pin that is behind emits the staleness notice.
# INNOCENCE: the ordinary day installs exactly the pin and says nothing alarming;
#            a current pin emits no staleness notice; the platform package is
#            DERIVED, so arm64 and musl each ask about their own tarball.
#
# Run: bash scripts/tests/test_install_claude_code_version_skew.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/install-claude-code.sh"

PASS=0
FAIL=0

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    FAIL=$((FAIL + 1))
}
ok() {
    printf 'ok  : %s\n' "$1"
    PASS=$((PASS + 1))
}

[ -f "${SCRIPT}" ] || {
    echo "FATAL: ${SCRIPT} not found — this corpus is anchored to a file that moved." >&2
    exit 2
}

# ---------------------------------------------------------------------------
# The fake world.
#   build_world <dir> <platform> <arch> <libc> <umbrella-versions> <platform-versions>
# Version lists are space-separated.
# ---------------------------------------------------------------------------
build_world() {
    local dir="$1" platform="$2" arch="$3" libc="$4"
    local umbrella="$5" platver="$6"
    mkdir -p "${dir}/bin"

    cat > "${dir}/bin/node" <<EOF
#!/usr/bin/env bash
# only \`node -p <expr>\` is used by the script under test
if [ "\$1" = "-p" ]; then
  case "\$2" in
    *platform*) echo "${platform}"; exit 0 ;;
    *arch*)     echo "${arch}"; exit 0 ;;
  esac
fi
echo "fake-node: unexpected invocation: \$*" >&2
exit 1
EOF

    cat > "${dir}/bin/ldd" <<EOF
#!/usr/bin/env bash
if [ "${libc}" = "musl" ]; then
  echo "musl libc (x86_64)" >&2
  exit 1
fi
echo "ldd (Debian GLIBC 2.41-1) 2.41"
EOF

    # Records every invocation so the test can assert WHICH package was asked
    # about and WHICH spec was installed — not merely that the script survived.
    cat > "${dir}/bin/npm" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "${dir}/npm-calls.log"
if [ "\$1" = "view" ] && [ "\$3" = "versions" ]; then
  case "\$2" in
    "@anthropic-ai/claude-code")  list="${umbrella}" ;;
    *)                            list="${platver}" ;;
  esac
  [ -z "\$list" ] && exit 1
  printf '[\n'
  sep=""
  for v in \$list; do printf '%s  "%s"' "\$sep" "\$v"; sep=\$',\n'; done
  printf '\n]\n'
  exit 0
fi
if [ "\$1" = "install" ]; then
  spec="\${@: -1}"
  printf '%s\n' "\$spec" >> "${dir}/installed.log"
  if [ "\${FAKE_NPM_INSTALL_BROKEN_CLAUDE:-0}" = "1" ]; then
    # The REAL failure of 2026-08-20: npm exits 0, the JS launcher lands on
    # PATH, and only running it reveals the native binary behind it is absent.
    printf '#!/usr/bin/env bash\necho "Error: claude native binary not installed." >&2\nexit 1\n' > "${dir}/bin/claude"
    chmod +x "${dir}/bin/claude"
  elif [ "\${FAKE_NPM_INSTALL_LEAVES_NO_CLAUDE:-0}" != "1" ]; then
    printf '#!/usr/bin/env bash\necho "2.1.236 (Claude Code)"\n' > "${dir}/bin/claude"
    chmod +x "${dir}/bin/claude"
  fi
  exit 0
fi
echo "fake-npm: unexpected invocation: \$*" >&2
exit 1
EOF

    chmod +x "${dir}/bin/node" "${dir}/bin/ldd" "${dir}/bin/npm"
}

# The fake world is HERMETIC — `${dir}/bin` plus the system coreutils, and nothing
# else. Inheriting the caller's PATH is what made the first draft of the no-claude
# case pass: this machine has a real `claude` at ~/.local/bin/claude, so
# `command -v claude` succeeded in a world whose fake npm had deliberately
# installed none. The probe was measuring its own leaky world, not the script.
HERMETIC_PATH="/usr/bin:/bin"

# run_in_world <dir> [PIN]
run_in_world() {
    local dir="$1"
    local pin="${2:-2.1.236}"
    ( PATH="${dir}/bin:${HERMETIC_PATH}" CLAUDE_CODE_PIN="${pin}" sh "${SCRIPT}" ) \
        > "${dir}/stdout.log" 2> "${dir}/stderr.log"
    echo "$?"
}

# ---------------------------------------------------------------------------
# GUILT 1 — the exact 2026-08-20 world, with the pin set to the bad release.
# A pin is not protection if nothing checks that the pin can install.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.234 2.1.235 2.1.236 2.1.237" \
    "2.1.234 2.1.235 2.1.236"
RC="$(run_in_world "$W" 2.1.237)"
if [ "$RC" = "0" ]; then
    fail "bad-pin world: exited 0 — it pinned to a version with no platform build"
elif [ -s "$W/installed.log" ]; then
    fail "bad-pin world: ran npm install anyway ($(cat "$W/installed.log"))"
elif ! grep -q "cannot confirm a published" "$W/stderr.log"; then
    fail "bad-pin world: failed without naming the missing platform build"
elif ! grep -q "newest: 2.1.236" "$W/stderr.log"; then
    fail "bad-pin world: did not tell the reader which version IS available"
else
    ok "a pin whose platform build does not exist fails closed, installs nothing, names it"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 2 — the platform publishes nothing at all (unsupported arch, or an
# unreachable registry). Must fail closed and say it cannot distinguish the two.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.236 2.1.237" ""
RC="$(run_in_world "$W")"
if [ "$RC" = "0" ]; then
    fail "no-platform-build world: exited 0 — a build with no CLI would have shipped"
elif [ -s "$W/installed.log" ]; then
    fail "no-platform-build world: ran npm install anyway"
elif ! grep -q "registry is unreachable" "$W/stderr.log"; then
    fail "no-platform-build world: asserted 'upstream ships nothing' without admitting it cannot tell that from an unreachable registry"
else
    ok "no platform builds at all fails closed and does NOT overclaim the cause"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 3 — npm exits 0 but nothing named `claude` lands on PATH.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.236" "2.1.236"
RC="$( ( PATH="$W/bin:${HERMETIC_PATH}" CLAUDE_CODE_PIN=2.1.236 \
         FAKE_NPM_INSTALL_LEAVES_NO_CLAUDE=1 sh "${SCRIPT}" ) \
        > "$W/stdout.log" 2> "$W/stderr.log"; echo "$?" )"
if [ "$RC" = "0" ]; then
    fail "no-claude world: exited 0 after installing a CLI that is not on PATH"
else
    ok "a successful npm install that leaves no 'claude' on PATH fails closed"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 4 — THE ACTUAL SHAPE OF THE INCIDENT. From the build log (job
# 96279824564), in order:
#     1.341  added 1 package in 852ms     npm exits 0, no error code
#     1.606  /usr/local/bin/claude        `which claude` SUCCEEDS
#     1.607  Error: claude native binary not installed.
# Neither "npm exited 0" nor "a file named claude exists" is evidence. Only
# running it is — and ai-pr-review.yml never did.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.236" "2.1.236"
RC="$( ( PATH="$W/bin:${HERMETIC_PATH}" CLAUDE_CODE_PIN=2.1.236 \
         FAKE_NPM_INSTALL_BROKEN_CLAUDE=1 sh "${SCRIPT}" ) \
        > "$W/stdout.log" 2> "$W/stderr.log"; echo "$?" )"
if [ "$RC" = "0" ]; then
    fail "broken-binary world: exited 0 — npm said success and a launcher exists, but the CLI does not run"
elif ! grep -q "native binary not installed" "$W/stderr.log"; then
    fail "broken-binary world: failed without surfacing the CLI's own reason"
else
    ok "a claude on PATH that cannot RUN fails closed, and the CLI's own reason is surfaced"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# INNOCENCE 1 — the ordinary day: install exactly the pin, exit 0, no alarm.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.234 2.1.235 2.1.236" \
    "2.1.234 2.1.235 2.1.236"
RC="$(run_in_world "$W")"
if [ "$RC" != "0" ]; then
    fail "ordinary world: exited ${RC} on a perfectly ordinary day ($(tail -2 "$W/stderr.log"))"
elif ! grep -Fxq "@anthropic-ai/claude-code@2.1.236" "$W/installed.log" 2>/dev/null; then
    fail "ordinary world: installed $(cat "$W/installed.log" 2>/dev/null), expected exactly the pin"
elif grep -q "FATAL" "$W/stderr.log"; then
    fail "ordinary world: printed a FATAL on a healthy install"
else
    ok "the ordinary day installs exactly the pin and exits clean"
fi
# ...and says nothing about staleness, because the pin IS the newest installable.
if grep -q "NOTICE" "$W/stdout.log"; then
    fail "ordinary world: emitted a staleness notice while the pin was current"
else
    ok "a current pin emits no staleness notice"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 5 — the pin has fallen behind. This is what re-measures the comment
# claiming "last verified-good"; without it the pin rots in silence.
# It must be a NOTICE, never a failure.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.236 2.1.237 2.1.238" \
    "2.1.236 2.1.238"
RC="$(run_in_world "$W")"
if [ "$RC" != "0" ]; then
    fail "stale-pin world: exited ${RC} — a staleness notice must never break a build"
elif ! grep -q "NOTICE — pin is 2.1.236; 2.1.238 is the newest" "$W/stdout.log"; then
    fail "stale-pin world: no notice naming the newer installable version ($(grep NOTICE "$W/stdout.log" | head -1))"
elif ! grep -Fxq "@anthropic-ai/claude-code@2.1.236" "$W/installed.log"; then
    fail "stale-pin world: the notice changed what got installed — it must not"
else
    ok "a stale pin is reported by name, still installs the pin, and does not fail the build"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# INNOCENCE 2 — the platform package is DERIVED, never hardcoded.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux arm64 glibc "2.1.236" "2.1.236"
RC="$(run_in_world "$W")"
if [ "$RC" != "0" ]; then
    fail "arm64 world: exited ${RC}"
elif ! grep -q "claude-code-linux-arm64 versions" "$W/npm-calls.log"; then
    fail "arm64 world: asked about $(grep -o 'claude-code-[a-z0-9-]*' "$W/npm-calls.log" | head -1), not its own arch"
else
    ok "an arm64 image asks the registry about linux-arm64, not amd64"
fi
rm -rf "$W"

W="$(mktemp -d)"
build_world "$W" linux x64 musl "2.1.236" "2.1.236"
RC="$(run_in_world "$W")"
if ! grep -q "claude-code-linux-x64-musl versions" "$W/npm-calls.log"; then
    fail "musl world: asked about the glibc tarball on a musl image"
else
    ok "a musl image asks the registry about the -musl tarball"
fi
rm -rf "$W"

printf '\n%s passed, %s failed\n' "${PASS}" "${FAIL}"
[ "${FAIL}" -eq 0 ] || exit 1
