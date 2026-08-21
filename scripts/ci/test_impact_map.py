#!/usr/bin/env python3
"""Guilt + innocence corpus for the static test-impact map (impact_map.py).

Hermetic by design: builds a small synthetic ``apps/backend-rag/backend``
tree under a temp directory per test, instead of asserting exact counts
against the live 3000+-module repo tree (which would drift every time
someone adds a file). A separate manual measurement against real recent PRs
(selection ratio) lives in the PR body / research capture, not here.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import impact_map as im


def _write(root: Path, rel: str, content: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixture(root: Path) -> None:
    b = "apps/backend-rag/backend"
    _write(root, f"{b}/__init__.py")
    _write(root, f"{b}/core/__init__.py")
    _write(root, f"{b}/core/config.py", "SETTING = 1\n")
    _write(root, f"{b}/services/__init__.py")
    _write(root, f"{b}/services/leaf.py", "from backend.core import config\n\nX = config.SETTING\n")
    _write(root, f"{b}/services/other.py", "from backend.core import config\n\nY = config.SETTING\n")
    _write(root, f"{b}/services/third.py", "from backend.core import config\n\nZ = config.SETTING\n")
    _write(root, f"{b}/services/unrelated.py", "W = 1\n")
    _write(root, f"{b}/tests/__init__.py")
    _write(root, f"{b}/tests/conftest.py", "import pytest\n")
    _write(root, f"{b}/tests/services/__init__.py")
    _write(root, f"{b}/tests/services/test_leaf.py", "from backend.services import leaf\n")
    _write(root, f"{b}/tests/services/test_other.py", "from backend.services import other\n")
    _write(root, f"{b}/tests/services/test_third.py", "from backend.services import third\n")
    _write(
        root,
        f"{b}/tests/services/test_unrelated.py",
        "from backend.services import unrelated\n",
    )
    _write(root, f"{b}/tests/services/sub/__init__.py")
    _write(root, f"{b}/tests/services/sub/conftest.py", "import pytest\n")
    _write(
        root,
        f"{b}/tests/services/sub/test_nested.py",
        "from backend.services import unrelated  # deliberately unrelated to leaf/other/third\n",
    )


class ImpactMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _build_fixture(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_guilt_leaf_module_selects_only_its_direct_test(self) -> None:
        result = im.compute(["apps/backend-rag/backend/services/leaf.py"], self.root)
        self.assertFalse(result["run_all"])
        self.assertEqual(result["reason"], "scoped")
        self.assertEqual(
            result["selected_tests"],
            ["apps/backend-rag/backend/tests/services/test_leaf.py"],
        )

    def test_e2e_dependent_is_excluded_mirroring_backend_tests_own_ignore_flag(
        self,
    ) -> None:
        # backend-tests' pytest invocation passes --ignore=backend/tests/e2e;
        # a direct importer living under that subtree must never appear in a
        # scoped selection, or a diff whose ONLY dependent is an e2e test
        # would hand pytest a target its own --ignore then filters back out.
        _write(
            self.root,
            "apps/backend-rag/backend/tests/e2e/test_leaf_e2e.py",
            "from backend.services import leaf\n",
        )
        result = im.compute(["apps/backend-rag/backend/services/leaf.py"], self.root)
        self.assertFalse(result["run_all"])
        self.assertEqual(
            result["selected_tests"],
            ["apps/backend-rag/backend/tests/services/test_leaf.py"],
        )

    def test_innocence_widely_imported_core_module_selects_broadly(self) -> None:
        leaf_result = im.compute(["apps/backend-rag/backend/services/leaf.py"], self.root)
        core_result = im.compute(["apps/backend-rag/backend/core/config.py"], self.root)
        self.assertFalse(core_result["run_all"])
        selected = set(core_result["selected_tests"])
        # config.py is imported (transitively, via leaf/other/third) by three
        # test modules; the fourth (test_unrelated / test_nested) never
        # touches it and must stay excluded — broad is not "everything".
        self.assertIn("apps/backend-rag/backend/tests/services/test_leaf.py", selected)
        self.assertIn("apps/backend-rag/backend/tests/services/test_other.py", selected)
        self.assertIn("apps/backend-rag/backend/tests/services/test_third.py", selected)
        self.assertNotIn(
            "apps/backend-rag/backend/tests/services/test_unrelated.py", selected
        )
        self.assertGreater(
            core_result["selected_test_count"], leaf_result["selected_test_count"]
        )

    def test_nested_conftest_selects_only_its_own_subtree(self) -> None:
        result = im.compute(
            ["apps/backend-rag/backend/tests/services/sub/conftest.py"], self.root
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(
            result["selected_tests"],
            ["apps/backend-rag/backend/tests/services/sub/test_nested.py"],
        )

    def test_root_conftest_selects_every_test_file(self) -> None:
        result = im.compute(["apps/backend-rag/backend/tests/conftest.py"], self.root)
        self.assertFalse(result["run_all"])
        self.assertEqual(result["selected_test_count"], result["total_test_count"])
        self.assertEqual(result["total_test_count"], 5)

    def test_editing_a_test_file_directly_selects_itself(self) -> None:
        result = im.compute(
            ["apps/backend-rag/backend/tests/services/test_unrelated.py"], self.root
        )
        self.assertFalse(result["run_all"])
        self.assertEqual(
            result["selected_tests"],
            ["apps/backend-rag/backend/tests/services/test_unrelated.py"],
        )

    def test_innocence_out_of_scope_path_falls_open(self) -> None:
        for path in (
            "apps/crm-cell/crm_cell/x.py",
            "scripts/bot/build_deid_corpus.py",
            "apps/backend-rag/backend/data/prices.json",
        ):
            with self.subTest(path=path):
                result = im.compute([path], self.root)
                self.assertTrue(result["run_all"])
                self.assertEqual(result["reason"], "out_of_scope_path")

    def test_empty_changed_set_falls_open(self) -> None:
        result = im.compute([], self.root)
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "empty_changed_set")

    def test_enumeration_error_falls_open(self) -> None:
        result = im.compute([im.ENUMERATION_ERROR], self.root)
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "enumeration_failed")

    def test_deleted_file_falls_open(self) -> None:
        result = im.compute(
            ["apps/backend-rag/backend/services/does_not_exist.py"], self.root
        )
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "unresolvable_changed_path")

    def test_module_with_zero_test_dependents_falls_open(self) -> None:
        _write(self.root, "apps/backend-rag/backend/services/orphan.py", "V = 1\n")
        result = im.compute(["apps/backend-rag/backend/services/orphan.py"], self.root)
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "empty_impact_set")

    def test_unparseable_module_anywhere_in_tree_falls_open(self) -> None:
        # A syntax error in a file the diff never touched still forces
        # run_all=True — the whole-tree graph is the unit of trust, per the
        # module docstring's "ROOT OF TRUST" / uncertainty-fails-open
        # contract, not just the changed file's own parse.
        _write(self.root, "apps/backend-rag/backend/services/broken.py", "def (:\n")
        result = im.compute(["apps/backend-rag/backend/services/leaf.py"], self.root)
        self.assertTrue(result["run_all"])
        self.assertEqual(result["reason"], "unparseable_module")

    def test_relative_import_resolves_to_the_right_module(self) -> None:
        b = "apps/backend-rag/backend"
        _write(self.root, f"{b}/services/pkg/__init__.py")
        _write(self.root, f"{b}/services/pkg/leaf_rel.py", "X = 1\n")
        _write(
            self.root,
            f"{b}/services/pkg/user.py",
            "from . import leaf_rel\n\nY = leaf_rel.X\n",
        )
        _write(self.root, f"{b}/tests/services/test_pkg_user.py", "from backend.services.pkg import user\n")
        result = im.compute(
            ["apps/backend-rag/backend/services/pkg/leaf_rel.py"], self.root
        )
        self.assertFalse(result["run_all"])
        self.assertIn(
            "apps/backend-rag/backend/tests/services/test_pkg_user.py",
            result["selected_tests"],
        )

    def test_cli_stdout_is_one_compact_json_line(self) -> None:
        script = Path(__file__).with_name("impact_map.py")
        completed = subprocess.run(
            [sys.executable, str(script), "--repo-root", str(self.root)],
            input="apps/backend-rag/backend/services/leaf.py\n",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(len(completed.stdout.splitlines()), 1)
        parsed = json.loads(completed.stdout)
        self.assertFalse(parsed["run_all"])
        self.assertEqual(parsed["reason"], "scoped")


if __name__ == "__main__":
    unittest.main(verbosity=2)
