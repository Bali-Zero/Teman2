"""mos-plus-compression-worker.py — the cascade fix (2026-08-13).

Three defects, one commit chain (see the promotion commit + this fix commit):
  1. HOME-fork (fixed by promotion, not tested here — that's lint_home_fork's job)
  2. OLLAMA_URL hardcoded to localhost, Pro's Ollama contended into 180s+ timeouts
  3. `failed += obs_count; continue` on a failed tier call — no retry cap, no
     alert, the same sid retried every 10min tick forever (measured:
     raw_observations backlog 5,022 -> 7,162 in one day)

This file tests (3) directly (retry cap + consecutive-fail alert) and the
degrade-without-losing-the-row contract that (2)'s fix depends on. It does
NOT re-test tg_notify.py itself (that gateway has its own suite) — only that
this worker calls it correctly (absolute interpreter, never raises, fires
exactly at the threshold).

Same import shape as test_wa_attention_episode_tier.py (W96 class): the
module does real work at import (os.path.expanduser("~/.claude/...") is
evaluated at module load), so HOME is redirected to a throwaway tmp_path
BEFORE import and the module is loaded by path (hyphenated filename, not a
valid Python identifier).
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "scripts" / "mos-plus-compression-worker.py"


@pytest.fixture()
def worker(tmp_path, monkeypatch):
    """Import the hyphenated script by path, in a throwaway HOME (W96)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("MOS_PLUS_OLLAMA_URL", raising=False)

    spec = importlib.util.spec_from_file_location("mos_plus_compression_worker", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mos_plus_compression_worker"] = mod
    spec.loader.exec_module(mod)
    try:
        assert Path(mod.DB_PATH).is_relative_to(home), (
            f"the import escaped the throwaway HOME: {mod.DB_PATH}"
        )
        yield mod
    finally:
        sys.modules.pop("mos_plus_compression_worker", None)


def _make_db(mod, rows: list[dict]) -> None:
    """Fresh raw_observations/memories schema (no retry_count — that column
    is added by main()'s own idempotent ALTER TABLE, so most tests exercise
    that path rather than assuming the column pre-exists)."""
    Path(mod.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(mod.DB_PATH)
    conn.execute("""
        CREATE TABLE raw_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            source TEXT,
            tool_name TEXT,
            payload_json TEXT,
            captured_at TEXT,
            osint_sensitive INTEGER DEFAULT 0,
            discarded_at TEXT,
            discard_reason TEXT,
            compressed_to_memory_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            type TEXT,
            content TEXT,
            importance INTEGER,
            tags TEXT
        )
    """)
    for row in rows:
        conn.execute(
            "INSERT INTO raw_observations "
            "(session_id, source, tool_name, payload_json, captured_at, osint_sensitive) "
            "VALUES (?, ?, ?, ?, datetime('now'), ?)",
            (
                row.get("session_id", "s1"),
                row.get("source", "pre_tool_use"),
                row.get("tool_name", "Bash"),
                row.get("payload_json", "ls -la"),
                row.get("osint_sensitive", 1),
            ),
        )
    conn.commit()
    conn.close()


def _fetch_row(mod, session_id: str = "s1") -> sqlite3.Row:
    conn = sqlite3.connect(mod.DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM raw_observations WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return row


def _run_main_expect_exit(mod, code: int = 0) -> None:
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == code


# ---------------------------------------------------------------------------
# Defect 2: configurable endpoint, default Mini
# ---------------------------------------------------------------------------


def test_ollama_url_defaults_to_mini_tailscale_ip(worker):
    assert worker.OLLAMA_HOST == "http://100.93.236.6:11434"
    assert worker.OLLAMA_URL == "http://100.93.236.6:11434/api/generate"


def test_ollama_url_is_overridable_via_dedicated_env_var(tmp_path, monkeypatch):
    home = tmp_path / "home2"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("MOS_PLUS_OLLAMA_URL", "http://127.0.0.1:9999")
    spec = importlib.util.spec_from_file_location("mos_plus_compression_worker_ov", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mos_plus_compression_worker_ov"] = mod
    try:
        spec.loader.exec_module(mod)
        assert mod.OLLAMA_URL == "http://127.0.0.1:9999/api/generate"
    finally:
        sys.modules.pop("mos_plus_compression_worker_ov", None)


# ---------------------------------------------------------------------------
# Defect 3a: retry cap — guilt (fires AT the cap) + innocence (survives BELOW it)
# ---------------------------------------------------------------------------


def test_row_below_retry_cap_is_not_discarded_and_not_lost(worker, monkeypatch):
    """Innocence: N-1 failed ticks must not touch discarded_at/compressed_to_memory_id."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: None)
    _make_db(worker, [{"session_id": "s1"}])

    for _ in range(worker.MAX_ROW_RETRIES - 1):
        _run_main_expect_exit(worker, 0)

    row = _fetch_row(worker)
    assert row["discarded_at"] is None
    assert row["compressed_to_memory_id"] is None
    assert row["retry_count"] == worker.MAX_ROW_RETRIES - 1


def test_row_at_retry_cap_is_discarded(worker, monkeypatch):
    """Guilt: the Nth failed tick must discard the row with the named reason."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: None)
    _make_db(worker, [{"session_id": "s1"}])

    for _ in range(worker.MAX_ROW_RETRIES):
        _run_main_expect_exit(worker, 0)

    row = _fetch_row(worker)
    assert row["discarded_at"] is not None
    assert row["discard_reason"] == "max_retries_exceeded"
    assert row["retry_count"] == worker.MAX_ROW_RETRIES


def test_unreachable_endpoint_degrades_the_tick_without_losing_the_row(worker, monkeypatch):
    """The specific claim from the mandate: an unreachable endpoint fails
    THAT tick cleanly (exit 0, no crash) and the row stays in the pending
    pool for the next tick — it is not silently dropped."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: None)
    _make_db(worker, [{"session_id": "s1"}])

    _run_main_expect_exit(worker, 0)

    row = _fetch_row(worker)
    assert row["discarded_at"] is None
    assert row["compressed_to_memory_id"] is None


def test_alter_table_retry_count_is_idempotent_across_runs(worker, monkeypatch):
    """The schema migration must not blow up on the second (and Nth) run,
    when the column it adds already exists."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: None)
    _make_db(worker, [{"session_id": "s1"}])

    _run_main_expect_exit(worker, 0)
    _run_main_expect_exit(worker, 0)  # retry_count already exists this time

    row = _fetch_row(worker)
    assert row["retry_count"] == 2


def test_discard_rows_over_retry_cap_pure_sql_boundary(worker):
    """Direct unit test of the cap SQL, independent of main()'s loop: a row
    exactly AT the cap is discarded, a row one BELOW it survives untouched."""
    _make_db(worker, [{"session_id": "below"}, {"session_id": "at"}])
    conn = sqlite3.connect(worker.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("ALTER TABLE raw_observations ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    ids = {
        r["session_id"]: r["id"]
        for r in conn.execute("SELECT id, session_id FROM raw_observations").fetchall()
    }
    conn.execute(
        "UPDATE raw_observations SET retry_count=? WHERE id=?",
        (worker.MAX_ROW_RETRIES - 1, ids["below"]),
    )
    conn.execute(
        "UPDATE raw_observations SET retry_count=? WHERE id=?",
        (worker.MAX_ROW_RETRIES, ids["at"]),
    )
    conn.commit()

    n = worker._discard_rows_over_retry_cap(conn, [ids["below"], ids["at"]])
    assert n == 1

    rows = {
        r["session_id"]: r
        for r in conn.execute("SELECT * FROM raw_observations").fetchall()
    }
    assert rows["below"]["discarded_at"] is None
    assert rows["at"]["discarded_at"] is not None
    assert rows["at"]["discard_reason"] == "max_retries_exceeded"
    conn.close()


def test_discard_rows_over_retry_cap_empty_ids_is_a_noop(worker):
    _make_db(worker, [])
    conn = sqlite3.connect(worker.DB_PATH)
    conn.execute("ALTER TABLE raw_observations ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    assert worker._discard_rows_over_retry_cap(conn, []) == 0
    conn.close()


def test_parse_fail_branch_also_counts_toward_the_retry_cap(worker, monkeypatch):
    """The cap must apply to BOTH failure branches (unreachable/timeout AND a
    tier that answered with unparseable output) — not just the network one."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: "not json at all")
    _make_db(worker, [{"session_id": "s1"}])

    for _ in range(worker.MAX_ROW_RETRIES):
        _run_main_expect_exit(worker, 0)

    row = _fetch_row(worker)
    assert row["discarded_at"] is not None
    assert row["discard_reason"] == "max_retries_exceeded"


# ---------------------------------------------------------------------------
# Defect 3b: consecutive-fail alert — pure functions + wiring
# ---------------------------------------------------------------------------


def test_next_ollama_health_state_success_resets_failure_extends(worker):
    assert worker._next_ollama_health_state({"consecutive_fails": 0}, True) == {"consecutive_fails": 0}
    assert worker._next_ollama_health_state({"consecutive_fails": 4}, True) == {"consecutive_fails": 0}
    assert worker._next_ollama_health_state({"consecutive_fails": 2}, False) == {"consecutive_fails": 3}
    assert worker._next_ollama_health_state({}, False) == {"consecutive_fails": 1}


def test_should_alert_ollama_down_boundary(worker):
    """Guilt (AT threshold, and above) + innocence (BELOW threshold), same test."""
    threshold = worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS
    assert worker._should_alert_ollama_down(threshold - 1) is False
    assert worker._should_alert_ollama_down(threshold) is True
    assert worker._should_alert_ollama_down(threshold + 1) is True


def test_record_ollama_health_pages_exactly_at_threshold_not_below(worker, monkeypatch):
    pages: list[int] = []
    monkeypatch.setattr(worker, "_send_ollama_down_alert", lambda n: pages.append(n))

    for _ in range(worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS - 1):
        worker._record_ollama_health(False)
    assert pages == []  # innocence: still below threshold

    worker._record_ollama_health(False)
    assert pages == [worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS]  # guilt: crosses now


def test_record_ollama_health_success_resets_the_streak(worker, monkeypatch):
    pages: list[int] = []
    monkeypatch.setattr(worker, "_send_ollama_down_alert", lambda n: pages.append(n))

    for _ in range(worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS):
        worker._record_ollama_health(False)
    assert len(pages) == 1

    worker._record_ollama_health(True)  # a single success clears the streak
    for _ in range(worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS - 1):
        worker._record_ollama_health(False)
    assert len(pages) == 1  # still just the one page — the new streak hasn't crossed yet


def test_call_tier_routes_every_ollama_attempt_through_health_tracking(worker, monkeypatch):
    """Both the direct choice AND the ollama_fallback retry path must hit the
    same health hook — this is the wiring, not just the pure predicate."""
    monkeypatch.setattr(worker, "call_ollama", lambda prompt: None)
    seen: list[bool] = []
    monkeypatch.setattr(worker, "_record_ollama_health", lambda success: seen.append(success))

    worker.call_tier("ollama_local", "prompt")
    worker.call_tier("ollama_fallback", "prompt")
    worker.call_tier("claude_haiku", "prompt")  # non-ollama tier: must NOT touch health tracking

    assert seen == [False, False]


def test_send_ollama_down_alert_uses_absolute_interpreter_and_never_raises(worker, monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        raise RuntimeError("subprocess exploded")

    monkeypatch.setattr(worker.subprocess, "run", fake_run)

    worker._send_ollama_down_alert(worker.OLLAMA_ALERT_AFTER_CONSECUTIVE_FAILS)  # must not raise

    assert captured["argv"][0] == sys.executable, (
        "must use the interpreter this process is actually running under, "
        "never a bare 'python3' re-resolved via PATH (cicatrix W108)"
    )
    assert "--dedup-key" in captured["argv"]
    assert "mos-plus-ollama-tier-down" in captured["argv"]
    assert "--tier" in captured["argv"] and "p0" in captured["argv"]


def test_send_ollama_down_alert_logs_the_gateway_outcome(worker, monkeypatch):
    class FakeResult:
        returncode = 0
        stderr = "tg_notify: sent\n"
        stdout = ""

    monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: FakeResult())
    worker._send_ollama_down_alert(3)

    log_text = Path(worker.ERR_LOG).read_text()
    assert "rc=0" in log_text
    assert "outcome=sent" in log_text
