"""A retirement is a DECLARATION, and it can be declared in the repo (2026-08-09).

TRAUMA. `verify-connectome` — the guardian of the guardians — alarmed at 07:30 on
two consecutive mornings with:

    connectome REGRESSED on Nuzantara
    WARNING REGRESSED com.balizero.wr2.newsletter [launchd/pro] label not loaded

The label is not loaded because it was **retired on purpose** on 2026-07-15,
superseded by a Fly daily task. `plist_intentionally_disabled()` exists precisely
to recognise that, and missed it twice over:

  1. it looked ONLY in `~/Library/LaunchAgents`, where the retirement left no
     declaration — just `…plist.bak-tcc-20260716` from the July TCC move. The
     retirement itself is recorded IN THE REPO, version-controlled, as
     `…plist.disabled-2026-07-15-superseded-by-fly-daily-task`.
  2. its marker list was `disabled` / `superseded` / `endswith(".bak")`, so
     `wa-viewer.plist.retired` and `ollama-warm-pin.plist.archived-from-pro-…`
     were unrecognised too.

Both P0s were dropped `p0_overflow`, so the false alarm was invisible — and the
same measurement proves the channel could not have carried a true one either.

WHAT IS DELIBERATELY NOT FIXED. `bak-*` and `pre-*` are not retirement markers.
A job that was backed up and then LOST is indistinguishable from one backed up
and retired, and treating a backup as a firebreak would mask a genuine silent
death — the one thing this function promises never to do (W94). Measured on Pro
the day this was written: of 205 non-active plist variants, 186 have an active
plist beside them and regress correctly; 19 do not, of which the shipping
predicate recognised 14 and this change takes it to 17. The two that remain
flagged —
`com.balizero.l5-2-phase2b-trigger.plist.bak-tcc-20260716` and
`com.claude-max-api.plist.bak-2026-05-15-pre-anthropic-removal` — carry only a
backup name and no declaration anywhere. That is the correct verdict for the
rule as written; the fix for them is to DECLARE the retirement, not to widen it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "verify_connectome.py"
_spec = importlib.util.spec_from_file_location("verify_connectome", SCRIPT)
vc = importlib.util.module_from_spec(_spec)
# Register BEFORE exec: the script defines @dataclass types, and dataclasses
# resolves annotations through sys.modules[cls.__module__] — absent, it raises
# AttributeError on None at import time.
sys.modules["verify_connectome"] = vc
_spec.loader.exec_module(vc)


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    live = tmp_path / "LaunchAgents"
    repo = tmp_path / "infra" / "launchagents"
    live.mkdir(parents=True)
    repo.mkdir(parents=True)
    monkeypatch.setattr(vc, "LAUNCHAGENTS_DIR", live)
    monkeypatch.setattr(vc, "REPO_LAUNCHAGENTS_DIR", repo)
    return live, repo


# ── guilt: a genuine silent death must NEVER be excused ──────────────────────

def test_an_active_plist_that_is_simply_not_loaded_still_regresses(dirs):
    """The whole point. A live plist present + label unloaded = silent death."""
    live, _ = dirs
    (live / "com.x.job.plist").write_text("<plist/>")
    (live / "com.x.job.plist.disabled-2026-01-01").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_backup_is_not_a_retirement(dirs):
    """`bak-*` with no declaration anywhere: could be a retirement, could be a
    job that was backed up and then lost. Unknown must read as REGRESSED."""
    live, _ = dirs
    (live / "com.x.job.plist.bak-tcc-20260716").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_pre_something_backup_is_not_a_retirement(dirs):
    live, _ = dirs
    (live / "com.x.job.plist.bak-2026-05-15-pre-anthropic-removal").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_repo_template_is_not_a_retirement(dirs):
    """`infra/launchagents/` carries four `*.plist.example` templates alongside
    the one real declaration. Scanning that directory must not turn a template
    into an excuse — a job whose plist was never installed is not a job that was
    deliberately retired."""
    _, repo = dirs
    (repo / "com.x.job.plist.example").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_marker_inside_the_LABEL_does_not_excuse_the_job(dirs):
    """The label is part of the filename. A whole-name test would read
    `com.balizero.retired-feeder.plist.example` as a retirement — the template of a
    job that was never installed, excused by its own name. The assertion lives in
    the SUFFIX, and that is what the predicate must be asked about."""
    _, repo = dirs
    (repo / "com.balizero.retired-feeder.plist.example").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.balizero.retired-feeder") is None


def test_nothing_at_all_regresses(dirs):
    assert vc.plist_intentionally_disabled("com.x.absent") is None


def test_a_non_com_label_is_not_considered(dirs):
    live, _ = dirs
    (live / "org.x.job.plist.retired").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("org.x.job") is None


# ── innocence: a declared retirement must not alarm ──────────────────────────

def test_the_repo_declaration_is_honoured_even_when_the_live_dir_only_has_a_backup(dirs):
    """The exact shape that alarmed twice: live dir has a TCC backup, the repo
    carries the retirement."""
    live, repo = dirs
    (live / "com.balizero.wr2.newsletter.plist.bak-tcc-20260716").write_text("<plist/>")
    (repo / "com.balizero.wr2.newsletter.plist.disabled-2026-07-15-superseded-by-fly-daily-task"
     ).write_text("<plist/>")
    got = vc.plist_intentionally_disabled("com.balizero.wr2.newsletter")
    assert got is not None and "disabled-2026-07-15" in got


@pytest.mark.parametrize("suffix", [
    "plist.retired",
    "plist.archived-from-pro-2026-05-09",
    "plist.disabled-W81-2026-06-15",
    "plist.superseded-by-fly",
    "plist.bak",  # pre-existing contract, kept unchanged by this diff
])
def test_a_declared_retirement_in_the_live_dir_is_honoured(dirs, suffix):
    live, _ = dirs
    (live / f"com.x.job.{suffix}").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") == f"com.x.job.{suffix}"


def test_a_repo_declaration_does_not_excuse_a_label_whose_plist_is_still_active(dirs):
    """Composition, the case a one-sided fix would get wrong: the repo says
    retired, but the live plist is right there and the label is unloaded. That is
    a deploy that half-happened, and it must still regress."""
    live, repo = dirs
    (live / "com.x.job.plist").write_text("<plist/>")
    (repo / "com.x.job.plist.disabled-2026-07-15").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_prefix_neighbour_does_not_excuse_a_different_label(dirs):
    """`com.x.job` and `com.x.job2` share a prefix but are different entities."""
    live, _ = dirs
    (live / "com.x.job2.plist.retired").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") is None


def test_a_missing_live_directory_does_not_crash_and_still_reads_the_repo(dirs, monkeypatch):
    """On a machine with no ~/Library/LaunchAgents the repo declaration must
    still be readable — the old code returned None before looking anywhere."""
    _, repo = dirs
    monkeypatch.setattr(vc, "LAUNCHAGENTS_DIR", Path("/nonexistent/LaunchAgents"))
    (repo / "com.x.job.plist.retired").write_text("<plist/>")
    assert vc.plist_intentionally_disabled("com.x.job") == "com.x.job.plist.retired"
