#!/bin/sh
# Install the `claude` CLI at a DELIBERATE, pinned version — and prove it works.
#
# ── WHY A PIN, AND WHY THIS FILE OWNS IT ────────────────────────────────────
#
# On 2026-08-19T23:57:54Z upstream published `@anthropic-ai/claude-code@2.1.237`
# whose `optionalDependencies` demand `@anthropic-ai/claude-code-linux-x64@2.1.237`
# — a version that was never published (`npm view` → E404; that platform package
# was still at 2.1.236 from 19:23:24Z, and the musl sibling likewise). Every
# unpinned `npm install -g` on linux-x64 then produced a CLI that could not run.
#
# READ THE FAILURE IN ORDER, because it is not where you would look. From the
# build log of job 96279824564:
#
#   1.341  added 1 package in 852ms     <- npm exits 0. NO error code at all.
#   1.606  /usr/local/bin/claude        <- `which claude` SUCCEEDS.
#   1.607  Error: claude native binary not installed.
#
# npm reported success and the JS launcher landed on PATH. Only `claude --version`
# — the CLI's own runtime self-check — knew. Grepping that log for `npm error`
# finds nothing, which is exactly how this reads as someone else's problem.
#
# The trap that kept it invisible: `linux-arm64@2.1.237` and `darwin-arm64@2.1.237`
# published normally. Only linux-x64 (and musl) were missing — so `docker build` on
# an M-series Mac SUCCEEDS while CI and Fly fail, and the machine most likely to be
# used for triage is structurally unable to reproduce the red.
#
# PR #4390 answered this by pinning to 2.1.236, deliberately, at two call sites,
# with the rule "bump after verifying the install flow, never back to floating
# latest". That decision stands and this file implements it rather than replacing
# it — an earlier draft of this script auto-resolved to "the newest version that
# CAN install", which is a weaker promise: a version that installs is not a version
# that WORKS, and adopting an unverified release automatically is how you inherit
# the next bad one without anyone deciding to.
#
# What this file adds to a bare `npm install -g <pkg>@<pin>`:
#
#   1. ONE pin, not three. It lived in the Dockerfile and in ai-pr-review.yml, and
#      scripts/ruslana-node/install.sh was still on floating latest — a class audit
#      that named three call sites and cured two.
#   2. The pin is VERIFIED INSTALLABLE for this image's own platform before the
#      install, so an upstream partial publish fails with a sentence naming
#      upstream instead of a mystery three steps later.
#   3. The CLI is RUN, not merely located. `command -v claude` succeeded during the
#      whole incident. Only `claude --version` disagreed, and ai-pr-review.yml never
#      ran it at all.
#   4. The pin does not rot silently. Every run reports whether a newer installable
#      version exists — a NOTICE, never a failure. A comment that says "2.1.236 is
#      last verified-good, bump deliberately" is a countdown unless something
#      re-measures it; this is that something.
#
# Corpus (fake registry, both skew directions): scripts/tests/test_install_claude_code_version_skew.sh

set -eu

PKG="@anthropic-ai/claude-code"

# ── THE PIN ─────────────────────────────────────────────────────────────────
# Single source of truth for all three call sites. Bump DELIBERATELY, in a PR,
# after verifying the install flow in a real build. Never set to "latest".
# 2.1.236 (2026-08-18T18:45Z) is the last verified-good release; 2.1.237 is the
# one that shipped without a linux-x64 build.
PINNED_VERSION="${CLAUDE_CODE_PIN:-2.1.236}"

# ── Which platform build does THIS machine need? ────────────────────────────
# Derived from the interpreter that will run the CLI, never hardcoded: this same
# script runs in a linux/amd64 image, on a linux-x64 CI runner, and on an
# arm64 Mac. `ldd` decides glibc-vs-musl by asking, not by assuming the base
# image is still the Debian one it is today.
NODE_PLATFORM="$(node -p 'process.platform')"
NODE_ARCH="$(node -p 'process.arch')"

LIBC_SUFFIX=""
if ldd --version 2>&1 | grep -qi musl; then
    LIBC_SUFFIX="-musl"
fi

PLATFORM_PKG="${PKG}-${NODE_PLATFORM}-${NODE_ARCH}${LIBC_SUFFIX}"

echo "claude-code: pin ${PINNED_VERSION}; this machine needs ${PLATFORM_PKG}"

# ── Read the platform package's published versions ──────────────────────────
# `npm view <pkg> versions --json` prints a JSON array (or a bare string for a
# single-version package). Quoted semver tokens are extracted rather than the
# JSON parsed, so this needs no jq in the image.
#
# Every capture is `|| true`-guarded and then checked for emptiness EXPLICITLY:
# under `set -e` a bare pipeline whose last stage matches nothing would abort the
# script here, and every diagnostic below it would be unreachable code on the one
# path it exists for.
list_versions() {
    npm view "$1" versions --json 2>/dev/null | grep -o '"[0-9][^"]*"' | tr -d '"' || true
}

PLATFORM_VERSIONS="$(list_versions "${PLATFORM_PKG}")"

if ! printf '%s\n' "${PLATFORM_VERSIONS}" | grep -Fxq "${PINNED_VERSION}"; then
    echo "FATAL: cannot confirm a published ${PLATFORM_PKG}@${PINNED_VERSION}." >&2
    if [ -z "${PLATFORM_VERSIONS}" ]; then
        echo "       That package reports NO versions at all — either upstream ships no" >&2
        echo "       build for ${NODE_PLATFORM}/${NODE_ARCH}${LIBC_SUFFIX}, or the registry is unreachable." >&2
    else
        echo "       It publishes other versions but not this one (newest: $(printf '%s\n' "${PLATFORM_VERSIONS}" | tail -n 1))." >&2
    fi
    echo "       Installing anyway is exactly the 2026-08-20 failure: npm would exit 0" >&2
    echo "       and the CLI would not run. Fix the pin, or wait for upstream." >&2
    exit 1
fi

# ── Install the pin ─────────────────────────────────────────────────────────
echo "claude-code: installing ${PKG}@${PINNED_VERSION}"
npm install -g "${PKG}@${PINNED_VERSION}"

# ── Prove it RUNS. A file named `claude` is not evidence. ───────────────────
# `command -v claude` succeeded throughout the incident this script exists for;
# only running it disagreed. The Dockerfile ends its RUN chain with
# `&& claude --version` and would have caught it there, but ai-pr-review.yml and
# scripts/ruslana-node/install.sh call this script with nothing after it — a check
# that lives in one of three callers is not a check.
command -v claude >/dev/null 2>&1 || {
    echo "FATAL: ${PKG}@${PINNED_VERSION} installed but no 'claude' landed on PATH." >&2
    exit 1
}

CC_REPORTED_VERSION="$(claude --version 2>&1)" || {
    echo "FATAL: ${PKG}@${PINNED_VERSION} installed and 'claude' is on PATH, but it does not run:" >&2
    echo "${CC_REPORTED_VERSION}" >&2
    echo "       npm exiting 0 is not proof the CLI works — the platform-native binary" >&2
    echo "       behind the launcher can be missing while every earlier step succeeds." >&2
    exit 1
}
echo "claude-code: installed ${CC_REPORTED_VERSION}"

# ── What re-measures the pin ────────────────────────────────────────────────
# A NOTICE, never a failure: a pin that nobody revisits stops receiving upstream
# fixes, and the comment declaring it "last verified-good" ages into a false
# statement with nothing to contradict it. This prints, in every build log, how
# far behind the pin actually is. It must never break a build, so a registry it
# cannot read simply says so.
UMBRELLA_VERSIONS="$(list_versions "${PKG}")"
if [ -n "${UMBRELLA_VERSIONS}" ]; then
    _common_file="$(mktemp)"
    printf '%s\n' "${PLATFORM_VERSIONS}" > "${_common_file}"
    NEWEST_INSTALLABLE="$(printf '%s\n' "${UMBRELLA_VERSIONS}" | grep -Fxf "${_common_file}" | tail -n 1 || true)"
    rm -f "${_common_file}"
    if [ -n "${NEWEST_INSTALLABLE}" ] && [ "${NEWEST_INSTALLABLE}" != "${PINNED_VERSION}" ]; then
        echo "claude-code: NOTICE — pin is ${PINNED_VERSION}; ${NEWEST_INSTALLABLE} is the newest version"
        echo "claude-code: both ${PKG} and ${PLATFORM_PKG} publish. Bump deliberately after"
        echo "claude-code: verifying the install flow — this notice is not a failure."
    fi
else
    echo "claude-code: NOTICE — could not read ${PKG} versions; pin staleness not measured this run."
fi
