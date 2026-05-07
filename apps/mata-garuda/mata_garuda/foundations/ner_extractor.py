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
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self._model_name = model_name
        self._pipeline = pipeline(
            "ner",
            model=model_name,
            aggregation_strategy="simple",
        )

    def extract(self, text: str, labels: Sequence[str] | None = None) -> list[NamedEntity]:
        if not text:
            return []
        raw = self._pipeline(text)
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
