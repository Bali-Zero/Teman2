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
    assert rep.disarmed == []  # SKIPPED never fails the build
    # This line used to read `assert rep.ok is True`. "SKIPPED never fails the build"
    # was frozen here as "a report of nothing but SKIPPED gates is GREEN", and those
    # are not the same claim: the second one made a run that verified nothing
    # indistinguishable from a healthy one. The rule is now "SKIPPED never fails a run
    # that checked something", pinned in both directions at the end of this file. What
    # this test is actually about — a local hook under --scope repo is SKIPPED and not
    # DISARMED — is asserted above, and directly.


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
    #
    # The registry carries a SECOND, repo-scope gate that is genuinely armed. It was
    # added when `Report.ok` stopped counting an all-SKIPPED run as green: without it
    # this test passed for the wrong reason — exit 0 meant "verified nothing" rather
    # than "the local hook was skipped, not disarmed", and the two were indistinguishable
    # in the exit code, which is precisely the defect the change cures. The original
    # assertion is preserved and now pinned by verdict as well as by exit code.
    lint = tmp_path / "lint_present.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "consumer.yml"
    consumer.write_text(f"python {lint}\n")
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: stop_verify\n    kind: claude_hook\n    target: {tmp_path / 'absent.py'}\n"
        f"    registered_in: {tmp_path / 'nope.json'}\n    event: Stop\n    disarm_substring: null\n"
        f"  - id: lint_present\n    kind: lint_script\n    target: {lint}\n    consumer: {consumer}\n"
    )
    monkeypatch.setenv("CI", "1")
    code = VTV.main(["--registry", str(reg), "--no-signal", "--json"])
    assert code == 0  # local hook SKIPPED under CI auto-scope, not DISARMED

    report = VTV.evaluate(
        {"gates": [
            {"id": "stop_verify", "kind": "claude_hook",
             "target": str(tmp_path / "absent.py"),
             "registered_in": str(tmp_path / "nope.json"),
             "event": "Stop", "disarm_substring": None},
            {"id": "lint_present", "kind": "lint_script",
             "target": str(lint), "consumer": str(consumer)},
        ]},
        only_scope="repo",
    )
    assert [r.verdict for r in report.results] == [VTV.SKIPPED, VTV.ARMED]


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


# --------------------------------------------------------------------------- #
# A meta-verifier that iterates nothing must be RED, not GREEN
#
# `Report.ok` used to read "zero DISARMED gates", which is trivially true of a run
# that checked nothing at all. Measured 2026-09-05 on a scratch copy of the shipped
# registry: emptying `gates:`, or deleting the key outright, produced "0/0 gates
# ARMED", `report.ok is True`, exit 0, and an alive signal reading `status: "ok"` —
# with no warning printed anywhere, unlike the `consumer: null` case which at least
# emits a WARN. The organ whose whole job is to make "a gate went dark" observable
# was the one place where an empty collection read as success.
#
# Both directions are pinned, because a floor strict enough to refuse the registry
# actually shipped, or the synthetic one- and two-gate registries the other tests
# pass via `--registry`, would be safe and useless (superscar #3).
# --------------------------------------------------------------------------- #

def test_guilt_a_report_that_checked_nothing_is_not_green() -> None:
    assert VTV.Report(results=[]).ok is False


def test_guilt_a_report_where_every_gate_was_SKIPPED_is_not_green() -> None:
    """"Nothing was found disarmed" is not the statement "the gates are armed"."""
    rep = VTV.Report(results=[
        VTV.GateResult("a", "claude_hook", VTV.SKIPPED, "scope=local"),
        VTV.GateResult("b", "claude_hook", VTV.SKIPPED, "scope=local"),
    ])
    assert rep.ok is False
    assert rep.checked == []


def test_guilt_an_empty_gates_list_evaluates_to_a_report_that_is_not_green() -> None:
    assert VTV.evaluate({"gates": []}).ok is False


def test_guilt_main_refuses_an_empty_registry_instead_of_exiting_zero(tmp_path: Path) -> None:
    """The measured fail-open: this returned 0 and printed "0/0 gates ARMED"."""
    reg = tmp_path / "gates.yaml"
    reg.write_text("version: 1\ngates: []\n")
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_guilt_main_refuses_a_registry_with_no_gates_key(tmp_path: Path) -> None:
    reg = tmp_path / "gates.yaml"
    reg.write_text("version: 1\n")
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_guilt_the_alive_signal_is_never_ok_for_a_run_that_checked_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """The dead-man's switch is the consumer that made this dangerous.

    CORRECTED after an independent read of the consumers (2026-09-05): NOTHING
    PARSES THIS PAYLOAD. `scripts/cost_breaker_deadman.sh:50` and
    `infra/launchagents/install_fase0_governance.sh:199` are the only two readers
    and both `stat` the mtime and nothing else, so `status` and `gates_total` are
    decorative to every consumer that exists today. An earlier draft of this
    docstring said a staleness watcher "would see" the payload; it would not. The
    deception was carried by the MTIME — the launchd job rewrote the file every
    600s, the deadman read FRESH, and it stayed silent forever.

    So the field is pinned here on its own merits, not on a consumer's: it is the
    only place the run's own verdict is written down, and `write_alive_signal`
    derives it from `report.ok`, so a property that lies makes the record lie too.
    The cure that actually reaches a consumer is in `main()`, which refuses BEFORE
    this file is written: the mtime then freezes, and after 1800s the deadman
    fires "GOVERNANCE MUTA" over Telegram
    (`scripts/cost_breaker_deadman.sh:54,227`). That trades silent-green for
    delayed-but-alarmed, which is the trade this change is actually making.
    """
    state = tmp_path / "state" / "verify_the_verifiers.json"
    monkeypatch.setattr(VTV, "STATE_FILE", state)
    VTV.write_alive_signal(VTV.Report(results=[]))
    data = json.loads(state.read_text())
    assert data["status"] == "disarmed_gates_detected"
    assert data["gates_total"] == 0


def test_guilt_the_default_registry_below_the_floor_is_refused(
    tmp_path: Path, monkeypatch
) -> None:
    """Emptying the registry is loud; deleting gates one at a time was not.

    The floor lives in the SCRIPT, not in the registry, so lowering it is a diff
    in a different file from the one a bad merge or an attacker edits.
    """
    lint = tmp_path / "lint_x.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "x.yml"
    consumer.write_text(f"python {lint}\n")
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: lint_x\n    kind: lint_script\n    target: {lint}\n    consumer: {consumer}\n"
    )
    monkeypatch.setattr(VTV, "DEFAULT_REGISTRY", reg)
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_innocence_a_synthetic_registry_passed_via_registry_is_not_floored(
    tmp_path: Path,
) -> None:
    """The over-match direction: `--registry` is a test affordance, not the shipped file.

    Every other `main()` test in this file passes a one- or two-gate registry. If the
    floor applied to those, this battery would fail the suite it belongs to.
    """
    lint = tmp_path / "lint_x.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / "x.yml"
    consumer.write_text(f"python {lint}\n")
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n"
        f"  - id: lint_x\n    kind: lint_script\n    target: {lint}\n    consumer: {consumer}\n"
    )
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 0


def test_innocence_the_shipped_registry_still_clears_the_floor() -> None:
    """A floor above the registry actually shipped would take main red on every run."""
    import yaml as _yaml
    doc = _yaml.safe_load(VTV.DEFAULT_REGISTRY.read_text())
    assert len(doc["gates"]) >= VTV.MINIMUM_GATES


def test_innocence_the_shipped_registry_still_checks_gates_under_repo_scope() -> None:
    """Not "is green" — the shipped registry's verdict depends on the environment.

    What must hold is that a repo-scope run still CHECKS gates rather than skipping
    them all, which is the precondition `Report.ok` now requires.
    """
    import yaml as _yaml
    doc = _yaml.safe_load(VTV.DEFAULT_REGISTRY.read_text())
    report = VTV.evaluate(doc, only_scope="repo")
    assert len(report.checked) >= 20


def test_innocence_a_report_with_armed_and_skipped_gates_is_still_green() -> None:
    """SKIPPED must not COUNT; it must also not POISON a run that checked something."""
    rep = VTV.Report(results=[
        VTV.GateResult("a", "lint_script", VTV.ARMED),
        VTV.GateResult("b", "claude_hook", VTV.SKIPPED, "scope=local"),
    ])
    assert rep.ok is True


# --------------------------------------------------------------------------- #
# The registry is a POLICY document and is loaded STRICTLY
#
# yaml.safe_load lets a duplicate top-level key win in silence, so a second `gates:`
# appended at the end replaces the 34 above it and reviews as an added block.
# MINIMUM_GATES catches that by COUNT — but only by count: a replacement list of 34
# harmless-looking entries clears the floor while checking nothing real. And one level
# further down, `gates:` is a LIST, so a repeated `id:` does not shadow — it produces
# two results, while render_json emits gates KEYED BY ID and any consumer building a
# dict from that output silently keeps the last. "Last one wins in silence" belongs to
# any keyed collection built without a collision check, not to YAML.
# --------------------------------------------------------------------------- #

def _armed_gate(tmp_path: Path, gate_id: str) -> str:
    """One genuinely ARMED lint gate, as registry YAML text."""
    lint = tmp_path / f"{gate_id}.py"
    lint.write_text("# lint\n")
    consumer = tmp_path / f"{gate_id}.yml"
    consumer.write_text(f"python {lint}\n")
    return f"  - id: {gate_id}\n    kind: lint_script\n    target: {lint}\n    consumer: {consumer}\n"


def test_guilt_a_duplicated_gates_key_is_refused(tmp_path) -> None:
    """The append attack: safe_load would take the second block and say nothing."""
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n" + _armed_gate(tmp_path, "real")
        + "gates:\n" + _armed_gate(tmp_path, "impostor")
    )
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_guilt_a_repeated_gate_ID_is_refused(tmp_path) -> None:
    """One level down: no duplicate YAML key at all, and the JSON report is id-keyed."""
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n" + _armed_gate(tmp_path, "twin") + _armed_gate(tmp_path, "twin")
    )
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_guilt_a_gate_without_an_id_is_refused(tmp_path) -> None:
    """A gate with no id cannot appear in a report, so it cannot be verified."""
    reg = tmp_path / "gates.yaml"
    reg.write_text("version: 1\ngates:\n  - kind: lint_script\n    target: /nope\n")
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_guilt_an_alias_in_the_registry_is_refused(tmp_path) -> None:
    """An anchor defined far from its use puts the governing value out of the reader's eye."""
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "anchor: &a\n  id: x\n  kind: lint_script\n  target: /nope\ngates:\n  - *a\n"
    )
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 3


def test_innocence_the_shipped_registry_still_loads_through_the_strict_loader() -> None:
    """A loader strict enough to refuse the file actually shipped would be useless."""
    registry = VTV._load_registry_strictly(VTV.DEFAULT_REGISTRY)
    assert len(registry["gates"]) >= VTV.MINIMUM_GATES


def test_innocence_the_shipped_registry_has_no_repeated_gate_id() -> None:
    """The over-match direction, asserted on the real file rather than assumed."""
    registry = VTV._load_registry_strictly(VTV.DEFAULT_REGISTRY)
    ids = [g["id"] for g in registry["gates"]]
    assert len(ids) == len(set(ids))


def test_innocence_two_DIFFERENT_gate_ids_are_not_a_collision(tmp_path) -> None:
    reg = tmp_path / "gates.yaml"
    reg.write_text(
        "version: 1\ngates:\n" + _armed_gate(tmp_path, "one") + _armed_gate(tmp_path, "two")
    )
    assert VTV.main(["--registry", str(reg), "--no-signal"]) == 0
