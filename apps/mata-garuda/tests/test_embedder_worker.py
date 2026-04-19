"""Tests for mata_garuda.workers.embedder_worker — model pick, encode, skip-path."""
from __future__ import annotations

from unittest.mock import patch

from mata_garuda.workers import embedder_worker


def test_encode_decode_vector_roundtrip():
    vec = [0.1, -0.2, 3.14159, 42.0]
    encoded = embedder_worker.encode_vector(vec)
    decoded = embedder_worker.decode_vector(encoded)
    assert len(decoded) == len(vec)
    for a, b in zip(vec, decoded):
        assert abs(a - b) < 1e-5


def test_pick_embedding_model_prefers_nomic():
    picked = embedder_worker.pick_embedding_model(
        available=["llama3:8b", "nomic-embed-text", "mxbai-embed-large"]
    )
    assert picked == "nomic-embed-text"


def test_pick_embedding_model_falls_back_to_mxbai():
    picked = embedder_worker.pick_embedding_model(
        available=["mxbai-embed-large", "gemma4:26b"]
    )
    assert picked == "mxbai-embed-large"


def test_pick_embedding_model_none_when_no_match():
    picked = embedder_worker.pick_embedding_model(available=["gemma4:26b"])
    assert picked is None


def test_pick_embedding_model_handles_latest_suffix():
    picked = embedder_worker.pick_embedding_model(
        available=["nomic-embed-text:latest"]
    )
    assert picked == "nomic-embed-text:latest"


def test_build_embedding_input_caps_length():
    title = "t" * 100
    content = "c" * 5000
    out = embedder_worker.build_embedding_input(title, content)
    assert len(out) <= embedder_worker.MAX_EMBED_INPUT_CHARS


def test_run_embedder_embeds_when_model_available():
    items = [{"id": "1-0", "data": {"title": "t", "content": "c"}}]
    published = []
    acked = []

    with patch.object(embedder_worker, "stream_read_new", return_value=items):
        stats = embedder_worker.run_embedder(
            embed_fn=lambda m, t: [0.1, 0.2, 0.3],
            list_fn=lambda: ["nomic-embed-text"],
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats == {
        "processed": 1,
        "embedded": 1,
        "skipped_no_model": 0,
        "errors": 0,
    }
    assert published[0]["embedding_status"] == "ok"
    assert published[0]["embedding_model"] == "nomic-embed-text"
    assert published[0]["embedding_dim"] == "3"
    decoded = embedder_worker.decode_vector(published[0]["embedding"])
    assert len(decoded) == 3
    assert acked == ["1-0"]


def test_run_embedder_skips_when_no_model_available():
    items = [{"id": "1-0", "data": {"title": "t", "content": "c"}}]
    published = []

    def never_called(*a, **kw):
        raise AssertionError("embed_fn must not be called when no model available")

    with patch.object(embedder_worker, "stream_read_new", return_value=items):
        stats = embedder_worker.run_embedder(
            embed_fn=never_called,
            list_fn=lambda: ["gemma4:26b"],  # no embed model
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["skipped_no_model"] == 1
    assert stats["embedded"] == 0
    assert published[0]["embedding_status"] == "skipped_no_local_model"
    assert "embedding" not in published[0]


def test_run_embedder_records_error_on_embed_failure():
    items = [{"id": "1-0", "data": {"title": "t", "content": "c"}}]
    published = []

    def failing_embed(model, text):
        return None  # ollama 500, timeout, etc.

    with patch.object(embedder_worker, "stream_read_new", return_value=items):
        stats = embedder_worker.run_embedder(
            embed_fn=failing_embed,
            list_fn=lambda: ["nomic-embed-text"],
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["errors"] == 1
    assert published[0]["embedding_status"] == "error"


def test_run_embedder_handles_embed_exception():
    items = [{"id": "1-0", "data": {"title": "t", "content": "c"}}]
    published = []

    def raising_embed(model, text):
        raise RuntimeError("network blip")

    with patch.object(embedder_worker, "stream_read_new", return_value=items):
        stats = embedder_worker.run_embedder(
            embed_fn=raising_embed,
            list_fn=lambda: ["nomic-embed-text"],
            publish=lambda s, d: published.append(dict(d)) or "ok",
            ack=lambda s, g, m: None,
        )

    assert stats["errors"] == 1
    assert published[0]["embedding_status"] == "error"


def test_run_embedder_skips_already_embedded_items():
    items = [
        {
            "id": "1-0",
            "data": {"title": "t", "content": "c", "embedding_status": "ok"},
        }
    ]
    published = []
    acked = []

    def never_called(*a, **kw):
        raise AssertionError("embed_fn must not be called on idempotent skip")

    with patch.object(embedder_worker, "stream_read_new", return_value=items):
        stats = embedder_worker.run_embedder(
            embed_fn=never_called,
            list_fn=lambda: ["nomic-embed-text"],
            publish=lambda s, d: published.append(d) or "ok",
            ack=lambda s, g, m: acked.append(m),
        )

    assert stats == {
        "processed": 1,
        "embedded": 0,
        "skipped_no_model": 0,
        "errors": 0,
    }
    assert published == []
    assert acked == ["1-0"]


def test_run_embedder_empty_stream():
    with patch.object(embedder_worker, "stream_read_new", return_value=[]):
        stats = embedder_worker.run_embedder(list_fn=lambda: [])
    assert stats["processed"] == 0
