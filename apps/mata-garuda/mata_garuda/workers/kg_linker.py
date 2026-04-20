"""
Mata Garuda — KG Linker Worker (Layer 3 Nexus).

Reads from garuda:enriched (after NER has populated `entities`), inserts
entities + co-occurrence relations into the local SQLite KG.

Strategy:
- Each entity extracted by NER becomes a kg_entities row (typed)
- For each pair of entities co-occurring in the same article, emit a
  `co_mentioned_with` relation. Confidence starts at 0.4, rises via
  reinforcement on repeated observations.
- Article URL attached as evidence_url.
- Each relevant article also recorded as an observation on each
  entity (field='mentioned_in', value=title, source_url=url).

Layer 3 — feeds Connector/Anomaly/Strategos cognitive layers that need
to query "which entities appeared together when?"
"""
from __future__ import annotations

import json
import logging
from itertools import combinations

from mata_garuda.config import STREAM_ENRICHED
from mata_garuda.runtime.kg_sqlite import KnowledgeGraph
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.kg_linker")

CONSUMER_GROUP = "kg_linker"
CONSUMER_NAME = "kg_linker-1"

# NER entity categories we want in the KG. Limits the blast radius to
# things worth linking; drops e.g. monetary_values (too noisy).
LINKABLE_ENTITY_TYPES: tuple[str, ...] = (
    "persons",
    "organizations",
    "locations",
    "laws",
    "products",
)

MAX_PAIRS_PER_ARTICLE = 50  # cap combinatorial explosion on dense docs


def _parse_entities(raw: str | dict | None) -> dict[str, list[str]]:
    """NER stores entities as JSON string. Normalize to dict[list]."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {k: (v if isinstance(v, list) else []) for k, v in raw.items()}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        k: (v if isinstance(v, list) else [])
        for k, v in parsed.items()
        if k in LINKABLE_ENTITY_TYPES
    }


def link_item(kg: KnowledgeGraph, data: dict) -> dict:
    """Insert entities + co-occurrence relations for one enriched item."""
    entities_dict = _parse_entities(data.get("entities"))
    flat: list[tuple[str, str]] = []  # (type, canonical_name)
    for ent_type, names in entities_dict.items():
        for name in names:
            cn = (name or "").strip()
            if not cn:
                continue
            flat.append((ent_type, cn))

    url = data.get("url", "")
    title = data.get("title", "")

    # Upsert every entity + attach observation
    ent_ids = []
    for ent_type, name in flat:
        kg.upsert_entity(ent_type, name)
        if title:
            kg.record_observation(
                ent_type, name, field="mentioned_in",
                value=title[:200], source_url=url or None,
            )
        ent_ids.append((ent_type, name))

    # Pairwise co-occurrence relations (capped)
    pairs = list(combinations(ent_ids, 2))[:MAX_PAIRS_PER_ARTICLE]
    for (t1, n1), (t2, n2) in pairs:
        kg.upsert_relation(
            t1, n1, "co_mentioned_with", t2, n2,
            evidence_url=url or None, confidence=0.4,
        )

    return {
        "entities": len(flat),
        "relations_emitted": len(pairs),
    }


def run_kg_linker(max_items: int = 50, kg: KnowledgeGraph | None = None) -> dict:
    """Drain garuda:enriched through KG linker. Returns stats."""
    kg = kg or KnowledgeGraph()
    stats = {"processed": 0, "skipped_no_entities": 0, "linked": 0,
             "entities_total": 0, "relations_total": 0}

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = dict(item["data"])
        stats["processed"] += 1

        if not data.get("entities"):
            stats["skipped_no_entities"] += 1
            stream_ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        try:
            r = link_item(kg, data)
            stats["linked"] += 1
            stats["entities_total"] += r["entities"]
            stats["relations_total"] += r["relations_emitted"]
        except Exception as exc:
            logger.warning("kg_linker failed on %s: %s", msg_id, exc)

        stream_ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        "[kg_linker] Done: %d processed, %d linked, %d entities, %d rels",
        stats["processed"], stats["linked"],
        stats["entities_total"], stats["relations_total"],
    )
    return stats
