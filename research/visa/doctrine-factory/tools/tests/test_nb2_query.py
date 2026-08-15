"""No-network tests for nb2_query.py (all `nlm` invocations are mocked subprocess runners).

Covers the mandate's required guilt/innocence surface:
  - refuses on conversation_id mismatch (mocked subprocess)
  - JSONL append-only behavior
"""
import json
import subprocess
import uuid

import nb2_query as nq
import pytest


def _cmd_conversation_id(cmd):
    idx = cmd.index("-c")
    return cmd[idx + 1]


def make_fake_runner(conversation_id_override=None, nlm_version="nlm version 0.9.8 (fake)\n"):
    """Fake `runner(cmd, ...) -> CompletedProcess`.

    Echoes the `-c` value it was sent back as `conversation_id` in the JSON payload, unless
    `conversation_id_override` is given — used to simulate the server NOT honoring the fresh
    conversation id (the isolation-mismatch guilt case).
    """

    def runner(cmd, capture_output=True, text=True, timeout=None):
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=nlm_version, stderr="")
        sent = _cmd_conversation_id(cmd)
        returned = conversation_id_override if conversation_id_override is not None else sent
        payload = {
            "answer": "PONG",
            "conversation_id": returned,
            "sources_used": [],
            "citations": {},
            "references": [],
            "turn_number": 1,
            "is_follow_up": False,
        }
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    return runner


def test_run_one_query_ok(tmp_path):
    log_path = tmp_path / "response-log.jsonl"
    record = nq.run_one_query(
        query_id="q1",
        question="Reply with exactly the word PONG.",
        log_path=log_path,
        runner=make_fake_runner(),
    )
    assert record["status"] == "OK"
    assert record["conversation_id_sent"] == record["conversation_id_returned"]
    assert record["conversation_id_sent"] != nq.CONTAMINATED_CONVERSATION_ID
    uuid.UUID(record["conversation_id_sent"])  # raises ValueError if not a real UUID


def test_conversation_id_sent_is_never_reused_across_calls(tmp_path):
    log_path = tmp_path / "response-log.jsonl"
    r1 = nq.run_one_query(query_id="q1", question="a", log_path=log_path, runner=make_fake_runner())
    r2 = nq.run_one_query(query_id="q2", question="b", log_path=log_path, runner=make_fake_runner())
    assert r1["conversation_id_sent"] != r2["conversation_id_sent"]


def test_jsonl_append_only(tmp_path):
    log_path = tmp_path / "response-log.jsonl"
    nq.run_one_query(query_id="q1", question="q1?", log_path=log_path, runner=make_fake_runner())
    nq.run_one_query(query_id="q2", question="q2?", log_path=log_path, runner=make_fake_runner())
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    ids = [json.loads(line)["query_id"] for line in lines]
    assert ids == ["q1", "q2"]


def test_jsonl_append_only_preserves_preexisting_content(tmp_path):
    log_path = tmp_path / "response-log.jsonl"
    log_path.write_text('{"query_id": "pre-existing"}\n', encoding="utf-8")
    nq.run_one_query(query_id="q1", question="q1?", log_path=log_path, runner=make_fake_runner())
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["query_id"] == "pre-existing"
    assert json.loads(lines[1])["query_id"] == "q1"


def test_refuses_on_conversation_id_mismatch(tmp_path):
    """Guilt case: the server echoes back the KNOWN-CONTAMINATED persistent conversation id
    instead of the fresh one we sent — must fail loud (raise) AND record the anomaly."""
    log_path = tmp_path / "response-log.jsonl"
    bad_runner = make_fake_runner(conversation_id_override=nq.CONTAMINATED_CONVERSATION_ID)
    with pytest.raises(nq.IsolationMismatchError):
        nq.run_one_query(query_id="q-mismatch", question="q?", log_path=log_path, runner=bad_runner)

    # Fail LOUD, but the record must still be durably appended before the raise.
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "ISOLATION_MISMATCH"
    assert record["conversation_id_returned"] == nq.CONTAMINATED_CONVERSATION_ID
    assert "anomaly" in record


def test_refuses_on_arbitrary_conversation_id_mismatch(tmp_path):
    """Guilt case, second flavor: server echoes back a DIFFERENT id than the one sent (not
    necessarily the known-contaminated one) — must still be caught."""
    log_path = tmp_path / "response-log.jsonl"
    bad_runner = make_fake_runner(conversation_id_override="not-the-id-we-sent")
    with pytest.raises(nq.IsolationMismatchError):
        nq.run_one_query(query_id="q-mismatch2", question="q?", log_path=log_path, runner=bad_runner)
    record = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["status"] == "ISOLATION_MISMATCH"


def test_build_record_handles_nonzero_returncode():
    record = nq.build_record(
        query_id="q1",
        question="q",
        notebook_id="nb",
        conversation_id_sent="c1",
        returncode=1,
        stdout="",
        stderr="boom",
        ts_asked_utc="t0",
        ts_answered_utc="t1",
        nlm_version="v",
    )
    assert record["status"] == "CLI_ERROR"
    assert record["sha256_raw_response"]  # present even on error (hashes stdout, may be empty)


def test_build_record_handles_unparseable_json():
    record = nq.build_record(
        query_id="q1",
        question="q",
        notebook_id="nb",
        conversation_id_sent="c1",
        returncode=0,
        stdout="not json",
        stderr="",
        ts_asked_utc="t0",
        ts_answered_utc="t1",
        nlm_version="v",
    )
    assert record["status"] == "UNPARSEABLE_JSON"


def test_build_record_handles_non_dict_payload():
    record = nq.build_record(
        query_id="q1",
        question="q",
        notebook_id="nb",
        conversation_id_sent="c1",
        returncode=0,
        stdout="[1, 2, 3]",
        stderr="",
        ts_asked_utc="t0",
        ts_answered_utc="t1",
        nlm_version="v",
    )
    assert record["status"] == "UNEXPECTED_SHAPE"


def test_snapshot_sources_writes_frozen_id_title_map(tmp_path):
    def runner(cmd, capture_output=True, text=True, timeout=None):
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="nlm version 0.9.8\n", stderr="")
        sources = [
            {"id": "s1", "title": "Regulation A", "type": "generated_text", "url": None, "status": 2},
            {"id": "s2", "title": "Regulation B", "type": "youtube", "url": None, "status": 2},
        ]
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(sources), stderr="")

    out_path = nq.snapshot_sources(out_dir=tmp_path, runner=runner, date_str="2026-08-15")
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["source_count"] == 2
    assert {s["id"] for s in data["sources"]} == {"s1", "s2"}


def test_snapshot_sources_raises_on_nonzero_returncode(tmp_path):
    def runner(cmd, capture_output=True, text=True, timeout=None):
        if "--version" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="nlm version 0.9.8\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    with pytest.raises(RuntimeError):
        nq.snapshot_sources(out_dir=tmp_path, runner=runner, date_str="2026-08-15")
