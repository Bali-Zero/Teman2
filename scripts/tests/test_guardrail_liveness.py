"""Tests for sentinel_lib.guardrail_liveness.

Each test encodes one panel-found defect class, so a regression re-surfaces it.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sentinel_lib import guardrail_liveness as gl  # noqa: E402


# ---- fixtures: settings.json shapes ----------------------------------------


def _settings_with(commands: list[str]) -> dict:
    """Build a minimal settings.json with given hook command strings."""
    return {
        "hooks": {
            "PreToolUse": [
                {"matcher": "*", "hooks": [{"type": "command", "command": c}]}
                for c in commands
            ]
        }
    }


HEALTHY_CMDS = [
    "python3 ~/.claude/hooks/stop_verify.py",
    "~/.claude/hooks/dispatch_nudge.py",
    "~/.claude/hooks/guardrails-client.sh",
]


def _write_settings(tmp_path, obj) -> str:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(obj))
    return str(p)


# ---- Check B core: behavior, not presence ----------------------------------


def test_all_green_no_alert(tmp_path):
    sp = _write_settings(tmp_path, _settings_with(HEALTHY_CMDS))
    rep = gl.run_check(host="X", settings_path=sp)
    assert rep.vector() == {
        "stop_verify": gl.OK,
        "dispatch_nudge": gl.OK,
        "guardrails_destructive_mcp": gl.OK,
    }
    assert rep.alert_needed is False


def test_stop_verify_wired_but_env_disabled_is_DISABLED(tmp_path):
    """THE counterexample: STOP_VERIFY_ALLOW_DIRTY=1 neutralizes a wired hook."""
    cmds = [
        "STOP_VERIFY_ALLOW_DIRTY=1 python3 ~/.claude/hooks/stop_verify.py",
        "~/.claude/hooks/dispatch_nudge.py",
        "~/.claude/hooks/guardrails-client.sh",
    ]
    sp = _write_settings(tmp_path, _settings_with(cmds))
    rep = gl.run_check(host="X", settings_path=sp)
    assert rep.vector()["stop_verify"] == gl.DISABLED
    assert rep.alert_needed is True
    assert "stop_verify" in rep.alert_reason


def test_env_disable_variants_detected(tmp_path):
    # Real shell assignment forms (no spaces around `=` — `VAR = 1` is NOT an
    # assignment in shell, it's the command `VAR` with args, so it must NOT
    # count as a disable; that case is covered by test_spaced_eq_is_not_disable).
    for token in ["=1", "=true", "='1'", '="yes"']:
        cmds = [f"STOP_VERIFY_ALLOW_DIRTY{token} python3 ~/.claude/hooks/stop_verify.py"]
        sp = _write_settings(tmp_path, _settings_with(cmds))
        rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[0]])
        assert rep.vector()["stop_verify"] == gl.DISABLED, token


def test_spaced_eq_is_not_disable(tmp_path):
    """`STOP_VERIFY_ALLOW_DIRTY = 1` is NOT a shell assignment → must not disable."""
    sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"],
                                  env_prefix="STOP_VERIFY_ALLOW_DIRTY = 1 ")
    rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[0]])
    assert rep.vector()["stop_verify"] == gl.OK


def test_hook_not_wired_is_DEAD(tmp_path):
    sp = _write_settings(tmp_path, _settings_with(["something/else.py"]))
    rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[1]])
    assert rep.vector()["dispatch_nudge"] == gl.DEAD
    assert rep.alert_needed is True


# ---- born-dead / first-run alerting (panel Codex#3, DeepSeek#4/#5) ----------


def test_born_dead_alerts_even_with_no_prior(tmp_path):
    """First run with a dead guardrail must alert (not silently baselined)."""
    sp = _write_settings(tmp_path, _settings_with(["unrelated.py"]))
    rep = gl.run_check(host="X", settings_path=sp, prior_vector=None)
    assert rep.alert_needed is True


def test_steady_dead_still_alerts_but_not_regression(tmp_path):
    sp = _write_settings(tmp_path, _settings_with(["unrelated.py"]))
    prior = {"stop_verify": gl.DEAD, "dispatch_nudge": gl.DEAD,
             "guardrails_destructive_mcp": gl.DEAD}
    rep = gl.run_check(host="X", settings_path=sp, prior_vector=prior)
    assert rep.alert_needed is True
    assert rep.regressed == []  # nothing NEWLY died


def test_regression_called_out_among_steady_failures(tmp_path):
    """One was ok, now dead, while another was already dead → regression named."""
    cmds = ["STOP_VERIFY_ALLOW_DIRTY=1 python3 ~/.claude/hooks/stop_verify.py"]
    sp = _write_settings(tmp_path, _settings_with(cmds))
    prior = {"stop_verify": gl.OK, "dispatch_nudge": gl.DEAD,
             "guardrails_destructive_mcp": gl.DEAD}
    rep = gl.run_check(host="X", settings_path=sp, prior_vector=prior)
    assert "stop_verify" in rep.regressed
    assert "dispatch_nudge" not in rep.regressed  # already dead, not new


# ---- state corruption fails LOUD (panel Codex#11) --------------------------


def test_corrupt_settings_json_fails_loud(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ this is not json ")
    rep = gl.run_check(host="X", settings_path=str(p))
    assert rep.vector().get("settings_json") == gl.DEAD
    assert rep.alert_needed is True


def test_missing_settings_json_marks_hooks_dead(tmp_path):
    sp = str(tmp_path / "does_not_exist.json")
    rep = gl.run_check(host="X", settings_path=sp)
    # no settings → wired-checks can't find their command → DEAD, alert
    assert rep.alert_needed is True
    assert all(v == gl.DEAD for k, v in rep.vector().items())


# ---- host scoping (panel Codex#9) ------------------------------------------


def test_wrong_host_is_SKIP_not_dead(tmp_path):
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [{"name": "pro_only_thing", "hosts": ["Nuzantara"],
            "probe": "script_exists", "path": "/nonexistent"}]
    rep = gl.run_check(host="Air-M5", settings_path=sp, registry=reg)
    assert rep.vector()["pro_only_thing"] == gl.SKIP
    assert rep.alert_needed is False  # skip is not a failure


def test_expected_host_absent_script_is_ABSENT(tmp_path):
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [{"name": "thing", "hosts": ["Air-M5"],
            "probe": "script_exists", "path": "/definitely/not/here.sh"}]
    rep = gl.run_check(host="Air-M5", settings_path=sp, registry=reg)
    assert rep.vector()["thing"] == gl.ABSENT
    assert rep.alert_needed is True


# ---- unknown probe is DEAD, never silently skipped --------------------------


def test_unknown_probe_is_dead(tmp_path):
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [{"name": "weird", "hosts": ["*"], "probe": "nope"}]
    rep = gl.run_check(host="X", settings_path=sp, registry=reg)
    assert rep.vector()["weird"] == gl.DEAD


# ---- phantom guardrail NOT seeded (the verify_mcp_integrity scar) -----------


def test_verify_mcp_integrity_not_in_default_registry():
    names = {e["name"] for e in gl.DEFAULT_REGISTRY}
    assert "verify_mcp_integrity" not in names, (
        "phantom guardrail must not be seeded as expected-present (scar 2026-06-06)"
    )


# ---- status_obj shape (caller folds this into sentinel status) -------------


def test_to_status_obj_shape(tmp_path):
    sp = _write_settings(tmp_path, _settings_with(HEALTHY_CMDS))
    rep = gl.run_check(host="X", settings_path=sp)
    obj = rep.to_status_obj()
    assert obj["host"] == "X"
    assert set(obj["vector"]) == {
        "stop_verify", "dispatch_nudge", "guardrails_destructive_mcp"
    }
    assert "regressed" in obj


# ============================================================================
# Panel-hardening regression tests (4-LLM CODE review 2026-06-06)
# Each guards one defect Codex/Gemini found. A real script on disk is needed
# for the "wired + file live" path, so we create temp hook files.
# ============================================================================


def _settings_pointing_at(tmp_path, script_names, env_prefix=""):
    """Create real hook files in tmp + settings.json wiring them."""
    cmds = []
    for n in script_names:
        f = tmp_path / n
        f.write_text("#!/bin/sh\nexit 2\n")  # non-empty
        cmds.append(f"{env_prefix}python3 {f}")
    return _write_settings(tmp_path, _settings_with(cmds)), cmds


def test_wired_but_file_deleted_is_DEAD(tmp_path):
    """C#3/#5: hook wired in settings but the script file doesn't exist."""
    sp = _write_settings(tmp_path, _settings_with(["python3 /no/such/dispatch_nudge.py"]))
    rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[1]])
    assert rep.vector()["dispatch_nudge"] == gl.DEAD


def test_wired_with_live_file_is_OK(tmp_path):
    sp, _ = _settings_pointing_at(tmp_path, ["dispatch_nudge.py"])
    rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[1]])
    assert rep.vector()["dispatch_nudge"] == gl.OK


def test_zero_byte_script_is_not_live(tmp_path):
    """C#4: empty file must NOT count as live (the phantom-shipped pattern)."""
    f = tmp_path / "thing.sh"
    f.write_text("")  # zero bytes
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [{"name": "thing", "hosts": ["*"], "probe": "script_exists", "path": str(f)}]
    rep = gl.run_check(host="X", settings_path=sp, registry=reg)
    assert rep.vector()["thing"] == gl.ABSENT


def test_substring_false_positive_rejected(tmp_path):
    """C#2: `echo stop_verify.py` or `.bak` must NOT mark it wired."""
    sp = _write_settings(tmp_path, _settings_with([
        "echo stop_verify.py.bak running",
        "python3 /x/dispatch_nudge.py.disabled",
    ]))
    rep = gl.run_check(host="X", settings_path=sp,
                       registry=[gl.DEFAULT_REGISTRY[0], gl.DEFAULT_REGISTRY[1]])
    assert rep.vector()["stop_verify"] == gl.DEAD
    assert rep.vector()["dispatch_nudge"] == gl.DEAD


def test_env_disable_via_daemon_environment(tmp_path):
    """C#1/G#1: override exported in env, command clean → DISABLED."""
    sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"])
    rep = gl.run_check(host="X", settings_path=sp,
                       registry=[gl.DEFAULT_REGISTRY[0]],
                       env={"STOP_VERIFY_ALLOW_DIRTY": "1"})
    assert rep.vector()["stop_verify"] == gl.DISABLED


def test_env_disable_uppercase_truthy(tmp_path):
    """G#2: TRUE/YES must still count as disable."""
    for v in ["TRUE", "Yes", "ON"]:
        sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"])
        rep = gl.run_check(host="X", settings_path=sp,
                           registry=[gl.DEFAULT_REGISTRY[0]],
                           env={"STOP_VERIFY_ALLOW_DIRTY": v})
        assert rep.vector()["stop_verify"] == gl.DISABLED, v


def test_env_disable_false_value_is_not_disable(tmp_path):
    """=0 / =false must NOT be read as disabled."""
    for v in ["0", "false", "no"]:
        sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"])
        rep = gl.run_check(host="X", settings_path=sp,
                           registry=[gl.DEFAULT_REGISTRY[0]],
                           env={"STOP_VERIFY_ALLOW_DIRTY": v})
        assert rep.vector()["stop_verify"] == gl.OK, v


def test_disable_env_prefix_var_not_matched(tmp_path):
    """G#2: NON_STOP_VERIFY_ALLOW_DIRTY=1 must NOT disable stop_verify."""
    sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"],
                                  env_prefix="NOT_STOP_VERIFY_ALLOW_DIRTY=1 ")
    rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[0]])
    assert rep.vector()["stop_verify"] == gl.OK


def test_partial_value_not_matched(tmp_path):
    """=12 / =true_x must NOT count as truthy disable."""
    for v in ["12", "true_override", "yesterday"]:
        sp, _ = _settings_pointing_at(tmp_path, ["stop_verify.py"],
                                      env_prefix=f"STOP_VERIFY_ALLOW_DIRTY={v} ")
        rep = gl.run_check(host="X", settings_path=sp, registry=[gl.DEFAULT_REGISTRY[0]])
        assert rep.vector()["stop_verify"] == gl.OK, v


def test_host_normalization_fqdn_and_local(tmp_path):
    """G#8/#9: Nuzantara.local / Nuzantara.domain / case all match 'Nuzantara'."""
    f = tmp_path / "h.sh"; f.write_text("x")
    reg = [{"name": "h", "hosts": ["Nuzantara"], "probe": "script_exists", "path": str(f)}]
    for h in ["Nuzantara", "nuzantara", "Nuzantara.local", "Nuzantara.tail123.ts.net"]:
        sp = _write_settings(tmp_path, _settings_with([]))
        rep = gl.run_check(host=h, settings_path=sp, registry=reg)
        assert rep.vector()["h"] == gl.OK, h


def test_hosts_as_string_does_not_loose_match(tmp_path):
    """G#8: hosts given as a string must not substring-match."""
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [{"name": "h", "hosts": "prod-host", "probe": "script_exists", "path": "/x"}]
    rep = gl.run_check(host="host", settings_path=sp, registry=reg)
    assert rep.vector()["h"] == gl.SKIP  # string hosts → does not apply, not a fake match


def test_duplicate_registry_names_loud(tmp_path):
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [
        {"name": "dup", "hosts": ["*"], "probe": "script_exists", "path": "/a"},
        {"name": "dup", "hosts": ["*"], "probe": "script_exists", "path": "/b"},
    ]
    rep = gl.run_check(host="X", settings_path=sp, registry=reg)
    assert rep.vector().get("registry_config") == gl.DEAD
    assert rep.alert_needed is True


def test_missing_required_key_is_loud_per_guardrail(tmp_path):
    """C#8: missing settings_key → that guardrail DEAD, not whole-run abort."""
    sp = _write_settings(tmp_path, _settings_with([]))
    reg = [
        {"name": "broken", "hosts": ["*"], "probe": "hook_wired"},  # no settings_key
        {"name": "fine", "hosts": ["X-only"], "probe": "script_exists", "path": "/x"},
    ]
    rep = gl.run_check(host="X", settings_path=sp, registry=reg)
    assert rep.vector()["broken"] == gl.DEAD
    # the other entry still got evaluated (SKIP, wrong host) — run did not abort
    assert "fine" in rep.vector()


def test_corrupt_settings_does_not_leak_content(tmp_path):
    """G#6: corrupt-json alert must not echo file bytes."""
    p = tmp_path / "settings.json"
    p.write_text('{ "secret_token": "ABCD-LEAK-1234" not json')
    rep = gl.run_check(host="X", settings_path=str(p))
    obj = rep.to_status_obj()
    blob = json.dumps(obj)
    assert "ABCD-LEAK-1234" not in blob


def test_invalid_utf8_settings_fails_loud_not_crash(tmp_path):
    """G#4/C#7: invalid UTF-8 must yield settings_json DEAD, not raise."""
    p = tmp_path / "settings.json"
    p.write_bytes(b"\xff\xfe not valid utf8")
    rep = gl.run_check(host="X", settings_path=str(p))  # must not raise
    assert rep.vector().get("settings_json") == gl.DEAD


def test_to_status_obj_keeps_alert_fields(tmp_path):
    """C#9: alert_needed/alert_reason must survive serialization."""
    sp = _write_settings(tmp_path, _settings_with(["unrelated.py"]))
    rep = gl.run_check(host="X", settings_path=sp)
    obj = rep.to_status_obj()
    assert obj["alert_needed"] is True
    assert obj["alert_reason"]


def test_malformed_hooks_shape_does_not_crash(tmp_path):
    """G#3: hooks as non-list must not raise."""
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": {"PreToolUse": 123}}))
    rep = gl.run_check(host="X", settings_path=str(p))  # must not raise
    # nothing wired → all dead, but no crash
    assert rep.alert_needed is True


def test_new_born_dead_guardrail_not_marked_regression(tmp_path):
    """DeepSeek #5: a guardrail UNKNOWN in prior, born dead, is NOT a regression."""
    sp = _write_settings(tmp_path, _settings_with(["unrelated.py"]))
    prior = {"dispatch_nudge": gl.OK}  # stop_verify NOT in prior at all
    rep = gl.run_check(host="X", settings_path=sp, prior_vector=prior)
    assert "stop_verify" not in rep.regressed  # new + dead != regression
    assert rep.alert_needed is True  # still alerts (born-dead), just not "regression"


def test_default_registry_not_mutated_across_runs(tmp_path):
    """DeepSeek #7: DEFAULT_REGISTRY must not be corrupted by a run."""
    before = [dict(e) for e in gl.DEFAULT_REGISTRY]
    sp = _write_settings(tmp_path, _settings_with([]))
    gl.run_check(host="X", settings_path=sp)
    assert gl.DEFAULT_REGISTRY == before
