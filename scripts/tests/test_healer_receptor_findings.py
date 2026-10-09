"""A fresh detector that completed and reported findings is alive, not dead.

Every row is a live producer shape (or its crash / cannot-verify twin) read at
the producer's own heartbeat write; a guilt row lands in `findings`, its
innocence twin stays `dead`.
"""

import importlib.util
import json
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[1] / "healer_receptor_registry.py"
_MOD_PATH = Path(os.environ.get("HEALER_REGISTRY_UNDER_TEST", _DEFAULT))
_spec = importlib.util.spec_from_file_location("healer_receptor_findings", _MOD_PATH)
mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)

EXPECTED_HB = 100
FRESH = 3 * EXPECTED_HB - 30
STALE = 3 * EXPECTED_HB + 30
KBLI = "detector_rc=1 result=divergence log=/x/kbli.log"
PULSE = {"pulse_count": 7, "tier": 1, "action": None}

KB, LD, MT, SH, CL, VS, DF = (
    "pro.kbli_surface_conformance", "pro.launchd_liveness", "pro.meta_one_steward",
    "mata_garuda.sentinel_hourly.pro", "cell.organism",
    "pro.visa_freshness_sentinel", "pro.disk_floor",
)
DISK = "free_gb=74.9 on /System/Volumes/Data (ok > 100, failed < 60)"
SENTINEL_RED = "pulse=red action=no_items pulse=42"

# row: (organ id, status, age_s, sidecar extra, expected bucket)
ROWS = {
    "K1-kbli-divergence-guilt": (KB, "error", FRESH, {"note": KBLI}, "findings"),
    "K2-kbli-detector-failure-innocence": (
        KB, "error", FRESH, {"note": "detector_rc=1 result=detector_failure log=/x"}, "dead"),
    "K3-kbli-cannot-verify-innocence": (
        KB, "warning", FRESH, {"note": "detector_rc=4 result=cannot_verify log=/x"}, "dead"),
    "K4-kbli-shape-wrong-status-innocence": (KB, "warning", FRESH, {"note": KBLI}, "dead"),
    "L1-launchd-alarms-guilt": (LD, "degraded", FRESH, {"note": "2 alarm(s)     see /x.log"}, "findings"),
    "L2-launchd-zero-alarms-innocence": (LD, "degraded", FRESH, {"note": "0 alarm(s) see /x"}, "dead"),
    "L3-launchd-unreadable-innocence": (LD, "error", FRESH, {"note": "rc=1 unreadable JSON output"}, "dead"),
    "M1-meta-token-dead-guilt": (MT, "warning", FRESH, {"note": "token=dead"}, "findings"),
    "M2-meta-token-alive-guilt": (MT, "warning", FRESH, {"note": "token=alive"}, "findings"),
    "M3-meta-token-unknown-innocence": (MT, "warning", FRESH, {"note": "token=unknown"}, "dead"),
    "M4-meta-token-suffix-innocence": (MT, "warning", FRESH, {"note": "token=deadline"}, "dead"),
    "M5-meta-crash-text-innocence": (MT, "error", FRESH, {"note": "token=dead"}, "dead"),
    "M6-meta-wrapper-crash-innocence": (MT, "error", FRESH, {"note": "wrapper rc=1"}, "dead"),
    "H1-sentinel-red-pulse-guilt": (
        SH, "warning", FRESH, {"note": SENTINEL_RED}, "findings"),
    "H2-sentinel-red-shape-wrong-status-innocence": (
        SH, "fail", FRESH, {"note": SENTINEL_RED}, "dead"),
    "H3-sentinel-note-without-shape-innocence": (
        SH, "warning", FRESH, {"note": "red pulse completed"}, "dead"),
    "H4-sentinel-shape-not-at-note-start-innocence": (
        SH, "warning", FRESH, {"note": f"see {SENTINEL_RED}"}, "dead"),
    "H5-sentinel-proof-on-another-organ-innocence": (
        VS, "warning", FRESH, {"note": SENTINEL_RED}, "dead"),
    "C1-cell-completed-pulse-guilt": (
        CL, "fail", FRESH, {"metadata": {"pulse_count": 7, "tier": 1, "action": None}}, "findings"),
    "C2-cell-pulse-threw-innocence": (
        CL, "fail", FRESH, {"metadata": {"pulse_count": 7, "error": "TimeoutError"}}, "dead"),
    "C3-cell-no-pulse-count-innocence": (CL, "fail", FRESH, {"metadata": {"tier": 1, "action": None}}, "dead"),
    "C4-cell-null-pulse-count-innocence": (CL, "fail", FRESH, {"metadata": {**PULSE, "pulse_count": None}}, "dead"),
    "C5-cell-bool-pulse-count-innocence": (CL, "fail", FRESH, {"metadata": {**PULSE, "pulse_count": True}}, "dead"),
    "C8-cell-negative-pulse-count-innocence": (CL, "fail", FRESH, {"metadata": {**PULSE, "pulse_count": -1}}, "dead"),
    "C9-cell-extra-key-innocence": (CL, "fail", FRESH, {"metadata": {**PULSE, "error": "X"}}, "dead"),
    "C11-cell-no-metadata-innocence": (CL, "fail", FRESH, {}, "dead"),
    "C10-cell-first-pulse-guilt": (CL, "fail", FRESH, {"metadata": {**PULSE, "pulse_count": 0}}, "findings"),
    "C6-cell-metadata-not-object-innocence": (CL, "fail", FRESH, {"metadata": "pulse_count"}, "dead"),
    "C7-cell-shape-wrong-status-innocence": (CL, "degraded", FRESH, {"metadata": PULSE}, "dead"),
    "V1-visa-rc-is-ambiguous-innocence": (VS, "error", FRESH, {"note": "rc=1"}, "dead"),
    "X1-proof-of-another-organ-innocence": (VS, "error", FRESH, {"note": KBLI}, "dead"),
    "X2-pulse-proof-on-another-organ-innocence": (
        VS, "fail", FRESH, {"metadata": PULSE}, "dead"),
    "P1-prose-is-not-proof-innocence": (
        KB, "error", FRESH, {"note": "detector completed with findings"}, "dead"),
    "P2-shape-not-at-note-start-innocence": (KB, "error", FRESH, {"note": f"see {KBLI}"}, "dead"),
    "D1-disk-warning-guilt": (DF, "warning", FRESH, {"note": f"{DISK}; biggest: ~/.colima 61.0GB"}, "findings"),
    "D2-disk-skipped-run-innocence": (
        DF, "warning", FRESH, {"note": "skipped: previous run alive (pid 123), free space not read"}, "dead"),
    "D3-disk-under-floor-still-pages-innocence": (DF, "error", FRESH, {"note": f"failed: {DISK}"}, "dead"),
    "D4-disk-unreadable-innocence": (
        DF, "error", FRESH, {"note": "free space unreadable: df -Pk /System/Volumes/Data gave no number"}, "dead"),
    "D5-disk-shape-not-at-note-start-innocence": (DF, "warning", FRESH, {"note": f"see {DISK}"}, "dead"),
    # The proof is bound to `warning`: a bare measurement under `error` is not a completed read.
    "D8-disk-measurement-under-error-innocence": (DF, "error", FRESH, {"note": DISK}, "dead"),
    "D6-disk-proof-on-another-organ-innocence": (VS, "warning", FRESH, {"note": DISK}, "dead"),
    "D7-disk-number-missing-innocence": (
        DF, "warning", FRESH, {"note": "free_gb= on /System/Volumes/Data (ok > 100, failed < 60)"}, "dead"),
    "S1-stale-beats-proof": (KB, "error", STALE, {"note": KBLI}, "dead"),
    "S2-healthy-status-stays-ok": (KB, "ok", 10, {"note": KBLI}, "ok"),
}


def _registry(tmp_path: Path, oid: str, runtime: str = "pro_launchd") -> Path:
    path = tmp_path / "organs.yaml"
    path.write_text(textwrap.dedent(f"""\
        organs:
          - id: {oid}
            runtime: {runtime}
            expected_hb_seconds: {EXPECTED_HB}
            enabled: true
            recovery_action: human_only
            severity_on_silence: warning
    """))
    return path


def _sidecars(tmp_path: Path, oid: str, status: str, age_s: int, extra: dict) -> Path:
    sidecars = tmp_path / "sidecars"
    sidecars.mkdir()
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    payload = {"ts": ts.isoformat(), "status": status, **extra}
    (sidecars / f"{oid}.json").write_text(json.dumps(payload))
    return sidecars


def _run(tmp_path: Path, oid: str, status: str, age_s: int, extra: dict, node: str = "pro") -> dict:
    registry = _registry(tmp_path, oid, f"{node}_launchd")
    return mod.run(node, registry, _sidecars(tmp_path, oid, status, age_s, extra))


def _bucket(report: dict) -> str:
    if report.get("findings"):
        return "findings"
    if report["dead"]:
        return "dead"
    return "ok" if report["ok"] else "other"


def test_branch_table(tmp_path):
    got = {}
    for row, (oid, status, age_s, extra, _) in ROWS.items():
        case = tmp_path / row
        case.mkdir()
        got[row] = _bucket(_run(case, oid, status, age_s, extra))
    assert got == {row: spec[4] for row, spec in ROWS.items()}


def test_finding_entry_is_named_not_counted_as_dead(tmp_path):
    report = _run(tmp_path, KB, "error", FRESH, {"note": KBLI})

    assert report["dead"] == [] and report["exit"] == 0
    assert report["dead_session"] == 0 and report["dead_owner"] == 0
    (entry,) = report["findings"]
    assert entry["id"] == KB
    assert entry["state"] == "alive_with_findings"
    assert entry["completion_evidence"] == "note:detector_rc=1 result=divergence"


def test_cell_evidence_is_named(tmp_path):
    report = _run(tmp_path, CL, "fail", FRESH, {"metadata": PULSE})
    assert report["findings"][0]["completion_evidence"] == "metadata.pulse_count"


def test_unhealthy_without_proof_is_dead_and_says_why(tmp_path):
    report = _run(tmp_path, VS, "error", FRESH, {"note": "rc=1"})

    assert report["findings"] == [] and report["exit"] == 1
    assert report["dead"][0]["note"] == "no detector completion evidence: rc=1"
    assert report["dead"][0]["cure"] == "session"


def test_mini_classification_is_unchanged(tmp_path):
    report = _run(tmp_path, KB, "error", FRESH, {"note": KBLI}, node="mini")

    assert report["findings"] == []
    assert [d["id"] for d in report["dead"]] == [KB]
    assert report["dead"][0]["note"] == KBLI
