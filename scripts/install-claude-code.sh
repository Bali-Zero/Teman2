#!/bin/sh
# Install the `claude` CLI into the production image at a version that CAN
# actually install on this image's platform.
#
# WHY THIS EXISTS (measured 2026-08-20, not reasoned).
#
# `npm install -g @anthropic-ai/claude-code` — unpinned, which is what the
# Dockerfile did until this file existed — makes a production image build
# depend on a third party publishing ATOMICALLY. It does not.
#
# On 2026-08-19T23:57:54Z the umbrella package published 2.1.237. Its
# `optionalDependencies` demand `@anthropic-ai/claude-code-linux-x64@2.1.237`,
# and that version DID NOT EXIST — `npm view` answered
#
#     npm error code E404
#     npm error 404 No match found for version 2.1.237
#
# while the platform package's newest published build was still 2.1.236
# (19:23:24Z). The umbrella resolved, the platform-native binary did not, the
# postinstall bailed with "the platform-native optional dependency was not
# downloaded", and the Dockerfile's `which claude` gate failed the build. The
# repository had not changed by one line. `Snyk Docker Security` went red on
# PR #4387 at 01:08:56Z; the SAME job had passed minutes earlier on PR #4384,
# whose image built at ~00:55Z.
#
# THE TRAP THAT KEEPS THIS INVISIBLE: `darwin-arm64@2.1.237` and
# `linux-arm64@2.1.237` were published normally. Only `linux-x64` and its musl
# sibling were missing — so `docker build` on an M-series Mac SUCCEEDS while CI
# and Fly fail, and "works for me" is wrong for a structural reason rather than
# by luck. The development machine was incapable of reproducing the red.
#
# WHY NOT A HARD PIN: a pinned number is a measurement of the world frozen into
# a constant that nobody re-takes; it stops receiving upstream fixes and rots
# silently. So the version is PROBED at build time against the artifact this
# image actually needs, and the normal-day behaviour is unchanged: if the
# `latest` dist-tag is installable here, that is exactly what gets installed.
# Only when upstream is mid-publish does this degrade — to the newest version
# both packages agree on — and it SAYS so in the build log.
#
# WHY NOT A RETRY: the missing tarball does not exist. Retrying cannot create
# it. A retry is the remedy that looks right when the cause is "slow"; the
# cause here is "absent".
#
# This is the same shape as the NodeSource 403 recorded in the Dockerfile
# comment above the caller: a third-party input to a production image build
# that moves on its own, invisible to `git diff`. That cure removed the APT
# dependency and left this npm one, of the same class, in place.

set -eu

PKG="@anthropic-ai/claude-code"

# ---------------------------------------------------------------------------
# Which platform build does THIS image need?
#
# Derived from the interpreter that will run the CLI, never hardcoded: an image
# built for a different architecture must ask about its own tarball, not about
# amd64's. `ldd` decides glibc-vs-musl the same way — by asking, not assuming
# the base image is still the Debian one it is today.
# ---------------------------------------------------------------------------
NODE_PLATFORM="$(node -p 'process.platform')"
NODE_ARCH="$(node -p 'process.arch')"

LIBC_SUFFIX=""
if ldd --version 2>&1 | grep -qi musl; then
    LIBC_SUFFIX="-musl"
fi

PLATFORM_PKG="${PKG}-${NODE_PLATFORM}-${NODE_ARCH}${LIBC_SUFFIX}"

echo "claude-code: this image needs ${PLATFORM_PKG}"

# ---------------------------------------------------------------------------
# Read both version lists.
#
# `npm view <pkg> versions --json` prints a JSON array (or a bare string when a
# package has exactly one version). Quoted semver tokens are extracted rather
# than the JSON parsed, so this needs no jq in the image.
#
# Every capture is `|| true`-guarded and then checked for emptiness EXPLICITLY:
# under `set -e` a bare pipeline whose last stage finds nothing would abort the
# script here, and every diagnostic below it would be unreachable code on the
# one path it exists for.
# ---------------------------------------------------------------------------
list_versions() {
    npm view "$1" versions --json 2>/dev/null | grep -o '"[0-9][^"]*"' | tr -d '"' || true
}

PLATFORM_VERSIONS="$(list_versions "${PLATFORM_PKG}")"
if [ -z "${PLATFORM_VERSIONS}" ]; then
    echo "FATAL: ${PLATFORM_PKG} has no published versions on the npm registry." >&2
    echo "       Upstream ships no build for ${NODE_PLATFORM}/${NODE_ARCH}${LIBC_SUFFIX}." >&2
    echo "       This is an UPSTREAM publishing gap, not a defect in this repository." >&2
    exit 1
fi

UMBRELLA_VERSIONS="$(list_versions "${PKG}")"
if [ -z "${UMBRELLA_VERSIONS}" ]; then
    echo "FATAL: ${PKG} has no published versions on the npm registry." >&2
    echo "       The registry is unreachable or the package moved." >&2
    echo "       This is an UPSTREAM condition, not a defect in this repository." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Prefer `latest` — normal-day behaviour is byte-for-byte what the unpinned
# install did. Fall back only when upstream is mid-publish.
# ---------------------------------------------------------------------------
LATEST="$(npm view "${PKG}" version 2>/dev/null || true)"

CC_VERSION=""
if [ -n "${LATEST}" ] && printf '%s\n' "${PLATFORM_VERSIONS}" | grep -Fxq "${LATEST}"; then
    CC_VERSION="${LATEST}"
    echo "claude-code: latest (${LATEST}) has a published ${PLATFORM_PKG} build"
else
    # The newest version BOTH packages publish. Ordered by the umbrella's own
    # list so the choice follows upstream's ordering rather than a string sort,
    # which gets 2.1.9-vs-2.1.10 wrong.
    PLATFORM_LIST_FILE="$(mktemp)"
    printf '%s\n' "${PLATFORM_VERSIONS}" > "${PLATFORM_LIST_FILE}"
    CC_VERSION="$(printf '%s\n' "${UMBRELLA_VERSIONS}" | grep -Fxf "${PLATFORM_LIST_FILE}" | tail -n 1 || true)"
    rm -f "${PLATFORM_LIST_FILE}"

    if [ -z "${CC_VERSION}" ]; then
        echo "FATAL: no version of ${PKG} has a matching ${PLATFORM_PKG} build." >&2
        echo "       The two packages share no version at all." >&2
        echo "       This is an UPSTREAM publishing gap, not a defect in this repository." >&2
        exit 1
    fi

    echo "claude-code: UPSTREAM SKEW — latest is '${LATEST:-<unreadable>}' but ${PLATFORM_PKG}" >&2
    echo "claude-code: has no such build; falling back to ${CC_VERSION}, the newest both publish." >&2
fi

echo "claude-code: installing ${PKG}@${CC_VERSION}"
npm install -g "${PKG}@${CC_VERSION}"

# The install is not the outcome, and NEITHER IS A FILE ON PATH.
#
# An earlier draft of this block checked only `command -v claude` and then
# printed `claude --version 2>/dev/null || echo '<version unreadable>'`. That
# would have passed the exact failure this script exists for. Read the build log
# of the incident (job 96279824564) in order:
#
#     1.341  added 1 package in 852ms          <- npm exits 0. No error code.
#     1.606  /usr/local/bin/claude             <- `which claude` SUCCEEDS.
#     1.607  Error: claude native binary not installed.
#
# npm reports success; the JS launcher lands on PATH; only the CLI's own
# runtime self-check knows the native binary behind it is missing. A guard that
# stops at "is there a file called claude" is blind to the whole disease, and
# `2>/dev/null || echo` would have swallowed the one line that tells the truth.
#
# So `claude --version` is an ASSERTION here, not a decoration — and it matters
# beyond this file: the Dockerfile ends its RUN chain with `&& claude --version`
# and would have caught it anyway, but `.github/workflows/ai-pr-review.yml` and
# `scripts/ruslana-node/install.sh` call this script with nothing after it. A
# check that lives only in one of three callers is not a check.
command -v claude >/dev/null 2>&1 || {
    echo "FATAL: ${PKG}@${CC_VERSION} installed but no 'claude' landed on PATH." >&2
    exit 1
}

CC_REPORTED_VERSION="$(claude --version 2>&1)" || {
    echo "FATAL: ${PKG}@${CC_VERSION} installed and 'claude' is on PATH, but it does not run:" >&2
    echo "${CC_REPORTED_VERSION}" >&2
    echo "       npm exiting 0 is not proof the CLI works — the platform-native binary" >&2
    echo "       behind the launcher can be missing while every earlier step succeeds." >&2
    exit 1
}
echo "claude-code: installed ${CC_REPORTED_VERSION}"
