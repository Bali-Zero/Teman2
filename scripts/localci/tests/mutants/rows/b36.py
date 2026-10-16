"""B36: the loader of mutants/rows/*.py, against test_mutant_rows.py. The first rows file: it uses the table's own helpers."""
from merger_mutants import MERGER_T  # noqa: F401  (a rows file may import the table's helpers; this one proves the import works)

MR, MR_T = "scripts/localci/tests/mutants/merger_mutants.py", ("scripts/localci/tests/test_mutant_rows.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b36-duplicate-check-dropped": (MR, "            if n in owner:\n", "            if False:\n", MR_T),
    "b36-malformed-check-dropped": (MR, "            _check_row(f.name, n, row)\n", "            pass\n", MR_T),
    "b36-loader-not-called-at-import": (MR, "\n\nmerge_rows()   # B36: at import", "\n\npass   # B36: at import", MR_T),
    "b36-rows-dir-typo": (MR, 'parent / "rows"   # B36', 'parent / "row"   # B36', MR_T),
    "b36-second-merge-raises": (MR, "if n in owner and _MERGED.get(n) == (f.name, row) and into.get(n) == row:", "if False:", MR_T),
    "b36-underscore-file-loaded": (MR, '        if f.name.startswith("_"):\n            continue\n', "", MR_T),
}
