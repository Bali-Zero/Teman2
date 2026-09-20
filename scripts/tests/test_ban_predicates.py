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


# ── the --baseline flag this gate needed, and the near-miss that shaped it ──
#
# P3 asks "what WOULD a scan say" and must not answer by mutating the tracked
# baseline. That is why `--baseline PATH` exists on both detect-secrets
# scripts. It is also why they now REFUSE an unknown flag: run as
# `--apply --baseline /tmp/copy.json` on a checkout that predated the flag,
# the old `set(sys.argv[1:])` parse dropped flag and path on the floor and
# rewrote the real `.secrets.baseline` — 616 lines deleted, caught only by
# `git status`.


def _run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / name), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )


@pytest.mark.parametrize(
    "script", ["detect_secrets_auto_triage.py", "detect_secrets_check_unaudited.py"]
)
def test_an_unknown_flag_is_refused_not_absorbed(script):
    r = _run_script(script, "--definitely-not-a-flag")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "definitely-not-a-flag" in (r.stdout + r.stderr)


def test_the_tracked_baseline_is_not_touched_by_an_off_tree_triage(tmp_path):
    tracked = REPO_ROOT / ".secrets.baseline"
    before = tracked.read_bytes()
    copy = tmp_path / "copy.json"
    copy.write_text(_empty_baseline())
    r = _run_script("detect_secrets_auto_triage.py", "--apply", "--baseline", str(copy))
    assert r.returncode == 0, r.stdout + r.stderr
    assert tracked.read_bytes() == before, "an off-tree triage rewrote the tracked baseline"


# ── council findings, each one a case that used to pass ─────────────────────


def test_innocence_unsetenv_is_a_strip_not_an_assignment():
    """codex-gpt-5.6-sol: "unsetenv" ends in "setenv".

    Without a word boundary the #40b alternative flagged the defensive STRIP
    the workflow's own comment calls allowed. Latent in CI, immediate here.
    """
    strip = "os." + "unsetenv" + '("ANTHROPIC_API_KEY")'
    assert cbp.grep_predicates([("app.py", 1, strip)]) == []


def test_guilt_a_real_setenv_assignment_still_fires():
    call = "os." + "setenv" + '("ANTHROPIC_API_KEY", "v")'
    assert cbp.grep_predicates([("app.py", 1, call)]) != []


def test_exclusion_reads_the_whole_output_line_exactly_as_ci_does():
    """kimi-code/k3: catE pipes `path:lineno:content` into `grep -vE`.

    A path-only copy is STRICTER than the workflow — it refuses a line CI
    lets through — and that is the direction that trains people to disable it.
    """
    line = "client = " + "Anthropic(" + "api_key" + "=contest_winner)"
    assert cbp.grep_predicates([("app.py", 1, line)]) == []
    plain = "client = " + "Anthropic(" + "api_key" + "=winner)"
    assert cbp.grep_predicates([("app.py", 1, plain)]) != []


def test_a_quoted_path_header_never_blames_the_previous_file(monkeypatch, capsys):
    """kimi-code/k3 and codex-gpt-5.6-sol, independently.

    git quotes any non-ASCII path, and the first parser only knew `+++ b/…`,
    so the quoted file's added lines were recorded under the PREVIOUS file in
    the diff. Hide one behind an excluded neighbour and it was never judged.
    `core.quotePath=false` removes that case; anything still unparseable must
    be COUNTED and announced, never attributed.
    """
    call = "client = " + "Anthropic(" + "api_key" + "=os.environ['X'])"
    diff = (
        "diff --git a/tests/a.py b/tests/a.py\n"
        "--- a/tests/a.py\n"
        "+++ b/tests/a.py\n"
        "@@ -0,0 +1 @@\n"
        "+x=1\n"
        'diff --git "a/caf\\\\303\\\\251.py" "b/caf\\\\303\\\\251.py"\n'
        '--- "a/caf\\\\303\\\\251.py"\n'
        '+++ "b/caf\\\\303\\\\251.py"\n'
        "@@ -0,0 +1 @@\n"
        f"+{call}\n"
    )
    monkeypatch.setattr(cbp, "_git", lambda *a: diff)
    entries, unattributed = cbp.staged_added_lines()
    assert unattributed == 1, entries
    assert all(path == "tests/a.py" for path, _, _ in entries)
    assert all(call not in text for _, _, text in entries)


def test_non_utf8_bytes_in_a_staged_file_do_not_crash_the_gate(tmp_path, monkeypatch, capsys):
    """kimi-code/k3: `text=True` decodes strictly.

    A Latin-1 byte anywhere in a staged file made `git diff` output
    undecodable, and the traceback came out of the pre-commit hook as a hard
    block on a commit with nothing wrong in it.
    """
    d = _repo(tmp_path)
    (d / "app.py").write_bytes(b'x = "\xe9"\n')
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)
    monkeypatch.setattr(cbp, "REPO_ROOT", d)
    monkeypatch.setattr(cbp, "BASELINE", d / ".secrets.baseline")
    (d / ".secrets.baseline").write_text(_empty_baseline())
    old = sys.argv
    sys.argv = ["check_ban_predicates.py", "--staged"]
    try:
        rc = cbp.main()
    finally:
        sys.argv = old
    assert rc == 0, capsys.readouterr().out


@pytest.mark.skipif(
    shutil.which("detect-secrets") is None, reason="detect-secrets not installed"
)
def test_the_scanner_judges_the_staged_blob_not_the_working_tree(tmp_path, monkeypatch, capsys):
    """kimi-code/k3: after `git add -p` the unstaged remainder is still on disk.

    Scanning the file as it sits refuses a commit for content the commit does
    not carry — and contradicts this script's own stated scope.
    """
    d = _repo(tmp_path)
    (d / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "app.py"], cwd=d, check=True, capture_output=True)
    # The offending line exists ONLY in the working tree, never in the index.
    (d / "app.py").write_text('x = 1\n' + "# " + '{"api_key": "opaque-value-here"}' + "\n")
    monkeypatch.setattr(cbp, "REPO_ROOT", d)
    baseline = d / ".secrets.baseline"
    baseline.write_text(_empty_baseline())
    monkeypatch.setattr(cbp, "BASELINE", baseline)
    old = sys.argv
    sys.argv = ["check_ban_predicates.py", "--staged"]
    try:
        rc = cbp.main()
    finally:
        sys.argv = old
    assert rc == 0, capsys.readouterr().out


def test_the_scanner_half_hands_back_numbers_and_never_a_string(tmp_path, monkeypatch):
    """The structural form of the CodeQL fix, asserted rather than trusted.

    Cutting the scanner's stdout out of the path was not enough: CodeQL kept
    calling this py/clear-text-logging-sensitive-data because any sentence
    built beside `BASELINE.read_text()` is downstream of that read. The cure
    is a type, not a filter — so this test guards the type. If someone
    reintroduces a message here, it fails before a reviewer has to notice.
    """
    d = _repo(tmp_path)
    (d / "note.py").write_text("# " + QUOTED_KEY + "\n")
    subprocess.run(["git", "add", "note.py"], cwd=d, check=True, capture_output=True)
    monkeypatch.setattr(cbp, "REPO_ROOT", d)
    baseline = d / ".secrets.baseline"
    baseline.write_text(_empty_baseline())
    monkeypatch.setattr(cbp, "BASELINE", baseline)

    located, skipped = cbp.detect_secrets_predicate(["note.py"], True)
    for item in located:
        assert isinstance(item, tuple) and len(item) == 2
        assert all(isinstance(v, int) for v in item), item
    if skipped is not None:
        code, detail = skipped
        assert code in cbp._SKIP_TEXT, code
        assert isinstance(detail, int)


def test_every_skip_code_has_a_message_and_formats_without_raising():
    for code, template in cbp._SKIP_TEXT.items():
        assert template.format(n=1, cap=cbp.SCAN_CAP)
