#!/usr/bin/env python3
"""Guilt + innocence for context_window_guard.py (Zero, 2026-09-09 mandate:
force a fresh window past a role's context-percent threshold).

Isolates from the real machine's HOME the same way
test_model_routing_gate_floor.py already does for this directory's other
PreToolUse gates (`env["HOME"] = tmp`, verified 2026-08-22 round): the guard
imports two REAL HOME hooks by file path
(`~/.tokenaudit/hooks/context_hygiene.py`'s `last_context_tokens()` and
`~/.claude/hooks/precompact-mnemos.py`'s `parse_transcript_jsonl()`) — a CI
runner has neither file at the real `$HOME`, so every test here plants
VERBATIM copies of both under a temp HOME and points the subprocess at it.
Copying the two files verbatim (not reimplementing their logic) keeps this
corpus honest to the module's own "reuse, never reinvent" doctrine — it
exercises the real reused code, just relocated for hermeticity (cicatrix
scar #1, HOME-fork drift, cuts both ways: a test that assumes the operator's
own $HOME is the same trap in a different outfit).

Run directly (`python3 test_context_window_guard.py`) or under pytest.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HOOK = pathlib.Path(__file__).resolve().parent / "context_window_guard.py"

# Verbatim copy of ~/.tokenaudit/hooks/context_hygiene.py's estimator, as
# read from the real M5 file 2026-09-09 — only the parts context_window_guard.py
# actually imports/uses (`last_context_tokens`) need to be present and
# byte-faithful; the PostToolUse-only bits (main(), Read-size nudge) are
# harmless to keep alongside for fidelity.
CONTEXT_HYGIENE_PY = '''
import json, os, sys, collections
BIG_BYTES = 60_000
CTX_WARN = int(os.environ.get("TOKENAUDIT_CTX_WARN", "150000"))
NUDGE_EVERY = 20
STATE_DIR = os.path.expanduser("~/.tokenaudit/hooks/state")

def last_context_tokens(transcript_path: str) -> int:
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400_000)); tail = f.read().decode("utf-8", "ignore")
    except OSError:
        return 0
    for line in reversed(tail.splitlines()):
        if '"usage"' not in line or '"assistant"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        u = (r.get("message") or {}).get("usage") or {}
        if u:
            return int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0))
    return 0

def main() -> int:
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

# Verbatim copy of ~/.claude/hooks/precompact-mnemos.py's parser, as read
# from the real M5 file 2026-09-09 — same rationale as above.
PRECOMPACT_MNEMOS_PY = '''
import json
import pathlib
import re
import sys
import datetime

STATE_DIR = pathlib.Path.home() / ".claude" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def parse_transcript_jsonl(path):
    attempted = []
    successful = []
    changed_attempted = []
    changed_successful = []
    user_prompts_last = []
    in_progress_subjects = []
    risks = set()
    pending = {}
    try:
        for line in path.read_text(errors="ignore").splitlines()[-2000:]:
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = evt.get("content") or evt.get("message", {}).get("content")
            role = evt.get("role") or evt.get("message", {}).get("role", "")
            if role == "user" and isinstance(content, str):
                if 20 < len(content) < 500:
                    user_prompts_last.append(content)
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    if itype == "tool_use":
                        tid = item.get("id", "")
                        tname = item.get("name", "")
                        tinput = item.get("input", {})
                        pending[tid] = {"name": tname, "input": tinput}
                        if tname == "Bash":
                            cmd = tinput.get("command", "")
                            if cmd:
                                attempted.append(cmd[:200])
                        if tname in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                            fp = tinput.get("file_path", "")
                            if fp:
                                changed_attempted.append(fp)
                    elif itype == "tool_result":
                        tid = item.get("tool_use_id", "")
                        is_error = item.get("is_error", False)
                        result_content = item.get("content", "")
                        if tid in pending:
                            tool_use = pending.pop(tid)
                            result_str = str(result_content)[:500]
                            failed = (
                                is_error or
                                "exit code 1" in result_str.lower() or
                                "exit code 2" in result_str.lower() or
                                "error:" in result_str.lower()[:100] or
                                "traceback" in result_str.lower()
                            )
                            if not failed:
                                if tool_use["name"] == "Bash":
                                    successful.append(tool_use["input"].get("command", "")[:200])
                                elif tool_use["name"] in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                                    changed_successful.append(tool_use["input"].get("file_path", ""))
    except Exception as e:
        return {"parse_error": str(e), "attempted_commands": [], "successful_commands": []}
    text_blob = path.read_text(errors="ignore")[-50_000:]
    if "dirty worktree" in text_blob.lower():
        risks.add("Dirty worktree detected")
    if re.search(r'sk-ant-[a-z0-9]{20,}|sk-[a-zA-Z0-9]{40,}', text_blob):
        risks.add("Potential secret exposure")
    if "fly deploy" in text_blob.lower() and "failed" in text_blob.lower():
        risks.add("Failed Fly deploy mentioned")
    next_action = in_progress_subjects[-1] if in_progress_subjects else "(deduce from objective)"
    return {
        "objective": user_prompts_last[-3:],
        "attempted_commands": attempted[-30:],
        "successful_commands": successful[-30:],
        "attempted_file_changes": changed_attempted[-20:],
        "successful_file_changes": list(set(changed_successful))[-20:],
        "risks": sorted(risks),
        "next_action": next_action,
    }


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    transcript_path = payload.get("transcript_path", "")
    session_id = payload.get("session_id", "unknown")
    if not transcript_path:
        sys.exit(0)
    p = pathlib.Path(transcript_path)
    if not p.exists():
        sys.exit(0)
    parsed = parse_transcript_jsonl(p)
    handoff = {
        "session_id": session_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "transcript_path": transcript_path,
        **parsed,
    }
    out = STATE_DIR / f"precompact-handoff-{session_id}.json"
    out.write_text(json.dumps(handoff, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
'''


def _install_home_fixtures(home: pathlib.Path):
    hygiene = home / ".tokenaudit" / "hooks" / "context_hygiene.py"
    hygiene.parent.mkdir(parents=True, exist_ok=True)
    hygiene.write_text(CONTEXT_HYGIENE_PY)

    precompact = home / ".claude" / "hooks" / "precompact-mnemos.py"
    precompact.parent.mkdir(parents=True, exist_ok=True)
    precompact.write_text(PRECOMPACT_MNEMOS_PY)


def _usage_line(model, input_tokens, cache_write=0, cache_read=0):
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_write,
                "cache_read_input_tokens": cache_read,
            },
        },
    })


FILLER = json.dumps({"type": "assistant", "message": {"content": []}})


def _transcript(usage_line, filler_turns=35):
    return "\n".join([FILLER] * filler_turns + [usage_line]) + "\n"


def run_gate(tool_name, tool_input, tokens, model="claude-sonnet-5", filler_turns=35,
             env_extra=None, session_id="testsess", home=None):
    tmp = pathlib.Path(home) if home else pathlib.Path(tempfile.mkdtemp())
    tmp.mkdir(parents=True, exist_ok=True)
    _install_home_fixtures(tmp)

    transcript = _transcript(_usage_line(model, tokens), filler_turns=filler_turns)
    tp = tmp / "transcript.jsonl"
    tp.write_text(transcript)

    payload = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "transcript_path": str(tp),
        "session_id": session_id,
    }
    env = {"HOME": str(tmp), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("CONTEXT_GUARD_OFF", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                        capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr, tmp


# ── below threshold ─────────────────────────────────────────────────────────

def test_below_threshold_allows():
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=1_000)
    assert rc == 0, f"1K/200K should allow, got rc={rc} err={err!r}"


# ── above threshold: deny generic, allow mem save ───────────────────────────

def test_above_threshold_denies_bash():
    rc, _, err, _ = run_gate("Bash", {"command": "rm -rf /tmp/x"}, tokens=150_000)
    assert rc == 2, f"150K/200K (75%) > default 40% must deny, got rc={rc} err={err!r}"
    assert "context_window_guard" in err


def test_deny_message_has_evidence_line_and_self_cure_route():
    # Zero, 2026-09-09: a session denied at 85K could not cure the guard
    # because the fix (editing settings.json) is itself a tool call. The
    # deny message must now state its own evidence (model/window/why) and
    # the `! python3 ...` escape route that runs OUTSIDE PreToolUse hooks.
    rc, _, err, _ = run_gate("Bash", {"command": "rm -rf /tmp/x"}, tokens=150_000, model="claude-sonnet-5")
    assert rc == 2
    assert "finestra assunta" in err, f"evidence line (assumed window + why) missing: {err!r}"
    assert "claude-sonnet-5" in err, f"model string missing from evidence line: {err!r}"
    assert "finestra assunta 200K (default)" in err, f"window reason missing: {err!r}"
    assert "! python3 -c" in err, f"the `! python3` self-cure route must be printed verbatim: {err!r}"
    assert "CONTEXT_WINDOW_TOKENS" in err, f"self-cure one-liner must name the env var it sets: {err!r}"
    assert "CONTEXT_GUARD_OFF=1" in err, "kill switch route must still be last resort"


def test_deny_message_evidence_reflects_1m_and_evidence_rule_reasons():
    # The evidence line's WHY must match whichever branch _window_size()
    # actually took: [1m] label vs >200K-implies-1M vs env override.
    rc_1m, _, err_1m, _ = run_gate("Bash", {"command": "ls"}, tokens=150_000, model="claude-opus-5[1m]")
    assert rc_1m == 0, "150K/1M is below the 40% default threshold, must allow"
    rc_evidence, _, err_evidence, _ = run_gate(
        "Bash", {"command": "ls"}, tokens=458_000, model="claude-fable-5-1",
    )
    assert rc_evidence == 2
    assert "modello [1m]" not in err_evidence
    assert ">200K evidenza" in err_evidence, f"evidence-rule reason missing: {err_evidence!r}"

    rc_env, _, err_env, _ = run_gate(
        "Bash", {"command": "ls"}, tokens=300_000, model="claude-sonnet-5",
        env_extra={"CONTEXT_WINDOW_TOKENS": "50000"},
    )
    assert rc_env == 2, "300K/50K forced by env override must deny (600%)"
    assert "finestra assunta 50K (env override)" in err_env, f"env-override reason missing: {err_env!r}"


def test_above_threshold_allows_mem_save():
    rc, _, err, _ = run_gate(
        "Bash", {"command": "~/.claude/scripts/mem save discovery 'x' 7"}, tokens=150_000,
    )
    assert rc == 0, f"mem save must stay allowed above threshold, got rc={rc} err={err!r}"


def test_above_threshold_allows_sendmessage_and_taskstop():
    rc1, _, _, _ = run_gate("SendMessage", {"to": "peer", "message": "handoff"}, tokens=150_000)
    rc2, _, _, _ = run_gate("TaskStop", {}, tokens=150_000)
    assert rc1 == 0 and rc2 == 0


def test_above_threshold_denies_agent_and_unrelated_write():
    rc_agent, _, _, _ = run_gate("Agent", {"description": "keep going", "model": "sonnet"}, tokens=150_000)
    rc_write, _, _, _ = run_gate("Write", {"file_path": "/tmp/unrelated.txt", "content": "x"}, tokens=150_000)
    assert rc_agent == 2 and rc_write == 2


def test_above_threshold_allows_write_to_own_handoff_file():
    home = tempfile.mkdtemp()
    handoff = pathlib.Path(home) / ".claude" / "state" / "precompact-handoff-testsess.json"
    rc, _, err, _ = run_gate(
        "Write", {"file_path": str(handoff), "content": "{}"}, tokens=150_000, home=home,
    )
    assert rc == 0, f"write to own handoff file must be allowed, got rc={rc} err={err!r}"


# ── role thresholds ──────────────────────────────────────────────────────────

def test_imperator_threshold_20_denies_where_default_40_allows():
    # 50K/200K = 25%: below default 40% (allow), at/above imperator 20% (deny).
    rc_default, _, _, _ = run_gate("Bash", {"command": "ls"}, tokens=50_000)
    rc_imperator, _, _, _ = run_gate(
        "Bash", {"command": "ls"}, tokens=50_000, env_extra={"CONTEXT_GUARD_ROLE": "imperator"},
    )
    assert rc_default == 0, f"25% must allow under default 40% threshold, got {rc_default}"
    assert rc_imperator == 2, f"25% must deny under imperator 20% threshold, got {rc_imperator}"


def test_context_guard_pct_override():
    rc, _, _, _ = run_gate(
        "Bash", {"command": "ls"}, tokens=50_000, env_extra={"CONTEXT_GUARD_PCT": "10"},
    )
    assert rc == 2, "explicit CONTEXT_GUARD_PCT=10 must override the 40% default"


# ── kill switch ──────────────────────────────────────────────────────────────

def test_context_guard_off_allows():
    rc, _, _, _ = run_gate(
        "Bash", {"command": "rm -rf /"}, tokens=199_000, env_extra={"CONTEXT_GUARD_OFF": "1"},
    )
    assert rc == 0, "CONTEXT_GUARD_OFF=1 must allow unconditionally"


# ── grace period ─────────────────────────────────────────────────────────────

def test_grace_under_30_turns_allows():
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=199_000, filler_turns=5)
    assert rc == 0, f"fewer than 30 turns must allow regardless of pct, got rc={rc} err={err!r}"


# ── 1M window detection ──────────────────────────────────────────────────────

def test_1m_model_widens_window():
    # 150K tokens: 75% of the 200K default window (deny), but 15% of a 1M
    # window (allow, below the 40% default threshold) once the transcript's
    # own last assistant record names a `[1m]` model. (Below 200K on purpose:
    # above it the evidence rule widens the window regardless of the label —
    # see test_context_beyond_200k_is_evidence_of_a_1m_window.)
    rc_normal, _, _, _ = run_gate("Bash", {"command": "ls"}, tokens=150_000, model="claude-sonnet-5")
    rc_1m, _, _, _ = run_gate("Bash", {"command": "ls"}, tokens=150_000, model="claude-opus-5[1m]")
    assert rc_normal == 2, f"150K/200K must deny on a normal-window model, got {rc_normal}"
    assert rc_1m == 0, f"150K/1M must allow on a [1m] model, got {rc_1m}"


def test_context_beyond_200k_is_evidence_of_a_1m_window():
    # 458K tokens on a model string WITHOUT the [1m] suffix (the transcript never
    # carries it — measured 2026-09-09 on M5, denied at "229%"). A context that
    # already exceeds 200K cannot live in a 200K window: 458K/1M = 45.8% denies
    # at the 40% default, 300K/1M = 30% allows — neither is "229%".
    rc_300, _, _, _ = run_gate("Bash", {"command": "ls"}, tokens=300_000, model="claude-fable-5-1")
    rc_458, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=458_000, model="claude-fable-5-1")
    assert rc_300 == 0, f"300K on an unlabelled seat is >200K, so 1M window, 30% must allow; got {rc_300}"
    assert rc_458 == 2 and "229%" not in err, f"458K/1M = 46% must deny at 40%, got rc={rc_458} err={err!r}"


def test_context_window_tokens_env_override():
    rc, _, _, _ = run_gate(
        "Bash", {"command": "ls"}, tokens=300_000, model="claude-sonnet-5",
        env_extra={"CONTEXT_WINDOW_TOKENS": "1000000"},
    )
    assert rc == 0, "CONTEXT_WINDOW_TOKENS=1000000 must override the model-suffix detection too"


# ── handoff artifact ──────────────────────────────────────────────────────────

def test_handoff_file_written_once_above_threshold():
    home = tempfile.mkdtemp()
    rc, _, err, tmp = run_gate("Bash", {"command": "rm -rf /tmp/x"}, tokens=150_000, home=home)
    handoff = pathlib.Path(home) / ".claude" / "state" / "precompact-handoff-testsess.json"
    assert rc == 2
    assert handoff.is_file(), f"handoff must be written on first deny, err={err!r}"
    data = json.loads(handoff.read_text())
    assert data["session_id"] == "testsess"
    first_mtime = handoff.stat().st_mtime_ns

    # Second deny within the rate-limit window must not rewrite the file.
    rc2, _, _, _ = run_gate("Bash", {"command": "rm -rf /tmp/y"}, tokens=150_000, home=home)
    assert rc2 == 2
    assert handoff.stat().st_mtime_ns == first_mtime, "handoff must be rate-limited, not rewritten every deny"


def _run_all():
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures.append(name)
                print(f"FAIL {name}: {e}")
    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        sys.exit(1)
    print("\nAll tests passed.")


if __name__ == "__main__":
    _run_all()
