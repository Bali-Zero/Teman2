"""Tests for scripts/portal_challenge_leaderboard.py — Portal Champion report.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package — same convention as test_pending_arms_report.py. Only pure helpers
are exercised here: value parsing and table rendering. Everything that shells
out to prod Postgres via scripts/pg.sh (`_run_sql`, `fetch_*`,
`fetch_round2_snapshot`) is out of scope for a unit test.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "portal_challenge_leaderboard.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("portal_challenge_leaderboard", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pcl = _load_module()


# ── value parsing ────────────────────────────────────────────────────────


def test_parse_ts_returns_none_for_missing_or_empty() -> None:
    assert pcl._parse_ts(None) is None
    assert pcl._parse_ts("") is None


def test_parse_ts_parses_a_real_iso_timestamp() -> None:
    parsed = pcl._parse_ts("2026-10-01T09:00:00+08:00")
    assert parsed == datetime(2026, 10, 1, 9, 0, tzinfo=parsed.tzinfo)


def test_parse_int_defaults_to_zero_for_missing_or_empty() -> None:
    assert pcl._parse_int(None) == 0
    assert pcl._parse_int("") == 0
    assert pcl._parse_int("7") == 7


def test_parse_optional_int_returns_none_for_missing_or_empty() -> None:
    assert pcl._parse_optional_int(None) is None
    assert pcl._parse_optional_int("") is None
    assert pcl._parse_optional_int("42") == 42


# ── table rendering ──────────────────────────────────────────────────────


def _r1_entry(**overrides) -> "pcl.AwardedEntry":
    defaults = dict(
        email="adit@balizero.com",
        member="adit",
        display_name="Adit",
        department="setup",
        is_tax=False,
        rank=1,
        activations=23,
        invited=23,
        last_activation_at=None,
        award_tier=1,
        prize_idr=3_000_000,
        tax_bonus_idr=0,
        total_prize_idr=3_000_000,
        next_tier_threshold=None,
        to_next_tier=None,
    )
    defaults.update(overrides)
    return pcl.AwardedEntry(**defaults)


def test_render_table_plain_includes_every_awarded_member() -> None:
    output = pcl.render_table([_r1_entry(), _r1_entry(member="surya", rank=2, award_tier=None)], markdown=False)
    assert "adit" in output
    assert "surya" in output


def test_render_table_markdown_uses_pipe_delimited_rows() -> None:
    output = pcl.render_table([_r1_entry()], markdown=True)
    assert output.splitlines()[0].startswith("| rank |")
    assert "| adit |" in output


def _r2_entry(**overrides) -> "pcl.r2.Round2Entry":
    defaults = dict(
        email="adit@balizero.com",
        member="adit",
        display_name="Adit",
        department="setup",
        is_tax=False,
        rank=1,
        points=26,
        carry_points=23,
        registrations=3,
        document_bonuses=0,
        unanswered_requests=0,
        unreviewed_documents=0,
        penalty_points=0,
        prize_idr=6_000_000,
        september_choice="carry",
    )
    defaults.update(overrides)
    return pcl.r2.Round2Entry(**defaults)


def test_render_round2_table_shows_the_breakdown_columns() -> None:
    output = pcl.render_round2_table([_r2_entry()], markdown=False)
    header, *_ = output.splitlines()
    for column in ("points", "carry", "reg", "docs", "unans", "unrev", "penalty", "choice"):
        assert column in header


def test_render_round2_table_shows_dash_for_no_september_choice() -> None:
    output = pcl.render_round2_table([_r2_entry(september_choice=None)], markdown=False)
    assert " - " in output or output.rstrip().endswith("-")


# ── round routing ────────────────────────────────────────────────────────


def test_main_defaults_to_whichever_round_is_active(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(pcl.r2, "active_round", lambda now: 2)
    monkeypatch.setattr(pcl, "_main_round1", lambda args, now: calls.append(1) or 0)
    monkeypatch.setattr(pcl, "_main_round2", lambda args, now: calls.append(2) or 0)

    assert pcl.main([]) == 0
    assert calls == [2]


def test_main_round_flag_overrides_the_active_round(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(pcl.r2, "active_round", lambda now: 2)
    monkeypatch.setattr(pcl, "_main_round1", lambda args, now: calls.append(1) or 0)
    monkeypatch.setattr(pcl, "_main_round2", lambda args, now: calls.append(2) or 0)

    assert pcl.main(["--round", "1"]) == 0
    assert calls == [1]


def test_main_passes_a_tz_aware_now_to_the_dispatched_round(monkeypatch) -> None:
    seen: dict[str, datetime] = {}

    def _capture(args, now):
        seen["now"] = now
        return 0

    monkeypatch.setattr(pcl.r2, "active_round", lambda now: 1)
    monkeypatch.setattr(pcl, "_main_round1", _capture)

    pcl.main([])
    assert seen["now"].tzinfo is not None


# ── SQL / column-list parity ─────────────────────────────────────────────
# `_run_sql` reads psql `-t -A` output BY POSITION, so every column list must
# name the main SELECT's output columns in order — a column added to the SQL
# without its list shifts every later field (e.g. `created_at` <- practice_id).


def _select_output_names(sql: str) -> list[str]:
    depth, i, start = 0, 0, None
    upper = sql.upper()
    while i < len(sql):
        ch = sql[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and start is None and re.match(r"SELECT\b", upper[i:]):
            start = i + len("SELECT")
        elif depth == 0 and start is not None and re.match(r"FROM\b", upper[i:]):
            break
        i += 1
    assert start is not None, "no top-level SELECT"
    parts, depth, cur = [], 0, ""
    for ch in sql[start:i]:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [re.search(r"(\w+)\s*$", part.strip()).group(1) for part in parts]


@pytest.mark.parametrize(
    ("builder", "columns"),
    [
        ("build_registration_aggregates_sql", "_AGGREGATES_COLUMNS"),
        ("build_first_documents_sql", "_FIRST_DOCUMENT_COLUMNS"),
        ("build_client_requests_sql", "_REQUEST_COLUMNS"),
        ("build_required_document_reviews_sql", "_REVIEW_COLUMNS"),
        ("build_asya_requests_sql", "_ASYA_REQUEST_COLUMNS"),
        ("build_asya_client_events_sql", "_ASYA_EVENT_COLUMNS"),
    ],
)
def test_round2_column_lists_match_the_select_order(builder: str, columns: str) -> None:
    sql = getattr(pcl.r2, builder)()
    assert _select_output_names(sql) == getattr(pcl, columns)
