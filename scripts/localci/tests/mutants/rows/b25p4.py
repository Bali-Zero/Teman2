"""B25-prime P4: Pro gate-verdict ledger reader (`harness_gate_read.py --ledger PATH --head SHA`), matrix argv, runner `$GATE_LEDGER` / `$HEAD`, and container isolation."""
HGR = "scripts/ci/harness_gate_read.py"
MATRIX = "scripts/localci/contexts_matrix.yaml"
RUNNER = "scripts/localci/runner.py"
MERGER = "scripts/localci/merger.py"

HGR_T = ("scripts/tests/test_harness_gate_read.py",)
GP_T = ("scripts/localci/tests/test_gate_pending.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b25p4-empty-ledger-not-pending": (
        HGR,
        'if why in ("ledger missing", "no entry for this head"):',
        "if False:",
        HGR_T,
    ),
    "b25p4-live-head-mismatch-ignored": (
        HGR,
        "if sha != args.head:",
        "if False:",
        HGR_T,
    ),
    "b25p4-head-without-ledger-allowed": (
        HGR,
        "if args.head is not None and args.ledger is None:",
        "if False:",
        HGR_T,
    ),
    "b25p4-ledger-without-valid-head-allowed": (
        HGR,
        'if not args.head or not re.fullmatch(r"[0-9a-f]{40}", args.head):',
        "if False:",
        HGR_T,
    ),
    "b25p4-ledger-falls-back-to-github": (
        HGR,
        "if args.ledger is not None:\n        if sha != args.head:",
        "if False:\n        if sha != args.head:",
        HGR_T,
    ),
    "b25p4-matrix-trusted-helper-dropped": (
        MATRIX,
        "[scripts/ci/harness_gate_read.py, scripts/localci/gate_ledger.py]",
        "[scripts/ci/harness_gate_read.py]",
        GP_T,
    ),
    "b25p4-matrix-ledger-argv-dropped": (
        MATRIX,
        "            - --ledger\n            - $GATE_LEDGER\n            - --head\n            - $HEAD\n",
        "",
        GP_T,
    ),
    "b25p4-runner-side-leaks-into-steps-json": (
        RUNNER,
        'st.pop("side", None)   # B25-prime P4:',
        "pass   # B25-prime P4:",
        GP_T,
    ),
    "b25p4-runner-empty-ledger-unblocked": (
        RUNNER,
        'if "$GATE_LEDGER" in argv and not ledger_arg:',
        "if False:",
        GP_T,
    ),
    "b25p4-runner-missing-secondary-trusted-file-ignored": (
        RUNNER,
        "if any(b is None for b in blobs.values()):",
        "if blobs.get(argv[1]) is None:",
        GP_T,
    ),
    "b25p4-merger-gate-ledger-dropped": (
        MERGER,
        'if runner_takes(base_wt, "--gate-ledger"):   # B25-prime P4:',
        "if False:   # B25-prime P4:",
        GP_T,
    ),
    "b25p4-merger-head-dropped": (
        MERGER,
        'if head_sha and runner_takes(base_wt, "--head"):   # B25-prime P4:',
        "if False:   # B25-prime P4:",
        GP_T,
    ),
}
