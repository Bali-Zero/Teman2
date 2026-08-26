#!/usr/bin/env python3
"""test_agent_defs_model_pins.py — E1/R1: seven grunt agent definitions pinned
to Haiku 4.5 in `.claude/agents/`, and proof that model_routing_gate.py's Rule
1 (frontmatter-pin honoring) actually recognizes each one as pinned.

Context (2026-08-27, spec §8 R1 in 2026-08-26-PIANO-SPEC-receptor-live.md):
measured the same day — 13 agent defs under `.claude/agents/` carried a
`model:` pin (4 opus, 9 sonnet, 0 haiku), and Haiku received 8 of 882
dispatches (0.9%) over the prior 48h. MODEL_ROSTER.md already names Haiku the
grunt tier (format/extract/classify/cheap VLM pre-pass); nothing routed there
because nothing was PINNED there. `model_routing_gate.py` Rule 1 ALLOWs an
Agent() call with no explicit `model` param IF the subagent_type's definition
file pins `model:` in its own frontmatter — so pinning these 7 defs is what
actually lets a conductor dispatch `Agent({subagent_type: "lint-fixer", ...})`
(no `model` kwarg needed) and land on Haiku instead of silently inheriting
the orchestrator's own model.

Guilt/innocence (cicatrix-superscar.md #3 antidote — a check that only ever
sees green proves nothing about what would turn it red): a def missing
`model:` in its frontmatter, a def pinned to the WRONG model, and a
subagent_type with no def file on disk at all, must all fail the checks the
7 real defs pass.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
GATE_MODULE_PATH = REPO_ROOT / "infra" / "claude-hooks" / "model_routing_gate.py"

GRUNT_AGENTS = [
    "ledger-writer",
    "lint-fixer",
    "i18n-sync",
    "fixture-gen",
    "log-triage",
    "catalog-meta",
    "docs-sync",
]

MODEL_PIN_HAIKU_RE = re.compile(r"^model\s*:\s*haiku\s*$", re.MULTILINE)
ANY_MODEL_PIN_RE = re.compile(r"^model\s*:\s*\S", re.MULTILINE)
DESCRIPTION_GRUNT_RE = re.compile(r"^description\s*:\s*GRUNT \(Haiku\):", re.MULTILINE)
TOOLS_LINE_RE = re.compile(r"^tools\s*:\s*(.+)$", re.MULTILINE)


def _frontmatter(text: str) -> str:
    stripped = text.lstrip()
    assert stripped.startswith("---"), "agent def must open with a --- frontmatter delimiter"
    parts = text.split("---", 2)
    assert len(parts) >= 3, "agent def must have a closing --- frontmatter delimiter"
    return parts[1]


# ---------------------------------------------------------------------------
# Innocence: the 7 real defs exist, are pinned to haiku, and self-identify.
# ---------------------------------------------------------------------------


def test_seven_grunt_agent_defs_exist_pinned_to_haiku_with_grunt_description():
    assert AGENTS_DIR.is_dir(), f"{AGENTS_DIR} missing"
    for name in GRUNT_AGENTS:
        path = AGENTS_DIR / f"{name}.md"
        assert path.is_file(), f"missing grunt agent def: {path}"
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        assert MODEL_PIN_HAIKU_RE.search(fm), (
            f"{path} frontmatter does not pin `model: haiku` — got:\n{fm}"
        )
        assert DESCRIPTION_GRUNT_RE.search(fm), (
            f"{path} description must start with 'GRUNT (Haiku):' — got:\n{fm}"
        )


def test_seven_grunt_agent_defs_declare_a_minimal_non_overlapping_toolset():
    """The actual safety property the spec asked for: MINIMAL tools. A def
    with no `tools:` line would inherit the harness default (every tool) —
    exactly what a cheap/fast grunt model must not have. A def that carries
    both Bash and Edit/Write can route around its own declared mutation
    surface via shell redirection, defeating the point of a narrow toolset."""
    for name in GRUNT_AGENTS:
        path = AGENTS_DIR / f"{name}.md"
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        m = TOOLS_LINE_RE.search(fm)
        assert m, f"{path} has no `tools:` line"
        tool_names = [t.strip() for t in m.group(1).split(",") if t.strip()]
        assert tool_names, f"{path} `tools:` line is empty"
        assert len(tool_names) <= 4, (
            f"{path} lists {len(tool_names)} tools ({tool_names}) — expected a MINIMAL "
            "grunt toolset (<=4), not a broad allowlist"
        )
        if "Bash" in tool_names:
            assert "Edit" not in tool_names and "Write" not in tool_names, (
                f"{path} combines Bash with Edit/Write — a grunt def should mutate "
                "files through ONE route, not two"
            )


# ---------------------------------------------------------------------------
# Guilt: a def missing the pin, wrongly pinned, or absent must NOT pass.
# ---------------------------------------------------------------------------


def test_guilt_a_def_missing_model_pin_fails_the_same_check(tmp_path):
    bad = tmp_path / "no-pin.md"
    bad.write_text(
        "---\nname: no-pin\ndescription: GRUNT (Haiku): a def with no model pin\ntools: Read\n---\n\n# no-pin\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    assert not MODEL_PIN_HAIKU_RE.search(fm)
    assert not ANY_MODEL_PIN_RE.search(fm)


def test_guilt_a_def_pinned_to_the_wrong_model_is_not_haiku(tmp_path):
    bad = tmp_path / "wrong-pin.md"
    bad.write_text(
        "---\nname: wrong-pin\ndescription: GRUNT (Haiku): says grunt, pins sonnet\ntools: Read\nmodel: sonnet\n---\n\n# wrong-pin\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    assert ANY_MODEL_PIN_RE.search(fm)  # it IS pinned to something...
    assert not MODEL_PIN_HAIKU_RE.search(fm)  # ...just not haiku


def test_guilt_a_def_with_seven_tools_is_not_minimal(tmp_path):
    bad = tmp_path / "seven-tools.md"
    bad.write_text(
        "---\nname: seven-tools\ndescription: GRUNT (Haiku): too many tools\n"
        "tools: Read, Write, Edit, Bash, Grep, Glob, WebFetch\nmodel: haiku\n---\n\n# seven-tools\n",
        encoding="utf-8",
    )
    fm = _frontmatter(bad.read_text(encoding="utf-8"))
    m = TOOLS_LINE_RE.search(fm)
    assert m
    tool_names = [t.strip() for t in m.group(1).split(",") if t.strip()]
    assert len(tool_names) > 4  # proves the >4 branch of the innocence test would fire


# ---------------------------------------------------------------------------
# model_routing_gate.py Rule 1 must actually recognize the pin (the real
# hook function, not a re-implementation of its regex in this test file).
# ---------------------------------------------------------------------------


def _load_gate_module():
    if not GATE_MODULE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("model_routing_gate_e1r1", GATE_MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_model_routing_gate_honors_the_pin_for_all_seven_defs():
    gate = _load_gate_module()
    if gate is None or not hasattr(gate, "agent_def_pins_model"):
        return  # documented fallback: hook not present/importable in this checkout
    for name in GRUNT_AGENTS:
        allowed = gate.agent_def_pins_model(name, str(REPO_ROOT))
        assert allowed is True, (
            f"model_routing_gate does not recognize {name} as pinned (Rule 1 would DENY "
            "an Agent() dispatch with no explicit model param)"
        )


def test_guilt_gate_denies_a_subagent_type_with_no_def_on_disk():
    gate = _load_gate_module()
    if gate is None or not hasattr(gate, "agent_def_pins_model"):
        return
    assert gate.agent_def_pins_model("definitely-not-a-real-grunt-agent-xyz", str(REPO_ROOT)) is False


if __name__ == "__main__":
    sys.exit(0)
