"""Tests for scripts/zero_population_monitor.py — the generalized "kill switch
off + table never written" probe (megatopics-1-5 action plan #1, 2026-08-03).

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools — matching the
existing test_pending_arms_report.py convention. Every test here injects a
fake query_fn (or monkeypatches the module-level default) — none of them
touch a real database.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess as real_subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "zero_population_monitor.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("zero_population_monitor", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


zpm = _load_module()

ENTRY = {
    "name": "e33_guarantee_scan",
    "switch_key": "e33_guarantee_scan_enabled",
    "table": "e33_cases",
}


def _outcome(ok: bool, rows=None, detail: str = ""):
    return zpm.QueryOutcome(ok=ok, rows=rows or [], detail=detail)


# ---------------------------------------------------------------------------
# Registry seed — the one real, verified finding (VCR §1, 2026-08-03)
# ---------------------------------------------------------------------------


def test_default_registry_has_exactly_one_e33_entry():
    assert zpm.DEFAULT_REGISTRY == [ENTRY]


# ---------------------------------------------------------------------------
# Guilt: unprovisioned + zero rows — the live E33 shape
# ---------------------------------------------------------------------------


def test_guilt_unprovisioned_and_empty_table_alerts():
    calls = []

    def fake_query(sql: str):
        calls.append(sql)
        if "system_settings" in sql:
            return _outcome(True, rows=[])  # no row at all -> unprovisioned
        return _outcome(True, rows=[["0"]])  # zero rows

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is True
    assert result["provisioned"] is False
    assert result["table_empty"] is True
    assert result["alert"] is True
    assert "UNPROVISIONED_AND_EMPTY" in result["reason"]
    assert len(calls) == 2


def test_guilt_falsy_switch_value_counts_as_unprovisioned():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["false"]])
        return _outcome(True, rows=[["0"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["provisioned"] is False
    assert result["alert"] is True
    assert "UNPROVISIONED_AND_EMPTY" in result["reason"]


# ---------------------------------------------------------------------------
# Guilt: provisioned but STILL empty — documented widening decision (see
# module docstring's ALERT RULE). This is the deliberate design choice the
# task asked to be made explicit: a provisioned-but-never-written organ is
# ALSO flagged, not silently passed as "half the conditions held".
# ---------------------------------------------------------------------------


def test_guilt_provisioned_but_empty_table_also_alerts_documented_decision():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["0"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is True
    assert result["provisioned"] is True
    assert result["table_empty"] is True
    assert result["alert"] is True  # documented widening: also alert here
    assert "PROVISIONED_BUT_EMPTY" in result["reason"]


# ---------------------------------------------------------------------------
# Innocence: populated table never alerts, regardless of provisioning
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("switch_rows", [[], [["false"]], [["true"]]])
def test_innocence_populated_table_no_alert_regardless_of_provisioning(switch_rows):
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=switch_rows)
        return _outcome(True, rows=[["42"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is True
    assert result["table_empty"] is False
    assert result["alert"] is False
    assert "healthy" in result["reason"]


def test_innocence_provisioned_and_populated_is_the_healthy_baseline():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["7"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["provisioned"] is True
    assert result["table_empty"] is False
    assert result["alert"] is False


# ---------------------------------------------------------------------------
# "Cannot verify" must never be silently "clean" (W84)
# ---------------------------------------------------------------------------


def test_guilt_switch_query_failure_reports_cannot_verify_not_clean():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(False, detail="connection refused")
        return _outcome(True, rows=[["0"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is False
    assert result["alert"] is False
    assert result["provisioned"] is None
    assert "connection refused" in result["detail"]


def test_guilt_table_query_failure_reports_cannot_verify_not_clean():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(False, detail="timeout")

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is False
    assert result["alert"] is False
    assert result["provisioned"] is True  # the switch check DID succeed
    assert "timeout" in result["detail"]


def test_guilt_unparseable_row_count_reports_cannot_verify():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["not-a-number"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is False
    assert result["alert"] is False


def test_guilt_empty_count_rows_reports_cannot_verify():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[])  # count(*) always returns one row; empty is a parse defect

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is False
    assert result["alert"] is False


# ---------------------------------------------------------------------------
# SQL-construction safety: unsafe identifiers/keys are refused, never queried
# ---------------------------------------------------------------------------


def test_guilt_unsafe_table_identifier_refused_without_querying():
    calls = []

    def fake_query(sql: str):
        calls.append(sql)
        return _outcome(True, rows=[["true"]])

    bad_entry = {"name": "x", "switch_key": "x_enabled", "table": "e33_cases; DROP TABLE users;"}
    result = zpm.check_entry(bad_entry, query_fn=fake_query)
    assert result["checked"] is False
    assert calls == []  # never even attempted a query


def test_guilt_unsafe_switch_key_refused_without_querying():
    calls = []

    def fake_query(sql: str):
        calls.append(sql)
        return _outcome(True, rows=[["true"]])

    bad_entry = {"name": "x", "switch_key": "x' OR '1'='1", "table": "e33_cases"}
    result = zpm.check_entry(bad_entry, query_fn=fake_query)
    assert result["checked"] is False
    assert calls == []


def test_innocence_real_registry_entry_identifiers_are_accepted():
    # Sanity check that the safety regexes aren't so strict they reject the
    # actual seeded entry.
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["5"]])

    result = zpm.check_entry(ENTRY, query_fn=fake_query)
    assert result["checked"] is True


# ---------------------------------------------------------------------------
# SQL shape: switch_key is quote-escaped; table name interpolated as-is (safe
# only because it was validated as a plain identifier above)
# ---------------------------------------------------------------------------


def test_switch_sql_quotes_the_key_literal():
    seen_sql = {}

    def fake_query(sql: str):
        if "system_settings" in sql:
            seen_sql["switch"] = sql
            return _outcome(True, rows=[["true"]])
        seen_sql["count"] = sql
        return _outcome(True, rows=[["1"]])

    zpm.check_entry(ENTRY, query_fn=fake_query)
    assert "'e33_guarantee_scan_enabled'" in seen_sql["switch"]
    assert "FROM e33_cases" in seen_sql["count"]


def test_sql_quote_literal_escapes_single_quotes():
    assert zpm._sql_quote_literal("a'b") == "'a''b'"


# ---------------------------------------------------------------------------
# run() over a registry list
# ---------------------------------------------------------------------------


def test_run_over_registry_returns_one_result_per_entry():
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["3"]])

    results = zpm.run([ENTRY, ENTRY], query_fn=fake_query)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# main(): exit codes + precedence (cannot-verify beats alert beats clean)
# ---------------------------------------------------------------------------


def test_main_exit_0_when_clean(monkeypatch, capsys):
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["9"]])

    monkeypatch.setattr(zpm, "_default_query_fn", fake_query)
    assert zpm.main([]) == 0
    out = capsys.readouterr().out
    assert "alert=False" in out


def test_main_exit_1_when_any_entry_alerts(monkeypatch, capsys):
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[])
        return _outcome(True, rows=[["0"]])

    monkeypatch.setattr(zpm, "_default_query_fn", fake_query)
    assert zpm.main([]) == 1
    out = capsys.readouterr().out
    assert "alert=True" in out


def test_main_exit_2_when_any_entry_cannot_be_checked(monkeypatch, capsys):
    def fake_query(sql: str):
        return _outcome(False, detail="db down")

    monkeypatch.setattr(zpm, "_default_query_fn", fake_query)
    assert zpm.main([]) == 2


def test_main_exit_2_takes_precedence_over_exit_1(monkeypatch):
    # Two registry entries: one alerts (unprovisioned+empty), one cannot be
    # checked at all — "cannot verify" must win, never masked by an alert
    # found elsewhere in the same run.
    call_count = {"n": 0}

    def fake_query(sql: str):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            if "system_settings" in sql:
                return _outcome(True, rows=[])
            return _outcome(True, rows=[["0"]])
        return _outcome(False, detail="connection refused")

    second_entry = {"name": "other", "switch_key": "other_enabled", "table": "other_table"}
    monkeypatch.setattr(zpm, "_default_query_fn", fake_query)
    monkeypatch.setattr(zpm, "DEFAULT_REGISTRY", [ENTRY, second_entry])
    assert zpm.main([]) == 2


def test_main_json_output_is_valid_json_and_names_the_entry(monkeypatch, capsys):
    def fake_query(sql: str):
        if "system_settings" in sql:
            return _outcome(True, rows=[["true"]])
        return _outcome(True, rows=[["1"]])

    monkeypatch.setattr(zpm, "_default_query_fn", fake_query)
    assert zpm.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["name"] == "e33_guarantee_scan"
    assert payload[0]["alert"] is False


# ---------------------------------------------------------------------------
# _default_query_fn: the real gh-of-postgres plumbing degrades safely
# ---------------------------------------------------------------------------


def test_default_query_fn_missing_pg_sh_reports_ok_false(tmp_path, monkeypatch):
    # Point __file__ at a directory with no pg.sh so the real subprocess call
    # exercises the FileNotFoundError branch — no real Fly proxy/Postgres
    # touched.
    monkeypatch.setattr(zpm, "__file__", str(tmp_path / "zero_population_monitor.py"))
    outcome = zpm._default_query_fn("SELECT 1;")
    assert outcome.ok is False
    assert "not found" in outcome.detail


def test_default_query_fn_non_zero_exit_reports_ok_false(monkeypatch):
    def fake_run(cmd, **kwargs):
        class _FakeProc:
            returncode = 1
            stdout = ""
            stderr = "psql: error: connection refused\n"

        return _FakeProc()

    monkeypatch.setattr(zpm.subprocess, "run", fake_run)
    outcome = zpm._default_query_fn("SELECT 1;")
    assert outcome.ok is False
    assert "connection refused" in outcome.detail


def test_default_query_fn_parses_pipe_delimited_rows(monkeypatch):
    def fake_run(cmd, **kwargs):
        class _FakeProc:
            returncode = 0
            stdout = "a|b\nc|d\n"
            stderr = ""

        return _FakeProc()

    monkeypatch.setattr(zpm.subprocess, "run", fake_run)
    outcome = zpm._default_query_fn("SELECT 1;")
    assert outcome.ok is True
    assert outcome.rows == [["a", "b"], ["c", "d"]]


def test_default_query_fn_timeout_reports_ok_false(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr(zpm.subprocess, "run", fake_run)
    outcome = zpm._default_query_fn("SELECT 1;")
    assert outcome.ok is False
