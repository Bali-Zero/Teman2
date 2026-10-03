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
