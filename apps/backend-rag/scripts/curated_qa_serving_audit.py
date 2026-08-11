#!/usr/bin/env python3
"""Report curated_qa points production SERVES that no corpus row explains.

WHY THIS EXISTS
---------------
`curated_qa_drift_report.py` compares the corpus on disk against its
manifests. That is the whole picture only if the collection contains exactly
what the manifests describe. It does not.

Measured against prod on 2026-08-11: the `curated_qa` collection holds **808
points**; **396** map to a row in `data/curated_qa/*.jsonl`; the remaining
**412 map to nothing on disk** — all `domain=visa`, all `source_date` in
2026-07, 61 of them in the verbatim class `JELAS`. They carry none of the
Phase-0 payload fields (`batch_id`, `active`, `invalidated_at`,
`verbatim_eligible`, `client_specific`), so they predate that schema, and no
manifest references them (`curated_qa_drift_report` reports zero
`source_missing`).

Two facts make that a governance gap rather than harmless archaeology, and
both are quoted from the code, not inferred:

1. **They are served.** `orchestrator_core._inject_curated_qa_grounding`
   filters with `metadata.get("active", True) is False` — a MISSING `active`
   field means active, deliberately ("a pre-Phase-0 point written before this
   rail existed — treated as active, not silently dropped"). Every one of the
   412 lacks the field.
2. **They cannot be withdrawn.** `curated_qa_regen_trigger.quarantine_row`
   takes a corpus ROW and derives the point id from it
   (`_stable_point_id(question, domain)`). A point with no row on disk can
   never be selected, so a regulatory delta can invalidate the 396 tracked
   answers and leave anything untracked serving the superseded fact forever.

So the corpus README's claim that the on-disk files are "the audit trail
behind the safety invariant" holds for 396 of 808 points. This script is what
makes the other half countable.

NOT a hypothesis this script tested and confirmed: an earlier guess that the
412 were id-derivation twins of the current rows (the `domain:` prefix was
added to the digest later, as `_stable_point_id`'s FATAL-1 note records) was
REFUTED — recomputing every disk row under three older derivations matched
zero live points. They are different questions, not old copies of these ones.

Pure reporter — it never writes, never deletes, never flags a point.
Withdrawing or re-homing an orphan is a judgment call about vetted client
content, not something a scan should do on its own.

    python scripts/curated_qa_serving_audit.py            # human summary
    python scripts/curated_qa_serving_audit.py --json     # machine-readable

Exit codes (bitwise, fail-visible):
    0  every served point maps to a corpus row, and every row is served
    1  orphans: points served with no reviewable source  (--strict, else advisory)
    2  corpus rows that production does NOT serve — always non-zero: the
       corpus claims grounding coverage the bot does not actually have
    4  CANNOT VERIFY — no corpus, or the collection could not be read in full.
       Never reported as clean: zero points traversed is not evidence of
       health, and a scroll that stops at page one under-reports by design.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The id rule is IMPORTED, never re-implemented: an audit that derives point
# ids its own way stops agreeing with the harvester the day the harvester
# changes, and would then report the whole corpus as orphaned.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.curated_qa_harvest import (
    _CURATED_QA_COLLECTION_NAME,
    _stable_point_id,
)

EXIT_OK = 0
EXIT_ORPHANS = 1
EXIT_ROWS_NOT_SERVED = 2
EXIT_CANNOT_VERIFY = 4

VERBATIM_CLASS = "JELAS"

# Mirrors orchestrator_core._inject_curated_qa_grounding: a point is excluded
# from grounding ONLY by an explicit `active is False`. Missing = served.
_SERVED_UNLESS_EXPLICITLY_INACTIVE = True


@dataclass
class Audit:
    served_points: int = 0
    matched: int = 0
    orphans: int = 0
    orphans_reachable: int = 0  # orphan AND served (not explicitly inactive)
    rows_on_disk: int = 0
    rows_not_served: list[str] = field(default_factory=list)
    orphan_domains: dict[str, int] = field(default_factory=dict)
    orphan_classes: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _point_is_served(payload: dict[str, Any]) -> bool:
    """A point reaches grounding unless it is EXPLICITLY flagged inactive.

    Written to match the read path rather than to be strict: the whole point
    of this audit is what production actually serves, so it has to inherit
    the read path's default, not a safer-looking one of its own.
    """
    return payload.get("active", _SERVED_UNLESS_EXPLICITLY_INACTIVE) is not False


def _load_disk_rows(corpus_dir: Path) -> tuple[dict[str, str], list[str]]:
    """Return ({point_id: "<domain>/<question head>"}, problems)."""
    problems: list[str] = []
    if not corpus_dir.is_dir():
        return {}, [f"corpus dir not found: {corpus_dir}"]

    ids: dict[str, str] = {}
    files = sorted(corpus_dir.glob("*.jsonl"))
    if not files:
        return {}, [f"no *.jsonl under {corpus_dir} — nothing to attribute points to"]

    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                problems.append(f"{path.name}: unparseable line (corpus is not valid JSONL)")
                continue
            question = rec.get("question")
            domain = rec.get("domain")
            if not question or not domain:
                problems.append(f"{path.name}: row without question/domain — cannot be attributed")
                continue
            ids[_stable_point_id(question, domain)] = f"{domain}/{str(question)[:60]}"
    return ids, problems


async def scroll_all(
    post: Callable[[str, dict], Awaitable[Any]],
    collection: str,
    *,
    page_size: int = 256,
    max_pages: int = 10_000,
) -> tuple[list[dict], list[str]]:
    """Read EVERY point's payload, following `next_page_offset`.

    A single scroll call returns one page. Reading that page as if it were
    the collection is how a partial list gets consumed as a complete one, and
    here it would silently under-report orphans — so exhausting the cursor is
    the contract, and hitting `max_pages` is a PROBLEM (exit 4), never a
    quietly truncated answer.
    """
    points: list[dict] = []
    problems: list[str] = []
    offset: Any = None
    for _ in range(max_pages):
        body: dict[str, Any] = {
            "limit": page_size,
            "with_payload": True,
            "with_vectors": False,
        }
        if offset is not None:
            body["offset"] = offset
        try:
            resp = await post(f"/collections/{collection}/points/scroll", body)
            resp.raise_for_status()
            result = resp.json().get("result") or {}
        except Exception as exc:
            problems.append(f"scroll failed after {len(points)} point(s): {type(exc).__name__}")
            return points, problems
        page = result.get("points") or []
        points.extend(page)
        offset = result.get("next_page_offset")
        if offset is None or not page:
            return points, problems
    problems.append(f"scroll did not terminate within {max_pages} pages — result is partial")
    return points, problems


def audit(points: list[dict], disk_ids: dict[str, str]) -> Audit:
    out = Audit(served_points=len(points), rows_on_disk=len(disk_ids))
    domains: collections.Counter[str] = collections.Counter()
    classes: collections.Counter[str] = collections.Counter()
    seen_ids: set[str] = set()

    for point in points:
        pid = str(point.get("id"))
        seen_ids.add(pid)
        payload = point.get("payload") or {}
        if pid in disk_ids:
            out.matched += 1
            continue
        out.orphans += 1
        if _point_is_served(payload):
            out.orphans_reachable += 1
        domains[str(payload.get("domain"))] += 1
        classes[str(payload.get("confidence_class"))] += 1

    out.rows_not_served = sorted(label for pid, label in disk_ids.items() if pid not in seen_ids)
    out.orphan_domains = dict(domains.most_common())
    out.orphan_classes = dict(classes.most_common())
    return out


def render(a: Audit) -> str:
    lines = [
        f"curated_qa serving audit — {a.served_points} point(s) in the collection, "
        f"{a.rows_on_disk} row(s) on disk: matched={a.matched} orphan={a.orphans} "
        f"rows_not_served={len(a.rows_not_served)}"
    ]
    if a.orphans:
        lines += [
            "",
            f"  ORPHANS — {a.orphans} served point(s) no corpus row explains, of which",
            f"  {a.orphans_reachable} reach grounding (not flagged inactive). They cannot be",
            "  reviewed (no file), and quarantine_row() derives its target from a corpus",
            "  row, so a regulatory delta can never withdraw them.",
            f"    by domain: {a.orphan_domains}",
            f"    by class:  {a.orphan_classes}",
        ]
        verbatim = a.orphan_classes.get(VERBATIM_CLASS, 0)
        if verbatim:
            lines.append(
                f"    {verbatim} are {VERBATIM_CLASS} — the class that carries verbatim"
                " eligibility when harvested."
            )
    if a.rows_not_served:
        lines += [
            "",
            f"  NOT SERVED — {len(a.rows_not_served)} vetted row(s) exist on disk but no",
            "  point answers to them: the corpus claims coverage the bot does not have.",
        ]
        lines += [f"    {label}" for label in a.rows_not_served[:20]]
        if len(a.rows_not_served) > 20:
            lines.append(f"    … and {len(a.rows_not_served) - 20} more")
    for problem in a.problems:
        lines.append(f"  CANNOT VERIFY: {problem}")
    if not a.orphans and not a.rows_not_served and not a.problems and a.served_points:
        lines.append("  every served point maps to a corpus row, and every row is served.")
    return "\n".join(lines)


async def run(corpus_dir: Path, collection: str) -> Audit:
    disk_ids, problems = _load_disk_rows(corpus_dir)
    if problems and not disk_ids:
        a = Audit()
        a.problems = problems
        return a

    from backend.core.qdrant_db import QdrantClient

    client = QdrantClient(collection_name=collection)
    try:
        http = await client._get_client()

        async def post(url: str, body: dict) -> Any:
            return await http.post(url, json=body)

        points, scroll_problems = await scroll_all(post, collection)
    finally:
        await client.close()

    a = audit(points, disk_ids)
    a.problems = problems + scroll_problems
    if not points:
        a.problems.append(f"zero points read from '{collection}' — not evidence of health")
    return a


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--corpus-dir",
        default=str(Path(__file__).resolve().parents[1] / "data" / "curated_qa"),
        help="directory holding the *.jsonl corpus (ops-populated; empty in a worktree)",
    )
    ap.add_argument("--collection", default=_CURATED_QA_COLLECTION_NAME)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on orphans too")
    args = ap.parse_args(argv)

    a = asyncio.run(run(Path(args.corpus_dir), args.collection))

    if args.json:
        print(
            json.dumps(
                {
                    "served_points": a.served_points,
                    "rows_on_disk": a.rows_on_disk,
                    "matched": a.matched,
                    "orphans": a.orphans,
                    "orphans_reachable": a.orphans_reachable,
                    "rows_not_served": a.rows_not_served,
                    "orphan_domains": a.orphan_domains,
                    "orphan_classes": a.orphan_classes,
                    "problems": a.problems,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(render(a))

    code = EXIT_OK
    if a.problems:
        code |= EXIT_CANNOT_VERIFY
    if a.rows_not_served:
        code |= EXIT_ROWS_NOT_SERVED
    if args.strict and a.orphans:
        code |= EXIT_ORPHANS
    return code


if __name__ == "__main__":
    sys.exit(main())
