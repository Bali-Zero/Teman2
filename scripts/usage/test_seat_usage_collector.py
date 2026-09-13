"""Tests for seat_usage_collector.collect_codex — regression pin for the
2026-08-20 "in=3.3e11/giorno" bug.

Real shape (verified against a live ~/.codex/sessions/**/*.jsonl on M5,
2026-08-20 seat-burn forensics): every `token_count` event carries TWO
sibling objects — `info.total_token_usage` (cumulative for the WHOLE
session, monotonically non-decreasing) and `info.last_token_usage` (delta
of just the last turn). The old collector did a blind DFS over the entire
JSON tree of every line and summed EVERY dict shaped like
{input_tokens,output_tokens} it found — i.e. it summed the cumulative
snapshot again at every single turn, on sessions with hundreds of turns.
That produces totals several orders of magnitude larger than real token
consumption (observed live: in=3.3e11/giorno on a machine whose actual
Codex Pro plan usage is in the low hundred-thousands).

Fixture numbers below are lifted verbatim from a real session file
(~/.codex/sessions/2026/08/19/rollout-2026-08-19T07-50-25-*.jsonl) so the
test pins the ACTUAL shape, not an invented one.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seat_usage_collector as suc  # noqa: E402

SINCE = datetime(2000, 1, 1, tzinfo=timezone.utc)  # far enough back to include any fixture mtime


def _token_count_line(total_in: int, total_out: int, last_in: int, last_out: int) -> str:
    """One `token_count` event_msg line, shaped exactly like a real Codex
    session file (payload.type == "token_count", info.total_token_usage =
    cumulative, info.last_token_usage = delta of the last turn only)."""
    return json.dumps({
        "timestamp": "2026-08-19T00:00:00.000Z",
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": total_in,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": total_out,
                    "reasoning_output_tokens": 0,
                    "total_tokens": total_in + total_out,
                },
                "last_token_usage": {
                    "input_tokens": last_in,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": last_out,
                    "reasoning_output_tokens": 0,
                    "total_tokens": last_in + last_out,
                },
                "model_context_window": 258400,
            },
        },
    })


def _write_session(tmp_path: Path, name: str, lines: list[str]) -> Path:
    sessions_dir = tmp_path / "sessions" / "2026" / "08" / "19"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    fp = sessions_dir / name
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fp


# --------------------------------------------------------------- the core bug


def test_collect_codex_last_wins_not_summed(tmp_path):
    """Guilt case, real numbers from a live session: 3 token_count events
    where total_token_usage GROWS (42053 -> 91887 -> 149329 input tokens)
    while last_token_usage is the per-turn delta (42053 -> 49834 -> 57442,
    which correctly sums to the final total — internal consistency check
    on the real data). The fixed collector must report the session's FINAL
    cumulative total (149329 in / 4024 out), not any sum across events."""
    lines = [
        _token_count_line(total_in=42053, total_out=1345, last_in=42053, last_out=1345),
        _token_count_line(total_in=91887, total_out=2071, last_in=49834, last_out=726),
        _token_count_line(total_in=149329, total_out=4024, last_in=57442, last_out=1953),
    ]
    _write_session(tmp_path, "rollout-fixture.jsonl", lines)

    result = suc.collect_codex(str(tmp_path), SINCE)
    assert result["status"] == "ok"
    day = next(iter(result["days"].values()))
    assert day["in"] == 149329
    assert day["out"] == 4024

    # Document the magnitude of the bug this pins: the OLD collector did a
    # blind DFS-sum over every {input_tokens,output_tokens} dict in every
    # line — i.e. total_token_usage AND last_token_usage, for all 3 events.
    naive_sum_in = sum(x["total_token_usage"]["input_tokens"] for x in (
        {"total_token_usage": {"input_tokens": 42053}},
        {"total_token_usage": {"input_tokens": 91887}},
        {"total_token_usage": {"input_tokens": 149329}},
    )) + sum((42053, 49834, 57442))  # + last_token_usage.input_tokens per event
    assert naive_sum_in == 432598
    assert day["in"] < naive_sum_in, (
        "fixed collector must land well under the old blind-sum reading — "
        "on a real session with hundreds of events this gap is what produced "
        "in=3.3e11/giorno"
    )


def test_collect_codex_stays_sane_order_of_magnitude_on_long_session(tmp_path):
    """A session with many turns (proxy for the real 900+-event sessions
    found on M5 2026-08-20) must still land in the thousands-to-low-millions
    range, never explode past it. The old DFS-sum-everything behavior grows
    roughly O(n^2) with turn count because each of n events re-contributes
    its (growing) cumulative snapshot."""
    n = 300
    lines = [
        _token_count_line(total_in=i * 1000, total_out=i * 40, last_in=1000, last_out=40)
        for i in range(1, n + 1)
    ]
    _write_session(tmp_path, "rollout-long.jsonl", lines)

    result = suc.collect_codex(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    # exact: last-wins must equal the FINAL event's cumulative total
    assert day["in"] == n * 1000
    assert day["out"] == n * 40
    # sanity ceiling: nowhere near the old bug's observed in=3.3e11/giorno
    assert day["in"] < 10_000_000


# --------------------------------------------------------------- schema-drift tolerance


def test_collect_codex_legacy_flat_schema_still_tolerated(tmp_path):
    """Docstring-promised resilience: an older/alternate Codex schema that
    puts input_tokens/output_tokens at the TOP level (no payload/info
    wrapper) must still be picked up — last-wins, same as the real shape."""
    lines = [
        json.dumps({"input_tokens": 500, "output_tokens": 100}),
        json.dumps({"input_tokens": 1200, "output_tokens": 300}),
    ]
    _write_session(tmp_path, "rollout-legacy.jsonl", lines)

    result = suc.collect_codex(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["in"] == 1200
    assert day["out"] == 300


def test_collect_codex_prompt_completion_alias_still_tolerated(tmp_path):
    """Same tolerance, alternate legacy key names (prompt_tokens/completion_tokens)."""
    lines = [json.dumps({"prompt_tokens": 777, "completion_tokens": 111})]
    _write_session(tmp_path, "rollout-alias.jsonl", lines)

    result = suc.collect_codex(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["in"] == 777
    assert day["out"] == 111


# --------------------------------------------------------------- innocence / no-crash


def test_collect_codex_absent_dir_returns_status_absent(tmp_path):
    result = suc.collect_codex(str(tmp_path / "nonexistent"), SINCE)
    assert result["status"] == "absent"


def test_collect_codex_ignores_lines_without_token_keyword(tmp_path):
    """Innocence: session-meta / non-usage lines (no 'token' substring) must
    not crash the parser and must not contribute any count."""
    lines = [
        json.dumps({"type": "session_meta", "payload": {"cwd": "/x"}}),
        _token_count_line(total_in=10, total_out=2, last_in=10, last_out=2),
    ]
    _write_session(tmp_path, "rollout-mixed.jsonl", lines)

    result = suc.collect_codex(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["in"] == 10
    assert day["out"] == 2


# ------------------------------------------------------ collect_invocations
#
# Regression pin for the 2026-08-20 "G1 counts OpenClaw's files as agy
# invocations" bug: seat_usage_collector.py::main() had G1 pointed at
# ~/.openclaw/logs (the OpenClaw bridge home — git-sync.log, t4_monitor.log,
# nlm pipeline logs, nothing to do with agy/Antigravity) and a blind
# `rglob("*")` file count over it published a plausible-looking number
# ("recent_files": 11) as if it were agy invocations. A zero would have been
# noticed; a small plausible number was not. The fix requires an identity
# marker (a file characteristic of the seat's real home dir) to exist BEFORE
# any count is trusted — absent marker => status "unknown", never a number.


def test_collect_invocations_wrong_directory_reports_unknown_not_a_count(tmp_path):
    """Guilt: point the collector at a directory that is real, non-empty,
    and recently touched — but has NOTHING to do with the claimed seat (no
    identity marker). This is exactly the shape of the live 2026-08-20 bug
    (an existing, populated, foreign directory). Must report status
    "unknown" and must NOT emit any invocation count."""
    foreign = tmp_path / "openclaw-logs"
    (foreign / "log").mkdir(parents=True)
    # foreign files that would have been miscounted by the old blind rglob
    for name in ("git-sync.log", "t4_monitor.log", "nlm_nb4_pipeline.log"):
        (foreign / name).write_text("noise")
    # even a file that happens to MATCH the entity_glob shape must not save it —
    # identity is checked first, independent of what the glob would find
    (foreign / "log" / "cli-20260101_000000.log").write_text("not really antigravity")

    result = suc.collect_invocations(
        str(foreign), SINCE,
        identity_marker="installation_id",
        entity_glob="log/cli-*.log",
    )
    assert result["status"] == "unknown"
    assert "recent_invocations" not in result
    assert "installation_id" in result["note"]


def test_collect_invocations_real_source_with_marker_counts_correctly(tmp_path):
    """Innocence: a directory that DOES carry the identity marker is counted
    normally — entity_glob scoped to the real invocation-log shape, filtered
    by mtime, cache/scratch/telemetry siblings ignored because the glob
    never reaches them."""
    home = tmp_path / "antigravity-cli"
    (home / "log").mkdir(parents=True)
    (home / "cache").mkdir()
    (home / "installation_id").write_text("fake-id-not-a-secret")
    # 2 recent invocation logs + 1 stale (outside window) + 1 non-matching cache file
    (home / "log" / "cli-20260820_120000.log").write_text("logging before google.Init")
    (home / "log" / "cli-20260820_130000.log").write_text("logging before google.Init")
    stale = home / "log" / "cli-20200101_000000.log"
    stale.write_text("logging before google.Init")
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(stale, (old_time, old_time))
    (home / "cache" / "onboarding.json").write_text("{}")  # must NOT be counted

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = suc.collect_invocations(
        str(home), since,
        identity_marker="installation_id",
        entity_glob="log/cli-*.log",
    )
    assert result["status"] == "ok"
    assert result["recent_invocations"] == 2


def test_collect_invocations_kimi_session_dirs_still_counted_correctly(tmp_path):
    """Innocence 2: K1 (kimi-code) gets the same treatment — session_*
    directories nested under sessions/<workdir>/ are the real per-session
    unit, must still be counted after the shared function was hardened."""
    home = tmp_path / "kimi-code"
    (home / "sessions" / "wd_nuzantara_abc123").mkdir(parents=True)
    (home / "sessions" / "wd_scratchpad_def456").mkdir(parents=True)
    (home / "session_index.jsonl").write_text('{"sessionId":"x"}\n')
    (home / "sessions" / "wd_nuzantara_abc123" / "session_11111111").mkdir()
    (home / "sessions" / "wd_nuzantara_abc123" / "session_22222222").mkdir()
    (home / "sessions" / "wd_scratchpad_def456" / "session_33333333").mkdir()
    (home / "cache").mkdir()
    (home / "cache" / "query-store").mkdir()  # must NOT be counted

    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    result = suc.collect_invocations(
        str(home), since,
        identity_marker="session_index.jsonl",
        entity_glob="sessions/**/session_*",
    )
    assert result["status"] == "ok"
    assert result["recent_invocations"] == 3


def test_collect_invocations_absent_dir_unaffected_by_identity_check(tmp_path):
    """Innocence: a seat whose CLI was never installed on this machine keeps
    reporting "absent" (not "unknown") — the identity check only applies
    once the base dir exists."""
    result = suc.collect_invocations(
        str(tmp_path / "never-installed"), SINCE,
        identity_marker="installation_id",
        entity_glob="log/cli-*.log",
    )
    assert result["status"] == "absent"


# --------------------------------------------------------------- collect_claude
#
# Regression pin for the 2026-09-07 "output 852 vs 14931" defect: Claude
# Code streaming writes the SAME response group (message.id, requestId)
# several times into the transcript, each line a CUMULATIVE snapshot of
# that group's counters growing as the stream advances. The old collector
# deduped on (message.id, requestId) with a first-wins `seen` set, keeping
# the earliest partial snapshot and dropping every later update (measured
# on a completed Sonnet builder transcript: 852 reported vs 14,931 from
# the final snapshots). Correct semantics: last-wins per response group,
# never a sum of the group's snapshots (they are cumulative — summing
# double-counts, same defect class as the Codex 2026-08-20 bug), and a
# missing counter surfaces as "unknown", never 0.
#
# All fixtures below are SYNTHETIC: invented ids, numbers and timestamps
# only — no real transcript content.


def _claude_line(msg_id: str | None, req_id: str | None, input_tokens, output_tokens,
                 cache_read=0, cache_creation=0,
                 ts: str = "2026-08-19T10:00:00.000Z") -> str:
    """One assistant-usage line shaped like a Claude Code transcript entry
    ({message: {id, model, usage}}, requestId, timestamp at top level).
    None => the counter is omitted from the record entirely; a None msg_id
    or req_id is serialized as JSON null, i.e. that half of the identity
    is missing."""
    usage = {}
    for k, v in (("input_tokens", input_tokens), ("output_tokens", output_tokens),
                 ("cache_read_input_tokens", cache_read),
                 ("cache_creation_input_tokens", cache_creation)):
        if v is not None:
            usage[k] = v
    return json.dumps({
        "type": "assistant",
        "timestamp": ts,
        "requestId": req_id,
        "message": {"id": msg_id, "model": "claude-test-model", "usage": usage},
    })


def _write_transcript(tmp_path: Path, name: str, lines: list[str]) -> Path:
    proj = tmp_path / "projects" / "-synthetic-workspace"
    proj.mkdir(parents=True, exist_ok=True)
    fp = proj / name
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fp


def test_collect_claude_streaming_last_snapshot_wins(tmp_path):
    """Guilt case, synthetic: two response groups, each re-written several
    times with growing cumulative snapshots (streaming). The collector must
    report the FINAL snapshot per group, summed across groups — not the
    first snapshot (the old first-wins defect) and not the sum of all
    snapshots (double-counting cumulative data)."""
    lines = [
        # group A: stream grows 100 -> 400 -> 852 output tokens
        _claude_line("msg_a", "req_a", 10, 100, cache_read=0, cache_creation=20),
        _claude_line("msg_a", "req_a", 10, 400, cache_read=0, cache_creation=60),
        _claude_line("msg_a", "req_a", 10, 852, cache_read=5, cache_creation=120),
        # group B: stream grows 50 -> 120 output tokens
        _claude_line("msg_b", "req_b", 7, 50, cache_read=2, cache_creation=9),
        _claude_line("msg_b", "req_b", 7, 120, cache_read=3, cache_creation=9),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    assert result["status"] == "ok"
    day = next(iter(result["days"].values()))
    assert day["out"] == 852 + 120
    assert day["in"] == 10 + 7
    assert day["cache_r"] == 5 + 3
    assert day["cache_w"] == 120 + 9

    # Document the two wrong readings this pins against:
    first_wins_out = 100 + 50        # the old defect: earliest partial snapshot
    naive_sum_out = 100 + 400 + 852 + 50 + 120  # summing cumulative snapshots
    assert day["out"] != first_wins_out
    assert day["out"] < naive_sum_out


def test_collect_claude_replayed_record_not_double_counted(tmp_path):
    """A replayed/duplicated line (same group, identical snapshot written
    twice) must be counted ONCE — last-wins makes the replay idempotent."""
    replay = _claude_line("msg_r", "req_r", 11, 852, cache_read=5, cache_creation=120)
    lines = [replay, replay]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 852
    assert day["in"] == 11


def test_collect_claude_distinct_request_ids_both_counted(tmp_path):
    """Same message.id under two different requestIds are two different
    response groups: both must contribute (the group key is the pair)."""
    lines = [
        _claude_line("msg_x", "req_1", 10, 200),
        _claude_line("msg_x", "req_2", 30, 300),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 500
    assert day["in"] == 40


def test_collect_claude_missing_counter_is_unknown_not_zero(tmp_path):
    """A record that omits a counter must surface 'unknown' for it — 0 and
    'not reported' are different facts. Counters that ARE reported stay
    numeric, and one unknown contribution makes the day total unknown."""
    lines = [
        _claude_line("msg_m", "req_m", None, 852, cache_read=5, cache_creation=120),
        _claude_line("msg_k", "req_k", 11, 100, cache_read=2, cache_creation=9),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["in"] == "unknown"  # one group never reported it
    assert day["out"] == 952
    assert day["cache_r"] == 7
    assert day["cache_w"] == 129
    assert result["models"]["claude-test-model"] == 952


def test_collect_claude_missing_output_does_not_zero_models(tmp_path):
    """If the final snapshot of a group omits output_tokens, the model
    breakdown must say 'unknown' rather than silently reporting 0."""
    lines = [_claude_line("msg_n", "req_n", 10, None)]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == "unknown"
    assert day["in"] == 10
    assert result["models"]["claude-test-model"] == "unknown"


def test_collect_claude_out_of_order_records_resolved_by_timestamp(tmp_path):
    """Round-1 blocker: last-wins must follow the record's TIMESTAMP, not
    file order — replays, merged logs and concurrent writers can deliver an
    older snapshot AFTER a newer one. Here the file lists the FINAL
    snapshot (10:02) first and the earlier partial one (10:00) last: a
    file-order last-wins would keep 100 output tokens, the timestamp-
    ordered answer is 852. The 10:02 record omits input_tokens, so 'in'
    must come from its latest report (the 10:00 record) — per-counter
    merge."""
    lines = [
        _claude_line("msg_a", "req_a", None, 852, cache_read=None, cache_creation=None,
                     ts="2026-08-19T10:02:00.000Z"),
        _claude_line("msg_a", "req_a", 10, 100, cache_read=None, cache_creation=None,
                     ts="2026-08-19T10:00:00.000Z"),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 852
    assert day["in"] == 10
    file_order_out = 100  # what the round-1 file-order last-wins would report
    assert day["out"] != file_order_out


def test_collect_claude_equal_timestamps_later_record_wins(tmp_path):
    """The documented tie-break: two records of one group with EQUAL
    timestamps resolve to the one encountered LATER in the scan — a
    same-timestamp streaming rewrite is the more advanced snapshot. Pinned
    so the rule stays explicit (collect_claude docstring), never implicit
    in dict-overwrite behavior."""
    lines = [
        _claude_line("msg_t", "req_t", 10, 400, ts="2026-08-19T10:00:00.000Z"),
        _claude_line("msg_t", "req_t", 10, 852, ts="2026-08-19T10:00:00.000Z"),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 852


def test_collect_claude_partial_update_preserves_earlier_counters(tmp_path):
    """Round-1 blocker 2: snapshot A reports input+output, the NEWER
    snapshot B reports only output — input must survive (per-counter
    merge), and a counter NO snapshot of the group ever reported stays
    'unknown' (never 'missing from the last one')."""
    lines = [
        _claude_line("msg_p", "req_p", 10, 100, cache_read=None, cache_creation=20,
                     ts="2026-08-19T10:00:00.000Z"),
        _claude_line("msg_p", "req_p", None, 852, cache_read=None, cache_creation=None,
                     ts="2026-08-19T10:02:00.000Z"),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["in"] == 10              # survives from snapshot A
    assert day["out"] == 852            # from the newer snapshot B
    assert day["cache_w"] == 20         # survives from snapshot A
    assert day["cache_r"] == "unknown"  # never reported by any snapshot
    assert result["models"]["claude-test-model"] == 852


# ------------------------------------------- incomplete identity (round-2 blocker)
#
# The dedup key (message.id, requestId) answers "are these the same
# record?" — and a tuple with a hole cannot answer yes. The old code
# treated PARTIAL identity as full identity: (None, "req-1") seen twice
# collapsed into one group even when the two records were genuinely
# independent (W1's exactly-once defect shape: a key that silently merges
# what it should distinguish). Explicit policy, pinned here and stated in
# collect_claude's code comment: BOTH ids present → dedupe on the pair;
# EITHER id missing → never merge on the strength of the half present;
# BOTH missing → the anonymous path (each record its own group).


def test_collect_claude_shared_request_id_without_message_id_not_merged(tmp_path):
    """Regression 1: two records sharing a requestId but BOTH missing
    message.id are not provably the same record — they must NOT collapse
    into one group on the strength of the shared requestId."""
    lines = [
        _claude_line(None, "req_shared", 10, 100),
        _claude_line(None, "req_shared", 20, 200),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 300  # not 200 (buggy partial-identity merge, last-wins)
    assert day["in"] == 30
    assert result["models"]["claude-test-model"] == 300


def test_collect_claude_shared_message_id_without_request_id_not_merged(tmp_path):
    """Regression 2: symmetric case — two records sharing a message.id but
    BOTH missing requestId must NOT collapse either."""
    lines = [
        _claude_line("msg_shared", None, 10, 100),
        _claude_line("msg_shared", None, 20, 200),
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 300
    assert day["in"] == 30


def test_collect_claude_fully_anonymous_records_still_never_collapse(tmp_path):
    """Regression 3: both ids missing on several records → the pre-existing
    anonymous behaviour holds: each record is its own group, nothing
    collapses, every record counts once. Includes one line with the id
    keys ABSENT ENTIRELY (not just null) — the truly keyless shape."""
    keyless = json.dumps({
        "type": "assistant",
        "timestamp": "2026-08-19T10:00:00.000Z",
        "message": {"model": "claude-test-model",
                    "usage": {"input_tokens": 5, "output_tokens": 50}},
    })
    lines = [
        _claude_line(None, None, 10, 100),
        _claude_line(None, None, 20, 200),
        keyless,
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 350
    assert day["in"] == 35


def test_collect_claude_full_identity_still_dedupes(tmp_path):
    """Positive control: two records that genuinely ARE the same response
    group (BOTH ids present and equal) must still dedupe, last-wins. A fix
    that simply stopped merging everything would pass regressions 1-3 and
    be wrong — this is the check that catches it."""
    lines = [
        _claude_line("msg_same", "req_same", 10, 100),
        _claude_line("msg_same", "req_same", 10, 852),  # same ts: later wins
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 852  # not 952 (never summed), not 100 (never first-wins)
    assert day["in"] == 10


def test_collect_claude_partial_identity_does_not_merge_into_full_group(tmp_path):
    """Boundary case: a record missing one id must not merge INTO a
    full-identity group that shares the other half — the shared half is
    not proof of sameness in either direction."""
    lines = [
        _claude_line("msg_a", "req_a", 10, 100),  # full-identity group
        _claude_line(None, "req_a", 20, 200),      # shares requestId only
        _claude_line("msg_a", None, 30, 300),      # shares message.id only
    ]
    _write_transcript(tmp_path, "transcript.jsonl", lines)

    result = suc.collect_claude(str(tmp_path), SINCE)
    day = next(iter(result["days"].values()))
    assert day["out"] == 600  # three distinct groups
    assert day["in"] == 60


def test_fmt_metrics_survives_unknown_counters():
    """A day carrying 'unknown' must format as 'unknown', never crash the
    {:,} formatter, and the 7-day total must not silently degrade to a
    partial sum."""
    days = {
        "19/08": {"in": 100, "out": "unknown", "cache_r": 5, "cache_w": 9},
        "20/08": {"in": 50, "out": 200, "cache_r": 1, "cache_w": 2},
    }
    text = suc.fmt_metrics(days)
    assert "unknown" in text
    # 7g out total must be unknown (one contribution is unknown), not 200
    assert "7g out: unknown tok" in text


# ------------------------------------------- provenance (matrix collector-provenance/2)
#
# Rows covered here: P1/C1 (label in the Claude metrics string AND the JSON
# payload), P2 (no billing/cost/quota vocabulary in the emitted surface,
# asserted BY NAME below), P3/C2 (existing keys in/out/cache_r/cache_w keep
# name, type and status semantics — provenance is additive), P4 ('unknown'
# stays distinct from 0 at the emitted boundary), P5 (the label names WHICH
# surface produced the figure), C3 (Codex/agy/Kimi/TP1 strings
# byte-unchanged, no provenance stamp on them).
#
# P2's named list. "crediti" is deliberately NOT in it: TP1's pre-existing
# static note ("crediti Token Plan: endpoint da individuare in PROBE-1") is
# protected byte-unchanged by row C3 and claims no remaining allowance — it
# is a probe TODO, not a figure. Test function names in this section avoid
# every banned substring on purpose: tmp_path embeds the test name and the
# snapshot carries tmp_path inside seat "source" fields.
BANNED_SURFACE_VOCABULARY = [
    "billing", "fattur", "cost", "costo", "spend", "spesa", "price",
    "prezzo", "quota", "allowance", "remaining", "saldo", "usd", "eur",
    "$", "€",
]


def test_fmt_metrics_default_rendering_byte_unchanged():
    """C3, unit level: the Codex path calls fmt_metrics WITHOUT provenance;
    its rendering must stay byte-identical to the pre-provenance format."""
    today = suc.NOW.strftime("%d/%m")
    days = {today: {"in": 17, "out": 952, "cache_r": 5, "cache_w": 120}}
    assert suc.fmt_metrics(days) == (
        "oggi: 17in/952out · 7g out: 952 tok · cache r/w oggi: 5/120"
    )


def test_fmt_metrics_claude_provenance_label():
    """P1/C1/P5, unit level: the Claude rendering carries the provenance
    label IN the string a dashboard reader copies, the label names which
    surface produced the figure, and the label itself is vocabulary-clean."""
    today = suc.NOW.strftime("%d/%m")
    days = {today: {"in": 17, "out": 952, "cache_r": 5, "cache_w": 120}}
    text = suc.fmt_metrics(days, provenance=suc.CLAUDE_LOCAL_JSONL_PROVENANCE)
    assert text.endswith(" · " + suc.CLAUDE_LOCAL_JSONL_PROVENANCE)
    assert "JSONL locali" in text           # names the surface (P5)
    assert "osservato/provvisorio" in text  # observed/provisional (P1)
    for word in BANNED_SURFACE_VOCABULARY:
        assert word not in text.lower()


def test_emitted_snapshot_provenance_end_to_end(tmp_path, monkeypatch):
    """Boundary round for the whole matrix: run main() against synthetic
    fixtures (HOME redirected to tmp_path so the agy/Kimi/api-mirror seats
    resolve to 'absent' deterministically) and assert every row on the REAL
    emitted snapshot, not on internals."""
    claude_prof = tmp_path / "claude-prof"
    _write_transcript(claude_prof, "t.jsonl", [
        # today (WITA): one complete group + one group that never reports
        # output_tokens -> day 'out' must be 'unknown'
        _claude_line("msg_a", "req_a", 10, 852, cache_read=5, cache_creation=120,
                     ts="2026-08-20T10:00:00.000Z"),
        _claude_line("msg_b", "req_b", 7, None,
                     ts="2026-08-20T10:01:00.000Z"),
        # yesterday: a group that genuinely reports ZERO — 0 is a fact and
        # must stay distinct from 'unknown' (P4)
        _claude_line("msg_z", "req_z", 0, 0,
                     ts="2026-08-19T10:00:00.000Z"),
    ])
    codex_home = tmp_path / "codex-home"
    _write_session(codex_home, "rollout.jsonl", [
        _token_count_line(total_in=1000, total_out=40, last_in=1000, last_out=40),
    ])
    seat_map = tmp_path / "seat_map.json"
    seat_map.write_text(json.dumps({
        "claude_profiles": {str(claude_prof): "A1"},
        "codex_homes": {str(codex_home): "O1"},
    }))
    out_json = tmp_path / "snapshot.json"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(suc, "NOW", datetime(2026, 8, 20, 12, 0, tzinfo=suc.WITA))
    monkeypatch.setattr(sys, "argv", [
        "seat_usage_collector.py", "--seat-map", str(seat_map), "--out", str(out_json),
    ])

    assert suc.main() == 0
    snap = json.loads(out_json.read_text())
    seats = {s["id"]: s for s in snap["seats"]}
    claude, codex = seats["A1"], seats["O1"]

    # P3/C2 — old keys, old types, old status semantics; provenance additive
    assert claude["status"] == "ok" and codex["status"] == "ok"
    day_today = claude["days"]["20/08"]
    assert set(day_today) == {"in", "out", "cache_r", "cache_w"}
    assert isinstance(day_today["in"], int)
    assert isinstance(claude["days"]["19/08"]["out"], int)

    # P4 — 'unknown' stays distinct from 0 in the EMITTED surface
    assert day_today["out"] == "unknown"
    assert claude["days"]["19/08"]["out"] == 0
    assert "oggi: 17in/unknownout" in claude["metrics"]
    assert "7g out: unknown tok" in claude["metrics"]

    # P1/C1 — provenance in the human string AND in the JSON payload
    assert suc.CLAUDE_LOCAL_JSONL_PROVENANCE in claude["metrics"]
    prov = claude["provenance"]
    assert prov["surface"] == "claude_code_local_jsonl_transcripts"  # P5
    assert "observed/provisional" in prov["reading"]

    # C3 — every other seat byte-unchanged, no provenance stamp anywhere
    assert codex["metrics"] == "oggi: 0in/0out · 7g out: 40 tok · cache r/w oggi: 0/0"
    assert "provenance" not in codex
    for seat_id in ("G1", "K1", "TP1"):
        assert "provenance" not in seats[seat_id]
        assert suc.CLAUDE_LOCAL_JSONL_PROVENANCE not in json.dumps(seats[seat_id])

    # P2 — no billing/cost/quota vocabulary ANYWHERE in the emitted surface
    surface = json.dumps(snap, ensure_ascii=False).lower()
    for word in BANNED_SURFACE_VOCABULARY:
        assert word not in surface, f"banned vocabulary leaked into emitted surface: {word!r}"
