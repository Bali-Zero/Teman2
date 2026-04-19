"""
Mata Garuda — Embedder Worker.

Reads from garuda:enriched and attaches a local-model vector embedding
(base64-encoded float32 array) so downstream semantic-search / KG
proximity queries can run without hitting OpenAI/Google (forbidden by
Legge 1 — OSINT blindato, CLI-only LLM, no cloud embeddings).

Model priority:
  1. nomic-embed-text  — purpose-built, 768-dim, fast
  2. mxbai-embed-large — alternative 1024-dim
Both are probed via `ollama_tools.list_local_models()`. If neither is
present we DO NOT fail: item is forwarded with
`embedding_status=skipped_no_local_model` so the pipeline keeps
flowing and operators can decide to pull a model later.

Layer 2 Kognitif — enrichment stage.
"""
from __future__ import annotations

import base64
import logging
import struct
from typing import Callable

from mata_garuda.config import STREAM_ENRICHED
from mata_garuda.tools.ollama_tools import embed as ollama_embed
from mata_garuda.tools.ollama_tools import list_local_models
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.embedder")

CONSUMER_GROUP = "embedder"
CONSUMER_NAME = "embedder-1"

# Ordered by preference — first locally pulled one wins.
PREFERRED_EMBEDDING_MODELS = (
    "nomic-embed-text",
    "nomic-embed-text:latest",
    "mxbai-embed-large",
    "mxbai-embed-large:latest",
)

MAX_EMBED_INPUT_CHARS = 2000


def pick_embedding_model(
    available: list[str] | None = None,
    *,
    list_fn: Callable[..., list[str]] = list_local_models,
) -> str | None:
    """Return the first preferred embedding model that is locally pulled."""
    if available is None:
        available = list_fn()
    available_set = set(available)
    for candidate in PREFERRED_EMBEDDING_MODELS:
        if candidate in available_set:
            return candidate
    return None


def encode_vector(vec: list[float]) -> str:
    """Pack a float vector as base64(float32 little-endian) for transport."""
    packed = struct.pack(f"<{len(vec)}f", *(float(x) for x in vec))
    return base64.b64encode(packed).decode("ascii")


def decode_vector(encoded: str) -> list[float]:
    """Inverse of `encode_vector` — for downstream consumers + tests."""
    raw = base64.b64decode(encoded.encode("ascii"))
    n = len(raw) // 4
    return list(struct.unpack(f"<{n}f", raw))


def build_embedding_input(title: str, content: str) -> str:
    """Combine title + content snippet, respecting the char cap."""
    combined = f"{title}\n{content}".strip()
    return combined[:MAX_EMBED_INPUT_CHARS]


def run_embedder(
    max_items: int = 20,
    *,
    embed_fn: Callable[..., list[float] | None] = ollama_embed,
    list_fn: Callable[..., list[str]] = list_local_models,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the embedder worker.

    Always ack's and forwards; on unavailable model, items still reach
    downstream consumers with a status flag instead of being retried
    forever.
    """
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {"processed": 0, "embedded": 0, "skipped_no_model": 0, "errors": 0}

    # Decide model ONCE per pass — avoid N `/api/tags` calls.
    model = pick_embedding_model(list_fn=list_fn)

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = dict(item["data"])
        stats["processed"] += 1

        if data.get("embedding_status") in ("ok", "skipped_no_local_model"):
            # Idempotent
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        if model is None:
            data["embedding_status"] = "skipped_no_local_model"
            stats["skipped_no_model"] += 1
            publish(STREAM_ENRICHED, data)
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        text = build_embedding_input(data.get("title", ""), data.get("content", ""))
        if not text:
            data["embedding_status"] = "skipped_empty_input"
            publish(STREAM_ENRICHED, data)
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        try:
            vec = embed_fn(model, text)
        except Exception as e:  # noqa: BLE001 — broad: best-effort embedding
            logger.warning(f"[embedder] embed error: {e}")
            vec = None

        if vec is None:
            data["embedding_status"] = "error"
            stats["errors"] += 1
        else:
            data["embedding"] = encode_vector(vec)
            data["embedding_model"] = model
            data["embedding_dim"] = str(len(vec))
            data["embedding_status"] = "ok"
            stats["embedded"] += 1

        publish(STREAM_ENRICHED, data)
        ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[embedder] Done: {stats['processed']} processed, "
        f"{stats['embedded']} embedded, {stats['skipped_no_model']} skipped, "
        f"{stats['errors']} errors"
    )
    return stats
