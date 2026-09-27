"""Guilt + innocence for infra/claude-hooks/jev_dispatch_gate.py (superscar #3).

Pure decision table first, then the real hook file as a subprocess exactly as
Claude Code invokes it, through the JEV_DISPATCH_GATE_FAKE_ANSWERS seam (no
network). Collected by scripts-tests-sweep.yml; also `python3 <file>`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK = ROOT / "infra" / "claude-hooks" / "jev_dispatch_gate.py"


def _mod():
    spec = importlib.util.spec_from_file_location("jev_dispatch_gate", str(HOOK))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = _mod()
OPUS = {"description": "Implement parser", "prompt": "Implement the CSV parser with tests.", "model": "opus"}


def _ans(needs=0.9, tier="implementer", conf=0.95, verdict=0.02):
    return {"needs_agent": {"type": "noul", "noul": needs},
            "tier": {"type": "choice", "choice": tier, "confidence": conf},
            "is_verdict": {"type": "noul", "noul": verdict}}


def test_deny_single_lookup_guilt():
    d = G.decide(OPUS, _ans(needs=0.04), denied_before=False)
    assert d["action"] == "deny" and "re-issue" in d["reason"]


def test_deny_is_one_shot_innocence():
    assert G.decide(OPUS, _ans(needs=0.04), denied_before=True)["action"] != "deny"


def test_no_deny_when_verdict_shaped():
    assert G.decide(OPUS, _ans(needs=0.04, verdict=0.9), denied_before=False)["action"] != "deny"


def test_downgrade_opus_implementer_to_sonnet():
    d = G.decide(OPUS, _ans(), False)
    assert (d["action"], d["model"]) == ("downgrade", "sonnet")


def test_downgrade_opus_grunt_to_haiku_and_sonnet_grunt_to_haiku():
    assert G.decide(OPUS, _ans(tier="grunt"), False)["model"] == "haiku"
    assert G.decide({**OPUS, "model": "sonnet"}, _ans(tier="grunt"), False)["model"] == "haiku"


def test_never_upgrade_never_touch_architect_or_unknown_model():
    assert G.decide({**OPUS, "model": "haiku"}, _ans(tier="implementer"), False)["action"] == "allow"
    assert G.decide(OPUS, _ans(tier="architect"), False)["action"] == "allow"
    assert G.decide({**OPUS, "model": "fable"}, _ans(tier="grunt"), False)["action"] == "allow"
    assert G.decide({k: v for k, v in OPUS.items() if k != "model"}, _ans(tier="grunt"), False)["action"] == "allow"


def test_low_confidence_or_verdict_blocks_downgrade():
    assert G.decide(OPUS, _ans(conf=0.7), False)["action"] == "allow"
    assert G.decide(OPUS, _ans(verdict=0.5), False)["action"] == "allow"


def test_no_opinion_and_malformed_probabilities_allow():
    assert G.decide(OPUS, None, False)["action"] == "allow"
    bad = _ans()
    bad["needs_agent"]["noul"] = True
    bad["tier"]["confidence"] = 1.5
    assert G.decide(OPUS, bad, False)["action"] == "allow"


def test_observe_mode_never_mutates():
    d = G.decide(OPUS, _ans(needs=0.03), False, mode="observe")
    assert d["action"] == "allow" and d["would"] == "deny"


def test_redact_masks_pii_keeps_paths_and_tech_pairs():
    s = G.redact("Mail Mario Rossi at mario@x.id, +62 812 3456 7890, ref 3171234567890001 "
                 "re scripts/agent_start.py and Bali Zero Visa Oracle")
    assert "[NAME]" in s and "[EMAIL]" in s and "[PHONE]" in s and "[NUM]" in s
    assert "Mario" not in s and "Rossi" not in s and "mario@" not in s
    assert "scripts/agent_start.py" in s and "Bali Zero" in s and "Visa Oracle" in s


def test_pii_shaped_detection():
    assert G.is_pii_shaped("attach the passport scan to the client record")
    assert G.is_pii_shaped("load client_id 7 dossier")
    assert not G.is_pii_shaped("fix the client-side JS bundle for the visa engine")


def _run(payload: dict, env: dict) -> tuple[str, list[dict]]:
    with tempfile.TemporaryDirectory() as tmp:
        e = {**os.environ, "JEV_DISPATCH_GATE_STATE": tmp, **env}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
                           text=True, env=e, timeout=30)
        assert p.returncode == 0, p.stderr
        rec = pathlib.Path(tmp, "receipts.jsonl")
        rows = [json.loads(x) for x in rec.read_text().splitlines()] if rec.exists() else []
        return p.stdout.strip(), rows


def test_hook_subprocess_deny_then_pass_and_receipt_has_no_prompt():
    fake = json.dumps(_ans(needs=0.02))
    payload = {"tool_name": "Agent", "session_id": "s1", "tool_use_id": "t1",
               "tool_input": {**OPUS, "prompt": "Count the files under infra/claude-hooks."}}
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "JEV_DISPATCH_GATE_STATE": tmp, "JEV_DISPATCH_GATE_FAKE_ANSWERS": fake,
               "JEV_DISPATCH_GATE": "enforce"}
        first = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=env)
        second = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=env)
        assert json.loads(first.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
        # the identical re-issue passes the deny; it may still be downgraded, never denied again
        assert json.loads(second.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"
        rows = [json.loads(x) for x in pathlib.Path(tmp, "receipts.jsonl").read_text().splitlines()]
        assert [r["action"] for r in rows] == ["deny", "downgrade"]
        assert "Count the files" not in pathlib.Path(tmp, "receipts.jsonl").read_text()


def test_hook_subprocess_downgrade_emits_updated_input():
    out, rows = _run({"tool_name": "Agent", "tool_input": OPUS},
                     {"JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans()), "JEV_DISPATCH_GATE": "enforce"})
    j = json.loads(out)
    assert j["hookSpecificOutput"]["updatedInput"]["model"] == "sonnet"
    assert j["hookSpecificOutput"]["updatedInput"]["prompt"] == OPUS["prompt"]
    assert rows[-1]["action"] == "downgrade" and rows[-1]["jev_status"] == "fake"


def test_hook_subprocess_innocence_bash_fork_pii_off_are_silent():
    fake = {"JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans(needs=0.01, tier="grunt"))}
    assert _run({"tool_name": "Bash", "tool_input": {"command": "ls"}}, fake)[0] == ""
    out, rows = _run({"tool_name": "Agent", "tool_input": {**OPUS, "subagent_type": "fork"}}, fake)
    assert out == "" and rows[-1]["skip"] == "fork"
    out, rows = _run({"tool_name": "Agent", "tool_input": {**OPUS, "prompt": "Read the passport scan of client_id 7"}}, fake)
    assert out == "" and rows[-1]["skip"] == "pii_shaped"
    out, rows = _run({"tool_name": "Agent", "tool_input": OPUS}, {**fake, "JEV_DISPATCH_GATE": "off"})
    assert out == "" and rows[-1]["skip"] == "off"
    out, rows = _run({"tool_name": "Agent", "tool_input": OPUS}, {**fake, "JEV_DISPATCH_GATE": "observe"})
    assert out == "" and rows[-1]["action"] == "allow" and rows[-1]["would"] == "deny"


def test_hook_subprocess_malformed_stdin_is_silent():
    p = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True,
                       env={**os.environ, "JEV_DISPATCH_GATE_STATE": tempfile.mkdtemp()})
    assert p.returncode == 0 and p.stdout.strip() == ""


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if failed else 0)
