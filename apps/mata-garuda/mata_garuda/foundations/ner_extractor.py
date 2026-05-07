"""Bahasa Indonesia NER extractor.

Discovered in R7 SOTA 2026-05-08.
Model: cahya/bert-base-indonesian-NER (HuggingFace, free).
Labels: PERSON, ORG, LOC, TIME, QUANTITY.

Used cross-domain (B1 regulation entity extraction, B5 macro stakeholders,
B6 OSINT person/org detection).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from transformers import pipeline

DEFAULT_MODEL = "cahya/bert-base-indonesian-NER"


@dataclass(frozen=True)
class NamedEntity:
    label: str  # "PERSON" | "ORG" | "LOC" | "TIME" | "QUANTITY"
    text: str
    score: float
    start: int
    end: int


class NERExtractor:
    """Lazy-loaded NER pipeline.

    External-review fix (Codex GPT-5 + DeepSeek v4, 2026-05-08):
    Old `__init__` called `pipeline()` eagerly, which downloads ~440MB and uses
    ~1.5GB RAM on first use. Now the pipeline is materialised on first
    `extract()` call, so a harmless `import` of mata_garuda.foundations doesn't
    stall workers or saturate Mini-Pro2 memory.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self._model_name = model_name
        self._pipeline = None  # lazily initialised in extract()

    def _get_pipeline(self):
        if self._pipeline is None:
            self._pipeline = pipeline(
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
