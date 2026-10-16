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


# ---------------------------------------------------------------------------
# Bare two-field rows (login, password) — the shape the regex's own comment
# lists as its second example, and the most natural shape of such a table.
# Before the fix the regex demanded a field BEFORE the trailing pair, so these
# were invisible. Expected counts are by-hand from the fixture.
# ---------------------------------------------------------------------------


def _scan_text(tmp_path, text):
    lint = _load()
    f = tmp_path / "t.py"
    f.write_text(text)
    return lint.scan_file(f)


def test_guilt_bare_pair_list_rows_next_to_a_password_comment_are_flagged(tmp_path):
    rows = "".join(f'    ["u{i}", "pw{i}"],\n' for i in range(1, 7))
    assert _scan_text(tmp_path, "# oss password pairs\nPAIRS = [\n" + rows + "]\n") == 6


def test_guilt_bare_pair_tuple_rows_with_declaring_variable_name_are_flagged(tmp_path):
    rows = "".join(f'    ("u{i}", "pw{i}"),\n' for i in range(1, 6))
    assert _scan_text(tmp_path, "PASSWORD_PAIRS = [\n" + rows + "]\n") == 5


def test_innocence_bare_pair_below_threshold_is_clean(tmp_path):
    rows = "".join(f'    ("u{i}", "pw{i}"),\n' for i in range(1, 5))
    assert _scan_text(tmp_path, "# password pairs\n" + rows) == 0


def test_innocence_bare_pair_vocabulary_mentioning_the_keyword_in_its_rows_is_clean(tmp_path):
    """A (text, category) label table whose ROWS mention the word is not a
    credential table: the keyword must come from the declaration, not the data."""
    text = (
        "CATEGORIES = [\n"
        '    ("credential revoked", "security"),\n'
        '    ("payment quota exhausted", "billing"),\n'
        '    ("secret rotation due", "security"),\n'
        '    ("disk inode exhausted", "storage"),\n'
        '    ("service timeout", "availability"),\n'
        "]\n"
    )
    assert _scan_text(tmp_path, text) == 0


def test_original_three_field_rows_still_count_a_keyword_that_sits_in_a_row(tmp_path):
    """The widening must not change the original shape's behaviour."""
    rows = "".join(f'    ({i}, "oss_user_{i}", "x{i}"),\n' for i in range(1, 6))
    assert _scan_text(tmp_path, "ROWS = [\n" + rows + "]\n") == 5
