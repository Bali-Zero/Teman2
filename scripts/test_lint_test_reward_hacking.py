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


def test_rh005_silent_on_a_fixture_named_test_something():
    """INNOCENCE: a @pytest.fixture named `test_client` is not a test.

    It has no business asserting anything — RH005 firing on it is an over-match
    of the `test_` prefix rule (cicatrix family #3), and it blocked a real commit.
    """
    src = (
        "import pytest\n"
        "@pytest.fixture\n"
        "def test_client():\n"
        "    app = build()\n"
        "    return TestClient(app)\n"
    )
    assert "RH005" not in _codes(src)


def test_rh005_silent_on_parametrized_fixture_and_bare_fixture_import():
    """INNOCENCE: the decorator forms that appear in this repo all count."""
    parametrized = (
        "import pytest\n"
        "@pytest.fixture(scope='module')\n"
        "def test_pool():\n"
        "    return Pool()\n"
    )
    bare_import = (
        "from pytest import fixture\n@fixture\ndef test_db():\n    return Db()\n"
    )
    assert "RH005" not in _codes(parametrized)
    assert "RH005" not in _codes(bare_import)


def test_rh005_still_fires_on_a_real_assertionless_test_next_to_a_fixture():
    """GUILT: the exemption is scoped to the fixture, it does not blanket the file.

    The whole point of family #3 is that a fix for an over-match must not become
    an under-match: a genuinely assertionless test sitting beside a fixture must
    still be caught.
    """
    src = (
        "import pytest\n"
        "@pytest.fixture\n"
        "def test_client():\n"
        "    return TestClient(build())\n"
        "\n"
        "def test_nothing(test_client):\n"
        "    test_client.get('/health')\n"
    )
    assert "RH005" in _codes(src)


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


# ─── merge-commit guard (scar #3 over-match): a test inherited unchanged from a
#     merge parent must NOT be linted — only tests THIS commit introduces ──────


def test_merge_parents_empty_without_merge_head(monkeypatch):
    """_merge_parents() returns [] on an ordinary commit (no MERGE_HEAD) — so the
    merge-guard is a no-op and normal-commit behavior is unchanged."""
    from scripts import lint_test_reward_hacking as L

    class _R:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _R())
    assert L._merge_parents() == []


def test_merge_parents_lists_head_and_merge_head(monkeypatch):
    """When MERGE_HEAD resolves, parents = HEAD + each MERGE_HEAD sha (octopus-safe)."""
    from scripts import lint_test_reward_hacking as L

    class _R:
        returncode = 0
        stdout = "abc123\ndef456\n"

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _R())
    assert L._merge_parents() == ["HEAD", "abc123", "def456"]


def test_merge_guard_drops_inherited_test(monkeypatch):
    """A staged test whose blob equals a parent's blob (inherited via merge, never
    touched by this branch) is dropped from the lint set — the #1732 false-positive."""
    from scripts import lint_test_reward_hacking as L

    # one staged test file
    class _Diff:
        returncode = 0
        stdout = "apps/backend-rag/backend/tests/x_test.py\n"

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _Diff())
    monkeypatch.setattr(L, "_is_test_file", lambda p: True)
    # active merge with one parent
    monkeypatch.setattr(L, "_merge_parents", lambda: ["HEAD"])
    # staged blob == HEAD blob → inherited, must be dropped
    monkeypatch.setattr(
        L, "_git_blob",
        lambda ref, path: "SAMESHA",  # both ":0" (index) and "HEAD" return same
    )
    assert L._staged_test_files() == []


def test_merge_guard_keeps_introduced_test(monkeypatch):
    """A staged test whose blob differs from every parent (genuinely changed by this
    commit) is KEPT — the guard must not blind the linter to real cheats in a merge."""
    from scripts import lint_test_reward_hacking as L

    class _Diff:
        returncode = 0
        stdout = "apps/backend-rag/backend/tests/x_test.py\n"

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: _Diff())
    monkeypatch.setattr(L, "_is_test_file", lambda p: True)
    monkeypatch.setattr(L, "_merge_parents", lambda: ["HEAD"])

    def _blob(ref, path):
        return "INDEXSHA" if ref == ":0" else "PARENTSHA"

    monkeypatch.setattr(L, "_git_blob", _blob)
    assert [str(p) for p in L._staged_test_files()] == [
        "apps/backend-rag/backend/tests/x_test.py"
    ]
