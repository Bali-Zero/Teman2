#!/usr/bin/env python3
"""Lane B pass 2 — scratch, NOT committed.

1. Extended company/investment keyword scan over ALL 388 docs (not just those
   with a [CONTEXT] header — checks metadata title fields + raw text prefix too).
2. Cukup-jelas damage count for lane-B candidate documents.
3. Permen_1_2026 distinct-title-header census (how many ministries actually collide).
4. UU_25_2007 categorisation: literal "Cukup jelas" vs elucidation-prose vs
   administrative boilerplate vs genuine operative-article text.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import re
import sys
from pathlib import Path


def repo_root(start=None):
    here = (start or Path(__file__)).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise SystemExit("repo root not found")


def load_env(root):
    env = root / "apps" / "backend-rag" / ".env"
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


ROOT = repo_root()
load_env(ROOT)

spec = importlib.util.spec_from_file_location("cukup_jelas_signal", ROOT / "scripts" / "kb" / "cukup_jelas_signal.py")
signal = importlib.util.module_from_spec(spec)
sys.modules["cukup_jelas_signal"] = signal
spec.loader.exec_module(signal)

from qdrant_client import QdrantClient  # noqa: E402

COLLECTION = "legal_unified_hybrid_hybrid"
CTX = re.compile(r"^\[CONTEXT:([^\]]*)\]\s*", re.S)
WS = re.compile(r"\s+")

KEYWORDS = [
    "kbli", "oss", "bkpm", "penanaman modal", "perseroan terbatas",
    "modal disetor", "lkpm", "nib", "akta pendirian", "bpjs", "badan usaha",
    "perizinan berusaha", "koperasi", "usaha mikro", "klasifikasi baku lapangan usaha",
    "penanaman modal asing", "izin usaha", "izin berusaha",
]

LANE_B_CANDIDATES = [
    "UU_25_2007", "UU_40_2007", "Permen_1_2026", "UU_13_2017", "UU_49_2021",
    "Permen_5_2025", "PP_7_2025", "PP_28_2025", "UU_16_2025", "DOC_UNKNOWN_UNKNOWN",
]

CUKUP_JELAS = signal.CUKUP_JELAS
UMUM_EXPL = re.compile(r"\byang dimaksud dengan\b", re.IGNORECASE)
SIGNATURE_BLOCK = re.compile(r"presiden republik indonesia|diundangkan di jakarta|ditetapkan di jakarta|lembaran negara|menteri (keuangan|hukum)", re.IGNORECASE)


def main():
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300)

    by_doc_count = collections.Counter()
    title_by_doc = {}          # from [CONTEXT] header, first seen
    meta_title_by_doc = {}     # from metadata fields, first seen
    text_prefix_by_doc = {}    # raw text prefix fallback, first seen
    permen_1_2026_headers = collections.Counter()
    u25_categories = collections.Counter()
    lane_b_damage = collections.defaultdict(lambda: {"points": 0, "damaged": 0})

    offset = None
    total = 0
    complete = False
    while True:
        batch, offset = client.scroll(COLLECTION, limit=1000, offset=offset, with_payload=True, with_vectors=False)
        if not batch:
            complete = True
            break
        for point in batch:
            total += 1
            payload = point.payload or {}
            did = signal.get_document_id(payload)
            by_doc_count[did] += 1
            text = signal.get_text(payload)

            if did not in title_by_doc:
                m = CTX.match(text or "")
                if m:
                    title_by_doc[did] = m.group(1).strip()
            if did not in meta_title_by_doc:
                meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
                for key in ("title", "document_title", "judul", "nama"):
                    v = payload.get(key) or meta.get(key)
                    if v:
                        meta_title_by_doc[did] = str(v)
                        break
            if did not in text_prefix_by_doc:
                norm = WS.sub(" ", CTX.sub("", text or "")).strip()
                if norm:
                    text_prefix_by_doc[did] = norm[:200]

            if did == "Permen_1_2026":
                m = CTX.match(text or "")
                header = m.group(1).strip() if m else "<no-header>"
                permen_1_2026_headers[header] += 1

            if did in LANE_B_CANDIDATES:
                lane_b_damage[did]["points"] += 1
                if signal.is_unmarked_penjelasan_fragment(payload):
                    lane_b_damage[did]["damaged"] += 1

            if did == "UU_25_2007":
                norm = WS.sub(" ", CTX.sub("", text or "")).strip()
                low = norm.lower()
                if CUKUP_JELAS.search(low) and len(norm) < 40:
                    u25_categories["bare_cukup_jelas"] += 1
                elif CUKUP_JELAS.search(low):
                    u25_categories["cukup_jelas_plus_more"] += 1
                elif UMUM_EXPL.search(low):
                    u25_categories["elucidation_prose_yang_dimaksud"] += 1
                elif SIGNATURE_BLOCK.search(low):
                    u25_categories["administrative_boilerplate"] += 1
                else:
                    u25_categories["other_narrative"] += 1
        if offset is None:
            complete = True
            break

    if not complete:
        print("BROKEN — scroll incomplete", file=sys.stderr)
        return 3

    out = {}
    out["total_points"] = total
    out["total_distinct_documents"] = len(by_doc_count)

    # extended keyword scan: header OR meta title OR text prefix
    matches = []
    for did in by_doc_count:
        candidates_text = " ".join(filter(None, [
            title_by_doc.get(did, ""), meta_title_by_doc.get(did, ""), text_prefix_by_doc.get(did, ""),
        ])).lower()
        hit = [kw for kw in KEYWORDS if kw in candidates_text]
        if hit:
            matches.append({
                "document_id": did,
                "points": by_doc_count[did],
                "title_header": title_by_doc.get(did),
                "meta_title": meta_title_by_doc.get(did),
                "text_prefix": text_prefix_by_doc.get(did),
                "matched_keywords": hit,
            })
    matches.sort(key=lambda m: -m["points"])
    out["extended_keyword_matches"] = matches
    out["extended_keyword_match_count"] = len(matches)

    out["permen_1_2026_distinct_headers"] = dict(permen_1_2026_headers.most_common(30))
    out["permen_1_2026_distinct_header_count"] = len(permen_1_2026_headers)

    out["uu_25_2007_categories"] = dict(u25_categories)

    out["lane_b_damage"] = {k: v for k, v in lane_b_damage.items()}

    out_path = ROOT / "research" / "legal" / "_lane_b_investigation2.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", out_path)
    print("extended_keyword_match_count=%d (vs 7 header-only)" % out["extended_keyword_match_count"])
    print("permen_1_2026 distinct headers: %d" % out["permen_1_2026_distinct_header_count"])
    for h, c in permen_1_2026_headers.most_common(10):
        print("  %6d  %s" % (c, h[:120]))
    print("UU_25_2007 categories:", dict(u25_categories))
    print("lane_b_damage:")
    for did, v in lane_b_damage.items():
        print("  %-20s points=%-6d damaged=%d" % (did, v["points"], v["damaged"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
