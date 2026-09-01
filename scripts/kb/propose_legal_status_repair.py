#!/usr/bin/env python3
"""propose_legal_status_repair — dry-run diff ONLY. Never writes to Qdrant.

Companion to audit_legal_status.py. That audit found `legal_status` is not a
document-level legal fact: it is derived per-chunk by a bare regex
(`apps/backend-rag/backend/core/legal/constants.py::STATUS_PATTERNS`) matching the
literal substrings DICABUT|TIDAK BERLAKU|DIGANTI vs BERLAKU|MASIH BERLAKU anywhere
in the chunk text, dict-order-first-match, with zero grammatical disambiguation of
what the match refers to. Sampled directly against production text (not inferred):
the DIGANTI pattern fires on the generic verb "digantikan" (a guarantor being
substituted, nothing to do with the regulation's status); TIDAK BERLAKU fires on
"Izin Tinggal yang tidak berlaku lagi" (an individual's STAY PERMIT expiring) and on
"ketentuan ... tidak berlaku terhadap warga negara Indonesia" (a provision not
applying to a class of person); and — the specific defect Decision 5 exists to
answer — a law's own standard closing clause revoking ITS PREDECESSORS
("Keputusan Presiden Nomor 31 Tahun 1998 ... dicabut dan dinyatakan tidak
berlaku") gets read as the CURRENT, still-valid document being revoked.

Given that mechanism, a corpus-wide row-patch is NOT proposed here — it would make
590+ other document_ids' values look equally trustworthy when the audit gives no
basis for that. This script proposes ONLY the narrow set of document_ids lane A
externally verified against peraturan.go.id / peraturan.bpk.go.id this session
(kb/topics/immigration.yaml), where a specific correct value can be named with a
source. Print-only: no --apply flag exists. Applying is the orchestrator's decision
once the audit has been reviewed.

Run: apps/backend-rag/.venv/bin/python scripts/kb/propose_legal_status_repair.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# document_id -> (current census value, proposed value, source)
# Restricted to instruments lane A verified this session with a live source_url
# fetch/search (kb/topics/immigration.yaml) AND that are actually present in
# legal_unified_hybrid_hybrid. Permen_27_2021 is deliberately EXCLUDED: its real
# status is recorded as `unknown` in kb/topics/immigration.yaml (source_verified:
# false) — proposing a value for it here would be exactly the guessing the mandate
# forbids ("If external verification of a given instrument is not possible, say
# UNDETERMINED for that one — do not guess").
PROPOSED_CORRECTIONS = {
    "UU_6_2011": (
        "dicabut", "berlaku",
        "peraturan.go.id: base articles still valid (amended by UU 63/2024, not "
        "repealed). kb/topics/immigration.yaml status=amended.",
    ),
    "Permen_22_2023": (
        "dicabut", "berlaku",
        "peraturan.go.id direct fetch 2026-08-25: current Visa dan Izin Tinggal "
        "regulation, amended by Permen_11_2024, not revoked. This is the exact "
        "instrument journey 3/4 (kb/journeys/immigration.yaml) named as the live "
        "defect.",
    ),
    "Permen_11_2024": (
        "dicabut", "berlaku",
        "peraturan.bpk.go.id + Permen_22_2023's own page: the 2024 amendment "
        "currently in force, not revoked.",
    ),
    "PP_31_2013": (
        "dicabut", "berlaku",
        "web search: standing implementing regulation for UU 6/2011, amended "
        "(most recently by PP 40/2023), not repealed. NOTE: lane A left OPEN "
        "whether the corpus TEXT reflects the article content as amended through "
        "PP 40/2023 or only the 2013 original — this correction addresses only "
        "the legal_status field, not that separate open question.",
    ),
}
# Verified correct, listed for completeness so this file is a full account of
# lane A's 7 present, real-status-known instruments — NOT proposed as changes:
#   Permen_29_2021: dicabut (340 pts) — genuinely superseded by Permen_22_2023.
#   UU_63_2024:     berlaku (38 pts)  — genuinely in force.
# Excluded (real status not established with a source):
#   Permen_27_2021: dicabut (6 pts) — kb/topics/immigration.yaml records
#                   status=unknown, source_verified=false. UNDETERMINED, not
#                   proposed.


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("propose_legal_status_repair: repo root not found")


def load_env(root: Path) -> None:
    env = root / "apps" / "backend-rag" / ".env"
    if not env.is_file():
        print(f"BROKEN — {env} not found, no credentials to reach Qdrant with.",
              file=sys.stderr)
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def extract_legal_status_location(payload: dict) -> str:
    """Returns 'top', 'metadata', 'both', or 'none' — where the point's own
    legal_status field actually lives, so the diff line shows exactly which key
    a real repair script would need to touch on THIS point."""
    meta = payload.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    top_present = "legal_status" in payload and payload.get("legal_status") is not None  # legal-status-lint: allow — proposes a MARKed, human-reviewed repair, does not decide with the field itself
    nested_present = "legal_status" in meta and meta.get("legal_status") is not None  # legal-status-lint: allow — proposes a MARKed, human-reviewed repair, does not decide with the field itself
    if top_present and nested_present:
        return "both"
    if top_present:
        return "top"
    if nested_present:
        return "metadata"
    return "none"


def main() -> int:
    root = repo_root()
    load_env(root)
    from qdrant_client import QdrantClient

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300
    )
    collection = "legal_unified_hybrid_hybrid"

    print("=== propose_legal_status_repair — DRY RUN, NOTHING IS WRITTEN ===")
    print(f"collection: {collection}\n")
    print("Scope: lane-A externally-verified immigration instruments ONLY. This is")
    print("NOT a corpus-wide repair proposal — see the audit for why one row-patch")
    print("pass cannot make the field trustworthy at large.\n")

    total_points_changed = 0
    for doc_id, (expect_from, to_value, source) in PROPOSED_CORRECTIONS.items():
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        flt = Filter(should=[
            FieldCondition(key="document_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="metadata.document_id", match=MatchValue(value=doc_id)),
        ])
        offset = None
        n_points = 0
        n_matching_expected = 0
        locations = {"top": 0, "metadata": 0, "both": 0, "none": 0}
        while True:
            batch, offset = client.scroll(
                collection, scroll_filter=flt, limit=1000, offset=offset,
                with_payload=True, with_vectors=False,
            )
            if not batch:
                break
            for point in batch:
                payload = point.payload or {}
                meta = payload.get("metadata")
                meta = meta if isinstance(meta, dict) else {}
                current = payload.get("legal_status") or meta.get("legal_status")  # legal-status-lint: allow — proposes a MARKed, human-reviewed repair, does not decide with the field itself
                n_points += 1
                if str(current) == expect_from:
                    n_matching_expected += 1
                locations[extract_legal_status_location(payload)] += 1
            if offset is None:
                break

        print(f"--- {doc_id} ---")
        print(f"  proposed: {expect_from!r} -> {to_value!r}")
        print(f"  source:   {source}")
        print(f"  live points matching document_id: {n_points}")
        print(f"  of those, currently == {expect_from!r}: {n_matching_expected}")
        print(f"  field location across these points: {locations}")
        if n_points != n_matching_expected:
            print(f"  ⚠ {n_points - n_matching_expected} point(s) do NOT currently "
                  f"hold {expect_from!r} — census may have moved since the audit ran, "
                  f"or a point already has a different value. A real repair script "
                  f"must re-check per-point, not assume uniformity.")
        print(f"  WOULD WRITE {n_matching_expected} point(s): legal_status "
              f"{expect_from!r} -> {to_value!r} (in whichever of top-level/"
              f"metadata key each point actually holds it)")
        print(f"  NOTHING WRITTEN (dry-run only, no --apply flag exists in this script)")
        print()
        total_points_changed += n_matching_expected

    print(f"=== TOTAL: {total_points_changed} points across "
          f"{len(PROPOSED_CORRECTIONS)} document_ids WOULD change if applied ===")
    print("No write performed. This script has no code path that calls .set_payload/")
    print(".overwrite_payload — the apply step, if authorized, is separate work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
