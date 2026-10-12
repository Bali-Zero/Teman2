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

What it does, per catalog row (same traversal as
``scripts/sync_frontend_prices.py::_iter_service_rows``):
  - matches a point by payload ``name`` == catalog ``name``;
  - expected price = catalog ``price``, or, for tier rows with an empty price,
    ``"<lo> - <hi> IDR"`` built from ``tier_range`` (the shape the points use);
  - if the payload ``price`` differs, plans a set-payload of ``price``,
    ``text`` (the old price string replaced by the new one, ONLY when it occurs
    exactly once in the text) and ``last_updated`` (today, ISO).

It NEVER re-embeds vectors, deletes points or creates points. Catalog rows with
no point and points with no catalog row are REPORTED, never acted on. Any
refusal (old price not found exactly once, ambiguous name) exits non-zero and
``--apply`` then applies NOTHING.

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/sync_pricing_collection_prices.py --apply
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
    """Same traversal as scripts/sync_frontend_prices.py::_iter_service_rows."""
    for category, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category == "tax_accounting":
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for key, row in sub_block.items():
                    if isinstance(row, dict):
                        yield f"{category}.{sub_block_name}", key, row
            continue
        for key, row in category_payload.items():
            if isinstance(row, dict):
                yield category, key, row


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
    """name -> expected price. A duplicated name is dropped (ambiguous)."""
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
    refusals: list[str] = field(default_factory=list)
    no_point: list[str] = field(default_factory=list)
    no_catalog_row: list[str] = field(default_factory=list)
    in_sync: int = 0


def build_plan(
    points: list[dict[str, Any]],
    prices: dict[str, str],
    today: str,
    only: frozenset[str] | None = None,
) -> Plan:
    """``only`` scopes the plan to those catalog names (everything else is ignored)."""
    if only:
        prices = {n: v for n, v in prices.items() if n in only}
        points = [p for p in points if (p.get("payload") or {}).get("name") in only]
    plan = Plan()
    by_name: dict[str, list[dict[str, Any]]] = {}
    for p in points:
        by_name.setdefault((p.get("payload") or {}).get("name", ""), []).append(p)
    for name in prices:
        if name not in by_name:
            plan.no_point.append(name)
    for name, group in by_name.items():
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
    for r in plan.refusals:
        print(f"REFUSED {r}")
    for n in plan.no_point:
        print(f"NO-POINT (report only) catalog row {n!r}")
    for n in plan.no_catalog_row:
        print(f"NO-CATALOG-ROW (report only) point {n!r}")
    print(
        f"SUMMARY updates={len(plan.updates)} refused={len(plan.refusals)} "
        f"in_sync={plan.in_sync} catalog_rows_without_point={len(plan.no_point)} "
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


def _load_catalog(path: str) -> dict[str, Any]:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def run(
    catalog_path: str,
    apply: bool,
    today: str | None = None,
    only: frozenset[str] | None = None,
) -> int:
    url = os.environ.get("QDRANT_URL")
    key = os.environ.get("QDRANT_API_KEY")
    if not url or not key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in the environment")
        return 1
    prices = catalog_prices(_load_catalog(catalog_path))
    headers = {"api-key": key, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        points = await _scroll_all_points(client, url, headers)
        plan = build_plan(points, prices, today or dt.date.today().isoformat(), only)
        print_plan(plan)
        if plan.refusals:
            print("REFUSALS PRESENT - nothing applied")
            return 2
        if not apply:
            print("Dry-run only (default) - pass --apply to write")
            return 0
        for u in plan.updates:
            await _set_payload(client, url, headers, u["id"], u["payload"])
        print(f"APPLIED {len(plan.updates)} point(s) in {COLLECTION_NAME}")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write (default: dry-run)")
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
    return asyncio.run(run(args.catalog, args.apply, only=only))


if __name__ == "__main__":
    raise SystemExit(main())
