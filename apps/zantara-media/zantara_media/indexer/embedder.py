"""OpenAI text-embedding-3-small embedder with disk cache for GARUDA indexer."""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

import openai  # openai>=1.40 AsyncOpenAI

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMS = 1536
BATCH_SIZE = 100
CACHE_DIR = Path(os.getenv("EMBED_CACHE_DIR", "/tmp/garuda_embed_cache"))


class Embedder:
    def __init__(self) -> None:
        self._client: Optional[openai.AsyncOpenAI] = None

    def _get_client(self) -> openai.AsyncOpenAI:
        """Lazy-init persistent async client (CLAUDE.md §10 rule: no new client in loops)."""
        if self._client is None:
            api_key = os.environ["OPENAI_API_KEY"]  # raises clearly if missing
            self._client = openai.AsyncOpenAI(api_key=api_key)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def _cache_path(self, key: str) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return CACHE_DIR / f"{key}.json"

    def _load_cache(self, text: str) -> Optional[list[float]]:
        path = self._cache_path(self._cache_key(text))
        if path.exists():
            return json.loads(path.read_text())
        return None

    def _save_cache(self, text: str, vector: list[float]) -> None:
        path = self._cache_path(self._cache_key(text))
        path.write_text(json.dumps(vector))

    async def embed_text(self, text: str) -> list[float]:
        """Embed single text. Uses disk cache."""
        # Truncate to max 8000 chars to stay within token limits
        text = text[:8000]
        cached = self._load_cache(text)
        if cached:
            return cached

        client = self._get_client()
        response = await client.embeddings.create(
            input=[text],
            model=EMBED_MODEL,
        )
        vector: list[float] = response.data[0].embedding
        self._save_cache(text, vector)
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed up to BATCH_SIZE texts in one API call."""
        # Truncate each
        texts = [t[:8000] for t in texts]

        results: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            # Check cache for each
            vectors: list[tuple[int, list[float]]] = []
            uncached_indices: list[int] = []
            uncached_texts: list[str] = []

            for j, text in enumerate(batch):
                cached = self._load_cache(text)
                if cached:
                    vectors.append((j, cached))
                else:
                    uncached_indices.append(j)
                    uncached_texts.append(text)

            if uncached_texts:
                client = self._get_client()
                response = await client.embeddings.create(
                    input=uncached_texts,
                    model=EMBED_MODEL,
                )
                for k, embedding_obj in enumerate(response.data):
                    idx = uncached_indices[k]
                    vector = embedding_obj.embedding
                    self._save_cache(uncached_texts[k], vector)
                    vectors.append((idx, vector))

            # Sort by original index and collect
            vectors.sort(key=lambda x: x[0])
            results.extend(v for _, v in vectors)

        return results
