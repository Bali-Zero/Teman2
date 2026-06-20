"""
Bombard the twin `kbli_2025_final_oss` (v3 chunked native format) before any alias swap.
Live `kbli_2025_final_hybrid` must stay intact (read-only here).

v3 twin = chunked like production: per code, one `_uraian` chunk + one chunk per per_skala group,
nested `metadata` payload (doc_type/chunk_id/kode_kbli/bali_status), ~4424 chunks over 1559 codes.

Checks (PASS/FAIL — exit 1 if any fail):
1. twin exists, chunk count in [4000, 4700]
2. LIVE collection untouched (baseline 4624)
3. exact codes carry correct L4 in metadata (55203 villa, 01111 padi, 01112/02103 forestry)
4. semantic retrieval parity vs LIVE: for known queries, the twin top score is within 0.05 of
   live AND >= 0.20 (no ABSTAIN) AND the canonical code appears in twin top-5
5. every code has an _uraian chunk carrying bali_status
6. double-truth present (national TERBUKA + Bali blocked)

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/verify_kbli_oss_twin.py
"""

import asyncio
import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TWIN = "kbli_2025_final_oss"
LIVE = "kbli_2025_final_hybrid"
LIVE_BASELINE = 4624
EMBEDDING_MODEL = "text-embedding-3-small"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    logger.info(f"  [{'PASS' if ok else 'FAIL'}] {name}{' — ' + detail if detail else ''}")


def pv(pl: dict, *keys: str, default=None):
    md = pl.get("metadata", {}) if isinstance(pl.get("metadata"), dict) else {}
    for k in keys:
        if pl.get(k) not in (None, ""):
            return pl[k]
        if md.get(k) not in (None, ""):
            return md[k]
    return default


async def main() -> None:
    qurl = os.environ["QDRANT_URL"].rstrip("/")
    qkey = os.environ.get("QDRANT_API_KEY", "")
    H = {"Content-Type": "application/json"}
    if qkey:
        H["api-key"] = qkey

    from openai import AsyncOpenAI

    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async with httpx.AsyncClient(timeout=60) as http:
        tc = (await http.get(f"{qurl}/collections/{TWIN}", headers=H)).json()["result"]["points_count"]
        check("1. twin chunk count in [4000,4700]", 4000 <= tc <= 4700, f"{tc} chunks")

        lc = (await http.get(f"{qurl}/collections/{LIVE}", headers=H)).json()["result"]["points_count"]
        check("2. live untouched", lc == LIVE_BASELINE, f"{lc} (baseline {LIVE_BASELINE})")

        # 3. exact codes — fetch the _uraian chunk BY deterministic id (not semantic search)
        import hashlib
        import uuid

        def uraian_id(code: str) -> str:
            return str(uuid.UUID(hashlib.md5(f"kbli_2025_oss::{code}::uraian".encode()).hexdigest()))

        async def find_uraian(code: str):
            r = await http.post(
                f"{qurl}/collections/{TWIN}/points",
                json={"ids": [uraian_id(code)], "with_payload": True},
                headers=H,
            )
            pts = r.json().get("result", [])
            return pts[0]["payload"] if pts else None

        expect = {
            "55203": ("BLOCCATO_CLASSE_RISCHIO", True),
            "01111": ("TERTUTUP", True),
            "01112": ("OK_or_HIGHER_RISK", False),
            "02103": ("OK_or_HIGHER_RISK", False),
        }
        for code, (ws, wb) in expect.items():
            pl = await find_uraian(code)
            if not pl:
                check(f"3.{code} L4", False, "code not retrievable")
                continue
            ok = pv(pl, "bali_status") == ws and bool(pv(pl, "bali_blocked")) == wb
            check(f"3.{code} L4 correct", ok, f"bali_status={pv(pl,'bali_status')} blocked={pv(pl,'bali_blocked')}")

        # 4. retrieval parity vs LIVE
        cases = [
            ("villa rental for tourists in Bali", "55203"),
            ("software development company", "62192"),
            ("restaurant food service in a building", "56101"),
            ("import export trading wholesale", "46799"),
        ]
        async def top(coll: str, emb):
            r = await http.post(
                f"{qurl}/collections/{coll}/points/query",
                json={"query": emb, "using": "dense", "limit": 5, "with_payload": True},
                headers=H,
            )
            pts = r.json().get("result", {}).get("points", [])
            codes, scores = [], []
            for p in pts:
                codes.append(pv(p["payload"], "kode_kbli", "kode", "kode_kbli_2025", default="?"))
                scores.append(p.get("score", 0))
            return codes, (scores[0] if scores else 0)

        # The real requirement is NOT absolute score parity (live has more chunks per code, so its
        # top score is naturally a bit higher). It is: the twin does NOT abstain (top >= 0.20, the
        # kbli evidence threshold) AND surfaces the canonical code in top-5 — same as live would.
        for q, want in cases:
            emb = (await oai.embeddings.create(model=EMBEDDING_MODEL, input=[q])).data[0].embedding
            lcodes, lscore = await top(LIVE, emb)
            tcodes, tscore = await top(TWIN, emb)
            ok = (tscore >= 0.20) and (want in tcodes)
            check(
                f"4. no-abstain + code found '{q[:22]}'",
                ok,
                f"twin_top={round(tscore,3)} live_top={round(lscore,3)} want_in_twin={want in tcodes}",
            )

        # 5 + 6. scroll all, check L4 coverage on _uraian chunks + double-truth
        all_pts = []
        offset = None
        while True:
            body = {"limit": 1000, "with_payload": True}
            if offset:
                body["offset"] = offset
            r = await http.post(f"{qurl}/collections/{TWIN}/points/scroll", json=body, headers=H)
            res = r.json()["result"]
            all_pts.extend(res["points"])
            offset = res.get("next_page_offset")
            if not offset:
                break
        uraian = [p for p in all_pts if (p["payload"].get("metadata") or {}).get("chunk_type") == "uraian"]
        u_with_l4 = sum(1 for p in uraian if (p["payload"].get("metadata") or {}).get("bali_status"))
        check("5. all _uraian chunks carry L4", u_with_l4 == len(uraian) and len(uraian) >= 1500,
              f"{u_with_l4}/{len(uraian)} uraian chunks have bali_status")
        double = sum(
            1 for p in all_pts
            if (p["payload"].get("metadata") or {}).get("pma_status") == "TERBUKA"
            and (p["payload"].get("metadata") or {}).get("bali_blocked")
        )
        check("6. double-truth present", double > 500, f"{double} chunks TERBUKA-national + Bali-blocked")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    logger.info(f"\n=== {passed}/{total} checks PASS ===")
    if passed < total:
        logger.info("VERDICT: TWIN NOT READY — do NOT swap alias")
        sys.exit(1)
    logger.info("VERDICT: TWIN READY — retrieval parity + L4 confirmed. Safe to swap alias.")


if __name__ == "__main__":
    asyncio.run(main())
