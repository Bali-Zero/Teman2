"""Tests for the governed agy Swarm Commander wrapper."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_swarm_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "agy_swarm_commander.py"
    spec = importlib.util.spec_from_file_location("agy_swarm_commander_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


swarm = _load_swarm_module()


def test_model_allowlist_resolves_new_gemini_high_models() -> None:
    assert swarm.resolve_model("flash-high") == "Gemini 3.5 Flash (High)"
    assert swarm.resolve_model("pro-high") == "Gemini 3.1 Pro (High)"


def test_unknown_model_is_rejected() -> None:
    try:
        swarm.resolve_model("random-model")
    except ValueError as exc:
        assert "Unsupported agy model" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("unknown model was not rejected")


def test_build_prompt_contains_kg_and_identity_guardrails() -> None:
    prompt = swarm.build_prompt("swarm", "Map public official source lanes.")
    assert "Do not promote knowledge-graph nodes" in prompt
    assert "merge identities" in prompt
    assert "private social accounts" in prompt
    assert "Source/tool plan" in prompt


def test_destructive_prompt_is_blocked() -> None:
    try:
        swarm.validate_prompt("run rm -rf /tmp/example")
    except ValueError as exc:
        assert "destructive" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("destructive prompt was not blocked")


def test_dry_run_audits_without_raw_prompt(tmp_path: Path) -> None:
    raw_prompt = "Map official public sources for Bali immigration officers."
    result = swarm.run_commander(
        model_key="flash-high",
        mode="fast-review",
        prompt=raw_prompt,
        timeout_s=10,
        agy_bin="agy",
        output_dir=tmp_path,
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["command_preview"][-1] == "<prompt omitted>"
    assert raw_prompt not in json.dumps(result)

    audit_path = tmp_path / "agy-swarm-audit.jsonl"
    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 1
    audit = json.loads(audit_lines[0])
    assert audit["model"] == "Gemini 3.5 Flash (High)"
    assert audit["mode"] == "fast-review"
    assert audit["dry_run"] is True
    assert raw_prompt not in audit_lines[0]
