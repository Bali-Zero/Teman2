"""Tests for the anti-reward-hacking AST linter — P1 STRATO-1 (FASE-3).

Spec P1 §7 #4 mandates "+ test delle regole stesse": each rule must FIRE on a
known-bad sample and STAY SILENT on a clean one. Without these, a refactor could
silently neuter a rule (cicatrix W64 — a guard with no test rots) and the linter
would pass everything while detecting nothing.

Run:
    cd ~/Desktop/nuzantara && python3 -m pytest scripts/test_lint_test_reward_hacking.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts.lint_test_reward_hacking import lint_source  # noqa: E402


def _codes(src: str) -> set[str]:
    return {f.code for f in lint_source(Path("test_sample.py"), src)}


# ─── each rule FIRES on its known-bad sample ─────────────────────────


def test_rh001_assert_true_fires():
    assert "RH001" in _codes("def test_x():\n    assert True\n")


def test_rh001_assert_nonzero_const_fires():
    assert "RH001" in _codes("def test_x():\n    assert 1\n")


def test_rh002_self_equal_fires():
    assert "RH002" in _codes("def test_x():\n    assert 1 == 1\n")


def test_rh002_self_equal_string_fires():
    assert "RH002" in _codes("def test_x():\n    assert 'a' == 'a'\n")


def test_rh003_broad_raises_fires():
    src = (
        "import pytest\n"
        "def test_x():\n"
        "    with pytest.raises(Exception):\n"
        "        boom()\n"
    )
    assert "RH003" in _codes(src)


def test_rh004_early_exit_fires():
    src = "import sys\ndef test_x():\n    sys.exit(0)\n    assert real()\n"
    assert "RH004" in _codes(src)


def test_rh005_no_assertion_fires():
    src = "def test_x():\n    y = compute()\n    print(y)\n"
    assert "RH005" in _codes(src)


# ─── each rule STAYS SILENT on the legitimate counterpart ────────────


def test_rh001_real_assert_silent():
    assert "RH001" not in _codes("def test_x():\n    assert compute() == 4\n")


def test_rh002_real_compare_silent():
    assert "RH002" not in _codes("def test_x():\n    assert got == expected\n")


def test_rh003_specific_raises_silent():
    src = (
        "import pytest\n"
        "def test_x():\n"
        "    with pytest.raises(ValueError):\n"
        "        boom()\n"
    )
    assert "RH003" not in _codes(src)


def test_rh003_broad_with_match_silent():
    """pytest.raises(Exception, match=...) is acceptable — match narrows it."""
    src = (
        "import pytest\n"
        "def test_x():\n"
        "    with pytest.raises(Exception, match='bad'):\n"
        "        boom()\n"
    )
    assert "RH003" not in _codes(src)


def test_rh004_no_exit_silent():
    assert "RH004" not in _codes("def test_x():\n    assert real()\n")


def test_rh005_self_assert_counts():
    """unittest-style self.assertEqual counts as an assertion → no RH005."""
    src = "def test_x(self):\n    self.assertEqual(go(), 3)\n"
    assert "RH005" not in _codes(src)


def test_rh005_pytest_raises_counts():
    """A test whose only check is a pytest.raises block still asserts something."""
    src = (
        "import pytest\n"
        "def test_x():\n"
        "    with pytest.raises(ValueError):\n"
        "        boom()\n"
    )
    assert "RH005" not in _codes(src)


# ─── a fully clean test file produces zero findings ──────────────────


def test_clean_file_zero_findings():
    src = (
        "import pytest\n"
        "def test_add():\n"
        "    assert add(2, 2) == 4\n"
        "def test_raises_specific():\n"
        "    with pytest.raises(ValueError, match='neg'):\n"
        "        sqrt(-1)\n"
    )
    assert _codes(src) == set()


# ─── non-test functions are NOT subjected to RH004/RH005 ─────────────


def test_helper_function_not_flagged_for_no_assert():
    """A non-test_ helper that asserts nothing must NOT trigger RH005."""
    src = "def helper_compute():\n    return 42\n"
    assert "RH005" not in _codes(src)
