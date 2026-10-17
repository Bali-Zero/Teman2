"""CodeQL version sentinel after the flip: hosted findings are advisory only once hosted no longer gates, and only then."""
RD, RN = "scripts/localci/codeql_version_read.py", "scripts/localci/runner.py"
T = "scripts/localci/tests/test_codeql_contexts.py"
FLIP = (f"{T}::test_every_hosted_finding_is_advisory_once_the_flip_is_in_force_and_blocking_before_it",
        f"{T}::test_the_sentinel_stays_blocking_in_every_state_that_is_not_the_flip")
PARITY = (f"{T}::test_the_readers_flip_predicate_is_hosted_compares_over_the_same_documents",)
FAILED = (f"{T}::test_a_clean_read_stays_clean_and_a_failed_read_stays_cannot_verify_after_the_flip",)
PLAN = (f"{T}::test_a_hosted_cli_move_after_the_flip_plans_the_leg_with_a_note_and_never_blocks",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "cqlver-flip-probe-skipped": (RD, "    if rc in FINDINGS and flipped(run, args.repo):", "    if rc in FINDINGS:", FLIP),
    "cqlver-protection-404-unchecked": (RD, '    if not (isinstance(doc, str) and NOT_PROTECTED in doc and "(HTTP 404)" in doc):\n        return False\n',
                                        '    if False:\n        return False\n', FLIP),
    "cqlver-ruleset-shape-unchecked": (RD, 'return isinstance(info, dict) and is_flipped_ruleset(rs, branch, info.get("default_branch"))',
                                       "return isinstance(info, dict)", FLIP),
    "cqlver-truncated-page-trusted": (RD, "if not isinstance(batch, list) or len(batch) >= PAGE:", "if not isinstance(batch, list):", FLIP),
    "cqlver-two-rulesets-trusted": (RD, "    if len(named) != 1 or not isinstance(named[0].get(\"id\"), int):", "    if not named or not isinstance(named[0].get(\"id\"), int):", FLIP),
    "cqlver-read-failure-advisory": (RD, "FINDINGS = (3, 4, 5, 6)", "FINDINGS = (1, 3, 4, 5, 6)", FAILED),
    "cqlver-exclude-glob-ignored": (RD, " and not any(_GLOB.search(x) for x in exclude))", ")", PARITY),
    "cqlver-exclude-ignored": (RD, " and not names & set(exclude)", "", PARITY),
    "cqlver-runner-advisory-blocks": (RN, '    if got["rc"] == ADVISORY_RC and notes is not None:', "    if False:", PLAN),
    "cqlver-runner-advisory-silent": (RN, "        notes.append(f\"version sentinel ADVISORY", "        (lambda _: None)(f\"version sentinel ADVISORY", PLAN),
}
