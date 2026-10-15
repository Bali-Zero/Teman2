"""B36: the loader of mutants/rows/*.py, against test_mutant_rows.py. The first rows file: it uses the table's own helpers."""
from merger_mutants import MERGER_T  # noqa: F401  (a rows file may import the table's helpers; this one proves the import works)

MR, MR_T = "scripts/localci/tests/mutants/merger_mutants.py", ("scripts/localci/tests/test_mutant_rows.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b36-duplicate-check-dropped": (MR, "            if n in owner:\n", "            if False:\n", MR_T),
    "b36-malformed-check-dropped": (MR, "            _check_row(f.name, n, row)\n", "            pass\n", MR_T),
    "b36-loader-not-called": (MR, "    merge_rows()\n    names = a.only", "    names = a.only", MR_T),
}
