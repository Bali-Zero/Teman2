"""
kg_kbli_contradicted_obligations.py — detach the `kg_edges` REQUIRES rows whose
target node states obligations (`properties.kewajiban`) that CANONICAL does not
attribute to that KBLI code.

WHY (2026-08-05, live finding): `kbli_notebook.py:466` renders each REQUIRES
target's `properties.kewajiban` verbatim as the code's `requirements`, so a
wrongly-attached target tells a client to do something the law does not ask of
their business. Measured on prod before this script existed:

  * `perizinan:0bf540b11cf6` ("NIB dan Sertifikat Standar", first obligation
    "Menerapkan cara budi daya tanaman pangan yang baik (good agriculture
    practices)…") is REQUIRES-linked from **778** KBLI codes.
  * `perizinan:55be853cd247` ("NIB dan Izin", first obligation "Menerapkan
    teknologi pembukaan lahan tanpa bakar…" — slash-and-burn-free land
    clearing) from **293**.
  * Two smaller siblings, `c7cd8d6c86e5` (36) and `41a60205c6c0` (22, whose
    single "obligation" is the bare word `skala`).

Concretely: `inspect_kbli 62110` (computer-game development) was told to apply
good agriculture practices, and `inspect_kbli 79122` (Umrah/Hajj travel agency)
to clear plantation land without burning.

THIS IS AN **EDGE** DEFECT, NOT A CANONICAL ONE. The canonical dataset is clean
for these codes — 62110 carries 6 obligations (SARA-free content, after-sales
SOP…), 79122 carries 29 (pilgrimage guides, accreditation every 5 years…). The
lie is produced by the graph edge, so the cure removes the edge and never
touches the canonical record.

RELATION TO `kg_kbli_license_fix.py` (deliberately a SEPARATE script, not a new
flag on that one): its cure is "canonical `per_skala == []` → the code has NO
licensing at all → delete EVERY REQUIRES edge of that code". That is a
whole-code verdict driven by an empty canonical block. This one is a
**per-edge** verdict driven by a NON-empty canonical block: the same code keeps
the targets canonical does support and loses only the ones it does not. On
79122 that is the difference between deleting all 6 targets and deleting the 1
that is wrong. Folding two different predicates into one entry point is how a
future reader applies the wrong one. That script's own docstring already NAMED
this population as out of its scope ("one shared agriculture-marker
`perizinan:*` node alone is REQUIRES-linked from ~68% of the KG's KBLI codes …
this script has nothing to derive a fix from"); canonical now carries per-scale
`kewajiban` for 1,341 of 1,559 codes, which is the thing to derive it from.

THE PREDICATE (pure, `edge_verdict` below — six outcomes, only ONE deletable):

  SUPPORTED                     ≥1 of the target's obligations appears in the
                                code's canonical obligations. KEEP.
  CONTRADICTED                  canonical states obligations for this code and
                                NONE of the target's appears among them.
                                DELETABLE — the only outcome that is.
  CANNOT_JUDGE_NODE_SILENT      the target states no obligations at all
                                (`license:nib`, document nodes, …). Nothing to
                                compare; this script has no opinion. KEEP.
  CANNOT_JUDGE_NODE_UNREADABLE  `kewajiban` is neither a list nor absent (a bare
                                string, a dict, …). A shape we cannot read is
                                not evidence — see `_obligation_list`. KEEP.
  CANNOT_JUDGE_CANONICAL_SILENT canonical states no obligation for this code.
                                Absence of a statement is not a denial, and
                                deleting here would remove the only obligation
                                text we hold. KEEP.
  CANNOT_JUDGE_CODE_ABSENT      the code is not in the canonical dataset. KEEP.

Both sides are compared through the SAME `_norm` (tags stripped, HTML entities
decoded, whitespace collapsed, lowercased) — one normaliser, so the two sides
cannot drift apart into disagreeing about the same string.

MEASURED SCOPE at the time of writing, this module replayed over the live graph
— **per ROW**: SUPPORTED 2,093 · CONTRADICTED 1,711 · node-silent 11,249 ·
canonical-silent 2 = 15,055. **Per (code, target) PAIR**, which is what the
DELETE acts on: 2,076 / 1,707 / 11,245 / 2 = 15,030; the 25-row difference is
duplicate rows on the same pair (17 SUPPORTED, 4 CONTRADICTED, 4 node-silent),
which is why the apply log reports rows AND pairs rather than one number. The
dangerous "delete the only obligation text we hold" class is those **2**
canonical-silent edges over 1 code, and the refusal above already covers them.
The four nodes named above account for 1,118 of the contradicted pairs; the rest
are spread over other targets, so this is a class, not four rows.

Ordering note (so a future reader is not surprised by an empty bucket): the
node-silent test runs BEFORE the code-absent one, so the 15 edges whose code is
missing from canonical report as `CANNOT_JUDGE_NODE_SILENT` — measured, all 15
point at targets that state no obligation at all. Both outcomes are KEEP, so the
label differs and the action does not.

DECLARED LIMIT (measured, not assumed): the comparison is exact-match after
normalisation, so a canonical obligation RE-WORDED in the KG reads CONTRADICTED.
490 of the 1,019 distinct obligation strings carried by contradicted targets do
appear verbatim in canonical elsewhere — the two vocabularies genuinely align —
and the other 529 are dominated by truncated/garbled extractions ("…good
agriculture practices) dan", "mengusahaka n lahan", the bare "skala"), i.e. text
canonical never states for ANY code. Against that residual risk the archive
below is the backstop: nothing is destroyed, only detached.

AUDIT PARITY (never silent-delete, same discipline as the sibling script): the
`(target, first obligation)` pairs about to be detached are archived on the
`kbli:<code>` node itself, under `properties._disputed_requires_obligations`,
BEFORE the edges go — so the removal is auditable by reading the node. Re-runs
merge into that archive by target and never blank it. Two consequences that an
earlier draft got wrong and a cross-family review caught:

  * If there is NO `kbli:<code>` node, there is nowhere to archive to, so the
    delete is REFUSED and counted, not performed with a warning. "Never
    silent-delete" has to bind on the path where archiving is impossible, or
    it is decoration.
  * Archive and delete run in ONE transaction per code. Separately committed,
    a delete that fails after the archive leaves the node asserting a
    detachment that never happened — an audit trail that lies is worse than
    no audit trail.

Target nodes are never deleted, only the edges: those nodes are shared across
many codes and several of their edges are SUPPORTED elsewhere.

CONCURRENCY (declared, not guarded): the archive is a read-modify-write of the
whole `properties` document, so two of these running at once on the same code
can lose each other's archive entries. This is an operator-run, one-at-a-time
cure; it is stated here rather than defended against.

USAGE (dry-run is the default; nothing is written without --apply):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_contradicted_obligations.py --only 79122"
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_kbli_contradicted_obligations.py --all-contradicted --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kg_kbli_contradicted_obligations")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

ARCHIVE_KEY = "_disputed_requires_obligations"

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
CANNOT_JUDGE_NODE_SILENT = "CANNOT_JUDGE_NODE_SILENT"
CANNOT_JUDGE_NODE_UNREADABLE = "CANNOT_JUDGE_NODE_UNREADABLE"
CANNOT_JUDGE_CANONICAL_SILENT = "CANNOT_JUDGE_CANONICAL_SILENT"
CANNOT_JUDGE_CODE_ABSENT = "CANNOT_JUDGE_CODE_ABSENT"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _norm(value: object) -> str:
    """Normalise one obligation string. BOTH sides of the comparison go through
    this single function — two normalisers would be two opinions about the same
    string, and the disagreement would surface as a phantom CONTRADICTED.

    Tags are stripped first, THEN entities decoded: markup goes away, and what
    survives is compared as the text a human reads. Decoding first would turn a
    literal `&lt;` back into `<` and let the tag-stripper eat the prose after it.
    Entity decoding is load-bearing, not cosmetic — 108 canonical obligation
    strings carry entities and no KG node string does, so without it the SAME
    sentence reads CONTRADICTED and the edge is deleted (measured: 0 verdicts
    flip on today's data, so this is a latent false-delete, not a live one)."""
    if not isinstance(value, str):
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip().lower()


def _obligation_list(value: object) -> list | None:
    """The obligations of one node, or None when the shape is unreadable.

    `properties.kewajiban` arrives as unvalidated JSON. A bare STRING is the
    dangerous shape: iterating it yields CHARACTERS, so a canonical set holding
    a one-letter entry would read SUPPORTED, and otherwise the whole node reads
    CONTRADICTED and gets deleted on the strength of a misparse. A shape we
    cannot read is not evidence of anything — it becomes a refusal, never a
    delete. (Measured 2026-08-05: every live value is a list or absent, so this
    is a guard against tomorrow's data, not today's.)"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return None


def canonical_obligations(record: dict | None) -> set[str] | None:
    """Union of `per_skala[*].kewajiban` for one canonical record.

    Returns None when the record itself is absent (a different verdict from "the
    record exists and states nothing", which is an empty set)."""
    if record is None:
        return None
    out: set[str] = set()
    for entry in record.get("per_skala") or []:
        for item in entry.get("kewajiban") or []:
            normalised = _norm(item)
            if normalised:
                out.add(normalised)
    return out


def edge_verdict(canon: set[str] | None, node_kewajiban: list | None) -> str:
    """Pure decision for ONE (code, target) pair — no I/O.

    `canon` is `canonical_obligations(record)`: None = code absent from the
    dataset, empty set = present but stating no obligation.
    `node_kewajiban` is the target node's raw `properties.kewajiban`.
    """
    items = _obligation_list(node_kewajiban)
    if items is None:
        return CANNOT_JUDGE_NODE_UNREADABLE
    node = [n for n in (_norm(x) for x in items) if n]
    if not node:
        return CANNOT_JUDGE_NODE_SILENT
    if canon is None:
        return CANNOT_JUDGE_CODE_ABSENT
    if not canon:
        return CANNOT_JUDGE_CANONICAL_SILENT
    if any(n in canon for n in node):
        return SUPPORTED
    return CONTRADICTED


def is_deletable(verdict: str) -> bool:
    """CONTRADICTED is the ONLY deletable outcome. Written as its own function so
    a future outcome added to `edge_verdict` is not silently swept into the
    delete set by an `!= SUPPORTED` test somewhere."""
    return verdict == CONTRADICTED


@dataclass
class CodePlan:
    code: str
    verdicts: dict[str, str] = field(default_factory=dict)  # target_entity_id -> verdict
    detach: list[str] = field(default_factory=list)  # target_entity_ids to detach
    archive: dict[str, str] = field(default_factory=dict)  # target -> first obligation

    @property
    def kept(self) -> int:
        return len(self.verdicts) - len(self.detach)


def plan_code(
    code: str,
    record: dict | None,
    targets: dict[str, list],
) -> CodePlan:
    """Pure per-code plan. `targets` maps target_entity_id -> its raw kewajiban."""
    canon = canonical_obligations(record)
    plan = CodePlan(code=code)
    for target_id, node_kewajiban in sorted(targets.items()):
        verdict = edge_verdict(canon, node_kewajiban)
        plan.verdicts[target_id] = verdict
        if is_deletable(verdict):
            plan.detach.append(target_id)
            first = next((_norm(x) for x in (node_kewajiban or []) if _norm(x)), "")
            plan.archive[target_id] = first[:300]
    return plan


def merge_archive(existing: object, additions: dict[str, str]) -> dict[str, str]:
    """Merge new detachments into whatever archive the node already carries.

    Idempotent and never blanking: an earlier run's entries survive, and a
    re-detach of the same target overwrites only its own key. A non-dict legacy
    value is preserved under a reserved key rather than dropped."""
    merged: dict[str, str] = {}
    if isinstance(existing, dict):
        merged.update({str(k): str(v) for k, v in existing.items()})
    elif existing:
        merged["_legacy"] = json.dumps(existing, ensure_ascii=False)[:300]
    merged.update(additions)
    return merged


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


async def load_dataset(source: str) -> list[dict]:
    if _looks_like_local_path(source):
        logger.info("dataset: reading local file %s", source)
        return json.loads(Path(source).read_text(encoding="utf-8"))["data"]
    logger.info("dataset: fetching %s", source)
    async with httpx.AsyncClient(timeout=60) as http:
        response = await http.get(source)
        response.raise_for_status()
        return response.json()["data"]


def _as_dict(value: object) -> dict:
    if isinstance(value, str):
        try:
            return json.loads(value) or {}
        except json.JSONDecodeError:
            return {}
    return value or {}  # type: ignore[return-value]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--only", help="comma-separated 5-digit codes")
    parser.add_argument(
        "--all-contradicted",
        action="store_true",
        help="every kbli code holding at least one CONTRADICTED edge",
    )
    parser.add_argument("--dataset", default=DATASET_URL)
    args = parser.parse_args()

    if bool(args.only) == bool(args.all_contradicted):
        logger.error("choose exactly one selector: --only <codes> OR --all-contradicted")
        return 2

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    dataset = await load_dataset(args.dataset)
    by_code = {str(r.get("kode_kbli_2025")): r for r in dataset}

    # Bound before the try so the summary after `finally` can never read an
    # unbound name on the very path where the summary matters most: a crash.
    acting: list[CodePlan] = []
    deleted_rows = 0
    unarchivable = 0

    conn = await asyncpg.connect(dsn)
    try:
        if args.only:
            wanted = [c.strip() for c in args.only.split(",") if c.strip()]
            edge_rows = await conn.fetch(
                "SELECT source_entity_id, target_entity_id FROM kg_edges "
                "WHERE relationship_type = 'REQUIRES' AND source_entity_id = ANY($1)",
                [f"kbli:{c}" for c in wanted],
            )
        else:
            edge_rows = await conn.fetch(
                "SELECT source_entity_id, target_entity_id FROM kg_edges "
                "WHERE relationship_type = 'REQUIRES' AND source_entity_id LIKE 'kbli:%'"
            )

        target_ids = sorted({r["target_entity_id"] for r in edge_rows})
        node_kewajiban: dict[str, list] = {}
        if target_ids:
            for row in await conn.fetch(
                "SELECT entity_id, properties FROM kg_nodes WHERE entity_id = ANY($1)", target_ids
            ):
                props = _as_dict(row["properties"])
                node_kewajiban[row["entity_id"]] = props.get("kewajiban") or []

        by_source: dict[str, dict[str, list]] = {}
        for row in edge_rows:
            by_source.setdefault(row["source_entity_id"], {})[row["target_entity_id"]] = (
                node_kewajiban.get(row["target_entity_id"], [])
            )

        plans = [
            plan_code(src.split(":", 1)[1], by_code.get(src.split(":", 1)[1]), targets)
            for src, targets in sorted(by_source.items())
        ]

        tally: dict[str, int] = {}
        for plan in plans:
            for verdict in plan.verdicts.values():
                tally[verdict] = tally.get(verdict, 0) + 1

        acting[:] = [p for p in plans if p.detach]
        logger.info(
            "scanned %d code(s) / %d REQUIRES edge(s) — verdicts: %s",
            len(plans),
            sum(len(p.verdicts) for p in plans),
            ", ".join(f"{k}={v}" for k, v in sorted(tally.items())),
        )
        logger.info(
            "deletable (%s only): %d edge(s) over %d code(s); the other %d edge(s) are KEPT",
            CONTRADICTED,
            sum(len(p.detach) for p in acting),
            len(acting),
            sum(len(p.verdicts) for p in plans) - sum(len(p.detach) for p in acting),
        )

        for plan in acting:
            logger.info("  %s: detach %d, keep %d", plan.code, len(plan.detach), plan.kept)
            for target_id in plan.detach:
                logger.info("    -> %s :: %s", target_id, plan.archive[target_id][:90])
            if not args.apply:
                continue

            node = await conn.fetchrow(
                "SELECT properties FROM kg_nodes WHERE entity_id = $1", f"kbli:{plan.code}"
            )
            if node is None:
                # No node means no place to archive to, and "archive BEFORE the
                # delete" is the whole audit contract — a delete here would be
                # exactly the silent-delete this script says it never does.
                # Refuse, count it, and let the summary name it.
                logger.warning(
                    "  %s: REFUSED — no kg_nodes row, so the detachment could not be "
                    "archived; edges left in place",
                    plan.code,
                )
                unarchivable += 1
                continue

            # One transaction per code: the archive and the delete it documents
            # land together or not at all. Without it a delete that fails after
            # the archive leaves the node asserting a detachment that never
            # happened — an audit trail that lies is worse than none.
            async with conn.transaction():
                props = _as_dict(node["properties"])
                props[ARCHIVE_KEY] = merge_archive(props.get(ARCHIVE_KEY), plan.archive)
                # W89 jsonb double-encoding class-guard: pre-serialise and cast
                # text->jsonb exactly once.
                await conn.execute(
                    "UPDATE kg_nodes SET properties = $2::text::jsonb, updated_at = now() "
                    "WHERE entity_id = $1",
                    f"kbli:{plan.code}",
                    json.dumps(props, ensure_ascii=False),
                )
                result = await conn.execute(
                    "DELETE FROM kg_edges WHERE source_entity_id = $1 "
                    "AND target_entity_id = ANY($2) AND relationship_type = 'REQUIRES'",
                    f"kbli:{plan.code}",
                    plan.detach,
                )
            deleted_rows += int(result.rsplit(" ", 1)[-1] or 0)
    finally:
        await conn.close()

    if args.apply and unarchivable:
        logger.warning(
            "REFUSED on %d code(s): no kg_nodes row to archive the detachment on", unarchivable
        )
    if args.apply:
        # rows can exceed pairs: 25 (code, target) pairs carry duplicate rows.
        logger.info(
            "APPLIED: %d edge ROW(s) deleted across %d pair(s) on %d code(s)",
            deleted_rows,
            sum(len(p.detach) for p in acting),
            len(acting),
        )
    else:
        logger.info("dry-run complete — rerun with --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
