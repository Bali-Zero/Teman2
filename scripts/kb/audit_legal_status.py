#!/usr/bin/env python3
"""audit_legal_status — whole-scroll audit of `legal_status` across legal_unified_hybrid_hybrid.

Decision 5 (Zero, 2026-08-25, KB current-live campaign) chose MARK over REMOVE for
Golden-Visa-canary journey 4's live defect: Permen_22_2023 (in force) and
Permen_29_2021 (superseded) BOTH carry `legal_status: dicabut` in their own payload.
A filter excluding `dicabut` would drop the correct regulation and keep the wrong
one — so the field is not trustworthy enough to filter on until an audit says how
far the damage goes. This script is that audit. READ-ONLY: it never writes to Qdrant.

It answers, whole-scroll (not sampled) over the collection named by --collection:

  1. What vocabulary does `legal_status` actually use? (never assume two values)
  2. How many points / documents carry it, and where does it live in the payload
     (top-level vs metadata.legal_status vs both vs neither)?
  3. For each distinct document_id: what value(s) does it carry? A document is
     INCONSISTENT if its own points disagree — that is itself evidence the field
     is not a per-document constant the way ingestion assumes.

It does NOT independently verify legal reality (in-force vs superseded) — that is
an external-verification step layered on top for a bounded instrument list (see
--topics), because verifying a document's real-world status requires a web/registry
fetch per instrument, not a Qdrant scroll.

Run: apps/backend-rag/.venv/bin/python scripts/kb/audit_legal_status.py \
        --collection legal_unified_hybrid_hybrid --topics kb/topics/immigration.yaml
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

_MISSING = "<missing:no legal_status field anywhere>"


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("audit_legal_status: repo root not found")


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        print(f"BROKEN — {env} not found, no credentials to reach Qdrant with. "
              "Nothing was measured.", file=sys.stderr)
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_legal_status(payload: dict) -> tuple[str, str]:
    """Returns (effective_value, where) — where in {'top', 'metadata', 'both', 'none'}.

    Both locations are read every time (mandate §4.1 lesson: a probe reading only
    one payload shape reports damage as zero on the shape it never looked at).
    When both are present and DISAGREE, the raw pair is returned as the value so
    that disagreement is visible rather than silently resolved by a preference
    order.
    """
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    top = payload.get("legal_status")
    nested = meta.get("legal_status")
    top_present = "legal_status" in payload and top is not None
    nested_present = "legal_status" in meta and nested is not None
    if top_present and nested_present:
        if top == nested:
            return (str(top), "both")
        return (f"CONFLICT[top={top!r} vs metadata={nested!r}]", "both")
    if top_present:
        return (str(top), "top")
    if nested_present:
        return (str(nested), "metadata")
    return (_MISSING, "none")


def extract_document_id(payload: dict) -> str:
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return payload.get("document_id") or meta.get("document_id") or "<none>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collection", default="legal_unified_hybrid_hybrid")
    parser.add_argument("--json-out", type=Path, default=None,
                         help="write the full per-document census as JSON here")
    parser.add_argument("--top-n", type=int, default=40,
                         help="how many highest-point documents to print in detail")
    args = parser.parse_args(argv)

    root = repo_root()
    load_env(root)
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    live = {c.name for c in client.get_collections().collections}
    if args.collection not in live:
        print(f"ABSENT — {args.collection!r} is not a live Qdrant collection. "
              f"Live collections: {sorted(live)}", file=sys.stderr)
        return 3

    total_points = 0
    where_counts: collections.Counter = collections.Counter()
    value_counts: collections.Counter = collections.Counter()
    # doc_id -> Counter(value -> count)
    per_doc: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    doc_points: collections.Counter = collections.Counter()

    offset = None
    batches = 0
    while True:
        batch, offset = client.scroll(
            args.collection, limit=2000, offset=offset, with_payload=True, with_vectors=False
        )
        if not batch:
            break
        batches += 1
        for point in batch:
            total_points += 1
            payload = point.payload or {}
            doc_id = extract_document_id(payload)
            doc_points[doc_id] += 1
            value, where = extract_legal_status(payload)
            where_counts[where] += 1
            value_counts[value] += 1
            per_doc[doc_id][value] += 1
        if offset is None:
            break

    print(f"=== audit_legal_status — {args.collection} ===")
    print(f"scroll batches: {batches}, total points: {total_points}, "
          f"distinct document_id values: {len(per_doc)}")
    print()
    print("--- Q1: where does legal_status live in the payload? ---")
    for where, count in where_counts.most_common():
        pct = 100.0 * count / total_points if total_points else 0.0
        print(f"  {where:10s} {count:7d} points ({pct:5.1f}%)")
    print()
    print("--- Q2: what is the FULL vocabulary of legal_status? (never assume 2 values) ---")
    for value, count in value_counts.most_common():
        pct = 100.0 * count / total_points if total_points else 0.0
        docs_with_value = sum(1 for c in per_doc.values() if value in c)
        print(f"  {value!r:60s} {count:7d} points ({pct:5.1f}%)  across {docs_with_value:4d} document_ids")
    print()

    # Q3: internal consistency — does every point of a document agree on the value?
    inconsistent = {doc: counter for doc, counter in per_doc.items() if len(counter) > 1}
    print(f"--- Q3: documents whose OWN points disagree on legal_status: {len(inconsistent)} ---")
    for doc, counter in sorted(inconsistent.items(), key=lambda kv: -sum(kv[1].values())):
        breakdown = ", ".join(f"{v!r}={c}" for v, c in counter.most_common())
        print(f"  {doc:40s} ({doc_points[doc]:5d} pts total): {breakdown}")
    print()

    print(f"--- top {args.top_n} documents by point count, with their legal_status ---")
    header = "%-40s %8s  %s" % ("document_id", "points", "legal_status(es)")
    print(header)
    print("-" * len(header))
    for doc, npts in doc_points.most_common(args.top_n):
        counter = per_doc[doc]
        breakdown = ", ".join(f"{v!r}={c}" for v, c in counter.most_common())
        print("%-40s %8d  %s" % (doc, npts, breakdown))

    if args.json_out:
        out = {
            "collection": args.collection,
            "total_points": total_points,
            "distinct_document_ids": len(per_doc),
            "where_counts": dict(where_counts),
            "value_counts": dict(value_counts),
            "per_document": {
                doc: dict(counter) for doc, counter in per_doc.items()
            },
        }
        args.json_out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\nfull per-document census written to {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
