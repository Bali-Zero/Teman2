#!/usr/bin/env python3
"""
Backfill pasal-level supersession metadata onto EXISTING legal_unified chunks.

WHY THIS EXISTS. The ingestion-side annotation (LegalIngestionService,
STAGE 6.5) stamps supersession metadata when an AMENDING instrument is
ingested. The two known amended pairs predate that mechanism, so their base
chunks carry no supersession keys and the retrieval guard no-ops on them:

    - UU 6/2011 (Keimigrasian)  <- amended by UU 63/2024   (base doc id UU_6_2011)
    - Permenkumham 22/2023      <- amended by Permenkumham 11/2024
                                 (base doc id Permen_22_2023)

WHAT IT DOES. For each --amendment FILE, it parses the file's own
"Pasal X diubah/dicabut/ditambah" clauses, finds the base documents' chunks in
the collection, and writes the flat supersession keys (superseded_by_document,
superseded_pasal_number, superseded_action, superseded_by_label) by point id.

DRY-RUN FIRST, ALWAYS. The default mode scrolls and reports exactly what it
WOULD write and never mutates the store. Pass --apply to execute. This is a
deploy-side act: the author of this script never ran it against any live or
production collection; the operator runs it, in dry-run first, against the
intended target.

USAGE (from apps/backend-rag, with the backend venv active):

    # report only — zero writes
    python scripts/backfill_pasal_supersession.py \
        --collection legal_unified \
        --amendment /path/to/UU_63_2024.pdf \
        --amendment /path/to/Permenkumham_11_2024.pdf

    # execute the exact plan the dry-run printed
    python scripts/backfill_pasal_supersession.py --apply ...same args...

FOLLOW-UP (stated, not done here): a corpus-wide retro-parse of every
amendment ever is the explicitly-larger separate decision. This script is the
mechanism; extending --amendment to more files is mechanical once those pairs
are curated and verified.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

KNOWN_PAIRS = {
    # informational only: which base document_id each known amendment should hit
    "UU_63_2024": "UU_6_2011",
    "Permenkumham_11_2024": "Permen_22_2023",
}


async def backfill_one(
    vector_db,
    amendment_path: Path,
    *,
    dry_run: bool,
) -> dict:
    from backend.core.legal import LegalCleaner, LegalMetadataExtractor
    from backend.core.legal.supersession import (
        annotate_superseded_pasals,
        identity_triple_to_document_id,
        parse_amendment_clauses,
    )
    from backend.core.parsers import auto_detect_and_parse

    raw_text = auto_detect_and_parse(str(amendment_path), use_ocr=False)
    cleaned_text = LegalCleaner().clean(raw_text)
    metadata = LegalMetadataExtractor().extract(cleaned_text)

    supersessions = parse_amendment_clauses(cleaned_text)
    if not supersessions:
        return {
            "amendment_file": str(amendment_path),
            "status": "no_clauses",
            "note": "no 'Pasal X diubah/dicabut/ditambah' clauses bound to a "
            "target instrument; nothing to backfill from this file",
        }

    amendment_doc_id = identity_triple_to_document_id(
        metadata.get("type_abbrev"),
        metadata.get("number"),
        metadata.get("year"),
    )
    if amendment_doc_id is None:
        return {
            "amendment_file": str(amendment_path),
            "status": "skipped",
            "reason": "amendment identity is hash-fallback; declare a "
            "document_id by re-ingesting with one, then re-run",
        }
    amendment_label = (
        f"{metadata.get('type_abbrev')} {metadata.get('number')}/{metadata.get('year')}"
    )

    summary = await annotate_superseded_pasals(
        vector_db,
        supersessions,
        amendment_doc_id=amendment_doc_id,
        amendment_label=amendment_label,
        dry_run=dry_run,
    )
    summary["amendment_file"] = str(amendment_path)
    return summary


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", default="legal_unified")
    parser.add_argument(
        "--amendment",
        action="append",
        required=True,
        help="path to an amending instrument's file (PDF/text); repeatable",
    )
    parser.add_argument(
        "--qdrant-url",
        default=None,
        help="override QDRANT_URL for this run; defaults to the environment",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute the writes; WITHOUT this flag the run is a dry report",
    )
    args = parser.parse_args()

    import os

    from backend.core.qdrant_db import QdrantClient

    qdrant_url = args.qdrant_url or os.environ.get("QDRANT_URL")
    if not qdrant_url:
        parser.error("QDRANT_URL is not set and --qdrant-url was not given")
    vector_db = QdrantClient(collection_name=args.collection, qdrant_url=qdrant_url)

    summaries = []
    for amendment in args.amendment:
        path = Path(amendment)
        if not path.exists():
            print(f"MISSING FILE: {path}", file=sys.stderr)
            continue
        summaries.append(await backfill_one(vector_db, path, dry_run=not args.apply))

    print(
        json.dumps(
            {
                "collection": args.collection,
                "dry_run": not args.apply,
                "known_pairs_reference": KNOWN_PAIRS,
                "summaries": summaries,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    unresolved = sum(len(s.get("unresolved", [])) for s in summaries)
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
