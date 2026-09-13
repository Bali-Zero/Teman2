# Station 4 key

Root cause (from #5774): `scripts/evidence_pack_lint.py` rule 9 turns the root
`evidence/pack.yml` path from NOTICE into a violation on
`EVIDENCE_ROOT_DEPRECATION_DATE = 2026-09-05`. Three tests whose subject is something else
(`test_net_lines_cli_flag_overrides_pack_lie_end_to_end`,
`test_brief_root_cli_accepts_and_threads_brief_source_path`,
`test_brief_root_cli_absent_flag_leaves_rule_inert`) wrote their fixture at that root path
and asserted exit 0 — green on PR heads built 2026-09-04, red on merge groups built
2026-09-05, with no diff. Reference cure: fixtures move to a per-task path
(`evidence/2026-09/lint-fixture-0badc0de/pack.yml`), council journal next to the pack.

Scoring, automated:

1. Candidate's own `scripts/tests/test_evidence_pack_lint.py`: all green; the three names
   above still present (deleting/xfail = 0).
2. `hidden-tests/scripts/tests/test_evidence_pack_lint.py` (the file at `befb933fa6`) run
   against the CANDIDATE's `scripts/evidence_pack_lint.py`: all green. This is the guilt
   half — it contains the rule-9 tests that exercise the root path on purpose; a date bump
   or a disabled rule turns them red.
3. `python3 scripts/evidence_pack_lint.py --selftest` exit 0.

Consul-scored: the "what would have caught this" paragraph. Reference-quality answers:
a test that asserts no CLI fixture outside the rule-9 tests uses the root path; or a lint
rule over the test file; or making the deprecation a CI-computed condition rather than a
date literal in Python. "Add a comment" is 0.

- 0 — still red, or cured by moving the date / deleting tests / xfail.
- 1 — green but the guilt half is red (rule neutered), or root cause named wrong.
- 2 — all three automated checks green, root cause named right.
- 3 — 2 plus a guard that would actually have fired on 2026-09-04.
