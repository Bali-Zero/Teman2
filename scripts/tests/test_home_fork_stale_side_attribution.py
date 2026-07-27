"""The HOME-fork guards must say WHICH side is stale, not just that two differ.

TRAUMA (2026-07-27). Both guards compared the live copy against the local
checkout and, on any difference, printed "realign live from repo". On M5 the
main checkout is deliberately 144 commits behind origin/main — pulling it would
race ~45 live worktrees — while both flagged live copies matched origin/main
EXACTLY. The proprioception report opened the session with that P1, and
following its prescription would have overwritten a current
`worktree_isolation.py` hook with a two-day-old one: the guard's own cure
causing the damage the guard exists to prevent, on the very file that keeps
agents off the main checkout.

The defect is not the comparison, it is the REFERENCE: a checkout is a proxy
for "what the repo says" and it lies whenever it trails (superscar #9, W88 —
judge by content against the right reference). origin/main is the fleet's copy.

Guilt + innocence per superscar #3, run against BOTH implementations
(`lint_home_fork.check_pairs` and `proprioception.probe_home_fork_scripts`)
because they are twins that must not drift apart (superscar #9).
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lhf = _load("lint_home_fork")
prop = _load("proprioception")

REL = "scripts/run.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, timeout=30,
    )


@pytest.fixture()
def world(tmp_path: Path):
    """A git repo whose origin/main holds `upstream`, plus a HOME dir.

    Returns a builder: set the working-tree content and the live content
    independently, then ask each guard what it sees.
    """
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")

    def build(upstream: str, checkout: str, live: str):
        (repo / REL).write_text(upstream)
        _git(repo, "add", REL)
        _git(repo, "commit", "-qm", "upstream")
        # Publish that commit as origin/main, then let the working tree drift.
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
        _git(repo, "update-ref", "refs/remotes/origin/main", head)
        (repo / REL).write_text(checkout)
        (home / REL).write_text(live)
        return repo, home

    return build


PAIRS = [{"live": "~/scripts/run.sh", "repo": REL, "machines": ["all"]}]


def _lint(repo: Path, home: Path):
    notices: list[str] = []
    breaches = lhf.check_pairs(PAIRS, repo, home, "mini", notices=notices)
    return breaches, notices


def _prop(repo: Path, home: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("HOME", str(home))
    status, findings, ev = prop.probe_home_fork_scripts(
        repo, {"pairs": [{"live": str(home / REL), "repo": REL}]}, 30
    )
    return status, findings, ev


# ---------------------------------------------------------------- INNOCENCE


def test_innocence_stale_checkout_is_not_a_home_fork(world, monkeypatch) -> None:
    """The M5 shape: live == origin/main, checkout trails. NOT a breach."""
    repo, home = world(upstream="new\n", checkout="old\n", live="new\n")

    breaches, notices = _lint(repo, home)
    assert breaches == [], f"a stale checkout was blamed on the live copy: {breaches}"
    assert len(notices) == 1 and "CHECKOUT-STALE" in notices[0]
    # The remedy must not be the one that would have caused the regression.
    assert "do NOT realign live" in notices[0] or "Do NOT realign live" in notices[0]

    status, findings, ev = _prop(repo, home, monkeypatch)
    assert findings == 0 and status == prop.RECONCILED
    assert any("CHECKOUT-STALE" in line for line in ev)


# ---------------------------------------------------------------- GUILT


def test_guilt_real_home_fork_still_bites(world, monkeypatch) -> None:
    """The disease the guards exist for: the LIVE copy is the stale one."""
    repo, home = world(upstream="new\n", checkout="new\n", live="old\n")

    breaches, notices = _lint(repo, home)
    assert len(breaches) == 1 and "DIVERGED" in breaches[0]
    assert "LIVE copy is the stale side" in breaches[0]
    assert notices == []

    status, findings, ev = _prop(repo, home, monkeypatch)
    assert findings == 1 and status == prop.DIVERGED
    assert any("DIVERGED" in line and "LIVE copy is stale" in line for line in ev)


def test_guilt_both_sides_moved_is_still_a_breach(world, monkeypatch) -> None:
    """Neither side matches the fleet: unattributable, so it must stay loud."""
    repo, home = world(upstream="base\n", checkout="one\n", live="other\n")

    breaches, notices = _lint(repo, home)
    assert len(breaches) == 1 and "BOTH sides differ" in breaches[0]
    assert notices == []

    status, findings, _ = _prop(repo, home, monkeypatch)
    assert findings == 1 and status == prop.DIVERGED


def test_guilt_no_origin_ref_falls_back_to_loud(tmp_path: Path, monkeypatch) -> None:
    """No git / no origin/main: never silently clean — 'could not attribute'
    is not 'nothing wrong' (W84)."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (home / "scripts").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    (repo / REL).write_text("a\n")
    (home / REL).write_text("b\n")

    breaches, notices = _lint(repo, home)
    assert len(breaches) == 1 and "unattributable" in breaches[0]
    assert notices == []

    status, findings, _ = _prop(repo, home, monkeypatch)
    assert findings == 1 and status == prop.DIVERGED


@pytest.mark.parametrize("fake_stdout", ["text not bytes", b"", None])
def test_the_attribution_probe_never_raises_on_odd_stdout(
    tmp_path: Path, monkeypatch, fake_stdout
) -> None:
    """The probe must DEGRADE, never explode.

    First draft assumed `subprocess.run(capture_output=True)` hands back bytes
    and called `hashlib.sha256(stdout)` on it directly. A caller running under a
    `text=True` double returned a str, and the TypeError that raised was caught
    by none of the `except` clauses — a guard that dies where it promised to
    degrade. Pinned for both twins, over every stdout shape a wrapper can hand back.
    """
    class _Fake:
        returncode = 0
        stdout = fake_stdout

    monkeypatch.setattr(lhf.subprocess, "run", lambda *a, **k: _Fake())
    monkeypatch.setattr(prop.subprocess, "run", lambda *a, **k: _Fake())

    # Not "it didn't raise" — the contract is a hex digest or None, nothing else.
    for got in (lhf.origin_main_sha(tmp_path, REL), prop.origin_main_sha(tmp_path, REL)):
        assert got is None or (len(got) == 64 and int(got, 16) >= 0)
    behind = lhf.commits_behind_origin(tmp_path)
    assert behind is None or isinstance(behind, int)


def test_guilt_no_notices_sink_keeps_the_finding(world) -> None:
    """A caller that passes no sink must not lose the CHECKOUT-STALE signal —
    it degrades to a breach naming the right side, never to silence."""
    repo, home = world(upstream="new\n", checkout="old\n", live="new\n")
    breaches = lhf.check_pairs(PAIRS, repo, home, "mini")  # no notices=
    assert len(breaches) == 1
    assert "CHECKOUT is the stale side" in breaches[0]
