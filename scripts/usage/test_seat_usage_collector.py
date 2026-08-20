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
