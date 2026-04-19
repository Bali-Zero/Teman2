"""Tests for mata_garuda.workers.ner_worker — entity extraction + coercion."""
from __future__ import annotations

import json
from unittest.mock import patch

from mata_garuda.workers import ner_worker


def test_coerce_entities_empty_on_none():
    out = ner_worker._coerce_entities(None)
    assert set(out.keys()) == {
        "persons",
        "organizations",
        "locations",
        "laws",
        "monetary_values",
        "dates",
    }
    assert all(v == [] for v in out.values())


def test_coerce_entities_empty_on_garbage():
    assert ner_worker._coerce_entities("not a dict")["persons"] == []
    assert ner_worker._coerce_entities([])["persons"] == []


def test_coerce_entities_filters_non_strings_and_dedups():
    raw = {
        "persons": ["Joko Widodo", "joko widodo", None, "", "Prabowo"],
        "organizations": ["DJP", 123, "DJP"],  # int coerced to string, dedup
        "locations": ["Bali"],
        "laws": [],
        "monetary_values": [],
        "dates": [],
    }
    out = ner_worker._coerce_entities(raw)
    assert out["persons"] == ["Joko Widodo", "Prabowo"]
    assert out["organizations"] == ["DJP", "123"]
    assert out["locations"] == ["Bali"]


def test_coerce_entities_caps_bucket_at_20():
    raw = {"persons": [f"person_{i}" for i in range(50)]}
    out = ner_worker._coerce_entities(raw)
    assert len(out["persons"]) == 20


def test_coerce_entities_ignores_non_list_fields():
    raw = {"persons": "not a list", "organizations": ["OK"]}
    out = ner_worker._coerce_entities(raw)
    assert out["persons"] == []
    assert out["organizations"] == ["OK"]


def test_extract_entities_uses_llm_when_valid():
    def fake_llm(model, prompt, **kwargs):
        assert model == ner_worker.NER_MODEL
        return {
            "persons": ["Joko Widodo"],
            "organizations": ["DJP"],
            "locations": ["Jakarta"],
            "laws": ["UU 6/2023"],
            "monetary_values": ["Rp 500 juta"],
            "dates": ["12 March 2026"],
        }

    out = ner_worker.extract_entities("title", "content", llm=fake_llm)
    assert out["persons"] == ["Joko Widodo"]
    assert out["laws"] == ["UU 6/2023"]


def test_extract_entities_empty_when_llm_returns_none():
    out = ner_worker.extract_entities(
        "title", "content", llm=lambda *a, **kw: None
    )
    assert all(v == [] for v in out.values())


def test_extract_entities_empty_when_llm_raises():
    def boom(*args, **kwargs):
        raise RuntimeError("ollama exploded")

    out = ner_worker.extract_entities("title", "content", llm=boom)
    assert out["persons"] == []


def test_run_ner_publishes_entities_and_acks():
    items = [
        {"id": "1-0", "data": {"title": "foo", "content": "bar"}},
    ]
    published = []
    acked = []

    def fake_llm(model, prompt, **kwargs):
        return {"persons": ["A"], "organizations": [], "locations": [],
                "laws": [], "monetary_values": [], "dates": []}

    with patch.object(ner_worker, "stream_read_new", return_value=items):
        stats = ner_worker.run_ner(
            llm=fake_llm,
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats == {"processed": 1, "extracted": 1, "empty": 0}
    assert published[0]["ner_completed"] == "true"
    entities = json.loads(published[0]["entities"])
    assert entities["persons"] == ["A"]
    assert acked == ["1-0"]


def test_run_ner_counts_empty_when_no_entities_found():
    items = [{"id": "1-0", "data": {"title": "t", "content": "c"}}]
    published = []

    with patch.object(ner_worker, "stream_read_new", return_value=items):
        stats = ner_worker.run_ner(
            llm=lambda *a, **kw: None,
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["empty"] == 1
    assert stats["extracted"] == 0
    entities = json.loads(published[0]["entities"])
    assert all(v == [] for v in entities.values())


def test_run_ner_skips_already_processed():
    items = [
        {"id": "9-0", "data": {"title": "x", "content": "y", "ner_completed": "true"}},
    ]
    published = []
    acked = []

    def no_llm(*a, **kw):
        raise AssertionError("LLM should not run on idempotent skip")

    with patch.object(ner_worker, "stream_read_new", return_value=items):
        stats = ner_worker.run_ner(
            llm=no_llm,
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats == {"processed": 1, "extracted": 0, "empty": 0}
    assert published == []
    assert acked == ["9-0"]


def test_run_ner_empty_stream():
    with patch.object(ner_worker, "stream_read_new", return_value=[]):
        stats = ner_worker.run_ner()
    assert stats == {"processed": 0, "extracted": 0, "empty": 0}
