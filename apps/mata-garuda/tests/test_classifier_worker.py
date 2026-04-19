"""Tests for mata_garuda.workers.classifier_worker — LLM + fallback + run loop."""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.config import RELEVANCE_WEIGHTS
from mata_garuda.workers import classifier_worker


def test_classify_fallback_immigration():
    out = classifier_worker.classify_fallback(
        "New KITAS rule announced by Imigrasi",
        "Starting May the kitas process will change...",
    )
    assert out["domain"] == "immigration_visa"
    assert out["source"] == "fallback_keyword"
    assert out["priority"] == "medium"
    assert out["keywords"]


def test_classify_fallback_other_when_nothing_matches():
    out = classifier_worker.classify_fallback(
        "Football transfer rumours",
        "Star midfielder expected to move clubs this summer.",
    )
    assert out["domain"] == "other"
    assert out["priority"] == "low"
    assert out["keywords"] == []


def test_classify_uses_llm_when_valid():
    def fake_llm(model, prompt, **kwargs):
        assert model == classifier_worker.CLASSIFIER_MODEL
        return {
            "domain": "tax_fiscal",
            "priority": "high",
            "keywords": ["pph", "vat", "djp"],
        }

    out = classifier_worker.classify("PPh 21 change", "new djp rule", llm=fake_llm)
    assert out["domain"] == "tax_fiscal"
    assert out["priority"] == "high"
    assert out["keywords"] == ["pph", "vat", "djp"]
    assert out["source"] == "ollama"


def test_classify_falls_back_when_llm_returns_unknown_domain():
    def fake_llm(model, prompt, **kwargs):
        return {"domain": "nonexistent_bucket", "priority": "high", "keywords": []}

    out = classifier_worker.classify(
        "New KITAS enforcement begins",
        "Imigrasi announced...",
        llm=fake_llm,
    )
    assert out["source"] == "fallback_keyword"
    assert out["domain"] == "immigration_visa"


def test_classify_falls_back_when_llm_returns_none():
    def fake_llm(model, prompt, **kwargs):
        return None

    out = classifier_worker.classify(
        "Tax update pph",
        "djp changes",
        llm=fake_llm,
    )
    assert out["source"] == "fallback_keyword"
    assert out["domain"] == "tax_fiscal"


def test_classify_tolerates_llm_exception():
    def fake_llm(model, prompt, **kwargs):
        raise RuntimeError("ollama down")

    out = classifier_worker.classify(
        "KBLI update for investors",
        "BKPM released new OSS rules",
        llm=fake_llm,
    )
    assert out["domain"] == "investment_licensing"
    assert out["source"] == "fallback_keyword"


def test_classify_coerces_keywords_to_strings_and_caps_at_8():
    def fake_llm(model, prompt, **kwargs):
        return {
            "domain": "property",
            "priority": "low",
            "keywords": [f"kw{i}" for i in range(20)] + [123, ""],
        }

    out = classifier_worker.classify("x", "y", llm=fake_llm)
    assert out["domain"] == "property"
    assert len(out["keywords"]) == 8
    assert all(isinstance(k, str) for k in out["keywords"])


def test_classify_normalises_invalid_priority_to_medium():
    def fake_llm(model, prompt, **kwargs):
        return {"domain": "labor_manpower", "priority": "URGENT", "keywords": []}

    out = classifier_worker.classify("x", "y", llm=fake_llm)
    assert out["priority"] == "medium"


def test_relevance_score_for_known_domain():
    assert classifier_worker.relevance_score_for("immigration_visa") == RELEVANCE_WEIGHTS[
        "immigration_visa"
    ]


def test_relevance_score_for_unknown_domain_is_one():
    assert classifier_worker.relevance_score_for("nonexistent") == 1


def test_run_classifier_appends_fields_and_acks():
    items = [
        {"id": "1-0", "data": {"title": "KITAS update", "content": "imigrasi news"}},
        {"id": "2-0", "data": {"title": "Sunny weather", "content": "bali sunshine"}},
    ]
    published = []
    acked = []

    def fake_llm(model, prompt, **kwargs):
        # Always fail → force fallback path
        return None

    with patch.object(classifier_worker, "stream_read_new", return_value=items):
        stats = classifier_worker.run_classifier(
            llm=fake_llm,
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["processed"] == 2
    assert stats["classified_fallback"] == 2
    assert stats["classified_llm"] == 0
    assert len(published) == 2
    first = published[0]
    assert first["domain"] == "immigration_visa"
    assert first["classified"] == "true"
    assert first["classifier_source"] == "fallback_keyword"
    assert first["relevance_score"] == str(RELEVANCE_WEIGHTS["immigration_visa"])
    assert acked == ["1-0", "2-0"]


def test_run_classifier_skips_already_classified_items():
    items = [
        {
            "id": "5-0",
            "data": {
                "title": "Already done",
                "content": "foo",
                "classified": "true",
            },
        }
    ]
    published = []
    acked = []

    def fake_llm(*a, **kw):
        raise AssertionError("LLM should not be called on pre-classified items")

    with patch.object(classifier_worker, "stream_read_new", return_value=items):
        stats = classifier_worker.run_classifier(
            llm=fake_llm,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["processed"] == 1
    assert stats["classified_llm"] == 0
    assert stats["classified_fallback"] == 0
    assert published == []
    assert acked == ["5-0"]


def test_run_classifier_counts_llm_path():
    items = [
        {"id": "1-0", "data": {"title": "pma oss", "content": "nib rule change"}},
    ]
    published = []
    acked = []

    def fake_llm(model, prompt, **kwargs):
        return {
            "domain": "investment_licensing",
            "priority": "high",
            "keywords": ["nib", "oss"],
        }

    with patch.object(classifier_worker, "stream_read_new", return_value=items):
        stats = classifier_worker.run_classifier(
            llm=fake_llm,
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats["classified_llm"] == 1
    assert stats["classified_fallback"] == 0
    assert published[0]["priority"] == "high"
    assert published[0]["keywords"] == "nib,oss"
    assert published[0]["classifier_source"] == "ollama"


def test_run_classifier_empty_stream():
    with patch.object(classifier_worker, "stream_read_new", return_value=[]):
        stats = classifier_worker.run_classifier()
    assert stats["processed"] == 0
