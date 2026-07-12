"""HEALTHY_STATUSES guilt+innocence (superscar #3): 'running' must not self-report dead.

Found 2026-07-06 (healer tick 2, Mini): `mini.healer`'s own heartbeat sidecar writes
status='running' for the whole duration of an active tick (healer-run.sh:231, up to
MAX_WALL_S=3300s), but HEALTHY_STATUSES lacked 'running' — so the registry classified
the healer as 'dead' every single time it checked itself (or was checked) mid-run,
regardless of freshness. Same disease shape as the parse_ts dialect bug this file's
sibling test guards (test_healer_receptor_parse_ts.py): a too-narrow classifier field
match causing false-dead on a legitimately-alive state.
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


def test_guilt_fresh_running_is_not_dead(tmp_path):
    # the exact bug: a fresh 'running' heartbeat (mid-tick, well under the
    # 3x-expected staleness window) must NOT be classified dead.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="running", age_s=30)

    report = run("mini", registry, sidecar_dir)

    assert report["dead"] == []
    assert "test.organ" in report["ok"]


def test_innocence_bad_status_still_dead(tmp_path):
    # a genuinely unhealthy status must still be caught — 'running' joining
    # HEALTHY_STATUSES must not swallow real failures.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="error", age_s=30)

    report = run("mini", registry, sidecar_dir)

    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"


def test_innocence_stale_running_still_dead(tmp_path):
    # a 'running' status past 3x expected_hb_seconds is a stuck/hung process,
    # not legitimate in-progress work — the age check must still fire.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="running", age_s=500)  # 5x expected(100)

    report = run("mini", registry, sidecar_dir)

    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"
