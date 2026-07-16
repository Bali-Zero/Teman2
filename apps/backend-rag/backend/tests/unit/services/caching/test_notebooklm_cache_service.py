"""P7 (SPEC v2 D3): provenance-enforcing FAQ cache.

Contract under test (backend/services/caching/notebooklm_cache_service.py):
- set() requires metadata keys {source_ref, source_date, domain, confidence_class,
  source_priority: int}; writes without them raise ValueError. This is the
  guardrail behind the "NO verbatim serving from any similarity-based layer;
  verbatim only from exact-match FAQ cache with pre-vetted provenance" invariant.
- get() validates the cached JSON shape (answer str + metadata dict) — malformed
  entries are treated as a miss AND self-heal (delete the corrupt key).
- Collision policy on set(): an existing entry with a HIGHER source_priority is
  never silently overwritten by a lower-priority write.
- The notebook_id-scoped path (legacy prewarm) keeps working; the unscoped path
  (notebook_id="") is what orchestrator_core.check_faq_cache() calls, and it must
  see harvester-written entries.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend.services.caching.notebooklm_cache_service import NotebookLMCacheService

VALID_METADATA: dict[str, Any] = {
    "source_ref": "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1",
    "source_date": "2026-07-15",
    "domain": "visa",
    "confidence_class": "BERSYARAT",
    "source_priority": 80,
}


class FakeAsyncRedis:
    """Minimal in-memory stand-in for the subset of redis.asyncio used here."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    async def scan_iter(self, match: str | None = None):
        prefix = (match or "*").rstrip("*")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


@pytest.fixture
def cache() -> NotebookLMCacheService:
    svc = NotebookLMCacheService()
    svc.redis_client = FakeAsyncRedis()
    return svc


# ── set() provenance enforcement ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_raises_value_error_when_metadata_missing_entirely(
    cache: NotebookLMCacheService,
) -> None:
    with pytest.raises(ValueError, match="source_ref"):
        await cache.set("What is PPh Badan?", "answer text")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_key",
    ["source_ref", "source_date", "domain", "confidence_class", "source_priority"],
)
async def test_set_raises_value_error_when_one_required_key_missing(
    cache: NotebookLMCacheService,
    missing_key: str,
) -> None:
    metadata = {k: v for k, v in VALID_METADATA.items() if k != missing_key}
    with pytest.raises(ValueError):
        await cache.set("question", "answer", metadata=metadata)


@pytest.mark.asyncio
async def test_set_raises_value_error_when_source_priority_not_int(
    cache: NotebookLMCacheService,
) -> None:
    metadata = {**VALID_METADATA, "source_priority": "high"}
    with pytest.raises(ValueError, match="source_priority"):
        await cache.set("question", "answer", metadata=metadata)


@pytest.mark.asyncio
async def test_set_raises_value_error_when_source_priority_is_bool(
    cache: NotebookLMCacheService,
) -> None:
    # bool is a subclass of int in Python — must be explicitly rejected.
    metadata = {**VALID_METADATA, "source_priority": True}
    with pytest.raises(ValueError, match="source_priority"):
        await cache.set("question", "answer", metadata=metadata)


@pytest.mark.asyncio
async def test_set_succeeds_with_full_provenance_metadata(
    cache: NotebookLMCacheService,
) -> None:
    ok = await cache.set("What is PPh Badan?", "PPh Badan is...", metadata=VALID_METADATA)
    assert ok is True

    got = await cache.get("What is PPh Badan?")
    assert got is not None
    assert got["answer"] == "PPh Badan is..."
    assert got["metadata"]["source_priority"] == 80


@pytest.mark.asyncio
async def test_set_provenance_check_happens_even_without_redis() -> None:
    """The contract violation (missing provenance) must surface regardless of
    infra availability — it's a caller bug, not a degraded-mode condition."""
    svc = NotebookLMCacheService()
    svc.redis_client = None
    with pytest.raises(ValueError):
        await svc.set("question", "answer")


# ── set() collision policy ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_refuses_overwrite_when_existing_entry_has_higher_priority(
    cache: NotebookLMCacheService,
) -> None:
    high_priority = {**VALID_METADATA, "source_priority": 90}
    low_priority = {**VALID_METADATA, "source_priority": 50}

    await cache.set("question", "high-priority answer", metadata=high_priority)
    ok = await cache.set("question", "low-priority answer", metadata=low_priority)

    assert ok is False
    got = await cache.get("question")
    assert got["answer"] == "high-priority answer"


@pytest.mark.asyncio
async def test_set_allows_overwrite_when_new_priority_is_higher_or_equal(
    cache: NotebookLMCacheService,
) -> None:
    low_priority = {**VALID_METADATA, "source_priority": 50}
    high_priority = {**VALID_METADATA, "source_priority": 90}

    await cache.set("question", "low-priority answer", metadata=low_priority)
    ok = await cache.set("question", "high-priority answer", metadata=high_priority)

    assert ok is True
    got = await cache.get("question")
    assert got["answer"] == "high-priority answer"


@pytest.mark.asyncio
async def test_set_allows_overwrite_when_existing_entry_is_malformed(
    cache: NotebookLMCacheService,
) -> None:
    key = cache.cache_prefix + cache._hash_question("question", "")
    cache.redis_client.store[key] = "not valid json {{{"

    ok = await cache.set("question", "fresh answer", metadata=VALID_METADATA)

    assert ok is True
    got = await cache.get("question")
    assert got["answer"] == "fresh answer"


# ── get() shape validation + self-heal ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_none_and_deletes_key_on_corrupt_json(
    cache: NotebookLMCacheService,
) -> None:
    key = cache.cache_prefix + cache._hash_question("question", "")
    cache.redis_client.store[key] = "{not json"

    result = await cache.get("question")

    assert result is None
    assert key not in cache.redis_client.store


@pytest.mark.asyncio
async def test_get_returns_none_and_deletes_key_on_missing_answer_field(
    cache: NotebookLMCacheService,
) -> None:
    key = cache.cache_prefix + cache._hash_question("question", "")
    cache.redis_client.store[key] = json.dumps({"metadata": {}})

    result = await cache.get("question")

    assert result is None
    assert key not in cache.redis_client.store


@pytest.mark.asyncio
async def test_get_returns_none_and_deletes_key_when_answer_not_a_string(
    cache: NotebookLMCacheService,
) -> None:
    key = cache.cache_prefix + cache._hash_question("question", "")
    cache.redis_client.store[key] = json.dumps({"answer": 12345, "metadata": {}})

    result = await cache.get("question")

    assert result is None
    assert key not in cache.redis_client.store


@pytest.mark.asyncio
async def test_get_returns_none_and_deletes_key_when_metadata_not_a_dict(
    cache: NotebookLMCacheService,
) -> None:
    key = cache.cache_prefix + cache._hash_question("question", "")
    cache.redis_client.store[key] = json.dumps({"answer": "ok", "metadata": "not-a-dict"})

    result = await cache.get("question")

    assert result is None
    assert key not in cache.redis_client.store


@pytest.mark.asyncio
async def test_get_returns_valid_entry_unchanged(cache: NotebookLMCacheService) -> None:
    await cache.set("question", "answer", metadata=VALID_METADATA)

    result = await cache.get("question")

    assert result["answer"] == "answer"
    assert result["metadata"]["domain"] == "visa"


# ── notebook_id scoping (harvester unscoped vs legacy prewarm scoped) ───────


@pytest.mark.asyncio
async def test_unscoped_get_finds_harvester_written_unscoped_entry(
    cache: NotebookLMCacheService,
) -> None:
    """orchestrator_core.check_faq_cache() calls faq_cache.get(query) with no
    notebook_id — harvester-written entries (also unscoped) must be visible."""
    await cache.set("What is KBLI 68112?", "harvester answer", metadata=VALID_METADATA)

    result = await cache.get("What is KBLI 68112?")

    assert result is not None
    assert result["answer"] == "harvester answer"


@pytest.mark.asyncio
async def test_notebook_scoped_and_unscoped_entries_do_not_collide(
    cache: NotebookLMCacheService,
) -> None:
    scoped_metadata = {**VALID_METADATA, "domain": "immigration"}
    await cache.set(
        "What is KBLI 68112?",
        "scoped legacy answer",
        metadata=scoped_metadata,
        notebook_id="84375bc3-12d0-4405-a774-9b89189d8c39",
    )
    await cache.set("What is KBLI 68112?", "harvester answer", metadata=VALID_METADATA)

    scoped = await cache.get(
        "What is KBLI 68112?",
        notebook_id="84375bc3-12d0-4405-a774-9b89189d8c39",
    )
    unscoped = await cache.get("What is KBLI 68112?")

    assert scoped["answer"] == "scoped legacy answer"
    assert unscoped["answer"] == "harvester answer"
