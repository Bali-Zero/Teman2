"""
kbli_qdrant_pma_sync.py — sync the `pma_status` / `pma_max_asing` Qdrant payload
fields of KBLI points from the canonical dataset.

WHY THIS EXISTS, AND WHY THE KG-SIDE CURE WAS NOT ENOUGH (2026-08-02, found
during the prove-live of the Perpres 49/2021 Lampiran III cure, #3515):
`inspect_kbli` resolves the PMA verdict with Qdrant FIRST and the KG node only
as a fallback (`backend/app/routers/kbli_notebook.py`):

    pma_status = (
        (_payload_value(qdrant_payload, "pma_status") if qdrant_payload else None)
        or props.get("pma_status")      # <- the kg_nodes property
        ...
    )

So `kg_kbli_resync.py` — whose own docstring exists *because* `inspect_kbli`
served a stale `pma_status` — cannot move that field on this endpoint while
Qdrant carries any value at all. Measured live: after the cure, `kg_nodes` said
TERBATAS on all twenty codes and `inspect_kbli 51101` still answered TERBUKA,
because the Qdrant payload still read `TERBUKA / 100`. A cure that stops at the
KG is a cure the channel never sees.

WHAT IT WRITES: exactly two flat keys, `pma_status` and `pma_max_asing`, via
`set_payload` — a payload MERGE that touches nothing else. Never
`overwrite_payload`, never `delete_payload`, never a vector. **The embedding
model is FROZEN** (`text-embedding-3-small`, 93k+ vectors — CLAUDE.md §9); a
re-index to change two scalars would put that invariant at risk for no reason.

SCOPE DISCIPLINE (mirrors `kbli_qdrant_risk_clear.py` and
`kg_kbli_license_fix.py`): `--codes` is MANDATORY. No code is ever
auto-discovered or swept.

`--collection` IS ALSO MANDATORY, and that is deliberate. The physical name is
`kbli_2025_final_hybrid`; the logical name `kbli_2025_final` **does not exist**
as a collection, and `kbli_2025_final_oss` (10,825 points) answers to none of
the code keys the router tries. Writing a default here would freeze a measure of
the world into a constant — the exact shape that took production down for 27h in
W106 — so the caller states it and the guard below checks it.

THE WRONG-COLLECTION GUARD: if not one of the requested codes matches a single
point, the run exits 2 instead of reporting a tidy "0 updated". A probe pointed
at a collection that does not carry `kode_kbli` returns a clean, believable zero
for every code you ask about, including codes you know exist — that is how this
defect was nearly mis-diagnosed on the day this script was written.

USAGE (dry-run is the default; nothing is written without --apply):
    cd /app && python backend/scripts/kbli_qdrant_pma_sync.py \\
        --collection kbli_2025_final_hybrid --codes 51101,25200

    cd /app && python backend/scripts/kbli_qdrant_pma_sync.py \\
        --collection kbli_2025_final_hybrid --codes 51101,25200 --apply

Deliberately import-free of `backend.*`: the two cure tools that already run in
this image (`kbli_documents_cure.py`, `kg_kbli_resync.py`) read their config
from the environment and fetch the canonical over HTTP, and `PYTHONPATH=.` in
this container REPLACES site-packages rather than extending it (it has already
cost one `ModuleNotFoundError: asyncpg`). Same shape here, for the same reason.

AFTER APPLYING, EVICT THE CACHE: `inspect_kbli` caches its assembled payload
under `kbli_inspect_v2_<code>` for up to 30 days, so a cured Qdrant payload is
invisible on the channel until `kbli_inspect_cache_bust.py --only <codes>
--apply` has run.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_qdrant_pma_sync")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

# The flat KBLI payload invariant (CLAUDE.md §9) — the code lives in
# `kode_kbli`, never nested. Points are always resolved through this filter,
# never through a point-id assumption.
CODE_KEY = "kode_kbli"

_SCROLL_PAGE_LIMIT = 256


@dataclass(frozen=True)
class Target:
    """What the canonical says this code's PMA fields should be."""

    code: str
    pma_status: str
    pma_max_asing: Any


@dataclass
class CodePlan:
    """Pure decision record for one code — no I/O, so it unit-tests directly."""

    code: str
    target: Target
    point_ids: list[Any]
    current: dict[Any, dict[str, Any]]

    @property
    def found(self) -> bool:
        return bool(self.point_ids)

    def stale_points(self) -> list[Any]:
        """Point ids whose payload disagrees with the canonical on either field."""
        out = []
        for pid in self.point_ids:
            cur = self.current.get(pid, {})
            if (
                cur.get("pma_status") != self.target.pma_status
                or cur.get("pma_max_asing") != self.target.pma_max_asing
            ):
                out.append(pid)
        return out


def build_targets(records: list[dict], codes: list[str]) -> tuple[dict[str, Target], list[str]]:
    """Read the canonical verdict for each requested code.

    A code the canonical does not carry is a REFUSAL, not a skip: writing a
    guessed or inherited PMA figure onto a client-facing store is the whole
    class of defect this lane exists to remove.
    """
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    targets: dict[str, Target] = {}
    refusals: list[str] = []
    for code in codes:
        rec = by_code.get(code)
        if rec is None:
            refusals.append(f"{code}: absent from the canonical dataset — refusing to write a PMA figure for it")
            continue
        status = rec.get("pma_status")
        if not status:
            refusals.append(f"{code}: canonical record carries no pma_status — nothing authoritative to sync")
            continue
        targets[code] = Target(code=code, pma_status=str(status), pma_max_asing=rec.get("pma_max_asing"))
    return targets, refusals


def load_dataset(source: str) -> list[dict]:
    """Local path or URL — the same two-mode source the sibling cure tools take."""
    if source.startswith(("http://", "https://")):
        logger.info("dataset: fetching %s", source)
        with httpx.Client(timeout=120) as http:
            resp = http.get(source)
            resp.raise_for_status()
            payload = resp.json()
    else:
        logger.info("dataset: reading %s", source)
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    return payload["data"]


def qdrant_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key
    return headers


def find_points_for_code(
    http: httpx.Client, url_base: str, headers: dict[str, str], collection: str, code: str
) -> list[dict]:
    """Scroll every point in `collection` whose flat `kode_kbli` equals `code`."""
    records: list[dict] = []
    offset = None
    while True:
        body: dict[str, Any] = {
            "filter": {"must": [{"key": CODE_KEY, "match": {"value": code}}]},
            "limit": _SCROLL_PAGE_LIMIT,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset
        resp = http.post(
            f"{url_base}/collections/{collection}/points/scroll", headers=headers, json=body
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        records.extend(result.get("points", []))
        offset = result.get("next_page_offset")
        if offset is None:
            break
    return records


def build_plan(code: str, target: Target, points: list[dict]) -> CodePlan:
    """Turn scrolled points into a plan — pure, no I/O."""
    ids = [p["id"] for p in points]
    current = {
        p["id"]: {
            "pma_status": (p.get("payload") or {}).get("pma_status"),
            "pma_max_asing": (p.get("payload") or {}).get("pma_max_asing"),
        }
        for p in points
    }
    return CodePlan(code=code, target=target, point_ids=ids, current=current)


def apply_plan(
    http: httpx.Client,
    url_base: str,
    headers: dict[str, str],
    collection: str,
    plan: CodePlan,
    apply: bool,
) -> int:
    """Report (always) and write (only when `apply`). Returns points written."""
    if not plan.found:
        logger.info("  %s: NOT FOUND — no point matches %s=%s", plan.code, CODE_KEY, plan.code)
        return 0

    stale = plan.stale_points()
    if not stale:
        logger.info(
            "  %s: already agrees with canonical (%s / %s)",
            plan.code,
            plan.target.pma_status,
            plan.target.pma_max_asing,
        )
        return 0

    if not isinstance(plan.target.pma_max_asing, int):
        # 47221 carries the string "special" — a non-percentage regime. Passed
        # through verbatim rather than coerced, but said out loud: a payload
        # field that changes type is exactly what a downstream reader does not
        # expect, and a silent coercion here would invent a number.
        logger.warning(
            "  %s: canonical cap is %r (%s), not an int — writing it verbatim",
            plan.code,
            plan.target.pma_max_asing,
            type(plan.target.pma_max_asing).__name__,
        )

    for pid in stale:
        cur = plan.current.get(pid, {})
        logger.info(
            "  %s: point %s  %s/%s -> %s/%s%s",
            plan.code,
            pid,
            cur.get("pma_status"),
            cur.get("pma_max_asing"),
            plan.target.pma_status,
            plan.target.pma_max_asing,
            "" if apply else "  (dry-run, not written)",
        )

    if not apply:
        return 0

    resp = http.post(
        f"{url_base}/collections/{collection}/points/payload",
        headers=headers,
        json={
            "payload": {
                "pma_status": plan.target.pma_status,
                "pma_max_asing": plan.target.pma_max_asing,
            },
            "points": stale,
        },
    )
    resp.raise_for_status()
    return len(stale)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--codes",
        required=True,
        help="comma-separated KBLI codes to sync (never auto-discovered or swept)",
    )
    ap.add_argument(
        "--collection",
        required=True,
        help="physical Qdrant collection, e.g. kbli_2025_final_hybrid. Mandatory on "
        "purpose: a default here would freeze a measure of the world into a constant.",
    )
    ap.add_argument("--dataset", default=DATASET_URL, help="canonical dataset: local path or URL")
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        logger.error("--codes produced an empty list, nothing to do")
        return 2

    targets, refusals = build_targets(load_dataset(args.dataset), codes)
    if refusals:
        for r in refusals:
            logger.error("REFUSED %s", r)
        logger.error("refusing the whole run — nothing written")
        return 2

    url_base = os.environ["QDRANT_URL"].rstrip("/")
    headers = qdrant_headers(os.environ.get("QDRANT_API_KEY"))

    written = 0
    found = 0
    agreed = 0
    with httpx.Client(timeout=60) as http:
        plans = []
        for code in codes:
            points = find_points_for_code(http, url_base, headers, args.collection, code)
            plans.append(build_plan(code, targets[code], points))

        if not any(p.found for p in plans):
            # A collection that does not carry `kode_kbli` returns a clean zero
            # for every code, including ones you know exist. Never report that
            # as "nothing to do".
            logger.error(
                "not one of the %d requested codes matched a point in %r on key %r — "
                "wrong collection? (the KBLI points live in kbli_2025_final_hybrid)",
                len(codes),
                args.collection,
                CODE_KEY,
            )
            return 2

        for plan in plans:
            if plan.found:
                found += 1
                if not plan.stale_points():
                    agreed += 1
            written += apply_plan(http, url_base, headers, args.collection, plan, args.apply)

    verb = "APPLIED" if args.apply else "DRY-RUN"
    logger.info(
        "%s: %d/%d code(s) found | %d already agreed | %d point(s) %s",
        verb,
        found,
        len(codes),
        agreed,
        written if args.apply else sum(len(p.stale_points()) for p in plans if p.found),
        "written" if args.apply else "would be written",
    )
    if not args.apply:
        logger.info("dry-run complete — rerun with --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
