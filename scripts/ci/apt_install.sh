#!/usr/bin/env bash
# Bounded, fail-closed apt install for CI.
#
# WHY THIS EXISTS (measured 2026-08-18, not reasoned):
#
# `organ-conformance.yml`'s "Require zsh" step ran 10m15s twice on merge_group
# refs — the job's ENTIRE `timeout-minutes: 10` budget — while every other step
# in that job takes 1-28s. Historical durations of the same job: 31s, 1m02s,
# 1m04s, 1m11s, 34s. It does not run slow; `apt-get update` HANGS on the
# mirrorlist, and apt has no timeout of its own.
#
# Why that was invisible: GitHub reports a job budget kill as `cancelled`, NOT
# `failure`. "Every organ is born with its genes" is a REQUIRED status context,
# and a cancelled required check is not green — so merge-queue entries went
# UNMERGEABLE with no failing check anywhere to point at.
#
# The first attempt at a cure was worse than the disease: 3 retries x 180s = 9
# minutes inside a 10-minute budget, so a stalling mirror was GUARANTEED to eat
# the job. Measured on PR #4286: three consecutive 180s kills in `lint`, and in
# `antidotes` the third attempt finally succeeded at 01:29:54 only for the job
# to be cancelled at 01:30:09. Retries do not help when the ceiling exceeds the
# budget.
#
# So: give apt its OWN network timeouts (the actual root cause), keep the total
# wall clock far under any job budget, and fail CLOSED by name.
#
# Usage:
#   apt_install.sh <verify-binary> <package> [package...]
#   apt_install.sh -  <package>...      # '-' = the caller does its own assertion
set -euo pipefail

VERIFY="${1:?usage: apt_install.sh <verify-binary|-> <package>...}"
shift
[ "$#" -gt 0 ] || { echo "apt_install: no package named" >&2; exit 2; }

if [ "$VERIFY" != "-" ] && command -v "$VERIFY" >/dev/null 2>&1; then
  echo "apt_install: ${VERIFY} already present — nothing to install"
  exit 0
fi

# Acquire::*::Timeout is the fix at the source: without it apt waits
# indefinitely on a stalled mirror and the outer `timeout` is the only thing
# that ever fires.
APT_OPTS=(
  -o Acquire::Retries=2
  -o Acquire::http::Timeout=15
  -o Acquire::https::Timeout=15
  -o Acquire::ftp::Timeout=15
  -o DPkg::Lock::Timeout=30
)

# Ceiling: (60 + 60) primary + (60 + 60) fallback = 240s worst case. Every
# caller has at least a 10-minute budget, so a stall now costs four minutes
# and SAYS SO, instead of consuming the job and reporting a cancellation
# nobody can attribute.
if ! timeout 60 sudo apt-get "${APT_OPTS[@]}" update -qq; then
  echo "::warning::apt_install: primary mirror update stalled or failed; attempting install against the existing cache"
fi
timeout 60 sudo apt-get "${APT_OPTS[@]}" install -y -qq "$@" || true

if [ "$VERIFY" = "-" ] || command -v "$VERIFY" >/dev/null 2>&1; then
  echo "apt_install: delivered by primary mirror"
else
  FALLBACK_ATTEMPTED=0
  SOURCE_FILE="${APT_INSTALL_SOURCES_FILE:-}"
  if [ -z "$SOURCE_FILE" ]; then
    if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
      SOURCE_FILE=/etc/apt/sources.list.d/ubuntu.sources
    elif [ -f /etc/apt/sources.list ]; then
      SOURCE_FILE=/etc/apt/sources.list
    fi
  fi

  if [ -z "$SOURCE_FILE" ] || [ ! -f "$SOURCE_FILE" ]; then
    echo "apt_install: no active apt sources file; fallback skipped" >&2
  else
    SOURCE_URL="$(grep -Eo 'https?://[^/[:space:]]+' "$SOURCE_FILE" | head -n 1 || true)"
    SOURCE_HOST="${SOURCE_URL#*://}"
    SOURCE_HOST="${SOURCE_HOST%%/*}"
    if [ -z "$SOURCE_URL" ] || [ -z "$SOURCE_HOST" ]; then
      echo "apt_install: no mirror host in active apt sources; fallback skipped" >&2
    else
      FALLBACK_HOST=archive.ubuntu.com
      [ "$SOURCE_HOST" = "$FALLBACK_HOST" ] && FALLBACK_HOST=us.archive.ubuntu.com
      # apt reads two formats from two places and never mixes them: a one-line
      # `deb ...` file through Dir::Etc::SourceList, and deb822 stanzas
      # (`Types:`/`URIs:`, ubuntu-24.04's sources.list.d/ubuntu.sources) only
      # as a `*.sources` file under Dir::Etc::SourceParts. A deb822 body handed
      # to SourceList dies at once with "Type 'Types:' is not known" (measured
      # 2026-10-07: PR #8037's antidotes run, and ubuntu:24.04 by hand), so a
      # deb822 fallback goes to SourceParts and SourceList is an EMPTY file.
      TMP_SOURCES="$(mktemp)"
      TMP_SOURCE_PARTS="$(mktemp -d)"
      trap 'rm -rf "$TMP_SOURCES" "$TMP_SOURCE_PARTS"' EXIT
      if grep -Eq '^[[:space:]]*(Types|URIs):' "$SOURCE_FILE"; then
        FALLBACK_FORMAT=deb822
        sed "s#://$SOURCE_HOST/#://$FALLBACK_HOST/#g" "$SOURCE_FILE" >"$TMP_SOURCE_PARTS/fallback.sources"
        echo "# apt_install fallback: deb822 sources live in $TMP_SOURCE_PARTS/fallback.sources" >"$TMP_SOURCES"
      else
        FALLBACK_FORMAT=one-line
        sed "s#://$SOURCE_HOST/#://$FALLBACK_HOST/#g" "$SOURCE_FILE" >"$TMP_SOURCES"
      fi
      FALLBACK_ATTEMPTED=1
      echo "::warning::apt_install: primary mirror $SOURCE_HOST did not deliver '$*'; trying $FALLBACK_HOST ($FALLBACK_FORMAT sources)"
      timeout 60 sudo apt-get "${APT_OPTS[@]}" \
        -o "Dir::Etc::SourceList=$TMP_SOURCES" \
        -o "Dir::Etc::SourceParts=$TMP_SOURCE_PARTS" update -qq || true
      timeout 60 sudo apt-get "${APT_OPTS[@]}" \
        -o "Dir::Etc::SourceList=$TMP_SOURCES" \
        -o "Dir::Etc::SourceParts=$TMP_SOURCE_PARTS" install -y -qq "$@" || true
      if command -v "$VERIFY" >/dev/null 2>&1; then
        echo "apt_install: delivered by fallback mirror $FALLBACK_HOST"
      fi
    fi
  fi
  if [ "$FALLBACK_ATTEMPTED" = "1" ] && ! command -v "$VERIFY" >/dev/null 2>&1; then
    echo "apt_install: package '$*' is still unavailable" >&2
  fi
fi

# FAIL-CLOSED. Without this the script would exit 0 after a failed install and
# the caller would go green with the tool absent — the same class of defect
# this file exists to remove. ('-' means the caller asserts instead; it must.)
if [ "$VERIFY" != "-" ]; then
  command -v "$VERIFY"
fi
