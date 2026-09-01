#!/usr/bin/env python3
"""Patch the retired WhatsApp/Location contact block baked into the LIVE
``bali_zero_pricing_hybrid`` Qdrant collection's payload ``text`` field.

WHY payload-only (no re-embed): the collection's generator
(``scripts/prepare_payloads.py``) already reads the CURRENT contact info from
``apps/backend-rag/backend/data/bali_zero_official_prices_2026.json``
(``metadata.contact.whatsapp``). What IS stale is the
collection itself: ``bali_zero_pricing_hybrid`` was built once via
``migration_031b_hybrid_collections.py`` by copying/re-embedding whatever
points existed in the OLD ``bali_zero_pricing`` collection at the time, and
those points still carry the retired contact block verbatim (matches
``bali_zero_official_prices_2025.json``'s ``text`` fields byte-for-byte:
``info@balizero.com`` / ``+62 813 3805 1876`` / ``Canggu, Bali, Indonesia``).
The collection was never refreshed since. A full re-embed (rerunning
``prepare_payloads.py`` + ``force_upload.sh``) would cost OpenAI calls, target
a differently-named collection (``bali_zero_pricing`` — not the
``_hybrid`` name actually registered/queried, see
``backend/core/collection_registry.py``), and risk reshaping the payload for
no semantic gain: only two trailer lines change, not the item name/category/
price the embedding is actually keyed on.

This script instead rewrites ONLY the ``**WhatsApp**:`` and ``**Location**:``
trailer lines inside each point's ``payload["text"]``, via Qdrant's
"set payload" endpoint (``POST .../points/payload``), which sets/overwrites
just the listed top-level payload keys — vectors and every other payload key
(``name``, ``category``, ``price``, ``duration``, ``validity``, ``notes``,
``source_type``, ``last_updated``, ``currency``) are left untouched. Prices
are NEVER touched (CLAUDE.md Golden Rule #11 — PricingTool only).

Idempotent: running twice is a no-op the second time (``rewrite_contact_block``
returns the input unchanged once the stale markers are gone).

Usage:
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/patch_pricing_contact_block.py           # dry-run (default)
    QDRANT_URL=... QDRANT_API_KEY=... python scripts/patch_pricing_contact_block.py --apply    # write
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COLLECTION_NAME = "bali_zero_pricing_hybrid"

# Ari's line — the CLIENT-facing number, deliberately NOT the bot's inbound
# `settings.SUPPORT_WHATSAPP` (owner ruling 2026-09-01). Kept in sync with
# `settings.CLIENT_CONTACT_WHATSAPP` and the price-list generator's
# `_CANONICAL_WHATSAPP_DIGITS` by the tripwires in
# apps/backend-rag/backend/tests/test_data_invariant_tripwires.py.
CANONICAL_WHATSAPP = "+62 821 3454 721"

# EVERY number this collection is known to have carried, not just the oldest.
# A single stale marker could only ever heal one generation of drift: if the
# collection were patched while a different number was canonical, the guard
# below would see no stale marker, return the text byte-identical, and the
# script would report a clean idempotent no-op over a payload it had itself
# made wrong. The second entry WAS canonical between 2026-08-31 and
# 2026-09-01 — not a hypothetical. Append here, never replace.
STALE_WHATSAPP_NUMBERS = (
    "+62 813 3805 1876",  # retired personal line, the original drift
    "+62 821 3465 159",  # the bot's INBOUND number, canonical 2026-08-31..09-01
)
_WHATSAPP_LABEL = "**WhatsApp**:"
_LOCATION_LABEL = "**Location**:"

STALE_LOCATION = "Canggu, Bali, Indonesia"
CANONICAL_LOCATION = "Kerobokan, Bali, Indonesia"

SCROLL_BATCH_SIZE = 100
_SAMPLE_TAIL_CHARS = 200


def rewrite_contact_block(text: str) -> str:
    """Rewrite ONLY the WhatsApp/Location trailer LINES of a pricing chunk's
    embedded text. Never touches the name/category/price/duration/validity/
    notes lines above the ``---`` separator.

    Line-anchored, not substring-replace. The substring form was wrong in two
    ways an adversarial review demonstrated on 2026-09-01:

      - `**WhatsApp**: +62 813 3805 1876 / +62 821 3465 159` — a line carrying
        BOTH stale numbers. The first replacement rewrote the prefix and left
        the second number sitting after it, and a second pass could no longer
        match because the label was no longer adjacent to it. The result was
        wrong AND stable, which is the worst combination: it looked idempotent.
      - `**Notes**: previous payload contained **WhatsApp**: <stale>` — a line
        that merely QUOTES a contact trailer was rewritten too, because
        `str.replace` has no notion of where a line begins.

    Rewriting the whole line, only when the line IS the trailer, answers both.

    Guilt: a line beginning `**WhatsApp**:` whose value contains ANY known
    stale number is replaced in full by the canonical trailer; likewise the
    stale Location line.
    Innocence: every other line is returned byte-identical, including a line
    that merely mentions a trailer, and including an already-canonical trailer
    (so a second run is a true no-op).
    """
    out: list[str] = []
    changed = False
    for line in text.split("\n"):
        # Preserve the line's own indentation and its CR, if the payload uses
        # CRLF. Rebuilding the line from the label alone silently normalised
        # both away, leaving ONE rewritten line with a bare LF among CRLF
        # neighbours — a corruption the rewrite has no business introducing.
        body = line.rstrip("\r")
        carriage = line[len(body) :]
        indent = body[: len(body) - len(body.lstrip())]
        stripped = body.strip()
        if stripped.startswith(_WHATSAPP_LABEL) and any(
            stale in stripped for stale in STALE_WHATSAPP_NUMBERS
        ):
            out.append(f"{indent}{_WHATSAPP_LABEL} {CANONICAL_WHATSAPP}{carriage}")
            changed = True
        elif stripped.startswith(_LOCATION_LABEL) and STALE_LOCATION in stripped:
            out.append(f"{indent}{_LOCATION_LABEL} {CANONICAL_LOCATION}{carriage}")
            changed = True
        else:
            out.append(line)
    return "\n".join(out) if changed else text


async def _scroll_all_points(
    client: httpx.AsyncClient, base_url: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    """Scroll every point's id + payload (never vectors) from the collection."""
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


async def _set_payload_text(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    point_id: Any,
    new_text: str,
) -> None:
    """Payload-only set — overwrites ONLY the ``text`` key for this one point
    id. Vectors and every other payload key are untouched by construction
    (Qdrant's set-payload endpoint merges at the top-level key)."""
    body = {"payload": {"text": new_text}, "points": [point_id]}
    resp = await client.post(
        f"{base_url}/collections/{COLLECTION_NAME}/points/payload",
        headers=headers,
        json=body,
        timeout=30,
    )
    resp.raise_for_status()


async def _run(apply: bool) -> int:
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_api_key:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set in the environment")
        return 1

    headers = {"api-key": qdrant_api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        points = await _scroll_all_points(client, qdrant_url, headers)
        logger.info("Scrolled %d point(s) from %s", len(points), COLLECTION_NAME)

        stale: list[tuple[Any, str, str]] = []
        for point in points:
            text = (point.get("payload") or {}).get("text", "")
            if not isinstance(text, str):
                continue
            new_text = rewrite_contact_block(text)
            if new_text != text:
                stale.append((point["id"], text, new_text))

        logger.info("Found %d point(s) with the retired contact block", len(stale))

        if stale:
            sample_id, sample_before, sample_after = stale[0]
            logger.info(
                "Sample point %s BEFORE (tail): ...%s",
                sample_id,
                sample_before[-_SAMPLE_TAIL_CHARS:],
            )
            logger.info(
                "Sample point %s AFTER  (tail): ...%s",
                sample_id,
                sample_after[-_SAMPLE_TAIL_CHARS:],
            )

        if not apply:
            logger.info("Dry-run only (default) — pass --apply to write changes")
            return 0

        for point_id, _before, after in stale:
            await _set_payload_text(client, qdrant_url, headers, point_id, after)

        logger.info("Patched %d point(s) in %s", len(stale), COLLECTION_NAME)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Write the patched payloads (default: dry-run)"
    )
    args = parser.parse_args()
    return asyncio.run(_run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
