"""TDD for the meta-verifier (P1 §4). 'Scrivilo con TDD + congelalo.'

Each check is exercised armed→ARMED and disarmed→DISARMED with synthetic
fixtures (a fake settings.json, a fake workflow, a fake lint+consumer). The
binary exit-code contract and the JSON schema are frozen here.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    path = Path(__file__).parents[1] / "verify_the_verifiers.py"
    spec = importlib.util.spec_from_file_location("verify_the_verifiers", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so @dataclass(field=...) can resolve
    # cls.__module__ (importlib + dataclass gotcha).
    sys.modules["verify_the_verifiers"] = module
    spec.loader.exec_module(module)
    return module


VTV = _load_module()


# --------------------------------------------------------------------------- #
# claude_hook
# --------------------------------------------------------------------------- #

def _write_settings(path: Path, event: str, command: str) -> None:
    path.write_text(json.dumps({
        "hooks": {event: [{"hooks": [{"type": "command", "command": command}]}]}
    }))


def test_claude_hook_armed(tmp_path: Path) -> None:
    hook = tmp_path / "stop_verify.py"
    hook.write_text("# hook\n")
    settings = tmp_path / "settings.json"
    _write_settings(settings, "Stop", "python3 ~/.claude/hooks/stop_verify.py")
    gate = {
        "id": "stop_verify", "kind": "claude_hook",
        "target": str(hook), "registered_in": str(settings),
        "event": "Stop", "disarm_substring": "STOP_VERIFY_ALLOW_DIRTY=1",
    }
    r = VTV.check_claude_hook(gate)
    assert r.verdict == VTV.ARMED, r.detail


def test_claude_hook_disarmed_by_substring(tmp_path: Path) -> None:
    hook = tmp_path / "stop_verify.py"
    hook.write_text("# hook\n")
    settings = tmp_path / "settings.json"
    # The disarm string is hardcoded in the command — the exact real-world bug.
    _write_settings(settings, "Stop",
                    "STOP_VERIFY_ALLOW_DIRTY=1 python3 ~/.claude/hooks/stop_verify.py")
    gate = {
        "id": "stop_verify", "kind": "claude_hook",
        "target": str(hook), "registered_in": str(settings),
        "event": "Stop", "disarm_substring": "STOP_VERIFY_ALLOW_DIRTY=1",
    }
    r = VTV.check_claude_hook(gate)
    assert r.verdict == VTV.DISARMED
    assert "disarm substring" in r.detail


def test_claude_hook_disarmed_when_target_missing(tmp_path: Path) -> None:
    settings = tmp_path / "settings.json"
    _write_settings(settings, "Stop", "python3 /nope/stop_verify.py")
    gate = {
        "id": "stop_verify", "kind": "claude_hook",
        "target": str(tmp_path / "absent.py"), "registered_in": str(settings),
        "event": "Stop", "disarm_substring": None,
    }
    r = VTV.check_claude_hook(gate)
    assert r.verdict == VTV.DISARMED
    assert "missing" in r.detail


def test_claude_hook_disarmed_when_not_registered(tmp_path: Path) -> None:
    hook = tmp_path / "guardrails-client.sh"
    hook.write_text("# hook\n")
    settings = tmp_path / "settings.json"
    _write_settings(settings, "PreToolUse", "python3 ~/.claude/hooks/something_else.py")
    gate = {
        "id": "guardrails_client", "kind": "claude_hook",
        "target": str(hook), "registered_in": str(settings),
        "event": "PreToolUse", "disarm_substring": None,
    }
    r = VTV.check_claude_hook(gate)
    assert r.verdict == VTV.DISARMED
    assert "not registered" in r.detail


# --------------------------------------------------------------------------- #
# ci_workflow
# --------------------------------------------------------------------------- #

def _write_workflow(path: Path, step_name: str, continue_on_error: bool) -> None:
    path.write_text(
        "name: wf\n"
        "on: [pull_request]\n"
        "jobs:\n"
        "  gate:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - name: {step_name}\n"
        f"        continue-on-error: {str(continue_on_error).lower()}\n"
        "        run: echo hi\n"
    )


def test_ci_workflow_armed_when_enforcing(tmp_path: Path) -> None:
    wf = tmp_path / "hot-zone.yml"
    _write_workflow(wf, "CODEOWNERS self-mod check", continue_on_error=False)
    gate = {
        "id": "hot_zone_codeowners_self_mod", "kind": "ci_workflow",
        "target": str(wf), "step_anchor": "CODEOWNERS self-mod check",
        "expected_continue_on_error": False,
    }
    r = VTV.check_ci_workflow(gate)
    assert r.verdict == VTV.ARMED, r.detail


def test_ci_workflow_disarmed_when_monitor_but_expected_enforcing(tmp_path: Path) -> None:
    wf = tmp_path / "hot-zone.yml"
    _write_workflow(wf, "CODEOWNERS self-mod check", continue_on_error=True)
    gate = {
        "id": "hot_zone_codeowners_self_mod", "kind": "ci_workflow",
        "target": str(wf), "step_anchor": "CODEOWNERS self-mod check",
        "expected_continue_on_error": False,
    }
    r = VTV.check_ci_workflow(gate)
    assert r.verdict == VTV.DISARMED
    assert "expected enforcing" in r.detail


def test_ci_workflow_monitor_by_design_is_armed(tmp_path: Path) -> None:
    # A monitor-by-design step (Redis lease) staying true is CORRECT, not disarmed.
    wf = tmp_path / "hot-zone.yml"
    _write_workflow(wf, "Redis lease check (best-effort)", continue_on_error=True)
    gate = {
        "id": "hot_zone_redis_lease", "kind": "ci_workflow",
        "target": str(wf), "step_anchor": "lease check",
        "expected_continue_on_error": True,
    }
    r = VTV.check_ci_workflow(gate)
    assert r.verdict == VTV.ARMED, r.detail


def test_ci_workflow_disarmed_when_step_missing(tmp_path: Path) -> None:
    wf = tmp_path / "hot-zone.yml"
    _write_workflow(wf, "Some other step", continue_on_error=False)
    gate = {
        "id": "hot_zone_codeowners_self_mod", "kind": "ci_workflow",
        "target": str(wf), "step_anchor": "CODEOWNERS self-mod check",
        "expected_continue_on_error": False,
    }
    r = VTV.check_ci_workflow(gate)
    assert r.verdict == VTV.DISARMED
    assert "not found" in r.detail


def test_ci_workflow_default_continue_on_error_is_false(tmp_path: Path) -> None:
    # GitHub semantics: absent continue-on-error == false (enforcing).
    wf = tmp_path / "hot-zone.yml"
    wf.write_text(
        "name: wf\non: [pull_request]\njobs:\n  gate:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - name: CODEOWNERS self-mod check\n        run: echo hi\n"
    )
    gate = {
        "id": "x", "kind": "ci_workflow", "target": str(wf),
        "step_anchor": "CODEOWNERS self-mod check", "expected_continue_on_error": False,
    }
    r = VTV.check_ci_workflow(gate)
    assert r.verdict == VTV.ARMED, r.detail


# --------------------------------------------------------------------------- #
# lint_script
# --------------------------------------------------------------------------- #

def test_lint_script_armed_with_consumer(tmp_path: Path) -> None:
    lint = tmp_path / "lint_migration_numbers.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "lint-migration-numbers.yml"
    consumer.write_text("run: python scripts/lint_migration_numbers.py\n")
    gate = {
        "id": "lint_migration_numbers", "kind": "lint_script",
        "target": str(lint), "consumer": str(consumer),
    }
    r = VTV.check_lint_script(gate)
    assert r.verdict == VTV.ARMED, r.detail


def test_lint_script_warn_without_consumer(tmp_path: Path) -> None:
    lint = tmp_path / "lint_asyncpg_except_completeness.py"
    lint.write_text("# lint\n")
    gate = {
        "id": "lint_asyncpg_except_completeness", "kind": "lint_script",
        "target": str(lint), "consumer": None,
    }
    r = VTV.check_lint_script(gate)
    assert r.verdict == VTV.WARN
    assert "NO consumer" in r.detail


def test_lint_script_disarmed_when_consumer_does_not_run_it(tmp_path: Path) -> None:
    lint = tmp_path / "lint_x.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "some.yml"
    consumer.write_text("run: echo unrelated\n")  # does NOT reference lint_x.py
    gate = {
        "id": "lint_x", "kind": "lint_script",
        "target": str(lint), "consumer": str(consumer),
    }
    r = VTV.check_lint_script(gate)
    assert r.verdict == VTV.DISARMED
    assert "does not reference" in r.detail


def test_lint_script_disarmed_when_missing(tmp_path: Path) -> None:
    gate = {
        "id": "lint_gone", "kind": "lint_script",
        "target": str(tmp_path / "gone.py"), "consumer": None,
    }
    r = VTV.check_lint_script(gate)
    assert r.verdict == VTV.DISARMED
    assert "missing" in r.detail


# --------------------------------------------------------------------------- #
# Report aggregation + binary exit contract
# --------------------------------------------------------------------------- #

def test_report_ok_with_only_warn() -> None:
    rep = VTV.Report(results=[
        VTV.GateResult("a", "lint_script", VTV.ARMED),
        VTV.GateResult("b", "lint_script", VTV.WARN, "no consumer"),
    ])
    assert rep.ok is True  # WARN does not fail the build


def test_report_not_ok_with_disarmed() -> None:
    rep = VTV.Report(results=[
        VTV.GateResult("a", "claude_hook", VTV.ARMED),
        VTV.GateResult("b", "ci_workflow", VTV.DISARMED, "monitor"),
    ])
    assert rep.ok is False


def test_evaluate_unknown_kind_is_disarmed() -> None:
    rep = VTV.evaluate({"gates": [{"id": "weird", "kind": "telepathy"}]})
    assert rep.disarmed[0].gate_id == "weird"
    assert "unknown gate kind" in rep.disarmed[0].detail


def test_json_schema_stable() -> None:
    rep = VTV.Report(results=[VTV.GateResult("a", "lint_script", VTV.ARMED, "ok")])
    payload = json.loads(VTV.render_json(rep))
    assert set(payload) == {"ok", "total", "armed", "disarmed", "warn", "skipped", "gates"}
    assert set(payload["gates"][0]) == {"id", "kind", "verdict", "detail"}


# --------------------------------------------------------------------------- #
# Scope (repo vs local) — claude_hook gates not verifiable on a CI runner
# --------------------------------------------------------------------------- #

def test_gate_scope_defaults_by_kind() -> None:
    assert VTV.gate_scope({"kind": "claude_hook"}) == "local"
    assert VTV.gate_scope({"kind": "ci_workflow"}) == "repo"
    assert VTV.gate_scope({"kind": "lint_script"}) == "repo"


def test_gate_scope_explicit_override() -> None:
    assert VTV.gate_scope({"kind": "ci_workflow", "scope": "local"}) == "local"


def test_evaluate_repo_scope_skips_local_hooks(tmp_path: Path) -> None:
    # A claude_hook whose target is absent would be DISARMED in a full check,
    # but under --scope repo it must be SKIPPED (not DISARMED) — the CI case.
    registry = {"gates": [
        {"id": "stop_verify", "kind": "claude_hook",
         "target": str(tmp_path / "absent.py"), "registered_in": str(tmp_path / "nope.json"),
         "event": "Stop", "disarm_substring": None},
    ]}
    rep = VTV.evaluate(registry, only_scope="repo")
    assert rep.skipped[0].gate_id == "stop_verify"
    assert rep.ok is True  # SKIPPED never fails the build


def test_evaluate_all_scope_checks_local_hooks(tmp_path: Path) -> None:
    # Without scope filter, the same missing hook is DISARMED (the local case).
    registry = {"gates": [
        {"id": "stop_verify", "kind": "claude_hook",
         "target": str(tmp_path / "absent.py"), "registered_in": str(tmp_path / "nope.json"),
         "event": "Stop", "disarm_substring": None},
    ]}
    rep = VTV.evaluate(registry, only_scope=None)
    assert rep.disarmed[0].gate_id == "stop_verify"
    assert rep.ok is False


def test_main_ci_env_auto_scopes_repo(tmp_path: Path, monkeypatch) -> None:
    # With CI=1 and a missing local hook, main must auto-scope to repo → green.
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: stop_verify\n    kind: claude_hook\n    target: {tmp_path / 'absent.py'}\n"
        f"    registered_in: {tmp_path / 'nope.json'}\n    event: Stop\n    disarm_substring: null\n"
    )
    monkeypatch.setenv("CI", "1")
    code = VTV.main(["--registry", str(reg), "--no-signal", "--json"])
    assert code == 0  # local hook SKIPPED under CI auto-scope, not DISARMED


def test_main_exit_code_green(tmp_path: Path, monkeypatch) -> None:
    # A registry with one armed lint (with consumer) → exit 0.
    lint = tmp_path / "lint_x.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "x.yml"
    consumer.write_text("python scripts/lint_x.py\n")
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: lint_x\n    kind: lint_script\n    target: {lint}\n    consumer: {consumer}\n"
    )
    code = VTV.main(["--registry", str(reg), "--no-signal", "--json"])
    assert code == 0


def test_main_exit_code_red(tmp_path: Path) -> None:
    # A truly disarmed claude_hook (target missing) → RED. Force --scope all so the
    # test is deterministic regardless of the CI env var (on a CI runner, default
    # auto-scope=repo would SKIP the claude_hook → false green; --scope all checks it).
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: gone\n    kind: claude_hook\n    target: {tmp_path / 'gone.py'}\n"
        f"    registered_in: {tmp_path / 'nope.json'}\n    event: Stop\n    disarm_substring: null\n"
    )
    code = VTV.main(["--registry", str(reg), "--no-signal", "--scope", "all"])
    assert code == 1


def test_main_registry_missing_returns_3(tmp_path: Path) -> None:
    code = VTV.main(["--registry", str(tmp_path / "nope.yaml"), "--no-signal"])
    assert code == 3


# --------------------------------------------------------------------------- #
# Canary self-test
# --------------------------------------------------------------------------- #

def test_canary_detects_lever() -> None:
    gate = {
        "id": "stop_verify", "kind": "claude_hook",
        "disarm_substring": "STOP_VERIFY_ALLOW_DIRTY=1",
        "canary": {"env": {"STOP_VERIFY_ALLOW_DIRTY": "1"}, "expect": "disarmed"},
    }
    r = VTV.run_canary(gate)
    assert r.verdict == VTV.ARMED
    assert "lever" in r.detail


# --------------------------------------------------------------------------- #
# Dead-man's switch (G5)
# --------------------------------------------------------------------------- #

def test_alive_signal_written(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "state" / "verify_the_verifiers.json"
    monkeypatch.setattr(VTV, "STATE_FILE", state)
    rep = VTV.Report(results=[VTV.GateResult("a", "lint_script", VTV.ARMED)])
    VTV.write_alive_signal(rep)
    data = json.loads(state.read_text())
    assert data["_writer"] == "verify_the_verifiers"
    assert data["status"] == "ok"
    assert "ts" in data and isinstance(data["ts"], int)
