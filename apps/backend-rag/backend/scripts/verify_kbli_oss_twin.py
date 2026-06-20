"""
Bombard the twin collection `kbli_2025_final_oss` with verification queries before any
alias swap. Live `kbli_2025_final_hybrid` must stay intact (read-only checks here).

Checks (each prints PASS/FAIL — exit 1 if ANY fail):
1. twin exists, points_count >= 1500
2. LIVE collection still at its baseline count (untouched)
3. exact-fetch known codes (55203 villa, 01111 padi-jagung, 01112) carry correct L4 payload
4. semantic dense search surfaces the right code for natural-language activity queries
5. payload integrity: bali_status present on all, the double-truth holds (national TERBUKA + Bali blocked)
6. distribution sanity: blocked-in-Bali count in expected band

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/verify_kbli_oss_twin.py
"""

import asyncio
import logging
import os
import sys

import httpx

from backend.scripts.reindex_kbli_2025_final import deterministic_uuid

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


async def main() -> None:
    qurl = os.environ["QDRANT_URL"].rstrip("/")
    qkey = os.environ.get("QDRANT_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if qkey:
        headers["api-key"] = qkey

    from openai import AsyncOpenAI

    oai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async with httpx.AsyncClient(timeout=60) as http:
        # 1. twin exists + count
        rt = await http.get(f"{qurl}/collections/{TWIN}", headers=headers)
        tc = rt.json()["result"]["points_count"] if rt.status_code == 200 else 0
        # 1559 = 1563 OSS 5-digit minus 4 removed phantoms
        check("1. twin exists, 1559 points (phantoms removed)", tc == 1559, f"{tc} points")

        # 2. live untouched
        rl = await http.get(f"{qurl}/collections/{LIVE}", headers=headers)
        lc = rl.json()["result"]["points_count"] if rl.status_code == 200 else -1
        check("2. live collection untouched", lc == LIVE_BASELINE, f"{lc} (baseline {LIVE_BASELINE})")

        # 3. exact-fetch known codes carry correct L4
        expect = {
            "55203": ("BLOCCATO_CLASSE_RISCHIO", True),   # villa — blocked in Bali
            "01111": ("TERTUTUP", True),                  # padi/jagung — closed
            "01112": ("OK_or_HIGHER_RISK", False),        # corrected forestry — registrable
            "02103": ("OK_or_HIGHER_RISK", False),        # corrected forestry
        }
        for code, (want_status, want_blocked) in expect.items():
            r = await http.post(
                f"{qurl}/collections/{TWIN}/points",
                json={"ids": [deterministic_uuid(code)], "with_payload": True},
                headers=headers,
            )
            pts = r.json().get("result", []) if r.status_code == 200 else []
            if not pts:
                check(f"3.{code} present + L4", False, "point not found")
                continue
            pl = pts[0]["payload"]
            ok = pl.get("bali_status") == want_status and bool(pl.get("bali_blocked")) == want_blocked
            check(
                f"3.{code} L4 correct",
                ok,
                f"bali_status={pl.get('bali_status')} blocked={pl.get('bali_blocked')} pma={pl.get('pma_status')}",
            )

        # 4. semantic dense search — natural-language activity → expect the right code in top-5
        sem = {"villa rental tourism accommodation Bali": "55203"}
        for query, want_code in sem.items():
            emb = (await oai.embeddings.create(model=EMBEDDING_MODEL, input=[query])).data[0].embedding
            r = await http.post(
                f"{qurl}/collections/{TWIN}/points/query",
                json={"query": emb, "using": "dense", "limit": 5, "with_payload": True},
                headers=headers,
            )
            hits = [h["payload"].get("kode") for h in r.json().get("result", {}).get("points", [])] if r.status_code == 200 else []
            check(f"4. semantic '{query[:30]}' finds {want_code}", want_code in hits, f"top5={hits}")

        # 5 + 6. scroll all, check payload integrity + distribution
        all_pts: list[dict] = []
        offset = None
        while True:
            body = {"limit": 500, "with_payload": True}
            if offset:
                body["offset"] = offset
            r = await http.post(f"{qurl}/collections/{TWIN}/points/scroll", json=body, headers=headers)
            res = r.json()["result"]
            all_pts.extend(res["points"])
            offset = res.get("next_page_offset")
            if not offset:
                break
        with_l4 = sum(1 for p in all_pts if p["payload"].get("bali_status"))
        blocked = sum(1 for p in all_pts if p["payload"].get("bali_blocked"))
        # The 4 phantom codes (in our old file, NOT in OSS ground-truth) have been REMOVED from
        # the twin — so every remaining point must carry bali_status (none should lack it).
        PHANTOMS = {"26120", "60111", "82920", "85598"}
        no_l4 = {p["payload"].get("kode") for p in all_pts if not p["payload"].get("bali_status")}
        phantoms_present = PHANTOMS & {p["payload"].get("kode") for p in all_pts}
        check(
            "5. all remaining points carry L4 (phantoms removed)",
            len(no_l4) == 0 and len(phantoms_present) == 0,
            f"{with_l4}/{len(all_pts)} carry L4; without={sorted(no_l4)}; phantoms_present={sorted(phantoms_present)}",
        )
        # double-truth: at least one code TERBUKA nationally but blocked in Bali
        double = sum(
            1 for p in all_pts
            if p["payload"].get("pma_status") == "TERBUKA" and p["payload"].get("bali_blocked")
        )
        check("5b. double-truth present (TERBUKA national + Bali blocked)", double > 100, f"{double} codes")
        check("6. blocked-in-Bali in band [800,1100]", 800 <= blocked <= 1100, f"{blocked} blocked")

    # summary
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    logger.info(f"\n=== {passed}/{total} checks PASS ===")
    if passed < total:
        logger.info("VERDICT: TWIN NOT READY — do NOT swap alias")
        sys.exit(1)
    logger.info("VERDICT: TWIN READY — safe to swap alias to production")


if __name__ == "__main__":
    asyncio.run(main())
