"""
Mata Garuda — Named Entity Recognition Worker.

Reads from garuda:enriched (after classifier), extracts entities via
qwen3.5:9b Ollama CLI and republishes with an `entities` JSON field.
Output schema mirrors what Layer 3 analysts + future KG ingestion
expect: persons, organizations, locations, laws, monetary_values,
dates — always present, empty list if none.

qwen3.5:9b chosen over gemma4:26b here because NER is a
short-context / structured-extraction task where the smaller model
is fast enough and leaves headroom for gemma4:26b to keep serving
the classifier.

Layer 2 Kognitif — enrichment stage.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from mata_garuda.config import STREAM_ENRICHED
from mata_garuda.tools.ollama_tools import generate_json
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.ner")

CONSUMER_GROUP = "ner"
CONSUMER_NAME = "ner-1"

NER_MODEL = "qwen3.5:9b"

_EMPTY_ENTITIES = {
    "persons": [],
    "organizations": [],
    "locations": [],
    "laws": [],
    "monetary_values": [],
    "dates": [],
}

_NER_PROMPT = """Extract named entities from the text. Return STRICT JSON (no prose, no markdown).

Required keys — each an array of strings (empty array if none found):
  persons         full personal names only (no honorifics alone)
  organizations   companies, ministries, agencies, NGOs
  locations       cities, provinces, countries, landmarks
  laws            statutes, regulations, decrees (e.g. "UU 6/2023", "PP No. 28")
  monetary_values numeric amounts with currency (e.g. "Rp 500 juta", "USD 1.2M")
  dates           explicit dates or date ranges ("12 March 2026", "Q2 2026")

Include only entities explicitly in the text. Do not infer.

TITLE: {title}
CONTENT: {content}
"""


def _coerce_entities(raw: dict | None) -> dict:
    """Force the LLM response into the expected schema (6 keys, str lists)."""
    out = {k: list(v) for k, v in _EMPTY_ENTITIES.items()}
    if not isinstance(raw, dict):
        return out

    for key in out:
        value = raw.get(key, [])
        if not isinstance(value, list):
            continue
        cleaned = []
        for v in value:
            if isinstance(v, (str, int, float)):
                s = str(v).strip()
                if s:
                    cleaned.append(s)
        # Dedup preserving order, cap at 20 per bucket
        seen: set[str] = set()
        dedup: list[str] = []
        for s in cleaned:
            key_norm = s.lower()
            if key_norm in seen:
                continue
            seen.add(key_norm)
            dedup.append(s)
            if len(dedup) >= 20:
                break
        out[key] = dedup

    return out


def extract_entities(
    title: str,
    content: str,
    *,
    llm: Callable[..., dict | None] = generate_json,
) -> dict:
    """Extract entities from a single item. Always returns a full dict."""
    prompt = _NER_PROMPT.format(title=title[:300], content=content[:1000])

    try:
        raw = llm(NER_MODEL, prompt, num_predict=400)
    except Exception as e:  # noqa: BLE001 — broad: LLM transport is best-effort
        logger.warning(f"[ner] LLM error: {e}")
        raw = None

    return _coerce_entities(raw)


def run_ner(
    max_items: int = 20,
    *,
    llm: Callable[..., dict | None] = generate_json,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the NER worker.

    Reads STREAM_ENRICHED, republishes items with an `entities` JSON
    string field appended. Sets `ner_completed=true` for idempotency.
    """
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {"processed": 0, "extracted": 0, "empty": 0}

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = dict(item["data"])
        stats["processed"] += 1

        if data.get("ner_completed") == "true":
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        entities = extract_entities(
            data.get("title", ""), data.get("content", ""), llm=llm
        )

        # Serialise as JSON string (Redis Streams is flat string-to-string)
        data["entities"] = json.dumps(entities, ensure_ascii=False)
        data["ner_completed"] = "true"

        total = sum(len(v) for v in entities.values())
        if total > 0:
            stats["extracted"] += 1
        else:
            stats["empty"] += 1

        publish(STREAM_ENRICHED, data)
        ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[ner] Done: {stats['processed']} processed, "
        f"{stats['extracted']} with entities, {stats['empty']} empty"
    )
    return stats
