"""Bahasa Indonesia NER extractor.

Discovered in R7 SOTA 2026-05-08.
Model: cahya/bert-base-indonesian-NER (HuggingFace, free).
Labels: PERSON, ORG, LOC, TIME, QUANTITY.

Used cross-domain (B1 regulation entity extraction, B5 macro stakeholders,
B6 OSINT person/org detection).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Sequence

DEFAULT_MODEL = "cahya/bert-base-indonesian-NER"


@dataclass(frozen=True)
class NamedEntity:
    label: str  # "PERSON" | "ORG" | "LOC" | "TIME" | "QUANTITY"
    text: str
    score: float
    start: int
    end: int


class NERExtractor:
    """Lazy-loaded, thread-safe NER pipeline.

    Wave 1 fix (Codex GPT-5 + DeepSeek v4, 2026-05-08):
    Old `__init__` called `pipeline()` eagerly, which downloads ~440MB and uses
    ~1.5GB RAM on first use. Now the pipeline is materialised on first
    `extract()` call.

    Wave 2 fix (DeepSeek W2 + Codex W2, 2026-05-08):
    Lazy load was racy: two concurrent `extract()` calls could both see
    `_pipeline is None` and both call HuggingFace `pipeline()`, downloading
    the model twice. Double-checked locking pattern serialises the init.

    Also: `transformers` is imported lazily inside `_get_pipeline()` so that
    a worker that only needs `gov_apis_health` does NOT pull torch/transformers
    at import time.
    """

    _lock = threading.Lock()

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self._model_name = model_name
        self._pipeline = None  # lazily initialised in _get_pipeline()

    def _get_pipeline(self):
        if self._pipeline is None:
            with self._lock:
                if self._pipeline is None:
                    # Lazy import: avoids loading transformers/torch unless
                    # extract() is actually called.
                    from transformers import pipeline as _hf_pipeline

                    self._pipeline = _hf_pipeline(
                        "ner",
                        model=self._model_name,
                        aggregation_strategy="simple",
                    )
        return self._pipeline

    def extract(self, text: str, labels: Sequence[str] | None = None) -> list[NamedEntity]:
        if not text:
            return []
        raw = self._get_pipeline()(text)
        entities = [
            NamedEntity(
                label=item["entity_group"],
                text=item["word"],
                score=float(item["score"]),
                start=int(item["start"]),
                end=int(item["end"]),
            )
            for item in raw
        ]
        if labels is None:
            return entities
        labelset = set(labels)
        return [e for e in entities if e.label in labelset]
