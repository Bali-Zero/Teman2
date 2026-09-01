#!/usr/bin/env python3
"""cukup_jelas_sample — measure the false-positive rate of the §6 damage signal.

Campaign §6 damage signal: a point whose `section` is not `penjelasan` AND whose
text contains "Cukup jelas" (elucidation/commentary text sitting in an article
slot). Reported as 34 damaged documents / 2,019 damaged fragments.

`section` is populated on only 792/84,283 points (the two 2026-08-25 repairs:
UU_6_2011 + UU_40_2007). For the other 99.1% the field is simply ABSENT, so
`!= "penjelasan"` is vacuously true and the signal degrades to a bare substring
match on "Cukup jelas" — no guilt/innocence split at all (superscar family #3).

This script:
  1. Scrolls legal_unified_hybrid_hybrid (`legal_unified`) in full (whole-or-nothing,
     no allow_partial).
  2. Collects every point whose text/content contains "cukup jelas" (case-insensitive)
     AND whose section (top-level, else metadata.section) != "penjelasan".
  3. Prints the full damaged-fragment count + damaged-document count (to compare
     against the claimed 2,019 / 34).
  4. Writes a stratified sample (>=40, spread across distinct documents, not the
     first N found) to a JSON file for manual reading.

Whole-or-nothing: if the scroll does not complete, this prints BROKEN and exits 3 —
never a partial count silently presented as the total.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import random
import sys
from pathlib import Path

MIN_FRAGMENT_CHARS = 40


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("cukup_jelas_sample: repo root not found")


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        print("BROKEN — %s not found. Nothing measured." % env, file=sys.stderr)
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _load_signal_module(root: Path):
    """Load cukup_jelas_signal.py as a module (it lives outside any package,
    same pattern as test_kb_inventory_contract.py::_probe)."""
    cached = sys.modules.get("cukup_jelas_signal")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "cukup_jelas_signal", root / "scripts" / "kb" / "cukup_jelas_signal.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["cukup_jelas_signal"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    root = repo_root()
    load_env(root)
    signal = _load_signal_module(root)
    get_text = signal.get_text
    get_section = signal.get_section
    get_document_id = signal.get_document_id
    from qdrant_client import QdrantClient

    collection = "legal_unified_hybrid_hybrid"
    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    live = {c.name for c in client.get_collections().collections}
    if collection not in live:
        print("BROKEN — collection %s absent from Qdrant. Nothing measured." % collection,
              file=sys.stderr)
        return 3

    total_points = 0
    damaged = []  # list of dicts: id, document_id, section, text
    by_doc = collections.Counter()
    offset = None
    scrolled_complete = False
    while True:
        batch, offset = client.scroll(
            collection, limit=1000, offset=offset, with_payload=True, with_vectors=False
        )
        if not batch:
            scrolled_complete = True
            break
        for point in batch:
            total_points += 1
            payload = point.payload or {}
            if not signal.is_unmarked_penjelasan_fragment(payload):
                continue
            text = get_text(payload)
            section = get_section(payload)
            did = get_document_id(payload)
            damaged.append({
                "id": str(point.id),
                "document_id": did,
                "section": section,
                "text": text,
            })
            by_doc[did] += 1
        if offset is None:
            scrolled_complete = True
            break

    if not scrolled_complete:
        print("BROKEN — scroll did not complete (no terminal offset=None seen). "
              "Whole-or-nothing: refusing to report a partial count.", file=sys.stderr)
        return 3

    print("total points scrolled: %d" % total_points)
    print("damaged fragments (section != penjelasan AND contains 'Cukup jelas'): %d"
          % len(damaged))
    print("damaged documents: %d" % len(by_doc))
    print()
    print("top 10 documents by damaged-fragment count:")
    for doc, count in by_doc.most_common(10):
        print("  %-30s %d" % (doc, count))

    # Stratified sample: pick documents spanning the distribution, then sample
    # fragments within each, so the sample isn't dominated by one mega-document.
    docs_sorted = sorted(by_doc.keys())
    rng = random.Random(20260825)  # fixed seed, reproducible, not time-based
    rng.shuffle(docs_sorted)

    sample = []
    target = 45
    # Round-robin across documents until we hit target, so many distinct docs
    # are represented rather than exhausting one document first.
    by_doc_fragments = collections.defaultdict(list)
    for item in damaged:
        by_doc_fragments[item["document_id"]].append(item)
    for lst in by_doc_fragments.values():
        rng.shuffle(lst)

    doc_cycle = list(by_doc_fragments.keys())
    rng.shuffle(doc_cycle)
    idx_per_doc = collections.Counter()
    i = 0
    while len(sample) < target and any(
        idx_per_doc[d] < len(by_doc_fragments[d]) for d in doc_cycle
    ):
        doc = doc_cycle[i % len(doc_cycle)]
        if idx_per_doc[doc] < len(by_doc_fragments[doc]):
            sample.append(by_doc_fragments[doc][idx_per_doc[doc]])
            idx_per_doc[doc] += 1
        i += 1

    # research/legal/, NOT kb/inventory/ — that directory's gate globs *.yaml
    # only and is reserved for curated inventories; this is a reproducible
    # scratch measurement (rerun this script to regenerate it), not committed.
    out_path = root / "research" / "legal" / "_cukup_jelas_sample.json"
    out_path.write_text(json.dumps({
        "total_points": total_points,
        "damaged_fragment_count": len(damaged),
        "damaged_document_count": len(by_doc),
        "by_doc_top10": by_doc.most_common(10),
        "sample_size": len(sample),
        "sample_method": "stratified round-robin across distinct documents, seed=20260825, "
                          "NOT the first N found",
        "sample": sample,
    }, indent=2, ensure_ascii=False))
    print()
    print("wrote %d-item sample across %d distinct documents to %s"
          % (len(sample), len(set(s["document_id"] for s in sample)), out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
