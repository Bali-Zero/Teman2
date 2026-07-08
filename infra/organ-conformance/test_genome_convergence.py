"""Guilt AND innocence tests for the CONVERGENCE v2 machinery
(picker eligibility, deterministic graft + dry-fire, baseline ratchet).

Run: python3 -m pytest infra/organ-conformance/test_genome_convergence.py -q
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ratchet = _load("check_baseline_ratchet", HERE / "check_baseline_ratchet.py")
retrofit = _load("genome_retrofit", REPO_ROOT / "scripts/genome_retrofit.py")
convergence = _load("genome_convergence", REPO_ROOT / "scripts/genome_convergence.py")


# ------------------------------------------------------------------ ratchet
def test_ratchet_innocence_shrink_and_equal_pass():
    base = {"a.plist": ["G2_heartbeat", "G5_kill_switch"], "b.plist": ["G9_fail_visible"]}
    assert ratchet.compare(base, base) == []
    assert ratchet.compare(base, {"a.plist": ["G2_heartbeat"]}) == []  # shrink + drop
    assert ratchet.compare(base, {}) == []  # full convergence


def test_ratchet_guilt_growth_fails():
    base = {"a.plist": ["G2_heartbeat"]}
    v = ratchet.compare(base, {"a.plist": ["G2_heartbeat", "G5_kill_switch"]})
    assert len(v) == 1 and "grew" in v[0]


def test_ratchet_guilt_new_grandfathered_entry_fails():
    v = ratchet.compare({}, {"new.plist": ["G2_heartbeat"]})
    assert len(v) == 1 and "born conformant" in v[0]


# ------------------------------------------------------------------- graft
FIXTURE_WRAPPER = """#!/bin/bash
# fixture organ wrapper — pre-genome era
# does one unit of work and exits

echo "payload work"
exit 0
"""


def test_graft_innocence_full_set_then_dry_fire(tmp_path):
    new_text, grafted, refused = retrofit.graft(
        FIXTURE_WRAPPER, "mini.fixture_organ",
        ["G2_heartbeat", "G5_kill_switch", "G9_fail_visible", "G10_single_instance"],
        node=None,
    )
    assert set(grafted) == {"G2_heartbeat", "G5_kill_switch",
                            "G9_fail_visible", "G10_single_instance"}, refused
    assert refused == []
    w = tmp_path / "w.sh"
    w.write_text(new_text, encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(w)]).returncode == 0
    ok, why = retrofit.dry_fire(w, "mini.fixture_organ")
    assert ok, why


def test_graft_guilt_no_shebang_refused():
    _, grafted, refused = retrofit.graft(
        "echo naked script\n", "mini.x", ["G2_heartbeat"], None)
    assert grafted == [] and any("shebang" in r for r in refused)


def test_graft_guilt_existing_exit_trap_refuses_heartbeat():
    text = "#!/bin/bash\ntrap 'cleanup' EXIT\necho hi\n"
    _, grafted, refused = retrofit.graft(
        text, "mini.x", ["G2_heartbeat", "G5_kill_switch"], None)
    assert "G2_heartbeat" not in grafted
    assert any("EXIT trap" in r for r in refused)


def test_graft_guilt_dependent_genes_refused_without_heartbeat():
    # G5 requested alone on a wrapper using a LIBRARY heartbeat writer:
    # no local heartbeat() -> visible-disabled invariant -> refuse, never mute
    text = ("#!/bin/bash\nsource ~/lib/heartbeat.sh\n"
            "organism_heartbeat x ok\necho work\n")
    _, grafted, refused = retrofit.graft(text, "mini.x", ["G5_kill_switch"], None)
    assert grafted == []
    assert any("visible-disabled" in r for r in refused)


def test_graft_idempotent_second_pass_grafts_nothing(tmp_path):
    new_text, grafted, _ = retrofit.graft(
        FIXTURE_WRAPPER, "mini.fixture_organ",
        ["G2_heartbeat", "G5_kill_switch"], None)
    assert grafted
    # second pass over the ALREADY grafted text: heartbeat() now exists ->
    # G2 conflict-refused; the kill-switch env var is present in text but we
    # re-request it — the graft must not duplicate blocks blindly
    _, grafted2, refused2 = retrofit.graft(
        new_text, "mini.fixture_organ", ["G2_heartbeat"], None)
    assert grafted2 == []
    assert any("already defines heartbeat" in r for r in refused2)


# ------------------------------------------------------------------- picker
def test_picker_schedule_weekly_calendar_ineligible(tmp_path):
    import plistlib
    p = tmp_path / "weekly.plist"
    p.write_bytes(plistlib.dumps({
        "Label": "com.test.weekly",
        "ProgramArguments": ["/bin/bash", "/x.sh"],
        "StartCalendarInterval": {"Weekday": 1, "Hour": 8},
    }))
    ok, why = convergence.schedule_ok(p)
    assert not ok and "weekly/monthly" in why


def test_picker_schedule_hourly_and_daemon_eligible(tmp_path):
    import plistlib
    hourly = tmp_path / "hourly.plist"
    hourly.write_bytes(plistlib.dumps({
        "Label": "com.test.hourly",
        "ProgramArguments": ["/bin/bash", "/x.sh"],
        "StartInterval": 3600,
    }))
    daemon = tmp_path / "daemon.plist"
    daemon.write_bytes(plistlib.dumps({
        "Label": "com.test.daemon",
        "ProgramArguments": ["/bin/bash", "/x.sh"],
        "KeepAlive": True,
    }))
    assert convergence.schedule_ok(hourly)[0]
    assert convergence.schedule_ok(daemon)[0]


def test_picker_forbids_genome_machinery_and_wa_mirror():
    for probe in ("infra/organ-conformance/x.plist", "infra/healer/x.plist",
                  ".github/workflows/x.plist", "apps/wa-mirror/scripts/x.plist"):
        assert any(part in probe for part in convergence.FORBIDDEN_PATH_PARTS), probe


def test_picker_human_gated_genes_never_retrofittable():
    assert "G6_spawn_hardened" not in convergence.RETROFITTABLE
    assert "G8_keepalive_sane" not in convergence.RETROFITTABLE
    assert "G3_declared_pair" not in convergence.RETROFITTABLE


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
