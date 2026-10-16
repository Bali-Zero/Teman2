# B02: prepared Redis observer admission and one-shot execution package

## Current package status (2026-10-16)

Both one-shot native observer exercises completed on Pro and Mini. Each verified metadata, policy-off/policy-on behavior, 6 positive and 17 negative permissions, and temporary-role removal. The preparation document and run template remain immutable historical pre-execution evidence. Current focused source suite: 153 passed. Active actor coverage remains UNKNOWN; no repeat execution is authorized. block_closed:false; production adoption is not claimed. Original deadline elapsed. This package is prepared for review; no final committed-head PASS is asserted.

This candidate combines the existing keyless observer/census work with the exact prepared admission hardening and one-shot runner patch chain. The package enforces fixed native routes, UID-derived home paths, the seven-file preimport contract, temporary observer cleanup and fail-closed consent checks. It remains source-only and ungranted for native use.

## Current source verification

- Current worktree: 83 passed, 0 failed, 0 skipped.
- Clean copy containing only the seven prepared files: 83 passed, 0 failed, 0 skipped.
- The original 42 helper assertions and 15 runner assertions are preserved.
- All seven corrected manifest digests match; the three previously reviewed dependency pins remain exact.
- Tests use only the already prepared synthetic/private fixture cases. The operational runner was not launched.

Commands, source digests, timestamps and temporary-environment settings are in integration-20261016/CURRENT-SOURCE-TESTS-ALIGNED.json and CURRENT-CLEAN-CHECKOUT.json. PATCH-INTAKE.json records preimages and all three successful apply checks/applications. PREPARED-VERIFICATION-SUMMARY.json retains the frozen finding IDs B1_UID_HOME_AND_FIXED_ROUTES, B2_EXACT_SEVEN_FILE_PREIMPORT_STAGE_CONTRACT and B3_NATIVE_ROUTE_DOCUMENTATION.

The first harness attempt returned 82 passed and 1 failed: its explicit pytest basetemp was outside tempfile.gettempdir(), so the existing isolated-root guard correctly returned TEST_PATH_REJECTED. Aligning the child's TMPDIR resolved the harness mismatch without source edits. Original and focused diagnostic receipts are preserved. Historical observer/census observations remain separately labelled in RESULT.json; they were not rerun by this bounded task.

Bites: the shipping test_redis_observer_native_once.py and test_redis_observer_admission.py consume the prepared runtime files and packet template. Two current source-bound 83-pass suites prove the synthetic scenarios, as recorded under integration-20261016/.

## Remaining boundaries

status: BLOCKED; block_closed: false; native permission: UNGRANTED. Source PASS is neither a whole-head gate nor owner consent nor native closure. Dated authenticated Redis metadata, effective native permissions, native dry-run observations and canonical operation bindings remain missing.

The authenticated owner availability exception removes unavailable Claude as a blocker while preserving independent review and native-consent requirements. The coordinator owns official verification, the externally bound committed head, final gates and the original single PR. Existing R1 metadata and frozen findings are preserved. The three reviewed source files lack adversarial_review/R1 docstring markers; the parent must assess actual applicability or waiver, since adding markers here would change reviewed pins. No commit, baseline change, native invocation, production credential read, native ACL change or deployment was performed by this integration.
