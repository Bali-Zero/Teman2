#!/usr/bin/env python3
"""Sync the frontend public price catalog from the PricingTool canonical JSON.

Single source of truth for Bali Zero prices is
``apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`` (the file
``PricingService._load_prices()`` reads — i.e. "PricingTool"). The Next.js
frontend (apps/mouth) is built/deployed separately on Vercel, so deterministic
public service cards read a COMMITTED, GENERATED copy under
``apps/mouth/data/``.

This script regenerates that copy. It preserves the legacy
``company_services`` icon lookup and also emits every exact PricingTool row
under ``services_by_category`` for client-facing service cards. Run it whenever
the canonical catalog changes; full-row parity is enforced by
``apps/mouth/src/lib/pricing-snapshot.test.ts`` and legacy company-card parity
by ``apps/mouth/src/lib/bali-zero-prices.test.ts``, so a stale copy cannot ship
silently.

Usage:
    python3 scripts/sync_frontend_prices.py          # write
    python3 scripts/sync_frontend_prices.py --check   # exit 1 if drift (no write)
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
DST = REPO_ROOT / "apps/mouth/data/bali-zero-prices.json"


def _iter_service_rows(
    services: dict[str, Any],
) -> Iterator[tuple[str, str, dict[str, Any]]]:
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


def build_payload() -> dict[str, Any]:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    company_services = src["services"]["company_services"]
    out: dict[str, Any] = {
        "_source": (
            "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json "
            "(PricingTool canonical)"
        ),
        "_note": (
            "SYNCED COPY — do not hand-edit. Regenerate via "
            "scripts/sync_frontend_prices.py. Parity enforced by "
            "apps/mouth/src/lib/pricing-snapshot.test.ts."
        ),
        "company_services": {},
        "services_by_category": {},
    }
    for name, svc in company_services.items():
        icon = svc.get("icon_id")
        if not icon:
            continue
        out["company_services"][icon] = {
            "name": svc.get("name", name),
            "price": svc.get("price"),
            "icon_id": icon,
        }
    for category, key, svc in _iter_service_rows(src["services"]):
        category_rows = out["services_by_category"].setdefault(category, {})
        if key in category_rows:
            raise ValueError(f"duplicate exact PricingTool key: {category}:{key}")
        category_rows[key] = {
            "category": category,
            "key": key,
            "name": svc.get("name", key),
            "price": svc.get("price"),
            "duration": svc.get("duration"),
            "validity": svc.get("validity"),
            "notes": svc.get("notes"),
            "description_en": svc.get("description_en"),
            "icon_id": svc.get("icon_id"),
        }
    return out


def serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the committed copy is out of sync (no write)",
    )
    args = parser.parse_args()

    payload = build_payload()
    rendered = serialize(payload)

    if args.check:
        current = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if current != rendered:
            logger.error(
                "DRIFT: %s is out of sync with %s. Run the sync script.",
                DST,
                SRC,
            )
            return 1
        logger.info("OK: %s is in sync with PricingTool canonical.", DST)
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(rendered, encoding="utf-8")
    exact_rows = sum(len(rows) for rows in payload["services_by_category"].values())
    logger.info("WROTE %s with %d exact rows", DST, exact_rows)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
