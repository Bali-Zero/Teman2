"""Tests for scripts/tp1_batch_runner.py — offline: the TP1 door is replaced by a fake call."""

from __future__ import annotations

import datetime as dt
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tp1_batch_runner as tbr  # noqa: E402

FUTURE = dt.datetime(2099, 1, 1, tzinfo=dt.timezone.utc)


class FakeCall:
    """Answers from a script of responses; counts every call (each one would be paid)."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def __call__(self, model: str, prompt: str) -> dict:
        with self.lock:
            self.calls.append(prompt)
            if self.script:
                return self.script.pop(0)
        return ok_response()


def ok_response(tokens: int = 100) -> dict:
    return {"status": 200, "answer": '```json\n{"defects": []}\n```', "secs": 0.1,
            "usage": {"prompt_tokens": tokens - 10, "completion_tokens": 10, "total_tokens": tokens}}


def jobs(n: int) -> list[dict]:
    return [{"id": f"j{i}", "prompt": f"prompt {i}", "lane": "test"} for i in range(n)]


def runner(tmp_path: Path, call, n: int = 3, **kw) -> tbr.Runner:
    kw.setdefault("stop_at", FUTURE)
    kw.setdefault("backoff", 0.01)
    return tbr.Runner(jobs(n), tmp_path, call, model="qwen3.8-max", **kw)


def rows(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]


def heartbeat(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "heartbeat.json").read_text())


def test_drains_queue_writes_rows_and_counts_tokens(tmp_path):
    call = FakeCall()
    assert runner(tmp_path, call).run() == 0
    out = rows(tmp_path)
    assert sorted(r["id"] for r in out) == ["j0", "j1", "j2"]
    assert all(r["status"] == "ok" and r["parsed"] == {"defects": []} for r in out)
    hb = heartbeat(tmp_path)
    assert hb["state"] == "stopped:drained" and hb["ok"] == 3 and hb["total_tokens"] == 300


def test_rerun_never_pays_for_a_finished_job_twice(tmp_path):
    first = FakeCall()
    runner(tmp_path, first).run()
    second = FakeCall()
    assert runner(tmp_path, second).run() == 0
    assert second.calls == []
    assert len(rows(tmp_path)) == 3
    assert heartbeat(tmp_path)["skipped_done"] == 3


def test_retry_failed_resends_only_non_ok_rows(tmp_path):
    runner(tmp_path, FakeCall([{"status": 400, "error": "bad request", "usage": {}}]), n=2,
           concurrency=1).run()
    assert {r["id"]: r["status"] for r in rows(tmp_path)} == {"j0": "rejected", "j1": "ok"}
    again = FakeCall()
    runner(tmp_path, again, n=2, retry_failed=True).run()
    assert again.calls == ["prompt 0"]


def test_hard_quota_error_stops_dispatch_and_writes_no_row(tmp_path):
    quota = {"status": 429, "error": '{"code":"insufficient_quota","message":"quota exhausted"}', "usage": {}}
    call = FakeCall([quota])
    assert runner(tmp_path, call, n=5, concurrency=1).run() == 5
    assert call.calls == ["prompt 0"]
    assert not (tmp_path / "results.jsonl").exists()
    hb = heartbeat(tmp_path)
    assert hb["state"] == "stopped:quota" and hb["last_error"].startswith("quota")


@pytest.mark.parametrize("status", [401, 402, 403])
def test_auth_or_payment_status_stops_the_run(tmp_path, status):
    call = FakeCall([{"status": status, "error": "denied", "usage": {}}])
    assert runner(tmp_path, call, n=3, concurrency=1).run() == 5
    assert len(call.calls) == 1


def test_rate_limit_backs_off_halves_concurrency_and_retries(tmp_path):
    rate = {"status": 429, "error": "Throttling.RateQuota: Requests rate limit exceeded", "usage": {}}
    call = FakeCall([rate])
    r = runner(tmp_path, call, n=2, concurrency=4)
    assert r.run() == 0
    assert {x["id"] for x in rows(tmp_path)} == {"j0", "j1"}
    assert heartbeat(tmp_path)["rate_limited"] == 1
    assert r.limit <= 3


def test_persistent_rate_limit_at_floor_is_presumed_quota(tmp_path):
    rate = {"status": 429, "error": "Too Many Requests", "usage": {}}
    call = FakeCall([rate] * 50)
    assert runner(tmp_path, call, n=2, concurrency=1, max_rate_strikes=3).run() == 5
    assert len(call.calls) == 3


def test_transient_error_retries_then_records_failure(tmp_path):
    dead = {"status": None, "error": "timed out", "usage": {}}
    call = FakeCall([dead, dead])
    assert runner(tmp_path, call, n=1, max_attempts=2).run() == 0
    assert [(r["status"], r["attempts"]) for r in rows(tmp_path)] == [("failed", 2)]
    assert len(call.calls) == 2


def test_kill_file_blocks_all_dispatch(tmp_path):
    (tmp_path / "STOP").touch()
    call = FakeCall()
    assert runner(tmp_path, call).run() == 3
    assert call.calls == []
    assert heartbeat(tmp_path)["state"] == "stopped:kill-file"


def test_deadline_in_the_past_blocks_all_dispatch(tmp_path):
    call = FakeCall()
    past = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    assert runner(tmp_path, call, stop_at=past).run() == 3
    assert call.calls == []


def test_token_budget_stops_dispatch(tmp_path):
    call = FakeCall()
    # max_concurrency=1 pins the window: the budget is checked before each dispatch, so
    # with N calls in flight it can overshoot by at most N-1 calls — never more.
    assert runner(tmp_path, call, n=5, concurrency=1, max_concurrency=1, token_budget=250).run() == 3
    assert len(call.calls) == 3


def test_torn_last_line_reruns_that_job_only(tmp_path):
    runner(tmp_path, FakeCall(), n=2).run()
    good = [line for line in (tmp_path / "results.jsonl").read_text().splitlines() if '"j0"' in line]
    (tmp_path / "results.jsonl").write_text(good[0] + "\n" + '{"id": "j1", "sta')
    again = FakeCall()
    runner(tmp_path, again, n=2).run()
    assert again.calls == ["prompt 1"]


@pytest.mark.parametrize(
    "status,body,kind",
    [
        (200, "", "ok"),
        (429, "Throttling.AllocationQuota: Allocated quota exceeded", "rate"),
        (429, '{"error":{"code":"insufficient_quota"}}', "quota"),
        (400, "Arrearage: Access denied, please make sure your account is in good standing", "quota"),
        (403, "", "quota"),
        (500, "internal error", "transient"),
        (None, "timed out", "transient"),
        (400, "Range of input length should be [1, 98304]", "rejected"),
        (302, "", "quota"),
    ],
)
def test_classify(status, body, kind):
    assert tbr.classify(status, body) == kind


def test_endpoint_is_the_token_plan_gateway_and_nothing_else():
    tbr.assert_token_plan_endpoint()
    with pytest.raises(SystemExit):
        tbr.assert_token_plan_endpoint("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions")


def test_duplicate_queue_ids_are_refused(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text('{"id": "a", "prompt": "x"}\n{"id": "a", "prompt": "y"}\n')
    with pytest.raises(ValueError):
        tbr.load_queue(q)


def test_out_dir_inside_the_repo_is_refused(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text('{"id": "a", "prompt": "x"}\n')
    inside = Path(tbr.__file__).resolve().parent / "tp1-out"
    with pytest.raises(SystemExit):
        tbr.main(["--queue", str(q), "--out-dir", str(inside)])


def test_second_runner_on_the_same_out_dir_refuses_without_calling(tmp_path):
    import fcntl

    tmp_path.mkdir(exist_ok=True)
    with open(tmp_path / ".lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        call = FakeCall()
        assert runner(tmp_path, call).run() == 6
        assert call.calls == []


def test_malformed_usage_after_a_paid_200_is_not_paid_again(tmp_path, monkeypatch):
    raw = json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": "n/a"}})
    sent = []
    monkeypatch.setattr(tbr, "no_stream_chat_completion", lambda *a: (sent.append(1), (200, raw, ""))[1])

    def call(model, prompt):
        return tbr.tp1_call_once(model, prompt, "medium", 10, 1.0, "dummy")

    assert runner(tmp_path, call, n=1).run() == 0
    assert len(sent) == 1 and rows(tmp_path)[0]["status"] == "ok"


def test_redirects_are_refused_not_followed():
    assert tbr._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://example.invalid/") is None
