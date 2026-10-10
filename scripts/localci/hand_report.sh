#!/usr/bin/env bash
# hand_report.sh — phase E, step 1, on Pro: recompute the merger's report.json by hand, the way the tick runs merger.py.
#
# Nothing regenerates report.json on a schedule: since F2 the tick judges READY in memory and writes no report, so the
# operator runs this immediately before `phase_e_flip.py --apply` (about 4 minutes, hundreds of GitHub GETs). It reads the
# code from the mirror's own ref, as the tick does (refs/merger/wrapper, else refs/merger/base), extracts the same files
# beside merger.py (the report's stale-verdict judge loads runner.py: without it every hosted-stale row stays FALSE_GREEN
# and READY can never be true), and runs it in launchd's environment — HOME and PATH only. test_hand_report.py keeps the
# file list equal to localci_merger_tick.sh's. A "refusing" exit (a tick was appending to the journal) writes nothing:
# run it again.
#
# Usage: bash scripts/localci/hand_report.sh [STATE_DIR]   (default ~/.nuzantara-pilots/local-ci/merger)
set -euo pipefail
if [ "${LOCALCI_HAND_REPORT_CLEAN:-}" != 1 ]; then   # nothing of the caller's shell reaches git or the report but HOME
  exec env -i HOME="$HOME" PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" LOCALCI_HAND_REPORT_CLEAN=1 /bin/bash "$0" "$@"
fi
STATE="${1:-$HOME/.nuzantara-pilots/local-ci/merger}"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
REF=refs/merger/wrapper
git -C "$STATE/repo.git" rev-parse --quiet --verify "$REF^{commit}" >/dev/null || REF=refs/merger/base
CODE="$(mktemp -d "${TMPDIR:-/tmp}/localci-hand-report.XXXXXX")"
trap 'rm -rf "$CODE"' EXIT
for f in merger.py hosted_compare.py runner.py prune.py contexts_matrix.yaml; do   # the tick's files (test_hand_report.py)
  git -C "$STATE/repo.git" show "$REF:scripts/localci/$f" > "$CODE/$f"
done
echo "hand_report: code $(git -C "$STATE/repo.git" rev-parse --short=12 "$REF") from $REF; state $STATE" >&2
"$STATE/venv/bin/python" -I "$CODE/merger.py" report --repo Bali-Zero/Teman2 --state-dir "$STATE"
