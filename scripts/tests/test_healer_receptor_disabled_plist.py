"""A `.disabled-*`-renamed plist must read as 'disabled', not 'dead' (superscar #2).

Found 2026-09-27 (healer tick, Mini): `mata_garuda.intel_bridge_daily.mini` was
deliberately unloaded on 2026-09-25 by renaming its plist to
`com.matagaruda.intel-bridge.daily.plist.disabled-20260925-owner-pro`. Its heartbeat
sidecar keeps its last (healthy) status forever because the job never runs again to
refresh it — so age-based classification alone calls it 'dead' on every subsequent
tick, permanently. Observed unfixed across 3 consecutive healer ticks
(2026-09-25/26/27) before this fix, each time re-diagnosed by hand and left as an
open observation ("would need a second confirmed case before generalizing a fix").
"""

import importlib.util
import json
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "healer_receptor_registry.py"
_spec = importlib.util.spec_from_file_location("healer_receptor_registry", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["healer_receptor_registry"] = _mod
_spec.loader.exec_module(_mod)

run = _mod.run

REGISTRY_YAML = textwrap.dedent(
    """\
    organs:
      - id: test.organ
        runtime: mini_launchd
        expected_hb_seconds: 100
        enabled: true
        recovery_action: launchctl_kickstart
        recovery_params:
          host: mini
          label: com.test.organ
    """
)


def _write_registry(tmp_path: Path) -> Path:
    p = tmp_path / "organs_registry.yaml"
    p.write_text(REGISTRY_YAML, encoding="utf-8")
    return p


def _write_sidecar(sidecar_dir: Path, oid: str, status: str, age_s: float) -> None:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    payload = {"organ": oid, "status": status, "note": "", "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}
    (sidecar_dir / f"{oid}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_guilt_renamed_away_plist_is_disabled_not_dead(tmp_path):
    # the exact bug: a plist renamed to `.disabled-*` leaves a permanently-stale
    # (but status='ok') sidecar behind — must read as disabled, not dead.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()
    (agents_dir / "com.test.organ.plist.disabled-20260925-owner-pro").write_text("", encoding="utf-8")

    report = run("mini", registry, sidecar_dir, launchagents_dir=agents_dir)

    assert report["dead"] == []
    assert report["stale"] == []
    assert "test.organ" in report["disabled"]


def test_innocence_plain_plist_still_present_stays_dead(tmp_path):
    # a genuinely dead organ (plist still installed, undecorated) must not be
    # swallowed just because some unrelated `.disabled-*` sibling exists.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()
    (agents_dir / "com.test.organ.plist").write_text("", encoding="utf-8")
    (agents_dir / "com.test.organ.plist.disabled-20260101-owner-someone-else").write_text(
        "", encoding="utf-8"
    )

    report = run("mini", registry, sidecar_dir, launchagents_dir=agents_dir)

    assert report["disabled"] == []
    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"


def test_innocence_no_disabled_sibling_stays_dead(tmp_path):
    # no plist at all (neither plain nor `.disabled-*`) must not be misread as
    # an intentional disable — this is the ordinary already-covered dead case.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()

    report = run("mini", registry, sidecar_dir, launchagents_dir=agents_dir)

    assert report["disabled"] == []
    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"
