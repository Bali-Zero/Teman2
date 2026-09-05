#!/usr/bin/env python3
"""Prove the trusted-classifier corpus actually RUNS in the layout that judges it.

WHY THIS EXISTS. tests.yml's "Extract trusted classifier (base ref)" step copies a
hand-kept list of ``scripts/ci/*`` files FLAT into ``$RUNNER_TEMP/trusted-classifier/``
(no ``scripts/ci/`` directory above them) and then runs ``test_change_map.py`` /
``test_impact_map.py`` from THAT directory, with the job's cwd left at the checkout
root. scripts/tests/test_classifier_extraction_closure.py already proves the
extraction list is import-closed by static AST inspection — but that catches only
one failure shape (a missing sibling module). It was NOT what broke on 2026-09-04
(#5679): ``test_change_map.py``'s own ``test_scripts_coupling_census_is_not_stale``
called ``Path(__file__).resolve().parents[2]`` to relocate the repo root, which
resolves to a nonsense directory once the file has no ``scripts/ci/`` above it in a
flat temp dir — an import-closure check cannot see that, because the import graph
was fine; the corpus imported cleanly and then failed AT RUNTIME. #5692 fixed it by
trying ``Path.cwd()`` and ``$GITHUB_WORKSPACE`` first. This file is the regression
guard for that class of bug: it actually EXECUTES the corpus in the exact flat
layout, from the exact repo-root cwd CI uses, so a future ``Path(__file__)``/cwd
assumption that only breaks once extracted is caught locally, without a GitHub
Actions runner.

Guilt case: delete one file from the flat copy before running the corpus — the
missing-sibling ModuleNotFoundError this file's design would also have caught,
proving this is a real test and not one that can only ever pass.
Innocence case: the current, unmodified extraction list runs clean today.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TESTS_YML = REPO / ".github" / "workflows" / "tests.yml"
CI_DIR = REPO / "scripts" / "ci"

# Same anchor as scripts/tests/test_classifier_extraction_closure.py's EXTRACT_RE
# (single quantifier, linear — a `\S+`-only version was CodeQL-flagged HIGH for
# catastrophic backtracking): match the shell `for f in <paths>; do` loop, not
# YAML structure, so a renamed step still gets found.
EXTRACT_RE = re.compile(r"for f in ([^;\n]+);\s*do")
CI_PREFIX = "scripts/ci/"

# The two corpus files this probe actually executes in the flat layout. Both are
# always present in tests.yml's list today; asserted below rather than assumed.
CORPUS_FILES = ("test_change_map.py", "test_impact_map.py")


def _tests_yml_extraction_list() -> tuple[str, ...]:
    """Parse tests.yml's own `for f in scripts/ci/...` extraction loop.

    Deliberately scoped to tests.yml only (not every workflow, unlike the
    closure test's discovery pass) — this probe reproduces ONE specific job's
    layout, and a change to security.yml's separate list is that guard's own
    business, not this one's.
    """

    text = TESTS_YML.read_text(encoding="utf-8")
    matches = [m for m in EXTRACT_RE.finditer(text) if CI_PREFIX in m.group(1)]
    if not matches:
        raise AssertionError(
            "tests.yml no longer has a discoverable `for f in scripts/ci/...; do` "
            "extraction loop — either the shell shape changed or the trust "
            "boundary itself was removed. Fix this probe (or its regex) before "
            "trusting anything below."
        )
    if len(matches) > 1:
        raise AssertionError(
            f"tests.yml has {len(matches)} extraction loops matching scripts/ci/ — "
            "this probe assumes exactly one; disambiguate before trusting it."
        )
    tokens = matches[0].group(1).split()
    files = tuple(tok for tok in tokens if tok.startswith(CI_PREFIX))
    if tuple(tokens) != files:
        raise AssertionError(
            f"tests.yml's extraction list mixes scripts/ci/ paths with tokens this "
            f"probe cannot check: {[t for t in tokens if not t.startswith(CI_PREFIX)]}"
        )
    return files


def _extract_flat(files: tuple[str, ...], dest: Path, *, omit: str | None = None) -> None:
    """Reproduce the "Extract trusted classifier (base ref)" step's shape:
    every file copied FLAT (basename only) into one directory, executable bit
    kept for the one shell script in the list. ``omit`` drops one basename —
    the guilt fixture for "a sibling went missing from the flat copy"."""

    for rel in files:
        name = Path(rel).name
        if name == omit:
            continue
        src = REPO / rel
        if not src.is_file():
            raise AssertionError(f"tests.yml extracts {rel}, which does not exist on disk")
        dst = dest / name
        shutil.copyfile(src, dst)
        if name.endswith(".sh"):
            dst.chmod(dst.stat().st_mode | 0o111)


def _run(script: Path) -> subprocess.CompletedProcess[str]:
    # CI's step runs `python3 "$CLASSIFIER_DIR/test_change_map.py"` as a plain
    # `run:` step, whose default working directory is the checkout root — NOT
    # the extraction directory. Reproduced exactly: script path inside the temp
    # dir, cwd at the repo root.
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )


class TrustedExtractionLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _tests_yml_extraction_list()
        self.tmp = tempfile.TemporaryDirectory(prefix="trusted-extraction-layout-")
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name)

    def test_the_extraction_shape_is_discoverable(self) -> None:
        # Innocence for the probe itself (mirrors the closure test's own
        # self-check): if this ever finds nothing, every test below would pass
        # vacuously — assert the list is non-trivial and carries both corpus
        # files this probe depends on.
        self.assertGreaterEqual(len(self.files), 2)
        basenames = {Path(f).name for f in self.files}
        for corpus_file in CORPUS_FILES:
            self.assertIn(
                corpus_file,
                basenames,
                f"tests.yml's extraction list no longer carries {corpus_file} — "
                "update CORPUS_FILES or the list itself.",
            )

    def test_innocence_current_extraction_runs_both_corpora_clean(self) -> None:
        _extract_flat(self.files, self.dest)
        for corpus_file in CORPUS_FILES:
            with self.subTest(corpus_file=corpus_file):
                result = _run(self.dest / corpus_file)
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{corpus_file} failed when run from the flat trusted-extraction "
                    f"layout (cwd={REPO}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
                )

    def test_guilt_a_missing_sibling_breaks_the_flat_corpus(self) -> None:
        # security_gate_flags.py is imported by test_change_map.py
        # (`import security_gate_flags as sgf`) but is not itself one of
        # CORPUS_FILES — omitting it from the flat copy reproduces exactly the
        # #5070 shape (a corpus file whose sibling import silently vanished)
        # and must fail loudly, proving this probe can actually detect
        # breakage rather than only ever reporting green.
        omitted = "security_gate_flags.py"
        self.assertIn(
            omitted,
            {Path(f).name for f in self.files},
            f"{omitted} is no longer in tests.yml's extraction list — pick a "
            "different guilt fixture.",
        )
        _extract_flat(self.files, self.dest, omit=omitted)
        result = _run(self.dest / "test_change_map.py")
        self.assertNotEqual(
            result.returncode,
            0,
            "test_change_map.py passed even with security_gate_flags.py missing "
            "from the flat extraction — this probe would not have caught #5070.",
        )
        self.assertIn("security_gate_flags", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
