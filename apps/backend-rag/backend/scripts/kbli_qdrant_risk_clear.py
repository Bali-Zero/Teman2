"""
kbli_qdrant_risk_clear.py — clear the stale flat `kategori_risiko` Qdrant
payload field for KBLI codes whose canonical dataset record was detached
from a cross-vintage code-number collision (the honest-gap cure pattern,
PR #2597 / commit `4c6f43bc6b`, and its KG-side sibling
`kg_kbli_license_fix.py`).

WHY: `_resolve_risk_profile()` (`backend/app/routers/kbli_notebook.py:282-292`)
degrades to the honest ``"Not classified"`` label instead of a
false-reassuring ``"Low"`` ONLY when the Qdrant `kategori_risiko` payload
value is falsy:

    qdrant_risk or (licenses[0].risk_level if licenses else None) or "Not classified"

A code whose canonical `per_skala` was detached by `kg_kbli_license_fix.py`
(the Postgres/KG-side cure) can still carry a STALE `kategori_risiko`
string in Qdrant — the cross-vintage collision's risk tier, inherited from
the original ingest, not this code's. As long as that stale value survives
in Qdrant, `_resolve_risk_profile` never sees a falsy `qdrant_risk` and
keeps serving the wrong risk label. This script is the Qdrant-side half of
the cure — it never touches Postgres/KG (that is `kg_kbli_license_fix.py`'s
job) and never touches any payload field other than `kategori_risiko`.

"CLEARED" MEANS EMPTY STRING, NOT KEY-DELETE: both `_resolve_risk_profile`
(`kbli_notebook.py:292`, the `qdrant_risk or ...` chain above) and the
flat-payload reader `_payload_value()` (`kbli_notebook.py:119-125` —
``payload.get(key) not in (None, "")``) already treat an empty string
exactly like an absent key: both fall through to their next fallback.
`--apply` therefore calls `set_payload` with `kategori_risiko: ""` (a
payload MERGE that only touches this one key, never `delete_payload`/
`overwrite_payload`) rather than deleting the key outright: the flat KBLI
payload invariant (`kode_kbli`, `judul`, `content`, `sektor_id`,
`pma_status`, `skala_usaha`, `kategori_risiko` — CLAUDE.md §9) keeps its
declared shape with an honest falsy value instead of a field that some
downstream reader might not guard for absence identically to emptiness.

SYNC CLIENT, NOT ASYNC: unlike `kg_kbli_license_fix.py` (asyncpg + httpx —
genuine async I/O), this script's only I/O is Qdrant reads/writes. The
codebase's own KBLI-collection Qdrant tooling
(`backend/services/knowledge_graph/kbli_enricher.py`) uses the SYNC
`qdrant_client.QdrantClient` for the same collection — matched here rather
than introducing `AsyncQdrantClient`, which nothing else in this repo uses.

SCOPE DISCIPLINE (mirrors kg_kbli_license_fix.py): --codes is MANDATORY —
no code is ever auto-discovered/swept.

USAGE (dry-run is the default; nothing is written without --apply):
    PYTHONPATH=. python backend/scripts/kbli_qdrant_risk_clear.py \
        --codes 68112,49213,51103,51203,20111,50115,60312,64310

    PYTHONPATH=. python backend/scripts/kbli_qdrant_risk_clear.py \
        --codes 68112 --apply
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Record

from backend.app.core.config import settings
from backend.core.collection_registry import resolve_collection_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_qdrant_risk_clear")

# Both _resolve_risk_profile (kbli_notebook.py:292) and _payload_value
# (kbli_notebook.py:119-125) treat "" exactly like an absent payload key —
# see module docstring "CLEARED MEANS EMPTY STRING" above.
CLEARED_RISK_VALUE = ""

# Point id as returned by qdrant_client (REST mode): int or string UUID.
PointId = int | str

_SCROLL_PAGE_LIMIT = 256


@dataclass
class CodeClearPlan:
    """Pure decision record for one KBLI code — no I/O, easy to unit test."""

    code: str
    point_ids: list[PointId] = field(default_factory=list)
    current_values: dict[PointId, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.point_ids)


def build_plan(code: str, records: list[Record]) -> CodeClearPlan:
    """Turn scrolled Qdrant records into a `CodeClearPlan` — pure, no I/O.

    `records` is whatever `find_points_for_code()` scrolled back for this
    code (already filtered on the flat `kode_kbli` field) — never guessed
    or derived from a point-id assumption.
    """
    plan = CodeClearPlan(code=code)
    for rec in records:
        payload = rec.payload or {}
        plan.point_ids.append(rec.id)
        plan.current_values[rec.id] = payload.get("kategori_risiko")
    return plan


def find_points_for_code(client: QdrantClient, collection: str, code: str) -> list[Record]:
    """Scroll `collection` for every point whose flat `kode_kbli` field equals `code`.

    Never guesses point ids — always resolved via the flat-payload filter
    (KBLI flat payload invariant: `kode_kbli`, `judul`, `content`,
    `sektor_id`, `pma_status`, `skala_usaha`, `kategori_risiko` — never
    nested. CLAUDE.md §9).
    """
    scroll_filter = models.Filter(
        must=[models.FieldCondition(key="kode_kbli", match=models.MatchValue(value=code))],
    )
    records: list[Record] = []
    offset = None
    while True:
        page, offset = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=_SCROLL_PAGE_LIMIT,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        records.extend(page)
        if offset is None:
            break
    return records


def clear_risk_for_code(
    client: QdrantClient,
    collection: str,
    plan: CodeClearPlan,
    apply: bool,
) -> None:
    """Report (always) and write (only if `apply`) the cleared payload for one code."""
    if not plan.found:
        logger.info("NOT FOUND %s: no points match kode_kbli=%s in %s", plan.code, plan.code, collection)
        return

    for point_id in plan.point_ids:
        logger.info(
            "  %s: point %s kategori_risiko %r -> %r%s",
            plan.code,
            point_id,
            plan.current_values.get(point_id),
            CLEARED_RISK_VALUE,
            "" if apply else " (dry-run, not written)",
        )

    if not apply:
        return

    for point_id in plan.point_ids:
        client.set_payload(
            collection_name=collection,
            payload={"kategori_risiko": CLEARED_RISK_VALUE},
            points=[point_id],
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--codes",
        required=True,
        help="comma-separated list of KBLI codes to process (never auto-discovered/swept)",
    )
    ap.add_argument(
        "--collection",
        default=resolve_collection_name("kbli_2025_final"),
        help="physical Qdrant collection name (default: resolved 'kbli_2025_final')",
    )
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        logger.error("--codes produced an empty code list, nothing to do")
        return

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    found = 0
    not_found = 0
    for code in codes:
        records = find_points_for_code(client, args.collection, code)
        plan = build_plan(code, records)
        clear_risk_for_code(client, args.collection, plan, args.apply)
        if plan.found:
            found += 1
        else:
            not_found += 1

    mode = "APPLIED" if args.apply else "DRY-RUN"
    logger.info("%s: %d code(s) with matching points | %d not found", mode, found, not_found)
    if not args.apply and found:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    main()
