#!/usr/bin/env python3
"""Lane B (company & investment) scratch investigation — NOT a committed artifact.

One full scroll of legal_unified_hybrid_hybrid, then a set of targeted reports:
  A. UU_25_2007 containment ratio (Pasal-marker count, char count, sample chunks)
  B. Permen_1_2026 ministry-collision classification (PMK vs Permenimipas per point)
  C. UU_13_2017 / UU_49_2021 / Permen_5_2025 title + sample read
  D. Company/investment keyword scan across all distinct document_ids (candidate
     instruments for lane B scope: KBLI, OSS, BKPM, PT/PMA, modal, LKPM, NIB, akta, BPJS)
"""
from __future__ import annotations

import collections
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
    if not env.is_file():
        print("BROKEN — %s not found." % env, file=sys.stderr)
        raise SystemExit(3)
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


ROOT = repo_root()
load_env(ROOT)
from qdrant_client import QdrantClient  # noqa: E402

CTX = re.compile(r"^\[CONTEXT:([^\]]*)\]\s*", re.S)
WS = re.compile(r"\s+")
PASAL = re.compile(r"\bPasal\s+\d+[A-Za-z]?\b", re.IGNORECASE)


def get_meta(payload):
    m = payload.get("metadata")
    return m if isinstance(m, dict) else {}


def get_document_id(payload):
    meta = get_meta(payload)
    return payload.get("document_id") or meta.get("document_id") or "<none>"


def get_text(payload):
    meta = get_meta(payload)
    return payload.get("text") or payload.get("content") or meta.get("text") or ""


def get_title_header(text):
    m = CTX.match(text or "")
    return m.group(1).strip() if m else None


COLLECTION = "legal_unified_hybrid_hybrid"

TARGETS = [
    "UU_25_2007",
    "UU_40_2007",
    "Permen_1_2026",
    "UU_13_2017",
    "UU_49_2021",
    "Permen_5_2025",
]

KEYWORDS = [
    "kbli", "oss", "bkpm", "penanaman modal", "perseroan terbatas",
    "modal disetor", "lkpm", "nib", "akta", "bpjs", "badan usaha",
    "perizinan berusaha", "koperasi", "usaha mikro", "kecil menengah",
    "umkm", "klasifikasi baku lapangan usaha",
]


def main():
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=300)
    live = {c.name for c in client.get_collections().collections}
    if COLLECTION not in live:
        print("BROKEN — %s absent" % COLLECTION, file=sys.stderr)
        return 3

    by_doc_count = collections.Counter()
    title_by_doc = {}
    target_points = collections.defaultdict(list)  # doc_id -> list of (id, text, section)
    total = 0
    scrolled_complete = False
    offset = None
    while True:
        batch, offset = client.scroll(COLLECTION, limit=1000, offset=offset, with_payload=True, with_vectors=False)
        if not batch:
            scrolled_complete = True
            break
        for point in batch:
            total += 1
            payload = point.payload or {}
            did = get_document_id(payload)
            by_doc_count[did] += 1
            text = get_text(payload)
            if did not in title_by_doc:
                title = get_title_header(text)
                if title:
                    title_by_doc[did] = title
            if did in TARGETS:
                meta = get_meta(payload)
                section = payload.get("section") or meta.get("section")
                target_points[did].append((str(point.id), text, section))
        if offset is None:
            scrolled_complete = True
            break

    if not scrolled_complete:
        print("BROKEN — scroll incomplete, whole-or-nothing refuses partial report.", file=sys.stderr)
        return 3

    out = {}
    out["total_points"] = total
    out["total_distinct_documents"] = len(by_doc_count)

    # ── A/B/C: per-target report ─────────────────────────────────────────
    targets_report = {}
    for did in TARGETS:
        pts = target_points.get(did, [])
        n = len(pts)
        chars = sum(len(WS.sub(" ", CTX.sub("", t)).strip()) for _, t, _ in pts)
        pasal_markers = set()
        for _, t, _ in pts:
            for m in PASAL.finditer(t):
                pasal_markers.add(m.group(0).lower().replace("  ", " "))
        title = title_by_doc.get(did)
        targets_report[did] = {
            "points": n,
            "chars": chars,
            "distinct_pasal_markers": len(pasal_markers),
            "pasal_markers_sample": sorted(pasal_markers)[:60],
            "title_header": title,
        }
    out["targets"] = targets_report

    # ── UU_25_2007 sample chunks (first 3, all if <=5) for manual read ────
    u25 = target_points.get("UU_25_2007", [])
    out["UU_25_2007_samples"] = [
        {"id": pid, "section": sec, "text_normalized": WS.sub(" ", CTX.sub("", t)).strip()[:1500]}
        for pid, t, sec in u25
    ]

    # ── Permen_1_2026 ministry-collision classification ───────────────────
    p1 = target_points.get("Permen_1_2026", [])
    pmk_markers = re.compile(r"\bPMK\b|kementerian keuangan|coretax|nomor induk berusaha wajib pajak", re.IGNORECASE)
    imipas_markers = re.compile(r"imigrasi|imipas|keimigrasian|pemasyarakatan", re.IGNORECASE)
    classification = collections.Counter()
    class_samples = collections.defaultdict(list)
    for pid, t, sec in p1:
        header = get_title_header(t) or ""
        is_pmk = bool(pmk_markers.search(header) or pmk_markers.search(t[:2000]))
        is_imipas = bool(imipas_markers.search(header) or imipas_markers.search(t[:2000]))
        if is_pmk and not is_imipas:
            cls = "pmk"
        elif is_imipas and not is_pmk:
            cls = "permenimipas"
        elif is_pmk and is_imipas:
            cls = "ambiguous_both"
        else:
            cls = "neither"
        classification[cls] += 1
        if len(class_samples[cls]) < 3:
            class_samples[cls].append({"id": pid, "header": header, "section": sec,
                                        "text_normalized": WS.sub(" ", CTX.sub("", t)).strip()[:400]})
    out["Permen_1_2026_classification"] = dict(classification)
    out["Permen_1_2026_samples"] = {k: v for k, v in class_samples.items()}
    out["Permen_1_2026_total_points"] = len(p1)

    # ── UU_13_2017 / UU_49_2021 / Permen_5_2025 sample chunks ──────────────
    for did in ["UU_13_2017", "UU_49_2021", "Permen_5_2025"]:
        pts = target_points.get(did, [])
        samples = []
        # spread: first, middle, last
        idxs = sorted(set([0, len(pts) // 2, len(pts) - 1])) if pts else []
        for i in idxs:
            if 0 <= i < len(pts):
                pid, t, sec = pts[i]
                samples.append({"id": pid, "section": sec,
                                 "text_normalized": WS.sub(" ", CTX.sub("", t)).strip()[:900]})
        out.setdefault("other_samples", {})[did] = samples

    # ── D: company/investment keyword scan over ALL distinct doc titles ────
    matches = []
    for did, title in title_by_doc.items():
        low = title.lower()
        hit_kw = [kw for kw in KEYWORDS if kw in low]
        if hit_kw:
            matches.append({
                "document_id": did,
                "points": by_doc_count[did],
                "title_header": title,
                "matched_keywords": hit_kw,
            })
    matches.sort(key=lambda m: -m["points"])
    out["keyword_scan_matches"] = matches
    out["keyword_scan_match_count"] = len(matches)
    out["distinct_documents_scanned"] = len(title_by_doc)

    out_path = ROOT / "research" / "legal" / "_lane_b_investigation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote report to %s" % out_path)
    print("total_points=%d distinct_documents=%d" % (out["total_points"], out["total_distinct_documents"]))
    print("keyword_scan_match_count=%d" % out["keyword_scan_match_count"])
    for did in TARGETS:
        t = targets_report[did]
        print("%-16s points=%-6d chars=%-8d distinct_pasal_markers=%-4d title=%r"
              % (did, t["points"], t["chars"], t["distinct_pasal_markers"], t["title_header"]))
    print("Permen_1_2026 classification:", dict(classification))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
