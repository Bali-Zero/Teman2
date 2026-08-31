#!/usr/bin/env python3
"""legal_status_drift_gate — re-measures `kb/inventory/legal_status.yaml` (kind:
field_integrity) against LIVE production. Rule (g), the convention already in force
on this branch (kb/ops/probe_history.py, scripts/kb/kb_inventory_probe.py): the thing
that proves an artifact still describes the world is a fresh scroll, never a stored
sha256 standing in for a fact about a collection that moves on its own.

Two independent things are checked, reported SEPARATELY (never folded into one verdict
string, for the same reason kb_inventory_probe.py keeps DRIFT and OUTSTANDING apart —
a reader must learn WHICH fact moved, not just that something did):

  1. DRIFT on the recorded numbers. The per-point distribution, per-document
     distribution, and CONTEXT-header coverage this artifact records were measured on
     a specific date against a corpus this campaign has already observed mutating
     (+314 points between two audits taken one day apart — kb/inventory/legal_status.yaml's
     own corpus-growth caveat). A number that has moved means the artifact is stale,
     not that anything is wrong with production.

  2. status_vigensi regression. Unlike every other check here, this one is a
     DECLARED EXCEPTION to "the probe must be red today" — it is expected to be, and
     stay, GREEN. `status_vigensi` is a key `build_search_filter()`
     (apps/backend-rag/backend/services/search/search_filters.py) already excludes
     `dicabut` on, in every collection listed in `_FLAT_PAYLOAD_COLLECTIONS`
     (apps/backend-rag/backend/core/qdrant_db.py) including `legal_unified` — but the
     key is written by a DIFFERENT ingestion path (`ingestion_service.py`) than the one
     that fills `legal_unified` (`legal_ingestion_service.py`, which never sets it) and
     is measured at 0 occurrences on `legal_unified` today. If it were ever populated —
     for instance by an apparent "field cleanup" copying `legal_status` into
     `status_vigensi` — the exclusion filter would go from inert to live instantly, with
     no code change and no review, and 42,420 points (50.3% of the corpus, including
     every one of Keimigrasian/Perseroan Terbatas/Cipta Kerja/Ketenagakerjaan) would
     vanish from every `SearchService`-routed query. This check guards exactly that:
     it must find 0 occurrences every time it runs, and going RED here is the one
     verdict in this whole campaign that means something got WORSE, not that an
     artifact went stale.

READ-ONLY: this script never writes to Qdrant (the guilt-test proof for check 2 runs
against an in-memory, fully isolated Qdrant instance — see
test_legal_status_field_integrity_contract.py — never against `legal_unified` or any
other production collection).

Run:
    apps/backend-rag/.venv/bin/python scripts/kb/legal_status_drift_gate.py kb/inventory/legal_status.yaml
    apps/backend-rag/.venv/bin/python scripts/kb/legal_status_drift_gate.py kb/inventory/legal_status.yaml --json

Exit codes (same family as scripts/kb/kb_inventory_probe.py; 2/"outstanding" does not
apply to a field-integrity artifact and is never emitted):
    0  AT_TARGET   every recorded number still matches live production, and
                    status_vigensi is still 0.
    1  DRIFT       the recorded distribution has moved, OR status_vigensi is no
                    longer 0 (reported as a distinct, more severe reason string,
                    never merged into the same sentence as an ordinary count drift).
    3  BROKEN      could not measure: no `.env`, Qdrant unreachable, the inventory
                    file is missing/malformed, or its `kind` is not `field_integrity`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VERDICT_BY_EXIT = {0: "at_target", 1: "drift", 3: "broken"}

_MISSING = "<missing:no legal_status field anywhere>"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("legal_status_drift_gate: repo root not found")


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _status_of(payload: dict) -> str:
    """Distinguishes THREE things a naive `payload.get("legal_status")` cannot:
    the key holding "dicabut"/"berlaku", the key holding an explicit JSON null
    (KEY PRESENT, value None -- str(None) == "None", matching the census
    convention this gate's recorded numbers were authored against), and the key
    being ABSENT entirely (_MISSING). Checking `"legal_status" in payload` for
    presence and reading its value SEPARATELY (never `and top is not None` in
    the presence test) is load-bearing: collapsing null-present into
    key-absent silently merged 9,012 "None" points into the "absent" bucket on
    the first version of this function, moving what this artifact records from
    dicabut 42,420 / berlaku 26,107 / none 9,012 / absent 6,744 to a wrong
    none:0 / absent:15,756 split with the SAME total -- a drift gate that
    cannot tell these two failure modes apart could not tell an operator which
    one just happened."""
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    top_exists = "legal_status" in payload  # legal-status-lint: allow — drift gate, inspects the broken field, does not decide with it
    nested_exists = "legal_status" in meta  # legal-status-lint: allow — drift gate, inspects the broken field, does not decide with it
    top = payload.get("legal_status")  # legal-status-lint: allow — drift gate, inspects the broken field, does not decide with it
    nested = meta.get("legal_status")  # legal-status-lint: allow — drift gate, inspects the broken field, does not decide with it
    if top_exists and nested_exists:
        return str(top) if top == nested else f"CONFLICT[{top!r}/{nested!r}]"
    if top_exists:
        return str(top)
    if nested_exists:
        return str(nested)
    return _MISSING


def _document_id_of(payload: dict) -> str:
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return payload.get("document_id") or meta.get("document_id") or "<none>"


def _has_context_header(payload: dict) -> bool:
    text = payload.get("text")
    return isinstance(text, str) and text.lstrip().startswith("[CONTEXT:")


def _has_status_vigensi(payload: dict) -> bool:
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return "status_vigensi" in payload or "status_vigensi" in meta


def scan_field_integrity(client, collection: str) -> dict:
    """Pure(ish) re-measurement over an injected Qdrant client — the client is the
    ONLY seam, so this same function runs against real production (main()) and
    against an in-memory scratch instance (the guilt/innocence tests in
    test_legal_status_field_integrity_contract.py) with no behavioral difference.

    Returns a dict with the exact shape kb/inventory/legal_status.yaml's
    `measured_against` block records, plus `status_vigensi_hits` (int, 0 expected).
    """
    per_point = {"dicabut": 0, "berlaku": 0, "none": 0, "absent": 0}
    by_doc_status: dict[str, dict[str, int]] = {}
    by_doc_header_points: dict[str, int] = {}
    by_doc_total_points: dict[str, int] = {}
    total_points = 0
    no_context_points = 0
    status_vigensi_hits = 0

    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection, offset=offset, limit=1000,
            with_payload=True, with_vectors=False,
        )
        for point in points:
            total_points += 1
            payload = point.payload or {}
            status = _status_of(payload)
            bucket = {
                "dicabut": "dicabut", "berlaku": "berlaku",
                "None": "none", _MISSING: "absent",
            }.get(status)
            if bucket is None:
                # A CONFLICT[...] value or any other stray string: counted toward
                # neither of the four known buckets, but never silently dropped from
                # the point total either -- see the assertion in the caller.
                pass
            else:
                per_point[bucket] += 1
            doc_id = _document_id_of(payload)
            by_doc_status.setdefault(doc_id, {}).setdefault(status, 0)
            by_doc_status[doc_id][status] += 1
            by_doc_total_points[doc_id] = by_doc_total_points.get(doc_id, 0) + 1
            if _has_context_header(payload):
                by_doc_header_points[doc_id] = by_doc_header_points.get(doc_id, 0) + 1
            else:
                no_context_points += 1
            if _has_status_vigensi(payload):
                status_vigensi_hits += 1
        if offset is None:
            break

    per_doc = {"dicabut": 0, "berlaku": 0, "none": 0, "absent": 0, "mixed": 0}
    for doc_id, counts in by_doc_status.items():
        present = {k: v for k, v in counts.items() if v > 0}
        if len(present) == 1:
            only = next(iter(present))
            bucket = {"dicabut": "dicabut", "berlaku": "berlaku", "None": "none",
                      _MISSING: "absent"}.get(only, "mixed")
        else:
            bucket = "mixed"
        per_doc[bucket] += 1

    zero_header_documents = sum(
        1 for doc_id, total in by_doc_total_points.items()
        if by_doc_header_points.get(doc_id, 0) == 0
    )

    return {
        "collection": collection,
        "points": total_points,
        "distinct_documents": len(by_doc_status),
        "per_point": per_point,
        "per_document": per_doc,
        "no_context_points": no_context_points,
        "zero_header_documents": zero_header_documents,
        "status_vigensi_hits": status_vigensi_hits,
    }


def diff_against_recorded(recorded: dict, live: dict) -> list[str]:
    """Pure function: every mismatch between a recorded `measured_against` block and
    a fresh `scan_field_integrity()` result, as human-readable findings. Empty list
    means AT TARGET. Kept pure so guilt/innocence cases in the test file do not need
    a live Qdrant connection to exercise it."""
    findings = []
    if recorded.get("points") != live["points"]:
        findings.append(
            f"total points: recorded {recorded.get('points')} vs live {live['points']}"
        )
    if recorded.get("distinct_documents") != live["distinct_documents"]:
        findings.append(
            f"distinct documents: recorded {recorded.get('distinct_documents')} "
            f"vs live {live['distinct_documents']}"
        )
    for key in ("dicabut", "berlaku", "none", "absent"):
        r = (recorded.get("per_point") or {}).get(key)
        v = live["per_point"][key]
        if r != v:
            findings.append(f"per-point {key}: recorded {r} vs live {v}")
    for key in ("dicabut", "berlaku", "none", "absent", "mixed"):
        r = (recorded.get("per_document") or {}).get(key)
        v = live["per_document"][key]
        if r != v:
            findings.append(f"per-document {key}: recorded {r} vs live {v}")
    if recorded.get("no_context_points") != live["no_context_points"]:
        findings.append(
            f"no-context points: recorded {recorded.get('no_context_points')} "
            f"vs live {live['no_context_points']}"
        )
    if recorded.get("zero_header_documents") != live["zero_header_documents"]:
        findings.append(
            f"zero-header documents: recorded {recorded.get('zero_header_documents')} "
            f"vs live {live['zero_header_documents']}"
        )
    return findings


def status_vigensi_regression(live: dict) -> str | None:
    """The declared-exception check: must always find 0. Returns a finding string
    if it does not, else None. Kept as its own function so it is reported as a
    distinct, more severe reason and never merged into diff_against_recorded's list."""
    hits = live["status_vigensi_hits"]
    if hits:
        return (
            f"status_vigensi now appears on {hits} point(s) of {live['collection']} — "
            "this is a REGRESSION, not staleness: build_search_filter() already "
            "excludes status_vigensi='dicabut' on every SearchService-routed query "
            "against this collection (_FLAT_PAYLOAD_COLLECTIONS includes it), so a "
            "populated status_vigensi is a live filter, armed with no code change."
        )
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args(argv)

    root = repo_root()
    if not args.inventory.is_file():
        print(f"BROKEN — {args.inventory} does not exist", file=sys.stderr)
        return 3

    import yaml

    data = yaml.safe_load(args.inventory.read_text(encoding="utf-8"))
    if (data or {}).get("kind") != "field_integrity":
        print(
            f"BROKEN — {args.inventory} has kind={data.get('kind')!r}, not "
            "'field_integrity'. This gate only re-measures field_integrity inventories.",
            file=sys.stderr,
        )
        return 3

    load_env(root)
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    recorded = data["measured_against"]
    collection = recorded["collection"]
    live = scan_field_integrity(client, collection)

    drift_findings = diff_against_recorded(recorded, live)
    regression = status_vigensi_regression(live)

    verdict_exit = 1 if (drift_findings or regression) else 0

    if args.json_mode:
        result = {
            "inventory": str(args.inventory),
            "verdict": VERDICT_BY_EXIT[verdict_exit],
            "exit_code": verdict_exit,
            "drift_findings": drift_findings,
            "status_vigensi_regression": regression,
            "live": live,
        }
        print(json.dumps(result))
        return verdict_exit

    print(f"legal_status_drift_gate — {args.inventory} vs live {collection}")
    print(f"  live: {live['points']} points / {live['distinct_documents']} documents")
    if not drift_findings and not regression:
        print("AT TARGET — every recorded number still matches production, and "
              "status_vigensi is still absent.")
        return 0
    if drift_findings:
        print(f"DRIFT — {len(drift_findings)} recorded number(s) no longer match "
              "live production (the artifact is stale, not necessarily production):")
        for f in drift_findings:
            print(f"    {f}")
    if regression:
        print("STATUS_VIGENSI REGRESSION (distinct from drift above — this means "
              "something got WORSE, not that the artifact went stale):")
        print(f"    {regression}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
