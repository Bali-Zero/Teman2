"""
Mata Garuda — Classifier Worker.

Reads from garuda:enriched (after dedup/normalizer), assigns:
- `domain`        one of RELEVANCE_WEIGHTS keys, or "other"
- `priority`      "high" | "medium" | "low"
- `keywords`      up to 8 lowercase tokens
- `relevance_score` 1..5 (deterministic from RELEVANCE_WEIGHTS[domain])

Uses `ollama_tools.generate_json` against `gemma4:26b`. When Ollama is
down or returns garbage, falls back to a deterministic keyword-match
classifier so the pipeline keeps moving. The fallback is intentionally
simple (substring over a lowercase corpus) — its job is only to stop
the worker from silently stalling.

Layer 2 Kognitif — enrichment stage.
"""
from __future__ import annotations

import logging
from typing import Callable

from mata_garuda.config import RELEVANCE_WEIGHTS, STREAM_ENRICHED
from mata_garuda.tools.ollama_tools import generate_json
from mata_garuda.workers.base_worker import (
    stream_ack,
    stream_publish,
    stream_read_new,
)

logger = logging.getLogger("mata_garuda.workers.classifier")

CONSUMER_GROUP = "classifier"
CONSUMER_NAME = "classifier-1"

CLASSIFIER_MODEL = "gemma4:26b"

_DOMAINS = tuple(RELEVANCE_WEIGHTS.keys()) + ("other",)

_CLASSIFY_PROMPT = """You classify Indonesian / English news or regulation snippets for a Bali business-services firm.

Return STRICT JSON (no prose, no markdown fences) with keys:
  "domain":   one of {domains}
  "priority": "high" | "medium" | "low"
  "keywords": array of up to 8 lowercase tokens, no phrases

Priority rubric:
  high   = affects clients THIS WEEK (new rule, enforcement wave, fee change)
  medium = will matter within a quarter (draft rule, consultation, trend)
  low    = background colour, opinion, long-horizon

Text to classify:
TITLE: {title}
CONTENT: {content}
"""

# Fallback keyword buckets. First-match wins, so order matters (most
# specific domains first). Kept deliberately small — this is a safety
# net, not a production NLP stage.
_FALLBACK_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("immigration_visa", ("visa", "kitas", "kitap", "imigrasi", "immigration", "passport", "paspor", "overstay")),
    ("tax_fiscal", ("tax", "pajak", "djp", "ppn", "pph", "vat", "npwp", "sptahunan")),
    ("investment_licensing", ("bkpm", "oss", "investment", "investor", "license", "izin", "nib", "kbli", "pma")),
    ("labor_manpower", ("manpower", "tenaga kerja", "bpjs", "ketenagakerjaan", "umk", "layoff", "phk")),
    ("provincial_bali", ("bali", "denpasar", "badung", "gianyar", "ubud", "governor bali")),
    ("financial_banking", ("bank", "ojk", "fintech", "kredit", "loan", "interest rate")),
    ("property", ("property", "land", "tanah", "sertifikat", "shm", "hgu", "hgb", "leasehold")),
    ("environmental", ("environment", "lingkungan", "amdal", "waste", "sampah", "climate")),
    ("ai_research", ("ai ", "llm", "neural", "model ", "paper", "arxiv", "huggingface")),
    ("procurement", ("procurement", "tender", "lpse", "lkpp", "pengadaan")),
)


def classify_fallback(title: str, content: str) -> dict:
    """Deterministic keyword-match classifier used when Ollama is down."""
    corpus = f"{title} {content}".lower()
    for domain, needles in _FALLBACK_KEYWORDS:
        if any(needle in corpus for needle in needles):
            keywords = [n.strip() for n in needles if n.strip() in corpus][:8]
            return {
                "domain": domain,
                "priority": "medium",
                "keywords": keywords,
                "source": "fallback_keyword",
            }
    return {
        "domain": "other",
        "priority": "low",
        "keywords": [],
        "source": "fallback_keyword",
    }


def _coerce_classification(raw: dict | None) -> dict:
    """Validate an LLM response; on any problem return fallback None sentinel."""
    if not isinstance(raw, dict):
        return {}

    domain = str(raw.get("domain", "")).strip().lower()
    if domain not in _DOMAINS:
        return {}

    priority = str(raw.get("priority", "")).strip().lower()
    if priority not in ("high", "medium", "low"):
        priority = "medium"

    keywords_raw = raw.get("keywords", [])
    if not isinstance(keywords_raw, list):
        keywords_raw = []
    keywords = [
        str(k).strip().lower()
        for k in keywords_raw
        if isinstance(k, (str, int, float)) and str(k).strip()
    ][:8]

    return {
        "domain": domain,
        "priority": priority,
        "keywords": keywords,
        "source": "ollama",
    }


def classify(
    title: str,
    content: str,
    *,
    llm: Callable[..., dict | None] = generate_json,
) -> dict:
    """Classify a single item. Tries Ollama first, then keyword fallback."""
    prompt = _CLASSIFY_PROMPT.format(
        domains=", ".join(_DOMAINS),
        title=title[:300],
        content=content[:500],
    )

    try:
        raw = llm(CLASSIFIER_MODEL, prompt, num_predict=180)
    except Exception as e:  # noqa: BLE001 — broad: LLM transport is best-effort
        logger.warning(f"[classifier] LLM error: {e}")
        raw = None

    validated = _coerce_classification(raw)
    if validated:
        return validated

    return classify_fallback(title, content)


def relevance_score_for(domain: str) -> int:
    """Map domain → 1..5 integer using RELEVANCE_WEIGHTS, clamped."""
    weight = RELEVANCE_WEIGHTS.get(domain, 1)
    return max(1, min(5, int(weight)))


def run_classifier(
    max_items: int = 20,
    *,
    llm: Callable[..., dict | None] = generate_json,
    publish: Callable[..., str] | None = None,
    ack: Callable[..., None] | None = None,
) -> dict:
    """Run one pass of the classifier worker.

    Reads from STREAM_ENRICHED (upstream dedup/normalizer output),
    republishes the same item to STREAM_ENRICHED with classification
    fields appended. Downstream scorer/alert workers read the enriched
    fields from the same stream.
    """
    publish = publish or (lambda stream, data: stream_publish(stream, data))
    ack = ack or (lambda stream, group, msg_id: stream_ack(stream, group, msg_id))

    stats = {"processed": 0, "classified_llm": 0, "classified_fallback": 0}

    items = stream_read_new(
        STREAM_ENRICHED, CONSUMER_GROUP, CONSUMER_NAME, count=max_items
    )
    if not items:
        return stats

    for item in items:
        msg_id = item["id"]
        data = dict(item["data"])
        stats["processed"] += 1

        # Idempotency: if this item already has a domain tag, skip work.
        if data.get("classified") == "true":
            ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)
            continue

        title = data.get("title", "")
        content = data.get("content", "")

        classification = classify(title, content, llm=llm)
        if classification["source"] == "ollama":
            stats["classified_llm"] += 1
        else:
            stats["classified_fallback"] += 1

        data["domain"] = classification["domain"]
        data["priority"] = classification["priority"]
        data["keywords"] = ",".join(classification["keywords"])
        data["relevance_score"] = str(relevance_score_for(classification["domain"]))
        data["classified"] = "true"
        data["classifier_source"] = classification["source"]

        publish(STREAM_ENRICHED, data)
        ack(STREAM_ENRICHED, CONSUMER_GROUP, msg_id)

    logger.info(
        f"[classifier] Done: {stats['processed']} processed, "
        f"LLM={stats['classified_llm']}, fallback={stats['classified_fallback']}"
    )
    return stats
