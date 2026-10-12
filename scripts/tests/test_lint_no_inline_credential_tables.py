#!/usr/bin/env python3
"""Guilt+innocence for `lint_no_inline_credential_tables.py` (family #3 discipline:
a guard on the ENTITY, never on a substring — over-match and under-match are
symmetric failures, both fixtures below prove one side each).

GUILT fixture: a literal table shaped exactly like the incident file — >=5
rows ending in two plaintext strings, next to a "password" mention. MUST flag.

INNOCENCE fixture: a table that also ends every row in two quoted strings (a
name + a department, say) but carries no credential keyword anywhere. MUST
NOT flag — proving the lint judges the credential-keyword+shape PAIR, not the
bare "tuple ending in two strings" substring shape.

    python3 -m pytest scripts/tests/test_lint_no_inline_credential_tables.py -q
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT = REPO_ROOT / "scripts" / "lint_no_inline_credential_tables.py"


def _load():
    spec = importlib.util.spec_from_file_location("lint_no_inline_credential_tables_under_test", LINT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


GUILTY_SOURCE = '''
# Per-client OSS login table (login, password)
ACCOUNTS: list[tuple[int, str, str]] = [
    (1, "svc_user_1", "Tr0ub4dor&1"),
    (2, "svc_user_2", "correct-horse-battery"),
    (3, "svc_user_3", "hunter2hunter2"),
    (4, "svc_user_4", "letmein12345"),
    (5, "svc_user_5", "p@ssw0rd!2026"),
    (6, "svc_user_6", "swordfish99"),
]
'''

INNOCENT_SOURCE = '''
# Staff directory: id, name, department.
STAFF: list[tuple[int, str, str]] = [
    (1, "Alice", "Engineering"),
    (2, "Bob", "Marketing"),
    (3, "Carla", "Finance"),
    (4, "Dedi", "Operations"),
    (5, "Eka", "Legal"),
    (6, "Fajar", "Support"),
]
'''


def test_guilty_fixture_is_flagged(tmp_path):
    lint = _load()
    f = tmp_path / "guilty.py"
    f.write_text(GUILTY_SOURCE)
    hits = lint.scan_file(f)
    assert hits >= 5, f"expected the credential-shaped table to be flagged, got hits={hits}"


def test_innocent_fixture_is_not_flagged(tmp_path):
    lint = _load()
    f = tmp_path / "innocent.py"
    f.write_text(INNOCENT_SOURCE)
    hits = lint.scan_file(f)
    assert hits == 0, f"expected a non-credential two-string table to pass clean, got hits={hits}"


def test_below_threshold_credential_table_is_not_flagged(tmp_path):
    """4 rows with a password keyword nearby must NOT flag (threshold is 5)."""
    lint = _load()
    f = tmp_path / "small.py"
    f.write_text(
        '# oss password table\n'
        'ACCOUNTS = [\n'
        '    (1, "u1", "pw1"),\n'
        '    (2, "u2", "pw2"),\n'
        '    (3, "u3", "pw3"),\n'
        '    (4, "u4", "pw4"),\n'
        ']\n',
    )
    hits = lint.scan_file(f)
    assert hits == 0, f"expected sub-threshold table to pass clean, got hits={hits}"


def test_main_exits_nonzero_on_guilty_file(tmp_path, monkeypatch):
    lint = _load()
    guilty = tmp_path / "guilty.py"
    guilty.write_text(GUILTY_SOURCE)
    monkeypatch.chdir(REPO_ROOT)
    rc = lint.main(["--files", str(guilty)])
    assert rc == 1


def test_main_exits_zero_on_innocent_file(tmp_path, monkeypatch):
    lint = _load()
    innocent = tmp_path / "innocent.py"
    innocent.write_text(INNOCENT_SOURCE)
    monkeypatch.chdir(REPO_ROOT)
    rc = lint.main(["--files", str(innocent)])
    assert rc == 0


# ------------------------------------------------- mutation-sweep pins (2026-10-12)
#
# Contract (module docstring + scan_file): a file is flagged only when a RUN of
# >= 5 single-line tuple/list rows ending in two quoted strings (comments do not
# break a run, any other line does) sits within its own declaration block — the
# run plus a 5-line look-back — together with a credential keyword. Rows below
# are obviously fake ("u1"/"pw1").

import subprocess

import pytest


def _rows(n: int, start: int = 1) -> str:
    return "".join(f'    ({i}, "u{i}", "pw{i}"),\n' for i in range(start, start + n))


def _scan(tmp_path, text: str) -> int:
    lint = _load()
    f = tmp_path / "t.py"
    f.write_text(text)
    return lint.scan_file(f)


def test_exactly_five_rows_with_keyword_is_flagged_and_count_is_exact(tmp_path):
    assert _scan(tmp_path, "# oss password table\nACCOUNTS = [\n" + _rows(5) + "]\n") == 5


def test_six_rows_report_six(tmp_path):
    assert _scan(tmp_path, "# password\n" + _rows(6)) == 6


def test_four_rows_with_keyword_is_clean(tmp_path):
    assert _scan(tmp_path, "# password\n" + _rows(4)) == 0


def test_rows_with_no_keyword_anywhere_is_clean(tmp_path):
    assert _scan(tmp_path, "# staff list\n" + _rows(8)) == 0


@pytest.mark.parametrize("kw", ["password", "PASSWORD", "credential", "secret", "login", "oss_user", "oss_pass"])
def test_each_documented_keyword_counts_case_insensitively(tmp_path, kw):
    assert _scan(tmp_path, f"# {kw} list\n" + _rows(5)) == 5


@pytest.mark.parametrize("word", ["plugin", "blogin", "pass", "user"])
def test_login_is_a_whole_word_and_near_misses_do_not_count(tmp_path, word):
    assert _scan(tmp_path, f"# {word} list\n" + _rows(5)) == 0


def test_keyword_five_lines_before_the_run_is_inside_the_window(tmp_path):
    text = "# password\n" + "a = 1\n" * 4 + _rows(5)  # keyword at start-5
    assert _scan(tmp_path, text) == 5


def test_keyword_six_lines_before_the_run_is_outside_the_window(tmp_path):
    text = "# password\n" + "a = 1\n" * 5 + _rows(5)  # keyword at start-6
    assert _scan(tmp_path, text) == 0


def test_comment_lines_before_the_first_row_do_not_extend_the_lookback(tmp_path):
    """The run starts at its first ROW; leading comments are not part of it, so
    a keyword six lines up is out of reach even when everything between is a
    comment."""
    text = "# password\n" + "# note\n" * 5 + _rows(5)
    assert _scan(tmp_path, text) == 0


def test_keyword_on_the_very_first_line_is_reachable_when_run_is_near_the_top(tmp_path):
    assert _scan(tmp_path, "# password\n" + _rows(5)) == 5


def test_keyword_inside_the_run_via_a_comment_counts(tmp_path):
    text = _rows(3) + "    # the secret ones\n" + _rows(2, start=4)
    assert _scan(tmp_path, text) == 5


def test_keyword_after_the_run_does_not_count(tmp_path):
    text = _rows(5) + "x = 1\ny = 2\n# password\n"
    assert _scan(tmp_path, text) == 0


def test_a_comment_inside_a_run_does_not_break_it(tmp_path):
    text = "# password\n" + _rows(3) + "    # between\n" + _rows(2, start=4)
    assert _scan(tmp_path, text) == 5


def test_a_code_line_inside_a_run_splits_it_into_two_short_runs(tmp_path):
    text = "# password\n" + _rows(3) + "x = 1\n" + _rows(2, start=4)
    assert _scan(tmp_path, text) == 0


def test_largest_run_wins_in_either_order(tmp_path):
    small_then_big = "# password\n" + _rows(5) + "x = 1\n# password\n" + _rows(7, start=10)
    big_then_small = "# password\n" + _rows(7) + "x = 1\n# password\n" + _rows(5, start=10)
    assert _scan(tmp_path, small_then_big) == 7
    assert _scan(tmp_path, big_then_small) == 7


def test_a_run_without_keyword_does_not_hide_a_later_run_with_one(tmp_path):
    text = _rows(6) + "x = 1\n" * 6 + "# login\n" + _rows(5, start=20)
    assert _scan(tmp_path, text) == 5


@pytest.mark.parametrize(
    "row",
    [
        '    [1, "u1", "pw1"],\n',
        '    [1, "u1", "pw1"]\n',
        "    (1, 'u1', 'pw1'),\n",
        '    (1, 2.5, "u1", "pw1"),\n',
    ],
)
def test_row_shapes_that_must_match(tmp_path, row):
    assert _scan(tmp_path, "# password\n" + row * 5) == 5


@pytest.mark.parametrize(
    "row",
    [
        '    (1, "u1", "pw1", 3),\n',          # last field is not a string
        '    (1, make("u1"), "pw1"),\n',       # nested call before the pair
        '    (1, "u1", pw1),\n',               # only one trailing string
        '    x = (1, "u1", "pw1")\n',          # assignment, not a bare row
    ],
)
def test_row_shapes_that_must_not_match(tmp_path, row):
    assert _scan(tmp_path, "# password\n" + row * 5) == 0


def test_unreadable_path_counts_zero(tmp_path):
    lint = _load()
    assert lint.scan_file(tmp_path / "does-not-exist.py") == 0
    assert lint.scan_file(tmp_path) == 0  # a directory


def test_repo_root_is_the_parent_of_scripts():
    assert _load().REPO_ROOT == REPO_ROOT


def test_tracked_py_files_excludes_only_the_guards_own_fixture_file():
    lint = _load()
    tracked = lint._tracked_py_files()
    assert "scripts/lint_no_inline_credential_tables.py" in tracked
    assert "scripts/tests/test_lint_no_inline_credential_tables.py" not in tracked
    assert tracked and all(p.endswith(".py") for p in tracked)
    assert "" not in tracked


def test_main_reports_the_flagged_file_and_count(tmp_path, monkeypatch, capsys):
    lint = _load()
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    (tmp_path / "bad.py").write_text("# password\n" + _rows(6))
    assert lint.main(["--files", "bad.py"]) == 1
    out = capsys.readouterr().out
    assert "FOUND inline credential-shaped table(s)" in out
    assert "  - bad.py: 6 password-shaped tuple/list literal(s)" in out


def test_main_clean_run_prints_scanned_count(tmp_path, monkeypatch, capsys):
    lint = _load()
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("# staff\n" + _rows(8))
    assert lint.main(["--files", "a.py", "b.py"]) == 0
    assert "clean (2 tracked *.py file(s) scanned)" in capsys.readouterr().out


def test_main_exit_two_when_git_listing_fails(tmp_path, monkeypatch, capsys):
    """Operational error is its own exit code, never a silent clean."""
    lint = _load()
    monkeypatch.setattr(lint, "REPO_ROOT", tmp_path)  # a directory that is not a git repo
    assert lint.main([]) == 2
    assert "git ls-files failed" in capsys.readouterr().err
