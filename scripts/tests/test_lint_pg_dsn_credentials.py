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


# ------------------------------------------------- mutation-sweep pins (2026-10-12)
#
# Expected values come from the module docstring's stated contract: a DSN
# password is real-looking when it is 10+ characters, has MORE than 4 distinct
# characters, no `<>${}`, no whitespace and is not an alpha/digit-segmented
# template; a GOCSPX body is 20+ base64url chars and not a placeholder. Every
# fixture is a synthetic string assembled from short fragments (the file's own
# discipline) — none is a credential.

import hashlib
import re
import subprocess


def _dsn_for(body: str, role: str = "svc_role") -> str:
    return "postgresql://" + role + ":" + body + "@localhost:5432/db"


def _gocspx(body: str) -> str:
    return "GOCSPX" + "-" + body


_TEN = "Kx9" + "mQp2" + "Rz7"  # 10 chars, 10 distinct-ish, mixed
_NINE = _TEN[:9]  # 9 chars


def test_password_length_floor_is_ten_characters() -> None:
    assert len(_TEN) == 10 and len(_NINE) == 9
    assert lint.scan_text(_dsn_for(_TEN))
    assert not lint.scan_text(_dsn_for(_NINE))


def test_more_than_four_distinct_characters_is_the_placeholder_boundary() -> None:
    four = "abcd" * 4  # 16 chars, 4 distinct -> placeholder
    five = "abcde" * 3  # 15 chars, 5 distinct -> real-looking
    assert len(set(four)) == 4 and len(set(five)) == 5
    assert not lint.scan_text(_dsn_for(four))
    assert lint.scan_text(_dsn_for(five))
    # same boundary for the GOCSPX shape (shared placeholder rule)
    assert not lint.scan_text(_gocspx("abcd" * 6))
    assert lint.scan_text(_gocspx("abcde" * 5))


def test_template_shape_needs_two_or_more_clean_segments() -> None:
    # exactly two clean segments -> template -> innocent
    assert not lint.scan_text(_dsn_for("abcdefgh" + "_" + "12345678"))
    # one clean alpha run with no separator -> judged on entropy -> guilty
    assert lint.scan_text(_dsn_for("abcdefghijkl"))
    # a mixed segment breaks the template shape -> guilty
    assert lint.scan_text(_dsn_for("abcdefgh" + "_" + "12ab5678"))
    # hyphen separates segments just like underscore
    assert not lint.scan_text(_dsn_for("local" + "-" + "dev" + "-" + "2024" + "-" + "pw"))


def test_a_character_outside_the_token_alphabet_means_not_template() -> None:
    """All-alpha segments, but a '.' makes the body fail the alphabet check, so
    it is judged on entropy alone and is guilty."""
    body = "abcdefghij" + "_" + "klmn" + "." + "opqr"
    assert lint.scan_text(_dsn_for(body))


def test_whitespace_in_a_password_candidate_is_never_real_looking() -> None:
    assert lint._is_real_looking_password("Kx9mQp2Rz7") is True
    assert lint._is_real_looking_password("Kx9mQp 2Rz7Lb") is False
    assert lint._is_real_looking_password("Kx9mQp\t2Rz7Lb") is False


def test_interpolation_and_bracket_characters_are_placeholders() -> None:
    for ch in "<>${}":
        assert lint._is_real_looking_password("Kx9mQp" + ch + "2Rz7Lb") is False


def test_dsn_marker_on_the_last_line_does_not_excuse_the_first_line() -> None:
    dsn = _dsn_for(_TEN)
    text = f'A = "{dsn}"\nplain\n# synthetic-pg-password\n'
    assert len(lint.scan_text(text)) == 1


def test_dsn_marker_directly_above_excuses_only_the_line_below_it() -> None:
    d1, d2 = _dsn_for(_TEN, "r_one"), _dsn_for("Qm7" + "vX2pL9" + "sT4", "r_two")
    text = f"{d1}\n# synthetic-pg-password\n{d2}\n"
    findings = lint.scan_text(text)
    assert len(findings) == 1
    assert ":1:" in findings[0]
    assert "'r_one'" in findings[0]


def test_dsn_finding_names_path_line_role_length_and_fingerprint_only() -> None:
    text = "first\n" + _dsn_for(_TEN, "my_role") + "\n"
    (finding,) = lint.scan_text(text, "docs/a.md")
    fp = hashlib.sha256(_TEN.encode()).hexdigest()[:16]
    assert finding == (
        "docs/a.md:2: literal Postgres DSN password for role 'my_role' "
        f"(10 chars, sha256:{fp})"
    )
    assert _TEN not in finding


# ---- GOCSPX shape

_GBODY = "aZ3xQ9" + "mR7bN2kP5vT8" + "wY1c"  # 22 chars


def test_gocspx_body_length_floor_is_twenty() -> None:
    nineteen = _GBODY[:19]
    twenty = _GBODY[:20]
    assert lint.scan_text(_gocspx(twenty))
    assert not lint.scan_text(_gocspx(nineteen))


def test_gocspx_finding_format_and_fingerprint() -> None:
    text = "x\n" + _gocspx(_GBODY) + "\n"
    (finding,) = lint.scan_text(text, "f.py")
    fp = hashlib.sha256(_GBODY.encode()).hexdigest()[:16]
    assert finding == (
        "f.py:2: literal Google OAuth client secret (GOCSPX-...) "
        f"(22 chars, sha256:{fp})"
    )
    assert _GBODY not in finding


def test_gocspx_two_matches_on_one_line_are_both_reported() -> None:
    other = "Hj4Lp8" + "Qw2Rt6Yu0Io3" + "Pa5Dg"
    text = _gocspx(_GBODY) + " and " + _gocspx(other)
    assert len(lint.scan_text(text)) == 2


def test_gocspx_synthetic_marker_same_line_and_line_above() -> None:
    same = _gocspx(_GBODY) + "  # synthetic-oauth-secret"
    above = "# synthetic-oauth-secret\n" + _gocspx(_GBODY)
    assert not lint.scan_text(same)
    assert not lint.scan_text(above)


def test_gocspx_marker_two_lines_above_or_on_last_line_does_not_reach() -> None:
    two_above = "# synthetic-oauth-secret\n# other\n" + _gocspx(_GBODY) + "\n"
    assert len(lint.scan_text(two_above)) == 1
    wraps = _gocspx(_GBODY) + "\nplain\n# synthetic-oauth-secret\n"
    assert len(lint.scan_text(wraps)) == 1


def test_gocspx_marker_cannot_launder_a_known_burned_secret(monkeypatch) -> None:
    monkeypatch.setitem(lint.GOCSPX_KNOWN_COMPROMISED, lint._fingerprint(_GBODY), "burned-fixture")
    hits = lint.scan_text(_gocspx(_GBODY) + "  # synthetic-oauth-secret")
    assert len(hits) == 1
    assert hits[0].endswith(" — burned-fixture")


def test_synthetic_marker_for_dsn_does_not_hide_a_gocspx_on_a_different_line() -> None:
    text = "# synthetic-pg-password\n" + _dsn_for(_TEN) + "\nplain\n" + _gocspx(_GBODY) + "\n"
    findings = lint.scan_text(text)
    assert len(findings) == 1
    assert ":4:" in findings[0]


# ---- enumeration / paths / entry point

def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_tracked_files_skips_vendor_dirs_at_any_depth(tmp_path) -> None:
    repo = _git_repo(tmp_path)
    for rel in ("a.md", "docs/b.md", "node_modules/c.md", "pkg/.venv/d.md", "x/dist/e.md", ".next/f.md"):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    subprocess.run(["git", "add", "-A", "-f"], cwd=repo, check=True)
    assert sorted(lint._tracked_files(repo)) == sorted([repo / "a.md", repo / "docs/b.md"])


def test_tracked_files_raises_when_git_fails(tmp_path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(subprocess.CalledProcessError):
        lint._tracked_files(plain)


def test_scan_paths_counts_only_readable_text_and_reports_missing(tmp_path) -> None:
    a = tmp_path / "a.md"
    a.write_text("clean\n")
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xfe\x00")
    d = tmp_path / "adir"
    d.mkdir()
    gone = tmp_path / "gone.md"
    findings, scanned, missing = lint.scan_paths([a, blob, d, gone], tmp_path)
    assert (findings, scanned, missing) == ([], 1, [str(gone)])


def test_scan_paths_relative_inside_root_absolute_outside(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    inside = root / "leak.md"
    inside.write_text(_dsn_for(_TEN) + "\n")
    outside = tmp_path / "leak2.md"
    outside.write_text(_dsn_for(_TEN) + "\n")
    findings, scanned, _ = lint.scan_paths([inside, outside], root)
    assert scanned == 2
    assert findings[0].startswith("leak.md:1:")
    assert findings[1].startswith(str(outside) + ":1:")


def test_selftest_fails_closed_when_scanner_is_blind(monkeypatch, capsys) -> None:
    monkeypatch.setattr(lint, "scan_text", lambda text, path="<m>": [])
    assert lint.selftest() == 1
    out = capsys.readouterr().out
    assert "GUILT   miss" in out
    assert "selftest FAILED (" in out


def test_selftest_fails_closed_on_false_positives(monkeypatch, capsys) -> None:
    monkeypatch.setattr(lint, "scan_text", lambda text, path="<m>": ["hit"])
    assert lint.selftest() == 1
    assert "INNOCENCE false positive" in capsys.readouterr().out


def test_no_args_is_nothing_to_scan_exit_two(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["lint"])
    assert lint.main() == 2
    assert "nothing to scan" in capsys.readouterr().err


def test_all_mode_end_to_end_on_a_real_repo(tmp_path, monkeypatch, capsys) -> None:
    repo = _git_repo(tmp_path)
    (repo / "ok.md").write_text("DATABASE_URL comes from the environment\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["lint", "--all"])
    assert lint.main() == 0
    assert "in 1 tracked text file(s)" in capsys.readouterr().out

    (repo / "leak.md").write_text("x\n" + _dsn_for(_TEN) + "\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert lint.main() == 1
    out = capsys.readouterr().out
    assert "found in 1 place(s)" in out
    assert "leak.md:2:" in out
    assert _TEN not in out


def test_outside_a_git_repo_the_guard_never_reports_clean(tmp_path, monkeypatch) -> None:
    clean = tmp_path / "ok.md"
    clean.write_text("nothing here\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["lint", str(clean)])
    try:
        rc = lint.main()
    except subprocess.CalledProcessError:
        return
    assert rc != 0
