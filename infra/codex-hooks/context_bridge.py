#!/usr/bin/env python3
"""Codex-native context accounting, exact handoffs, and verification receipts.

Reuses Codex's stable hooks and app-server; never parses Claude transcripts,
guesses a model window, selects the latest handoff, or drives a GUI. State is
per CODEX_HOME and session. Raw prompts and command output are not copied to
bridge state; original instructions are read transiently from source rollouts.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import time
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from rpc import binary_path

VERSION = "1.0.0"
HANDSHAKE_SECONDS = 45
SELF = Path(__file__).resolve()
EVENTS = (
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "Stop",
)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()


def state_dir() -> Path:
    path = codex_home() / "state" / "nuzantara-context"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def state_path(sid: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", sid):
        raise ValueError("invalid session id")
    return state_dir() / (sid + ".json")


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(temp, "w", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        json.dump(value, stream, indent=2)
    temp.replace(path)


@contextmanager
def locked(sid: str) -> Iterator[tuple[Path, dict[str, Any]]]:
    path = state_path(sid)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load(path)
        yield path, state


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_fingerprint(cwd: str) -> str:
    """Bind evidence to HEAD, tracked diff, and untracked file CONTENTS."""
    h = hashlib.sha256()
    for args in (
        ("rev-parse", "HEAD"),
        ("diff", "HEAD", "--binary"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        result = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, timeout=10
        )
        if result.returncode:
            raise ValueError("not a git worktree")
        h.update(result.stdout)
        if args[0] == "ls-files":
            for name in result.stdout.split(b"\0"):
                if name:
                    path = Path(cwd) / os.fsdecode(name)
                    if path.is_file() and not path.is_symlink():
                        h.update(path.read_bytes())
    return h.hexdigest()


def records(path: str, tail: bool = False) -> Iterator[dict[str, Any]]:
    with open(path, "rb") as stream:
        if tail:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 2_000_000))
            if size > 2_000_000:
                stream.readline()
        for line in stream:
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    yield item
            except ValueError:
                continue


def measure(path: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for rec in records(path, tail=True):
        data = rec.get("payload") or {}
        if rec.get("type") == "turn_context":
            result.update(
                {
                    k: data[k]
                    for k in ("model", "effort", "approval_policy", "sandbox_policy")
                    if k in data
                }
            )
        if rec.get("type") == "event_msg" and data.get("type") == "token_count":
            info = data.get("info") or {}
            usage = info.get("last_token_usage") or {}
            window, used = info.get("model_context_window"), usage.get("total_tokens")
            if (
                isinstance(window, int)
                and window > 0
                and isinstance(used, int)
                and used >= 0
            ):
                result.update(used=used, window=window, observed=rec.get("timestamp"))
    return result


def prompts(paths: list[str]) -> str:
    """Read original user instructions in memory; don't serialize them to state."""
    messages: list[str] = []
    for path in paths:
        for rec in records(path):
            p = rec.get("payload") or {}
            value = None
            if rec.get("type") == "event_msg" and p.get("type") == "user_message":
                value = p.get("message")
            elif (
                rec.get("type") == "response_item"
                and p.get("type") == "message"
                and p.get("role") == "user"
            ):
                kinds = p.get("internal_chat_message_metadata_passthrough", {}).get(
                    "content_item_kinds", []
                )
                if kinds and "user.text" not in kinds:
                    continue  # Codex reloads its AGENTS/environment injections in the destination.
                content = p.get("content", [])
                if any(c.get("type") not in ("input_text", "text") for c in content):
                    raise ValueError("non-text mandate requires an explicit handoff")
                value = "\n".join(c.get("text", "") for c in content)
                if value.startswith(
                    (
                        "<environment_context>",
                        "# AGENTS.md instructions",
                        "<recommended_plugins>",
                    )
                ):
                    continue
            if isinstance(value, str) and value.startswith(
                "Continue the owner's authorized work from Codex session "
            ):
                continue  # The generated wrapper is not another owner instruction.
            if isinstance(value, str) and value and value not in messages:
                messages.append(value)
    if not messages:
        raise ValueError("original mandate unavailable")
    # Original mandate plus later steering, with an explicit bound on the new context.
    text = "\n\n".join(messages)  # Never silently discard intervening constraints.
    if len(text) > 32000:
        raise ValueError("mandate needs an explicit bounded handoff")
    return text


def continuation_command(runtime: dict[str, Any]) -> list[str]:
    """Use the official CLI identity and retain the source permission boundaries."""
    policy = runtime["sandbox_policy"]
    mode = policy.get("type")
    approval = runtime["approval_policy"]
    if mode not in (
        "read-only",
        "workspace-write",
        "danger-full-access",
    ) or approval not in ("never", "on-request"):
        raise ValueError("source policy cannot be preserved by CLI")
    args = [binary_path(), "--ask-for-approval", approval, "--sandbox", mode]
    fields = {
        "writable_roots",
        "network_access",
        "exclude_tmpdir_env_var",
        "exclude_slash_tmp",
    }
    if set(policy) - fields - {"type"}:
        raise ValueError("unknown source permission fields")
    if mode == "workspace-write":
        defaults = {
            "writable_roots": [],
            "network_access": False,
            "exclude_tmpdir_env_var": False,
            "exclude_slash_tmp": False,
        }
        for key, default in defaults.items():
            args += [
                "-c",
                "sandbox_workspace_write."
                + key
                + "="
                + json.dumps(policy.get(key, default)),
            ]
    elif mode == "read-only" and policy.get("network_access"):
        raise ValueError("read-only network policy requires interactive continuation")
    if runtime.get("effort"):
        args += ["-c", "model_reasoning_effort=" + json.dumps(runtime["effort"])]
    return [*args, "exec", "--model", runtime["model"], "--json", "-"]


def context_output(event: str, message: str, deny: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {"hookEventName": event, "additionalContext": message}
    if deny:
        body.update(permissionDecision="deny", permissionDecisionReason=message)
    return {"hookSpecificOutput": body}


def helper_call(
    payload: dict[str, Any], sid: str
) -> tuple[str, dict[str, Any] | None] | None:
    if payload.get("tool_name") not in ("Bash", "exec_command", "shell_command"):
        return None
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command", tool_input.get("cmd", ""))
    if isinstance(command, list):
        command = command[-1] if command else ""
    if not isinstance(command, str) or "$(" in command or "`" in command:
        return None
    first = command.split("\n", 1)[0]
    heredoc = re.search(r"\s+<<\s*'([A-Z_]+)'$", first)
    data = None
    try:
        if heredoc:
            parts = command.rstrip("\n").split("\n")
            if len(parts) < 3 or parts[-1] != heredoc[1]:
                return None
            data = json.loads("\n".join(parts[1:-1]))
            first = first[: heredoc.start()]
        elif "\n" in command.strip():
            return None
        args = shlex.split(first)
        if len(args) == 5:
            data = json.loads(args.pop())
        if len(args) != 4 or (data is not None and not isinstance(data, dict)):
            return None
        if (
            Path(args[0]).resolve() != Path(sys.executable).resolve()
            or args[1] != str(SELF)
            or args[2] not in ("checkpoint", "status", "verify")
            or args[3] != sid
        ):
            return None
        return args[2], data
    except ValueError:
        return None


def helper_command(payload: dict[str, Any], sid: str) -> bool:
    return helper_call(payload, sid) is not None


def receipt_from_output(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if all(k in value for k in ("fingerprint", "passed", "checks", "timestamp")):
            return {
                k: value[k] for k in ("fingerprint", "passed", "checks", "timestamp")
            }
        for key in ("stdout", "output", "content", "text"):
            found = receipt_from_output(value.get(key))
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = receipt_from_output(item)
            if found:
                return found
    elif isinstance(value, str):
        for match in re.finditer(r"\{", value):
            try:
                obj, _ = json.JSONDecoder().raw_decode(value[match.start() :])
                found = receipt_from_output(obj)
                if found:
                    return found
            except ValueError:
                continue
    return None


def instructions(sid: str) -> str:
    cmd = shlex.join([sys.executable, str(SELF), "checkpoint", sid])
    return (
        "Nuzantara Codex workflow: actual Codex token usage controls context rollover. "
        "Before rollover, save a concise English operational handoff (no client PII, secrets, "
        "or raw outputs): run "
        + cmd
        + " with a single shell-quoted JSON argument (avoid heredocs in read-only sessions): "
        '{"objective":"...","next_action":"...","remaining":["..."],"risks":[]}. '
        "Then end this turn; Stop will open the continuation and stop this source only after "
        "Codex accepts it. The continuation uses the same model and permission policy. "
        "For code changes, record real checks using the same helper with verb verify and "
        '{"commands":[["absolute/path/to/venv/bin/python","-m","pytest","specific_test.py"]]}. '
        "Verify again after editing; a successful tool invocation alone is not proof-live."
    )


def hook(payload: dict[str, Any]) -> dict[str, Any]:
    sid = str(payload.get("session_id") or "")
    event = payload.get("hook_event_name")
    policy = load(codex_home() / "nuzantara-context-policy.json")
    if not policy.get("enabled") or event not in EVENTS:
        return {}
    cwd = str(Path(payload.get("cwd") or os.getcwd()).resolve())
    roots = [str(Path(p).expanduser().resolve()) for p in policy.get("roots", [])]
    if not any(cwd == p or cwd.startswith(p + os.sep) for p in roots):
        return {}
    source_id = os.environ.get("CODEX_CONTEXT_FROM_SESSION")
    if (
        source_id
        and event in ("PreToolUse", "Stop")
        and load(state_path(sid)).get("from_session") != source_id
    ):
        reason = "Continuation has no valid source acknowledgement; no work is authorized here."
        if event == "PreToolUse":
            return context_output(event, reason, deny=True)
        return {"continue": False, "stopReason": reason}
    helper = (
        helper_call(payload, sid) if event in ("PreToolUse", "PostToolUse") else None
    )
    if (
        event == "PreToolUse"
        and helper
        and helper[0] == "checkpoint"
        and helper[1] is not None
    ):
        # The authorized hook writes only its metadata; no sandbox write is added.
        checkpoint(sid, helper[1])
    with locked(sid) as (path, state):
        state.update(
            version=VERSION,
            session_id=sid,
            cwd=cwd,
            last_event=event,
            heartbeat=time.time(),
        )
        counts = state.setdefault("event_counts", {})
        counts[event] = counts.get(event, 0) + 1
        if event == "PostToolUse" and helper and helper[0] == "verify":
            proof = receipt_from_output(payload.get("tool_response"))
            if (
                proof
                and isinstance(proof["checks"], list)
                and 1 <= len(proof["checks"]) <= 8
            ):
                proof["passed"] = (
                    proof["passed"] is True
                    and proof["fingerprint"] == git_fingerprint(cwd)
                    and all(c.get("exit_code") == 0 for c in proof["checks"])
                )
                state["verification"] = proof
        if event == "PreToolUse":
            state["last_tool_name"] = payload.get("tool_name")
            state["last_tool_input_keys"] = sorted(
                (payload.get("tool_input") or {}).keys()
            )
        transcript = payload.get("transcript_path")
        if transcript:
            state["transcript"] = transcript
            state.update(measure(transcript))
        state.setdefault("root_transcripts", [transcript] if transcript else [])
        if (
            event == "PreToolUse"
            and state.get("rollover") == "finished"
            and state.get("observed") != state.get("finished_observed")
        ):
            state.pop("rollover", None)
        if event == "SessionStart":
            source_id = os.environ.get("CODEX_CONTEXT_FROM_SESSION")
            if source_id and "from_session" not in state:
                with locked(source_id) as (source_path, source):
                    if (
                        source.get("rollover") != "starting"
                        or source.get("cwd") != cwd
                        or source.get("launch_nonce")
                        != os.environ.get("CODEX_CONTEXT_NONCE")
                        or source.get("claimed_by") not in (None, sid)
                    ):
                        raise ValueError("invalid or already claimed handoff")
                    source["claimed_by"] = sid
                    save(source_path, source)
                    paths = list(
                        dict.fromkeys(
                            [*source["root_transcripts"], source["transcript"]]
                        )
                    )
                    state.update(
                        from_session=source_id,
                        root_transcripts=paths,
                        hops=source.get("hops", 0) + 1,
                        role=source.get("role", "builder"),
                    )
            state.setdefault(
                "role",
                (
                    os.environ.get("CODEX_CONTEXT_ROLE")
                    or os.environ.get("CONTEXT_GUARD_ROLE")
                    or "builder"
                ).lower(),
            )
            state.setdefault("baseline", git_fingerprint(cwd))
            save(path, state)
            return context_output(event, instructions(sid))
        if event == "PostCompact":
            state["ignore_observed"] = state.get("observed")
            state.pop("rollover", None)
            save(path, state)
            return context_output(event, instructions(sid))
        fraction = policy.get("thresholds", {}).get(state.get("role", "builder"), 0.4)
        if not isinstance(fraction, (float, int)) or not 0 < fraction < 1:
            raise ValueError("invalid threshold")
        over = state.get("used", 0) >= state.get("window", float("inf")) * fraction
        over = over and state.get("observed") != state.get("ignore_observed")
        if over and not state.get("rollover"):
            state["rollover"] = "requested"
        save(path, state)
        if event == "PreToolUse" and state.get("rollover") in (
            "requested",
            "starting",
            "accepted",
        ):
            if not helper_command(payload, sid):
                return context_output(
                    event, "Context threshold reached. " + instructions(sid), deny=True
                )
        if event == "PostToolUse" and over:
            return context_output(
                event, "Context threshold reached. " + instructions(sid)
            )
        if event == "PreCompact":
            return context_output(
                event,
                "Preserve the original mandate and remaining work. "
                + instructions(sid),
            )
    if event == "Stop":
        if state.get("rollover") == "requested":
            if not state.get("checkpoint"):
                if payload.get("stop_hook_active"):
                    return {
                        "systemMessage": "Context handoff incomplete; source preserved. "
                        + instructions(sid)
                    }
                return {"decision": "block", "reason": instructions(sid)}
            if state["checkpoint"].get("remaining") == []:
                with locked(sid) as (path, latest):
                    latest["rollover"] = "finished"
                    latest["finished_observed"] = latest.get("observed")
                    save(path, latest)
            else:
                return launch(sid, int(policy.get("max_hops", 3)))
        if state.get("rollover") == "accepted":
            return {
                "continue": False,
                "stopReason": "Continuation accepted: " + state["to_session"],
            }
        current = git_fingerprint(cwd)
        if state.get("baseline") and current != state["baseline"]:
            proof = state.get("verification", {})
            if proof.get("fingerprint") != current or not proof.get("passed"):
                message = (
                    "Code changed without a current successful verification receipt. "
                    + instructions(sid)
                )
                if not payload.get("stop_hook_active"):
                    return {"decision": "block", "reason": message}
                return {"systemMessage": "Completion remains unverified. " + message}
    return {}


def checkpoint(sid: str, data: dict[str, Any]) -> None:
    allowed = {
        k: data[k]
        for k in ("objective", "next_action", "remaining", "risks")
        if k in data
    }
    if not all(
        isinstance(allowed.get(k), str) and allowed[k].strip()
        for k in ("objective", "next_action")
    ):
        raise ValueError("objective and next_action required")
    text = json.dumps(allowed)
    if len(text) > 12000 or re.search(
        r"sk-[A-Za-z0-9_-]{16,}|Bearer\s+\S+|\b[^\s@]+@[^\s@]+\.[^\s@]+", text
    ):
        raise ValueError("handoff exceeds limit or contains sensitive identifiers")
    with locked(sid) as (path, state):
        if not state.get("cwd"):
            raise ValueError("unknown source session")
        state["checkpoint"] = allowed
        state["checkpoint_fingerprint"] = git_fingerprint(state["cwd"])
        save(path, state)


def verify(sid: str, data: dict[str, Any], persist: bool = True) -> dict[str, Any]:
    state = load(state_path(sid))
    commands = data.get("commands")
    if not isinstance(commands, list) or not 1 <= len(commands) <= 8:
        raise ValueError("one to eight argv commands required")
    before = git_fingerprint(state["cwd"])
    results = []
    for argv in commands:
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(a, str) for a in argv)
        ):
            raise ValueError("commands must be argv arrays")
        run = subprocess.run(argv, cwd=state["cwd"], capture_output=True, timeout=300)
        results.append(
            {
                "command_sha256": digest(json.dumps(argv).encode()),
                "exit_code": run.returncode,
                "output_sha256": digest(run.stdout + run.stderr),
            }
        )
    after = git_fingerprint(state["cwd"])
    proof = {
        "timestamp": time.time(),
        "fingerprint": after,
        "passed": before == after and all(r["exit_code"] == 0 for r in results),
        "checks": results,
    }
    if persist:
        with locked(sid) as (path, latest):
            latest["verification"] = proof
            save(path, latest)
    return proof


def launch(sid: str, max_hops: int) -> dict[str, Any]:
    with locked(sid) as (path, state):
        if state.get("rollover") != "requested":
            return {}
        if state.get("hops", 0) >= max_hops:
            state["rollover"] = "needs_attention"
            save(path, state)
            return {
                "systemMessage": "Context hop limit reached; source and handoff preserved."
            }
        if state.get("checkpoint_fingerprint") != git_fingerprint(state["cwd"]):
            return {
                "decision": "block",
                "reason": "Worktree changed after checkpoint. " + instructions(sid),
            }
        state.update(
            rollover="starting",
            launch_deadline=time.time() + HANDSHAKE_SECONDS,
            launch_nonce=uuid.uuid4().hex,
        )
        for field in ("claimed_by", "failure", "to_session"):
            state.pop(field, None)
        save(path, state)
        subprocess.Popen(
            [sys.executable, str(SELF), "continue", sid],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    until = time.monotonic() + HANDSHAKE_SECONDS
    while time.monotonic() < until:
        latest = load(state_path(sid))
        if latest.get("rollover") == "accepted":
            return {
                "continue": False,
                "stopReason": "Continuation accepted: " + latest["to_session"],
                "systemMessage": "Work continues in Codex task " + latest["to_session"],
            }
        if latest.get("rollover") == "needs_attention":
            break
        time.sleep(0.1)
    # Never terminate the source on an unconfirmed launch; invalidate late acceptance.
    with locked(sid) as (path, latest):
        latest["rollover"] = "needs_attention"
        latest.setdefault("failure", "continuation_not_confirmed")
        save(path, latest)
    return {
        "systemMessage": "Continuation not confirmed. Source preserved; inspect context bridge status."
    }


def continue_session(sid: str) -> None:
    proc = None
    try:
        state = load(state_path(sid))
        paths = list(dict.fromkeys([*state["root_transcripts"], state["transcript"]]))
        mandate = prompts(paths)
        runtime: dict[str, Any] = {}
        for rec in records(state["transcript"]):
            if rec.get("type") == "turn_context":
                runtime = rec["payload"]
        if not all(
            k in runtime for k in ("model", "approval_policy", "sandbox_policy")
        ):
            raise ValueError("source runtime policy unavailable")
        command = continuation_command(runtime)
        if state.get("rollover") != "starting":
            raise ValueError("source cancelled launch")
        text = (
            "Continue the owner's authorized work from Codex session "
            + sid
            + ". Do not repeat verified work. Recheck current disk state. Do not publish, merge, "
            "deploy, or send messages unless the owner explicitly authorized that action. "
            "Keep client data and credentials out of outputs.\n\nOriginal instructions and steering:\n"
            + mandate
            + "\n\nOperational checkpoint:\n"
            + json.dumps(state["checkpoint"])
            + "\n\nVerification receipts:\n"
            + json.dumps(state.get("verification", {}))
        )
        env = os.environ.copy()
        env.update(
            CODEX_CONTEXT_FROM_SESSION=sid, CODEX_CONTEXT_NONCE=state["launch_nonce"]
        )
        proc = subprocess.Popen(
            command,
            cwd=state["cwd"],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        assert proc.stdin and proc.stdout
        proc.stdin.write(text)
        proc.stdin.close()
        messages: queue.Queue[dict[str, Any]] = queue.Queue()

        def read_events() -> None:
            assert proc and proc.stdout
            for line in proc.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    continue
            messages.put({"type": "bridge/eof"})

        threading.Thread(target=read_events, daemon=True).start()
        accepted, to = False, None
        while True:
            try:
                msg = messages.get(timeout=1 if not accepted else 600)
            except queue.Empty:
                if not accepted and time.time() < state["launch_deadline"]:
                    continue
                raise TimeoutError("destination did not make progress") from None
            kind, item = msg.get("type"), msg.get("item", {})
            if kind == "thread.started":
                to = msg["thread_id"]
            progress = kind in ("item.started", "item.completed") and item.get(
                "type"
            ) in ("agent_message", "reasoning", "command_execution", "mcp_tool_call")
            if not accepted and to and progress:
                child = load(state_path(to))
                if child.get("from_session") != sid:
                    raise ValueError("destination did not acknowledge exact source")
                with locked(sid) as (path, latest):
                    if (
                        latest.get("rollover") != "starting"
                        or time.time() > latest["launch_deadline"]
                    ):
                        raise TimeoutError("source cancelled late continuation")
                    latest.update(
                        to_session=to, rollover="accepted", accepted_at=time.time()
                    )
                    save(path, latest)
                accepted = True
            if kind in ("turn.completed", "turn.failed", "bridge/eof"):
                status = "completed" if kind == "turn.completed" else "failed"
                with locked(sid) as (path, latest):
                    latest["destination_status"] = status
                    if not accepted or status != "completed":
                        latest.update(
                            rollover="needs_attention", failure="destination_" + status
                        )
                    save(path, latest)
                break
    except Exception as exc:
        with locked(sid) as (path, latest):
            latest.update(rollover="needs_attention", failure=type(exc).__name__)
            save(path, latest)
    finally:
        if proc and proc.poll() is None:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def main() -> int:
    try:
        verb = sys.argv[1] if len(sys.argv) > 1 else "hook"
        if verb == "continue":
            continue_session(sys.argv[2])
            return 0
        if verb == "status":
            print(json.dumps(load(state_path(sys.argv[2])), indent=2))
            return 0
        data = json.loads(sys.argv[3]) if len(sys.argv) > 3 else json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("object required")
        if verb == "checkpoint":
            state = load(state_path(sys.argv[2]))
            if state.get("checkpoint") != data or state.get(
                "checkpoint_fingerprint"
            ) != git_fingerprint(state["cwd"]):
                checkpoint(sys.argv[2], data)
            print('{"checkpoint_saved":true}')
        elif verb == "verify":
            proof = verify(sys.argv[2], data, persist=False)
            print(json.dumps(proof))
            return 0 if proof["passed"] else 1
        else:
            print(json.dumps(hook(data)))
        return 0
    except Exception as exc:
        # Protocol/format failures cannot masquerade as a threshold verdict.
        if len(sys.argv) == 1 or sys.argv[1] == "hook":
            print(
                json.dumps(
                    {
                        "systemMessage": "Codex context bridge could not verify state: "
                        + type(exc).__name__
                    }
                )
            )
            return 0
        print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
