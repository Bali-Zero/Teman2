"""
kg_fix_68112_node.py — surgical cure for the `kbli:68112` Postgres KG node
(Fase 1 pilot A1, GO given by Zero 2026-07-16 — see
`.claude/skills/kbli-navigator/SKILL.md` §1 LIVE STATE).

WHY (2026-07-17): PR #2508/#2527 (merged 2026-07-16) corrected the CANONICAL
dataset for KBLI 68112 (`per_skala -> []`, `per_skala_disputed_pp28_mice`
audit key, corrected `intel_2026.whatYouNeed`, `_data_note`) — but the
Postgres Knowledge Graph node `kbli:68112` is a SEPARATE datastore that
dataset-level fix never touched (same root cause `kg_kbli_resync.py`
already documents: "the KG was loaded from a pre-#2164 snapshot ... has no
generator left in the repo"). A live read (dev Postgres, 2026-07-17 — prod
is NOT reachable from this headless session, see the companion report at
`research/operations/2026-07-17-kbli-68112-node-cure.md` for that boundary)
found the KG node still carrying THREE separate contamination points, all
traceable to the same pre-#2508 code-number collision (68112 = residential
leasing under BPS Peraturan 7/2025, current; a DIFFERENT activity,
"Penyewaan Venue Penyelenggaraan Aktifitas MICE dan Event Khusus", carries
the same number 68112 under PP 28/2025's older KBLI-2020 numbering — see
`scripts/tests/test_kbli_68112_pp28_mice_collision.py` for the full,
image-verified regulatory chain):

  1. `kbli:68112.properties.uraian` — stale, bleeds into the UNRELATED 6812
     subgroup ("... 6812 AKTIVITAS REAL ESTAT (BANGUNAN DAN LAHAN)
     NONHUNIAN ..."). The router (`kbli_notebook.py`
     `props.get("uraian", node["description"])`) PREFERS this field over
     the `description` column, so even though `description` itself is
     already correct (residential), this stale value wins whenever a
     reader asks for `properties.uraian` specifically.
  2. `kbli:68112.properties.whatYouNeed` — stale, still the PRE-#2508 text
     ("Self-Assessment document covering MICE venue standards ...")
     verbatim-quoted in the dataset-level regression test's docstring as
     the ORIGINAL bug shape. `kg_kbli_resync.py` (this script's older
     sibling, already on `main`) has correct sync logic for this exact
     field (its `INTEL_KEYS` loop) — it has simply never been RE-RUN
     against prod since #2508 shipped the canonical-dataset fix (per the
     corner file: "fly apply NEVER run").
  3. Two wrong `REQUIRES` edges: `kbli:68112 -> perizinan:<agriculture>`
     ("good agriculture practices" / reports to "Menteri Pertanian",
     entirely unrelated sector) and `kbli:68112 -> perizinan:<mice>` (the
     PP28 MICE-venue block — its `properties.kewajiban` literally names
     "Penyewaan Venue Penyelenggaraan Aktifitas MICE dan Event Khusus").
     Both edges are read by `kbli_notebook.py::inspect_kbli` into the
     `licenses[].requirements` array served to balizero.com/kbli/68112's
     Licensing section (via `apps/mouth`/`apps/kbli-navigator` UIs) — the
     most direct client-facing leak of the three. A parked, UNMERGED PR
     (#2528, branch `agent/air-m5/infra/kg-68112-licenses`) already wrote
     an equivalent fix for this specific edge class
     (`per_skala == []` -> delete `REQUIRES -> perizinan:*` edges, never
     touch `REQUIRES -> company:*`) but does not cover (1)/(2) above, and
     is not merged. This script supersedes it FOR 68112 SPECIFICALLY by
     doing all three in one surgical, single-code pass; PR #2528 is left
     untouched (not merged, not superseded project-wide — that is a wider
     decision out of scope here, see the report).

Also handles the SHADOW legacy node `kbli_68112` (underscore, pre-dating the
`kbli:<code>` colon convention — 2,384 such underscore duplicates exist
system-wide as of this writing, a separate, much wider finding OUT OF SCOPE
here; see the report). Its own `description` column IS the literal MICE
text ("Penyewaan Venue Penyelenggaraan Aktifitas MICE dan Event Khusus"),
and while no currently-traced consumer reads it directly (every live query
path constructs `kbli:{code}` explicitly, never bare `{code}` or
`kbli_{code}`), KG entity resolution in
`kg_graph_nodes.py::resolve_entities_node` does a NAME-similarity
fuzzy-match (pg_trgm) that could in principle resolve this node instead of
the real one for some query phrasings — both share `entity_type='kbli'`.
Per the KG's own established conservative pattern ("orphaned perizinan:*
nodes are left in place, not deleted — deleting nodes is a separate,
higher-risk decision"), this script NEUTRALIZES the false description
(marks it `_deprecated` + points to `kbli:68112`) but does NOT delete the
row or touch its edges.

WHAT IT DOES (dry-run by default; nothing is written without --apply):

  kbli:68112 (per canonical dataset, fetched fresh from GitHub raw @ main,
  same source+URL convention as `kg_kbli_resync.py`):
    - description            <- canonical uraian (no-op in practice; the
                                 column is already correct, but kept for
                                 idempotent consistency with properties.uraian)
    - properties.uraian      <- canonical uraian (fixes the subgroup-bleed)
    - properties.{whatItMeans,whatYouNeed,baliContext,whatChanged,
      zantaraOpener}         <- canonical intel_2026.* (only PRESENT keys,
                                 never nulled — same discipline as
                                 `kg_kbli_resync.py`)
    - properties._data_note  <- canonical _data_note (if present)
    - DELETE FROM kg_edges WHERE source_entity_id='kbli:68112' AND
      relationship_type='REQUIRES' AND target_entity_id LIKE 'perizinan:%'
      — ONLY if the freshly-fetched canonical `per_skala == []` (guard
      identical in spirit to the parked `kg_kbli_license_fix.py`; refuses
      to touch edges if that ever stops being true). Edges to non-perizinan
      targets (`company:pt_pma`, `sektor:*`, etc.) are NEVER touched.

  kbli_68112 (shadow node, hardcoded neutralization, no canonical lookup —
  there is nothing canonical to sync it FROM, it is being retired, not
  corrected-to-match):
    - description            <- SHADOW_DEPRECATION_NOTICE (honest pointer +
                                 explanation, no invented "correct" content —
                                 per the KG's own "no new licensing values
                                 without provenance" rule applied to prose)
    - properties._deprecated = true
    - properties._superseded_by = "kbli:68112"
    - properties._data_note  <- explanation (see SHADOW_DEPRECATION_NOTICE)
    - edges: left untouched (out of surgical scope; see report)

VERIFICATION (three independent checks on the main node, one on the shadow
node — see the Codex GPT-5.6-sol red-team note below for why a single
marker scan was judged insufficient and blocked the first draft):
  1. Marker scan — same guilt+innocence markers as
     `scripts/tests/test_kbli_68112_pp28_mice_collision.py`
     (CONTAMINATION_MARKERS "MICE"/"Venue" tolerated ONLY alongside the
     DISCLAIMER_MARKER "code-number collision", excluding the intentional
     audit-preservation key if one is ever present — AUDIT_KEY_PROPERTY).
  2. Exact-match against a FRESH fetch of the canonical dataset — catches
     staleness that doesn't happen to say "MICE"/"Venue" (e.g. the
     properties.uraian subgroup-bleed text), which (1) alone would miss.
  3. Zero `REQUIRES -> perizinan:*` edges remain on kbli:68112.
  4. (shadow node only) `_deprecated`/`_superseded_by` are actually set —
     not just "no bad text", but "positively marked retired".
All four are read-only. Exits non-zero if ANY check fails, even after a
successful write — "the write succeeded" and "the cure worked" are
different claims, only the second is what --apply should be judged on.
`--verify` runs the exact same checks standalone (re-fetches canonical,
re-reads the DB, never writes) — usable any time to (re-)confirm current
DB state without touching anything.

ADVERSARIAL REVIEW (Codex GPT-5.6-sol, read-only, 2026-07-17): an earlier
draft of this script was reviewed before being committed and returned
BLOCK MERGE on: (a) a literal string bug where the shadow node's
_data_note used "code-number-collision" (extra hyphen) instead of the
DISCLAIMER_MARKER's exact "code-number collision", which meant the shadow
node could never converge to a clean verification; (b) the verification
gap this docstring's point (2) above now closes; (c) the shadow node's
_deprecated markers not being independently checked (this docstring's
point (4)); (d) the three writes not being atomic (see the `async with
conn.transaction()` wrap in `main()`); (e) a latent bug where an empty
canonical `uraian` could have written NULL over a valid existing
description (fixed — `new_description` now falls back to the CURRENT
description, never to NULL). All five were fixed in this version; see the
companion report (research/operations/2026-07-17-kbli-68112-node-cure.md)
for the full review transcript and the residual risks that were
consciously NOT expanded into this script's scope (the shadow node's own
graph edges and `name` field are left untouched — see WHAT IT DOES above).

USAGE:
    # 1. Dry run (always do this first) — connects read-only, prints the plan.
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_fix_68112_node.py"

    # 2. Apply.
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_fix_68112_node.py --apply"

    # 3. Re-running --apply again is idempotent (converges to 0 changes,
    #    verification still runs and should PASS).

    # Standalone verification (re-fetches canonical, re-reads DB, no writes):
    fly ssh console -a nuzantara-rag -C \
        "python backend/scripts/kg_fix_68112_node.py --verify"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kg_fix_68112_node")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

CODE = "68112"
CANONICAL_ENTITY_ID = f"kbli:{CODE}"
SHADOW_ENTITY_ID = f"kbli_{CODE}"

# Same field list as kg_kbli_resync.py's INTEL_KEYS — kept as a separate
# literal here (not imported) so this script stays a single, self-contained
# file runnable via `fly ssh console` with no local package-relative import
# surprises, mirroring the sibling scripts' own convention.
INTEL_KEYS = ("whatItMeans", "whatYouNeed", "baliContext", "whatChanged", "zantaraOpener")

# Guilt+innocence markers reused VERBATIM from
# scripts/tests/test_kbli_68112_pp28_mice_collision.py so the dataset-side
# and KG-side guards agree on what "clean" means for this exact collision.
CONTAMINATION_MARKERS = ("MICE", "Venue")
DISCLAIMER_MARKER = "code-number collision"

SHADOW_DEPRECATION_NOTICE = (
    "[DEPRECATED legacy duplicate entity_id — superseded by kbli:68112, "
    "code-number collision cure 2026-07-17] This node predates the "
    "kbli:<code> colon convention. Its original description named the "
    "PP28/2025 MICE-venue-rental activity that shares the number 68112 "
    "under PP28's older KBLI-2020 numbering — a pure code-number "
    "collision, not the same business activity as KBLI 2025's "
    "residential-leasing 68112. See kbli:68112 for the current, correct "
    "record. Left in place (not deleted) for audit continuity; see "
    "research/operations/2026-07-17-kbli-68112-node-cure.md."
)

SHADOW_DATA_NOTE = (
    "Legacy pre-colon-convention duplicate of kbli:68112, neutralized "
    "2026-07-17 (was carrying the PP28 MICE-venue code-number collision "
    "description as if it were this code's own activity)."
)

# Mirrors test_kbli_68112_pp28_mice_collision.py's AUDIT_KEY exclusion: an
# intentional audit-preservation key is allowed to name MICE/Venue without a
# disclaimer (it exists precisely to keep the original text for the record).
# Not currently written by this script into kg_nodes.properties (verified:
# plan_main_node_fix only ever sets uraian/INTEL_KEYS/_data_note) — kept here
# defensively in case a future sync (e.g. the parked kg_kbli_license_fix.py,
# or a wider Filiera-driven KG rebuild) ever mirrors the dataset's audit key
# into KG properties too, so this verifier doesn't false-fail on it.
AUDIT_KEY_PROPERTY = "per_skala_disputed_pp28_mice"


# ============================================================================
# Pure planning functions — no I/O, unit-testable
# (backend/tests/unit/scripts/test_kg_fix_68112_node.py)
# ============================================================================


@dataclass
class NodeFixPlan:
    entity_id: str
    exists: bool
    update_node: bool
    new_description: str | None
    new_properties: dict | None
    delete_requires_perizinan_edges: bool
    skip_reason: str | None = None


@dataclass
class ShadowFixPlan:
    entity_id: str
    exists: bool
    update_node: bool
    new_description: str | None
    new_properties: dict | None


def plan_main_node_fix(record: dict | None, kg_row: dict | None) -> NodeFixPlan:
    """Pure decision function for `kbli:68112`.

    `record` = canonical dataset row for 68112 (or None if the fetch/parse
    somehow returns nothing — treated as an abort, this script never
    guesses at licensing/descriptive text).
    `kg_row` = {"description": str, "properties": dict} from `kg_nodes` (or
    None if the row doesn't exist in this Postgres).
    """
    if record is None:
        return NodeFixPlan(
            CANONICAL_ENTITY_ID,
            kg_row is not None,
            False,
            None,
            None,
            False,
            "canonical dataset fetch/parse returned no 68112 record",
        )
    if kg_row is None:
        return NodeFixPlan(
            CANONICAL_ENTITY_ID,
            False,
            False,
            None,
            None,
            False,
            "kbli:68112 not present in this kg_nodes table",
        )

    uraian = (record.get("uraian") or "").strip()
    intel = record.get("intel_2026") or {}
    data_note = record.get("_data_note")
    per_skala = record.get("per_skala")
    per_skala_empty = per_skala == []

    old_props = kg_row["properties"] or {}
    new_props = dict(old_props)
    if uraian:
        new_props["uraian"] = uraian
    for k in INTEL_KEYS:
        v = intel.get(k)
        if v:
            new_props[k] = v
    if data_note:
        new_props["_data_note"] = data_note

    description_stale = bool(uraian) and kg_row["description"] != uraian
    props_stale = new_props != old_props
    update_node = description_stale or props_stale

    # Never let an empty/missing canonical uraian translate into writing NULL
    # over a perfectly good existing description (Codex red-team finding,
    # 2026-07-17: `new_description=None` used to mean "write NULL" in the SQL
    # path whenever update_node was True for a properties-only change while
    # uraian happened to be empty). Falling back to the CURRENT description
    # makes this a true no-op on that field instead of a regression.
    new_description = uraian if uraian else kg_row["description"]

    return NodeFixPlan(
        entity_id=CANONICAL_ENTITY_ID,
        exists=True,
        update_node=update_node,
        new_description=new_description if update_node else None,
        new_properties=new_props if update_node else None,
        delete_requires_perizinan_edges=per_skala_empty,
        skip_reason=(
            None
            if per_skala_empty
            else (
                "canonical per_skala is non-empty — refusing to touch REQUIRES "
                "edges (expected [] for 68112 per PR #2508/#2527; re-verify "
                "before applying, the dataset may have changed since this "
                "script was written)"
            )
        ),
    )


def plan_shadow_node_fix(kg_row: dict | None) -> ShadowFixPlan:
    """Pure decision function for the `kbli_68112` shadow node.

    No canonical lookup — there is nothing to sync it FROM (it is being
    retired/neutralized, not corrected-to-match). Idempotent: a row already
    carrying the deprecation marker plans no further change.
    """
    if kg_row is None:
        return ShadowFixPlan(SHADOW_ENTITY_ID, False, False, None, None)

    old_props = kg_row["properties"] or {}
    already_deprecated = (
        kg_row["description"] == SHADOW_DEPRECATION_NOTICE
        and old_props.get("_deprecated") is True
        and old_props.get("_superseded_by") == CANONICAL_ENTITY_ID
    )
    if already_deprecated:
        return ShadowFixPlan(SHADOW_ENTITY_ID, True, False, None, None)

    new_props = dict(old_props)
    new_props["_deprecated"] = True
    new_props["_superseded_by"] = CANONICAL_ENTITY_ID
    new_props["_data_note"] = SHADOW_DATA_NOTE

    return ShadowFixPlan(
        entity_id=SHADOW_ENTITY_ID,
        exists=True,
        update_node=True,
        new_description=SHADOW_DEPRECATION_NOTICE,
        new_properties=new_props,
    )


def _field_is_contaminated(value: str) -> bool:
    """True if `value` asserts MICE/Venue licensing with no disclaimer.

    Same rule as test_68112_record_has_no_mice_venue_outside_audit_key: a
    marker's presence is fine IF the disclaiming phrase is in the same
    string (explaining the collision), never fine bare (asserting it).
    """
    if not any(marker in value for marker in CONTAMINATION_MARKERS):
        return False
    return DISCLAIMER_MARKER not in value.lower()


def verify_node_clean(description: str, properties: dict) -> list[str]:
    """Return a list of problems (empty = clean) for one kg_nodes row.

    Walks description + every string leaf of properties (mirrors the
    dataset-level whole-record guard's `_iter_leaf_strings`), EXCLUDING the
    audit-preservation key (mirrors that guard's own `AUDIT_KEY` exclusion —
    see AUDIT_KEY_PROPERTY above).

    NOTE (Codex red-team, 2026-07-17): this is a MARKER scan, not a
    canonical-equivalence check — it catches the MICE/Venue-flavored
    contamination but would NOT by itself catch a differently-worded stale
    value (e.g. the properties.uraian subgroup-bleed text, which contains
    neither "MICE" nor "Venue"). `verify_main_node_matches_canonical` below
    closes that gap for the one field class this script actually writes;
    this function stays useful on its own for the shadow node (which has no
    canonical counterpart to compare against) and as a defense-in-depth
    second signal on the main node.
    """
    problems: list[str] = []
    if _field_is_contaminated(description or ""):
        problems.append(f"description still contaminated: {description!r}")

    def _walk(obj, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if not path and k == AUDIT_KEY_PROPERTY:
                    continue  # intentional audit-preservation key, never judged
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _walk(v, f"{path}[{i}]")
        elif isinstance(obj, str) and _field_is_contaminated(obj):
            problems.append(f"properties.{path} still contaminated: {obj!r}")

    _walk(properties or {}, "")
    return problems


def verify_main_node_matches_canonical(record: dict, kg_row: dict) -> list[str]:
    """Exact-match check for kbli:68112 against the fetched canonical record.

    Added in response to Codex red-team (2026-07-17): the marker scan alone
    cannot detect a stale value that doesn't happen to say "MICE"/"Venue"
    (e.g. the uraian subgroup-bleed text). This asserts the fields THIS
    script actually writes are byte-equal to canonical, not just
    "un-contaminated by this one collision's vocabulary".
    """
    problems: list[str] = []
    uraian = (record.get("uraian") or "").strip()
    intel = record.get("intel_2026") or {}
    props = kg_row["properties"] or {}

    if uraian and kg_row["description"] != uraian:
        problems.append(f"description does not match canonical uraian: {kg_row['description']!r}")
    if uraian and props.get("uraian") != uraian:
        problems.append(f"properties.uraian does not match canonical uraian: {props.get('uraian')!r}")
    for k in INTEL_KEYS:
        v = intel.get(k)
        if v and props.get(k) != v:
            problems.append(f"properties.{k} does not match canonical intel_2026.{k}")
    return problems


def verify_shadow_node_deprecated(kg_row: dict) -> list[str]:
    """Assert the shadow node's deprecation markers are actually set — the
    marker scan alone would PASS a row that has neutral text but was never
    actually tagged `_deprecated`/`_superseded_by` (Codex red-team finding)."""
    problems: list[str] = []
    props = kg_row["properties"] or {}
    if kg_row["description"] != SHADOW_DEPRECATION_NOTICE:
        problems.append("description does not match SHADOW_DEPRECATION_NOTICE")
    if props.get("_deprecated") is not True:
        problems.append("properties._deprecated is not True")
    if props.get("_superseded_by") != CANONICAL_ENTITY_ID:
        problems.append(f"properties._superseded_by != {CANONICAL_ENTITY_ID!r}")
    return problems


# ============================================================================
# I/O — dataset fetch + DB
# ============================================================================


async def fetch_canonical_record() -> dict | None:
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(DATASET_URL)
        r.raise_for_status()
        dataset = r.json()["data"]
    return next((rec for rec in dataset if str(rec.get("kode_kbli_2025")) == CODE), None)


async def _fetch_kg_row(conn: asyncpg.Connection, entity_id: str) -> dict | None:
    row = await conn.fetchrow(
        "SELECT entity_id, description, properties FROM kg_nodes WHERE entity_id = $1",
        entity_id,
    )
    if row is None:
        return None
    props = json.loads(row["properties"]) if isinstance(row["properties"], str) else row["properties"]
    return {"description": row["description"], "properties": props or {}}


async def _fetch_requires_perizinan_edges(conn: asyncpg.Connection, entity_id: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT target_entity_id FROM kg_edges "
        "WHERE source_entity_id = $1 AND relationship_type = 'REQUIRES' "
        "AND target_entity_id LIKE 'perizinan:%'",
        entity_id,
    )
    return [r["target_entity_id"] for r in rows]


async def run_verification(conn: asyncpg.Connection) -> bool:
    """Re-read both nodes + kbli:68112's REQUIRES->perizinan edges, re-fetch
    canonical, print a PASS/FAIL report. Returns True iff everything is
    clean. Read-only (network GET + SELECTs) — never writes.

    Three independent checks on the main node (Codex red-team, 2026-07-17:
    the marker scan alone was not sufficient — see verify_node_clean's
    docstring): marker scan, exact-match against canonical, and (separately)
    the edge check. All three must pass.
    """
    ok = True

    record = await fetch_canonical_record()
    if record is None:
        logger.error("VERIFY FAIL: canonical dataset fetch/parse returned no 68112 record")
        ok = False

    main_row = await _fetch_kg_row(conn, CANONICAL_ENTITY_ID)
    if main_row is None:
        logger.error("VERIFY FAIL: %s not found in kg_nodes", CANONICAL_ENTITY_ID)
        ok = False
    else:
        problems = verify_node_clean(main_row["description"], main_row["properties"])
        if problems:
            ok = False
            for p in problems:
                logger.error("VERIFY FAIL %s: %s", CANONICAL_ENTITY_ID, p)
        else:
            logger.info("VERIFY PASS %s: no uncorroborated MICE/Venue text", CANONICAL_ENTITY_ID)

        if record is not None:
            canon_problems = verify_main_node_matches_canonical(record, main_row)
            if canon_problems:
                ok = False
                for p in canon_problems:
                    logger.error("VERIFY FAIL %s: %s", CANONICAL_ENTITY_ID, p)
            else:
                logger.info("VERIFY PASS %s: description/properties match canonical", CANONICAL_ENTITY_ID)

    edges = await _fetch_requires_perizinan_edges(conn, CANONICAL_ENTITY_ID)
    if edges:
        ok = False
        logger.error(
            "VERIFY FAIL %s: still has %d REQUIRES->perizinan:* edge(s): %s",
            CANONICAL_ENTITY_ID,
            len(edges),
            edges,
        )
    else:
        logger.info("VERIFY PASS %s: zero REQUIRES->perizinan:* edges", CANONICAL_ENTITY_ID)

    shadow_row = await _fetch_kg_row(conn, SHADOW_ENTITY_ID)
    if shadow_row is None:
        logger.info("VERIFY SKIP %s: not present (nothing to neutralize)", SHADOW_ENTITY_ID)
    else:
        problems = verify_node_clean(shadow_row["description"], shadow_row["properties"])
        dep_problems = verify_shadow_node_deprecated(shadow_row)
        if problems or dep_problems:
            ok = False
            for p in problems + dep_problems:
                logger.error("VERIFY FAIL %s: %s", SHADOW_ENTITY_ID, p)
        else:
            logger.info(
                "VERIFY PASS %s: neutralized (no uncorroborated MICE/Venue text, "
                "_deprecated markers present)",
                SHADOW_ENTITY_ID,
            )

    return ok


# ============================================================================
# Main
# ============================================================================


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--verify",
        action="store_true",
        help="run ONLY the post-cure verification checks (re-fetches canonical "
        "+ re-reads DB, never writes)",
    )
    args = ap.parse_args()

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        if args.verify:
            clean = await run_verification(conn)
            logger.info("VERIFY %s", "PASS" if clean else "FAIL")
            return 0 if clean else 1

        record = await fetch_canonical_record()
        main_row = await _fetch_kg_row(conn, CANONICAL_ENTITY_ID)
        shadow_row = await _fetch_kg_row(conn, SHADOW_ENTITY_ID)

        main_plan = plan_main_node_fix(record, main_row)
        shadow_plan = plan_shadow_node_fix(shadow_row)

        mode = "APPLY" if args.apply else "DRY-RUN"
        logger.info("=== %s: kbli:68112 node cure ===", mode)

        if main_plan.skip_reason and not main_plan.update_node:
            logger.warning("SKIP %s: %s", CANONICAL_ENTITY_ID, main_plan.skip_reason)
        else:
            logger.info(
                "%s node update=%s edges_delete=%s%s",
                CANONICAL_ENTITY_ID,
                main_plan.update_node,
                main_plan.delete_requires_perizinan_edges,
                f" (skip_reason={main_plan.skip_reason!r})" if main_plan.skip_reason else "",
            )
            if main_plan.update_node:
                before_props = (main_row or {}).get("properties", {})
                for k in ("uraian", *INTEL_KEYS, "_data_note"):
                    old_v = before_props.get(k)
                    new_v = (main_plan.new_properties or {}).get(k)
                    if old_v != new_v:
                        logger.info(
                            "  properties.%s: %s -> %s",
                            k,
                            (old_v[:80] + "...") if isinstance(old_v, str) and len(old_v) > 80 else old_v,
                            (new_v[:80] + "...") if isinstance(new_v, str) and len(new_v) > 80 else new_v,
                        )

        if main_plan.delete_requires_perizinan_edges:
            edges = await _fetch_requires_perizinan_edges(conn, CANONICAL_ENTITY_ID)
            for target in edges:
                logger.info("  %s: would DELETE REQUIRES -> %s", CANONICAL_ENTITY_ID, target)

        if shadow_plan.exists and shadow_plan.update_node:
            logger.info(
                "%s node update=True (neutralizing MICE description, marking _deprecated)",
                SHADOW_ENTITY_ID,
            )
        elif shadow_plan.exists:
            logger.info("%s already neutralized — no-op", SHADOW_ENTITY_ID)
        else:
            logger.info("%s not present — nothing to neutralize", SHADOW_ENTITY_ID)

        if args.apply:
            # All writes in ONE transaction (Codex red-team, 2026-07-17: three
            # separate autocommit statements meant a mid-way failure left a
            # partial cure — e.g. edges deleted but properties not yet synced,
            # or vice versa — with no rollback). Either everything below lands
            # together or nothing does.
            async with conn.transaction():
                if main_plan.update_node:
                    await conn.execute(
                        "UPDATE kg_nodes SET description = $2, properties = $3::jsonb, "
                        "updated_at = now() WHERE entity_id = $1",
                        CANONICAL_ENTITY_ID,
                        main_plan.new_description,
                        json.dumps(main_plan.new_properties, ensure_ascii=False),
                    )
                if main_plan.delete_requires_perizinan_edges:
                    await conn.execute(
                        "DELETE FROM kg_edges WHERE source_entity_id = $1 "
                        "AND relationship_type = 'REQUIRES' AND target_entity_id LIKE 'perizinan:%'",
                        CANONICAL_ENTITY_ID,
                    )
                if shadow_plan.exists and shadow_plan.update_node:
                    await conn.execute(
                        "UPDATE kg_nodes SET description = $2, properties = $3::jsonb, "
                        "updated_at = now() WHERE entity_id = $1",
                        SHADOW_ENTITY_ID,
                        shadow_plan.new_description,
                        json.dumps(shadow_plan.new_properties, ensure_ascii=False),
                    )

            logger.info("=== APPLIED (transaction committed) — running post-apply verification ===")
            clean = await run_verification(conn)
            logger.info("VERIFY %s", "PASS" if clean else "FAIL")
            return 0 if clean else 1

        logger.info("dry-run complete — rerun with --apply to write")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
