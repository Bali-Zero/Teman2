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
already writes canonical `pma_status` wholesale.  That path may only consume
the verified divergences reported here; an explicit unverified gap remains a
backlog item and is never an instruction to overwrite the client-facing store.

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
    - `pma_status` disagrees with a canonical verdict whose per-code official
      basis and source vintage are both verified (`located`).
    - `pma_status` disagrees while canonical's verification declaration is
      absent or malformed.  This fails closed as `pma_invalid_divergent`; it is
      NOT safe input to a cure.
    - licensing PRESENCE disagrees: canonical detached the rows (declared gap)
      while the table still serves them, or the reverse. This is the exact shape
      of the 50113 disease that reached WhatsApp.
    - a row exists in the table for a code canonical does not have, and it has
      NOT been neutralised as a retired KBLI-2020 phantom.
    - a row is marked `NOT_IN_KBLI_2025` while canonical DOES carry the code —
      a live activity advertised to clients as retired.
    - a code the website cites from a NAMED Perpres annex (locator bucket
      `named-in-annex`) has no canonical `pma_official_basis` and canonical has
      not honestly declared that adjudication gap.

  DECLARED ONLY (counted, never fails)
    - a table PMA value disagrees with a canonical `declared_gap`.  The value is
      retained for continuity but is explicitly unverified, so it cannot be
      propagated as truth.
    - a named-annex locator has not propagated to canonical, but canonical
      explicitly records `declared_gap`.  Locator presence identifies an
      adjudication candidate; it does not prove that a KBLI-2020 restriction
      transfers to its KBLI-2025 descendant.
    - `judul` text differences. 1,423 rows still carry the original UPPERCASE
      seed titles with English glosses; failing on that would drown the signal
      above in cosmetic noise on its first run. The TRUNCATED subset is counted
      separately because truncation is not cosmetic — on 5 government codes the
      cut lands past the word `Pemerintah`, which is the word that says the
      activity is governmental.

KG DIMENSION (spec §7) — a SECOND surface this organ checks, over `kg_nodes` +
`kg_edges` rather than `kbli_documents`. Same wrapper, same read path, same
exit codes. Five checks, each with a manifest so a check can be ENFORCED on
what has been cured while the rest is still DECLARED — `kg_status_function`,
`kg_licence_presence` (both: canonical `per_skala` manifest = all codes minus
Phase-1b minus the Table-B S3 codes minus the 75 `NOT_APPLICABLE_OSS`
allowlist, each direction), `kg_stray_admission` (admitted edge to a §2.1
placeholder id or a `permit_type` node, catalog-wide), `kg_allowlist_contradiction`
(an allowlisted code failing zero-rows / zero-admitted / exact
`NOT_APPLICABLE_OSS`), `kg_node_presence` (every canonical code has a KG node,
every KG code node is canonical or carries `NOT_IN_KBLI_2025`, catalog-wide).

  ALL FIVE SHIP DECLARED — counted and rendered, NEVER folded into
  `enforced_divergences` or the exit code. W116: the flip to ENFORCED per
  check is its own one-line PR after that check's own log reads 0 on its
  manifest — never in the same PR as a cure, and never all five at once.
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

from _coverage_basis import (  # noqa: E402
    CODE_FIELD,
    PMA_DECLARED_UNVERIFIED,
    PMA_LOCATED,
    classify_pma,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
DEFAULT_PSQL_WRAPPER = REPO_ROOT / "scripts/pg.sh"
DEFAULT_LOCATORS = REPO_ROOT / "apps" / "mouth" / "data" / "perpres-locators.json"
DEFAULT_KG_ALLOWLIST = REPO_ROOT / "scripts/kbli_filiera/kg_oss_not_applicable_codes.json"
DEFAULT_BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"

EXIT_OK = 0
EXIT_DIVERGENCE = 1
EXIT_CANNOT_VERIFY = 4

PRINT_SAMPLE = 20
KG_PRINT_SAMPLE = 10

# Marker written by `kbli_documents_phantom_cure.py` onto rows for KBLI-2020
# codes that 2025 retired. Such a row legitimately has no canonical record.
PHANTOM_MARKER = "NOT_IN_KBLI_2025"

# --------------------------------------------------------------------------
# KG dimension (spec §7) — constants
# --------------------------------------------------------------------------

REGULATED_STATUS = "REGULATED"
PENDING_REGULATION_STATUS = "PENDING_REGULATION"
NOT_APPLICABLE_OSS_STATUS = "NOT_APPLICABLE_OSS"
NOT_IN_KBLI_2025_STATUS = "NOT_IN_KBLI_2025"

#: The three §2.1 nodes served to clients as licences that are not one — the
#: graph's own admission of ignorance about a code's regulatory status,
#: materialised as a fake permit. `kg_stray_admission` checks by ID, not by
#: name: the third id's name ("Status Perizinan PENDING_REGULATION", no
#: colon) does not match `_NOT_A_PERMIT_LABELS`'s exact string and currently
#: survives `permit_name_verdict` as a "permit" — the ID check is the only
#: thing that catches it today (measured on PROD, see this PR's body).
PLACEHOLDER_ENTITY_IDS: frozenset[str] = frozenset(
    {
        "status_perizinan_pending",
        "izin_usaha_pending",
        "izin_usaha_status_pending_regulation",
    }
)

#: `per_skala[].persyaratan` marker for a non-OSS-issued licence (spec §5): the
#: licence exists, but a ministry/dinas outside the OSS issuance path is the
#: issuer. This derives the manifest exclusion straight from canonical rather
#: than hard-coding a code list. Measured on canonical 2026-09-21: 91 codes /
#: 472 rows carry the marker — the spec's own count for the marker ALONE
#: (§5). This is a SUPERSET of spec §7's "61 Phase-1b codes": that narrower
#: number further intersects with the placeholder-cure Table A/B 175-code
#: universe (S1 26 + S2 34 + S3 1), which this detector does not compute. A
#: wider exclusion only SHRINKS the manifest — fewer codes judged — so it
#: cannot manufacture a new failure; it is a declared limit of this PR, not a
#: correctness bug in the ENFORCED direction (checks below ship DECLARED
#: only).
PHASE1B_PERSYARATAN_MARKER = "Lembaga OSS hanya menerbitkan NIB"

KG_SNAPSHOT_SQL = """
SELECT coalesce(json_agg(t), '[]'::json) FROM (
  SELECT
    n.entity_id AS code_id,
    n.properties->>'licensing_status' AS licensing_status,
    coalesce(json_agg(json_build_object(
        'entity_id', tgt.entity_id,
        'entity_type', tgt.entity_type,
        'name', tgt.name
    )) FILTER (WHERE e.target_entity_id IS NOT NULL), '[]'::json) AS targets
  FROM kg_nodes n
  LEFT JOIN kg_edges e
    ON e.source_entity_id = n.entity_id AND e.relationship_type = 'REQUIRES'
  LEFT JOIN kg_nodes tgt ON tgt.entity_id = e.target_entity_id
  WHERE n.entity_id ~ '^kbli:[0-9]{5}$'
  GROUP BY n.entity_id, n.properties->>'licensing_status'
) t;
"""

# `perpres-locators.json` bucket names that carry a SPECIFIC, code-named
# regulatory citation (a named Perpres annex entry). Every other bucket
# (`residual-besar-*`, `body-*`) is a generic default-provision fallback
# applied uniformly wherever no annex names the code — never flagged here,
# because flagging it would just restate the pre-existing "no annex" default,
# not surface new information.
#
# `priority-lampiran-i` was in this set until 2026-08-06 and FAILED that very
# test. Measured on the artifact: its 175 codes carry **exactly one distinct
# cite** between them — "Perpres 49/2021 Lampiran I — priority business field
# (Pasal 3(1)(a))" — which names no code, no percentage, no ownership treatment
# (0 of its cites mention asing/%/foreign/modal). `named-in-annex` by contrast
# has **61 distinct cites across 270 codes**, several carrying the KBLI-2020
# crosswalk that earned the entry ("… via KBLI-2020 47911").
#
# So the check was demanding an adjudicated FOREIGN-OWNERSHIP basis for 173
# codes whose citation asserts nothing about ownership — judging by which
# bucket a code sits in rather than by what its citation actually says
# (superscar #3). The compiler already knew: `perpres_body_default_relation.py`
# records that priority listing "incentivises, it never restricts". A backlog
# of 414 was really 241.
SPECIFIC_CITATION_BUCKETS = {"named-in-annex"}

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


def load_locators(path: Path) -> dict[str, dict[str, Any]]:
    """Loads `perpres-locators.json` and unwraps its `locators` sub-dict — the
    same shape `apps/mouth/src/app/kbli/[code]/page.tsx` reads to render the
    "Basis: ..." citation. Raises loudly on anything malformed; the caller
    turns that into CANNOT VERIFY rather than a silently skipped check."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    locators = payload["locators"] if isinstance(payload, dict) else payload
    if not isinstance(locators, dict) or not locators:
        raise ValueError(f"{path}: expected a non-empty 'locators' mapping")
    return locators


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


def fetch_kg_snapshot(psql_wrapper: Path) -> list[dict[str, Any]]:
    """I/O. Same read-only `scripts/pg.sh` wrapper, second query (`KG_SNAPSHOT_SQL`).

    One entry per `kbli:<5 digits>` node: `code_id`, `licensing_status`, and
    every `REQUIRES` edge target's `(entity_id, entity_type, name)`.
    """
    proc = subprocess.run(
        [str(psql_wrapper), "-A", "-t", "-c", KG_SNAPSHOT_SQL],
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


def load_kg_allowlist(path: Path) -> set[str]:
    """Loads `kg_oss_not_applicable_codes.json`'s `codes` list — the 75-code
    `NOT_APPLICABLE_OSS` freeze (spec §7 `kg_allowlist_contradiction`)."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    codes = payload["codes"] if isinstance(payload, dict) else payload
    if not isinstance(codes, list) or not codes:
        raise ValueError(f"{path}: expected a non-empty 'codes' list")
    return {str(c) for c in codes}


def import_client_admitted_permit():
    """I/O-adjacent: imports the ONE admission predicate (spec §1/§7) from
    `apps/backend-rag`, added to `sys.path` the same way
    `recert_pma_editorial_registry.py` reaches backend code — no existing
    `scripts/kbli_filiera` module imports it at module scope, so this is a
    fresh, minimal instance of that pattern rather than a reuse of one.

    Returns the function, never raises: an ImportError here is a CANNOT
    VERIFY condition for the caller, not a crash.
    """
    backend_rag = str(DEFAULT_BACKEND_RAG)
    if backend_rag not in sys.path:
        sys.path.insert(0, backend_rag)
    from backend.services.kbli_requires_kind import client_admitted_permit  # noqa: PLC0415

    return client_admitted_permit


def phase1b_candidate_codes(canonical: dict[str, dict[str, Any]]) -> set[str]:
    """Codes carrying `PHASE1B_PERSYARATAN_MARKER` on any `per_skala` row's
    `persyaratan` — see that constant's docstring for the 91-vs-61 declared
    limit."""
    out: set[str] = set()
    for code, record in canonical.items():
        for row in record.get("per_skala") or []:
            persyaratan = row.get("persyaratan")
            texts: list[str] = []
            if isinstance(persyaratan, str):
                texts = [persyaratan]
            elif isinstance(persyaratan, list):
                texts = [p for p in persyaratan if isinstance(p, str)]
            if any(PHASE1B_PERSYARATAN_MARKER in t for t in texts):
                out.add(code)
                break
    return out


def _index_kg_snapshot(
    kg_snapshot: list[dict[str, Any]],
) -> tuple[dict[str, str | None], dict[str, list[dict[str, Any]]]]:
    """Splits the flat `kg_snapshot` rows into per-code status and targets,
    keyed on the bare 5-digit code (the `kbli:` prefix stripped once here so
    every check below compares like with like against canonical)."""
    status_by_code: dict[str, str | None] = {}
    targets_by_code: dict[str, list[dict[str, Any]]] = {}
    for entry in kg_snapshot:
        code_id = str(entry.get("code_id") or "")
        if not code_id.startswith("kbli:"):
            continue
        code = code_id[len("kbli:") :]
        status_by_code[code] = entry.get("licensing_status")
        targets_by_code[code] = entry.get("targets") or []
    return status_by_code, targets_by_code


def _admitted_count(
    targets: list[dict[str, Any]], admitted_permit_fn
) -> int:
    return sum(
        1
        for t in targets
        if admitted_permit_fn(t.get("entity_id"), t.get("entity_type"), t.get("name"))
    )


def _kg_status_function(
    manifest: set[str],
    canonical_rows_by_code: dict[str, int],
    status_by_code: dict[str, str | None],
) -> dict[str, Any]:
    forward: list[dict[str, Any]] = []
    reverse: list[dict[str, Any]] = []
    for code in sorted(manifest):
        rows = canonical_rows_by_code.get(code, 0)
        status = status_by_code.get(code)
        if rows > 0:
            if status != REGULATED_STATUS:
                forward.append({"code": code, "canonical_rows": rows, "kg_status": status})
        else:
            if status != PENDING_REGULATION_STATUS:
                reverse.append({"code": code, "canonical_rows": rows, "kg_status": status})
    return {"manifest_size": len(manifest), "forward_failures": forward, "reverse_failures": reverse}


def _kg_licence_presence(
    manifest: set[str],
    canonical_rows_by_code: dict[str, int],
    admitted_count_by_code: dict[str, int],
) -> dict[str, Any]:
    forward: list[dict[str, Any]] = []
    reverse: list[dict[str, Any]] = []
    for code in sorted(manifest):
        rows = canonical_rows_by_code.get(code, 0)
        admitted = admitted_count_by_code.get(code, 0)
        if rows > 0:
            if admitted < 1:
                forward.append({"code": code, "canonical_rows": rows, "admitted": admitted})
        else:
            if admitted != 0:
                reverse.append({"code": code, "canonical_rows": rows, "admitted": admitted})
    return {"manifest_size": len(manifest), "forward_failures": forward, "reverse_failures": reverse}


def _kg_stray_admission(
    targets_by_code: dict[str, list[dict[str, Any]]], admitted_permit_fn
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for code in sorted(targets_by_code):
        for t in targets_by_code[code]:
            entity_id = t.get("entity_id")
            entity_type = t.get("entity_type")
            name = t.get("name")
            if not admitted_permit_fn(entity_id, entity_type, name):
                continue
            eid = (entity_id or "").strip().lower()
            etype = (entity_type or "").strip().lower()
            if eid in PLACEHOLDER_ENTITY_IDS or etype == "permit_type":
                failures.append(
                    {"code": code, "entity_id": entity_id, "entity_type": entity_type, "name": name}
                )
    return {"failures": failures}


def _kg_allowlist_contradiction(
    allowlist_codes: set[str],
    canonical_rows_by_code: dict[str, int],
    admitted_count_by_code: dict[str, int],
    status_by_code: dict[str, str | None],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for code in sorted(allowlist_codes):
        rows = canonical_rows_by_code.get(code, 0)
        admitted = admitted_count_by_code.get(code, 0)
        status = status_by_code.get(code)
        if rows != 0 or admitted != 0 or status != NOT_APPLICABLE_OSS_STATUS:
            failures.append({"code": code, "canonical_rows": rows, "admitted": admitted, "kg_status": status})
    return {"allowlist_size": len(allowlist_codes), "failures": failures}


def _kg_node_presence(
    canonical_codes: set[str],
    kg_code_ids: set[str],
    status_by_code: dict[str, str | None],
) -> dict[str, Any]:
    forward_failures = sorted(canonical_codes - kg_code_ids)
    reverse_failures: list[dict[str, Any]] = []
    for code in sorted(kg_code_ids - canonical_codes):
        status = status_by_code.get(code)
        if status != NOT_IN_KBLI_2025_STATUS:
            reverse_failures.append({"code": code, "kg_status": status})
    return {"forward_failures": forward_failures, "reverse_failures": reverse_failures}


def plan_kg_conformance(
    canonical: dict[str, dict[str, Any]],
    kg_snapshot: list[dict[str, Any]],
    allowlist_codes: set[str],
    admitted_permit_fn,
) -> dict[str, Any]:
    """Pure. The KG dimension (spec §7) — five checks, all DECLARED (never
    added to the caller's exit-code arithmetic). `admitted_permit_fn` is
    `client_admitted_permit` from `kbli_requires_kind.py`, injected so this
    function stays testable with no DB and no `apps/backend-rag` import."""
    status_by_code, targets_by_code = _index_kg_snapshot(kg_snapshot)
    kg_code_ids = set(status_by_code)
    canonical_codes = set(canonical)
    canonical_rows_by_code = {c: len(r.get("per_skala") or []) for c, r in canonical.items()}
    admitted_count_by_code = {
        code: _admitted_count(targets, admitted_permit_fn) for code, targets in targets_by_code.items()
    }

    phase1b_codes = phase1b_candidate_codes(canonical)
    s3_codes = {
        code
        for code in canonical_codes
        if status_by_code.get(code) == PENDING_REGULATION_STATUS
        and admitted_count_by_code.get(code, 0) >= 1
    }
    manifest = canonical_codes - phase1b_codes - s3_codes - allowlist_codes

    return {
        "manifest_size": len(manifest),
        "phase1b_excluded": len(phase1b_codes),
        "s3_excluded": len(s3_codes),
        "allowlist_excluded": len(allowlist_codes),
        "kg_status_function": _kg_status_function(manifest, canonical_rows_by_code, status_by_code),
        "kg_licence_presence": _kg_licence_presence(
            manifest, canonical_rows_by_code, admitted_count_by_code
        ),
        "kg_stray_admission": _kg_stray_admission(targets_by_code, admitted_permit_fn),
        "kg_allowlist_contradiction": _kg_allowlist_contradiction(
            allowlist_codes, canonical_rows_by_code, admitted_count_by_code, status_by_code
        ),
        "kg_node_presence": _kg_node_presence(canonical_codes, kg_code_ids, status_by_code),
    }


def plan_conformance(
    canonical: dict[str, dict[str, Any]], table: list[dict[str, Any]]
) -> dict[str, Any]:
    """Pure. No list of codes anywhere: every row of the table is judged, and
    every canonical code is asked for."""
    pma_divergent: list[dict[str, Any]] = []
    pma_unverified_divergent: list[dict[str, Any]] = []
    pma_invalid_divergent: list[dict[str, Any]] = []
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
            verification_state = classify_pma(record)
            detail = {
                "code": code,
                "canonical": canonical_pma,
                "table": table_pma,
                "canonical_basis": bool(record.get("pma_official_basis")),
                "canonical_vintage": bool(record.get("pma_source_vintage")),
                "canonical_cap_verified": record.get("pma_cap_verified"),
                "verification_state": verification_state,
            }
            if verification_state == PMA_LOCATED:
                pma_divergent.append(detail)
            elif verification_state == PMA_DECLARED_UNVERIFIED:
                pma_unverified_divergent.append(detail)
            else:
                # Fail closed, but keep this distinct from a verified truth
                # mismatch: a writer must repair/adjudicate canonical first.
                pma_invalid_divergent.append(detail)

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
        + len(pma_invalid_divergent)
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
        "pma_unverified_divergent": sorted(
            pma_unverified_divergent, key=lambda d: d["code"]
        ),
        "pma_invalid_divergent": sorted(
            pma_invalid_divergent, key=lambda d: d["code"]
        ),
        "licensing_divergent": sorted(licensing_divergent, key=lambda d: d["code"]),
        "unneutralised_phantoms": sorted(unneutralised_phantoms),
        "live_marked_retired": sorted(live_marked_retired),
        "missing_from_table": missing_from_table,
        "declared_only": {"judul_differs": judul_differs, "judul_truncated": judul_truncated},
    }


def plan_citation_propagation(
    canonical: dict[str, dict[str, Any]], locators: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Pure. A THIRD data source, judged independently of the Postgres table
    this file otherwise checks: does the website's per-code Perpres citation
    (`apps/mouth/data/perpres-locators.json`) propagate to canonical's
    adjudicated `pma_official_basis` field?

    Only the SPECIFIC buckets carry code-named regulatory information
    (`SPECIFIC_CITATION_BUCKETS`); every other bucket is a generic
    default-provision fallback and is never flagged — see that constant's
    docstring.

    `locators` is already unwrapped (the caller passes `payload["locators"]`,
    same as `load_locators` returns).
    """
    specific_citation_codes = 0
    citation_not_propagated: list[dict[str, Any]] = []
    citation_pending_adjudication: list[dict[str, Any]] = []

    for code, locator in locators.items():
        bucket = locator.get("bucket")
        if bucket not in SPECIFIC_CITATION_BUCKETS:
            continue
        specific_citation_codes += 1

        record = canonical.get(code)
        if record is None:
            # Informational-only oddity — locators is meant to be a subset of
            # the 1,559-code canonical universe of record. Never crash on it,
            # just skip it from this check.
            continue

        if not record.get("pma_official_basis"):
            detail = {
                "code": code,
                "bucket": bucket,
                "cite": locator.get("cite"),
                "canonical_pma_status": record.get("pma_status"),
                "verification_state": classify_pma(record),
            }
            if detail["verification_state"] == PMA_DECLARED_UNVERIFIED:
                citation_pending_adjudication.append(detail)
            else:
                citation_not_propagated.append(detail)

    return {
        "specific_citation_codes": specific_citation_codes,
        "citation_not_propagated": sorted(citation_not_propagated, key=lambda d: d["code"]),
        "citation_pending_adjudication": sorted(
            citation_pending_adjudication, key=lambda d: d["code"]
        ),
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        "kbli_documents conformance vs canonical",
        f"  canonical codes : {report['canonical_codes']}",
        f"  table rows      : {report['table_rows']}",
        "",
    ]
    for key, label in (
        ("pma_divergent", "pma_status disagrees with VERIFIED canonical"),
        ("pma_invalid_divergent", "pma_status disagrees; canonical state INVALID"),
        ("licensing_divergent", "licensing presence disagrees"),
        ("unneutralised_phantoms", "in table, absent from canonical, NOT neutralised"),
        ("live_marked_retired", "marked NOT_IN_KBLI_2025 while canonical has the code"),
        ("missing_from_table", "in canonical, absent from the table"),
    ):
        items = report[key]
        lines.append(f"  {label}: {len(items)}")
        for item in items[:PRINT_SAMPLE]:
            if isinstance(item, dict) and key.startswith("pma_"):
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

    pud = report.get("pma_unverified_divergent", [])
    lines.append(f"  pma_unverified_divergent: {len(pud)} (declared only; never sync)")
    for item in pud[:PRINT_SAMPLE]:
        lines.append(
            f"      {item['code']}  canonical={item['canonical']} "
            f"table={item['table']}  [declared_gap]"
        )
    if len(pud) > PRINT_SAMPLE:
        lines.append(f"      ... showing {PRINT_SAMPLE} of {len(pud)}")

    citation = report.get("citation_propagation", {})
    cnp = citation.get("citation_not_propagated", [])
    lines.append(
        f"  citation_not_propagated: {len(cnp)} "
        f"(of {citation.get('specific_citation_codes', 0)} codes with a named-annex Perpres citation)"
    )
    for item in cnp[:PRINT_SAMPLE]:
        lines.append(
            f"      {item['code']}  bucket={item['bucket']} "
            f"canonical_pma_status={item['canonical_pma_status']}"
        )
    if len(cnp) > PRINT_SAMPLE:
        lines.append(f"      ... showing {PRINT_SAMPLE} of {len(cnp)}")

    cpa = citation.get("citation_pending_adjudication", [])
    lines.append(
        f"  citation_pending_adjudication: {len(cpa)} "
        "(declared only; named locator is not an inherited PMA ruling)"
    )
    for item in cpa[:PRINT_SAMPLE]:
        lines.append(
            f"      {item['code']}  bucket={item['bucket']} "
            f"canonical_pma_status={item['canonical_pma_status']}"
        )
    if len(cpa) > PRINT_SAMPLE:
        lines.append(f"      ... showing {PRINT_SAMPLE} of {len(cpa)}")

    declared = report["declared_only"]
    lines += [
        "",
        f"  DECLARED, NOT ENFORCED — judul differs on {declared['judul_differs']} rows "
        f"({declared['judul_truncated']} of them truncated). A green run above does NOT",
        "  mean the titles are conformant; see this file's docstring for why.",
    ]

    kg = report.get("kg")
    if kg is not None:
        lines += _render_kg(kg)
    return "\n".join(lines)


def _render_kg_direction(label: str, items: list[Any]) -> list[str]:
    lines = [f"    {label}: {len(items)}"]
    for item in items[:KG_PRINT_SAMPLE]:
        if isinstance(item, dict):
            extra = ", ".join(f"{k}={v}" for k, v in item.items() if k != "code")
            lines.append(f"        {item.get('code')}  {extra}")
        else:
            lines.append(f"        {item}")
    if len(items) > KG_PRINT_SAMPLE:
        lines.append(f"        ... showing {KG_PRINT_SAMPLE} of {len(items)}")
    return lines


def _render_kg(kg: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "KG dimension (spec §7) — DECLARED ONLY, never folded into the exit code",
        f"  manifest: {kg['manifest_size']} (excluded: {kg['phase1b_excluded']} Phase-1b, "
        f"{kg['s3_excluded']} Table-B S3, {kg['allowlist_excluded']} NOT_APPLICABLE_OSS allowlist)",
        "",
        "  kg_status_function (per_skala rows > 0 <=> KG status REGULATED)",
    ]
    sf = kg["kg_status_function"]
    lines += _render_kg_direction("forward failures (rows>0, status!=REGULATED)", sf["forward_failures"])
    lines += _render_kg_direction(
        "reverse failures (rows==0, status!=PENDING_REGULATION)", sf["reverse_failures"]
    )

    lines.append("")
    lines.append("  kg_licence_presence (per_skala rows > 0 <=> >=1 admitted permit)")
    lp = kg["kg_licence_presence"]
    lines += _render_kg_direction("forward failures (rows>0, 0 admitted)", lp["forward_failures"])
    lines += _render_kg_direction("reverse failures (rows==0, >=1 admitted)", lp["reverse_failures"])

    lines.append("")
    sa = kg["kg_stray_admission"]
    lines.append("  kg_stray_admission (admitted edge to a §2.1 placeholder id or permit_type node)")
    lines += _render_kg_direction("failures (catalog-wide)", sa["failures"])

    lines.append("")
    ac = kg["kg_allowlist_contradiction"]
    lines.append(f"  kg_allowlist_contradiction (of {ac['allowlist_size']} NOT_APPLICABLE_OSS codes)")
    lines += _render_kg_direction("failures", ac["failures"])

    lines.append("")
    np_ = kg["kg_node_presence"]
    lines.append("  kg_node_presence (every canonical code has a KG node, and the reverse)")
    lines += _render_kg_direction("forward failures (canonical code, no KG node)", np_["forward_failures"])
    lines += _render_kg_direction(
        "reverse failures (KG node, not canonical, no NOT_IN_KBLI_2025)", np_["reverse_failures"]
    )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--locators", type=Path, default=DEFAULT_LOCATORS)
    parser.add_argument("--kg-allowlist", type=Path, default=DEFAULT_KG_ALLOWLIST)
    parser.add_argument("--psql-wrapper", type=Path, default=DEFAULT_PSQL_WRAPPER)
    parser.add_argument("--table-json", type=Path, default=None, help="use a snapshot file instead of the DB")
    parser.add_argument(
        "--kg-json", type=Path, default=None, help="use a KG snapshot file instead of the DB"
    )
    parser.add_argument("--emit-sql", action="store_true", help="print both snapshot queries and exit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.emit_sql:
        print(SNAPSHOT_SQL.strip())
        print()
        print(KG_SNAPSHOT_SQL.strip())
        return EXIT_OK

    try:
        canonical = load_canonical(args.canonical)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: canonical unreadable ({args.canonical}): {exc}")
        return EXIT_CANNOT_VERIFY

    try:
        locators = load_locators(args.locators)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: locators unreadable ({args.locators}): {exc}")
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

    try:
        allowlist_codes = load_kg_allowlist(args.kg_allowlist)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: KG allowlist unreadable ({args.kg_allowlist}): {exc}")
        return EXIT_CANNOT_VERIFY

    try:
        admitted_permit_fn = import_client_admitted_permit()
    except ImportError as exc:
        print(f"CANNOT VERIFY: client_admitted_permit unimportable: {exc}")
        return EXIT_CANNOT_VERIFY

    try:
        if args.kg_json:
            kg_snapshot = json.loads(args.kg_json.read_text(encoding="utf-8"))
        else:
            kg_snapshot = fetch_kg_snapshot(args.psql_wrapper)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"CANNOT VERIFY: KG snapshot unavailable: {exc}")
        return EXIT_CANNOT_VERIFY

    if not isinstance(kg_snapshot, list) or not kg_snapshot:
        print("CANNOT VERIFY: KG snapshot is empty — zero rows traversed is not a clean bill")
        return EXIT_CANNOT_VERIFY

    report = plan_conformance(canonical, table)
    citation_report = plan_citation_propagation(canonical, locators)
    report["citation_propagation"] = citation_report
    report["kg"] = plan_kg_conformance(canonical, kg_snapshot, allowlist_codes, admitted_permit_fn)

    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))

    # KG checks are ALL DECLARED (spec §7 / W116) — never added here.
    total_enforced = report["enforced_divergences"] + len(citation_report["citation_not_propagated"])
    return EXIT_DIVERGENCE if total_enforced else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
