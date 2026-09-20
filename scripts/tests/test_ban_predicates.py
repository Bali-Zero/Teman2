"""Guilt + innocence for scripts/check_ban_predicates.py.

Two things need proving and they are different kinds of claim.

TRANSCRIPTION. The script re-states two regexes that live in
`.github/workflows/catE-sovereignty-lint.yml`. A transcription that drifts is
worse than no local check at all: it reports green on something CI will red, or
red on something CI allows. The first tests shell-unquote the workflow's own
`grep -rnE` arguments and compare them character for character.

BEHAVIOUR. The rest run the script against synthetic trees. Every banned
literal is ASSEMBLED at runtime rather than typed here — the predicates read
the FIXTURE, never this file, so the corpus is exactly as guilty either way,
and a spelled-out literal in a test source is what spent the incumbent's
budget in the first place.

Run:  python3 -m pytest scripts/tests/test_ban_predicates.py -q
"""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "catE-sovereignty-lint.yml"

_spec = importlib.util.spec_from_file_location(
    "check_ban_predicates", REPO_ROOT / "scripts" / "check_ban_predicates.py"
)
cbp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(cbp)

# The banned spellings, never written out in this file.
PAID_CALL = "Anthropic(" + "api_key" + "=os.environ['X'])"
OAUTH_CALL = "Anthropic(" + "auth_token" + "=os.environ['X'])"
QUOTED_KEY = '{"' + "api_key" + '": "opaque-value-here"}'


def _grep_args() -> list[list[str]]:
    """Shell-unquote every `grep -rnE ...` invocation in the workflow."""
    out = []
    for line in WORKFLOW.read_text().splitlines():
        marker = "grep -rnE "
        if marker not in line:
            continue
        rest = line.split(marker, 1)[1].rstrip()
        if rest.endswith("\\"):
            rest = rest[:-1]
        out.append(shlex.split(rest))
    return out


def _grep_v_args() -> list[str]:
    out = []
    for line in WORKFLOW.read_text().splitlines():
        marker = "grep -vE "
        if marker not in line:
            continue
        rest = line.split(marker, 1)[1].rstrip()
        if rest.endswith("\\"):
            rest = rest[:-1]
        parsed = shlex.split(rest)
        if parsed:
            out.append(parsed[0])
    return out


def test_p1_transcription_is_the_workflow_regex():
    patterns = [a[0] for a in _grep_args()]
    assert cbp.P1_PATTERN in patterns, (
        "the paid-constructor regex in check_ban_predicates.py is no longer "
        f"one the workflow runs; workflow has {patterns}"
    )


def test_p2_transcription_is_the_workflow_regex():
    patterns = [a[0] for a in _grep_args()]
    assert cbp.P2_PATTERN in patterns, (
        "the key-assignment regex in check_ban_predicates.py is no longer "
        f"one the workflow runs; workflow has {patterns}"
    )


def test_both_exclusion_lists_are_the_workflow_ones():
    excludes = _grep_v_args()
    assert cbp.P1_EXCLUDE in excludes
    assert cbp.P2_EXCLUDE in excludes


def test_posix_class_translation_keeps_the_meaning():
    rx = cbp._posix_bracket_to_python(cbp.P2_PATTERN)
    import re

    assert re.search(rx, "export ANTHROPIC_API_KEY=value")
    assert not re.search(rx, "unset ANTHROPIC_API_KEY")


# ── behaviour ───────────────────────────────────────────────────────────────


def _empty_baseline() -> str:
    """The repo's own baseline, emptied of results — same plugin set, no rows."""
    import json

    data = json.loads((REPO_ROOT / ".secrets.baseline").read_text())
    data["results"] = {}
    return json.dumps(data)


def _run(monkeypatch, tmp_path: Path, *names: str) -> int:
    """Judge RELATIVE paths inside a fake repo root.

    Absolute paths would carry pytest's own tmp dir name into the predicate,
    and every exclusion list here contains `test_` — the fixtures would excuse
    themselves and every guilt case would pass.
    """
    monkeypatch.setattr(cbp, "REPO_ROOT", tmp_path)
    baseline = tmp_path / ".secrets.baseline"
    if not baseline.exists():
        baseline.write_text(_empty_baseline())
    monkeypatch.setattr(cbp, "BASELINE", baseline)
    old = sys.argv
    sys.argv = ["check_ban_predicates.py", *names]
    try:
        return cbp.main()
    finally:
        sys.argv = old


def test_guilt_a_new_paid_call_site_is_refused(tmp_path, capsys, monkeypatch):
    (tmp_path / "app.py").write_text(f"client = {PAID_CALL}\n")
    assert _run(monkeypatch, tmp_path, "app.py") == 1
    assert "P1 catE #40" in capsys.readouterr().out


def test_innocence_the_oauth_constructor_passes(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(f"client = {OAUTH_CALL}\n")
    assert _run(monkeypatch, tmp_path, "app.py") == 0


def test_innocence_a_guilt_corpus_under_test_prefix_passes(tmp_path, monkeypatch):
    (tmp_path / "test_fixture.py").write_text(f"client = {PAID_CALL}\n")
    assert _run(monkeypatch, tmp_path, "test_fixture.py") == 0


def test_innocence_prose_that_describes_the_shape_passes(tmp_path, monkeypatch):
    (tmp_path / "doc.py").write_text(
        '"""We ban the vendor SDK constructor taking a per-token key."""\n'
    )
    assert _run(monkeypatch, tmp_path, "doc.py") == 0


def test_guilt_prose_that_spells_the_constructor_is_refused(tmp_path, monkeypatch):
    """The exact shape that reddened catE on PR #6926: a docstring quoting it."""
    (tmp_path / "doc.py").write_text(f'"""Do not write {PAID_CALL} here."""\n')
    assert _run(monkeypatch, tmp_path, "doc.py") == 1


@pytest.mark.skipif(
    shutil.which("detect-secrets") is None, reason="detect-secrets not installed"
)
def test_guilt_a_quoted_key_in_prose_is_refused_by_the_scanner(tmp_path, capsys, monkeypatch):
    """The shape that reddened Detect Secrets on #6926 and #6935.

    No grep predicate sees this one — it is the detect-secrets half, and it is
    the half that caught two of the four occurrences.
    """
    (tmp_path / "note.py").write_text(f"# the rule misses {QUOTED_KEY}\n")
    rc = _run(monkeypatch, tmp_path, "note.py")
    assert rc == 1
    assert "P3 detect-secrets" in capsys.readouterr().out


def test_a_missing_scanner_is_announced_and_never_silently_green(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cbp.shutil, "which", lambda _: None)
    (tmp_path / "app.py").write_text("x = 1\n")
    assert _run(monkeypatch, tmp_path, "app.py") == 0
    out = capsys.readouterr().out
    assert "NOT run" in out and "detect-secrets" in out
    assert out.count("ban-predicates] scanner half") == 1, (
        "the skip notice prints on every commit on a machine without the "
        "scanner; more than one line and it becomes wallpaper"
    )


def test_the_kill_switch_exits_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BAN_PREDICATES_ENFORCEMENT", "false")
    (tmp_path / "app.py").write_text(f"client = {PAID_CALL}\n")
    assert _run(monkeypatch, tmp_path, "app.py") == 0
    assert "DISABLED" in capsys.readouterr().out


# ── staged mode: only what this commit ADDS ─────────────────────────────────


def _repo(tmp_path: Path) -> Path:
    d = tmp_path / "wt"
    d.mkdir()
    run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    return d


def test_staged_mode_judges_added_lines_not_the_whole_file(tmp_path, monkeypatch, capsys):
    """A pre-existing offending line in a file you touch is not yours.

    Two such lines live in catE-sovereignty-lint.yml itself, so a whole-file
    rule would make that workflow uneditable without the kill switch — a gate
    you must disable to touch is a gate being trained out of existence.
    """
    d = _repo(tmp_path)
    (d / "app.py").write_text(f"client = {PAID_CALL}\n")
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "seed", "--no-verify"], cwd=d, check=True, capture_output=True
    )
    (d / "app.py").write_text(f"client = {PAID_CALL}\nunrelated = 1\n")
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)

    monkeypatch.setattr(cbp, "REPO_ROOT", d)
    monkeypatch.setattr(cbp, "BASELINE", d / ".secrets.baseline")
    old = sys.argv
    sys.argv = ["check_ban_predicates.py", "--staged"]
    try:
        rc = cbp.main()
    finally:
        sys.argv = old
    assert rc == 0, capsys.readouterr().out


def test_staged_mode_refuses_an_added_offending_line(tmp_path, monkeypatch, capsys):
    d = _repo(tmp_path)
    (d / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "seed", "--no-verify"], cwd=d, check=True, capture_output=True
    )
    (d / "app.py").write_text(f"x = 1\nclient = {PAID_CALL}\n")
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)

    monkeypatch.setattr(cbp, "REPO_ROOT", d)
    monkeypatch.setattr(cbp, "BASELINE", d / ".secrets.baseline")
    old = sys.argv
    sys.argv = ["check_ban_predicates.py", "--staged"]
    try:
        rc = cbp.main()
    finally:
        sys.argv = old
    assert rc == 1
    assert "app.py:2" in capsys.readouterr().out
