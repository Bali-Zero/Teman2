"""Pysa verdict determinism (5052/5053 flip): one row per rule of the partial-sink statement key, against test_pysa_check.py."""
PY, T = "scripts/localci/pysa_check.py", ("scripts/localci/tests/test_pysa_check.py",)
ANCHOR = '                anchor = (family, d["callable"], lf, stmt_start(app_dir, lf, ll))\n'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "pysa-det-no-statement-dedupe": (PY, 'if d["code"] not in FAMILIES:   #', 'if False:   #', T),
    "pysa-det-dedupe-by-line": (PY, ANCHOR, '                anchor = (family, d["callable"], lf, ll)\n', T),
    "pysa-det-code-dropped-from-anchor": (PY, ANCHOR, '                anchor = ("pysa", d["callable"], lf, stmt_start(app_dir, lf, ll))\n', T),
    "pysa-det-source-dropped-from-anchor": (PY, ANCHOR, '                anchor = (family, "", lf, stmt_start(app_dir, lf, ll))\n', T),
    "pysa-det-file-dropped-from-anchor": (PY, ANCHOR, '                anchor = (family, d["callable"], "", stmt_start(app_dir, lf, ll))\n', T),
    "pysa-det-statement-start-is-first-line-of-file": (PY, "    return best[0] if best else line\n", "    return 0\n", T),
    "pysa-det-listed-families-deduped-too": (PY, 'if d["code"] not in FAMILIES:   #', 'if True:   #', T),
}
