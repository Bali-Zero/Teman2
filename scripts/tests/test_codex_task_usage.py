from __future__ import annotations

import json
from pathlib import Path

from codex_task_usage import account_task


ROOT = "root-session"
TURN = "root-turn"


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def _meta(session_id: str, parent: str | None = None) -> dict:
    payload = {"id": session_id}
    if parent is not None:
        payload["parent_thread_id"] = parent
    return {"type": "session_meta", "payload": payload}


def _usage(
    thread: str,
    response: str,
    *,
    root_turn: str = TURN,
    input_tokens: int = 100,
    cached_input_tokens: int | None = 20,
    output_tokens: int = 10,
    reasoning_output_tokens: int = 2,
) -> dict:
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
    }
    if cached_input_tokens is not None:
        usage["cached_input_tokens"] = cached_input_tokens
    return {
        "type": "token_usage_record",
        "payload": {
            "thread_id": thread,
            "root_turn_id": root_turn,
            "response_id": response,
            "usage": usage,
            "turn_token_usage": {"input_tokens": 999999},
            "thread_token_usage": {"input_tokens": 999999},
        },
    }


def test_accounts_root_and_explicit_descendant_only(tmp_path):
    root = _write(tmp_path / "root.jsonl", [_meta(ROOT), _usage(ROOT, "r1")])
    child = _write(
        tmp_path / "child.jsonl",
        [
            _meta("child", ROOT),
            _usage(
                "child",
                "r2",
                input_tokens=50,
                cached_input_tokens=10,
                output_tokens=5,
                reasoning_output_tokens=1,
            ),
        ],
    )
    unrelated = _write(
        tmp_path / "unrelated.jsonl",
        [_meta("unrelated"), _usage("unrelated", "r3", input_tokens=900)],
    )

    report = account_task([root, child, unrelated], ROOT, TURN)

    assert report["included_threads"] == [ROOT, "child"]
    assert report["receipt_count"] == 2
    assert report["usage"] == {
        "uncached_input_tokens": 120,
        "cached_input_tokens": 30,
        "output_tokens": 15,
        "reasoning_output_tokens": 3,
    }
    assert report["excluded"]["unrelated_threads"] == 1


def test_duplicate_response_id_counts_once(tmp_path):
    path = _write(
        tmp_path / "root.jsonl",
        [_meta(ROOT), _usage(ROOT, "same"), _usage(ROOT, "same")],
    )

    report = account_task([path], ROOT, TURN)

    assert report["receipt_count"] == 1
    assert report["excluded"]["duplicate_receipts"] == 1
    assert report["usage"]["output_tokens"] == 10


def test_missing_usage_is_unknown_never_zero(tmp_path):
    path = _write(
        tmp_path / "root.jsonl",
        [_meta(ROOT), _usage(ROOT, "r1", cached_input_tokens=None)],
    )

    report = account_task([path], ROOT, TURN)

    assert report["usage"]["cached_input_tokens"] is None
    assert report["usage"]["uncached_input_tokens"] is None
    assert report["missing_field_receipts"] == {
        "cached_input_tokens": 1,
        "uncached_input_tokens": 1,
    }


def test_wrong_root_turn_is_excluded_even_for_a_child(tmp_path):
    root = _write(tmp_path / "root.jsonl", [_meta(ROOT), _usage(ROOT, "r1")])
    child = _write(
        tmp_path / "child.jsonl",
        [_meta("child", ROOT), _usage("child", "r2", root_turn="other")],
    )

    report = account_task([root, child], ROOT, TURN)

    assert report["receipt_count"] == 1
    assert report["excluded"]["other_root_turn"] == 1


def test_incomplete_included_stream_is_reported_and_usage_is_unknown(tmp_path):
    path = tmp_path / "root.jsonl"
    rows = [
        json.dumps(_meta(ROOT)),
        "{not-json",
        json.dumps([]),
        json.dumps({"type": "token_usage_record", "payload": []}),
        json.dumps(_usage(ROOT, "r1")),
    ]
    path.write_text("\n".join(rows) + "\n")

    report = account_task([path], ROOT, TURN)

    assert report["receipt_count"] == 1
    assert report["incomplete_receipt_stream"] is True
    assert all(value is None for value in report["usage"].values())
    assert report["excluded"]["malformed_lines"] == 1
    assert report["excluded"]["non_dict_records"] == 1
    assert report["excluded"]["non_dict_payloads"] == 1


def test_read_error_in_included_stream_is_not_silent(tmp_path, monkeypatch):
    path = _write(tmp_path / "root.jsonl", [_meta(ROOT), _usage(ROOT, "r1")])
    real_open = Path.open
    opens = 0

    def flaky_open(self, *args, **kwargs):
        nonlocal opens
        if self == path:
            opens += 1
            if opens == 2:
                raise OSError("synthetic read failure")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)

    report = account_task([path], ROOT, TURN)

    assert report["incomplete_receipt_stream"] is True
    assert all(value is None for value in report["usage"].values())
    assert report["excluded"]["read_errors"] == 1
