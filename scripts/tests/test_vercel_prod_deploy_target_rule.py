#!/usr/bin/env python3
"""Corpus for the question `vercel_prod_deploy` asks before it does anything:
WHICH commit must production be serving, and does it already?

WHY THIS EXISTS
---------------
Measured 2026-08-10. Production had served a 4h50m-old build across all eight domains while a
READY, never-aliased `target=production` build for the newest frontend commit sat on Vercel.
The Frontend Live Sentinel was correctly red for three consecutive runs. The cure script,
asked for its plan, said:

    main HEAD       : d674ece46e...   (a docs-only commit)
    production runs : 6013a842f5...
    dry-run: no READY build for this commit — would deploy, changing nothing

Every line true, the conclusion wrong. The script targeted `main HEAD`; this repo lands ~40
PRs a day and almost none touch the frontend, so HEAD is nearly always a commit Vercel
deliberately SKIPPED. Against that target, BOTH good outcomes are unreachable: there is never
a READY build for a skipped commit, and production can never equal it. The optimisation that
exists to turn a 6-minute rebuild into a 3-second promote could essentially never fire.

The sentinel had already been taught the right rule on 2026-07-28 — "does production INCLUDE
this commit, not does it EQUAL this sha", against the newest commit touching a path that
reaches the bundle. The alarm knew; the cure did not. So the load-bearing test here is not
either function in isolation, it is that THE TWO FILES CANNOT DRIFT: the path list is read
back out of the workflow YAML and compared to the script's constants.

No network, no Vercel, no `gh`: `_deploy_relevant_head` is exercised against a real throwaway
git repo with a real `origin`, because the thing under test is a `git log` pathspec and a
fixture that mimicked it would only confirm my own idea of it (W114).
"""
from __future__ import annotations

import io
import json
import pathlib
import shlex
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

vpd = pytest.importorskip("vercel_prod_deploy")

WORKFLOW = REPO / ".github" / "workflows" / "frontend-live-sentinel.yml"


def _run(cwd: pathlib.Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _commit(repo: pathlib.Path, relpath: str, body: str) -> str:
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", f"touch {relpath}")
    return _run(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A clone with a real `origin`, whose main carries, in order:

        0. a seed commit              (README)                <- something to be BEHIND
        1. a frontend commit          (apps/mouth/page.tsx)
        2. an e2e-only commit         (apps/mouth/e2e/…)      <- latest mouth change
        3. a docs commit              (docs/…)                <- what HEAD usually is here

    The seed exists because the first draft used `rev-list --max-parents=0` as "an older
    commit" and the root commit WAS the frontend one, so the staleness case compared a sha to
    itself and passed while asserting nothing.

    Returns (clone_path, {label: sha}).
    """
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True,
                   capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)

    shas = {}
    shas["seed"] = _commit(work, "README.md", "# seed\n")
    shas["frontend"] = _commit(work, "apps/mouth/page.tsx", "export default () => null\n")
    shas["e2e"] = _commit(work, "apps/mouth/e2e/spec.ts", "test('x', () => {})\n")
    shas["docs"] = _commit(work, "docs/ledger.md", "# ledger\n")
    _run(work, "remote", "add", "origin", str(origin))
    _run(work, "push", "-q", "origin", "main")
    _run(work, "fetch", "-q", "origin", "main")

    monkeypatch.chdir(work)
    return work, shas


# --------------------------------------------------------------------------------------
# The pin: one question, one definition, in two files.
# --------------------------------------------------------------------------------------

def test_the_script_and_the_sentinel_ask_about_the_same_paths():
    """If this fails, someone changed which paths reach the bundle in ONE of the two places.
    Change both, or the alarm and its cure are aimed at different commits."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines) if "git log -1 --format=%H --" in ln), None)
    assert start is not None, (
        f"could not find the sentinel's `git log` in {WORKFLOW} — did its shape change? "
        "This test asserts nothing if it cannot locate the command, so it fails instead."
    )
    # Join the shell line-continuations, then drop the closing paren of the $( … ).
    chunk = lines[start].split("--format=%H --", 1)[1]
    i = start
    while lines[i].rstrip().endswith("\\"):
        i += 1
        chunk += " " + lines[i]
    chunk = chunk.replace("\\", " ").strip()
    assert chunk.endswith(")"), f"unexpected command shape: {chunk!r}"
    declared = shlex.split(chunk[:-1])  # shlex, so ':(exclude)…' survives its quotes intact
    assert declared == list(vpd.BUNDLE_PATHS) + list(vpd.BUNDLE_EXCLUDE), (
        f"sentinel says {declared}, script says "
        f"{list(vpd.BUNDLE_PATHS) + list(vpd.BUNDLE_EXCLUDE)}"
    )


# --------------------------------------------------------------------------------------
# GUILT — the shape that was live on 2026-08-10.
# --------------------------------------------------------------------------------------

def test_a_docs_only_head_does_not_become_the_target(repo):
    """The bug, exactly: HEAD is a docs commit, so the old rule aimed production at a sha
    Vercel skipped and could never build."""
    work, shas = repo
    sha, how = vpd._deploy_relevant_head()
    assert sha == shas["e2e"], "target must be the newest mouth or shared-input commit"
    assert sha != shas["docs"], "targeting main HEAD is the defect this test exists for"
    assert "bundle-relevant" in how


def test_production_on_the_frontend_commit_is_current_even_though_head_moved_on(repo):
    """Production serving the newest frontend commit IS current — the old equality test
    called this stale and would have rebuilt."""
    work, shas = repo
    assert vpd._production_includes(shas["frontend"], shas["frontend"]) is True


def test_production_ahead_of_the_target_is_current(repo):
    """Production may legitimately carry MORE than the target (someone deployed HEAD).
    Ancestry, not equality."""
    work, shas = repo
    assert vpd._production_includes(shas["frontend"], shas["docs"]) is True


# --------------------------------------------------------------------------------------
# INNOCENCE — the new rule must not go quiet on a real staleness, or wander.
# --------------------------------------------------------------------------------------

def test_production_behind_the_target_is_still_reported_stale(repo):
    """The whole point of the alarm. Production on an ancestor of the target is BEHIND."""
    work, shas = repo
    assert shas["seed"] != shas["frontend"], "premise: the two must be different commits"
    assert vpd._production_includes(shas["frontend"], shas["seed"]) is False


def test_an_e2e_only_commit_moves_the_target(repo):
    """The September 6 contract covers all mouth paths, matching Vercel's build trigger."""
    work, shas = repo
    newer = _commit(work, "apps/mouth/e2e/another.spec.ts", "test('y', () => {})\n")
    _run(work, "push", "-q", "origin", "main")
    sha, _how = vpd._deploy_relevant_head()
    assert sha == newer


def test_a_later_frontend_commit_does_move_the_target(repo):
    """Innocence's mirror: the selector must not be inert. A real frontend change moves it."""
    work, shas = repo
    newer = _commit(work, "apps/mouth/app/layout.tsx", "export default () => null\n")
    _run(work, "push", "-q", "origin", "main")
    sha, _how = vpd._deploy_relevant_head()
    assert sha == newer


def test_an_unprobeable_production_is_never_read_as_current(repo):
    """A failed probe returns None. None is 'I could not look', not 'it is fine'."""
    work, shas = repo
    assert vpd._production_includes(shas["frontend"], None) is False


def test_a_served_sha_absent_from_history_fails_closed(repo):
    """`merge-base --is-ancestor` exits 128 on an object we do not have. Only exit 0 is
    currency — 128 must not be mistaken for one."""
    work, shas = repo
    assert vpd._production_includes(shas["frontend"], "0" * 40) is False


def test_git_failure_degrades_to_main_head_and_says_so(repo, monkeypatch):
    """Being unable to look is not evidence that no frontend commit exists. Fall back to the
    old behaviour, and NAME the degradation — a silent fallback is how the next reader is
    told a wrong thing confidently (W106)."""
    work, _shas = repo
    monkeypatch.setattr(vpd, "_git", lambda *a: None)
    monkeypatch.setattr(vpd, "_main_head", lambda: "d" * 40)
    sha, how = vpd._deploy_relevant_head()
    assert sha == "d" * 40
    assert "could not filter by path" in how


def test_git_returning_empty_output_is_not_treated_as_failure(repo, monkeypatch):
    """`git fetch` succeeds with empty stdout. If `_git` conflated '' with None, every run
    would degrade to main HEAD while reporting success — the defect wearing the fix's face."""
    work, shas = repo
    assert vpd._git("fetch", "--no-tags", "--quiet", "origin", "main") == ""
    sha, how = vpd._deploy_relevant_head()
    assert sha == shas["e2e"] and "bundle-relevant" in how


@pytest.mark.parametrize("kita_current", [True, False])
def test_served_commit_observes_kita_when_the_apex_disagrees(
    repo: tuple[pathlib.Path, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    kita_current: bool,
) -> None:
    _work, shas = repo
    kita_commit = shas["docs"] if kita_current else shas["seed"]
    apex_commit = shas["seed"] if kita_current else shas["docs"]
    calls: list[str] = []

    def urlopen(url: str, timeout: int) -> io.BytesIO:
        calls.append(url)
        assert timeout == 25
        commits = {
            "https://kita.balizero.com/api/health": kita_commit,
            "https://balizero.com/api/health": apex_commit,
        }
        return io.BytesIO(json.dumps({"commit": commits[url]}).encode())

    monkeypatch.setattr(vpd.urllib.request, "urlopen", urlopen)
    served = vpd._served_commit()
    assert calls == ["https://kita.balizero.com/api/health"]
    assert served == kita_commit
    assert vpd._production_includes(shas["frontend"], served) is kita_current
