#!/bin/bash
# docs_inventory_regen.sh — SSOT regen for the docs-inventory + DOCSYNC derived artifacts.
#
# Single source of truth for the exact docs_audit.py invocation (whitelist + cluster
# args) so automation that needs a fresh docs/DOCS_INVENTORY.md never carries a second
# copy of that arg list that silently drifts from the original (cicatrix superscar #1 —
# HOME-fork / duplicate-copy family). Introduced 2026-07-17 as the structural cure for
# "docs-guardian inventory-check marcisce col calendario": docs_audit.py's classify()
# flips a doc LIVE->ARCHIVED purely on wall-clock (mtime>90d, Rule 2), independent of any
# PR's content — so the table committed on main silently rots until an unrelated PR's
# `inventory-check` gate hits the accumulated calendar delta and fails innocently (2x on
# #2509 2026-07-16, again on #2592 2026-07-17). See memory
# discovery_docs_guardian_wallclock_gate_rot_2026_07_16.md for the full incident history.
#
# LOCKSTEP NOTICE (read before editing --whitelist/--cluster args):
#   .github/workflows/docs-guardian.yml's `inventory-check` job (the required PR gate)
#   still INLINES its own copy of this same args list (for --check, read-only) rather
#   than calling this script. That required/hot-zone workflow file was deliberately left
#   untouched here — editing it for a non-functional refactor was judged higher risk
#   (CODEOWNERS-TIER1 + pre-commit lease-check + meta-verifier surface) than the benefit
#   of a single extra indirection, per the design tradeoff documented in the PR that added
#   this script. If you add/remove/rename a --whitelist or --cluster entry, you MUST
#   update BOTH this file AND docs-guardian.yml's inline args, or the two will diverge
#   and one of them will start reporting false drift.
#   scripts/docs_guardian.sh (the existing weekly Pro cron, docs/operations/docs-guardian-cron.md)
#   ALSO inlines a third copy today (pre-dates this script) — not touched here, out of
#   scope for this change; a future cleanup could point it at this script too.
#
# What this does:
#   1. Re-syncs DOCSYNC markers (scripts/docs_sync.py, write mode).
#   2. Regenerates docs/DOCS_INVENTORY.md in TABLE-ONLY mode (docs_audit.py --regen-only):
#      refreshes the calendar-driven LIVE/STALE/ARCHIVED classification WITHOUT physically
#      git-mv'ing orphans into docs/archive/. Physical archival remains
#      scripts/docs_guardian.sh's weekly L1 job — this script only cures the TABLE drift.
#
# P3-prime (2026-07-17, research/operations/2026-07-17-push-pipeline-optimization-spec.md
# §P3): docs_audit.py --regen-only now runs in a "write mode" that deterministically
# stamps `orphan_flipped_on` on any doc that just crossed its `orphan_eligible_on` date
# (real "today", since no --as-of is passed here — this is the ONE legitimate place in
# the whole pipeline allowed to consult wall-clock for that decision; --check, the PR
# gate, never does). If $DOCS_AUDIT_STATS_JSON is set, the --json stats payload
# (includes `flips_this_run`/`flipped_paths`) is captured there for the calling workflow
# to surface in its PR body/log — see .github/workflows/docs-inventory-refresh.yml. Unset
# by default so this script's plain-usage contract (scripts/docs_guardian.sh does NOT use
# this script today, but a future caller that doesn't care about the flip count pays zero
# extra cost) is unchanged.
#
# Exit code (revised BLOCKER-3, red-team 2026-07-18): 0 on a completed run, REGARDLESS
# of whether content changed — docs_sync.py (write mode) and docs_audit.py --regen-only
# both return RC=1 BY DESIGN when they rewrite content ("drift detected" is not a
# failure) and this script swallows exactly that expected 1. Callers must check
# `git diff --quiet` on the working tree afterward to detect real drift; this script
# does not make that decision. A GENUINE crash in either tool (docs_sync.py returning
# non-zero at all — it never legitimately does in this write-mode call — or
# docs_audit.py returning >1, its own dedicated crash code) now PROPAGATES as this
# script's own non-zero exit instead of being silently absorbed: the old blanket
# `|| true` could not distinguish "1 = expected drift" from "1 or more = actually
# crashed", so a real crash used to look identical to "ran fine, nothing changed" —
# invisible to any caller checking only this script's exit code, and invisible to the
# P3-prime liveness guardian, which only sees whether the calling GH Actions STEP
# succeeded, not what happened inside it.
#
# Usage: scripts/docs_inventory_regen.sh   (no args; run from anywhere, cd's to repo root)
#        DOCS_AUDIT_STATS_JSON=/path/to/out.json scripts/docs_inventory_regen.sh
#          (also writes the --json stats payload to that path)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Kept identical to .github/workflows/docs-guardian.yml's inventory-check step args —
# see LOCKSTEP NOTICE above.
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

echo "docs_inventory_regen: syncing DOCSYNC markers..." >&2
# BLOCKER-3 fix (red-team 2026-07-18): the old `|| true` swallowed ANY
# non-zero exit here, but this write-mode call (no --check/--diff) legitimately
# ALWAYS returns 0 on a clean run (see docs_sync.py main()'s final `return 0`
# fallthrough — `return 1` only exists under --check, never reached here). So
# a non-zero exit can ONLY mean docs_sync.py CRASHED — that must fail this
# wrapper loud (a swallowed crash here means DOCSYNC markers silently did not
# refresh, on an apparently-green run), not be silently absorbed. No `-e` is
# set (see `set -uo pipefail` above), so this is an explicit $? check, not a
# no-op comment: removing `|| true` alone would NOT propagate the failure.
python3 scripts/docs_sync.py --quiet
sync_rc=$?
if [[ "$sync_rc" -ne 0 ]]; then
  echo "docs_inventory_regen: docs_sync.py CRASHED (exit $sync_rc) — propagating failure (BLOCKER-3 fix)." >&2
  exit "$sync_rc"
fi

echo "docs_inventory_regen: regenerating docs/DOCS_INVENTORY.md (table-only, --regen-only)..." >&2
# BLOCKER-3 fix: docs_audit.py's exit code is OVERLOADED even in write mode —
# 0 = no drift, 1 = drift detected (intentional, NOT a failure: this
# wrapper's whole job is to regen content, so "content changed" is the
# expected/successful outcome), 2 = CRASHED (docs_audit.py's own __main__
# crash boundary, P3-prime fix). The old `|| true` swallowed 1 and 2
# identically — a crash silently became "nothing to see here" on a green
# workflow run. Only the EXPECTED 1 is swallowed below; anything higher
# propagates as a real failure.
if [[ -n "${DOCS_AUDIT_STATS_JSON:-}" ]]; then
  # --json instead of --quiet: stdout (JSON only) goes to the stats file,
  # stderr (including docs_audit's own "advanced N flip(s)..." line, P3-prime)
  # still flows to the caller's log normally.
  python3 scripts/docs_audit.py --regen-only --json "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}" \
    >"$DOCS_AUDIT_STATS_JSON"
else
  python3 scripts/docs_audit.py --regen-only --quiet "${WHITELIST_ARGS[@]}" "${CLUSTER_ARGS[@]}"
fi
audit_rc=$?
if [[ "$audit_rc" -gt 1 ]]; then
  echo "docs_inventory_regen: docs_audit.py CRASHED (exit $audit_rc) — not a content-drift signal, propagating failure (BLOCKER-3 fix)." >&2
  exit "$audit_rc"
fi

echo "docs_inventory_regen: done." >&2
exit 0
