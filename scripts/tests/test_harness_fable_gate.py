"""Tests for scripts/harness_fable_gate.py — the harness/fable-gate publisher.

This is a PUBLISHER, not a guard (it never accepts/rejects PR content — see
its own docstring: "no verdict logic inside"), so it is deliberately NOT
registered in infra/guard-conformance/registry.json alongside
evidence_pack_lint.py. These tests still pin the verdict->state mapping and
the CLI's --dry-run contract so a future edit can't quietly invert PASS/BLOCK.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from harness_fable_gate import VERDICT_STATE, build_description  # noqa: E402


def test_pass_maps_to_success():
    assert VERDICT_STATE["PASS"] == "success"


def test_pass_with_conditions_maps_to_success():
    assert VERDICT_STATE["PASS-WITH-CONDITIONS"] == "success"


def test_rework_build_maps_to_failure():
    assert VERDICT_STATE["REWORK-BUILD"] == "failure"


def test_rework_design_maps_to_failure():
    assert VERDICT_STATE["REWORK-DESIGN"] == "failure"


def test_block_maps_to_failure():
    assert VERDICT_STATE["BLOCK"] == "failure"


def test_exactly_five_legal_verdicts():
    """No sixth verdict can sneak in — the harness-v2 §6 grammar is closed."""
    assert set(VERDICT_STATE) == {
        "PASS", "PASS-WITH-CONDITIONS", "REWORK-BUILD", "REWORK-DESIGN", "BLOCK",
    }


def test_description_names_degraded_fallback():
    desc = build_description("PASS", degraded=True, extra=None, conditions_ref=None)
    assert "gate_degraded=fable->opus" in desc


def test_description_clean_pass_has_no_degraded_marker():
    desc = build_description("PASS", degraded=False, extra=None, conditions_ref=None)
    assert "gate_degraded" not in desc


def test_description_carries_conditions_ref_only_on_pwc():
    desc = build_description("PASS-WITH-CONDITIONS", degraded=False, extra=None,
                              conditions_ref="PENDING-ARMS.md#L900")
    assert "PENDING-ARMS.md#L900" in desc
    desc_pass = build_description("PASS", degraded=False, extra=None,
                                   conditions_ref="PENDING-ARMS.md#L900")
    assert "PENDING-ARMS.md#L900" not in desc_pass


def test_description_truncates_at_140_chars():
    long_extra = "x" * 300
    desc = build_description("PASS", degraded=False, extra=long_extra, conditions_ref=None)
    assert len(desc) <= 140
    assert desc.endswith("...")


def test_cli_dry_run_prints_gh_command_without_network():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "PASS", "--sha", "deadbeef", "--repo", "acme/example", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DRY-RUN:" in proc.stdout
    assert "state=success" in proc.stdout
    assert "context=harness/fable-gate" in proc.stdout
    assert "repos/acme/example/statuses/deadbeef" in proc.stdout


def test_cli_rejects_unknown_verdict():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "APPROVED", "--sha", "deadbeef", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode != 0


def test_cli_dry_run_marks_degraded_and_block_as_failure():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "harness_fable_gate.py"),
         "--verdict", "BLOCK", "--sha", "cafef00d", "--repo", "acme/example",
         "--degraded", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state=failure" in proc.stdout
    assert "gate_degraded" in proc.stdout
