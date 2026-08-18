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

# Ceiling: 60 + 60 = 120s worst case. Every caller has at least a 10-minute
# budget, so a stall now costs two minutes and SAYS SO, instead of consuming
# the job and reporting a cancellation nobody can attribute.
if ! timeout 60 sudo apt-get "${APT_OPTS[@]}" update -qq; then
  echo "::warning::apt_install: 'apt-get update' stalled or failed; attempting install against the existing cache"
fi
timeout 60 sudo apt-get "${APT_OPTS[@]}" install -y -qq "$@" || true

# FAIL-CLOSED. Without this the script would exit 0 after a failed install and
# the caller would go green with the tool absent — the same class of defect
# this file exists to remove. ('-' means the caller asserts instead; it must.)
if [ "$VERIFY" != "-" ]; then
  command -v "$VERIFY"
fi
