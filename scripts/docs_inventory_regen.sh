#!/bin/bash
# docs_inventory_regen.sh — generate volatile documentation state as artifacts.
#
# Single source of truth for an ephemeral documentation-state bundle:
#   - docs-sync.json: live/tree-derived counts and atlases
#   - docs-audit.json: audit summary
#   - DOCS_INVENTORY.md: rendered inventory
#
# The bundle is written under DOCS_DERIVED_OUTPUT_DIR (default:
# .artifacts/docs-derived-state) and never changes tracked documentation.
#
# P3-prime (2026-07-17, research/operations/2026-07-17-push-pipeline-optimization-spec.md
# §P3): docs_audit.py --regen-only runs in a "write mode" that deterministically stamps
# `orphan_flipped_on` on any doc that just crossed its `orphan_eligible_on` date.
# DOCS_AUDIT_STATS_JSON may override the JSON summary destination.
#
# DEFAULT MODE vs --organ (footgun fix, 2026-07-19 — PR #2626 landing incident):
#   default (no args): GATE-CONSISTENT — passes docs_audit.py --gate-consistent, which
#     never invents a fresh orphan flip and reads provenance from --trusted-ref.
#   --organ: the OLD dated/wall-clock behavior, explicitly opted into — passes
#     docs_audit.py --as-of "$(date -u +%Y-%m-%d)" (real "today"; this is the ONE
#     legitimate place in the whole pipeline allowed to consult wall-clock for the
#     orphan-eligibility TIME-CROSSING decision — --check, the PR gate, never does). ONLY
#     the scheduled refresh organ (.github/workflows/docs-inventory-refresh.yml) should
#     pass this — it is the one caller whose entire job IS advancing flips from real time.
#
# Exit code: 0 for a completed bundle. docs_audit.py's expected content-change
# exit 1 is accepted; genuine generator crashes propagate.
#
# Usage: scripts/docs_inventory_regen.sh            (no args; gate-consistent; run from
#                                                      anywhere, cd's to repo root)
#        scripts/docs_inventory_regen.sh --organ     (dated/wall-clock mode; scheduled
#                                                      refresh organ ONLY)
#        DOCS_AUDIT_STATS_JSON=/path/to/out.json scripts/docs_inventory_regen.sh [--organ]
#          (also writes the --json stats payload to that path)
#
# Arg parsing is STRICT (R1 review, 2026-07-20): anything other than zero
# args or exactly `--organ` (unknown flag, `--organ` misplaced as $2, a
# typo) exits 2 with an explicit error — it never silently falls through to
# gate-consistent mode.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Strict arg validation (R1 red-team, 2026-07-20, PR #2863 review): the
# original version only ever inspected `${1:-}` — any OTHER argument
# (typo'd flag, `--organ` passed as $2, an unrelated flag like `--quiet`)
# silently fell through to the ORGAN_MODE=false branch with zero error,
# meaning a misconfigured caller silently got gate-consistent mode instead
# of organ mode (or vice versa) with no signal anything was wrong — the
# same "footgun via silent default" class this script exists to cure, just
# one layer up at the CLI-parsing level. Now: accept ONLY zero args or
# exactly one arg that is literally `--organ`; anything else is a hard
# usage error (exit 2), never a silent fallback.
ORGAN_MODE=false
case "$#" in
  0)
    ;;
  1)
    if [[ "$1" == "--organ" ]]; then
      ORGAN_MODE=true
    else
      echo "docs_inventory_regen.sh: unknown argument '$1' (only '--organ' is accepted, or no arguments at all)" >&2
      exit 2
    fi
    ;;
  *)
    echo "docs_inventory_regen.sh: too many arguments — only a single optional '--organ' is accepted, got: $*" >&2
    exit 2
    ;;
esac

# Advisory only — never changes this script's exit code. See the helper's
# header for the 2026-08-07 measurement (PR #3750) and for why this warns
# instead of refusing: regenerating to resolve a DOCS_INVENTORY.md conflict is
# the CORRECT use, it just has to be repeated once the merge commit exists.
#
# Absence is a HARD error, not a shrug: this script runs without `set -e`, so a
# failed `.` would sail on and leave `warn_if_merge_in_progress` undefined —
# the guard would be gone with nothing saying so (superscar #2, exists-but-not-
# armed). Same posture as the strict arg parsing below: never a silent fallback.
MERGE_STATE_LIB="$SCRIPT_DIR/lib/git_merge_state.sh"
if [[ ! -f "$MERGE_STATE_LIB" ]]; then
  echo "docs_inventory_regen: missing $MERGE_STATE_LIB — broken checkout, refusing to run half-armed" >&2
  exit 2
fi
# shellcheck source=scripts/lib/git_merge_state.sh
. "$MERGE_STATE_LIB"
warn_if_merge_in_progress "$SCRIPT_DIR/.."

if [[ "$ORGAN_MODE" == "true" ]]; then
  TIME_MODE_ARGS=(--as-of "$(date -u +%Y-%m-%d)")
else
  TIME_MODE_ARGS=(--gate-consistent)
fi

# Shared audit policy. The CI generator-correctness job calls this wrapper.
WHITELIST_ARGS=(
  --whitelist "docs/ARCHITECTURE_DECISION_RECORDS.md"
  --whitelist "docs/API_REFERENCE.md"
  --whitelist "AUTONOMOUS_OPS.md"
  --whitelist "docs/PRO_AIR_CONNECTION.md"
)

CLUSTER_ARGS=(
  --cluster "automation-autonomy:docs/archive/autonomy-history/AUTOMATION_AUTONOMY_PLAN_v3_1.md,docs/archive/autonomy-history/AUTOMATION_AUTONOMY_SYSTEM_V3_2.md,docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md,docs/archive/autonomy-history/AUTOMATION_AUTONOMY_NB1_SUBMISSION.md:docs/AUTOMATION_AUTONOMY_SYSTEM_V3_3.md"
  --cluster "automations-catalog:docs/archive/ACTIVE_AUTOMATIONS.md,docs/archive/AUTOMATION_MODEL_MAP.md,docs/AUTOMATIONS.md:docs/AUTOMATIONS.md"
  --cluster "system-map:docs/archive/system-map-history/SYSTEM_MAP_4D.md,docs/archive/system-map-history/SYSTEM_OVERVIEW.md,docs/archive/system-map-history/CODEBASE_THEMATIC_AREAS.md,docs/LIVING_ARCHITECTURE.md:docs/LIVING_ARCHITECTURE.md"
  --cluster "system-audit:docs/archive/SYSTEM_AUDIT_2026-04-03.md,docs/SYSTEM_AUDIT_FINAL_2026-04-03.md:docs/SYSTEM_AUDIT_FINAL_2026-04-03.md"
)

OUTPUT_DIR="${DOCS_DERIVED_OUTPUT_DIR:-.artifacts/docs-derived-state}"
mkdir -p "$OUTPUT_DIR"

echo "docs_inventory_regen: generating live DOCSYNC JSON artifact..." >&2
# This read-only producer has no expected non-zero status.
python3 scripts/docs_sync.py --json >"$OUTPUT_DIR/docs-sync.json"
sync_rc=$?
if [[ "$sync_rc" -ne 0 ]]; then
  echo "docs_inventory_regen: docs_sync.py CRASHED (exit $sync_rc) — propagating failure (BLOCKER-3 fix)." >&2
  exit "$sync_rc"
fi

echo "docs_inventory_regen: generating DOCS_INVENTORY.md artifact..." >&2
# docs_audit.py uses 1 for expected content change and 2 for a crash.
if [[ -n "${DOCS_AUDIT_STATS_JSON:-}" ]]; then
  # --json instead of --quiet: stdout (JSON only) goes to the stats file,
  # stderr (including docs_audit's own "advanced N flip(s)..." line, P3-prime)
  # still flows to the caller's log normally.
  python3 scripts/docs_audit.py --regen-only --json "${TIME_MODE_ARGS[@]}" "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" \
    --output "$OUTPUT_DIR/DOCS_INVENTORY.md" \
    >"$DOCS_AUDIT_STATS_JSON"
else
  python3 scripts/docs_audit.py --regen-only --json "${TIME_MODE_ARGS[@]}" "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" \
    --output "$OUTPUT_DIR/DOCS_INVENTORY.md" \
    >"$OUTPUT_DIR/docs-audit.json"
fi
audit_rc=$?
if [[ "$audit_rc" -gt 1 ]]; then
  echo "docs_inventory_regen: docs_audit.py CRASHED (exit $audit_rc) — not a content-drift signal, propagating failure (BLOCKER-3 fix)." >&2
  exit "$audit_rc"
fi

echo "docs_inventory_regen: done." >&2
exit 0
