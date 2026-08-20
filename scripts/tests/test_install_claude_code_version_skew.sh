#!/usr/bin/env bash
# Corpus for scripts/install-claude-code.sh — the ONE installer behind all three
# places this repo installs the Claude CLI (the production image, the AI-review
# Action, and the Ruslana node provisioner). It lives at fleet level and not
# under apps/backend-rag/ for exactly that reason: curing only the call site
# that bit us would have left the other two on the unpinned install.
#
# The defect it cures was NOT reproducible on the machine that writes this test:
# on 2026-08-20 the missing platform tarball was `linux-x64` (and its musl
# sibling) while `darwin-arm64` published normally, so a real `docker build` on
# an M-series Mac succeeded while CI and Fly failed. A corpus that needs the
# real registry would therefore be green on the one machine that most needs it
# to be red. So the registry is FAKED — `npm`, `node` and `ldd` are shadowed on
# PATH — and every world the script must survive is asserted directly.
#
# GUILT   : upstream skew installs the newest INSTALLABLE version, not `latest`;
#           a platform with no builds at all fails CLOSED without installing;
#           two packages sharing no version fail closed; a successful npm
#           install that leaves no `claude` on PATH fails closed.
# INNOCENCE: the ordinary lockstep day installs `latest` — byte-for-byte the
#           behaviour of the unpinned install this replaces — and the platform
#           package name is DERIVED from the interpreter, so an arm64 image asks
#           about its own tarball and a musl image about its own.
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
#
# build_world <dir> <platform> <arch> <libc> <umbrella-versions> <platform-versions> <latest>
#
# Version lists are space-separated. `latest` is what `npm view <pkg> version`
# answers — deliberately separate from the umbrella list, because the whole
# defect is `latest` naming a version some OTHER package has not published.
# ---------------------------------------------------------------------------
build_world() {
    local dir="$1" platform="$2" arch="$3" libc="$4"
    local umbrella="$5" platver="$6" latest="$7"
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
if [ "\$1" = "view" ]; then
  pkg="\$2"
  if [ "\$3" = "versions" ]; then
    case "\$pkg" in
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
  if [ "\$3" = "version" ]; then
    [ -z "${latest}" ] && exit 1
    echo "${latest}"
    exit 0
  fi
fi
if [ "\$1" = "install" ]; then
  # last argument is the spec
  spec="\${@: -1}"
  printf '%s\n' "\$spec" >> "${dir}/installed.log"
  if [ "\${FAKE_NPM_INSTALL_BROKEN_CLAUDE:-0}" = "1" ]; then
    # The REAL failure of 2026-08-20: npm exits 0, the JS launcher lands on
    # PATH, and only running it reveals the native binary behind it is absent.
    printf '#!/usr/bin/env bash\necho "Error: claude native binary not installed." >&2\nexit 1\n' > "${dir}/bin/claude"
    chmod +x "${dir}/bin/claude"
  elif [ "\${FAKE_NPM_INSTALL_LEAVES_NO_CLAUDE:-0}" != "1" ]; then
    printf '#!/usr/bin/env bash\necho "1.2.3 (fake)"\n' > "${dir}/bin/claude"
    chmod +x "${dir}/bin/claude"
  fi
  exit 0
fi
echo "fake-npm: unexpected invocation: \$*" >&2
exit 1
EOF

    chmod +x "${dir}/bin/node" "${dir}/bin/ldd" "${dir}/bin/npm"
}

# The fake world is HERMETIC — `${dir}/bin` plus the system coreutils, and
# nothing else. Inheriting the caller's PATH is what made the first draft of
# the no-claude case pass: this machine has a real `claude` at
# ~/.local/bin/claude, so `command -v claude` succeeded in a world whose fake
# npm had deliberately installed none. The probe was measuring its own leaky
# world instead of the script.
HERMETIC_PATH="/usr/bin:/bin"

run_in_world() {
    local dir="$1"
    ( PATH="${dir}/bin:${HERMETIC_PATH}" sh "${SCRIPT}" ) > "${dir}/stdout.log" 2> "${dir}/stderr.log"
    echo "$?"
}

# ---------------------------------------------------------------------------
# GUILT 1 — the exact 2026-08-20 world.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.234 2.1.235 2.1.236 2.1.237" \
    "2.1.234 2.1.235 2.1.236" \
    "2.1.237"
RC="$(run_in_world "$W")"
if [ "$RC" != "0" ]; then
    fail "skew world: script exited ${RC}, expected 0 (2.1.236 was installable)"
elif ! grep -Fxq "@anthropic-ai/claude-code@2.1.236" "$W/installed.log" 2>/dev/null; then
    fail "skew world: installed $(cat "$W/installed.log" 2>/dev/null), expected @2.1.236"
elif grep -Fq "2.1.237" "$W/installed.log" 2>/dev/null; then
    fail "skew world: installed the version whose platform build does not exist"
else
    ok "upstream skew installs 2.1.236, the newest version BOTH packages publish"
fi
# The skew must be announced, not silently absorbed.
if ! grep -qi "UPSTREAM SKEW" "$W/stderr.log"; then
    fail "skew world: fell back silently — the build log never names the skew"
else
    ok "the fallback names the skew on stderr instead of absorbing it"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 2 — no platform build at all: fail CLOSED, and install NOTHING.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.236 2.1.237" "" "2.1.237"
RC="$(run_in_world "$W")"
if [ "$RC" = "0" ]; then
    fail "no-platform-build world: exited 0 — a build with no CLI would have shipped"
elif [ -s "$W/installed.log" ]; then
    fail "no-platform-build world: ran npm install anyway ($(cat "$W/installed.log"))"
elif ! grep -qi "not a defect in this repository" "$W/stderr.log"; then
    fail "no-platform-build world: the diagnostic does not name upstream as the cause"
else
    ok "a platform with no published build fails closed, installs nothing, names upstream"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 3 — the two packages share no version at all.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "3.0.0 3.0.1" "2.1.236" "3.0.1"
RC="$(run_in_world "$W")"
if [ "$RC" = "0" ]; then
    fail "disjoint world: exited 0 with no common version"
elif [ -s "$W/installed.log" ]; then
    fail "disjoint world: installed something ($(cat "$W/installed.log"))"
else
    ok "disjoint version sets fail closed without installing"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 4 — npm reports success but no `claude` lands on PATH.
# The install is not the outcome; a resolvable CLI is.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.237" "2.1.237" "2.1.237"
RC="$( ( PATH="$W/bin:${HERMETIC_PATH}" FAKE_NPM_INSTALL_LEAVES_NO_CLAUDE=1 sh "${SCRIPT}" ) \
        > "$W/stdout.log" 2> "$W/stderr.log"; echo "$?" )"
if [ "$RC" = "0" ]; then
    fail "no-claude world: exited 0 after installing a CLI that is not on PATH"
else
    ok "a successful npm install that leaves no 'claude' on PATH fails closed"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 5 — THE ACTUAL SHAPE OF THE 2026-08-20 FAILURE, and the one an earlier
# draft of this script would have passed.
#
# From the incident's own build log (job 96279824564), in order:
#     1.341  added 1 package in 852ms          npm exits 0, no error code
#     1.606  /usr/local/bin/claude             `which claude` SUCCEEDS
#     1.607  Error: claude native binary not installed.
#
# So neither "npm exited 0" nor "a file called claude exists" is evidence. Only
# RUNNING it is. A guard that stops one step earlier is blind to the disease it
# was written for.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc "2.1.237" "2.1.237" "2.1.237"
RC="$( ( PATH="$W/bin:${HERMETIC_PATH}" FAKE_NPM_INSTALL_BROKEN_CLAUDE=1 sh "${SCRIPT}" ) \
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
# INNOCENCE 1 — the ordinary day is unchanged: `latest` is installed.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.235 2.1.236 2.1.237" "2.1.235 2.1.236 2.1.237" "2.1.237"
RC="$(run_in_world "$W")"
if [ "$RC" != "0" ]; then
    fail "lockstep world: exited ${RC} on a perfectly ordinary day"
elif ! grep -Fxq "@anthropic-ai/claude-code@2.1.237" "$W/installed.log" 2>/dev/null; then
    fail "lockstep world: installed $(cat "$W/installed.log" 2>/dev/null), expected latest @2.1.237"
elif grep -qi "UPSTREAM SKEW" "$W/stderr.log"; then
    fail "lockstep world: cried skew on a day with no skew"
else
    ok "a lockstep day installs latest and says nothing — behaviour unchanged"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# INNOCENCE 2 — the platform package is DERIVED, never hardcoded.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux arm64 glibc "2.1.237" "2.1.237" "2.1.237"
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
build_world "$W" linux x64 musl "2.1.237" "2.1.237" "2.1.237"
RC="$(run_in_world "$W")"
if ! grep -q "claude-code-linux-x64-musl versions" "$W/npm-calls.log"; then
    fail "musl world: asked about the glibc tarball on a musl image"
else
    ok "a musl image asks the registry about the -musl tarball"
fi
rm -rf "$W"

# ---------------------------------------------------------------------------
# GUILT 5 — ordering follows upstream's own list, not a string sort.
# "2.1.9" > "2.1.10" lexically; the newest common version here is 2.1.10.
# ---------------------------------------------------------------------------
W="$(mktemp -d)"
build_world "$W" linux x64 glibc \
    "2.1.8 2.1.9 2.1.10 2.1.11" \
    "2.1.8 2.1.9 2.1.10" \
    "2.1.11"
RC="$(run_in_world "$W")"
if ! grep -Fxq "@anthropic-ai/claude-code@2.1.10" "$W/installed.log" 2>/dev/null; then
    fail "ordering: installed $(cat "$W/installed.log" 2>/dev/null), expected @2.1.10 (a string sort picks 2.1.9)"
else
    ok "the fallback picks 2.1.10 over 2.1.9 — upstream ordering, not a string sort"
fi
rm -rf "$W"

printf '\n%s passed, %s failed\n' "${PASS}" "${FAIL}"
[ "${FAIL}" -eq 0 ] || exit 1
