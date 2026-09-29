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


def test_no_deny_when_verdict_shaped_or_verdict_axis_missing():
    assert G.decide(OPUS, _ans(needs=0.04, verdict=0.9), denied_before=False)["action"] != "deny"
    assert G.decide(OPUS, _ans(needs=0.04, verdict=0.3), denied_before=False)["action"] != "deny"
    no_axis = _ans(needs=0.04)
    del no_axis["is_verdict"]
    assert G.decide(OPUS, no_axis, denied_before=False)["action"] != "deny"


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


def test_redact_masks_credentials_tokens_and_names_keeps_technical_runs():
    s = G.redact("token=abc123XYZ authorization: Bearer x api_key = k9 sha 3f2a9c0d1e4b5a6f7d8c9b0a1f2e3d4c5b6a7f8e "
                 "Binary Search Tree and Abstract Syntax Tree for Ibu Sari Dewi and Type Safe System One")
    assert "abc123XYZ" not in s and "Bearer x" not in s and "k9" not in s and "[SECRET]" in s
    assert "3f2a9c0d1e4b5a6f7d8c9b0a1f2e3d4c5b6a7f8e" not in s and "[TOKEN]" in s
    assert "Binary Search Tree" in s and "Abstract Syntax Tree" in s and "Type Safe System One" in s
    assert "Sari" not in s and "Dewi" not in s


def _straddle(head_len: int, token: str, filler: str = "x") -> str:
    """Place `token` (space-delimited, as in any real prompt) so that the cut
    at head_len falls in its middle."""
    start = head_len - len(token) // 2 - 1
    return filler * start + " " + token + " " + filler * 3000


TOKENS = ("mario.rossi@example.id", "tok_" + "A" * 33, "Giovanni Bianchi")


def test_redact_then_clip_never_splits_a_token_at_the_head_cut():
    H, T = G.HEAD_CHARS, G.TAIL_CHARS
    for token in TOKENS:
        out = G.redact_then_clip(_straddle(H, token), H, T)
        assert token not in out and token[: len(token) // 2] not in out.replace("[...]", "")
        assert "rossi" not in out and "Bianchi" not in out and "AAAA" not in out


def test_redact_then_clip_never_splits_a_token_at_the_tail_cut():
    H, T = G.HEAD_CHARS, G.TAIL_CHARS
    for token in TOKENS:
        text = "x" * (H + 3000) + " " + token + " " + "x" * (T - len(token) // 2 - 1)
        out = G.redact_then_clip(text, H, T)
        assert token not in out and "rossi" not in out and "Bianchi" not in out and "AAAA" not in out
        assert len(out) <= H + T + len("\n[...]\n")


def test_redact_then_clip_survives_masks_shrinking_the_head_by_more_than_any_margin():
    # gate r3: with windowed redaction, >512 chars of shrinkage before the cut
    # slid the cut past the margin. Redacting everything first has no margin.
    H, T = G.HEAD_CHARS, G.TAIL_CHARS
    shrink = ("tok_" + "A" * 60 + " ") * 40          # 40 masks × ~58 chars shrink ≈ 2.3k
    text = shrink + "x" * (H + 512 - len(shrink) - 8) + " Giovanni Bianchi " + "x" * 3000
    out = G.redact_then_clip(text, H, T)
    assert "Bianchi" not in out and "Giovanni" not in out and "AAAA" not in out


def test_redact_is_linear_on_pathological_inputs():
    import time
    for txt in ("a" * 200_000, "a." * 100_000, "+62 " * 50_000, "Aaa " * 50_000, "a@" * 100_000, "token=x " * 30_000):
        t0 = time.process_time()
        G.redact(txt)
        assert time.process_time() - t0 < 1.5  # CPU time: immune to machine load (gate r4 nit)


def test_redact_masks_short_bearer_whole():
    s = G.redact("Authorization: Bearer abc.def then curl")
    assert "abc.def" not in s and "[SECRET]" in s and "curl" in s


def test_deadline_is_a_base_exception_not_swallowed_by_except_exception():
    assert issubclass(G._Deadline, BaseException) and not issubclass(G._Deadline, Exception)
    try:
        try:
            G._raise_deadline()
        except Exception:  # noqa: BLE001 — this is the swallow we prove impossible
            raise AssertionError("swallowed")
    except G._Deadline:
        pass


def test_family_is_anchored_not_substring():
    assert G._family("haiku-opus") == "haiku"
    assert G._family("claude-opus-5-5") == "opus" and G._family("sonnet") == "sonnet"
    assert G._family("opusish") is None and G._family("inherit") is None and G._family("fable") is None


def test_key_self_load_reads_only_that_variable_and_never_exports():
    def run(content: str, chmod: int = 0o600) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp, "secrets.env")
            f.write_bytes(content.encode("utf-8"))
            os.chmod(f, chmod)
            env = {**os.environ, "NUZANTARA_SECRETS_FILE": str(f)}
            env.pop("TYPESAFE_API_KEY", None)
            code = ("import importlib.util,os,json;s=importlib.util.spec_from_file_location('g',%r);"
                    "g=importlib.util.module_from_spec(s);s.loader.exec_module(g);"
                    "print(json.dumps([g._load_key_into_own_env(),'OTHER_SECRET' in os.environ,"
                    "os.environ.get('TYPESAFE_API_KEY')]))" % str(HOOK))
            p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
            assert p.returncode == 0, p.stdout + p.stderr
            return json.loads(p.stdout)

    loaded, other, value = run("export OTHER_SECRET='zzz'\nexport TYPESAFE_API_KEY='k-synthetic-1'\n")
    assert (loaded, other, value) == (True, False, "k-synthetic-1")

    assert run("nothing here\n")[0] is False

    loaded, _, value = run("TYPESAFE_API_KEY='first'\nTYPESAFE_API_KEY='second'\n")
    assert loaded is True and value == "second"

    assert run("TYPESAFE_API_KEY_OLD='zzz'\n")[0] is False
    assert run("TYPESAFE_API_KEY=\n")[0] is False

    loaded, _, value = run("TYPESAFE_API_KEY='k-crlf'\r\n")
    assert loaded is True and value == "k-crlf"

    loaded, _, value = run("export\t\tTYPESAFE_API_KEY='k2'\n")
    assert loaded is True and value == "k2"

    loaded, _, value = run("TYPESAFE_API_KEY=k3 # rotated\n")
    assert loaded is True and value == "k3"

    assert run("TYPESAFE_API_KEY='k-perm'\n", chmod=0o644)[0] is False


def test_gate_run_never_prints_or_stores_the_key():
    secret = "k-synthetic-never-seen"
    with tempfile.TemporaryDirectory() as tmp:
        secrets_file = pathlib.Path(tmp, "secrets.env")
        secrets_file.write_text(f"TYPESAFE_API_KEY='{secret}'\n")
        os.chmod(secrets_file, 0o600)
        state_dir = pathlib.Path(tmp, "state")
        env = {**os.environ, "NUZANTARA_SECRETS_FILE": str(secrets_file),
               "JEV_DISPATCH_GATE_STATE": str(state_dir),
               "JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans(conf=0.7)),
               "JEV_DISPATCH_GATE": "enforce"}
        env.pop("TYPESAFE_API_KEY", None)
        payload = {"tool_name": "Agent", "tool_input": OPUS}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                           capture_output=True, text=True, env=env, timeout=30)
        assert p.returncode == 0
        assert secret not in p.stdout and secret not in p.stderr
        receipts = state_dir / "receipts.jsonl"
        text = receipts.read_text() if receipts.exists() else ""
        assert secret not in text
        rows = [json.loads(x) for x in text.splitlines()]
        assert rows and rows[-1]["action"] == "allow"
        assert isinstance(rows[-1]["repo_redactor"], bool)


def test_report_includes_by_repo_redactor():
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = pathlib.Path(tmp)
        (state_dir / "receipts.jsonl").write_text(
            json.dumps({"action": "allow", "repo_redactor": True}) + "\n"
            + json.dumps({"action": "skip", "repo_redactor": False}) + "\n"
        )
        env = {**os.environ, "JEV_DISPATCH_GATE_STATE": str(state_dir)}
        p = subprocess.run([sys.executable, str(HOOK), "--report"], capture_output=True, text=True, env=env)
        assert p.returncode == 0, p.stdout + p.stderr
        out = json.loads(p.stdout)
        assert out["by_repo_redactor"] == {"True": 1, "False": 1}


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


def test_hook_subprocess_unwritable_state_never_denies():
    with tempfile.TemporaryDirectory() as tmp:
        blocker = pathlib.Path(tmp, "file")
        blocker.write_text("x")
        env = {**os.environ, "JEV_DISPATCH_GATE_STATE": str(blocker / "state"),
               "JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans(needs=0.02, tier="grunt")), "JEV_DISPATCH_GATE": "enforce"}
        for _ in range(3):
            p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": "Agent", "tool_input": OPUS}),
                               capture_output=True, text=True, env=env)
            assert p.returncode == 0
            assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_hook_subprocess_parallel_distinct_dispatches_each_denied_exactly_once():
    from concurrent.futures import ThreadPoolExecutor
    fake = json.dumps(_ans(needs=0.02, tier="grunt"))
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "JEV_DISPATCH_GATE_STATE": tmp, "JEV_DISPATCH_GATE_FAKE_ANSWERS": fake, "JEV_DISPATCH_GATE": "enforce"}
        payloads = [json.dumps({"tool_name": "Agent", "tool_input": {**OPUS, "prompt": f"lookup {i}"}}) for i in range(12)]

        def run(p):
            return json.loads(subprocess.run([sys.executable, str(HOOK)], input=p, capture_output=True, text=True, env=env).stdout)["hookSpecificOutput"]["permissionDecision"]

        with ThreadPoolExecutor(12) as ex:
            first = list(ex.map(run, payloads))
            second = list(ex.map(run, payloads))
    assert first.count("deny") == 12 and second.count("deny") == 0


def test_hook_subprocess_malformed_env_still_exit_0():
    out, rows = _run({"tool_name": "Agent", "tool_input": OPUS},
                     {"JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans()), "JEV_DISPATCH_GATE_DEADLINE_S": "abc"})
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "allow" and rows[-1]["action"] == "downgrade"


def test_hook_subprocess_huge_prompt_is_bounded():
    import time
    t0 = time.time()
    out, rows = _run({"tool_name": "Agent", "tool_input": {**OPUS, "prompt": "a" * 200_000}},
                     {"JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans()), "JEV_DISPATCH_GATE": "enforce"})
    assert time.time() - t0 < 4 and rows[-1]["action"] == "downgrade" and rows[-1]["state_chars"] < 8000


def test_hook_subprocess_malformed_stdin_is_silent():
    p = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True,
                       env={**os.environ, "JEV_DISPATCH_GATE_STATE": tempfile.mkdtemp()})
    assert p.returncode == 0 and p.stdout.strip() == ""


def _fake_venv_script(tmp: pathlib.Path) -> pathlib.Path:
    script = tmp / "fake_venv_python"
    script.write_text(
        "#!/bin/sh\n"
        'echo "REEXEC_MARKER reexec_env=${JEV_DISPATCH_GATE_REEXEC:+SET} argc=$# arg1=$(basename "$1")"\n'
        "exit 0\n"
    )
    script.chmod(0o755)
    return script


def test_reexec_guilt_execs_under_fake_venv_with_hook_path_as_arg1():
    with tempfile.TemporaryDirectory() as tmp:
        script = _fake_venv_script(pathlib.Path(tmp))
        env = {**os.environ, "JEV_DISPATCH_GATE_FORCE_REEXEC_TEST": "1",
               "JEV_DISPATCH_GATE_VENV_PYTHON": str(script)}
        p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env)
        assert p.returncode == 0
        assert "REEXEC_MARKER reexec_env=SET" in p.stdout
        assert "arg1=jev_dispatch_gate.py" in p.stdout


def test_reexec_innocence_nonexistent_venv_python_fails_open():
    env = {**os.environ, "JEV_DISPATCH_GATE_FORCE_REEXEC_TEST": "1",
           "JEV_DISPATCH_GATE_VENV_PYTHON": "/nonexistent/python"}
    p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env)
    assert p.returncode == 0 and p.stdout == "" and p.stderr == ""


def test_reexec_innocence_already_reexeced_never_loops():
    with tempfile.TemporaryDirectory() as tmp:
        script = _fake_venv_script(pathlib.Path(tmp))
        env = {**os.environ, "JEV_DISPATCH_GATE_REEXEC": "1", "JEV_DISPATCH_GATE_FORCE_REEXEC_TEST": "1",
               "JEV_DISPATCH_GATE_VENV_PYTHON": str(script)}
        p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env)
        assert p.returncode == 0 and "REEXEC_MARKER" not in p.stdout


def test_reexec_innocence_importable_redactor_skips_reexec():
    with tempfile.TemporaryDirectory() as tmp:
        script = _fake_venv_script(pathlib.Path(tmp))
        env = {**os.environ, "JEV_DISPATCH_GATE_VENV_PYTHON": str(script)}
        env.pop("JEV_DISPATCH_GATE_FORCE_REEXEC_TEST", None)
        p = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env)
        assert p.returncode == 0 and "REEXEC_MARKER" not in p.stdout


def test_receipt_and_report_include_interpreter_path():
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "JEV_DISPATCH_GATE_STATE": tmp,
               "JEV_DISPATCH_GATE_FAKE_ANSWERS": json.dumps(_ans()), "JEV_DISPATCH_GATE": "enforce"}
        payload = {"tool_name": "Agent", "tool_input": OPUS}
        p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
        assert p.returncode == 0
        rows = [json.loads(x) for x in pathlib.Path(tmp, "receipts.jsonl").read_text().splitlines()]
        assert rows[-1]["interpreter"] == "path"
        rp = subprocess.run([sys.executable, str(HOOK), "--report"], capture_output=True, text=True, env=env)
        assert rp.returncode == 0, rp.stdout + rp.stderr
        assert json.loads(rp.stdout)["by_interpreter"] == {"path": 1}


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
