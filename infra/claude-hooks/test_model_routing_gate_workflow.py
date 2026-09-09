#!/usr/bin/env python3
"""Workflow-tool coverage tests for model_routing_gate.py (added 2026-09-08).

Rule 1 ("no subagent spawn without an explicit `model`") previously inspected
only the `Agent` tool. A multi-agent orchestration script run via the
`Workflow` tool calls `agent(prompt, {model: ...})` internally, and those
calls were invisible to this hook — measured 2026-09-05, a Workflow run
spawned 35 agents that all inherited the session model (claude-fable-5-1,
3.5M tokens). `.claude/skills/workflow/SKILL.md` §1.1 already states the
rule ("PIN model: ON EVERY agent() CALL"); this file pins the enforcement.

Same discipline as its sibling `test_model_routing_gate_floor.py`: real
`assert` (pytest-collectible AND directly runnable), the hook invoked as a
subprocess so this is a black-box test of the actual exit code / stderr the
harness would see, never an import of internal functions.

Run directly:
    python3 infra/claude-hooks/test_model_routing_gate_workflow.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "model_routing_gate.py"


def run_gate(payload, home=None):
    """Invoke the real hook via subprocess. Returns (rc, stdout, stderr).
    HOME is isolated to a throwaway tempdir per call (unless `home` is
    given) so no real `~/.claude/agents/*.md` frontmatter pin leaks in."""
    tmp = pathlib.Path(home) if home else pathlib.Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    out = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return out.returncode, out.stdout, out.stderr


def _workflow(script=None, script_path=None, name=None, cwd=None):
    tool_input = {}
    if script is not None:
        tool_input["script"] = script
    if script_path is not None:
        tool_input["scriptPath"] = script_path
    if name is not None:
        tool_input["name"] = name
    payload = {"tool_name": "Workflow", "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def _agent(description="do the thing", model=None, subagent_type=None):
    tool_input = {"description": description}
    if model is not None:
        tool_input["model"] = model
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return {"tool_name": "Agent", "tool_input": tool_input}


# ── guilt: unpinned agent() calls in a Workflow script deny ────────────────


def test_workflow_all_pinned_allows():
    script = (
        "const a = await agent('do angle A', {model: \"sonnet\", label: \"a\"});\n"
        "const b = await agent('do angle B', {label: \"b\", model: 'haiku'});\n"
    )
    rc, out, err = run_gate(_workflow(script=script))
    assert rc == 0, f"every agent() carries model -> allow: rc={rc} err={err!r}"
    assert out == "" and err == ""


def test_workflow_one_unpinned_call_denies_with_line():
    script = (
        "const a = await agent('do angle A', {model: \"sonnet\"});\n"
        "const b = await agent('do angle B', {label: \"b\"});\n"
    )
    rc, out, err = run_gate(_workflow(script=script))
    assert rc == 2, f"one unpinned agent() must deny: rc={rc} err={err!r}"
    assert "L2" in err, f"deny message must name the offending line: {err!r}"
    assert "L1" not in err, f"the pinned call (line 1) must not be listed as an offender: {err!r}"
    assert "§1.1" in err
    assert out == "", f"deny path prints to stderr only: {out!r}"


def test_workflow_scriptpath_variant():
    tmp = tempfile.mkdtemp()
    repo = pathlib.Path(tmp) / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    script_file = repo / "wf.js"
    script_file.write_text("await agent('x', {});\n")
    rc, out, err = run_gate(
        _workflow(script_path="wf.js", cwd=str(repo)), home=tmp,
    )
    assert rc == 2, f"scriptPath is read and scanned: rc={rc} err={err!r}"
    assert "L1" in err, err


def test_workflow_scriptpath_unreadable_allows_fail_open():
    tmp = tempfile.mkdtemp()
    rc, out, err = run_gate(
        _workflow(script_path="does/not/exist.js", cwd=tmp), home=tmp,
    )
    assert rc == 0, f"unreadable scriptPath must fail open, not crash/deny: rc={rc} err={err!r}"
    assert "unreadable" in err.lower() or "fail-open" in err.lower()


def test_workflow_name_only_allows():
    rc, out, err = run_gate(_workflow(name="verify-template"))
    assert rc == 0, f"a name-only saved/builtin workflow cannot be inspected -> allow: rc={rc} err={err!r}"


def test_workflow_nested_braces_in_options_allow():
    script = (
        "const r = await agent('x', {model: \"opus\", "
        "schema: {type: \"object\", properties: {a: {type: \"string\"}}}});\n"
    )
    rc, out, err = run_gate(_workflow(script=script))
    assert rc == 0, f"nested braces inside options must not confuse the scan: rc={rc} err={err!r}"


def test_workflow_agent_call_inside_comment_is_ignored():
    script = (
        "// example: agent('x', {})\n"
        "const r = await agent('y', {model: \"sonnet\"});\n"
    )
    rc, out, err = run_gate(_workflow(script=script))
    assert rc == 0, (
        f"an agent( occurrence inside a // comment must not be scanned as a call site: "
        f"rc={rc} err={err!r}"
    )


def test_workflow_agent_call_inside_comment_does_not_mask_a_real_offender():
    script = (
        "// example: agent('x', {})\n"
        "const r = await agent('y', {});\n"
    )
    rc, out, err = run_gate(_workflow(script=script))
    assert rc == 2, f"the real (uncommented) unpinned call must still deny: rc={rc} err={err!r}"
    assert "L2" in err, err


# ── regression: the Agent-tool path is unchanged ────────────────────────────


def test_agent_tool_unpinned_still_denies():
    rc, out, err = run_gate(_agent(model=None))
    assert rc == 2, f"Rule 1 on the Agent tool must still deny with no model: rc={rc} err={err!r}"
    assert "model_routing_gate" in err


def test_agent_tool_pinned_still_allows():
    rc, out, err = run_gate(_agent(model="sonnet"))
    assert rc == 0, f"Rule 1 on the Agent tool must still allow an explicit model: rc={rc} err={err!r}"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]


def main():
    failures = []
    for t in TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures.append(t.__name__)
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(TESTS) - len(failures)}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
