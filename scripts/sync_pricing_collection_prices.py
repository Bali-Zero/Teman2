#!/usr/bin/env python3
# ruff: noqa: T201
"""Sync the PRICE of the LIVE ``bali_zero_pricing_hybrid`` Qdrant collection
from the canonical price catalog, payload-only.

WHY: nothing re-syncs this collection from
``apps/backend-rag/backend/data/bali_zero_official_prices_2026.json``. A catalog
price change (e.g. PT PMA 20M -> 25M, owner ruling 2026-10-12) therefore never
reaches ``backend/app/modules/knowledge/service.py``'s pricing queries until the
points are patched. ``scripts/patch_pricing_contact_block.py`` is the sibling
patcher (contact block); this one handles price drift.

What it does, per non-internal catalog row (rows marked ``"internal": true`` are
skipped during sync so retired/internal-only entries are never upserted into the
conversational Qdrant collection):
  - matches a point by payload ``name`` == catalog ``name``;
  - expected price = catalog ``price``, or, for tier rows with an empty price,
    ``"<lo> - <hi> IDR"`` built from ``tier_range`` (the shape the points use);
  - if the payload ``price`` differs, plans a set-payload of ``price``,
    ``text`` (the old price string replaced by the new one, ONLY when it occurs
    exactly once in the text) and ``last_updated`` (today, ISO).

By default it NEVER re-embeds vectors, deletes points or creates points. Catalog
rows with no point and points with no catalog row are REPORTED, never acted on.
With ``--create-missing`` every public catalog row with no point is planned as a
CREATE, built like ``apps/backend-rag/scripts/prepare_payloads.py`` built the live
points (same payload keys, same text template, id = md5("<category>:<name>")) and
embedded with the backend's own ``EmbeddingsGenerator`` on the collection's model;
``--create-missing --apply`` writes those creates ONLY (pending price updates are
reported, never applied, and it refuses ``--purge-internal``).
Without ``--purge-internal``, Qdrant points matching catalog rows marked
``"internal": true`` are reported (``INTERNAL (report only; pass --purge-internal
to delete) id=<id> <name!r>``) and never upserted or counted in ``no_catalog_row``.
When ``--purge-internal`` is passed, those points are listed for deletion (dry-run
by default; ``--purge-internal --apply`` deletes those exact point IDs and also
applies pending price updates in the same run — use ``--only`` to narrow).
Any refusal (old price not found exactly once, ambiguous name) exits non-zero and
``--apply`` then applies NOTHING.
``--delete-orphans`` is a delete-only mode: it plans the deletion of every point whose
payload ``name`` matches no catalog row (matched by ``row.get("name", key)`` over public
AND internal rows, so a point of either kind is protected regardless of price). A point
with no usable name, or a catalog with no rows, is a refusal. ``--apply`` needs
``--expect-orphans N``, the count the reviewed dry run printed; any other count applies
nothing. It writes deletes only and refuses ``--create-missing``, ``--purge-internal``
and ``--only``.

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --apply
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --purge-internal
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --purge-internal --apply
    # Note: --purge-internal --apply also applies pending price updates in the same run (use --only to narrow)
    ... --catalog PATH     # default: the canonical JSON in the repo; "-" reads stdin
    ... --only "New Company (PT PMA)"   # scope to one catalog name (repeatable)
    ... --create-missing [--apply]       # plan [and write] points for rows that have none
    ... --delete-orphans                 # dry run: list points with no catalog row
    ... --delete-orphans --expect-orphans N --apply   # delete exactly those N points
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import importlib.util
import json
import logging
import os
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COLLECTION_NAME = "bali_zero_pricing_hybrid"
# `__file__` is undefined when the script is piped to `python3 -` (remote dry-run).
_HERE = (
    Path(__file__).resolve()
    if "__file__" in globals()
    else Path.cwd() / "scripts" / "x.py"
)
DEFAULT_CATALOG = (
    _HERE.parents[1]
    / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
)
BACKEND_RAG_ROOT = _HERE.parents[1] / "apps" / "backend-rag"
PREPARE_PAYLOADS = BACKEND_RAG_ROOT / "scripts" / "prepare_payloads.py"
SCROLL_BATCH_SIZE = 100
UPSERT_BATCH_SIZE = 32
# The model that produced every vector in the collection (backend-rag CLAUDE.md §9: FROZEN).
EMBED_MODEL = "text-embedding-3-small"
DENSE_VECTOR_NAME = "dense"
DENSE_VECTOR_SIZE = 1536

Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]


def _iter_service_rows(
    services: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield ``(category_key, key, row)`` for public (non-internal) rows only.

    Rows marked ``"internal": true`` are skipped so internal-only catalogue
    rows are never synced/upserted into ``bali_zero_pricing_hybrid``.
    """
    for category, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category == "tax_accounting":
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for key, row in sub_block.items():
                    if isinstance(row, dict) and row.get("internal") is not True:
                        yield f"{category}.{sub_block_name}", key, row
            continue
        for key, row in category_payload.items():
            if isinstance(row, dict) and row.get("internal") is not True:
                yield category, key, row


def _iter_internal_service_rows(
    services: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield ``(category_key, key, row)`` for rows marked ``"internal": true``."""
    for category, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category == "tax_accounting":
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for key, row in sub_block.items():
                    if isinstance(row, dict) and row.get("internal") is True:
                        yield f"{category}.{sub_block_name}", key, row
            continue
        for key, row in category_payload.items():
            if isinstance(row, dict) and row.get("internal") is True:
                yield category, key, row


def internal_catalog_names(catalog: dict[str, Any]) -> frozenset[str]:
    """Return the set of catalog ``name`` values for rows marked ``"internal": true``."""
    return frozenset(
        row.get("name", key)
        for _cat, key, row in _iter_internal_service_rows(catalog.get("services", {}))
    )


def catalog_names(catalog: dict[str, Any]) -> frozenset[str]:
    """Every catalog row name, public AND internal, whatever its price.

    Same name rule as the price sync and the create path (``row.get("name", key)``).
    Unlike ``catalog_prices`` it ignores price and duplicates: a row with no price or a
    repeated name is still a catalog name.
    """
    services = catalog.get("services", {})
    return frozenset(
        row.get("name", key)
        for _cat, key, row in (
            *_iter_service_rows(services),
            *_iter_internal_service_rows(services),
        )
    )


def expected_price(row: dict[str, Any]) -> str | None:
    """The price string a point should carry for this catalog row."""
    price = row.get("price")
    if isinstance(price, str) and price.strip():
        return price.strip()
    tier = row.get("tier_range")
    if (
        isinstance(tier, list)
        and len(tier) == 2
        and all(isinstance(t, str) for t in tier)
    ):
        lo, hi = tier
        return f"{lo.removesuffix(' IDR')} - {hi}"
    return None


def catalog_prices(catalog: dict[str, Any]) -> dict[str, str]:
    """name -> expected price for non-internal rows. A duplicated name is dropped (ambiguous)."""
    out: dict[str, str] = {}
    dup: set[str] = set()
    for _cat, key, row in _iter_service_rows(catalog["services"]):
        name = row.get("name", key)
        price = expected_price(row)
        if price is None:
            continue
        if name in out:
            dup.add(name)
        out[name] = price
    for name in dup:
        del out[name]
    return out


@dataclass
class Plan:
    updates: list[dict[str, Any]] = field(
        default_factory=list
    )  # id,name,old,new,payload
    deletes: list[dict[str, Any]] = field(
        default_factory=list
    )  # id,name (populated only when purge_internal=True)
    internal_points: list[dict[str, Any]] = field(
        default_factory=list
    )  # id,name (populated when purge_internal=False for internal catalog rows)
    refusals: list[str] = field(default_factory=list)
    creates: list[dict[str, Any]] = field(
        default_factory=list
    )  # id,name,payload (populated only by --create-missing)
    no_point: list[str] = field(default_factory=list)
    no_catalog_row: list[str] = field(default_factory=list)
    in_sync: int = 0


def build_plan(
    points: list[dict[str, Any]],
    prices: dict[str, str],
    today: str,
    only: frozenset[str] | None = None,
    *,
    internal_names: frozenset[str] = frozenset(),
    purge_internal: bool = False,
) -> Plan:
    """``only`` scopes the plan to those catalog names (everything else is ignored)."""
    prices = {n: v for n, v in prices.items() if n not in internal_names}
    if only:
        prices = {n: v for n, v in prices.items() if n in only}
        internal_names = frozenset(n for n in internal_names if n in only)
        points = [p for p in points if (p.get("payload") or {}).get("name") in only]
    plan = Plan()
    by_name: dict[str, list[dict[str, Any]]] = {}
    for p in points:
        by_name.setdefault((p.get("payload") or {}).get("name", ""), []).append(p)
    for name in prices:
        if name not in by_name:
            plan.no_point.append(name)
    for name, group in by_name.items():
        if name in internal_names:
            for p in group:
                if purge_internal:
                    plan.deletes.append({"id": p["id"], "name": name})
                else:
                    plan.internal_points.append({"id": p["id"], "name": name})
            continue
        if name not in prices:
            plan.no_catalog_row.append(name)
            continue
        new = prices[name]
        for p in group:
            payload = p.get("payload") or {}
            old = payload.get("price")
            if old == new:
                plan.in_sync += 1
                continue
            text = payload.get("text")
            if not isinstance(old, str) or not old or not isinstance(text, str):
                plan.refusals.append(
                    f"{p['id']} {name!r}: payload price/text missing or not a string"
                )
                continue
            if text.count(old) != 1:
                plan.refusals.append(
                    f"{p['id']} {name!r}: old price {old!r} occurs {text.count(old)}x in text "
                    "(need exactly 1)"
                )
                continue
            plan.updates.append(
                {
                    "id": p["id"],
                    "name": name,
                    "old": old,
                    "new": new,
                    "payload": {
                        "price": new,
                        "text": text.replace(old, new),
                        "last_updated": today,
                    },
                }
            )
    return plan


def _load_prepare_payloads() -> Any:
    """The original ingestion module: the text template and the point-id rule live there."""
    spec = importlib.util.spec_from_file_location("prepare_payloads", PREPARE_PAYLOADS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PREPARE_PAYLOADS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_creates(
    points: list[dict[str, Any]],
    catalog: dict[str, Any],
    today: str,
    only: frozenset[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Points to create for public catalog rows that have none, and the refusals.

    Built like ``prepare_payloads.py`` built the live points, with two deliberate
    differences: ``name`` is the row's display name (the key this script matches on),
    and the price is ``expected_price(row)`` so the text carries the payload price
    exactly once and a later price sync can update it. Internal rows, rows that
    already have a point and ids already taken are never created.
    """
    prepare = _load_prepare_payloads()
    services = catalog.get("services", {})
    metadata = catalog.get("metadata") or {}
    contact = catalog.get("contact_info") or metadata.get("contact") or {}
    currency = catalog.get("currency") or metadata.get("currency") or "IDR"
    internal = internal_catalog_names(catalog)
    existing = {(p.get("payload") or {}).get("name") for p in points}
    taken_ids = {p["id"] for p in points}
    rows = list(_iter_service_rows(services))
    seen = Counter(row.get("name", key) for _cat, key, row in rows)
    creates: list[dict[str, Any]] = []
    refusals: list[str] = []
    for category_key, key, row in rows:
        name = row.get("name", key)
        if name in internal or name in existing or (only and name not in only):
            continue
        if seen[name] > 1:
            refusals.append(
                f"create {name!r}: name occurs {seen[name]}x in the catalog"
            )
            continue
        price = expected_price(row)
        if price is None:
            refusals.append(
                f"create {name!r}: catalog row has no price and no tier_range"
            )
            continue
        category = category_key.replace(".", "/")
        text = prepare.generate_semantic_text(
            name, category, {**row, "price": price}, contact
        )
        if text.count(price) != 1:
            refusals.append(
                f"create {name!r}: price {price!r} occurs {text.count(price)}x in text "
                "(need exactly 1)"
            )
            continue
        point_id = prepare.generate_point_id(name, category)
        if point_id in taken_ids:
            refusals.append(f"create {name!r}: point id {point_id} is already taken")
            continue
        taken_ids.add(point_id)
        creates.append(
            {
                "id": point_id,
                "name": name,
                "payload": {
                    "text": text,
                    "name": name,
                    "category": category,
                    "price": price,
                    "duration": row.get("duration") or "",
                    "validity": row.get("validity") or "",
                    "notes": row.get("notes") or "",
                    "source_type": "bali_zero_pricing",
                    "last_updated": today,
                    "currency": currency,
                },
            }
        )
    return creates, refusals


def plan_orphan_deletes(
    points: list[dict[str, Any]], catalog: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Points whose payload name matches no catalog row, and the refusals.

    A point that cannot be named is never deleted, and an empty catalog never turns
    every point into an orphan.
    """
    names = catalog_names(catalog)
    if not names:
        return [], [
            "delete-orphans: the catalog has no rows - refusing to orphan every point"
        ]
    deletes: list[dict[str, Any]] = []
    refusals: list[str] = []
    for p in points:
        name = (p.get("payload") or {}).get("name")
        if not isinstance(name, str) or not name:
            refusals.append(
                f"{p['id']}: payload name missing or not a string - cannot be classified"
            )
            continue
        if name not in names:
            deletes.append({"id": p["id"], "name": name})
    return deletes, refusals


def print_plan(plan: Plan) -> None:
    for c in plan.creates:
        print(f"CREATE id={c['id']} {c['name']!r}: {c['payload']['price']}")
    for u in plan.updates:
        print(f"UPDATE id={u['id']} {u['name']!r}: {u['old']} -> {u['new']}")
    for d in plan.deletes:
        print(f"DELETE id={d['id']} {d['name']!r}")
    for ip in plan.internal_points:
        print(
            "INTERNAL (report only; pass --purge-internal to delete) "
            f"id={ip['id']} {ip['name']!r}"
        )
    for r in plan.refusals:
        print(f"REFUSED {r}")
    for n in plan.no_point:
        print(f"NO-POINT (report only) catalog row {n!r}")
    for n in plan.no_catalog_row:
        print(f"NO-CATALOG-ROW (report only) point {n!r}")
    print(
        f"SUMMARY updates={len(plan.updates)} deletes={len(plan.deletes)} "
        f"internal_points={len(plan.internal_points)} "
        f"refused={len(plan.refusals)} in_sync={plan.in_sync} "
        f"catalog_rows_without_point={len(plan.no_point)} "
        f"points_without_catalog_row={len(plan.no_catalog_row)} "
        f"creates={len(plan.creates)}"
    )


async def _scroll_all_points(
    client: httpx.AsyncClient, base_url: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    offset: Any = None
    while True:
        body: dict[str, Any] = {
            "limit": SCROLL_BATCH_SIZE,
            "with_payload": True,
            "with_vectors": False,
        }
        if offset is not None:
            body["offset"] = offset
        resp = await client.post(
            f"{base_url}/collections/{COLLECTION_NAME}/points/scroll",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()["result"]
        points.extend(result["points"])
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return points


async def _set_payload(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    point_id: Any,
    payload: dict[str, Any],
) -> None:
    """Payload-only set: merges the listed top-level keys, vectors untouched."""
    resp = await client.post(
        f"{base_url}/collections/{COLLECTION_NAME}/points/payload",
        headers=headers,
        json={"payload": payload, "points": [point_id]},
        timeout=30,
    )
    resp.raise_for_status()


async def _delete_points(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    point_ids: list[Any],
) -> None:
    """Delete the specified point IDs from the Qdrant collection."""
    if not point_ids:
        return
    resp = await client.post(
        f"{base_url}/collections/{COLLECTION_NAME}/points/delete",
        headers=headers,
        json={"points": point_ids},
        timeout=30,
    )
    resp.raise_for_status()


async def _dense_vector_size(
    client: httpx.AsyncClient, base_url: str, headers: dict[str, str]
) -> Any:
    resp = await client.get(
        f"{base_url}/collections/{COLLECTION_NAME}", headers=headers, timeout=30
    )
    resp.raise_for_status()
    vectors = resp.json()["result"]["config"]["params"].get("vectors") or {}
    return (vectors.get(DENSE_VECTOR_NAME) or {}).get("size")


async def _existing_ids(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    point_ids: list[Any],
) -> set[Any]:
    """The subset of ``point_ids`` that already exists in the collection."""
    resp = await client.post(
        f"{base_url}/collections/{COLLECTION_NAME}/points",
        headers=headers,
        json={"ids": point_ids, "with_payload": False, "with_vector": False},
        timeout=30,
    )
    resp.raise_for_status()
    return {p["id"] for p in resp.json()["result"]}


async def _upsert_points(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    points: list[dict[str, Any]],
) -> None:
    resp = await client.put(
        f"{base_url}/collections/{COLLECTION_NAME}/points?wait=true",
        headers=headers,
        json={"points": points},
        timeout=60,
    )
    resp.raise_for_status()


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed through the backend's own client, pinned to the collection's model."""
    if str(BACKEND_RAG_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_RAG_ROOT))
    from backend.core.embeddings import EmbeddingsGenerator

    generator = EmbeddingsGenerator(provider="openai", model=EMBED_MODEL)
    return await generator.generate_embeddings(texts)


async def _apply_creates(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    creates: list[dict[str, Any]],
    embed: Embedder,
) -> int:
    """Write the planned creates and nothing else; any doubt writes nothing."""
    if not creates:
        print(f"CREATED 0 point(s) in {COLLECTION_NAME}")
        return 0
    size = await _dense_vector_size(client, base_url, headers)
    if size != DENSE_VECTOR_SIZE:
        print(
            f"REFUSED dense vector size is {size}, expected {DENSE_VECTOR_SIZE} - nothing created"
        )
        return 2
    present = await _existing_ids(client, base_url, headers, [c["id"] for c in creates])
    if present:
        print(
            f"REFUSED point id(s) already present {sorted(present)} - nothing created"
        )
        return 2
    vectors = await embed([c["payload"]["text"] for c in creates])
    if len(vectors) != len(creates) or any(
        len(v) != DENSE_VECTOR_SIZE for v in vectors
    ):
        print("REFUSED embeddings do not match the planned creates - nothing created")
        return 2
    points = [
        {"id": c["id"], "vector": {DENSE_VECTOR_NAME: v}, "payload": c["payload"]}
        for c, v in zip(creates, vectors, strict=True)
    ]
    for i in range(0, len(points), UPSERT_BATCH_SIZE):
        await _upsert_points(
            client, base_url, headers, points[i : i + UPSERT_BATCH_SIZE]
        )
    print(f"CREATED {len(points)} point(s) in {COLLECTION_NAME}")
    return 0


def _load_catalog(path: str) -> dict[str, Any]:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def run(
    catalog_path: str,
    apply: bool,
    today: str | None = None,
    only: frozenset[str] | None = None,
    purge_internal: bool = False,
    create_missing: bool = False,
    embed: Embedder | None = None,
    delete_orphans: bool = False,
    expect_orphans: int | None = None,
) -> int:
    if create_missing and purge_internal:
        logger.error("--create-missing never deletes: drop --purge-internal")
        return 1
    if delete_orphans and (create_missing or purge_internal or only):
        logger.error(
            "--delete-orphans is delete-only: drop --create-missing, --purge-internal and --only"
        )
        return 1
    if delete_orphans and apply and expect_orphans is None:
        logger.error(
            "--delete-orphans --apply needs --expect-orphans N (the count the dry run printed)"
        )
        return 1
    url = os.environ.get("QDRANT_URL")
    key = os.environ.get("QDRANT_API_KEY")
    if not url or not key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in the environment")
        return 1
    catalog = _load_catalog(catalog_path)
    prices = catalog_prices(catalog)
    internal_names = internal_catalog_names(catalog)
    headers = {"api-key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        points = await _scroll_all_points(client, url, headers)
        today = today or dt.date.today().isoformat()
        plan = build_plan(
            points,
            prices,
            today,
            only,
            internal_names=internal_names,
            purge_internal=purge_internal,
        )
        if create_missing:
            plan.creates, create_refusals = plan_creates(points, catalog, today, only)
            plan.refusals.extend(create_refusals)
        if delete_orphans:
            plan.deletes, orphan_refusals = plan_orphan_deletes(points, catalog)
            plan.refusals.extend(orphan_refusals)
        print_plan(plan)
        if plan.refusals:
            print("REFUSALS PRESENT - nothing applied")
            return 2
        if not apply:
            print("Dry-run only (default) - pass --apply to write")
            return 0
        if delete_orphans:
            if len(plan.deletes) != expect_orphans:
                print(
                    f"ORPHAN COUNT {len(plan.deletes)} != --expect-orphans {expect_orphans} - nothing applied"
                )
                return 2
            if plan.updates:
                print(
                    f"{len(plan.updates)} UPDATE(s) reported, not applied: --delete-orphans writes deletes only"
                )
            await _delete_points(client, url, headers, [d["id"] for d in plan.deletes])
            print(f"DELETED {len(plan.deletes)} orphan point(s) from {COLLECTION_NAME}")
            return 0
        if create_missing:
            if plan.updates:
                print(
                    f"{len(plan.updates)} UPDATE(s) reported, not applied: --create-missing writes creates only"
                )
            return await _apply_creates(
                client, url, headers, plan.creates, embed or _embed_texts
            )
        for u in plan.updates:
            await _set_payload(client, url, headers, u["id"], u["payload"])
        if purge_internal and plan.deletes:
            await _delete_points(client, url, headers, [d["id"] for d in plan.deletes])
            print(
                f"DELETED {len(plan.deletes)} internal point(s) from {COLLECTION_NAME}"
            )
        print(f"APPLIED {len(plan.updates)} point(s) in {COLLECTION_NAME}")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write (default: dry-run)")
    parser.add_argument(
        "--purge-internal",
        action="store_true",
        help=(
            "plan deletion of Qdrant points matching catalog rows marked "
            '"internal": true (dry-run by default; combine with --apply to delete)'
        ),
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help=(
            "plan a point for every public catalog row that has none (dry-run by "
            "default; with --apply writes those creates and nothing else)"
        ),
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help=(
            "plan deletion of points whose name matches no catalog row, public or "
            "internal (delete-only; dry-run by default)"
        ),
    )
    parser.add_argument(
        "--expect-orphans",
        type=int,
        default=None,
        metavar="N",
        help="with --delete-orphans --apply: the orphan count the dry run printed",
    )
    parser.add_argument(
        "--catalog", default=str(DEFAULT_CATALOG), help="catalog JSON path or -"
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="NAME",
        help="restrict to this exact catalog name (repeatable); default: every drifted row",
    )
    args = parser.parse_args()
    if args.create_missing and args.purge_internal:
        parser.error("--create-missing never deletes: drop --purge-internal")
    if args.delete_orphans and (
        args.create_missing or args.purge_internal or args.only
    ):
        parser.error(
            "--delete-orphans is delete-only: drop --create-missing, --purge-internal and --only"
        )
    if args.expect_orphans is not None and not args.delete_orphans:
        parser.error("--expect-orphans only makes sense with --delete-orphans")
    only = frozenset(args.only) if args.only else None
    return asyncio.run(
        run(
            args.catalog,
            args.apply,
            only=only,
            purge_internal=args.purge_internal,
            create_missing=args.create_missing,
            delete_orphans=args.delete_orphans,
            expect_orphans=args.expect_orphans,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
