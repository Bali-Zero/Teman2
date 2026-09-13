"""Accept only a fresh native Workflow completion bound to this exact request.

Assistant prose and CLI exit zero are never execution evidence. This module reads
only the random session id assigned by the launcher and that run's native journal.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sessions(session_id: str, roots: list[Path]) -> list[Path]:
    if str(uuid.UUID(session_id)) != session_id:
        raise ValueError("invalid_session")
    return sorted({p.resolve() for root in roots for p in root.glob("projects/*/" + session_id + ".jsonl")})


def rows(path: Path) -> list[dict]:
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in result):
        raise ValueError("invalid_native_rows")
    return result


def tag(text: str, name: str) -> str:
    found = re.findall("<" + name + r">([\s\S]*?)</" + name + ">", text)
    if len(found) != 1:
        raise ValueError("invalid_notification")
    return found[0]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def verify(session_id: str, roots: list[Path], request: dict, *, smoke=False,
           script_sha256: str | None = None) -> dict:
    try:
        candidates = sessions(session_id, roots)
        require(len(candidates) == 1, "session_missing_or_ambiguous")
        session = candidates[0]
        data = rows(session)
        calls = [(row, block) for row in data if row.get("type") == "assistant"
                 for block in row.get("message", {}).get("content", []) if isinstance(block, dict)
                 and block.get("type") == "tool_use" and block.get("name") == "Workflow"]
        require(len(calls) == 1, "workflow_invocation_missing_or_repeated")
        owner, invocation = calls[0]
        require(owner.get("sessionId") == session_id and invocation.get("input") == request,
                "workflow_request_mismatch")
        tool_id = invocation["id"]
        launches = [row for row in data if row.get("type") == "user"
                    and row.get("toolUseResult", {}).get("status") == "async_launched"
                    and row.get("toolUseResult", {}).get("taskType") == "local_workflow"]
        require(len(launches) == 1, "native_launch_missing_or_repeated")
        launch_row = launches[0]
        require(data.index(owner) < data.index(launch_row), "native_launch_out_of_order")
        require(launch_row.get("sessionId") == session_id and any(
            b.get("type") == "tool_result" and b.get("tool_use_id") == tool_id
            and not b.get("is_error") for b in launch_row.get("message", {}).get("content", [])
            if isinstance(b, dict)), "native_launch_unbound")
        launch = launch_row["toolUseResult"]
        run_id, task_id = launch["runId"], launch["taskId"]
        require(isinstance(run_id, str) and bool(re.fullmatch(r"wf_[A-Za-z0-9-]+", run_id)), "invalid_run_id")
        owned = session.with_suffix("").resolve()
        transcript = Path(launch["transcriptDir"]).resolve()
        require(transcript == owned / "subagents/workflows" / run_id, "stale_or_foreign_journal")
        script = Path(launch["scriptPath"]).resolve()
        if "script" in request:
            require(script.parent == owned / "workflows/scripts", "foreign_inline_script")
            require(script.read_text() == request["script"], "script_content_mismatch")
        else:
            require(script == Path(request["scriptPath"]).resolve()
                    or script.parent == owned / "workflows/scripts", "foreign_script")
            require(script_sha256 is not None and digest(script.read_bytes()) == script_sha256,
                    "script_content_mismatch")
        notifications = []
        for row in data:
            attachment = row.get("attachment", {})
            if row.get("type") != "attachment" or attachment.get("type") != "queued_command" or attachment.get("commandMode") != "task-notification":
                continue
            prompt = attachment.get("prompt", "")
            if "<task-notification>" not in prompt:
                continue
            if tag(prompt, "task-id") == task_id and tag(prompt, "tool-use-id") == tool_id:
                require(row.get("sessionId") == session_id, "foreign_completion")
                require(data.index(launch_row) < data.index(row), "completion_out_of_order")
                notifications.append(prompt)
        require(len(notifications) == 1, "completion_missing_or_repeated")
        notification = notifications[0]
        require(tag(notification, "status") == "completed", "native_workflow_not_completed")
        result = json.loads(tag(notification, "result"))
        require(isinstance(result, dict), "native_result_missing")
        if smoke:
            require(result == {"marker": "SAETTA_NATIVE_SMOKE"}, "smoke_result_not_passed")
        else:
            args = request["args"]
            require(result.get("mission") == args["mission"] and result.get("verdict") == "PASS",
                    "mission_not_passed")
            outcomes, close = result.get("results", []), result.get("close", {})
            require(isinstance(outcomes, list) and len(outcomes) == len(args["tasks"])
                    and all(isinstance(r, dict) and r.get("verdict") == "PASS" for r in outcomes)
                    and {r.get("key") for r in outcomes} == {t["key"] for t in args["tasks"]},
                    "mission_results_incomplete")
            require(isinstance(close, dict) and close.get("recorded") is True
                    and close.get("verdict") == "PASS" and isinstance(close.get("receipt"), str)
                    and Path(close["receipt"]).is_absolute(), "mission_close_incomplete")
        journal = transcript / "journal.jsonl"
        records = rows(journal)
        require(sum(r.get("type") == "launched" for r in records) == 1, "journal_launch_missing")
        require(records[0].get("type") == "launched", "journal_launch_out_of_order")
        started = {(r.get("key"), r.get("agentId")) for r in records if r.get("type") == "started"}
        completed = {(r.get("key"), r.get("agentId")) for r in records
                     if r.get("type") == "result" and r.get("result") is not None}
        require(bool(started) and started == completed, "journal_agent_results_incomplete")
        return {"verdict": "PASS", "sessionId": session_id, "runId": run_id,
                "sessionPath": str(session), "scriptPath": str(script), "journalPath": str(journal),
                "requestSha256": digest(json.dumps(request, sort_keys=True).encode()),
                "scriptSha256": digest(script.read_bytes()), "journalSha256": digest(journal.read_bytes()),
                "nativeResultSha256": digest(json.dumps(result, sort_keys=True).encode())}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # Fixed reason codes only: never leak JSON excerpts, model output or a credential.
        reason = str(exc) if type(exc) is ValueError and re.fullmatch(r"[a-z_]+", str(exc)) else "invalid_native_evidence"
        return {"verdict": "BLOCK", "sessionId": session_id, "reason": reason}
