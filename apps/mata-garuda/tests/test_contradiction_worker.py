"""Tests for mata_garuda.workers.contradiction_worker — verdict coercion + run loop."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from mata_garuda.workers import contradiction_worker


def test_coerce_verdict_none_defaults_to_noop():
    out = contradiction_worker._coerce_verdict(None, prior_count=3)
    assert out == {"contradicts": False, "which": -1, "reason": ""}


def test_coerce_verdict_valid_contradiction():
    raw = {"contradicts": True, "which": 1, "reason": "fee raised"}
    out = contradiction_worker._coerce_verdict(raw, prior_count=3)
    assert out == {"contradicts": True, "which": 1, "reason": "fee raised"}


def test_coerce_verdict_contradicts_true_but_index_out_of_range():
    raw = {"contradicts": True, "which": 99, "reason": "r"}
    out = contradiction_worker._coerce_verdict(raw, prior_count=3)
    assert out["contradicts"] is False


def test_coerce_verdict_contradicts_true_but_empty_reason():
    raw = {"contradicts": True, "which": 0, "reason": "  "}
    out = contradiction_worker._coerce_verdict(raw, prior_count=3)
    assert out["contradicts"] is False


def test_coerce_verdict_nonint_which_falls_back_to_neg1():
    raw = {"contradicts": False, "which": "NaN", "reason": ""}
    out = contradiction_worker._coerce_verdict(raw, prior_count=3)
    assert out["which"] == -1


def test_check_contradiction_short_circuits_on_empty_priors():
    called = []

    def fake_llm(*a, **kw):
        called.append(1)
        return {"contradicts": True, "which": 0, "reason": "x"}

    out = contradiction_worker.check_contradiction("t", "c", [], llm=fake_llm)
    assert out["contradicts"] is False
    assert called == []  # LLM skipped entirely


def test_check_contradiction_happy_path():
    priors = [{"content": "prior 1"}, {"content": "prior 2"}]
    fake_llm = lambda m, p, **k: {  # noqa: E731
        "contradicts": True, "which": 0, "reason": "policy reversed"
    }
    out = contradiction_worker.check_contradiction("t", "c", priors, llm=fake_llm)
    assert out["contradicts"] is True
    assert out["which"] == 0


def test_check_contradiction_tolerates_llm_exception():
    def boom(*a, **kw):
        raise RuntimeError("offline")

    out = contradiction_worker.check_contradiction(
        "t", "c", [{"content": "p"}], llm=boom
    )
    assert out["contradicts"] is False


def test_run_contradiction_skips_non_watched_domain():
    items = [
        {"id": "1-0", "data": {"domain": "property", "title": "t", "content": "c"}},
    ]
    published = []
    acked = []
    fake_kb = MagicMock()

    def never_called(*a, **kw):
        raise AssertionError("LLM should not run on non-watched domain")

    with patch.object(contradiction_worker, "stream_read_new", return_value=items):
        stats = contradiction_worker.run_contradiction(
            fake_kb,
            llm=never_called,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["skipped_domain"] == 1
    assert stats["checked"] == 0
    assert published == []
    assert acked == ["1-0"]
    fake_kb.search.assert_not_called()


def test_run_contradiction_publishes_alert_on_conflict():
    items = [
        {
            "id": "2-0",
            "data": {
                "domain": "immigration_visa",
                "title": "New KITAS rule",
                "content": "Fee reversed to old amount",
                "url": "https://example.id/new",
                "source": "imigrasi.go.id",
            },
        }
    ]
    priors = [
        {"content": "Fee raised last month", "source": "https://example.id/old"},
        {"content": "Another unrelated item", "source": "https://example.id/x"},
    ]
    fake_kb = MagicMock()
    fake_kb.search.return_value = priors

    fake_llm = lambda m, p, **k: {  # noqa: E731
        "contradicts": True, "which": 0, "reason": "Fee policy reversed"
    }

    published = []
    acked = []

    with patch.object(contradiction_worker, "stream_read_new", return_value=items):
        stats = contradiction_worker.run_contradiction(
            fake_kb,
            llm=fake_llm,
            publish=lambda s, d: published.append((s, dict(d))) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["alerts"] == 1
    assert stats["checked"] == 1
    assert len(published) == 1
    stream, alert = published[0]
    assert stream == contradiction_worker.STREAM_ALERTS
    assert alert["kind"] == "contradiction"
    assert alert["domain"] == "immigration_visa"
    assert alert["prior_which"] == "0"
    assert alert["prior_source"] == "https://example.id/old"
    fake_kb.store.assert_called_once()
    assert acked == ["2-0"]


def test_run_contradiction_no_alert_when_llm_says_no():
    items = [
        {
            "id": "3-0",
            "data": {
                "domain": "tax_fiscal",
                "title": "Tax update",
                "content": "Clarification only",
            },
        }
    ]
    fake_kb = MagicMock()
    fake_kb.search.return_value = [{"content": "prior"}]

    fake_llm = lambda m, p, **k: {  # noqa: E731
        "contradicts": False, "which": -1, "reason": ""
    }

    published = []

    with patch.object(contradiction_worker, "stream_read_new", return_value=items):
        stats = contradiction_worker.run_contradiction(
            fake_kb,
            llm=fake_llm,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["alerts"] == 0
    assert published == []


def test_run_contradiction_empty_stream():
    fake_kb = MagicMock()
    with patch.object(contradiction_worker, "stream_read_new", return_value=[]):
        stats = contradiction_worker.run_contradiction(fake_kb)
    assert stats["processed"] == 0
