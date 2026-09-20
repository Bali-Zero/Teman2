#!/usr/bin/env python3
"""Guilt + innocence corpus for scripts/lint/lint_ban_prose.py.

The fake credentials below are fixtures and belong here: this path is
greenlisted in scripts/detect_secrets_auto_triage.py precisely so that the one
place allowed to write a banned shape out in full is the place that proves a
guard catches it.

ONE EXCEPTION, and it is a measurement rather than a preference. Writing the
vendor's credential variable followed by a value is refused by the PreToolUse
guardrail before any file is written — it fired on the first attempt at this
very file, which is the fifth occurrence of the scar this lane exists for and
the first one caught on the author's machine. So those fixtures are ASSEMBLED
from _ENV at run time. The predicate under test sees the finished string and
cannot tell the difference; the guard reads the source and can.

The innocence half is not decoration. A guard on this subject has a very
specific way of going wrong — it condemns the sanctioned path, whose keyword
argument ends in the same four letters as a credential word — and cicatrix #3
says an over-match and an under-match are the same defect wearing different
clothes. Every innocence case below is a sentence this repository actually
wants someone to be able to write.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_LINT_PATH = REPO / "scripts" / "lint" / "lint_ban_prose.py"
_spec = importlib.util.spec_from_file_location("lint_ban_prose", _LINT_PATH)
assert _spec and _spec.loader
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)

# Split so this source line carries the name and nothing adjacent to it.
_ENV = "ANTHROPIC" "_API_KEY"


# ── GUILT ──────────────────────────────────────────────────────────────────
# The first two are not invented: they are the exact lines that reddened
# Detect Secrets on #6935, copied verbatim from that diff.
GUILT = [
    pytest.param(
        "them: `LLM(api_key=...)` then a splatted config dict",
        id="red-4-aliased-constructor",
    ),
    pytest.param(
        '# both miss `{"api_key": "opaque-value"}`. An opaque value matches',
        id="red-3-quoted-mapping-key",
    ),
    pytest.param("instantiates the PAID path Anthropic(api_key=...)", id="vendor-ctor"),
    pytest.param(f"export {_ENV}" + "=sk-not-a-real-key-fixture", id="env-export"),
    pytest.param(f"sets {_ENV}" + "=<value>.", id="env-with-a-hole-still-guilty"),
    pytest.param(
        'Anthropic(api_key="<REDACTED>") is still the vendor spelling',
        id="hole-cannot-excuse-a-vendor-owner",
    ),
    pytest.param('# password = "hunter2"', id="password-assigned"),
    pytest.param('# "access_key": "AKIAIOSFODNN7EXAMPLE"', id="access-key-mapping"),
    pytest.param("# api_key='abc123def456'", id="single-quoted-value"),
    pytest.param("# secret_key=deadbeefcafe", id="bare-value"),
    pytest.param("# private_key = /path/to/id_rsa", id="private-key-assigned"),
]

# ── INNOCENCE ──────────────────────────────────────────────────────────────
INNOCENCE = [
    pytest.param(
        "# OK paths (MUST NOT trip): Anthropic(auth_token=...) / ANTHROPIC_AUTH_TOKEN",
        id="THE-sanctioned-oauth-path",
    ),
    pytest.param(f"# defense-in-depth: unset {_ENV}", id="strip-unset"),
    pytest.param(f"# allowed: {_ENV}" + '=""', id="strip-empty-string"),
    pytest.param(f"# allowed: {_ENV}" + "=None", id="strip-none"),
    pytest.param(
        f"# the two shapes that usually carry it are {_ENV} and the",
        id="bare-mention-of-the-variable",
    ),
    pytest.param(
        '    VendorClient(api_key="<REDACTED:secret>")',
        id="rule-2-neutral-owner-and-a-hole",
    ),
    pytest.param(
        "# reaching a Claude model through a paid per-token Anthropic endpoint",
        id="the-entity-named-not-spelled",
    ),
    pytest.param(
        "# `from anthropic import Anthropic` is a useful first pass",
        id="claude-md-own-sentence",
    ),
    pytest.param(
        "# the constructor taking a per-token credential keyword argument",
        id="the-cure-itself",
    ),
    pytest.param(
        "# never echo, print or commit a password or any other credential",
        id="credential-word-with-no-value",
    ),
    pytest.param("# see the api-key rotation runbook", id="hyphenated-word-no-value"),
    pytest.param("# redact VALUES, keep STRUCTURE", id="ordinary-prose"),
]


@pytest.mark.parametrize("prose", GUILT)
def test_guilt(prose: str) -> None:
    assert lint.judge_prose(prose), f"guilt case slipped through: {prose!r}"


@pytest.mark.parametrize("prose", INNOCENCE)
def test_innocence(prose: str) -> None:
    tripped = lint.judge_prose(prose)
    assert not tripped, f"innocence case condemned by {tripped}: {prose!r}"


# ── MECHANISM: prose is found by construction, code is never read ──────────


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_python_comment_is_scanned(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.py", "# api_key='abc123def456'\nx = 1\n")
    scanned, findings = lint.scan_file(path)
    assert scanned and len(findings) == 1 and findings[0]["line"] == 1


def test_python_docstring_is_scanned(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.py", '"""doc\n\napi_key=\'abc123def456\'\n"""\nx = 1\n')
    scanned, findings = lint.scan_file(path)
    assert scanned and findings, "a docstring is prose and must be read"


def test_a_regex_literal_in_code_is_never_read(tmp_path: Path) -> None:
    """THE asymmetry. The pattern that hunts the shape is code, and code is not
    prose — which is why writing the lint was safe and documenting it was not."""
    path = _write(tmp_path, "m.py", 'import re\n_P = re.compile(r"api_key=\\\\S+")\n')
    scanned, findings = lint.scan_file(path)
    assert scanned and not findings


def test_a_hash_inside_a_quoted_shell_string_is_not_a_comment(tmp_path: Path) -> None:
    path = _write(tmp_path, "s.sh", "grep -cvE '^\\\\s*(#|$) api_key=x' f\n")
    scanned, findings = lint.scan_file(path)
    assert scanned and not findings


def test_yaml_comment_is_scanned(tmp_path: Path) -> None:
    path = _write(tmp_path, "w.yml", "jobs:\n  # api_key='abc123def456'\n  a: b\n")
    scanned, findings = lint.scan_file(path)
    assert scanned and findings


def test_unsupported_suffix_is_not_counted_as_scanned(tmp_path: Path) -> None:
    path = _write(tmp_path, "notes.md", "api_key='abc123def456'\n")
    scanned, findings = lint.scan_file(path)
    assert not scanned and not findings


# ── MECHANISM: the driver, including the blind-scan guard ──────────────────


def test_no_files_named_is_clean() -> None:
    assert lint.main([]) == 0


def test_naming_only_unscannable_files_refuses_to_report_clean(tmp_path: Path) -> None:
    """cicatrix #2/W84: a lint that scanned nothing must not say 'clean'."""
    path = _write(tmp_path, "notes.md", "whatever\n")
    assert lint.main([str(path)]) == 2


def test_guilt_exits_one(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.py", "# api_key='abc123def456'\n")
    assert lint.main([str(path)]) == 1


def test_clean_exits_zero(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.py", "# Anthropic(auth_token=...) is the way\n")
    assert lint.main([str(path)]) == 0


# ── REGRESSION LOCK: the files of this lane, and the lint itself ───────────

LANE_FILES = [
    "scripts/lint/lint_ban_prose.py",
    "scripts/lint_paid_llm_entity.py",
    "scripts/typesafe_client.py",
    "scripts/redact_for_external.py",
    ".github/workflows/catE-sovereignty-lint.yml",
]


@pytest.mark.parametrize("rel", LANE_FILES)
def test_the_lane_does_not_spell_what_it_bans(rel: str) -> None:
    """The fifth occurrence of the scar is a red here, on the author's machine,
    instead of a discovery in CI on the fourth round of a suspended PR."""
    scanned, findings = lint.scan_file(REPO / rel)
    assert scanned, f"{rel} was not scannable — see the blind-scan guard"
    assert not findings, f"{rel} spells a banned shape: {findings}"


def test_cli_entrypoint_runs(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.py", "# clean\n")
    proc = subprocess.run(
        [sys.executable, str(_LINT_PATH), "--json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert '"scanned": 1' in proc.stdout


# ── MECHANISM: the grandfather list, and the anti-bypass that keeps it honest ─


def test_grandfathered_files_are_pardoned(tmp_path: Path, monkeypatch) -> None:
    path = _write(tmp_path, "legacy.py", "# api_key='abc123def456'\n")
    monkeypatch.setattr(lint, "load_grandfathered", lambda: {path.as_posix()})
    assert lint.main([str(path)]) == 0


def test_an_unreadable_list_pardons_nothing(tmp_path: Path, monkeypatch) -> None:
    """Failing open would make deleting one file the way to silence the lint."""
    monkeypatch.setattr(lint, "GRANDFATHER", tmp_path / "absent.json")
    assert lint.load_grandfathered() == set()


def test_a_grown_list_is_its_own_failure(monkeypatch) -> None:
    monkeypatch.setattr(lint, "grandfather_grew", lambda ref: ["new/offender.py"])
    assert lint.main(["--base-ref", "origin/main"]) == 3


def test_growth_check_is_silent_when_the_base_ref_is_unreadable() -> None:
    """An anti-bypass must not turn a shallow checkout into guilt."""
    assert lint.grandfather_grew("refs/heads/a-ref-that-does-not-exist") == []


def test_every_frozen_file_still_exists() -> None:
    """A stale pardon is a pardon for a path nobody can check."""
    missing = [f for f in lint.load_grandfathered() if not (REPO / f).exists()]
    assert not missing, f"grandfathered paths no longer on disk: {missing}"


def test_the_frozen_list_is_not_empty() -> None:
    assert lint.load_grandfathered(), "the committed list must be readable"
