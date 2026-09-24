#!/usr/bin/env python3
"""Aggregate one Codex task from native token receipts without reading prompts.

The task boundary is an explicit root session plus root_turn_id. Descendants
count only when the first session_meta record links them through
parent_thread_id. Output is aggregate JSON; raw rollout records never leave the
local machine.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


FIELDS = ("cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def _first_record(path: Path) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as handle:
            line = handle.readline()
        row = json.loads(line)
    except (OSError, ValueError, RecursionError):
        return None
    return row if isinstance(row, dict) else None


def _session_meta(path: Path) -> tuple[str, str | None] | None:
    first = _first_record(path)
    if not first or first.get("type") != "session_meta":
        return None
    payload = first.get("payload")
    if not isinstance(payload, dict):
        return None
    session_id = payload.get("id") or payload.get("session_id")
    parent = payload.get("parent_thread_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id, parent if isinstance(parent, str) and parent else None


def _is_descendant(
    session_id: str, root_session_id: str, parents: dict[str, str | None]
) -> bool:
    if session_id == root_session_id:
        return True
    seen: set[str] = set()
    current = session_id
    while current not in seen:
        seen.add(current)
        parent = parents.get(current)
        if parent is None:
            return False
        if parent == root_session_id:
            return True
        current = parent
    return False


def _records(
    path: Path, diagnostics: dict[str, int]
) -> Iterable[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except (ValueError, RecursionError):
                    diagnostics["malformed_lines"] += 1
                    continue
                if isinstance(row, dict):
                    yield row
                else:
                    diagnostics["non_dict_records"] += 1
    except OSError:
        diagnostics["read_errors"] += 1
        return


def account_task(
    rollout_paths: Iterable[Path], root_session_id: str, root_turn_id: str
) -> dict[str, Any]:
    """Return aggregate usage for one explicit Codex root turn."""
    paths = [Path(path) for path in rollout_paths]
    parents: dict[str, str | None] = {}
    by_session: dict[str, list[Path]] = {}
    malformed_files = 0
    for path in paths:
        meta = _session_meta(path)
        if meta is None:
            malformed_files += 1
            continue
        session_id, parent = meta
        parents.setdefault(session_id, parent)
        by_session.setdefault(session_id, []).append(path)

    included = {
        session_id
        for session_id in by_session
        if _is_descendant(session_id, root_session_id, parents)
    }
    ordered_threads = ([root_session_id] if root_session_id in included else []) + sorted(
        included - {root_session_id}
    )

    totals = {
        "uncached_input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }
    missing = {name: 0 for name in totals}
    seen_responses: set[str] = set()
    duplicate_receipts = 0
    other_root_turn = 0
    receipt_count = 0
    diagnostics = {
        "malformed_lines": 0,
        "non_dict_records": 0,
        "non_dict_payloads": 0,
        "read_errors": 0,
    }

    for session_id in ordered_threads:
        for path in by_session[session_id]:
            for row in _records(path, diagnostics):
                if row.get("type") != "token_usage_record":
                    continue
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    diagnostics["non_dict_payloads"] += 1
                    continue
                if payload.get("root_turn_id") != root_turn_id:
                    other_root_turn += 1
                    continue
                response_id = payload.get("response_id")
                if not isinstance(response_id, str) or not response_id:
                    response_id = f"{session_id}:{path}:{receipt_count}"
                if response_id in seen_responses:
                    duplicate_receipts += 1
                    continue
                seen_responses.add(response_id)
                receipt_count += 1
                usage = payload.get("usage")
                usage = usage if isinstance(usage, dict) else {}

                input_value = usage.get("input_tokens")
                cached_value = usage.get("cached_input_tokens")
                valid_input = (
                    isinstance(input_value, int)
                    and not isinstance(input_value, bool)
                    and input_value >= 0
                )
                valid_cached = (
                    isinstance(cached_value, int)
                    and not isinstance(cached_value, bool)
                    and cached_value >= 0
                    and valid_input
                    and cached_value <= input_value
                )
                if valid_cached:
                    totals["cached_input_tokens"] += cached_value
                    totals["uncached_input_tokens"] += input_value - cached_value
                else:
                    missing["cached_input_tokens"] += 1
                    missing["uncached_input_tokens"] += 1

                for field in ("output_tokens", "reasoning_output_tokens"):
                    value = usage.get(field)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        totals[field] += value
                    else:
                        missing[field] += 1

    for field, count in missing.items():
        if count or receipt_count == 0:
            totals[field] = None
    incomplete_receipt_stream = any(diagnostics.values())
    if incomplete_receipt_stream:
        totals = {field: None for field in totals}

    return {
        "root_session_id": root_session_id,
        "root_turn_id": root_turn_id,
        "included_threads": ordered_threads,
        "receipt_count": receipt_count,
        "usage": totals,
        "incomplete_receipt_stream": incomplete_receipt_stream,
        "missing_field_receipts": {
            field: count for field, count in missing.items() if count
        },
        "excluded": {
            "unrelated_threads": len(by_session) - len(included),
            "other_root_turn": other_root_turn,
            "duplicate_receipts": duplicate_receipts,
            "malformed_files": malformed_files,
            **diagnostics,
        },
    }


def discover_rollouts(codex_home: Path) -> list[Path]:
    roots = (codex_home / "sessions", codex_home / "archived_sessions")
    return sorted(path for root in roots if root.exists() for path in root.rglob("*.jsonl"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-session-id", required=True)
    parser.add_argument("--root-turn-id", required=True)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    args = parser.parse_args(argv)
    report = account_task(
        discover_rollouts(args.codex_home), args.root_session_id, args.root_turn_id
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
