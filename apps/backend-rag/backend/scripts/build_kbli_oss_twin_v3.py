"""
Build the OSS twin `kbli_2025_final_oss` in PRODUCTION-NATIVE CHUNKED format (v3 — the real fix).

The journey:
- v1: reused reindex_kbli_2025_final flat format → lower retrieval scores (ABSTAIN risk).
- v2: replicated the native plain-text format but kept 1 point/code → STILL lower scores.
- v3 (this): the discriminating experiment proved the cause is CHUNKING. The live collection
  splits each code into:
    * one `_uraian` chunk  = pure BPS description (this is what semantic queries match)
    * one chunk per per_skala group = scale + licensing detail
  Verified on disk from live 56101 (4 chunks: _mikro_0, _kecil_menengah_besar_1, _uraian, _mikro_kecil_2)
  and the distribution {2:776,3:301,4:366,5:58,6:38,7:17,8:4,9:4} over 1564 codes = 4618 points.

v3 replicates that chunking EXACTLY + injects L4 Bali into the _uraian chunk (text + metadata),
so retrieval parity holds AND the Bali block rides on the chunk that matches activity queries.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/build_kbli_oss_twin_v3.py [--limit N] [--dry-run]
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LIVE = "kbli_2025_final_hybrid"
TWIN = "kbli_2025_final_oss"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH = 50
UPSERT_BATCH = 50
PHANTOMS = {"26120", "60111", "82920", "85598"}

SOURCE_FILE = Path(__file__).resolve().parents[4] / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def det_uuid(key: str) -> str:
    return str(uuid.UUID(hashlib.md5(key.encode()).hexdigest()))


def l4_text_block(e: dict) -> list[str]:
    l4 = e.get("l4_bali") or {}
    if not l4.get("status"):
        return []
    out = ["", "STATUS PMA DI BALI (L4 - moratorium provinsi 2026-05-13):"]
    if l4.get("blocked"):
        out.append("- DIBLOKIR untuk PMA di Bali (kegiatan risiko Rendah/Menengah-Rendah).")
    out.append(f"- Status Bali: {l4['status']}")
    if l4.get("reason"):
        out.append(f"- Catatan: {l4['reason']}")
    out.append("- Nasional bisa TERBUKA 100% sementara Bali memblokir.")
    return out


def l4_meta(e: dict) -> dict:
    l4 = e.get("l4_bali") or {}
    return {
        "bali_status": l4.get("status", ""),
        "bali_blocked": bool(l4.get("blocked")),
        "bali_reason": l4.get("reason", ""),
    }


def build_chunks(e: dict) -> list[dict]:
    """Return list of {id, text, metadata} chunks for one code, mirroring live anatomy."""
    code = e["kode_kbli_2025"]
    judul = e.get("judul", "")
    sektor = e.get("sektor_id", "")
    pma = e.get("pma_status", "")
    pma_max = e.get("pma_max_asing", "")
    uraian = e.get("uraian", "")
    base_meta = {
        "kode_kbli": code, "kode": code, "kode_kbli_2025": code,
        "judul": judul, "sektor_id": sektor,
        "pma_status": pma, "pma_max_asing": pma_max,
        "doc_type": "kbli_bps",
        **l4_meta(e),
    }
    chunks = []

    # 1) _uraian chunk — pure description + L4 (this matches activity queries)
    utext = "\n".join(
        [f"[KBLI {code}] {judul}", "", uraian] + l4_text_block(e),
    )
    chunks.append({
        "id": det_uuid(f"kbli_2025_oss::{code}::uraian"),
        "text": utext,
        "metadata": {**base_meta, "chunk_id": f"kbli_{code}_uraian", "chunk_type": "uraian"},
    })

    # 2) one chunk per per_skala group (scale + licensing detail)
    for i, s in enumerate(e.get("per_skala", []) or []):
        scales = s.get("skala_usaha", []) or []
        scale_tag = "_".join(sc.lower() for sc in scales) or f"grp{i}"
        risk = s.get("kategori_risiko", "")
        lines = [
            f"KBLI {code} - {judul}",
            f"Skala Usaha: {', '.join(scales)}" if scales else "Skala Usaha: -",
            f"Kategori Risiko: {risk}" if risk else "Kategori Risiko: -",
            "",
            f"Sektor: {sektor}",
            f"Status PMA: {pma}" + (f" (Max {pma_max}%)" if pma_max not in ("", None) else ""),
            "",
            "PERIZINAN:",
            f"- Jenis Izin: {s.get('perizinan', '')}",
            f"- Jangka Waktu Penerbitan: {s.get('jangka_waktu', '')}",
            f"- Kewenangan: {s.get('kewenangan', '')}",
            f"- Fiktif Positif: {'Ya (auto-approval berlaku)' if s.get('fiktif_positif') else 'Tidak'}",
        ]
        persy = s.get("persyaratan", []) or []
        lines.append("")
        if persy:
            lines.append("PERSYARATAN DOKUMEN:")
            lines += [f"- {x}" for x in persy]
        else:
            lines.append("PERSYARATAN DOKUMEN: Tidak ada persyaratan khusus")
        kew = s.get("kewajiban", []) or []
        if kew:
            lines.append("")
            lines.append("KEWAJIBAN PELAKU USAHA:")
            lines += [f"- {x}" for x in kew]
        lines += l4_text_block(e)
        chunks.append({
            "id": det_uuid(f"kbli_2025_oss::{code}::skala::{scale_tag}::{i}"),
            "text": "\n".join(lines),
            "metadata": {
                **base_meta,
                "chunk_id": f"kbli_{code}_{scale_tag}_{i}",
                "chunk_type": "per_skala",
                "skala_usaha": scales,
                "kategori_risiko": risk,
                "perizinan": s.get("perizinan", ""),
                "jangka_waktu": s.get("jangka_waktu", ""),
                "kewenangan": s.get("kewenangan", ""),
                "fiktif_positif": bool(s.get("fiktif_positif")),
            },
        })
    return chunks


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    qurl = os.environ["QDRANT_URL"].rstrip("/")
    qkey = os.environ.get("QDRANT_API_KEY", "")
    H = {"Content-Type": "application/json"}
    if qkey:
        H["api-key"] = qkey

    source = json.load(open(SOURCE_FILE, encoding="utf-8"))
    entries = [e for e in source["data"]
               if len(str(e.get("kode_kbli_2025", ""))) == 5 and e["kode_kbli_2025"] not in PHANTOMS]
    if args.limit:
        entries = entries[: args.limit]

    all_chunks = []
    for e in entries:
        all_chunks.extend(build_chunks(e))
    logger.info(f"codes={len(entries)} -> chunks={len(all_chunks)} (live has ~4618)")
    l4c = sum(1 for c in all_chunks if c["metadata"].get("bali_status"))
    logger.info(f"chunks carrying bali_status: {l4c}")

    if args.dry_run:
        s = next((c for c in all_chunks if c["metadata"]["kode_kbli"] == "56101"), all_chunks[0])
        logger.info(f"sample chunk {s['metadata']['chunk_id']}:\n{s['text'][:400]}")
        codes_56101 = [c["metadata"]["chunk_id"] for c in all_chunks if c["metadata"]["kode_kbli"] == "56101"]
        logger.info(f"56101 chunks: {codes_56101}")
        return

    from openai import AsyncOpenAI

    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    texts = [c["text"] for c in all_chunks]
    embs = []
    for i in range(0, len(texts), EMBED_BATCH):
        resp = await oai.embeddings.create(model=EMBEDDING_MODEL, input=texts[i : i + EMBED_BATCH])
        embs.extend(d.embedding for d in resp.data)
        if i % 500 == 0:
            logger.info(f"  embedded {i}/{len(texts)}")
    logger.info(f"got {len(embs)} dense vectors")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.core.bm25_vectorizer import BM25Vectorizer

    bm = BM25Vectorizer()
    tl = [len(bm.tokenize(t)) for t in texts]
    bm.update_avg_doc_length(sum(tl) / len(tl))
    sparse = [bm.generate_sparse_vector(t) for t in texts]
    logger.info(f"got {len(sparse)} bm25 vectors")

    async with httpx.AsyncClient(timeout=120) as http:
        sch = (await http.get(f"{qurl}/collections/{LIVE}", headers=H)).json()["result"]["config"]["params"]
        await http.delete(f"{qurl}/collections/{TWIN}", headers=H)
        r = await http.put(f"{qurl}/collections/{TWIN}",
                           json={"vectors": sch["vectors"], "sparse_vectors": sch.get("sparse_vectors", {"bm25": {}})},
                           headers=H)
        r.raise_for_status()
        logger.info(f"created {TWIN}")
        qp = [{"id": c["id"], "vector": {"dense": e, "bm25": s},
               "payload": {"text": c["text"], "metadata": c["metadata"]}}
              for c, e, s in zip(all_chunks, embs, sparse, strict=False)]
        for i in range(0, len(qp), UPSERT_BATCH):
            r = await http.put(f"{qurl}/collections/{TWIN}/points?wait=true",
                               json={"points": qp[i : i + UPSERT_BATCH]}, headers=H)
            r.raise_for_status()
        tc = (await http.get(f"{qurl}/collections/{TWIN}", headers=H)).json()["result"]["points_count"]
        lc = (await http.get(f"{qurl}/collections/{LIVE}", headers=H)).json()["result"]["points_count"]
        logger.info(f"TWIN {TWIN}: {tc} chunks | LIVE {LIVE}: {lc} (untouched)")
    logger.info("Done v3 — chunked native format. Live untouched.")


if __name__ == "__main__":
    asyncio.run(main())
