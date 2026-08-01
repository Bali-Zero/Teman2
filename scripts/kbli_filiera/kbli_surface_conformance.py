"""Does the client-facing store still agree with canonical? Ask about the STATE,
never about a list of codes.

WHY THIS EXISTS. `kbli_documents` is the 4th KBLI surface: `chat_kbli` injects its
rows VERBATIM into the LLM context answering on WhatsApp and web chat. It is not
derived from canonical — it was seeded once (2026-02-18) and has been PATCHED ever
since, one `--only <list of codes>` cure at a time. Measured 2026-08-01: **1,423 of
its 1,563 rows have never been touched by any cure**, and 8 of them disagree with
canonical about whether a foreign investor may own the activity — three in the
permissive direction, on the sea-cabotage family, where canonical carries an
adjudicated 49% cap.

Every one of those 8 was invisible to every previous tool for the same reason:
each cure selected the codes a census had NAMED. This one selects on the STATE
"exists in both stores and disagrees", so a divergence that nobody has thought to
look for is still caught. It is the corner's own meta-pattern applied to itself —
"the selector is the disease", fourth sighting, this time on the cure that closed
the third.

READ-ONLY. This file never writes. The cure is
`apps/backend-rag/backend/scripts/kbli_documents_cure.py`, whose `--only` path
already writes canonical `pma_status` wholesale — the tooling was never the
problem, the selector was.

USAGE
    scripts/kbli_filiera/kbli_surface_conformance.py                # via scripts/pg.sh
    scripts/kbli_filiera/kbli_surface_conformance.py --table-json snap.json
    scripts/kbli_filiera/kbli_surface_conformance.py --emit-sql     # print the query only

EXIT CODES
    0  conformant
    1  DIVERGENCE on a load-bearing dimension
    4  CANNOT VERIFY — canonical or the table snapshot unreadable/empty

An empty snapshot is bit 4, never 0: "I traversed nothing" must never render as
"I found nothing wrong" (W84).

WHAT IS ENFORCED, AND WHAT IS ONLY DECLARED — stated here so a green run is never
misread as "the surface is clean":

  ENFORCED (exit 1)
    - `pma_status` disagrees with canonical.
    - licensing PRESENCE disagrees: canonical detached the rows (declared gap)
      while the table still serves them, or the reverse. This is the exact shape
      of the 50113 disease that reached WhatsApp.
    - a row exists in the table for a code canonical does not have, and it has
      NOT been neutralised as a retired KBLI-2020 phantom.
    - a row is marked `NOT_IN_KBLI_2025` while canonical DOES carry the code —
      a live activity advertised to clients as retired.

  DECLARED ONLY (counted, never fails)
    - `judul` text differences. 1,423 rows still carry the original UPPERCASE
      seed titles with English glosses; failing on that would drown the signal
      above in cosmetic noise on its first run. The TRUNCATED subset is counted
      separately because truncation is not cosmetic — on 5 government codes the
      cut lands past the word `Pemerintah`, which is the word that says the
      activity is governmental.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

from _coverage_basis import CODE_FIELD  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DEFAULT_PSQL_WRAPPER = REPO_ROOT / "scripts/pg.sh"

EXIT_OK = 0
EXIT_DIVERGENCE = 1
EXIT_CANNOT_VERIFY = 4

PRINT_SAMPLE = 20

# Marker written by `kbli_documents_phantom_cure.py` onto rows for KBLI-2020
# codes that 2025 retired. Such a row legitimately has no canonical record.
PHANTOM_MARKER = "NOT_IN_KBLI_2025"

SNAPSHOT_SQL = """
SELECT coalesce(json_agg(json_build_object(
    'code', kode_kbli,
    'pma_status', metadata->>'pma_status',
    'judul', judul,
    'licensing_status', metadata->>'licensing_status',
    'rows', coalesce(jsonb_array_length(metadata->'per_skala'), 0)
)), '[]'::json) FROM kbli_documents;
"""


def load_canonical(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path}: expected a non-empty record list")
    return {str(r[CODE_FIELD]): r for r in records}


def fetch_table_snapshot(psql_wrapper: Path) -> list[dict[str, Any]]:
    """I/O. Shells out to the repo's one-true-way read-only psql wrapper rather
    than opening its own connection — there is exactly one correct
    role/db/proxy combo for prod and it already lives in that script."""
    proc = subprocess.run(
        [str(psql_wrapper), "-A", "-t", "-c", SNAPSHOT_SQL],
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


def plan_conformance(
    canonical: dict[str, dict[str, Any]], table: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pure. No list of codes anywhere: every row of the table is judged, and
    every canonical code is asked for."""
    pma_divergent: list[dict[str, Any]] = []
    licensing_divergent: list[dict[str, Any]] = []
    unneutralised_phantoms: list[str] = []
    live_marked_retired: list[str] = []
    judul_differs = 0
    judul_truncated = 0

    seen: set[str] = set()
    for row in table:
        code = str(row.get("code"))
        seen.add(code)
        record = canonical.get(code)
        is_phantom_marked = row.get("licensing_status") == PHANTOM_MARKER

        if record is None:
            if not is_phantom_marked:
                unneutralised_phantoms.append(code)
            continue

        if is_phantom_marked:
            live_marked_retired.append(code)
            continue

        canonical_pma = record.get("pma_status")
        table_pma = row.get("pma_status")
        if canonical_pma != table_pma:
            pma_divergent.append(
                {
                    "code": code,
                    "canonical": canonical_pma,
                    "table": table_pma,
                    # Named so the report can say WHICH divergences sync to an
                    # adjudicated basis and which merely sync to the SSOT's own
                    # unverified value — a distinction the cure must not blur.
                    "canonical_basis": bool(record.get("pma_official_basis")),
                    "canonical_cap_verified": record.get("pma_cap_verified"),
                }
            )

        canonical_rows = len(record.get("per_skala") or [])
        table_rows = int(row.get("rows") or 0)
        if (canonical_rows == 0) != (table_rows == 0):
            licensing_divergent.append(
                {"code": code, "canonical_rows": canonical_rows, "table_rows": table_rows}
            )

        canonical_judul = (record.get("judul") or "").strip()
        table_judul = (row.get("judul") or "").strip()
        if canonical_judul.casefold() != table_judul.casefold():
            judul_differs += 1
            if table_judul and canonical_judul.casefold().startswith(table_judul.casefold()):
                judul_truncated += 1

    missing_from_table = sorted(set(canonical) - seen)

    enforced = (
        len(pma_divergent)
        + len(licensing_divergent)
        + len(unneutralised_phantoms)
        + len(live_marked_retired)
        + len(missing_from_table)
    )
    return {
        "canonical_codes": len(canonical),
        "table_rows": len(table),
        "enforced_divergences": enforced,
        "pma_divergent": sorted(pma_divergent, key=lambda d: d["code"]),
        "licensing_divergent": sorted(licensing_divergent, key=lambda d: d["code"]),
        "unneutralised_phantoms": sorted(unneutralised_phantoms),
        "live_marked_retired": sorted(live_marked_retired),
        "missing_from_table": missing_from_table,
        "declared_only": {"judul_differs": judul_differs, "judul_truncated": judul_truncated},
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        "kbli_documents conformance vs canonical",
        f"  canonical codes : {report['canonical_codes']}",
        f"  table rows      : {report['table_rows']}",
        "",
    ]
    for key, label in (
        ("pma_divergent", "pma_status disagrees"),
        ("licensing_divergent", "licensing presence disagrees"),
        ("unneutralised_phantoms", "in table, absent from canonical, NOT neutralised"),
        ("live_marked_retired", "marked NOT_IN_KBLI_2025 while canonical has the code"),
        ("missing_from_table", "in canonical, absent from the table"),
    ):
        items = report[key]
        lines.append(f"  {label}: {len(items)}")
        for item in items[:PRINT_SAMPLE]:
            if isinstance(item, dict) and key == "pma_divergent":
                basis = "adjudicated basis" if item["canonical_basis"] else "NO basis on canonical"
                lines.append(
                    f"      {item['code']}  canonical={item['canonical']} "
                    f"table={item['table']}  [{basis}]"
                )
            elif isinstance(item, dict):
                lines.append(
                    f"      {item['code']}  canonical_rows={item['canonical_rows']} "
                    f"table_rows={item['table_rows']}"
                )
            else:
                lines.append(f"      {item}")
        if len(items) > PRINT_SAMPLE:
            lines.append(f"      ... showing {PRINT_SAMPLE} of {len(items)}")
    declared = report["declared_only"]
    lines += [
        "",
        f"  DECLARED, NOT ENFORCED — judul differs on {declared['judul_differs']} rows "
        f"({declared['judul_truncated']} of them truncated). A green run above does NOT",
        "  mean the titles are conformant; see this file's docstring for why.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--psql-wrapper", type=Path, default=DEFAULT_PSQL_WRAPPER)
    parser.add_argument("--table-json", type=Path, default=None, help="use a snapshot file instead of the DB")
    parser.add_argument("--emit-sql", action="store_true", help="print the snapshot query and exit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.emit_sql:
        print(SNAPSHOT_SQL.strip())
        return EXIT_OK

    try:
        canonical = load_canonical(args.canonical)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: canonical unreadable ({args.canonical}): {exc}")
        return EXIT_CANNOT_VERIFY

    try:
        if args.table_json:
            table = json.loads(args.table_json.read_text(encoding="utf-8"))
        else:
            table = fetch_table_snapshot(args.psql_wrapper)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: table snapshot unavailable: {exc}")
        return EXIT_CANNOT_VERIFY

    if not isinstance(table, list) or not table:
        print("CANNOT VERIFY: table snapshot is empty — zero rows traversed is not a clean bill")
        return EXIT_CANNOT_VERIFY

    report = plan_conformance(canonical, table)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return EXIT_DIVERGENCE if report["enforced_divergences"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
