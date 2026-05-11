"""arxiv-sanity SVM-on-tfidf scorer.

Discovered in R5 SOTA 2026-05-08. Karpathy's pattern: zero LLM cost,
self-host. Port of arxiv-sanity-lite core algorithm.

Train on Antonello's tagged papers, score new candidates by per-tag SVM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV


@dataclass(frozen=True)
class LabeledPaper:
    id: str
    abstract: str
    label: int  # 1 = relevant, 0 = not relevant


class ArxivSanityScorer:
    def __init__(self, max_features: int = 5000):
        self._max_features = max_features
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._model: Optional[CalibratedClassifierCV] = None

    def train(self, papers: list[LabeledPaper]) -> None:
        labels = {p.label for p in papers}
        if len(labels) < 2:
            raise ValueError("Training requires at least two classes (positive and negative)")
        # External-review fix (Codex GPT-5 + DeepSeek v4, 2026-05-08):
        # Old: cv = min(3, len(papers) // 2 or 2)
        # With 3 papers: 3//2 = 1, `1 or 2` → 1 (truthy short-circuit), min(3, 1) = 1.
        # CalibratedClassifierCV rejects cv=1 (k-fold needs >=2 splits).
        # Also need each class to have >= cv samples — use min class count as ceiling.
        positive = sum(1 for p in papers if p.label == 1)
        negative = len(papers) - positive
        min_class = min(positive, negative)
        cv = max(2, min(3, min_class))
        if min_class < 2:
            raise ValueError(
                f"Each class needs >=2 samples for CV calibration (got pos={positive}, neg={negative})"
            )
        self._vectorizer = TfidfVectorizer(
            max_features=self._max_features,
            ngram_range=(1, 2),
            stop_words="english",
        )
        X = self._vectorizer.fit_transform([p.abstract for p in papers])
        y = np.array([p.label for p in papers])
        base = LinearSVC()
        self._model = CalibratedClassifierCV(base, cv=cv)
        self._model.fit(X, y)

    def score(self, abstract: str) -> float:
        if self._vectorizer is None or self._model is None:
            raise RuntimeError("Scorer not trained. Call train() first.")
        X = self._vectorizer.transform([abstract])
        proba = self._model.predict_proba(X)[0]
        # Return P(label=1)
        idx = list(self._model.classes_).index(1)
        return float(proba[idx])
