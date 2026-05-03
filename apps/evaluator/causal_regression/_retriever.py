"""Deterministic BM25-ish retriever that works over plain text files.

The replay engine needs a retriever that (a) has zero external dependencies so
we can run in CI without Qdrant or sentence-transformers, and (b) is strictly
deterministic across runs so the causal report is byte-identical. This module
implements a tiny BM25 over whitespace-tokenized lowercased documents with
punctuation stripping. It is intentionally worse than production; its only
job is to produce **consistent** retrieval decisions that the diff engine can
compare between commits.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ._types import RetrievedChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class _Doc:
    path: str
    tokens: list[str]
    token_freq: dict[str, int]
    length: int
    text: str


class MockRetriever:
    """Simple BM25 retriever over an in-memory dict of {path: text}.

    BM25 parameters are fixed (k1=1.5, b=0.75) so scoring is reproducible. Ties
    in score are broken by lexicographically-smaller doc path, ensuring that
    determinism holds even when multiple docs match identically.
    """

    k1: float = 1.5
    b: float = 0.75

    def __init__(self, docs: dict[str, str]) -> None:
        self._docs: list[_Doc] = []
        for path, text in sorted(docs.items()):  # sorted for determinism
            tokens = _tokenize(text)
            freq: dict[str, int] = {}
            for t in tokens:
                freq[t] = freq.get(t, 0) + 1
            self._docs.append(
                _Doc(
                    path=path,
                    tokens=tokens,
                    token_freq=freq,
                    length=len(tokens),
                    text=text,
                )
            )
        self._avgdl = (
            sum(d.length for d in self._docs) / len(self._docs) if self._docs else 0.0
        )
        # Document frequency: number of docs containing each term.
        df: dict[str, int] = {}
        for d in self._docs:
            for term in d.token_freq.keys():
                df[term] = df.get(term, 0) + 1
        self._df = df
        self._n = len(self._docs)

    def _idf(self, term: str) -> float:
        n_qi = self._df.get(term, 0)
        if n_qi == 0:
            return 0.0
        # BM25+ style idf, floor at 0 to avoid negatives on common terms.
        val = math.log((self._n - n_qi + 0.5) / (n_qi + 0.5) + 1.0)
        return max(val, 0.0)

    def _score(self, q_terms: list[str], d: _Doc) -> float:
        if d.length == 0 or not q_terms:
            return 0.0
        score = 0.0
        for term in q_terms:
            if term not in d.token_freq:
                continue
            idf = self._idf(term)
            if idf == 0.0:
                continue
            f = d.token_freq[term]
            denom = f + self.k1 * (1 - self.b + self.b * (d.length / (self._avgdl or 1.0)))
            numer = f * (self.k1 + 1)
            score += idf * (numer / denom)
        return score

    def _snippet(self, d: _Doc, q_terms: list[str], window: int = 160) -> str:
        """Return a short snippet of `d.text` centered on the first matching token."""
        text = d.text
        if not text:
            return ""
        low = text.lower()
        first_pos = -1
        for term in q_terms:
            idx = low.find(term)
            if idx != -1 and (first_pos == -1 or idx < first_pos):
                first_pos = idx
        if first_pos == -1:
            return text[:window].replace("\n", " ").strip()
        start = max(0, first_pos - window // 2)
        end = min(len(text), start + window)
        return text[start:end].replace("\n", " ").strip()

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        q_terms = _tokenize(query)
        scored: list[tuple[float, str, _Doc]] = []
        for d in self._docs:
            s = self._score(q_terms, d)
            if s > 0:
                scored.append((s, d.path, d))
        # Sort: highest score first, ties broken by path ascending (stable).
        scored.sort(key=lambda t: (-t[0], t[1]))
        out: list[RetrievedChunk] = []
        for rank, (score, _path, d) in enumerate(scored[:top_k], start=1):
            out.append(
                RetrievedChunk(
                    doc_path=d.path,
                    score=score,
                    rank=rank,
                    snippet=self._snippet(d, q_terms),
                )
            )
        return out
