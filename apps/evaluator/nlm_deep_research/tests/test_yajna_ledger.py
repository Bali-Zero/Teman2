"""Tests for yajna_ledger append-only audit module."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.yajna_ledger import (
    EVENT_CLAIM_CITED_IN_CHAT,
    EVENT_CLAIM_CORROBORATED,
    EVENT_CLAIM_OFFERED,
    EVENT_CLAIM_ORPHAN_30D,
    EVENT_CLAIM_PROMOTED_TO_SYNTH,
    ORPHAN_WINDOW_DAYS,
    _load_ledger,
    append_event,
    append_events_batch,
    compute_metrics,
    run_scan,
)


# ── append_event basics ──────────────────────────────────────────────────────


def test_append_event_writes_jsonl_line(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    ok = append_event(
        EVENT_CLAIM_OFFERED,
        nb="nb4",
        claim_id="NB4-001",
        metadata={"category": "FEE_CHANGE", "confidence": 0.78},
        ledger_file=ledger,
    )
    assert ok is True
    rows = _load_ledger(ledger)
    assert len(rows) == 1
    assert rows[0]["event"] == EVENT_CLAIM_OFFERED
    assert rows[0]["nb"] == "nb4"
    assert rows[0]["claim_id"] == "NB4-001"
    assert rows[0]["meta"] == {"category": "FEE_CHANGE", "confidence": 0.78}


def test_append_event_rejects_unknown_event_type(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    ok = append_event("BOGUS", nb="nb4", claim_id="X", ledger_file=ledger)
    assert ok is False
    assert not ledger.exists()


def test_append_event_rejects_empty_claim_id(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    assert append_event(EVENT_CLAIM_OFFERED, nb="nb4", claim_id="", ledger_file=ledger) is False
    assert append_event(EVENT_CLAIM_OFFERED, nb="", claim_id="X", ledger_file=ledger) is False


def test_append_event_kill_switch_honored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "yajna.jsonl"
    monkeypatch.setenv("YAJNA_LEDGER_DISABLED", "1")
    ok = append_event(EVENT_CLAIM_OFFERED, nb="nb4", claim_id="NB4-001", ledger_file=ledger)
    assert ok is False
    assert not ledger.exists()


def test_append_event_kill_switch_off_means_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = tmp_path / "yajna.jsonl"
    monkeypatch.setenv("YAJNA_LEDGER_DISABLED", "0")
    ok = append_event(EVENT_CLAIM_OFFERED, nb="nb4", claim_id="NB4-001", ledger_file=ledger)
    assert ok is True


# ── batch append ─────────────────────────────────────────────────────────────


def test_append_events_batch(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    entries = [
        ("NB4-001", {"category": "FEE_CHANGE"}),
        ("NB4-002", {"category": "LEGAL_CHANGE"}),
        ("NB4-003", None),
    ]
    count = append_events_batch(
        event_type=EVENT_CLAIM_OFFERED,
        nb="nb4",
        entries=entries,
        ledger_file=ledger,
    )
    assert count == 3
    rows = _load_ledger(ledger)
    assert [r["claim_id"] for r in rows] == ["NB4-001", "NB4-002", "NB4-003"]
    assert rows[0]["meta"]["category"] == "FEE_CHANGE"
    # Entry with None metadata has no 'meta' key
    assert "meta" not in rows[2]


def test_append_events_batch_skips_empty_claim_id(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    entries = [("NB4-001", None), ("", None), ("NB4-002", None)]
    count = append_events_batch(EVENT_CLAIM_OFFERED, "nb4", entries, ledger_file=ledger)
    assert count == 2


# ── compute_metrics ──────────────────────────────────────────────────────────


def _make_row(event: str, claim_id: str, ts: datetime, nb: str = "nb4", meta: dict | None = None) -> dict:
    row = {"ts": ts.isoformat(), "event": event, "nb": nb, "claim_id": claim_id}
    if meta:
        row["meta"] = meta
    return row


def test_compute_metrics_cite_rate() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    rows = [
        _make_row(EVENT_CLAIM_OFFERED, "C1", now - timedelta(days=5), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "C2", now - timedelta(days=4), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "C3", now - timedelta(days=3), meta={"category": "LEGAL_CHANGE"}),
        _make_row(EVENT_CLAIM_CITED_IN_CHAT, "C1", now - timedelta(days=2)),
        _make_row(EVENT_CLAIM_CITED_IN_CHAT, "C2", now - timedelta(days=1)),
    ]
    metrics = compute_metrics(rows, now=now)
    assert metrics["totals"]["offered"] == 3
    assert metrics["totals"]["cited"] == 2
    assert metrics["rates"]["cite_rate"] == round(2 / 3, 3)


def test_compute_metrics_orphan_detection() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    # C1 offered 35d ago, never cited → orphan
    # C2 offered 35d ago, cited at 10d → not orphan
    # C3 offered 10d ago, never cited → not orphan (< 30d)
    rows = [
        _make_row(EVENT_CLAIM_OFFERED, "C1", now - timedelta(days=35), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "C2", now - timedelta(days=35), meta={"category": "LEGAL_CHANGE"}),
        _make_row(EVENT_CLAIM_CITED_IN_CHAT, "C2", now - timedelta(days=10)),
        _make_row(EVENT_CLAIM_OFFERED, "C3", now - timedelta(days=10), meta={"category": "FEE_CHANGE"}),
    ]
    # Use a wider window to include C1 and C2 offered events
    metrics = compute_metrics(rows, now=now, window_days=60)
    assert metrics["orphan_count"] == 1
    assert metrics["orphans"][0]["claim_id"] == "C1"
    assert metrics["orphans"][0]["category"] == "FEE_CHANGE"
    assert metrics["orphans"][0]["age_days"] == 35


def test_compute_metrics_per_nb_breakdown() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    rows = [
        _make_row(EVENT_CLAIM_OFFERED, "A1", now - timedelta(days=3), nb="nb4"),
        _make_row(EVENT_CLAIM_OFFERED, "A2", now - timedelta(days=3), nb="nb4"),
        _make_row(EVENT_CLAIM_OFFERED, "B1", now - timedelta(days=3), nb="nb5"),
        _make_row(EVENT_CLAIM_CITED_IN_CHAT, "A1", now - timedelta(days=2), nb="nb4"),
    ]
    metrics = compute_metrics(rows, now=now)
    assert metrics["per_nb"]["nb4"]["offered"] == 2
    assert metrics["per_nb"]["nb4"]["cited"] == 1
    assert metrics["per_nb"]["nb5"]["offered"] == 1
    assert metrics["per_nb"]["nb5"]["cited"] == 0


def test_compute_metrics_per_category() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    rows = [
        _make_row(EVENT_CLAIM_OFFERED, "A", now - timedelta(days=3), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "B", now - timedelta(days=3), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "C", now - timedelta(days=3), meta={"category": "LEGAL_CHANGE"}),
        _make_row(EVENT_CLAIM_CITED_IN_CHAT, "A", now - timedelta(days=1)),
    ]
    metrics = compute_metrics(rows, now=now)
    assert metrics["per_category"]["FEE_CHANGE"]["offered"] == 2
    assert metrics["per_category"]["FEE_CHANGE"]["cited"] == 1
    assert metrics["per_category"]["LEGAL_CHANGE"]["offered"] == 1
    assert metrics["per_category"]["LEGAL_CHANGE"]["cited"] == 0


def test_compute_metrics_empty_ledger_is_safe() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    metrics = compute_metrics([], now=now)
    assert metrics["totals"]["offered"] == 0
    assert metrics["rates"]["cite_rate"] == 0.0
    assert metrics["orphans"] == []


def test_compute_metrics_window_excludes_old_rows() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    rows = [
        _make_row(EVENT_CLAIM_OFFERED, "OLD", now - timedelta(days=100), meta={"category": "FEE_CHANGE"}),
        _make_row(EVENT_CLAIM_OFFERED, "NEW", now - timedelta(days=3), meta={"category": "FEE_CHANGE"}),
    ]
    metrics = compute_metrics(rows, now=now, window_days=30)
    assert metrics["totals"]["offered"] == 1


def test_compute_metrics_malformed_ts_skipped() -> None:
    now = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    rows = [
        {"ts": "not-a-date", "event": EVENT_CLAIM_OFFERED, "nb": "nb4", "claim_id": "X"},
        _make_row(EVENT_CLAIM_OFFERED, "Y", now - timedelta(days=1)),
    ]
    metrics = compute_metrics(rows, now=now)
    assert metrics["totals"]["offered"] == 1


# ── run_scan integration ─────────────────────────────────────────────────────


def test_run_scan_writes_metrics_and_emits_orphan(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    metrics = tmp_path / "yajna_metrics.jsonl"

    # Offer a claim 35d ago, never cite it
    old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    with open(ledger, "w") as f:
        f.write(json.dumps({"ts": old_ts, "event": EVENT_CLAIM_OFFERED, "nb": "nb4", "claim_id": "ORPHAN1", "meta": {"category": "FEE_CHANGE"}}) + "\n")

    result = run_scan(ledger_file=ledger, metrics_file=metrics, window_days=60)
    assert result["orphan_count"] == 1
    # Metrics file should have one line
    assert metrics.exists()
    with open(metrics) as f:
        metrics_lines = [json.loads(l) for l in f if l.strip()]
    assert len(metrics_lines) == 1
    # Ledger should now have an ORPHAN_30D event appended
    rows = _load_ledger(ledger)
    orphan_events = [r for r in rows if r["event"] == EVENT_CLAIM_ORPHAN_30D]
    assert len(orphan_events) == 1
    assert orphan_events[0]["claim_id"] == "ORPHAN1"


def test_run_scan_idempotent_does_not_double_emit_orphans(tmp_path: Path) -> None:
    ledger = tmp_path / "yajna.jsonl"
    metrics = tmp_path / "yajna_metrics.jsonl"

    old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    with open(ledger, "w") as f:
        f.write(json.dumps({"ts": old_ts, "event": EVENT_CLAIM_OFFERED, "nb": "nb4", "claim_id": "ORPHAN1", "meta": {"category": "FEE_CHANGE"}}) + "\n")

    # First scan emits orphan
    run_scan(ledger_file=ledger, metrics_file=metrics, window_days=60)
    rows_after_1 = _load_ledger(ledger)
    orphan_count_1 = sum(1 for r in rows_after_1 if r["event"] == EVENT_CLAIM_ORPHAN_30D)
    assert orphan_count_1 == 1

    # Second scan should NOT re-emit the same orphan
    run_scan(ledger_file=ledger, metrics_file=metrics, window_days=60)
    rows_after_2 = _load_ledger(ledger)
    orphan_count_2 = sum(1 for r in rows_after_2 if r["event"] == EVENT_CLAIM_ORPHAN_30D)
    assert orphan_count_2 == 1
