"""Tests for mata_garuda.workers.semantic_diff_worker — snapshot pairing + diff."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from mata_garuda.workers import semantic_diff_worker


def test_snapshot_type_deterministic():
    a = semantic_diff_worker.snapshot_type_for("https://example.id/foo")
    b = semantic_diff_worker.snapshot_type_for("https://example.id/foo")
    assert a == b
    assert a.startswith(semantic_diff_worker.SNAPSHOT_TYPE_PREFIX + ":")


def test_text_similarity_extremes():
    assert semantic_diff_worker.text_similarity("", "") == 1.0
    assert semantic_diff_worker.text_similarity("abc", "") == 0.0
    assert semantic_diff_worker.text_similarity("same", "same") == 1.0


def test_text_similarity_partial():
    a = "The new rule requires KITAS holders to report monthly."
    b = "The new rule requires KITAS holders to report weekly."
    ratio = semantic_diff_worker.text_similarity(a, b)
    assert 0.8 < ratio < 1.0


def test_coerce_diff_verdict_none():
    assert semantic_diff_worker._coerce_diff_verdict(None) == {
        "significant": False,
        "change_summary": "",
    }


def test_coerce_diff_verdict_significant_without_summary_defaults_off():
    out = semantic_diff_worker._coerce_diff_verdict(
        {"significant": True, "change_summary": "   "}
    )
    assert out == {"significant": False, "change_summary": ""}


def test_coerce_diff_verdict_valid():
    out = semantic_diff_worker._coerce_diff_verdict(
        {"significant": True, "change_summary": "Reporting cadence changed"}
    )
    assert out["significant"] is True
    assert "cadence" in out["change_summary"]


def test_parse_snapshot_handles_invalid_json_gracefully():
    raw_entry = {"content": "not-json", "source": "x"}
    parsed = semantic_diff_worker._parse_snapshot(raw_entry)
    assert parsed["title"] == ""
    assert parsed["content"] == "not-json"


def test_parse_snapshot_happy_path():
    payload = json.dumps({"title": "t", "content": "c", "captured_at": "2026-04-20"})
    parsed = semantic_diff_worker._parse_snapshot({"content": payload})
    assert parsed["title"] == "t"
    assert parsed["content"] == "c"


def test_run_semantic_diff_skips_non_regulation_source_type():
    items = [{"id": "1-0", "data": {"source_type": "news", "url": "u"}}]
    published = []
    acked = []
    fake_kb = MagicMock()

    def never_called(*a, **kw):
        raise AssertionError("LLM should not run on non-regulation items")

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=never_called,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["skipped_non_regulation"] == 1
    assert published == []
    assert acked == ["1-0"]


def test_run_semantic_diff_skips_no_url():
    items = [{"id": "1-0", "data": {"source_type": "regulation", "url": "  "}}]
    fake_kb = MagicMock()

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=lambda *a, **kw: None,
            publish=lambda s, d: None,
            ack=lambda s, g, m: None,
        )

    assert stats["skipped_no_url"] == 1


def test_run_semantic_diff_first_seen_stores_snapshot():
    items = [
        {
            "id": "1-0",
            "data": {
                "source_type": "regulation",
                "url": "https://example.go.id/page",
                "title": "Rule v1",
                "content": "Content of v1",
            },
        }
    ]
    fake_kb = MagicMock()
    fake_kb.get_by_type.return_value = []

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=lambda *a, **kw: None,  # must not be called on first-seen
            publish=lambda s, d: None,
            ack=lambda s, g, m: None,
        )

    assert stats["first_seen"] == 1
    fake_kb.store.assert_called_once()


def test_run_semantic_diff_unchanged_when_similarity_high():
    items = [
        {
            "id": "2-0",
            "data": {
                "source_type": "regulation",
                "url": "https://example.go.id/p",
                "title": "Rule",
                "content": "The new rule requires KITAS holders to report monthly.",
            },
        }
    ]
    prior_snapshot = {
        "content": json.dumps(
            {
                "title": "Rule",
                "content": "The new rule requires KITAS holders to report monthly.",
                "captured_at": "2026-04-01",
            }
        )
    }
    fake_kb = MagicMock()
    fake_kb.get_by_type.return_value = [prior_snapshot]

    def never_called(*a, **kw):
        raise AssertionError("LLM should not run when text unchanged")

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=never_called,
            publish=lambda s, d: None,
            ack=lambda s, g, m: None,
        )

    assert stats["unchanged"] == 1
    assert stats["semantic_alerts"] == 0


def test_run_semantic_diff_publishes_alert_on_significant_change():
    items = [
        {
            "id": "3-0",
            "data": {
                "source_type": "regulation",
                "url": "https://example.go.id/p",
                "title": "Rule",
                "content": "A totally rewritten rule with new obligations and fees.",
                "source": "imigrasi.go.id",
            },
        }
    ]
    prior_snapshot = {
        "content": json.dumps(
            {
                "title": "Rule",
                "content": "An old much shorter rule.",
                "captured_at": "2026-04-01",
            }
        )
    }
    fake_kb = MagicMock()
    fake_kb.get_by_type.return_value = [prior_snapshot]

    fake_llm = lambda m, p, **k: {  # noqa: E731
        "significant": True, "change_summary": "New obligations added"
    }

    published = []

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=fake_llm,
            publish=lambda s, d: published.append((s, dict(d))) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["semantic_alerts"] == 1
    stream, alert = published[0]
    assert stream == semantic_diff_worker.STREAM_ALERTS
    assert alert["kind"] == "regulation_change"
    assert alert["change_summary"] == "New obligations added"
    # Snapshot is re-stored so next diff compares to NEW, not stale OLD
    fake_kb.store.assert_called_once()


def test_run_semantic_diff_cosmetic_change_no_alert():
    items = [
        {
            "id": "4-0",
            "data": {
                "source_type": "regulation",
                "url": "https://example.go.id/p",
                "title": "Rule",
                "content": "Rule text with minor typo fix and reformatting but same idea.",
            },
        }
    ]
    prior_snapshot = {
        "content": json.dumps(
            {
                "title": "Rule",
                "content": "Rule text with a minor typo and reformatting and same idea.",
                "captured_at": "2026-04-01",
            }
        )
    }
    fake_kb = MagicMock()
    fake_kb.get_by_type.return_value = [prior_snapshot]

    fake_llm = lambda m, p, **k: {  # noqa: E731
        "significant": False, "change_summary": ""
    }

    published = []

    with patch.object(semantic_diff_worker, "stream_read_new", return_value=items):
        stats = semantic_diff_worker.run_semantic_diff(
            fake_kb,
            llm=fake_llm,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["cosmetic"] == 1
    assert stats["semantic_alerts"] == 0
    assert published == []


def test_run_semantic_diff_empty_stream():
    fake_kb = MagicMock()
    with patch.object(semantic_diff_worker, "stream_read_new", return_value=[]):
        stats = semantic_diff_worker.run_semantic_diff(fake_kb)
    assert stats["processed"] == 0
