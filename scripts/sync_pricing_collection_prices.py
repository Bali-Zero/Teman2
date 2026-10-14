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
Without ``--purge-internal``, Qdrant points matching catalog rows marked
``"internal": true`` are reported (``INTERNAL (report only; pass --purge-internal
to delete) id=<id> <name!r>``) and never upserted or counted in ``no_catalog_row``.
When ``--purge-internal`` is passed, those points are listed for deletion (dry-run
by default; ``--purge-internal --apply`` deletes those exact point IDs and also
applies pending price updates in the same run — use ``--only`` to narrow).
Any refusal (old price not found exactly once, ambiguous name) exits non-zero and
``--apply`` then applies NOTHING.

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --apply
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --purge-internal
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --purge-internal --apply
    # Note: --purge-internal --apply also applies pending price updates in the same run (use --only to narrow)
    ... --catalog PATH     # default: the canonical JSON in the repo; "-" reads stdin
    ... --only "New Company (PT PMA)"   # scope to one catalog name (repeatable)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import sys
from collections.abc import Iterator
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
SCROLL_BATCH_SIZE = 100


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


def print_plan(plan: Plan) -> None:
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
        f"points_without_catalog_row={len(plan.no_catalog_row)}"
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
) -> int:
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
        plan = build_plan(
            points,
            prices,
            today or dt.date.today().isoformat(),
            only,
            internal_names=internal_names,
            purge_internal=purge_internal,
        )
        print_plan(plan)
        if plan.refusals:
            print("REFUSALS PRESENT - nothing applied")
            return 2
        if not apply:
            print("Dry-run only (default) - pass --apply to write")
            return 0
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
    only = frozenset(args.only) if args.only else None
    return asyncio.run(
        run(
            args.catalog,
            args.apply,
            only=only,
            purge_internal=args.purge_internal,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
