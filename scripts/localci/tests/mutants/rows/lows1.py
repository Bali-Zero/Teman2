"""Gate LOWs, batch 1: the run-time guard of the rows loader (B36 L1/L2) and the exact host_checks membership (B30 L3), each with a mutant that removes it."""
MR, MR_T = "scripts/localci/tests/mutants/merger_mutants.py", ("scripts/localci/tests/test_mutant_rows_runtime_guard.py",)
PY, REDECIDE_T = "scripts/localci/merger.py", ("scripts/localci/tests/test_redecide_lows1.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "lows1-guard-not-called": (MR, "        _check_untouched(f.name, tables, snaps, bound)\n", "        pass\n", MR_T),
    "lows1-snapshot-is-live": (MR, "snaps = [dict(t) for t in tables]", "snaps = list(tables)", MR_T),
    "lows1-rebind-unchecked": (MR, 'if globals()["MUTANTS"] is not bound:', "if False:", MR_T),
    "lows1-removed-unseen": (MR, "removed = sorted(k for k in snap if k not in table)", "removed = []", MR_T),
    "lows1-changed-unseen": (MR, "changed = sorted(k for k in snap if k in table and table[k] is not snap[k])", "changed = []", MR_T),
    "lows1-added-unseen": (MR, "added = sorted(k for k in table if k not in snap)", "added = []", MR_T),
    "lows1-module-table-unwatched": (MR, "[into] if into is MUTANTS else [into, MUTANTS]", "[into]", MR_T),
    "lows1-setdefault-dropped": (MR, 'sys.modules.setdefault("merger_mutants", sys.modules[__name__])', "pass", MR_T),
    "lows1-host-checks-by-prefix": (PY, '(v == "ERROR" and host and k in named)', '(v == "ERROR" and host and any(k.startswith(n) for n in named if isinstance(n, str)))', REDECIDE_T),
}
