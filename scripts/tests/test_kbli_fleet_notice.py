"""Guilt AND innocence for scripts/lib/kbli_fleet_notice.sh.

The defect this pins (2026-08-02): the notice compared ONE file — the app repo's
`Resources/` copy — and on that basis printed "already matches canonical". But
`build.sh` refreshes `Resources/` from canonical on every build, so between a build
and a deploy `Resources/` agrees while every installed `.app` is still stale. The
fleet sat 20 codes behind for eight days under that reassurance, each of the 20
promising MORE foreign ownership than the truth (25200 arms, 30400 military
vehicles, 51101/51102 airlines at 100% vs 49%, 79122 Umrah/Hajj at 100% vs 0%).

`test_resources_fresh_but_bundle_stale_still_warns` is that exact world. To confirm
these tests can fail, delete the `app_bundle` branch from the function: that one test
must go red while the innocence tests stay green.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "lib" / "kbli_fleet_notice.sh"
WARNING = "NOT aligned"
REASSURANCE = "both match canonical"


def run_notice(canonical: Path, app_repo: Path, bundle_dir: Path) -> subprocess.CompletedProcess:
    """Invoke the function in a fake world and return the completed process."""
    script = (
        f'set -euo pipefail\n. "{LIB}"\n'
        f'kbli_fleet_notice "{canonical}" "{app_repo}" "{bundle_dir}" testhost\n'
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=30, cwd=REPO
    )


@pytest.fixture
def world(tmp_path: Path):
    """A canonical file, an app repo and an installed bundle — all initially aligned."""
    canonical = tmp_path / "canonical.json"
    canonical.write_text('{"kbli": "TRUTH"}', encoding="utf-8")

    app_repo = tmp_path / "kbli-navigator-app"
    (app_repo / "Resources").mkdir(parents=True)
    (app_repo / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
        canonical.read_text(encoding="utf-8"), encoding="utf-8"
    )

    bundle_dir = tmp_path / "KBLI Navigator.app"
    (bundle_dir / "Contents" / "Resources").mkdir(parents=True)
    (bundle_dir / "Contents" / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
        canonical.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return canonical, app_repo, bundle_dir


def test_the_library_exists_and_is_sourceable() -> None:
    """A probe must be shown able to produce a positive before its negatives mean anything."""
    assert LIB.is_file(), f"{LIB} missing — every other test here would pass vacuously"
    out = subprocess.run(
        ["bash", "-c", f'. "{LIB}"; type kbli_fleet_notice'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    assert "function" in out.stdout


# ── innocence ──────────────────────────────────────────────────────────────────────


def test_fully_aligned_fleet_is_not_accused(world) -> None:
    canonical, app_repo, bundle_dir = world
    res = run_notice(canonical, app_repo, bundle_dir)
    assert res.returncode == 0, res.stderr
    assert WARNING not in res.stdout, res.stdout
    assert REASSURANCE in res.stdout, res.stdout


def test_absent_app_repo_says_nothing_at_all(world, tmp_path: Path) -> None:
    """Pro, Mini and CI have no app repo — there is no local copy there to be stale."""
    canonical, _, bundle_dir = world
    res = run_notice(canonical, tmp_path / "does-not-exist", bundle_dir)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "", res.stdout


# ── guilt ──────────────────────────────────────────────────────────────────────────


def test_resources_fresh_but_bundle_stale_still_warns(world) -> None:
    """THE regression: the state the old one-file check called 'already matches'."""
    canonical, app_repo, bundle_dir = world
    (bundle_dir / "Contents" / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
        '{"kbli": "STALE — arms manufacturing 100% open"}', encoding="utf-8"
    )
    res = run_notice(canonical, app_repo, bundle_dir)
    assert res.returncode == 0, res.stderr
    assert WARNING in res.stdout, res.stdout
    assert REASSURANCE not in res.stdout, res.stdout
    assert ".app installed on testhost" in res.stdout, res.stdout


def test_stale_resources_is_named(world) -> None:
    canonical, app_repo, bundle_dir = world
    (app_repo / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
        '{"kbli": "STALE"}', encoding="utf-8"
    )
    res = run_notice(canonical, app_repo, bundle_dir)
    assert WARNING in res.stdout, res.stdout
    assert "Resources/" in res.stdout, res.stdout


def test_missing_bundle_is_not_alignment(world, tmp_path: Path) -> None:
    """W84: absence must never read as health."""
    canonical, app_repo, _ = world
    res = run_notice(canonical, app_repo, tmp_path / "no-such.app")
    assert WARNING in res.stdout, res.stdout
    assert REASSURANCE not in res.stdout, res.stdout
    assert "no .app" in res.stdout, res.stdout


# ── contract ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("break_bundle", [True, False])
def test_never_exits_non_zero(world, break_bundle: bool) -> None:
    """The kbli_filiera cure compilers call the sync script unconditionally under errexit.

    A deploy reminder must never abort a data cure.
    """
    canonical, app_repo, bundle_dir = world
    if break_bundle:
        (bundle_dir / "Contents" / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
            "stale", encoding="utf-8"
        )
    assert run_notice(canonical, app_repo, bundle_dir).returncode == 0


@pytest.mark.parametrize("break_bundle", [True, False])
def test_both_branches_disclaim_what_they_cannot_see(world, break_bundle: bool) -> None:
    """No ssh happens here, so neither verdict may imply Pro/Mini or the team zip."""
    canonical, app_repo, bundle_dir = world
    if break_bundle:
        (bundle_dir / "Contents" / "Resources" / "KBLI_2025_FINAL_CLEAN.json").write_text(
            "stale", encoding="utf-8"
        )
    res = run_notice(canonical, app_repo, bundle_dir)
    assert "only check-fleet.sh speaks for them" in res.stdout, res.stdout


def test_sync_script_sources_the_library_without_the_or_true_trap() -> None:
    """W108: `source <missing> || true` under `set -e` EXITS — the `||` never runs."""
    body = (REPO / "scripts" / "sync_kbli_dataset.sh").read_text(encoding="utf-8")
    assert "kbli_fleet_notice" in body, "the sync script no longer calls the notice at all"
    assert "|| true" not in body.split("FLEET_NOTICE=")[-1], (
        "the fleet-notice source must be guarded by [ -f ], never by `|| true`"
    )
