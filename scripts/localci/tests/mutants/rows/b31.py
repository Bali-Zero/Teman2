"""B31'': the mutants of the label helper. Hand-written ones pin `docs_guardian.sh` (bash, no extractor); the rest are GENERATED from the Python
conditionals of label_intent.py and label_census.py (scripts/localci/predicate_census.py), one negation mutant per conditional."""
import importlib.util
import sys

from merger_mutants import ROOT

_spec = importlib.util.spec_from_file_location("b31_predicate_census", ROOT / "scripts/localci/predicate_census.py")
_pc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _pc
_spec.loader.exec_module(_pc)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b31-dg-gate-broken-dropped": ('scripts/docs_guardian.sh', 'if [[ "$BROKEN" == "0" && -n "$PR_URL" &&', 'if [[ -n "$PR_URL" &&', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-gate-broken-inverted": ('scripts/docs_guardian.sh', 'if [[ "$BROKEN" == "0" && -n "$PR_URL" &&', 'if [[ "$BROKEN" != "0" && -n "$PR_URL" &&', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-gate-url-pattern-dropped": ('scripts/docs_guardian.sh', '-n "$PR_URL" && "$PR_URL" =~ ^https://github.com/.+/pull/[0-9]+$ ]]', '-n "$PR_URL" ]]', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-gate-url-pattern-loose": ('scripts/docs_guardian.sh', '^https://github.com/.+/pull/[0-9]+$ ]]', '^https://.+/pull/[0-9]+$ ]]', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-helper-present-inverted": ('scripts/docs_guardian.sh', 'if [ -x scripts/signal_merge_intent.sh ]; then', 'if [ ! -x scripts/signal_merge_intent.sh ]; then', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-helper-present-never": ('scripts/docs_guardian.sh', 'if [ -x scripts/signal_merge_intent.sh ]; then', 'if false; then', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-fallback-arm-dropped": ('scripts/docs_guardian.sh', 'gh pr merge "$PR_NUM" --auto >/dev/null 2>&1 || true', 'true || true', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-fallback-arm-fatal": ('scripts/docs_guardian.sh', 'gh pr merge "$PR_NUM" --auto >/dev/null 2>&1 || true', 'gh pr merge "$PR_NUM" --auto >/dev/null 2>&1', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-fallback-true-dropped": ('scripts/docs_guardian.sh', 'gh pr merge "$PR_NUM" --auto >/dev/null 2>&1 || true', 'gh pr merge "$PR_NUM" --auto >/dev/null 2>&1 || false', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-status-discarded": ('scripts/docs_guardian.sh', '    if ! INTENT_OUT=$(scripts/signal_merge_intent.sh "$PR_NUM" 2>&1); then', '    INTENT_OUT=$(scripts/signal_merge_intent.sh "$PR_NUM" 2>&1)\n    if false; then', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-status-inverted": ('scripts/docs_guardian.sh', '    if ! INTENT_OUT=$(scripts/signal_merge_intent.sh "$PR_NUM" 2>&1); then', '    if INTENT_OUT=$(scripts/signal_merge_intent.sh "$PR_NUM" 2>&1); then', ("scripts/localci/tests/test_label_census.py",)),
    "b31-docs-guardian-swallows-helper": ('scripts/docs_guardian.sh', 'if ! INTENT_OUT=$(scripts/signal_merge_intent.sh "$PR_NUM" 2>&1); then', 'scripts/signal_merge_intent.sh "$PR_NUM" || true\n    if false; then', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-intent-flag-unset": ('scripts/docs_guardian.sh', '      INTENT_FAILED=1\n', '      :\n', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-notify-dropped": ('scripts/docs_guardian.sh', '[[ "${INTENT_FAILED:-0}" == "1" ]] && SUMMARY+=', '[[ "${INTENT_FAILED:-0}" == "X" ]] && SUMMARY+=', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-notify-always": ('scripts/docs_guardian.sh', '[[ "${INTENT_FAILED:-0}" == "1" ]] && SUMMARY+=', '[[ "${INTENT_FAILED:-0}" != "X" ]] && SUMMARY+=', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-notify-default-failed": ('scripts/docs_guardian.sh', '[[ "${INTENT_FAILED:-0}" == "1" ]] && SUMMARY+=', '[[ "${INTENT_FAILED:-1}" == "1" ]] && SUMMARY+=', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-notify-text-dropped": ('scripts/docs_guardian.sh', 'SUMMARY+=("MERGE INTENT FAILED on PR #${PR_NUM:-?} (label/arm) — it will not merge by itself")', 'SUMMARY+=()', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-exit-dropped": ('scripts/docs_guardian.sh', 'if [[ "${INTENT_FAILED:-0}" == "1" ]]; then exit 1; fi', 'true', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-exit-always": ('scripts/docs_guardian.sh', 'if [[ "${INTENT_FAILED:-0}" == "1" ]]; then exit 1; fi', 'if [[ "${INTENT_FAILED:-0}" != "X" ]]; then exit 1; fi', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-exit-default-failed": ('scripts/docs_guardian.sh', 'if [[ "${INTENT_FAILED:-0}" == "1" ]]; then exit 1; fi', 'if [[ "${INTENT_FAILED:-1}" == "1" ]]; then exit 1; fi', ("scripts/localci/tests/test_label_census.py",)),
    "b31-dg-gate-url-empty-allowed": ('scripts/docs_guardian.sh', '-n "$PR_URL" && "$PR_URL" =~', '-z "$PR_URL" && "$PR_URL" =~', ("scripts/localci/tests/test_label_census.py",)),
}
ROWS.update(_pc.auto_mutants(ROOT))
