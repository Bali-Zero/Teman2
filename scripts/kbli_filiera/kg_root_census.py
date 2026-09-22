"""How many KBLI nodes does the graph actually hold, and how many hold data?

WHY THIS EXISTS. The KG has no generator. Nodes named `kbli` are written by
several code paths that each build `entity_id` their own way, and only one of
them produces the form the readers query. The 2026-08-02 read-only probe
(kbli-navigator SKILL.md §5.5 "F4 — root and upkeep") measured the result once
and by hand. This script makes that measurement REPRODUCIBLE: it prints §2 of
`docs/specs/2026-09-22-kg-root-generator-spec.md` from PROD, so the next session
can re-run the numbers instead of trusting a date-stamped paragraph.

READ-ONLY. It issues one SELECT through `scripts/pg.sh` and never writes. The
cure it informs is not in this file and is not written yet — the spec prices it
and asks the owner first.

WHAT IT COUNTS. Every `kg_nodes` row with `entity_type IN ('kbli','kbli_code')`,
bucketed by the SHAPE of its `entity_id`:

    kbli_colon        `kbli:<code>`        the form every reader queries
    kbli_underscore   `kbli_<name>`        `f"{type}_{name}"`, name = the code
    kbli_kbli         `kbli_kbli_<name>`   `f"{type}_{name}"`, name = "KBLI <code>"
    bare              `<digits>`           no prefix at all
    other             anything else        free text swept up by an extractor

and, inside each bucket, by whether the node carries data (`properties->>'kode'`).
The discriminator is the finding: the shape predicts the emptiness perfectly, so
"which writer made this node" and "does this node answer a question" are the
same question asked twice.

`entity_type='kbli_code'` is included deliberately. A census that filters
`entity_type='kbli'` — as every previous one did, including the detector's own
`kg_node_presence` — cannot see those rows at all, and the id shape is not the
only axis on which this store drifted.

EXIT CODES
    0  census printed
    4  CANNOT VERIFY — `pg.sh` failed, or returned an empty snapshot

An empty snapshot is 4, never 0: "I traversed nothing" must never render as
"there is nothing there" (W84).

USAGE
    scripts/kbli_filiera/kg_root_census.py                  # via scripts/pg.sh
    scripts/kbli_filiera/kg_root_census.py --json           # machine-readable
    scripts/kbli_filiera/kg_root_census.py --snapshot s.json  # offline replay
    scripts/kbli_filiera/kg_root_census.py --emit-sql       # print the query only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PSQL_WRAPPER = REPO_ROOT / "scripts/pg.sh"

EXIT_OK = 0
EXIT_CANNOT_VERIFY = 4

FAMILY_COLON = "kbli_colon"
FAMILY_UNDERSCORE = "kbli_underscore"
FAMILY_KBLI_KBLI = "kbli_kbli"
FAMILY_BARE = "bare"
FAMILY_OTHER = "other"

#: Print order. `kbli_colon` first because it is the only family a reader can
#: use; everything below it is the same node written by a writer that did not
#: know the convention.
FAMILY_ORDER = (
    FAMILY_COLON,
    FAMILY_UNDERSCORE,
    FAMILY_KBLI_KBLI,
    FAMILY_BARE,
    FAMILY_OTHER,
)

FIVE_DIGIT = re.compile(r"^[0-9]{5}$")
ALL_DIGITS = re.compile(r"^[0-9]+$")

TOP_N = 10

#: One row per KBLI-ish node. Degrees are computed in SQL because the alternative
#: is shipping 271k edges to Python to count them; everything else the census
#: decides is decided by the pure functions below, off these fields.
CENSUS_SQL = """
SELECT coalesce(json_agg(t), '[]'::json) FROM (
  SELECT
    n.entity_id,
    n.entity_type,
    n.name,
    n.source_collection,
    n.created_at::date::text                                    AS created_on,
    jsonb_typeof(n.properties)                                  AS properties_kind,
    (jsonb_typeof(n.properties) = 'object'
       AND n.properties ? 'kode')                               AS has_kode,
    (SELECT count(*) FROM kg_edges e WHERE e.target_entity_id = n.entity_id) AS in_degree,
    (SELECT count(*) FROM kg_edges e WHERE e.source_entity_id = n.entity_id) AS out_degree
  FROM kg_nodes n
  WHERE n.entity_type IN ('kbli', 'kbli_code')
) t;
"""

#: Edges by `(node, direction, relationship_type)`. Kept as its own query rather
#: than folded into the census rows: an edge histogram is per-edge, and the
#: census is per-node. BOTH directions, because a cure that repoints only the
#: inbound edges leaves the empty node still talking — the 15,315 edges leaving
#: `kbli_kbli_*` are assertions made BY a node that knows nothing.
EDGE_SQL = """
SELECT coalesce(json_agg(t), '[]'::json) FROM (
  SELECT n.entity_id, 'in' AS direction, e.relationship_type, count(*) AS n
  FROM kg_edges e
  JOIN kg_nodes n ON n.entity_id = e.target_entity_id
  WHERE n.entity_type IN ('kbli', 'kbli_code')
  GROUP BY n.entity_id, e.relationship_type
  UNION ALL
  SELECT n.entity_id, 'out' AS direction, e.relationship_type, count(*) AS n
  FROM kg_edges e
  JOIN kg_nodes n ON n.entity_id = e.source_entity_id
  WHERE n.entity_type IN ('kbli', 'kbli_code')
  GROUP BY n.entity_id, e.relationship_type
) t;
"""


# --------------------------------------------------------------------------
# Pure
# --------------------------------------------------------------------------


def classify_family(entity_id: str) -> str:
    """Which writer's id convention made this node.

    Order matters: `kbli_kbli_01191` also matches the `kbli_` test, and reading
    it as the single-prefix family would merge the two writers into one and hide
    the double-prefix bug entirely.
    """
    if entity_id.startswith("kbli:"):
        return FAMILY_COLON
    if entity_id.startswith("kbli_kbli_"):
        return FAMILY_KBLI_KBLI
    if entity_id.startswith("kbli_"):
        return FAMILY_UNDERSCORE
    if ALL_DIGITS.match(entity_id):
        return FAMILY_BARE
    return FAMILY_OTHER


def extract_token(entity_id: str) -> str:
    """The text the writer thought was a KBLI code, with its prefix removed once.

    Stripping is not `replace("kbli:", "")`: that is a no-op on `kbli_01191` and
    would hand the caller `kbli_01191` as if it were a code. Each family is
    stripped by the prefix that family actually carries, and only once.
    """
    family = classify_family(entity_id)
    if family == FAMILY_COLON:
        return entity_id[len("kbli:") :]
    if family == FAMILY_KBLI_KBLI:
        return entity_id[len("kbli_kbli_") :]
    if family == FAMILY_UNDERSCORE:
        return entity_id[len("kbli_") :]
    return entity_id


def plan_census(rows: list[dict[str, Any]], edge_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure. Everything the census reports, computed off the two snapshots."""
    by_family: dict[str, dict[str, Any]] = {
        fam: {
            "family": fam,
            "nodes": 0,
            "with_kode": 0,
            "without_kode": 0,
            "edge_reachable": 0,
            "in_edges": 0,
            "out_edges": 0,
            "properties_kinds": Counter(),
            "entity_types": Counter(),
            "sources": Counter(),
            "first_seen": None,
            "last_seen": None,
        }
        for fam in FAMILY_ORDER
    }

    rich_tokens: set[str] = set()
    tokens_by_family: dict[str, set[str]] = defaultdict(set)
    all_tokens: set[str] = set()
    name_carries_prefix: Counter[str] = Counter()

    for row in rows:
        entity_id = row["entity_id"]
        family = classify_family(entity_id)
        bucket = by_family[family]
        bucket["nodes"] += 1
        has_kode = bool(row.get("has_kode"))
        bucket["with_kode" if has_kode else "without_kode"] += 1
        in_deg = int(row.get("in_degree") or 0)
        out_deg = int(row.get("out_degree") or 0)
        bucket["in_edges"] += in_deg
        bucket["out_edges"] += out_deg
        if in_deg or out_deg:
            bucket["edge_reachable"] += 1
        bucket["properties_kinds"][row.get("properties_kind") or "<sql-null>"] += 1
        bucket["entity_types"][row.get("entity_type") or "<sql-null>"] += 1
        bucket["sources"][row.get("source_collection") or "<sql-null>"] += 1
        created_on = row.get("created_on")
        if created_on:
            if bucket["first_seen"] is None or created_on < bucket["first_seen"]:
                bucket["first_seen"] = created_on
            if bucket["last_seen"] is None or created_on > bucket["last_seen"]:
                bucket["last_seen"] = created_on
        if (row.get("name") or "").strip().lower().startswith("kbli"):
            name_carries_prefix[family] += 1

        token = extract_token(entity_id)
        all_tokens.add(token)
        tokens_by_family[family].add(token)
        if family == FAMILY_COLON and has_kode:
            rich_tokens.add(token)

    five_digit_tokens = {t for t in all_tokens if FIVE_DIGIT.match(t)}
    phantom_tokens = sorted(five_digit_tokens - rich_tokens)

    # Duplicate families, counted as the reader meets them: how many nodes does
    # one well-formed code resolve to? The `LIMIT 5` in the notebook fallback is
    # safe exactly as long as this maximum stays below 5.
    nodes_per_token: Counter[str] = Counter()
    for row in rows:
        token = extract_token(row["entity_id"])
        if FIVE_DIGIT.match(token):
            nodes_per_token[token] += 1
    fanout = Counter(nodes_per_token.values())

    # Repointable: an empty node whose code HAS a rich twin. These are the only
    # ones whose edges can be moved without inventing a destination.
    repointable_ids = {
        row["entity_id"]
        for row in rows
        if classify_family(row["entity_id"]) != FAMILY_COLON
        and extract_token(row["entity_id"]) in rich_tokens
    }
    repointable_edges = Counter()
    for edge_row in edge_rows:
        if edge_row["entity_id"] in repointable_ids:
            repointable_edges[edge_row.get("direction", "in")] += int(edge_row["n"])

    rel_by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for edge_row in edge_rows:
        if edge_row.get("direction", "in") != "in":
            continue
        family = classify_family(edge_row["entity_id"])
        rel_by_family[family][edge_row["relationship_type"] or "<null>"] += int(edge_row["n"])

    phantom_sources: Counter[str] = Counter()
    phantom_set = set(phantom_tokens)
    for row in rows:
        token = extract_token(row["entity_id"])
        if token in phantom_set:
            phantom_sources[row.get("source_collection") or "<sql-null>"] += 1

    return {
        "total_nodes": len(rows),
        "families": [_finalise(by_family[fam]) for fam in FAMILY_ORDER],
        "name_carries_kbli_prefix": dict(name_carries_prefix),
        "relationship_types": {fam: rel_by_family[fam].most_common(TOP_N) for fam in FAMILY_ORDER},
        "distinct_tokens": len(all_tokens),
        "five_digit_tokens": len(five_digit_tokens),
        "rich_tokens": len(rich_tokens),
        "phantom_count": len(phantom_tokens),
        "phantom_sample": phantom_tokens[:TOP_N],
        "phantom_sources": phantom_sources.most_common(TOP_N),
        "fanout": sorted(fanout.items()),
        "repointable_nodes": len(repointable_ids),
        "repointable_edges_in": repointable_edges["in"],
        "repointable_edges_out": repointable_edges["out"],
    }


def _finalise(bucket: dict[str, Any]) -> dict[str, Any]:
    out = dict(bucket)
    out["properties_kinds"] = bucket["properties_kinds"].most_common()
    out["entity_types"] = bucket["entity_types"].most_common()
    out["sources"] = bucket["sources"].most_common(TOP_N)
    return out


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------


def fetch(psql_wrapper: Path, sql: str) -> list[dict[str, Any]]:
    """Shells out to the repo's one read-only psql wrapper rather than opening
    its own connection — there is exactly one correct role/db/proxy combo for
    prod and it already lives in that script."""
    proc = subprocess.run(
        [str(psql_wrapper), "-A", "-t", "-c", sql],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pg.sh exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    body = proc.stdout.strip()
    if not body:
        raise RuntimeError("pg.sh returned an empty body")
    return json.loads(body)


def render(census: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"KG ROOT CENSUS — {census['total_nodes']} KBLI-ish nodes")
    lines.append("")
    lines.append("  id shape          nodes   with-kode   empty   edge-reachable   in-edges  out-edges")
    for fam in census["families"]:
        lines.append(
            f"  {fam['family']:<16}{fam['nodes']:>7}{fam['with_kode']:>12}{fam['without_kode']:>8}"
            f"{fam['edge_reachable']:>17}{fam['in_edges']:>11}{fam['out_edges']:>11}"
        )
    lines.append("")
    lines.append("  provenance (top source_collection per family, first/last created_at)")
    for fam in census["families"]:
        if not fam["nodes"]:
            continue
        window = f"{fam['first_seen']}..{fam['last_seen']}"
        lines.append(f"    {fam['family']}  [{window}]  types={fam['entity_types']}")
        for source, count in fam["sources"]:
            lines.append(f"        {source:<36}{count:>7}")
        lines.append(f"        properties kinds: {fam['properties_kinds']}")
    lines.append("")
    lines.append("  inbound relationship_type (top 10 per family)")
    for fam in FAMILY_ORDER:
        pairs = census["relationship_types"].get(fam) or []
        if not pairs:
            continue
        lines.append(f"    {fam}")
        for rel, count in pairs:
            lines.append(f"        {rel:<28}{count:>8}")
    lines.append("")
    lines.append("  extracted tokens (the text each writer took for a code)")
    lines.append(f"    distinct tokens across all families : {census['distinct_tokens']}")
    lines.append(f"    well-formed 5-digit                 : {census['five_digit_tokens']}")
    lines.append(f"    of those, backed by a rich node     : {census['rich_tokens']}")
    lines.append(f"    PHANTOM (5-digit, no data anywhere) : {census['phantom_count']}")
    lines.append(f"      sample: {', '.join(census['phantom_sample'])}")
    lines.append("    phantom provenance:")
    for source, count in census["phantom_sources"]:
        lines.append(f"        {source:<36}{count:>7}")
    lines.append("")
    lines.append("  names that already carry the 'KBLI' prefix (the double-prefix proof)")
    for fam, count in sorted(census["name_carries_kbli_prefix"].items()):
        lines.append(f"    {fam:<18}{count:>7}")
    lines.append("")
    lines.append("  duplicate fan-out per well-formed code (LIMIT 5 in the notebook fallback)")
    for size, codes in census["fanout"]:
        lines.append(f"    {size} node(s)  ->  {codes} codes")
    lines.append("")
    lines.append("  cure surface")
    lines.append(f"    empty nodes whose code HAS a rich twin (repointable): {census['repointable_nodes']}")
    lines.append(f"    inbound edges landing on those                     : {census['repointable_edges_in']}")
    lines.append(f"    outbound edges asserted BY those                   : {census['repointable_edges_out']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--psql-wrapper", type=Path, default=DEFAULT_PSQL_WRAPPER)
    parser.add_argument("--snapshot", type=Path, help="replay a saved snapshot instead of querying")
    parser.add_argument("--snapshot-out", type=Path, help="write the fetched snapshot here")
    parser.add_argument("--json", action="store_true", help="emit the census as JSON")
    parser.add_argument("--emit-sql", action="store_true", help="print the queries and exit")
    args = parser.parse_args(argv)

    if args.emit_sql:
        print(CENSUS_SQL)
        print(EDGE_SQL)
        return EXIT_OK

    try:
        if args.snapshot:
            payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
            rows, edge_rows = payload["nodes"], payload["edges"]
        else:
            rows = fetch(args.psql_wrapper, CENSUS_SQL)
            edge_rows = fetch(args.psql_wrapper, EDGE_SQL)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"CANNOT VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    if not rows:
        print("CANNOT VERIFY: the snapshot is empty — 0 KBLI nodes read", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    if args.snapshot_out:
        args.snapshot_out.write_text(
            json.dumps({"nodes": rows, "edges": edge_rows}, indent=1), encoding="utf-8"
        )

    census = plan_census(rows, edge_rows)
    print(json.dumps(census, indent=2) if args.json else render(census))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
