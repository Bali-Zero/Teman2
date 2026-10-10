#!/usr/bin/env bash
# hand_report.sh — phase E, step 1, on Pro: recompute the merger's report.json by hand, the way the tick runs merger.py.
#
# Nothing regenerates report.json on a schedule: since F2 the tick judges READY in memory and writes no report, so the
# operator runs this immediately before `phase_e_flip.py --apply` (about 6 minutes, hundreds of GitHub GETs). It reads the
# code from the mirror's own ref, as the tick does (refs/merger/wrapper, else refs/merger/base, resolved once), extracts
# the same files beside merger.py (the report's stale-verdict judge loads runner.py: without it every hosted-stale row
# stays FALSE_GREEN and READY can never be true; a file missing at that commit fails the run, never a silent judge), and
# runs it in launchd's environment — HOME and PATH only, plus the tick's git isolation. test_hand_report.py keeps the
# file list equal to localci_merger_tick.sh's. "merger report: refusing — <reason>" writes nothing: read the reason — a
# tick appending to the journal at that moment is transient, run it again; an unreadable journal line needs repair first.
#
# Usage: bash scripts/localci/hand_report.sh [STATE_DIR]   (default ~/.nuzantara-pilots/local-ci/merger)
set -euo pipefail
if [ "${LOCALCI_HAND_REPORT_CLEAN:-}" != "$$" ]; then   # the exec keeps the pid: a caller cannot pre-set the sentinel
  exec env -i HOME="$HOME" PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" LOCALCI_HAND_REPORT_CLEAN="$$" /bin/bash "$0" "$@"
fi
STATE="${1:-$HOME/.nuzantara-pilots/local-ci/merger}"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_ATTR_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0   # the tick's isolation
export GIT_CONFIG_COUNT=3 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null GIT_CONFIG_KEY_1=core.fsmonitor \
  GIT_CONFIG_VALUE_1=false GIT_CONFIG_KEY_2=core.attributesFile GIT_CONFIG_VALUE_2=/dev/null
REF=refs/merger/wrapper
SHA="$(git -C "$STATE/repo.git" rev-parse --verify --quiet "$REF^{commit}")" \
  || { REF=refs/merger/base; SHA="$(git -C "$STATE/repo.git" rev-parse --verify "$REF^{commit}")"; }
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-hand-report.XXXXXX")"
trap 'rm -rf "$CODE"' EXIT
for f in merger.py hosted_compare.py runner.py prune.py contexts_matrix.yaml; do   # the tick's files (test_hand_report.py)
  git -C "$STATE/repo.git" show "$SHA:scripts/localci/$f" > "$CODE/$f"
done
echo "hand_report: code ${SHA:0:12} from $REF; state $STATE" >&2
"$STATE/venv/bin/python" -I "$CODE/merger.py" report --repo Bali-Zero/Teman2 --state-dir "$STATE"
