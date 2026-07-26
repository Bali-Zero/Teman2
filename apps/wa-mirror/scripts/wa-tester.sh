#!/usr/bin/env bash
# wa-tester.sh — thin wrapper around scripts/wa-tester.ts.
#
# On-demand CLI only — NOT a daemon, NOT in any plist/cron, NOT in the
# wa-mirror accounts roster. See docs/wa-tester.md.
#
# Usage:
#   bash wa-tester.sh --pair
#   bash wa-tester.sh --send-battery battery.json [--out transcript.json]
#   bash wa-tester.sh --status

set -eo pipefail

# Runtime is Pro — non-interactive ssh sessions don't source the shell rc
# files that put Homebrew node/npm on PATH (the well-known ssh-non-interactive
# PATH gotcha; see org runbook). Prepend it explicitly rather than assuming.
export PATH="/opt/homebrew/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$APP_ROOT"
exec npx tsx scripts/wa-tester.ts "$@"
