#!/usr/bin/env python3
"""Sync the frontend company-services price catalog from the PricingTool canonical JSON.

Single source of truth for Bali Zero prices is
``apps/backend-rag/backend/data/bali_zero_official_prices_2026.json`` (the file
``PricingService._load_prices()`` reads — i.e. "PricingTool"). The Next.js
frontend (apps/mouth) is built/deployed separately on Vercel and cannot reach
the backend at request time for two annual-static company prices, so it reads a
COMMITTED, GENERATED copy under ``apps/mouth/data/``.

This script regenerates that copy. It extracts ONLY the ``company_services``
block, keyed by ``icon_id`` (stable against display-name changes). Run it
whenever the canonical catalog changes; CI parity is enforced by
``apps/mouth/src/lib/bali-zero-prices.test.ts`` (the test fails if the copy
drifts from the canonical), so a stale copy cannot ship silently.

Usage:
    python3 scripts/sync_frontend_prices.py          # write
    python3 scripts/sync_frontend_prices.py --check   # exit 1 if drift (no write)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = (
    REPO_ROOT
    / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"
)
DST = REPO_ROOT / "apps/mouth/data/bali-zero-prices.json"


def build_payload() -> dict:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    company_services = src["services"]["company_services"]
    out: dict = {
        "_source": (
            "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json "
            "(PricingTool canonical)"
        ),
        "_note": (
            "SYNCED COPY — do not hand-edit. Regenerate via "
            "scripts/sync_frontend_prices.py. Parity enforced by "
            "apps/mouth/src/lib/bali-zero-prices.test.ts."
        ),
        "company_services": {},
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
    return out


def serialize(payload: dict) -> str:
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
            sys.stderr.write(
                f"DRIFT: {DST} is out of sync with {SRC}. "
                "Run: python3 scripts/sync_frontend_prices.py\n"
            )
            return 1
        print(f"OK: {DST} is in sync with PricingTool canonical.")
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(rendered, encoding="utf-8")
    print(f"WROTE {DST}")
    print(f"  company-pma     -> {payload['company_services'].get('company-pma')}")
    print(f"  company-virtual -> {payload['company_services'].get('company-virtual')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
