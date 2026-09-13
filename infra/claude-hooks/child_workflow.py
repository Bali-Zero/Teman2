"""Child-local adapter. Never creates parent handoffs or launches a replacement.

Unknown ownership is a request to report an incomplete result, never permission
to stage, reset, stash or delete a sibling's work. A Stop reminder is not grading.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def budget_module() -> Any:
    try:
        return importlib.import_module("mandate_budget")
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).parents[1] / "codex-hooks"))
        return importlib.import_module("mandate_budget")


def budget_reserve(*args: Any, **kwargs: Any) -> str | None:
    return budget_module().reserve(*args, **kwargs)


def budget_observe(*args: Any, **kwargs: Any) -> str | None:
    return budget_module().observe(*args, **kwargs)


CONTRACT = (
    "Child workflow: use the assigned objective, write scope, expected result, constraints "
    "and checks. Do not inherit the coordinator's rank. Return result, evidence, remaining "
    "work and ownership to the parent; never start a replacement or a parent context jump. "
    "Writers need an existing broker worktree or serialized ownership covering every "
    "mutation channel, including shell and MCP. Never clean another worker's files. "
    "A finished tool call or an empty remaining list is not independent acceptance. "
    "The coordinator owns the total attempts, retries, replacements, depth, concurrency "
    "and deadline; do not reset those budgets when replacing a child."
)

REPORTING_TOOLS = ("SendMessage", "TaskStop")


def reporting_exempt(payload: dict[str, Any]) -> bool:
    """Tools a capped child may still call, because they ARE the return path.

    SendMessage and TaskStop were already exempt; ToolSearch was not. In a
    harness that defers tool schemas, a deferred SendMessage is a NAME with no
    parameters until ToolSearch fetches its definition, so denying ToolSearch
    denied the report itself while the deny text told the child to report. The
    exemption is narrowed BY THE QUERY whenever the hook can read one: only a
    search naming SendMessage or TaskStop passes, and an unrelated search stays
    denied like any other tool. When the payload carries no readable query --
    a payload shape this hook does not own -- ToolSearch is exempted AS A WHOLE
    rather than trapping the child in an unreportable cap; the denial counter
    and the ledger still record that the cap fired.
    """
    tool = payload.get("tool_name")
    if tool in REPORTING_TOOLS:
        return True
    if tool != "ToolSearch":
        return False
    query = (payload.get("tool_input") or {}).get("query")
    if not isinstance(query, str) or not query.strip():
        return True
    return any(name.lower() in query.lower() for name in REPORTING_TOOLS)


def budget_denial(state: dict[str, Any], mandate: str) -> str:
    """Name the counter that fired, never only the contract.

    The old denial recited CONTRACT and stopped: the child learned it was over
    budget without learning WHICH budget, by how much, or under whose mandate,
    so it could not report the number upward and the transcript could not be
    audited after the fact. Every field here is one the coordinator asks for.
    """
    return (
        "Child context budget reached: counter="
        + str(state.get("budget_reason") or "UNKNOWN")
        + " used="
        + str(state.get("budget_used", "UNKNOWN"))
        + " limit="
        + str(state.get("budget_limit", "UNKNOWN"))
        + " role="
        + str(state.get("role") or "builder")
        + " mandate="
        + (mandate or "UNKNOWN")
        + ". Required next action: send the checkpoint and the remaining work to the "
        "parent with SendMessage, then TaskStop; ToolSearch stays available only to "
        "load those two schemas. No other tool is granted. "
        + CONTRACT
    )


def child_identity(payload: dict[str, Any]) -> tuple[str, str] | None:
    # Same detection as orchestrate_gate, but Stop's transcript is explicitly the parent.
    stop = payload.get("hook_event_name") == "SubagentStop"
    if not stop:
        from orchestrate_gate import is_subagent_context

        if not is_subagent_context(payload):
            return None
    transcript = str(
        payload.get("agent_transcript_path" if stop else "transcript_path") or ""
    )
    agent = str(payload.get("agent_id") or "")
    if agent and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", agent):
        return hashlib.sha256(
            (str(payload.get("session_id")) + ":UNKNOWN").encode()
        ).hexdigest(), ""
    if not stop and agent and transcript and "subagents" not in Path(transcript).parts:
        # Claude 2.1.266 reports the parent's path even INSIDE child PreToolUse.
        candidate = (
            Path(transcript).with_suffix("")
            / "subagents"
            / ("agent-" + agent + ".jsonl")
        )
        transcript = str(candidate) if candidate.is_file() else ""
    if not agent and transcript and "subagents" in Path(transcript).parts:
        agent = Path(transcript).stem
    key = hashlib.sha256(
        (
            str(payload.get("session_id") or "UNKNOWN") + ":" + (agent or "UNKNOWN")
        ).encode()
    ).hexdigest()
    return key, transcript


@contextmanager
def child_state(key: str) -> Iterator[tuple[Path, dict[str, Any]]]:
    root = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        / "state"
        / "child-workflow"
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (key + ".json")
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            state = {}
        yield path, state
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        with open(temporary, "w", opener=lambda p, f: os.open(p, f, 0o600)) as out:
            json.dump(state, out)
        temporary.replace(path)


def context_guard(payload: dict[str, Any], guard: dict[str, Any]) -> int | None:
    identity = child_identity(payload)
    if identity is None:
        if payload.get("tool_name") in ("Agent", "Task"):
            root = mandate_id(payload, guard)
            reason = budget_reserve(
                budget_dir(),
                root,
                str(payload.get("tool_use_id") or ""),
                {
                    "strict": bool(os.environ.get("NUZANTARA_MANDATE_ID")),
                    "active_ttl": 1800,
                    "max_active": 8,
                },
                target=(payload.get("tool_input") or {}).get("resume"),
            )
            if reason:
                sys.stderr.write(reason + "\n")
                return 2
        return None  # Top-level behavior stays with the existing guard.
    key, transcript = identity
    import child_context

    mandate = mandate_id(payload, guard)
    lease_error = budget_observe(
        budget_dir(),
        mandate,
        str(payload.get("agent_id") or "UNKNOWN"),
        transcript=transcript or None,
    )
    if lease_error:
        sys.stderr.write(
            lease_error + "; return an incomplete checkpoint to the parent.\n"
        )
        return 0 if reporting_exempt(payload) else 2
    if payload.get("tool_name") in ("Agent", "Task"):
        sys.stderr.write(
            "Child delegation depth reached. Return remaining work to the parent.\n"
        )
        return 2
    tail = guard["_read_tail"](transcript)
    with child_state(key) as (_, state):
        if state.get("transport") == "stopped":
            state.pop("stop_reminded", None)
            state["transport"] = "running"
        state.update(
            role="builder",
            topology="child",
            parent_session=payload.get("session_id"),
            agent_id=payload.get("agent_id"),
            heartbeat=time.time(),
            acceptance="unverified",
        )
        state["pretool_count"] = state.get("pretool_count", 0) + 1
        tool = payload.get("tool_name")
        # Shell, MCP, notebooks and unknown tools are potential mutations. Absence of
        # Edit/Write is never evidence of read-only ownership.
        if tool not in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
            state["mutation_possible"] = True
        state.update(child_context.snapshot(tail or ""))
        window = (payload.get("context_window") or {}).get("context_window_size")
        native = type(window) is int and window > 0
        state["window"] = (
            window
            if native
            else child_context.capacity(
                state["model"], state["version"], payload.get("cwd", os.getcwd())
            )
        )
        state["measurement"] = (
            ("observed" if native else "calibrated")
            if state["window"] and state["used"] is not None
            else "UNKNOWN"
        )
        state.setdefault("budget_started_at", time.time())
        strict = bool(os.environ.get("NUZANTARA_MANDATE_ID"))
        state["budget_mode"] = "enforced" if strict else "interactive_observation"
        state["token_limit"] = (
            int(state["window"] * 0.4)
            if state["window"]
            else child_context.FALLBACK_TOKENS
        )
        over = state["used"] is not None and state["used"] >= state["token_limit"]
        # Child ACTIVE TIME, measured and reported here. It is not the mission
        # deadline: `mandate_budget` owns that one, and conflating them would let
        # a fresh child inherit an expired wall or a stale mandate outlive itself.
        elapsed = (
            state.get("budget_elapsed", 0) + time.time() - state["budget_started_at"]
        )
        state["time_budget_exceeded"] = elapsed >= child_context.MAX_SECONDS
        if state["pretool_count"] > child_context.MAX_TOOL_CALLS:
            state.update(
                budget_reason="tool_calls",
                budget_used=state["pretool_count"],
                budget_limit=child_context.MAX_TOOL_CALLS,
            )
            over = True
        elif state["time_budget_exceeded"]:
            state.update(
                budget_reason="elapsed_time",
                budget_used=round(elapsed),
                budget_limit=child_context.MAX_SECONDS,
            )
            over = True
        elif over:
            state.update(
                budget_reason="context_tokens",
                budget_used=state["used"],
                budget_limit=state["token_limit"],
            )
        if over:
            state.update(
                status="needs_attention",
                reason=state["budget_reason"],
                budget_attention=True,
            )
            if strict:
                state["return_required"] = True
        if strict and state.get("return_required") and not reporting_exempt(payload):
            state["denials"] = state.get("denials", 0) + 1
            sys.stderr.write(budget_denial(state, mandate) + "\n")
            return 2  # Repeated denials never grant normal tools.
        warnings = []
        if state["measurement"] == "UNKNOWN":
            warnings.append(
                "Child capacity/usage UNKNOWN; no percentage is claimed. "
                "Strict mandates enforce 3600 active seconds, 120 tools and an emergency "
                "ceiling of 400000 measured tokens. Calibrate the actual model."
            )
        if not strict and over:
            warnings.append(
                "Interactive budget observation: "
                + state["budget_reason"]
                + "; needs_attention, no denial."
            )
        if warnings:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "additionalContext": " ".join(warnings),
                        }
                    }
                )
            )
    return 0


def budget_dir() -> Path:
    return (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        / "state"
        / "child-mandates"
    )


def mandate_id(payload: dict[str, Any], guard: dict[str, Any] | None = None) -> str:
    """Follow exact claimed Claude jump links, never the latest file by time."""
    if os.environ.get("NUZANTARA_MANDATE_ID"):
        return os.environ["NUZANTARA_MANDATE_ID"]
    sid = str(payload.get("session_id") or "UNKNOWN")
    if guard and guard.get("_chain_link"):
        seen = set()
        for _ in range(4):
            if sid in seen:
                break
            seen.add(sid)
            link = guard["_chain_link"](sid)
            if (
                not link
                or link.get("to_session") != sid
                or not link.get("from_session")
            ):
                break
            sid = str(link["from_session"])
    else:
        directory = Path.home() / ".organism" / "context-guard"
        for _ in range(4):
            matches = []
            for path in directory.glob("pending-jump-*.json"):
                try:
                    link = json.loads(path.read_text())
                    if link.get("to_session") == sid and link.get("from_session"):
                        matches.append(str(link["from_session"]))
                except (OSError, ValueError):
                    continue
            if len(matches) != 1:
                break
            sid = matches[0]
    return sid


def stop_lifecycle(payload: dict[str, Any]) -> None:
    """Always release and pause, including recovery bypass and broken verification."""
    identity = child_identity({**payload, "hook_event_name": "SubagentStop"})
    assert identity is not None
    key, _ = identity
    # Release first: verification or local-state failure must not pin a mandate.
    budget_observe(
        budget_dir(),
        mandate_id(payload),
        str(payload.get("agent_id") or "UNKNOWN"),
        stopped=True,
    )
    with child_state(key) as (_, state):
        if "budget_started_at" in state:
            state["budget_elapsed"] = state.get("budget_elapsed", 0) + max(
                0, time.time() - state.pop("budget_started_at")
            )
        state.update(
            transport="stopped", acceptance="unverified", heartbeat=time.time()
        )
        state["status"] = (
            "needs_attention"
            if state.get("budget_attention")
            else "returned_unverified"
        )


def _stop_guard(payload: dict[str, Any], legacy: dict[str, Any]) -> int:
    identity = child_identity({**payload, "hook_event_name": "SubagentStop"})
    assert identity is not None
    key, transcript = identity
    with child_state(key) as (_, state):
        message = str(payload.get("last_assistant_message") or "")
        # Only the child's current, explicit declaration counts, not quoted tools,
        # a parent's transcript, or the word "checkpoint" in old instructions.
        declared = bool(
            re.search(r"(?im)^\s*(?:leave-dirty|incomplete|checkpoint):\s+\S", message)
        )
        state["claimed_incomplete"] = declared
        if payload.get("stop_hook_active") or state.get("stop_reminded"):
            state["status"] = (
                "needs_attention"
                if state.get("stop_reminded")
                else "returned_unverified"
            )
            return 0
        identifiable = (
            bool(payload.get("agent_id"))
            and bool(transcript)
            and Path(transcript).is_file()
        )
        problem = None
        if not identifiable:
            problem = "Child identity, transcript or ownership evidence is UNKNOWN."
        elif (
            state.get("return_required")
            and os.environ.get("NUZANTARA_MANDATE_ID")
            and not declared
        ):
            problem = "Child context budget requires an incomplete checkpoint."
        elif state.get("mutation_possible"):
            lane = legacy.get("_lane_check")
            if lane is not None:
                try:
                    result = lane.evaluate(
                        payload.get("cwd", os.getcwd()),
                        changed_paths_fn=lambda: legacy["_changed_paths"](
                            payload.get("cwd", os.getcwd())
                        ),
                    )
                    if lane.blocks(result):
                        problem = "The lane's declared check did not pass. Report its failure to the parent."
                except Exception:
                    problem = "The lane's declared check could not be verified."
            if (
                not problem
                and legacy["_git_dirty_status"](payload.get("cwd", os.getcwd()))
                and not declared
            ):
                problem = (
                    "The worktree is dirty and ownership is not independently verified."
                )
        if problem:
            state.update(
                stop_reminded=True, status="needs_attention", transport="stop_blocked"
            )
            sys.stderr.write(
                problem
                + " Return an explicit 'incomplete: <remaining work and owner>' or 'leave-dirty: <owner and reason>'. Commit only your explicitly assigned paths when appropriate; never stage, stash, reset or remove sibling files to satisfy this reminder. Parent must verify the result independently.\n"
            )
            return 2
        state["status"] = (
            "needs_attention"
            if state.get("budget_attention")
            else "returned_unverified"
        )
        return 0


def stop_guard(payload: dict[str, Any], legacy: dict[str, Any]) -> int:
    stop_lifecycle(payload)
    return _stop_guard(payload, legacy)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "attention":
        root = budget_dir().parent
        report = []
        for directory in (root / "child-workflow", budget_dir()):
            for path in directory.glob("*.json"):
                try:
                    state = json.loads(path.read_text())
                    if state.get("status") == "needs_attention":
                        report.append(
                            {
                                k: state.get(k)
                                for k in (
                                    "mandate_id",
                                    "parent_session",
                                    "agent_id",
                                    "status",
                                    "reason",
                                )
                            }
                        )
                except (OSError, ValueError):
                    continue
        print(json.dumps(report))
        return
    payload = json.load(sys.stdin)
    event = payload.get("hook_event_name")
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    if mode == "stop":
        stop_lifecycle(payload)
        if (
            os.environ.get("SUBAGENT_STOP_VERIFY_OFF") == "1"
            or os.environ.get("STOP_VERIFY_ALLOW_DIRTY") == "1"
        ):
            raise SystemExit(0)
    if mode in ("context", "stop"):
        name = "context_window_guard" if mode == "context" else "subagent_stop_verify"
        spec = importlib.util.spec_from_file_location(
            name, Path(__file__).with_name(name + ".py")
        )
        assert spec and spec.loader
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        if mode == "context":
            if os.environ.get("CONTEXT_GUARD_OFF") == "1":
                result = 0
            else:
                result = context_guard(payload, vars(legacy))
            if result is None:
                sys.stdin = io.StringIO(json.dumps(payload))
                result = legacy.main()
                if not result and payload.get("tool_name") in ("Agent", "Task"):
                    print(
                        json.dumps(
                            {
                                "hookSpecificOutput": {
                                    "hookEventName": "PreToolUse",
                                    "additionalContext": CONTRACT,
                                }
                            }
                        )
                    )
        else:
            result = _stop_guard(payload, vars(legacy))
        raise SystemExit(result or 0)
    if event == "SubagentStart":
        budget_observe(
            budget_dir(),
            mandate_id(payload),
            str(payload.get("agent_id") or "UNKNOWN"),
        )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": CONTRACT,
                }
            }
        )
    )


def entrypoint() -> None:
    raw = sys.stdin.read()
    sys.stdin = io.StringIO(raw)
    try:
        main()
    except Exception:
        mode = sys.argv[1] if len(sys.argv) > 1 else "start"
        sys.stderr.write("Child adapter unavailable; result remains unverified.\n")
        if mode == "context":
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}
            if (
                payload.get("agent_id")
                or "subagents" in Path(payload.get("transcript_path") or "").parts
            ):
                sys.stderr.write(
                    "Return an incomplete checkpoint to the parent; no parent jump is authorized.\n"
                )
                raise SystemExit(2)
            # Preserve the original parent guard even when loading the router fails.
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).with_name("context_window_guard.py")),
                    ],
                    input=raw,
                    text=True,
                    timeout=20,
                )
                raise SystemExit(result.returncode)
            except (OSError, subprocess.TimeoutExpired):
                pass
        # A broken Stop observer must not trap the child in another tool cycle.
        raise SystemExit(0)


if __name__ == "__main__":
    entrypoint()
