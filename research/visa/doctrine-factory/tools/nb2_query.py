#!/usr/bin/env python3
"""QW-1 NB-2 transport isolation runner.

ROOT-CAUSE (verified at source level, this session, 2026-08-15 — cite, do not re-derive):
`nlm` CLI (package `notebooklm-mcp-cli` v0.9.8, installed at
`~/.local/share/uv/tools/notebooklm-mcp-cli/lib/python3.11/site-packages/notebooklm_tools/`).
`core/conversation.py::ConversationManager.query()` (~lines 392-403): when
`--conversation-id` is omitted, the client calls `get_conversation_id(notebook_id)` first,
which fetches NotebookLM's PERSISTENT server-side conversation id for that notebook ("This is
what makes CLI/MCP chats appear in the web UI's chat history" — verbatim docstring) and reuses
it. That is why two independent harnesses — blueprint A's executed P0 batch
(`visa-oracle-adjudication/output-A/run_p0.py`, which never passes `-c`) and blueprint C's live
probes — both landed in the SAME conversation `3e8fe6db-8873-4689-9bff-226ee875c09d` and
observed cross-context contamination ("As we discussed in our previous evaluation...").

CURE (client-side, verified by reading the code path, not assumed): pass an EXPLICIT fresh
`uuid.uuid4()` via `-c`. `cli/commands/notebook.py::query_notebook()` forwards it straight to
`ConversationManager.query(conversation_id=...)`, which then takes the `else` branch —
`is_new_conversation` is False, so the server-side persistent-id lookup is skipped entirely,
and `conversation_history = self._build_conversation_history(conversation_id)`. Because
`_conversation_cache` lives only in the CLI process's memory and every `nlm` invocation is a
fresh process, a never-seen UUID always misses the cache lookup -> `conversation_history =
None` -> `params[2] = None` is what actually goes to the server. The server has no stored
history for an unrecognized conversation id, so it cannot inject cross-context contamination.

QUERY-ONLY CONTRACT: this module shells out ONLY to `nlm notebook query` (chat) and, in
--snapshot-sources mode, `nlm source list` (read-only listing). It NEVER calls
`source add/delete/rename`, NEVER `delete_chat_history`, and NEVER mutates the notebook in any
way. Judge the OUTPUT JSON, not just the process exit code (cicatrix W104: a green exit code is
not proof of a good answer) — and the converse also holds (GLM grader finding P2, 2026-08-15):
a NONZERO exit code is not proof of a WORTHLESS answer either. `build_record()` always attempts
to parse stdout and run the isolation check regardless of returncode, so a valid JSON payload
is never silently discarded just because the CLI process also complained on stderr.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

NB2_ID = "cff93ab0-813a-42f2-a8de-36987e724271"

# The known-contaminated persistent server-side conversation id both independent harnesses
# (blueprint A's executed P0 batch and blueprint C's live probes) landed in when `-c` was
# omitted. Any query result that resolves back to this id is treated as an isolation failure
# even if conversation_id_returned happens to equal conversation_id_sent (which cannot happen
# for a UUID4 we just minted, but is checked as an independent guard regardless).
CONTAMINATED_CONVERSATION_ID = "3e8fe6db-8873-4689-9bff-226ee875c09d"

_HERE = Path(__file__).resolve()
_FACTORY_ROOT = _HERE.parents[1]  # research/visa/doctrine-factory/
DEFAULT_LOG_PATH = _FACTORY_ROOT / "nb2-answers" / "response-log.jsonl"
DEFAULT_SOURCES_DIR = _FACTORY_ROOT / "sources"
DEFAULT_NLM_BIN = os.environ.get("NLM_BIN") or str(Path.home() / ".local" / "bin" / "nlm")

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class IsolationMismatchError(RuntimeError):
    """Raised when the server did not honor the fresh conversation id we sent.

    Per the mandate: "Refuse to run if the returned conversation_id != the sent one (fail
    loud, record the anomaly)." The anomaly IS recorded (append-only, before this is raised) —
    this exception is the fail-loud half of that contract, not a silent swallow.
    """

    def __init__(self, message: str, record: dict[str, Any]):
        super().__init__(message)
        self.record = record


class QueryTimeoutError(RuntimeError):
    """Raised when `nlm` does not return within its subprocess timeout.

    Per GLM grader finding P2 (2026-08-15): the log is the anomaly's domicile — a timeout is
    durably appended as a JSONL record (partial stdout/stderr if the OS captured any) BEFORE
    this is raised, exactly like IsolationMismatchError.
    """

    def __init__(self, message: str, record: dict[str, Any]):
        super().__init__(message)
        self.record = record


def utcnow_iso() -> str:
    """ISO 8601 with an explicit UTC timezone offset (mandate: "ts_utc (ISO with timezone)")."""
    return datetime.now(timezone.utc).isoformat()


def get_nlm_version(nlm_bin: str = DEFAULT_NLM_BIN, runner: Runner = subprocess.run) -> str:
    try:
        proc = runner([nlm_bin, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"UNKNOWN ({exc.__class__.__name__})"
    if proc.returncode != 0:
        return f"UNKNOWN (rc={proc.returncode})"
    return proc.stdout.strip() or proc.stderr.strip() or "UNKNOWN (empty output)"


def run_nlm_query(
    notebook_id: str,
    question: str,
    conversation_id: str,
    timeout: float = 120.0,
    nlm_bin: str = DEFAULT_NLM_BIN,
    runner: Runner = subprocess.run,
) -> "subprocess.CompletedProcess[str]":
    """Invoke `nlm notebook query <nb> <question> --json -c <conversation_id> -t <timeout>`.

    Never invoked without an explicit -c: an omitted conversation_id is exactly the defect
    this tool exists to cure (see module docstring root-cause). May raise
    `subprocess.TimeoutExpired` — the caller (`run_one_query`) is responsible for turning that
    into a durable JSONL anomaly record before it propagates.
    """
    cmd = [
        nlm_bin,
        "notebook",
        "query",
        notebook_id,
        question,
        "--json",
        "-c",
        conversation_id,
        "-t",
        str(timeout),
    ]
    return runner(cmd, capture_output=True, text=True, timeout=timeout + 30)


def _try_parse_json(stdout: str) -> tuple[Any | None, str | None]:
    """(payload, parse_error). payload is None if stdout is empty/whitespace or invalid JSON."""
    text = (stdout or "").strip()
    if not text:
        return None, "empty stdout"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"


def _isolation_hypotheses(conversation_id_sent: str, conversation_id_returned: Any) -> list[str]:
    """Non-empty ONLY when isolation looks broken. A list of possible causes, never a single
    asserted one (GLM grader finding P2, 2026-08-15: the previous message text asserted "the
    server did not honor the fresh conversation id" as if that were the only possible
    explanation — it is one hypothesis among several: the payload could also carry no
    conversation_id field at all, or the id we're comparing against could itself be a parse
    artifact)."""
    hypotheses: list[str] = []
    if conversation_id_returned is None:
        hypotheses.append("payload carries no conversation_id field at all")
    elif conversation_id_returned != conversation_id_sent:
        hypotheses.append(
            f"server echoed back a different conversation_id ({conversation_id_returned!r}) "
            f"than the one sent ({conversation_id_sent!r})"
        )
    if conversation_id_returned == CONTAMINATED_CONVERSATION_ID:
        hypotheses.append(
            f"conversation_id equals the known-contaminated persistent conversation id "
            f"{CONTAMINATED_CONVERSATION_ID}"
        )
    return hypotheses


def build_record(
    *,
    query_id: str,
    question: str,
    notebook_id: str,
    conversation_id_sent: str,
    returncode: int,
    stdout: str,
    stderr: str,
    ts_asked_utc: str,
    ts_answered_utc: str,
    nlm_version: str,
) -> dict[str, Any]:
    """Build the JSONL record. Judges the OUTPUT JSON, never the exit code alone, in EITHER
    direction (W104 + GLM grader finding P2): rc==0 does not prove a good answer, and rc!=0
    does not prove a worthless one — stdout is always parsed and the isolation check always
    runs, regardless of returncode.
    """
    record: dict[str, Any] = {
        "query_id": query_id,
        "question": question,
        "notebook_id": notebook_id,
        "conversation_id_sent": conversation_id_sent,
        "ts_utc": ts_answered_utc,
        "asked_at_utc": ts_asked_utc,
        "nlm_version": nlm_version,
        "returncode": returncode,
        "sha256_raw_response": hashlib.sha256((stdout or "").encode("utf-8")).hexdigest(),
    }

    payload, parse_error = _try_parse_json(stdout)

    if payload is None:
        if returncode != 0:
            record["status"] = "CLI_ERROR"
            record["anomaly"] = f"nlm exited {returncode} and stdout did not parse as JSON ({parse_error})"
        else:
            record["status"] = "UNPARSEABLE_JSON"
            record["anomaly"] = parse_error
        if stderr:
            record["stderr"] = stderr[-4000:]
        if stdout:
            record["raw_stdout"] = stdout[-4000:]
        return record

    if not isinstance(payload, dict):
        record["status"] = "UNEXPECTED_SHAPE"
        record["anomaly"] = f"payload is a {type(payload).__name__}, expected a dict"
        record["raw_stdout"] = stdout[-4000:]
        if stderr:
            record["stderr"] = stderr[-4000:]
        return record

    conversation_id_returned = payload.get("conversation_id")
    record["conversation_id_returned"] = conversation_id_returned
    record["answer"] = payload.get("answer")
    record["citations"] = payload.get("citations")
    record["references"] = payload.get("references")
    record["sources_used"] = payload.get("sources_used")
    record["turn_number"] = payload.get("turn_number")
    record["is_follow_up"] = payload.get("is_follow_up")

    hypotheses = _isolation_hypotheses(conversation_id_sent, conversation_id_returned)

    if returncode != 0:
        # A valid JSON payload came back despite a nonzero exit (e.g. the CLI printed a
        # warning to stderr and still exited non-zero). Preserve BOTH signals — never silently
        # drop the payload just because rc!=0.
        record["stderr"] = stderr[-4000:] if stderr else None
        if hypotheses:
            record["status"] = "ISOLATION_MISMATCH"
            record["anomaly"] = (
                f"nlm exited {returncode} AND the conversation isolation check failed — "
                "possible causes (not narrowed to one): " + "; ".join(hypotheses)
            )
        else:
            record["status"] = "CLI_ERROR_WITH_JSON"
            record["anomaly"] = (
                f"nlm exited {returncode} despite returning a parseable, isolation-clean JSON "
                "payload — the answer/citations fields above are still usable"
            )
        return record

    if hypotheses:
        record["status"] = "ISOLATION_MISMATCH"
        record["anomaly"] = (
            "conversation isolation check failed — possible causes (not narrowed to one): "
            + "; ".join(hypotheses)
        )
    else:
        record["status"] = "OK"

    return record


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append-only. Never rewrites the file, never truncates, never re-reads to dedup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _timeout_record(
    *,
    query_id: str,
    question: str,
    notebook_id: str,
    conversation_id_sent: str,
    timeout: float,
    exc: "subprocess.TimeoutExpired",
    ts_asked_utc: str,
    ts_answered_utc: str,
    nlm_version: str,
) -> dict[str, Any]:
    def _decode(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    partial_stdout = _decode(getattr(exc, "output", None))
    partial_stderr = _decode(getattr(exc, "stderr", None))
    return {
        "query_id": query_id,
        "question": question,
        "notebook_id": notebook_id,
        "conversation_id_sent": conversation_id_sent,
        "ts_utc": ts_answered_utc,
        "asked_at_utc": ts_asked_utc,
        "nlm_version": nlm_version,
        "returncode": None,
        "status": "TIMEOUT",
        "anomaly": f"nlm did not return within the {timeout}s query timeout (subprocess.run timeout={exc.timeout}s)",
        "sha256_raw_response": hashlib.sha256(partial_stdout.encode("utf-8")).hexdigest(),
        "partial_stdout": partial_stdout[-4000:],
        "partial_stderr": partial_stderr[-4000:],
    }


def run_one_query(
    *,
    query_id: str,
    question: str,
    notebook_id: str = NB2_ID,
    timeout: float = 120.0,
    log_path: Path = DEFAULT_LOG_PATH,
    nlm_bin: str = DEFAULT_NLM_BIN,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Mint a fresh conversation, run one query, append the record, return it.

    Raises IsolationMismatchError or QueryTimeoutError (in both cases AFTER the record is
    already durably appended) on the respective failure — the log is always the anomaly's
    domicile first, the exception is the fail-loud signal second.
    """
    conversation_id_sent = str(uuid.uuid4())
    nlm_version = get_nlm_version(nlm_bin=nlm_bin, runner=runner)
    ts_asked = utcnow_iso()
    try:
        proc = run_nlm_query(
            notebook_id,
            question,
            conversation_id_sent,
            timeout=timeout,
            nlm_bin=nlm_bin,
            runner=runner,
        )
    except subprocess.TimeoutExpired as exc:
        ts_answered = utcnow_iso()
        record = _timeout_record(
            query_id=query_id,
            question=question,
            notebook_id=notebook_id,
            conversation_id_sent=conversation_id_sent,
            timeout=timeout,
            exc=exc,
            ts_asked_utc=ts_asked,
            ts_answered_utc=ts_answered,
            nlm_version=nlm_version,
        )
        append_jsonl(log_path, record)
        raise QueryTimeoutError(record["anomaly"], record=record) from exc

    ts_answered = utcnow_iso()
    record = build_record(
        query_id=query_id,
        question=question,
        notebook_id=notebook_id,
        conversation_id_sent=conversation_id_sent,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        ts_asked_utc=ts_asked,
        ts_answered_utc=ts_answered,
        nlm_version=nlm_version,
    )
    append_jsonl(log_path, record)
    if record["status"] == "ISOLATION_MISMATCH":
        raise IsolationMismatchError(record["anomaly"], record=record)
    return record


def _content_hash(sources: list[dict[str, Any]]) -> str:
    """Stable 8-hex-char hash of the sources list CONTENT (not the timestamped wrapper) —
    two honest captures of the same source list on the same day get the same filename;
    different content never collides with an old filename by accident."""
    canonical = json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def snapshot_sources(
    *,
    notebook_id: str = NB2_ID,
    out_dir: Path = DEFAULT_SOURCES_DIR,
    nlm_bin: str = DEFAULT_NLM_BIN,
    runner: Runner = subprocess.run,
    date_str: str | None = None,
) -> Path:
    """Freeze the notebook's source id<->title map (read-only listing, never a mutation).

    Filename carries a content short-hash (`nb2-source-snapshot-<date>-<sha8>.json`, GLM
    grader finding P2, 2026-08-15) so a stale or hand-edited file that happens to sit at the
    same date-stamped path with DIFFERENT sources is detected and refused rather than silently
    overwritten. Same content at the same path is treated as an idempotent no-op (the file is
    left untouched, not re-timestamped).
    """
    cmd = [nlm_bin, "source", "list", notebook_id, "--json"]
    proc = runner(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"nlm source list failed rc={proc.returncode}: {proc.stderr[-2000:]}")
    sources = json.loads(proc.stdout)
    if not isinstance(sources, list):
        raise RuntimeError(f"nlm source list --json returned a {type(sources).__name__}, expected a list")

    date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content_hash = _content_hash(sources)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"nb2-source-snapshot-{date_str}-{content_hash}.json"

    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            existing_sources = existing.get("sources") if isinstance(existing, dict) else None
        except json.JSONDecodeError:
            existing_sources = None
        if existing_sources != sources:
            raise FileExistsError(
                f"{out_path} already exists with DIFFERENT sources content than what was just "
                "fetched — same date+content-hash filename should imply identical content; "
                "refusing to overwrite. Investigate (hand-edited file? true hash collision?) "
                "before deleting it manually."
            )
        return out_path  # identical content already frozen for this date — idempotent no-op

    snapshot = {
        "notebook_id": notebook_id,
        "captured_at_utc": utcnow_iso(),
        "nlm_version": get_nlm_version(nlm_bin=nlm_bin, runner=runner),
        "source_count": len(sources),
        "content_sha256_8": content_hash,
        "sources": sources,
    }
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)

    q = sub.add_parser("query", help="Run one isolated (fresh-conversation) NB-2 query")
    q.add_argument("--query-id", required=True)
    q.add_argument("--question", required=True)
    q.add_argument("--notebook-id", default=NB2_ID)
    q.add_argument("--timeout", type=float, default=120.0)
    q.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    q.add_argument("--nlm-bin", default=DEFAULT_NLM_BIN)

    s = sub.add_parser("snapshot-sources", help="Freeze the 131-source id<->title map (read-only)")
    s.add_argument("--notebook-id", default=NB2_ID)
    s.add_argument("--out-dir", type=Path, default=DEFAULT_SOURCES_DIR)
    s.add_argument("--nlm-bin", default=DEFAULT_NLM_BIN)
    s.add_argument("--date", default=None)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.mode == "query":
        try:
            record = run_one_query(
                query_id=args.query_id,
                question=args.question,
                notebook_id=args.notebook_id,
                timeout=args.timeout,
                log_path=args.log,
                nlm_bin=args.nlm_bin,
            )
        except IsolationMismatchError as exc:
            print(f"ISOLATION_MISMATCH: {exc}", file=sys.stderr)
            return 3
        except QueryTimeoutError as exc:
            print(f"TIMEOUT: {exc}", file=sys.stderr)
            return 4
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0 if record["status"] == "OK" else 1

    if args.mode == "snapshot-sources":
        try:
            out_path = snapshot_sources(
                notebook_id=args.notebook_id,
                out_dir=args.out_dir,
                nlm_bin=args.nlm_bin,
                date_str=args.date,
            )
        except FileExistsError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 5
        print(f"wrote {out_path}")
        return 0

    return 2  # pragma: no cover - argparse enforces `required=True` on the subparser


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
