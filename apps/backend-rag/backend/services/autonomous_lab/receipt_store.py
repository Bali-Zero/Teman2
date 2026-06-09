"""Append-only receipt persistence for autonomous lab runs."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.autonomous_lab.planner import LabRun
from backend.services.autonomous_lab.reviewer import AutonomousLabReviewer

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_FORBIDDEN_RECEIPT_KEYS = frozenset({"raw", "raw_text", "text", "html_content"})
_UNPERSISTABLE_REVIEW_RULES = frozenset(
    {
        "deploy_command",
        "merge_command",
        "push_command",
        "raw_text_leakage",
        "unsafe_command",
        "unsafe_target_path",
        "verification_command_not_allowlisted",
    }
)
_RAW_MARKER_RE = re.compile(
    r"\b(?:RAW(?:_[A-Z0-9]+){1,}|[A-Z0-9]+_(?:MUST_NOT_LEAK|SHOULD_NOT_APPEAR))\b"
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"
)
_MUTATING_COMMAND_RE = re.compile(
    r"(?i)\b(?:fly|flyctl)\s+deploy\b"
    r"|\bvercel\s+(?:deploy|--prod)\b"
    r"|\b(?:npm|pnpm|yarn)\s+(?:run\s+)?deploy\b"
    r"|\bgit\s+(?:push|merge|rebase)\b"
    r"|\bgh\s+pr\s+merge\b"
    r"|\bdocker\s+push\b"
    r"|\bkubectl\s+(?:apply|rollout|set)\b"
    r"|\bgcloud\s+run\s+deploy\b"
    r"|\bterraform\s+apply\b"
)


@dataclass(frozen=True)
class ReceiptRecord:
    """Receipt write result."""

    run_id: str
    receipt_path: Path
    event_path: Path
    blocked: bool


class ReceiptStore:
    """Persist receipt-safe lab run records and a lightweight event log."""

    def __init__(self, receipt_dir: Path, *, event_path: Path | None = None) -> None:
        self.receipt_dir = receipt_dir
        self.event_path = event_path or receipt_dir / "events.jsonl"

    def write_run(self, run: LabRun) -> ReceiptRecord:
        """Persist a LabRun receipt without storing raw material text."""
        return self.write_receipt(run.to_receipt())

    def write_receipt(self, receipt: Mapping[str, Any]) -> ReceiptRecord:
        """Persist a receipt payload atomically and append a receipt event."""
        run_id = _receipt_run_id(receipt)
        _validate_run_id(run_id)
        _assert_receipt_safe(receipt)
        _assert_receipt_review_persistable(receipt)

        self.receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = self.receipt_dir / f"{run_id}.json"
        if receipt_path.exists():
            raise FileExistsError(f"receipt already exists for run_id: {run_id}")
        _write_json_atomic(receipt_path, dict(receipt))

        event = {
            "event": "autonomous_lab.receipt_written",
            "run_id": run_id,
            "blocked": _receipt_blocked(receipt),
            "receipt_path": str(receipt_path),
            "written_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        _append_jsonl(self.event_path, event)
        return ReceiptRecord(
            run_id=run_id,
            receipt_path=receipt_path,
            event_path=self.event_path,
            blocked=event["blocked"],
        )

    def load_receipt(self, run_id: str) -> dict[str, Any]:
        """Load a persisted receipt by safe run id."""
        _validate_run_id(run_id)
        path = self.receipt_dir / f"{run_id}.json"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"receipt {path} is not a JSON object")
        return payload

    def list_run_ids(self) -> list[str]:
        """Return known receipt run ids sorted by filename."""
        if not self.receipt_dir.exists():
            return []
        return sorted(
            path.stem
            for path in self.receipt_dir.glob("*.json")
            if path.name != self.event_path.name and _RUN_ID_PATTERN.match(path.stem)
        )


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_PATTERN.match(run_id):
        raise ValueError("run_id must match safe receipt id pattern")


def _receipt_run_id(receipt: Mapping[str, Any]) -> str:
    run_id = str(receipt.get("run_id", "")).strip()
    if run_id:
        return run_id
    run = receipt.get("run")
    if isinstance(run, Mapping):
        return str(run.get("run_id", "")).strip()
    return ""


def _receipt_blocked(receipt: Mapping[str, Any]) -> bool:
    if "blocked" in receipt:
        return bool(receipt["blocked"])
    run = receipt.get("run")
    if isinstance(run, Mapping):
        return bool(run.get("blocked", False))
    return False


def _assert_receipt_safe(value: Any, *, path: str = "$", key: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in _FORBIDDEN_RECEIPT_KEYS:
                raise ValueError(f"receipt contains forbidden raw-content key: {key}")
            _assert_receipt_safe(child, path=f"{path}.{key_text}", key=key_text)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_receipt_safe(child, path=f"{path}[{index}]", key=key)
    elif isinstance(value, str):
        if _RAW_MARKER_RE.search(value) or _SECRET_ASSIGNMENT_RE.search(value):
            raise ValueError(f"receipt contains unsafe raw or secret-like value at {path}")
        if _MUTATING_COMMAND_RE.search(value):
            raise ValueError(f"receipt contains mutating command-like value at {path}")


def _assert_receipt_review_persistable(receipt: Mapping[str, Any]) -> None:
    decision = AutonomousLabReviewer().review(receipt)
    blocked_rules = {
        finding.rule_id
        for finding in decision.findings
        if finding.rule_id in _UNPERSISTABLE_REVIEW_RULES
    }
    blocked_rules.update(_embedded_unpersistable_rules(receipt))
    if blocked_rules:
        raise ValueError(
            "receipt contains unpersistable autonomous lab finding(s): "
            + ", ".join(sorted(blocked_rules))
        )


def _embedded_unpersistable_rules(value: Any) -> set[str]:
    rules: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in {"code", "rule_id"} and isinstance(child, str):
                if child in _UNPERSISTABLE_REVIEW_RULES:
                    rules.add(child)
            elif key_text in {"blockers", "failed_blockers"} and isinstance(child, list):
                rules.update(
                    item
                    for item in child
                    if isinstance(item, str) and item in _UNPERSISTABLE_REVIEW_RULES
                )
            rules.update(_embedded_unpersistable_rules(child))
    elif isinstance(value, list):
        for child in value:
            rules.update(_embedded_unpersistable_rules(child))
    return rules


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_path, path)
        except FileExistsError:
            raise FileExistsError(f"receipt already exists for run_id: {path.stem}") from None
        _fsync_parent_dir(path.parent)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            # The hard link may have been created and the temp file removed by cleanup.
            pass


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        written = os.write(fd, line)
        if written != len(line):
            raise OSError("short write while appending autonomous lab receipt event")
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_parent_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = ["ReceiptRecord", "ReceiptStore"]
