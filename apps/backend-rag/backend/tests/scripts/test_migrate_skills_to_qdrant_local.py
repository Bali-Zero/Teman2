"""Tests for migrate_skills_to_qdrant_local.

R10 forensic-informed: skill/reflection/insight rows are LIVE in
apps/mata-garuda/data/knowledge.db (304 total as of 2026-05-06). This
script mirrors them to a local Qdrant collection. SQLite stays primary;
Qdrant is read-mostly semantic mirror. No P1 dead-code retire.
"""

from __future__ import annotations

import argparse
import importlib
import sqlite3 as _sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

# ---------------------------------------------------------------------------
# Smoke: module imports + constants
# ---------------------------------------------------------------------------


def test_module_importable() -> None:
    """Smoke: the script module imports without error and exposes the API."""
    module = importlib.import_module(
        "backend.scripts.migrate_skills_to_qdrant_local",
    )
    assert hasattr(module, "main"), "expected `main` entry point"
    assert hasattr(module, "COLLECTION_NAME"), "expected COLLECTION_NAME"
    assert module.COLLECTION_NAME == "bali_zero_skills_local"
    assert hasattr(module, "VECTOR_SIZE")
    assert module.VECTOR_SIZE == 1536, "embedding dim FROZEN per CLAUDE.md §6"
    assert module.EMBED_MODEL == "text-embedding-3-small"
    assert set(module.TARGET_TYPES) == {"skill", "reflection", "insight"}


# ---------------------------------------------------------------------------
# SQLite reader + payload mapping
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_kb(tmp_path: Path) -> Path:
    """Build a tiny SQLite KB with schema-compatible rows for 3 types + noise."""
    db_path = tmp_path / "knowledge.db"
    conn = _sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now')),
            accessed_count INTEGER DEFAULT 0,
            last_accessed TEXT
        );
        """,
    )
    rows = [
        ("Regulation Watcher", "skill", "harvest-and-publish: scrape ...",
         "reflection_RegW", 0.8, "2026-04-14 06:53:33", 3),
        ("Regulation Watcher", "reflection",
         '{"what_worked": "scraped 10 regs"}',
         "reflection_RegW", 0.5, "2026-04-14 06:53:33", 1),
        ("Regulation Watcher", "insight",
         "Stream has 351 items; consider dedup.",
         "reflection_RegW", 0.7, "2026-04-14 06:53:33", 0),
        # noise — must be excluded
        ("Bus Worker", "harvested_item", "raw http body", None, 0.5,
         "2026-04-14 06:53:33", 0),
        ("Bus Worker", "scored_item", "scored body", None, 0.5,
         "2026-04-14 06:53:33", 0),
    ]
    conn.executemany(
        "INSERT INTO knowledge (agent, type, content, source, confidence, "
        "created_at, accessed_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


def test_load_rows_filters_to_three_types(fixture_kb: Path) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import (
        TARGET_TYPES,
        load_rows,
    )
    rows = load_rows(fixture_kb)
    assert len(rows) == 3, "must load exactly skill/reflection/insight"
    assert {r.type for r in rows} == set(TARGET_TYPES)


def test_load_rows_respects_limit(fixture_kb: Path) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import load_rows
    rows = load_rows(fixture_kb, limit=2)
    assert len(rows) == 2


def test_load_rows_raises_on_missing_db(tmp_path: Path) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import load_rows
    missing = tmp_path / "nope.db"
    with pytest.raises(FileNotFoundError):
        load_rows(missing)


def test_skill_id_format(fixture_kb: Path) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import (
        load_rows,
        skill_id_for,
    )
    rows = load_rows(fixture_kb)
    skill = next(r for r in rows if r.type == "skill")
    assert skill_id_for(skill) == f"skill_{skill.row_id}"


def test_point_uuid_is_deterministic(fixture_kb: Path) -> None:
    """uuid5 with fixed namespace ⇒ same skill_id always maps to same point_id."""
    from backend.scripts.migrate_skills_to_qdrant_local import (
        load_rows,
        point_uuid_for,
    )
    rows = load_rows(fixture_kb)
    ids_run1 = [point_uuid_for(r) for r in rows]
    ids_run2 = [point_uuid_for(r) for r in rows]
    assert ids_run1 == ids_run2, "uuid5 must be deterministic"
    assert len(set(ids_run1)) == len(ids_run1), "no collisions across types/ids"


def test_payload_for_row_is_flat(fixture_kb: Path) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import (
        load_rows,
        payload_for,
    )
    rows = load_rows(fixture_kb)
    payload = payload_for(rows[0])
    # Golden Rule 11: payload flat, no nested dicts/lists-of-dicts
    for value in payload.values():
        assert not isinstance(value, dict), (
            f"nested dict in payload: {value!r}"
        )
    expected_keys = {
        "skill_id", "type", "content", "source_cell", "source",
        "confidence", "scope", "valid_from", "uses_count",
        "embedding_dim_check",
    }
    assert expected_keys <= set(payload), (
        f"missing keys: {expected_keys - set(payload)}"
    )
    assert payload["embedding_dim_check"] == 1536
    assert payload["scope"] == payload["type"]
    assert payload["source_cell"] == rows[0].agent
    assert payload["valid_from"] == rows[0].created_at
    assert payload["uses_count"] == rows[0].accessed_count


# ---------------------------------------------------------------------------
# Qdrant HTTP helpers
# ---------------------------------------------------------------------------


async def test_bootstrap_creates_collection_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import (
        COLLECTION_NAME,
        bootstrap_collection,
    )

    calls: list[tuple[str, str]] = []

    class FakeResp:
        def __init__(self, status: int, body: dict | None = None) -> None:
            self.status_code = status
            self._body = body or {}
            self.text = ""

        def json(self) -> dict:
            return self._body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "boom", request=None, response=None,  # type: ignore[arg-type]
                )

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        calls.append(("GET", url))
        return FakeResp(404)

    async def fake_put(self: object, url: str, **_: object) -> FakeResp:
        calls.append(("PUT", url))
        return FakeResp(200, {"result": True})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "put", fake_put)

    created = await bootstrap_collection("http://test:6333")
    assert created is True
    assert ("GET", f"http://test:6333/collections/{COLLECTION_NAME}") in calls
    put_url = next(url for verb, url in calls if verb == "PUT")
    assert put_url.endswith(f"/collections/{COLLECTION_NAME}")


def _existing_collection_body(size: int = 1536, distance: str = "Cosine") -> dict:
    """Mimic Qdrant's GET /collections/{name} response shape."""
    return {
        "result": {
            "status": "green",
            "config": {
                "params": {
                    "vectors": {"size": size, "distance": distance},
                },
            },
        },
    }


async def test_bootstrap_noop_when_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import bootstrap_collection

    class FakeResp:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return _existing_collection_body()

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp()

    put_called = False

    async def fake_put(self: object, url: str, **_: object) -> FakeResp:
        nonlocal put_called
        put_called = True
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "put", fake_put)

    created = await bootstrap_collection("http://test:6333")
    assert created is False
    assert put_called is False, "must NOT recreate existing collection"


async def test_bootstrap_rejects_dim_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per Codex review 2026-05-06 P2: existing collection with wrong dim must
    raise BEFORE we burn embedding calls."""
    from backend.scripts.migrate_skills_to_qdrant_local import bootstrap_collection

    class FakeResp:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return _existing_collection_body(size=768)  # WRONG

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(RuntimeError, match=r"dim=768.*FROZEN"):
        await bootstrap_collection("http://test:6333")


async def test_bootstrap_rejects_distance_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing collection with wrong distance metric must raise."""
    from backend.scripts.migrate_skills_to_qdrant_local import bootstrap_collection

    class FakeResp:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return _existing_collection_body(distance="Euclid")  # WRONG

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    with pytest.raises(RuntimeError, match=r"distance='Euclid'"):
        await bootstrap_collection("http://test:6333")


async def test_bootstrap_handles_toctou_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET says 404, PUT races with sibling and gets 4xx 'already exists'.

    Per Gemini review 2026-05-06: TOCTOU between GET-404 check and PUT.
    Treat a post-PUT 4xx with 'already exists' body as success-by-sibling.
    """
    from backend.scripts.migrate_skills_to_qdrant_local import bootstrap_collection

    class FakeResp:
        def __init__(self, status: int, text: str = "") -> None:
            self.status_code = status
            self.text = text

        def json(self) -> dict:
            return {}

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp(404)

    async def fake_put(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp(
            400,
            text='{"status":{"error":"Wrong input: Collection bali_zero_skills_local already exists!"}}',
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "put", fake_put)

    # Should NOT raise — sibling-created counts as success
    created = await bootstrap_collection("http://test:6333")
    assert created is False


async def test_bootstrap_raises_on_genuine_4xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 4xx that is NOT 'already exists' (e.g. malformed body) must raise."""
    from backend.scripts.migrate_skills_to_qdrant_local import bootstrap_collection

    class FakeResp:
        def __init__(self, status: int, text: str = "") -> None:
            self.status_code = status
            self.text = text

        def json(self) -> dict:
            return {}

    async def fake_get(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp(404)

    async def fake_put(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp(400, text='{"error": "invalid vector size 9999"}')

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "put", fake_put)

    with pytest.raises(RuntimeError, match="create collection failed"):
        await bootstrap_collection("http://test:6333")


async def test_count_points_in_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import count_points

    class FakeResp:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {"result": {"count": 304}}

        def raise_for_status(self) -> None:  # noqa: D401
            return None

    async def fake_post(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    n = await count_points("http://test:6333")
    assert n == 304


async def test_count_points_returns_zero_when_collection_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.scripts.migrate_skills_to_qdrant_local import count_points

    class FakeResp:
        status_code = 404
        text = "not found"

        def json(self) -> dict:
            return {}

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "404", request=None, response=None,  # type: ignore[arg-type]
            )

    async def fake_post(self: object, url: str, **_: object) -> FakeResp:
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await count_points("http://test:6333") == 0


# ---------------------------------------------------------------------------
# Anti-Anthropic-paid invariant (CLAUDE.md global hard rule)
# ---------------------------------------------------------------------------


def test_anthropic_sdk_never_imported() -> None:
    """Hard rule per CLAUDE.md global: never import paid Anthropic SDK."""
    # parents[2] = backend/, then backend/scripts/<file>
    src = Path(__file__).resolve().parents[2] / "scripts" / (
        "migrate_skills_to_qdrant_local.py"
    )
    assert src.exists(), f"script missing at {src}"
    text = src.read_text()
    assert "import anthropic" not in text
    assert "from anthropic" not in text
    assert "ANTHROPIC_API_KEY" not in text


# ---------------------------------------------------------------------------
# End-to-end _run flow + idempotency
# ---------------------------------------------------------------------------


async def test_run_dry_run_does_not_call_qdrant_or_openai(
    fixture_kb: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--dry-run must NOT mutate qdrant nor call OpenAI."""
    import backend.scripts.migrate_skills_to_qdrant_local as mod

    upserts = 0

    async def boom_embed(self: object, texts: list[str]) -> list[list[float]]:
        raise AssertionError("dry-run must not embed")

    async def boom_upsert(*_: object, **__: object) -> None:
        nonlocal upserts
        upserts += 1
        raise AssertionError("dry-run must not upsert")

    async def boom_bootstrap(*_: object, **__: object) -> bool:
        raise AssertionError("dry-run must not bootstrap")

    monkeypatch.setattr(mod.OpenAIEmbedder, "embed", boom_embed)
    monkeypatch.setattr(mod, "upsert_points", boom_upsert)
    monkeypatch.setattr(mod, "bootstrap_collection", boom_bootstrap)
    monkeypatch.setattr(mod, "count_points", AsyncMock(return_value=0))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-dry")

    args = argparse.Namespace(
        bootstrap_only=False, dry_run=True, apply=False,
        qdrant_url="http://test:6333", sqlite_path=fixture_kb, limit=None,
    )
    rc = await mod._run(args)
    assert rc == 0
    assert upserts == 0


async def test_run_apply_idempotent_via_uuidv5(
    fixture_kb: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-running --apply must produce stable point ids (no duplicates)."""
    import backend.scripts.migrate_skills_to_qdrant_local as mod

    rows = mod.load_rows(fixture_kb)
    expected_ids = sorted(mod.point_uuid_for(r) for r in rows)
    assert len(expected_ids) == len(set(expected_ids)), "uuidv5 collision"

    captured: list[list[str]] = []

    async def fake_embed(self: object, texts: list[str]) -> list[list[float]]:
        return [[0.0] * mod.VECTOR_SIZE for _ in texts]

    async def fake_upsert(url: str, points: list[dict[str, object]]) -> None:
        captured.append([str(p["id"]) for p in points])

    monkeypatch.setattr(mod.OpenAIEmbedder, "embed", fake_embed)
    monkeypatch.setattr(mod, "upsert_points", fake_upsert)
    monkeypatch.setattr(
        mod, "bootstrap_collection", AsyncMock(return_value=True),
    )
    monkeypatch.setattr(mod, "count_points", AsyncMock(return_value=0))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    args = argparse.Namespace(
        bootstrap_only=False, dry_run=False, apply=True,
        qdrant_url="http://test:6333", sqlite_path=fixture_kb, limit=None,
    )
    rc1 = await mod._run(args)
    midpoint = len(captured)
    rc2 = await mod._run(args)
    assert rc1 == 0 == rc2

    flat_run1 = sorted(pid for batch in captured[:midpoint] for pid in batch)
    flat_run2 = sorted(pid for batch in captured[midpoint:] for pid in batch)
    assert flat_run1 == flat_run2 == expected_ids, (
        "id sets must be identical between runs (idempotency)"
    )


async def test_run_bootstrap_only(
    fixture_kb: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--bootstrap-only creates collection, doesn't embed/upsert."""
    import backend.scripts.migrate_skills_to_qdrant_local as mod

    bootstrap_called = False

    async def fake_bootstrap(url: str) -> bool:
        nonlocal bootstrap_called
        bootstrap_called = True
        return True

    async def boom_embed(self: object, texts: list[str]) -> list[list[float]]:
        raise AssertionError("bootstrap-only must not embed")

    async def boom_upsert(*_: object, **__: object) -> None:
        raise AssertionError("bootstrap-only must not upsert")

    monkeypatch.setattr(mod, "bootstrap_collection", fake_bootstrap)
    monkeypatch.setattr(mod.OpenAIEmbedder, "embed", boom_embed)
    monkeypatch.setattr(mod, "upsert_points", boom_upsert)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    args = argparse.Namespace(
        bootstrap_only=True, dry_run=False, apply=False,
        qdrant_url="http://test:6333", sqlite_path=fixture_kb, limit=None,
    )
    rc = await mod._run(args)
    assert rc == 0
    assert bootstrap_called is True
