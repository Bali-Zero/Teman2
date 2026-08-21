"""Guilt + innocence for scripts/lint_pg_dsn_credentials.py.

Every password-shaped string here is assembled from fragments at import time.
A literal 10+ char alnum string in this file would make it the scanner's own
first finding, and the usual escape — exempting the guard's own test path —
is how a guard grows a hole named after itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "lint_pg_dsn_credentials",
    Path(__file__).resolve().parents[1] / "lint_pg_dsn_credentials.py",
)
assert _SPEC and _SPEC.loader
lint = importlib.util.module_from_spec(_SPEC)
sys.modules["lint_pg_dsn_credentials"] = lint
_SPEC.loader.exec_module(lint)

_REAL_BODY = "2z" + "Ejit43IF" + "6gNUV"  # the sync_targeted.py shape, 15 chars
_OTHER_BODY = "Kx9" + "mQp2Rz" + "7Lb4Wt"  # a different 15-char literal


def _dsn(body: str = _OTHER_BODY, scheme: str = "postgresql") -> str:
    return f"{scheme}://backend_rag_v2:{body}@nuzantara-postgres.flycast:5432/nuzantara_rag"


# ---------------------------------------------------------------- guilt


@pytest.mark.parametrize(
    "label,text",
    [
        ("python fallback default", 'DB = "' + _dsn() + '"'),
        ("shell export", "export DATABASE_URL=" + _dsn(scheme="postgres")),
        ("env file line", "DATABASE_URL=" + _dsn()),
        ("markdown code block", "```\nDB_URL = " + _dsn() + "\n```"),
        ("psql cli one-liner", "psql '" + _dsn() + "'"),
    ],
)
def test_guilt_a_real_shaped_dsn_password_is_found(label: str, text: str) -> None:
    assert lint.scan_text(text), f"scanner blind to a DSN password in {label}"


def test_guilt_the_burned_sync_targeted_literal_is_named_not_merely_flagged() -> None:
    """The known-compromised registry is matched by hash, so a re-introduction
    of THAT password says where it leaked from instead of just 'a password'."""
    assert "514ff07dd2f405f6" in lint.KNOWN_COMPROMISED
    assert "sync_targeted.py" in lint.KNOWN_COMPROMISED["514ff07dd2f405f6"]
    fingerprint = lint._fingerprint(_REAL_BODY)
    assert fingerprint == "514ff07dd2f405f6", "test fixture no longer matches the real leaked value"
    hits = lint.scan_text(_dsn(_REAL_BODY))
    assert hits
    assert "sync_targeted.py" in hits[0]


def test_innocence_an_explicitly_marked_synthetic_fixture_passes() -> None:
    same_line = f'FAKE = "{_dsn()}"  # synthetic-pg-password'
    line_above = f"# synthetic-pg-password\nFAKE = \"{_dsn()}\"\n"
    assert not lint.scan_text(same_line)
    assert not lint.scan_text(line_above)


def test_the_synthetic_marker_cannot_launder_a_known_burned_password(monkeypatch) -> None:
    monkeypatch.setitem(lint.KNOWN_COMPROMISED, lint._fingerprint(_REAL_BODY), "@test-fixture")
    marked = f'DSN = "{_dsn(_REAL_BODY)}"  # synthetic-pg-password'
    hits = lint.scan_text(marked)
    assert hits, "a burned password must be reported however it is marked"
    assert "@test-fixture" in hits[0]


def test_the_marker_two_lines_above_does_not_reach() -> None:
    text = "# synthetic-pg-password\n# unrelated comment\n" + f'D = "{_dsn()}"\n'
    assert lint.scan_text(text)


def test_guilt_findings_never_contain_the_password_body() -> None:
    findings = lint.scan_text(_dsn())
    assert findings
    assert _OTHER_BODY not in "\n".join(findings)


# ------------------------------------------------------------ innocence


@pytest.mark.parametrize(
    "label,text",
    [
        ("established rotation placeholder", "backend_rag_v2:<<ROTATED_2026_05_22_see_DATABASE_URL_env>>@localhost:15432/nuzantara_rag"),
        ("angle-bracket placeholder", "postgresql://backend_rag_v2:<password>@localhost:15432/nuzantara_rag"),
        ("short test word secret", "postgres://backend_rag_v2:secret" + "@nuzantara-postgres.flycast:5432/nuzantara_rag"),
        ("dot-env template value", "WA_MIRROR_DATABASE_URL=postgresql://backend_rag_v2:CHANGE_ME" + "@localhost:15432/nuzantara_rag"),
        ("short placeholder word", "FLY_TUNNEL_URL=postgresql://backend_rag_v2:PASS" + "@localhost:15432/nuzantara_rag"),
        ("env-var read, no literal", 'DB = os.environ.get("WA_LAUNCHER_DB_DSN") or os.environ.get("DATABASE_URL")'),
        ("unrelated role, test DSN", "DATABASE_URL: postgresql://test:test" + "@localhost:5432/nuzantara_test"),
        ("different role, password-shaped value", "postgresql://nuzantara:nuzantara_local_2024" + "@localhost:5432/nuzantara"),
        ("repeated-char placeholder", "backend_rag_v2:" + "x" * 20 + "@localhost"),
        ("two-char alternating placeholder", "backend_rag_v2:" + "ab" * 8 + "@localhost"),
        ("bare role name, no password", 'RUNTIME_ROLE = "backend_rag_v2"'),
        ("comment mentioning the role", "# backend_rag_v2 does NOT have pg_monitor granted"),
        ("sha256 digest", "commit sha256:3d69bc0e10ab4419f8b2c7d5e6a1f0b3c2d4e5f6"),
    ],
)
def test_innocence_lookalikes_do_not_fire(label: str, text: str) -> None:
    assert not lint.scan_text(text), f"false positive on {label}"


# ------------------------------------------------------------- behaviour


def test_a_path_that_does_not_exist_is_an_error_not_a_clean_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["lint", str(tmp_path / "does-not-exist.md")])
    assert lint.main() == 2


def test_an_all_scan_that_read_nothing_is_not_reported_clean(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lint, "_tracked_files", lambda root: [])
    monkeypatch.setattr(sys, "argv", ["lint", "--all"])
    assert lint.main() == 2


def test_innocence_a_commit_of_only_binaries_is_not_blocked(tmp_path, monkeypatch) -> None:
    png = tmp_path / "logo.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd")
    monkeypatch.setattr(sys, "argv", ["lint", str(png)])
    assert lint.main() == 0


def test_a_clean_readable_file_exits_zero(tmp_path, monkeypatch) -> None:
    good = tmp_path / "ok.md"
    good.write_text("DATABASE_URL comes from ${DATABASE_URL}\n")
    monkeypatch.setattr(sys, "argv", ["lint", str(good)])
    assert lint.main() == 0


def test_a_file_carrying_a_dsn_password_exits_one(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "leak.md"
    bad.write_text(_dsn() + "\n")
    monkeypatch.setattr(sys, "argv", ["lint", str(bad)])
    assert lint.main() == 1


def test_the_embedded_selftest_passes() -> None:
    assert lint.selftest() == 0


# ------------------------------------------------------- mutation guard


def test_mutation_disabling_the_length_floor_is_caught_by_selftest() -> None:
    """If the 10-char floor regresses to something that swallows short
    placeholders (e.g. dropped to 3), the innocence fixtures must catch it —
    this is the assertion the PR description's mutation-verification claim
    rests on: turn the guard off and confirm tests go red, not green.

    2026-08-21 generalization moved the length floor OUT of `DSN_PASSWORD_RE`
    (which now matches ANY role, any-length password segment, for the shape
    check to judge) and INTO `_is_real_looking_password`'s `len(body) < 10`
    gate — so the mutation this test performs moved with it: weaken that
    function's floor, not the regex.
    """
    # High-diversity but SHORT (8 chars) — clears `_is_placeholder` on its own
    # merit, so this isolates the length floor specifically, not the
    # distinct-character filter.
    short_diverse = "Ab3Kx9Qz"
    text = f"postgresql://backend_rag_v2:{short_diverse}@localhost:15432/nuzantara_rag"

    original = lint._is_real_looking_password

    def weakened(body: str) -> bool:
        if len(body) < 3:  # floor dropped from 10 to 3
            return False
        if lint._is_placeholder(body):
            return False
        if any(c in body for c in "<>${}"):
            return False
        if any(c.isspace() for c in body):
            return False
        if lint._is_template_shaped(body):
            return False
        return True

    try:
        lint._is_real_looking_password = weakened
        assert lint.scan_text(text), (
            "weakening the length floor should make an 8-char diverse token match "
            "— if this assertion itself fails, the mutation didn't do what it claims"
        )
    finally:
        lint._is_real_looking_password = original
    # With the floor restored, the same innocent (too-short) text must NOT fire.
    assert not lint.scan_text(text)
