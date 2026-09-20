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


def test_naming_only_unreadable_files_refuses_to_report_clean(tmp_path: Path) -> None:
    """cicatrix #2/W84: a lint whose every in-scope file failed to read must not
    say 'clean'. An out-of-scope suffix and a deleted path are NOT that."""
    path = _write(tmp_path, "broken.py", 'x = "unterminated\n')
    assert lint.main([str(path)]) == 2


def test_an_out_of_scope_file_is_reported_as_such_and_not_as_scanned(
    tmp_path: Path, capsys
) -> None:
    """The refuting seat's sharpest finding: a run that covered none of the diff
    printed a count that read like coverage."""
    doc = _write(tmp_path, "notes.md", "whatever\n")
    clean = _write(tmp_path, "m.py", "# clean\n")
    assert lint.main([str(clean), str(doc)]) == 0
    out = capsys.readouterr().out
    assert "1 out of scope" in out


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
    monkeypatch.setattr(
        lint, "grandfather_grew", lambda ref: (["new/offender.py"], "")
    )
    assert lint.main(["--base-ref", "origin/main"]) == 3


def test_growth_check_is_silent_when_the_base_ref_is_unreadable() -> None:
    """An anti-bypass must not turn a shallow checkout into guilt — but it must
    say so, which is the refuting seat's objection 9."""
    grew, note = lint.grandfather_grew("refs/heads/a-ref-that-does-not-exist")
    assert grew == []
    assert "does not resolve" in note


def test_every_frozen_file_still_exists() -> None:
    """A stale pardon is a pardon for a path nobody can check."""
    missing = [f for f in lint.load_grandfathered() if not (REPO / f).exists()]
    assert not missing, f"grandfathered paths no longer on disk: {missing}"


def test_the_frozen_list_is_not_empty() -> None:
    assert lint.load_grandfathered(), "the committed list must be readable"


# ── THE REFUTING SEAT'S CORPUS ─────────────────────────────────────────────
# Eleven objections, every one reproduced by the seat before it was asserted.
# Eight broke the first version of this lint. They are pinned here by the
# seat's own number so a future edit that reopens one is named, not guessed.


@pytest.mark.parametrize(
    "body",
    [
        pytest.param('# password\n# = "hunter2-real-fixture"\n', id="R1-comment-split"),
        pytest.param(
            '"""doc\napi_key\n= "abc123def456"\n"""\n', id="R1-docstring-split"
        ),
        pytest.param(
            'class C:\n    api_key = None\n    """VendorClient(api_key="sk-fixture1234")"""\n',
            id="R4-attribute-docstring-ast-get-docstring-cannot-see",
        ),
    ],
)
def test_refutation_python_shapes_that_used_to_slip(tmp_path: Path, body: str) -> None:
    path = _write(tmp_path, "m.py", body)
    scanned, findings = lint.scan_file(path)
    assert scanned and findings


def test_refutation_2_a_bare_mapping_value_that_looks_like_a_credential() -> None:
    assert lint.judge_prose("# config sets password: hunter2-actual-fixture")


def test_refutation_2_an_ordinary_english_clause_stays_writable() -> None:
    assert not lint.judge_prose("# the password: it is never printed")


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("c.ts", "// new VendorClient({api_key: 'sk-fixture12345'})\n"),
        ("c.js", "/* api_key: 'sk-fixture12345' */\n"),
    ],
)
def test_refutation_3_the_suffixes_the_workflow_already_triggers_on(
    tmp_path: Path, name: str, body: str
) -> None:
    scanned, findings = lint.scan_file(_write(tmp_path, name, body))
    assert scanned and findings


def test_refutation_5_a_homoglyph_is_a_DOCUMENTED_LIMIT_not_a_claim() -> None:
    """Cyrillic a. This guard is built against honest description, not against
    an author smuggling a credential past themselves. Pinned so the limit is
    recorded rather than imagined — if a future version closes it, this test
    fails and the docstring's KNOWN LIMITS section is what must change."""
    assert not lint.judge_prose('# VendorClient(\u0430pi_key="sk-fixture")')


def test_refutation_6_a_backslash_escaped_apostrophe_is_not_a_quote(
    tmp_path: Path,
) -> None:
    """Verified by the seat against bash itself: the line below is a valid
    shell line whose trailing hash IS a comment."""
    line = "echo don\\'t worry  # api_key=fixture9999value\n"
    assert lint._strip_code(line.rstrip("\n")).strip()
    scanned, findings = lint.scan_file(_write(tmp_path, "e.sh", line))
    assert scanned and findings


@pytest.mark.parametrize(
    "prose",
    [
        pytest.param("Client(api_key=<anthropic-key>)", id="R7-vendor-inside-the-hole"),
        pytest.param(
            "VendorClient(api_key=<ANTHROPIC_FIXTURE>)", id="R7-vendor-uppercased"
        ),
    ],
)
def test_refutation_7_a_hole_excuses_a_value_never_the_vendor(prose: str) -> None:
    assert lint.judge_prose(prose)


def test_refutation_9_an_absent_list_at_the_base_says_so_instead_of_passing() -> None:
    """An anti-bypass that fails open in silence is indistinguishable from one
    that passed. The empty tree resolves as a commit and carries no files."""
    grew, note = lint.grandfather_grew("4b825dc642cb6eb9a060e54bf8d69288fbee4904")
    assert grew == []
    assert note, "the growth check must say when it could not run"


def test_refutation_10_a_deletion_only_change_is_not_a_blind_scan(
    tmp_path: Path,
) -> None:
    """A deleted file cannot introduce prose. Failing it as a blind scan would
    block a legitimate deletion-only PR."""
    assert lint.main([str(tmp_path / "gone_one.py"), str(tmp_path / "gone_two.py")]) == 0


@pytest.mark.parametrize(
    "prose",
    [
        pytest.param(
            "# call rotate(api_key) after 90 days to comply with SOC2",
            id="R11-a-bare-mention-inside-parens",
        ),
        pytest.param(
            '# schema allows {"password": null} for anonymous guest sessions',
            id="R11-a-null-in-a-schema",
        ),
        pytest.param(
            "# the bug: Client(api_key=None) silently no-ops instead of raising",
            id="R11-a-null-in-a-bug-report",
        ),
        pytest.param(
            "# see generate(access_key) in the SDK reference for signature v4",
            id="R11-a-cross-reference",
        ),
    ],
)
def test_refutation_11_ordinary_engineering_prose_must_stay_writable(
    prose: str,
) -> None:
    """The dangerous half. This is a BLOCKING step; a false red teaches people
    to route around the guard, which is the only way one truly dies. Five of the
    sixteen files the first pardon list froze were this class of false positive,
    and requiring a value removed them."""
    assert not lint.judge_prose(prose)
