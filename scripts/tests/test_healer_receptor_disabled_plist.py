"""Registry dead-organ cure classification (superscar #2).

Found 2026-09-27 (healer tick, Mini): `mata_garuda.intel_bridge_daily.mini` was
deliberately unloaded on 2026-09-25 by renaming its plist to
`com.matagaruda.intel-bridge.daily.plist.disabled-20260925-owner-pro`. Its heartbeat
sidecar keeps its last status forever. It must stay visible as dead/escalated while
being marked owner-only, so the healer does not spawn a session that cannot reload it.
"""

import importlib.util
import json
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

_MOD_PATH = Path(os.environ.get(
    "HEALER_REGISTRY_UNDER_TEST",
    Path(__file__).resolve().parents[1] / "healer_receptor_registry.py",
))
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


def _write_registry(
    tmp_path: Path, extra: str = "", runtime: str = "mini_launchd"
) -> Path:
    p = tmp_path / "organs_registry.yaml"
    body = REGISTRY_YAML.replace("mini_launchd", runtime)
    p.write_text(body.replace("    recovery_action:", extra + "    recovery_action:"), encoding="utf-8")
    return p


def _write_sidecar(
    sidecar_dir: Path, oid: str, status: str, age_s: float, note: str = ""
) -> None:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    payload = {"organ": oid, "status": status, "note": note, "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}
    (sidecar_dir / f"{oid}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_pro_renamed_away_unloaded_plist_is_owner_dead(tmp_path):
    registry = _write_registry(tmp_path, runtime="pro_launchd")
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()
    (agents_dir / "com.test.organ.plist.disabled-20260925-owner-pro").write_text("", encoding="utf-8")

    report = run(
        "pro", registry, sidecar_dir, launchagents_dir=agents_dir,
        launchctl_probe=lambda _label: (False, "not loaded"),
    )

    assert report["disabled"] == []
    assert report["dead"][0]["cure"] == "owner"
    assert (report["dead_session"], report["dead_owner"]) == (0, 1)


def test_mini_renamed_away_plist_keeps_existing_disabled_exemption(tmp_path):
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()
    (agents_dir / "com.test.organ.plist.disabled-owner-pro").write_text("")

    report = run("mini", registry, sidecar_dir, launchagents_dir=agents_dir)

    assert report["dead"] == []
    assert report["disabled"] == ["test.organ"]


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

    report = run(
        "mini", registry, sidecar_dir, launchagents_dir=agents_dir,
        launchctl_probe=lambda _label: (False, "not loaded"),
    )

    assert report["disabled"] == []
    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"
    assert report["dead"][0]["cure"] == "session"


def test_innocence_no_disabled_sibling_stays_dead(tmp_path):
    # no plist at all (neither plain nor `.disabled-*`) must not be misread as
    # an intentional disable — this is the ordinary already-covered dead case.
    registry = _write_registry(tmp_path)
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="ok", age_s=1_000_000)
    agents_dir = tmp_path / "LaunchAgents"
    agents_dir.mkdir()

    report = run(
        "mini", registry, sidecar_dir, launchagents_dir=agents_dir,
        launchctl_probe=lambda _label: (False, "not loaded"),
    )

    assert report["disabled"] == []
    assert len(report["dead"]) == 1
    assert report["dead"][0]["id"] == "test.organ"
    assert report["dead"][0]["cure"] == "session"




def _cure_of(tmp_path, *, extra="", status="error", note="", loaded=True,
             evidence="", renamed=False, node="mini"):
    registry = _write_registry(tmp_path, extra, runtime=f"{node}_launchd")
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status=status, age_s=1, note=note)
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(exist_ok=True)
    if renamed:
        (agents_dir / "com.test.organ.plist.disabled-20261007").write_text("")
    report = run(node, registry, sidecar_dir, launchagents_dir=agents_dir,
                 launchctl_probe=lambda _label: (loaded, evidence))
    return report["dead"][0]["cure"]


# Every owner-deciding branch of _dead_cure: a guilt row (owner) and an innocence row (session).
CURE_ROWS = {
    "declared-owner-guilt": ({"extra": "    cure: owner\n"}, "owner"),
    "declared-session-innocence": ({"extra": "    cure: session\n"}, "session"),
    "sidecar-note-tcc-guilt": ({"note": "launch failed: Operation not permitted"}, "owner"),
    "sidecar-note-eacces-innocence": ({"note": "exec: Permission denied"}, "session"),
    "sidecar-note-eperm-innocence": ({"note": "posix_spawn failed: EPERM"}, "session"),
    "sidecar-status-tcc-guilt": ({"status": "OPERATION NOT PERMITTED"}, "owner"),
    "launchctl-exit-tcc-guilt": ({"evidence": "last exit reason = Operation not permitted"}, "owner"),
    "launchctl-exit-plain-innocence": ({"evidence": "last exit code = 1"}, "session"),
    "renamed-unloaded-guilt": ({"loaded": False, "renamed": True, "node": "pro"}, "owner"),
    "renamed-loaded-innocence": ({"loaded": True, "renamed": True, "node": "pro"}, "session"),
    "renamed-unprobeable-innocence": ({"loaded": None, "renamed": True, "node": "pro"}, "session"),
    "owner-note-unloaded-guilt": ({"extra": "    owner_note: GUI consent\n", "loaded": False}, "owner"),
    "owner-note-loaded-innocence": ({"extra": "    owner_note: GUI consent\n", "loaded": True}, "session"),
    "disabled-reason-unloaded-guilt": ({"extra": "    disabled_reason: owner ruling\n", "loaded": False}, "owner"),
    "disabled-reason-unprobeable-innocence": ({"extra": "    disabled_reason: owner ruling\n", "loaded": None}, "session"),
    "unloaded-alone-innocence": ({"loaded": False}, "session"),
}


def test_dead_cure_branch_table(tmp_path):
    got = {}
    for i, (row, (kwargs, _want)) in enumerate(CURE_ROWS.items()):
        case = tmp_path / str(i)
        case.mkdir()
        got[row] = _cure_of(case, **kwargs)
    assert got == {row: want for row, (_kwargs, want) in CURE_ROWS.items()}


def test_undeclared_cure_breaks_the_receptor_visibly(tmp_path, monkeypatch, capsys):
    registry = _write_registry(tmp_path, "    cure: Owner\n")
    sidecar_dir = tmp_path / "sidecars"
    _write_sidecar(sidecar_dir, "test.organ", status="error", age_s=1)
    monkeypatch.setattr(_mod, "_launchctl_print", lambda _label: (True, ""))

    rc = _mod.main(["--node", "mini", "--json", "--registry", str(registry),
                    "--sidecar-dir", str(sidecar_dir)])

    assert rc == 2
    assert "invalid cure 'Owner'" in json.loads(capsys.readouterr().out)["receptor_broken"]


def test_launchctl_print_reads_only_exit_lines_and_maps_return_codes(monkeypatch):
    stdout = "\tenvironment = {\n\t\tX => Operation not permitted\n\t}\n\tlast exit code = 1\n"
    outcomes = {
        "loaded": (0, stdout),
        "not-found": (113, "Could not find service"),
        "other-error": (5, ""),
    }

    def fake_run(argv, **_kw):
        rc, out = outcomes[argv[-1].rsplit("/", 1)[-1]]
        return _mod.subprocess.CompletedProcess(argv, rc, out, "")

    monkeypatch.setattr(_mod.subprocess, "run", fake_run)
    got = {label: _mod._launchctl_print(label) for label in outcomes}

    def timeout(*_a, **_kw):
        raise _mod.subprocess.TimeoutExpired("launchctl", 10)

    monkeypatch.setattr(_mod.subprocess, "run", timeout)
    got["timeout"] = _mod._launchctl_print("loaded")
    got["no-label"] = _mod._launchctl_print("")
    assert got == {
        "loaded": (True, "last exit code = 1"),
        "not-found": (False, ""),
        "other-error": (None, ""),
        "timeout": (None, ""),
        "no-label": (None, ""),
    }
