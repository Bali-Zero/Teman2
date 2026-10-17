"""B25-prime P4 follow-up (gate-b25p4 LOW-1/2/3): an unreadable ledger is no verdict, every trusted reader file is BASE's, and the heads compared are whole."""
HGR_PY, HGR_T = "scripts/ci/harness_gate_read.py", "scripts/tests/test_harness_gate_read.py"
RUNNER, SC_T = "scripts/localci/runner.py", "scripts/localci/tests/test_service_contexts.py"
MERGER, MG_T = "scripts/localci/merger.py", "scripts/localci/tests/test_merger.py"
UNREADABLE = (f"{HGR_T}::test_b25p4fu_a_ledger_that_exists_but_cannot_be_read_is_cannot_verify_never_success_never_a_verdict",)
HEAD_WHOLE = (f"{HGR_T}::test_b25p4fu_a_live_head_that_shares_a_prefix_with_the_decided_head_does_not_match",)
SIBLING = (f"{SC_T}::test_every_trusted_file_of_a_host_reader_is_the_base_copy_never_the_candidates",)
DECIDED = (f"{MG_T}::test_the_tick_hands_run_gate_the_decided_head_not_the_candidate_nor_the_base",)
CNV = "CANNOT-VERIFY (the ledger itself is unreadable, not the same as 'no verdict') — {err}\", file=sys.stderr)\n            return 1"

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "p4fu-unreadable-ledger-plain-error": (HGR_PY, CNV, "{err}\", file=sys.stderr)\n            return 1", UNREADABLE),
    "p4fu-unreadable-ledger-reads-success": (HGR_PY, CNV, CNV.replace("return 1", "return 0"), UNREADABLE),
    "p4fu-unreadable-ledger-reads-pending": (HGR_PY, CNV, CNV.replace("CANNOT-VERIFY (the ledger itself is unreadable, not the same as 'no verdict')", "PENDING"), UNREADABLE),
    "p4fu-head-compared-on-a-twelve-char-prefix": (HGR_PY, "if sha != args.head:", "if sha[:12] != args.head[:12]:", HEAD_WHOLE),
    "p4fu-head-compared-without-its-last-char": (HGR_PY, "if sha != args.head:", "if sha[:39] != args.head[:39]:", HEAD_WHOLE),
    "p4fu-head-compared-without-its-first-char": (HGR_PY, "if sha != args.head:", "if sha[1:] != args.head[1:]:", HEAD_WHOLE),
    "p4fu-head-startswith": (HGR_PY, "if sha != args.head:", "if not sha.startswith(args.head[:20]):", HEAD_WHOLE),
    "p4fu-every-trusted-file-from-the-candidate": (RUNNER, "blobs = {tf: _extract_base_file(wt, base, tf) for tf in tfiles}",
                                                    "blobs = {tf: _extract_base_file(wt, cand, tf) for tf in tfiles}", SIBLING),
    "p4fu-secondary-trusted-file-from-the-candidate": (RUNNER, "blobs = {tf: _extract_base_file(wt, base, tf) for tf in tfiles}",
                                                       "blobs = {tf: _extract_base_file(wt, base if tf == argv[1] else cand, tf) for tf in tfiles}", SIBLING),
    "p4fu-decide-hands-the-gate-the-candidate-as-head": (MERGER, "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n, head)",
                                                         "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n, cand_sha)", DECIDED),
    "p4fu-decide-hands-the-gate-the-base-as-head": (MERGER, "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n, head)",
                                                    "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n, base_sha)", DECIDED),
    "p4fu-decide-hands-the-gate-no-head": (MERGER, "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n, head)",
                                           "gate = run_gate(a, base_wt, cand, run_dir, base_sha, cand_sha, n)", DECIDED),
}
