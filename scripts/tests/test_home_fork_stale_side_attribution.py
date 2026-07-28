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
import json
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


# ===========================================================================
# The MISSING HALF of the same cure: the reference itself can be stale.
#
# W106b cured "which side is stale?" by asking origin/main. But origin/main is
# resolved out of the LOCAL object store, so the fleet's copy can be exactly as
# stale as the checkout it was brought in to arbitrate — and then the direction
# test can name the CURRENT side as the stale one and prescribe overwriting it.
# The trauma one layer down, with the cure's own mechanism as the vector.
#
# This was not a hypothetical gap, it was an ASYMMETRY, which is why it survived:
# the twin (`proprioception.probe_home_fork_scripts`) fetches before comparing
# and has since the cure landed; `lint_home_fork` never did. W106b's own text
# calls them "gemelli con la stessa logica" while only one of them refreshed the
# reference. A fix that covers only the surface that bit you is half a fix.
#
# Where the two twins DO differ, deliberately: the twin is a signaler (its
# product is a report a human reads, so a failed fetch is a line of evidence),
# while this lint's product is an EXIT CODE a healer acts on — so it must encode
# CANNOT-VERIFY in that exit code (bit 4), never fold it into drift (bit 1).
# Same information, the channel each consumer actually reads.
# ===========================================================================


def _config(tmp_path: Path) -> Path:
    cfg = tmp_path / "pairs.json"
    cfg.write_text(
        json.dumps({"pairs": [{"live": "~/scripts/run.sh", "repo": REL}], "allow": []}),
        encoding="utf-8",
    )
    return cfg


def _unfetchable_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A real git repo whose `origin` is a path that does not exist.

    The fetch then fails deterministically, with no network and no waiting —
    the same class of failure as an offline machine or a refused credential.
    """
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / REL).write_text("same\n")
    _git(repo, "add", REL)
    _git(repo, "commit", "-qm", "init")
    _git(repo, "remote", "add", "origin", str(tmp_path / "nowhere.git"))
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / REL).write_text("same\n")  # identical: any finding here is the fetch
    return repo, home


def _run_check(repo: Path, home: Path, cfg: Path, *extra: str) -> tuple[int, dict]:
    """--check only (no --discover, so no crontab to fake), JSON verdict."""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = lhf.main([
            "--check", "--json", "--config", str(cfg),
            "--home", str(home), "--repo-root", str(repo), *extra,
        ])
    return rc, json.loads(buf.getvalue())


def test_guilt_failed_fetch_is_cannot_verify_not_clean(tmp_path: Path) -> None:
    """A fetch that fails must show up as a scan error (bit 4), never as clean."""
    repo, home = _unfetchable_repo(tmp_path)

    # Vacuous-guilt guard: prove the fixture really cannot fetch. Without this
    # the assertions below would pass just as happily against a repo that
    # fetched fine and had nothing to report.
    ok, detail = lhf.fetch_origin_main(repo, timeout=10)
    assert ok is False, f"fixture fetched successfully ({detail}) — test is vacuous"

    rc, verdict = _run_check(repo, home, _config(tmp_path))

    assert rc & 4, f"CANNOT-VERIFY did not reach the exit code (rc={rc})"
    assert not rc & 1, "a failed fetch was reported as DRIFT — a healer would act on it"
    assert len(verdict["errors"]) == 1
    assert "CANNOT-VERIFY" in verdict["errors"][0]
    assert verdict["check_breaches"] == []


def test_innocence_no_fetch_flag_does_not_manufacture_an_error(tmp_path: Path) -> None:
    """Offline runs opt out explicitly and stay quiet — Law 6: a disconnected
    machine is a natural state. The escape hatch must not itself be a finding."""
    repo, home = _unfetchable_repo(tmp_path)

    rc, verdict = _run_check(repo, home, _config(tmp_path), "--no-fetch")

    assert verdict["errors"] == [], f"--no-fetch still reported: {verdict['errors']}"
    assert not rc & 4
    assert verdict["check_breaches"] == []


def test_innocence_a_reachable_origin_reports_nothing(tmp_path: Path) -> None:
    """The everyday path: origin resolves, the fetch succeeds, no noise."""
    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(upstream)],
        check=True, capture_output=True, timeout=30,
    )
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / REL).write_text("same\n")
    _git(repo, "add", REL)
    _git(repo, "commit", "-qm", "init")
    _git(repo, "remote", "add", "origin", str(upstream))
    _git(repo, "push", "-q", "origin", "main")
    home = tmp_path / "home"
    (home / "scripts").mkdir(parents=True)
    (home / REL).write_text("same\n")

    ok, detail = lhf.fetch_origin_main(repo, timeout=10)
    assert ok is True, f"fixture could not fetch from a real local remote: {detail}"

    rc, verdict = _run_check(repo, home, _config(tmp_path))
    assert verdict["errors"] == []
    assert verdict["check_breaches"] == []
    assert rc == 0


def test_the_twins_do_not_drift_apart_on_refreshing_the_reference() -> None:
    """Pin the asymmetry that let this half stay missing.

    Both guards decide WHICH side is stale by consulting origin/main, so both
    must refresh it and both must expose the same offline escape. Asserting the
    behaviour of only the twin that bit you is how the next half goes missing.
    """
    for mod in (lhf, prop):
        assert hasattr(mod, "origin_main_sha"), f"{mod.__name__} lost the reference probe"
    assert callable(lhf.fetch_origin_main), "the lint no longer refreshes the reference"

    lint_flags = lhf.main.__doc__ or ""  # not the contract; read argparse instead
    del lint_flags
    import argparse

    parser_flags: set[str] = set()
    real_init = argparse.ArgumentParser.add_argument

    def _spy(self, *args, **kwargs):  # noqa: ANN001,ANN002,ANN003
        for a in args:
            if isinstance(a, str) and a.startswith("--"):
                parser_flags.add(a)
        return real_init(self, *args, **kwargs)

    argparse.ArgumentParser.add_argument = _spy  # type: ignore[method-assign]
    try:
        with pytest.raises(SystemExit):
            lhf.main(["--help"])
    finally:
        argparse.ArgumentParser.add_argument = real_init  # type: ignore[method-assign]
    assert "--no-fetch" in parser_flags, "the lint lost its offline escape hatch"

    prop_src = (_SCRIPTS / "proprioception.py").read_text(encoding="utf-8")
    assert "no_fetch" in prop_src, "the twin lost its offline escape hatch"
    assert "fetch" in prop_src, "the twin no longer refreshes the reference"


def test_guilt_a_live_copy_with_no_repo_twin_is_still_named(world) -> None:
    """A live payload with nothing in the repo is a breach in its own right —
    it has no source of truth at all, which the direction logic must not
    swallow while it is busy deciding which of two sides moved."""
    repo, home = world(upstream="x\n", checkout="x\n", live="x\n")
    (home / "scripts" / "orphan.sh").write_text("live only\n")

    notices: list[str] = []
    breaches = lhf.check_pairs(
        [{"live": "~/scripts/orphan.sh", "repo": "scripts/orphan.sh", "machines": ["all"]}],
        repo, home, "mini", notices=notices,
    )
    assert len(breaches) == 1 and "NO-REPO-TWIN" in breaches[0]
    assert notices == []


def test_known_gap_both_sides_equally_behind_reads_clean(world) -> None:
    """CHARACTERIZATION of a gap that is REAL and deliberately NOT cured here.

    `check_pairs` compares live↔checkout FIRST and short-circuits when they
    match, so it never asks origin/main about the one case where both sides
    agree and both trail the fleet: a fix landed on main that NEITHER the
    checkout NOR the live copy has. The live payload is then genuinely running
    stale code and this guard reports clean.

    Curing it means changing the comparison base from the checkout to
    origin/main for every pair, which on M5 — a checkout deliberately ~144
    commits behind — turns every matching pair into a finding. That is a
    fleet-wide behavioural change owed its own measurement on all three
    machines, not a rider on this diff. Ledgered in PENDING-ARMS.

    This test asserts TODAY'S behaviour on purpose: whoever cures the gap will
    see it fail and must delete it deliberately, which is the point. It is not
    a blessing of the gap — it is the gap, pinned where it cannot be forgotten.
    """
    repo, home = world(upstream="fleet\n", checkout="behind\n", live="behind\n")

    notices: list[str] = []
    breaches = lhf.check_pairs(PAIRS, repo, home, "mini", notices=notices)

    assert breaches == [] and notices == []
    # And the evidence that this IS a gap, not a non-issue: the fleet's copy
    # differs from what is actually executing.
    assert lhf.origin_main_sha(repo, REL) != lhf.sha256_file(home / REL)
