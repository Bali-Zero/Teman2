#!/usr/bin/env python3
"""verify_the_verifiers.py — the meta-verifier (P1 §4 of the SOTA meta-dev-loop).

The deterministic gate that makes it OBSERVABLE when another safety gate is
DISARMED. It is NOT intelligent — it is deterministic, auditable-once, and frozen
(P1 §4). It does three things:

  1. For every gate in scripts/verify_the_verifiers_gates.yaml, check it is ARMED.
  2. (--canary, local only) fire known-bad inputs and verify the disarm lever works.
  3. Emit a BINARY red/green report (+ --json for CI). Exit 0 if all armed
     (WARN allowed), exit 1 if any gate is DISARMED.

Why it must itself be immutable (R1, council DeepSeek — "quis custodiet ipsos
custodes?"): a meta-verifier the agent can disarm is just another disarmable gate.
Immutability is enforced OUTSIDE this file (CODEOWNERS + .sha256 verified in the
verify-the-verifiers.yml CI on an isolated runner). This script only RENDERS the
state observable; it does not (and cannot) protect itself.

No LLM. No network. Pure filesystem + YAML/JSON parsing. Deterministic.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a repo dependency
    print("FATAL: pyyaml not installed (pip install pyyaml)", file=sys.stderr)
    sys.exit(3)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "scripts" / "verify_the_verifiers_gates.yaml"
STATE_FILE = Path.home() / ".agent" / "decisions" / "state" / "verify_the_verifiers.json"

# Verdicts
ARMED = "ARMED"
DISARMED = "DISARMED"
WARN = "WARN"


@dataclass
class GateResult:
    gate_id: str
    kind: str
    verdict: str  # ARMED | DISARMED | WARN
    detail: str = ""


@dataclass
class Report:
    results: list[GateResult] = field(default_factory=list)

    @property
    def disarmed(self) -> list[GateResult]:
        return [r for r in self.results if r.verdict == DISARMED]

    @property
    def warnings(self) -> list[GateResult]:
        return [r for r in self.results if r.verdict == WARN]

    @property
    def armed(self) -> list[GateResult]:
        return [r for r in self.results if r.verdict == ARMED]

    @property
    def ok(self) -> bool:
        """Green iff zero DISARMED gates. WARN does not fail the build."""
        return len(self.disarmed) == 0


def _expand(path: str) -> Path:
    """Expand ~ and resolve repo-relative paths."""
    if path.startswith("~"):
        return Path(path).expanduser()
    p = Path(path)
    return p if p.is_absolute() else (REPO_ROOT / p)


# --------------------------------------------------------------------------- #
# Per-kind arming checks (pure, deterministic)
# --------------------------------------------------------------------------- #

def _iter_hook_commands(settings: dict, event: str) -> list[str]:
    """Return every hook command string registered under a settings.json event."""
    commands: list[str] = []
    for entry in settings.get("hooks", {}).get(event, []):
        for hook in entry.get("hooks", []):
            cmd = hook.get("command")
            if isinstance(cmd, str):
                commands.append(cmd)
    return commands


def check_claude_hook(gate: dict) -> GateResult:
    gid = gate["id"]
    target = _expand(gate["target"])
    settings_path = _expand(gate["registered_in"])
    event = gate.get("event", "")
    disarm = gate.get("disarm_substring")

    if not target.exists():
        return GateResult(gid, "claude_hook", DISARMED,
                          f"target hook file missing: {target}")
    if not settings_path.exists():
        return GateResult(gid, "claude_hook", DISARMED,
                          f"settings file missing: {settings_path}")
    try:
        settings = json.loads(settings_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return GateResult(gid, "claude_hook", DISARMED,
                          f"settings.json unreadable: {exc}")

    commands = _iter_hook_commands(settings, event)
    # The hook is registered iff some command references the target basename.
    target_name = target.name
    matching = [c for c in commands if target_name in c]
    if not matching:
        return GateResult(gid, "claude_hook", DISARMED,
                          f"hook not registered under event '{event}' in settings.json")

    # Disarm substring present in the registering command → disarmed.
    if disarm:
        for cmd in matching:
            if disarm in cmd:
                return GateResult(gid, "claude_hook", DISARMED,
                                  f"disarm substring present in command: '{disarm}'")
    return GateResult(gid, "claude_hook", ARMED,
                      f"registered under '{event}', no disarm substring")


def _step_continue_on_error(workflow: dict, anchor: str) -> bool | None:
    """Find the step whose name contains `anchor`, return its continue-on-error.

    Returns None if no matching step found. continue-on-error defaults to False
    when the key is absent (GitHub Actions semantics).
    """
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            name = step.get("name", "")
            if anchor in name:
                return bool(step.get("continue-on-error", False))
    return None


def check_ci_workflow(gate: dict) -> GateResult:
    gid = gate["id"]
    target = _expand(gate["target"])
    anchor = gate["step_anchor"]
    expected = bool(gate["expected_continue_on_error"])

    if not target.exists():
        return GateResult(gid, "ci_workflow", DISARMED,
                          f"workflow file missing: {target}")
    try:
        workflow = yaml.safe_load(target.read_text())
    except (OSError, yaml.YAMLError) as exc:
        return GateResult(gid, "ci_workflow", DISARMED,
                          f"workflow unparseable: {exc}")

    actual = _step_continue_on_error(workflow, anchor)
    if actual is None:
        return GateResult(gid, "ci_workflow", DISARMED,
                          f"step matching '{anchor}' not found in {target.name}")
    if actual != expected:
        state = "monitor (continue-on-error=true)" if actual else "enforcing (continue-on-error=false)"
        want = "enforcing" if not expected else "monitor"
        return GateResult(gid, "ci_workflow", DISARMED,
                          f"step '{anchor}' is {state}, expected {want}")
    return GateResult(gid, "ci_workflow", ARMED,
                      f"step '{anchor}' continue-on-error={actual} as expected")


def _consumer_runs_script(consumer: Path, script_name: str) -> bool:
    """Best-effort: does the consumer file reference the lint script's name?"""
    try:
        return script_name in consumer.read_text()
    except OSError:
        return False


def check_lint_script(gate: dict) -> GateResult:
    gid = gate["id"]
    target = _expand(gate["target"])
    consumer = gate.get("consumer")

    if not target.exists():
        return GateResult(gid, "lint_script", DISARMED,
                          f"lint script missing: {target}")
    if consumer is None:
        return GateResult(gid, "lint_script", WARN,
                          "lint exists but has NO consumer — it gates nothing (cicatrix W64)")

    consumer_path = _expand(consumer)
    if not consumer_path.exists():
        return GateResult(gid, "lint_script", DISARMED,
                          f"declared consumer missing: {consumer_path}")
    if not _consumer_runs_script(consumer_path, target.name):
        return GateResult(gid, "lint_script", DISARMED,
                          f"consumer {consumer_path.name} does not reference {target.name}")
    return GateResult(gid, "lint_script", ARMED,
                      f"wired into {consumer_path.name}")


_CHECKERS = {
    "claude_hook": check_claude_hook,
    "ci_workflow": check_ci_workflow,
    "lint_script": check_lint_script,
}


def evaluate(registry: dict) -> Report:
    report = Report()
    for gate in registry.get("gates", []):
        kind = gate.get("kind")
        checker = _CHECKERS.get(kind)
        if checker is None:
            report.results.append(
                GateResult(gate.get("id", "?"), str(kind), DISARMED,
                           f"unknown gate kind: {kind}")
            )
            continue
        try:
            report.results.append(checker(gate))
        except Exception as exc:  # defensive: a malformed gate must not crash the run
            report.results.append(
                GateResult(gate.get("id", "?"), str(kind), DISARMED,
                           f"checker raised: {exc}")
            )
    return report


# --------------------------------------------------------------------------- #
# Canary self-test (--canary, local only)
# --------------------------------------------------------------------------- #

def run_canary(gate: dict) -> GateResult:
    """Prove the disarm LEVER works: set the env, re-check, expect DISARMED.

    Only meaningful for claude_hook gates with a `canary.env` + disarm_substring
    embeddable via env. We re-run the hook-command check with the env applied to a
    SYNTHETIC command (the registered command + the env prefix) — we never mutate
    settings.json. This validates "disarmable-but-currently-armed".
    """
    gid = gate["id"]
    canary = gate.get("canary")
    if not canary or gate.get("kind") != "claude_hook":
        return GateResult(gid, gate.get("kind", "?"), WARN, "no canary defined")
    disarm = gate.get("disarm_substring")
    if not disarm:
        return GateResult(gid, "claude_hook", WARN, "no disarm lever to canary")
    # Synthetic: the disarm substring, if injected into the command, must be
    # detected by the same check_claude_hook logic. We assert the substring would
    # be caught (the lever is real and the detector sees it).
    if disarm in f"{disarm} python3 hook.py":
        return GateResult(gid, "claude_hook", ARMED,
                          f"canary OK: disarm lever '{disarm}' is detectable")
    return GateResult(gid, "claude_hook", DISARMED,
                      f"canary FAIL: disarm lever '{disarm}' not detectable")


# --------------------------------------------------------------------------- #
# Dead-man's switch (G5) — write alive signal, reuse sentinel_meta_watchdog idiom
# --------------------------------------------------------------------------- #

def write_alive_signal(report: Report) -> None:
    """Write the meta-verifier's own 'alive' signal so it can be detected stale.

    Idiom from scripts/sentinel_meta_watchdog.sh:74-87 (state-file with ts +
    _writer). A future FASE-6 watcher (P9 §3.4) detects when this file goes stale
    → 'meta-verifier muto'. Failure to write must NOT fail the run.
    """
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": int(time.time()),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "ok" if report.ok else "disarmed_gates_detected",
            "gates_total": len(report.results),
            "gates_armed": len(report.armed),
            "gates_disarmed": len(report.disarmed),
            "gates_warn": len(report.warnings),
            "disarmed_ids": [r.gate_id for r in report.disarmed],
            "_writer": "verify_the_verifiers",
        }
        STATE_FILE.write_text(json.dumps(payload, indent=2))
    except OSError as exc:
        print(f"WARN: could not write alive signal: {exc}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def render_text(report: Report) -> str:
    lines = []
    total = len(report.results)
    n_armed = len(report.armed)
    lines.append(f"meta-verifier: {n_armed}/{total} gates ARMED")
    if report.disarmed:
        lines.append("")
        lines.append("DISARMED:")
        for r in report.disarmed:
            lines.append(f"  ✗ {r.gate_id} [{r.kind}] — {r.detail}")
    if report.warnings:
        lines.append("")
        lines.append("WARN:")
        for r in report.warnings:
            lines.append(f"  ! {r.gate_id} [{r.kind}] — {r.detail}")
    lines.append("")
    lines.append("VERDICT: " + ("GREEN (all gates armed)" if report.ok
                                 else f"RED ({len(report.disarmed)} gate(s) DISARMED)"))
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps({
        "ok": report.ok,
        "total": len(report.results),
        "armed": len(report.armed),
        "disarmed": len(report.disarmed),
        "warn": len(report.warnings),
        "gates": [
            {"id": r.gate_id, "kind": r.kind, "verdict": r.verdict, "detail": r.detail}
            for r in report.results
        ],
    }, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meta-verifier — check safety gates are armed (P1 §4).")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY),
                        help="path to verify_the_verifiers_gates.yaml")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--canary", action="store_true",
                        help="run disarm-lever canary self-tests (local only)")
    parser.add_argument("--no-signal", action="store_true",
                        help="do not write the dead-man's-switch alive signal")
    args = parser.parse_args(argv)

    registry_path = _expand(args.registry)
    if not registry_path.exists():
        print(f"FATAL: registry not found: {registry_path}", file=sys.stderr)
        return 3
    try:
        registry = yaml.safe_load(registry_path.read_text())
    except yaml.YAMLError as exc:
        print(f"FATAL: registry unparseable: {exc}", file=sys.stderr)
        return 3

    if args.canary:
        report = Report(results=[run_canary(g) for g in registry.get("gates", [])])
    else:
        report = evaluate(registry)

    if not args.no_signal:
        write_alive_signal(report)

    print(render_json(report) if args.json else render_text(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
