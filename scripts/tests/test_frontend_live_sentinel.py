"""Tests for .github/workflows/frontend-live-sentinel.yml — the "is production stale?" guard.

The guard is two decisions written in shell inside a workflow, so both are EXTRACTED from
the workflow text here rather than retyped: a retyped copy would pass forever while the
real gate rots (W65 — never build on a citation you did not re-read).

  1. WHICH commit must production include — the latest apps/mouth/** or shared-input
     commit, including e2e under the September 6 follow-up contract.
  2. WHETHER production includes it — `git merge-base --is-ancestor "$SHA" "$live"`.
     Argument ORDER is the whole meaning: reversed, it asserts that production is BEHIND,
     which passes on exactly the outage this guard exists to catch.

Superscar #3 discipline: guilt (it fires on a genuinely stale production) AND innocence
(it stays quiet when production is legitimately AHEAD, and docs-only commits are not
demanded). Plus fail-closed on a sha that is not in history — an unknown commit
is not evidence of health.
"""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "frontend-live-sentinel.yml"
)


def _workflow_text() -> str:
    assert WORKFLOW.exists(), f"workflow missing at {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def _extract_pathspec() -> list[str]:
    """The pathspec the workflow actually uses to pick the expected commit."""
    text = _workflow_text()
    match = re.search(
        r"git log -1 --format=%H -- \\\n(.*?)\)\n",
        text,
        re.DOTALL,
    )
    assert match, "could not find the `git log -1 --format=%H --` pathspec in the workflow"
    raw = match.group(1).replace("\\\n", " ")
    args = [a.strip().strip("'") for a in raw.split() if a.strip() and a.strip() != "\\"]
    assert args, "extracted an empty pathspec — the extraction, not the guard, is broken"
    return args


def _extract_ancestor_args() -> tuple[str, str]:
    """The two operands of --is-ancestor, in the order the workflow passes them."""
    text = _workflow_text()
    match = re.search(r'git merge-base --is-ancestor "(\$\w+)" "(\$\w+)"', text)
    assert match, "could not find `git merge-base --is-ancestor` in the workflow"
    return match.group(1), match.group(2)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A synthetic history: a bundle-relevant commit, then an e2e-only one on top."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")

    def commit(rel: str, message: str) -> str:
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(message, encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", message)
        return _git(r, "rev-parse", "HEAD")

    commit("README.md", "base")
    relevant = commit("apps/mouth/app/page.tsx", "ships to the browser")
    e2e_only = commit("apps/mouth/e2e/smoke.spec.ts", "runs in CI only")
    unrelated = commit("docs/notes.md", "no bundle impact")

    (r / ".shas").write_text(f"{relevant}\n{e2e_only}\n{unrelated}\n", encoding="utf-8")
    return r


def _expected_commit(repo: Path) -> str:
    return _git(repo, "log", "-1", "--format=%H", "--", *_extract_pathspec())


def _includes(repo: Path, expected: str, served: str) -> bool:
    """Exactly what the workflow asks git, operands in the workflow's own order."""
    first, second = _extract_ancestor_args()
    assert (first, second) == ("$SHA", "$live"), (
        f"--is-ancestor operand order changed: got ({first}, {second}). "
        "Reversed, the guard asserts production is BEHIND and passes on the real outage."
    )
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", expected, served]
        ).returncode
        == 0
    )


def test_pathspec_includes_all_mouth_changes() -> None:
    args = _extract_pathspec()
    assert not any("exclude" in path for path in args)
    assert "apps/mouth" in args, f"apps/mouth dropped from the pathspec: {args}"


def test_expected_commit_is_the_last_mouth_commit_not_docs(repo: Path) -> None:
    relevant, e2e_only, unrelated = (repo / ".shas").read_text().split()
    expected = _expected_commit(repo)
    assert expected == e2e_only
    assert expected not in (relevant, unrelated)


def test_guilt_production_behind_the_relevant_commit_is_flagged(repo: Path) -> None:
    """GUILT: production on the pre-change commit does NOT include it — the real outage."""
    relevant, _e2e, _docs = (repo / ".shas").read_text().split()
    before = _git(repo, "rev-parse", f"{relevant}~1")
    assert _includes(repo, relevant, before) is False


def test_innocence_production_ahead_still_passes(repo: Path) -> None:
    """INNOCENCE: production carrying a LATER commit includes the expected one.

    This is the case equality got wrong: a deploy that happened to ship a newer sha was
    reported stale purely because the strings differed.
    """
    relevant, e2e_only, unrelated = (repo / ".shas").read_text().split()
    assert _includes(repo, relevant, relevant) is True
    assert _includes(repo, relevant, e2e_only) is True
    assert _includes(repo, relevant, unrelated) is True


def test_fail_closed_on_a_commit_absent_from_history(repo: Path) -> None:
    """A served sha git has never seen is unknown, and unknown is not healthy."""
    relevant, _e2e, _docs = (repo / ".shas").read_text().split()
    assert _includes(repo, relevant, "0" * 40) is False


def test_schedule_trigger_is_present() -> None:
    """The 2026-07-28 hole: with only a push trigger, a silence produces no run at all.

    Production sat 6 hours and 8 commits stale overnight and this workflow never ran.
    """
    text = _workflow_text()
    assert re.search(r"^\s+schedule:", text, re.MULTILINE), (
        "the schedule trigger is gone — the sentinel can only speak when someone pushes "
        "frontend code, which is exactly not the failure it guards"
    )
    assert re.search(r'cron:\s*"\*/\d+ \* \* \* \*"', text), "no recurring cron expression found"


@pytest.mark.parametrize("kita_current", [True, False])
def test_probe_follows_kita_when_the_apex_disagrees(
    repo: Path, tmp_path: Path, kita_current: bool
) -> None:
    relevant, _e2e, newest = (repo / ".shas").read_text().split()
    before = _git(repo, "rev-parse", f"{relevant}~1")
    match = re.search(
        r"      - name: Poll [^\n]+\n.*?        run: \|\n"
        r"(?P<shell>(?:          [^\n]*\n|\n)+)",
        _workflow_text(),
        re.DOTALL,
    )
    assert match, "production poll step must be executable by this test"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "curl-calls"
    curl = bin_dir / "curl"
    curl.write_text(
        '#!/bin/bash\n'
        'url="${@: -1}"\n'
        'printf "%s\\n" "$url" >> "$CURL_CALLS"\n'
        'case "$url" in\n'
        '  https://kita.balizero.com/api/health) commit="$KITA_COMMIT" ;;\n'
        '  https://balizero.com/api/health) commit="$APEX_COMMIT" ;;\n'
        '  *) exit 22 ;;\n'
        'esac\n'
        'printf \'{"commit":"%s"}\\n\' "$commit"\n',
        encoding="utf-8",
    )
    curl.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)
    outcome = subprocess.run(
        ["bash", "-e", "-c", textwrap.dedent(match.group("shell"))],
        cwd=repo,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "SHA": relevant,
            "ATTEMPTS": "1",
            "CURL_CALLS": str(calls),
            "KITA_COMMIT": newest if kita_current else before,
            "APEX_COMMIT": before if kita_current else newest,
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert calls.read_text().splitlines() == ["https://kita.balizero.com/api/health"]
    assert outcome.returncode == (0 if kita_current else 1), outcome.stdout + outcome.stderr
    if kita_current:
        assert "OK - kita.balizero.com includes this commit." in outcome.stdout
    else:
        assert "kita.balizero.com did not prove inclusion" in outcome.stdout


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
@pytest.mark.parametrize("age_seconds", [0, 1799, 1800, 3600])
def test_grace_window_uses_commit_age(
    repo: Path, tmp_path: Path, event: str, age_seconds: int
) -> None:
    match = re.search(
        r"      - name: Which commit[^\n]+\n.*?        run: \|\n"
        r"(?P<shell>(?:          [^\n]*\n|\n)+)",
        _workflow_text(), re.DOTALL,
    )
    assert match
    bin_dir = tmp_path / "clock-bin"
    bin_dir.mkdir()
    expected = _expected_commit(repo)
    timestamp = int(_git(repo, "show", "-s", "--format=%ct", expected))
    date_command = bin_dir / "date"
    date_command.write_text(f"#!/bin/sh\necho {timestamp + age_seconds}\n")
    date_command.chmod(0o755)
    output_path = tmp_path / "outputs"
    outcome = subprocess.run(
        ["bash", "-e", "-c", textwrap.dedent(match.group("shell"))], cwd=repo,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "EVENT": event, "GITHUB_OUTPUT": str(output_path)},
        capture_output=True, text=True, timeout=10,
    )
    assert outcome.returncode == 0, outcome.stderr
    outputs = dict(line.split("=", 1) for line in output_path.read_text().splitlines())
    assert outputs["sha"] == expected
    assert (outputs["skip"] == "true") == (event == "schedule" and age_seconds < 1800)
    if event != "schedule" and age_seconds < 1800:
        assert age_seconds + (int(outputs["attempts"]) - 1) * 60 >= 1800
    else:
        assert outputs["attempts"] == "3"


def test_sentinel_self_change_runs_on_main() -> None:
    push_paths = _workflow_text().split("  schedule:", 1)[0]
    assert '".github/workflows/frontend-live-sentinel.yml"' in push_paths
    assert "ref: main" in _workflow_text()
    assert "timeout-minutes: 45" in _workflow_text()
