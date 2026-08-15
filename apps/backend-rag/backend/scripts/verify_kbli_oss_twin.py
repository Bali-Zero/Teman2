"""Verify the KBLI OSS twin against the current canonical disclosure contract.

The verifier is read-only.  Every structural expectation is derived from the
same canonical dataset used by ``build_kbli_oss_twin_v3.py``; it deliberately
does not freeze historical point counts or assume every code has a publishable
Bali verdict.  A PMA/Bali claim is public only through ``disclose_pma`` and
``disclose_bali``.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python backend/scripts/verify_kbli_oss_twin.py

To prove the live collection count did not move during a separately observed
build window, pass that pre-build observation explicitly:
    ... verify_kbli_oss_twin.py --live-baseline 4624
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import uuid
from collections import Counter
from collections.abc import Mapping
from typing import Any

import httpx

from backend.scripts.build_kbli_oss_twin_v3 import PHANTOMS, SOURCE_FILE
from backend.services.kbli_pma_disclosure import disclose_bali, disclose_pma

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TWIN = "kbli_2025_final_oss"
LIVE = "kbli_2025_final_hybrid"
EMBEDDING_MODEL = "text-embedding-3-small"

PMA_METADATA_KEYS = (
    "pma_status",
    "pma_max_asing",
    "pma_verification_status",
    "pma_official_basis",
    "pma_source_vintage",
    "pma_cap_special",
    "pma_cap_verified",
)
BALI_METADATA_KEYS = ("bali_status", "bali_blocked", "bali_reason", "has_bali_l4")

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    logger.info("  [%s] %s%s", "PASS" if ok else "FAIL", name, f" — {detail}" if detail else "")


def pv(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    for key in keys:
        if payload.get(key) not in (None, ""):
            return payload[key]
        if metadata.get(key) not in (None, ""):
            return metadata[key]
    return default


def load_canonical_records() -> list[dict[str, Any]]:
    source = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    return [
        record
        for record in source["data"]
        if len(str(record.get("kode_kbli_2025", ""))) == 5
        and record.get("kode_kbli_2025") not in PHANTOMS
    ]


def expected_public_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    pma = disclose_pma(record)
    return {
        **{key: pma[key] for key in PMA_METADATA_KEYS},
        **disclose_bali(record),
    }


def metadata_contract_problems(
    payload: Mapping[str, Any],
    canonical_by_code: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return all public-disclosure mismatches for one Qdrant payload."""
    problems: list[str] = []
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return ["payload.metadata is missing or not an object"]

    code = metadata.get("kode_kbli")
    if not isinstance(code, str) or code not in canonical_by_code:
        return [f"metadata.kode_kbli is not canonical: {code!r}"]
    record = canonical_by_code[code]
    expected = expected_public_metadata(record)

    for key, value in expected.items():
        if key not in metadata:
            problems.append(f"{code}: metadata.{key} is absent")
        elif metadata.get(key) != value:
            problems.append(f"{code}: metadata.{key}={metadata.get(key)!r}, expected {value!r}")

    text = payload.get("text")
    if not isinstance(text, str):
        problems.append(f"{code}: payload.text is missing or not a string")
        return problems

    if expected["pma_verification_status"] != "located":
        raw_status = record.get("pma_status")
        raw_cap = record.get("pma_max_asing")
        if isinstance(raw_status, str) and f"Status PMA: {raw_status}" in text:
            problems.append(f"{code}: text republishes raw gap PMA status {raw_status!r}")
        if raw_cap not in (None, "") and f"(Max {raw_cap}%)" in text:
            problems.append(f"{code}: text republishes raw gap PMA cap {raw_cap!r}")

    bali_heading = "STATUS PMA DI BALI (L4 - moratorium provinsi 2026-05-13):"
    if expected["has_bali_l4"]:
        if bali_heading not in text:
            problems.append(f"{code}: disclosed Bali metadata has no matching text block")
        if f"- Status Bali: {expected['bali_status']}" not in text:
            problems.append(f"{code}: Bali status text does not match metadata")
    elif bali_heading in text:
        problems.append(f"{code}: neutral Bali disclosure still has a Bali text block")

    return problems


def expected_chunk_count(record: Mapping[str, Any]) -> int:
    per_skala = record.get("per_skala")
    return 1 + (len(per_skala) if isinstance(per_skala, list) else 0)


def audit_twin_points(
    points: list[Mapping[str, Any]],
    records: list[Mapping[str, Any]],
) -> tuple[list[str], dict[str, int]]:
    """Audit a complete scroll of the twin without network side effects."""
    canonical = {str(record["kode_kbli_2025"]): record for record in records}
    per_code: Counter[str] = Counter()
    uraian_per_code: Counter[str] = Counter()
    problems: list[str] = []
    actual_located_uraian = 0
    actual_double_truth_chunks = 0

    for point in points:
        payload = point.get("payload")
        if not isinstance(payload, Mapping):
            problems.append(f"point {point.get('id')!r}: payload is missing or not an object")
            continue
        point_problems = metadata_contract_problems(payload, canonical)
        problems.extend(f"point {point.get('id')!r}: {problem}" for problem in point_problems)

        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        code = metadata.get("kode_kbli")
        if not isinstance(code, str):
            continue
        per_code[code] += 1
        if metadata.get("chunk_type") == "uraian":
            uraian_per_code[code] += 1
            if metadata.get("pma_verification_status") == "located":
                actual_located_uraian += 1
        if metadata.get("pma_status") == "TERBUKA" and metadata.get("bali_blocked") is True:
            actual_double_truth_chunks += 1

    for code, record in canonical.items():
        wanted = expected_chunk_count(record)
        if per_code[code] != wanted:
            problems.append(f"{code}: {per_code[code]} chunks, expected {wanted}")
        if uraian_per_code[code] != 1:
            problems.append(f"{code}: {uraian_per_code[code]} uraian chunks, expected exactly 1")
    for extra in sorted(set(per_code) - set(canonical)):
        problems.append(f"{extra}: point exists but code is absent from canonical input")

    expected_located_codes = sum(
        1 for record in records if disclose_pma(record)["pma_verification_status"] == "located"
    )
    expected_double_truth_chunks = sum(
        expected_chunk_count(record)
        for record in records
        if disclose_pma(record)["pma_status"] == "TERBUKA"
        and disclose_bali(record)["bali_blocked"] is True
    )
    if actual_located_uraian != expected_located_codes:
        problems.append(
            "located uraian count differs from canonical: "
            f"{actual_located_uraian} != {expected_located_codes}"
        )
    if actual_double_truth_chunks != expected_double_truth_chunks:
        problems.append(
            "double-truth chunk count differs from canonical: "
            f"{actual_double_truth_chunks} != {expected_double_truth_chunks}"
        )

    return problems, {
        "expected_codes": len(records),
        "expected_chunks": sum(expected_chunk_count(record) for record in records),
        "actual_points": len(points),
        "expected_located_codes": expected_located_codes,
        "actual_located_uraian": actual_located_uraian,
        "expected_double_truth_chunks": expected_double_truth_chunks,
        "actual_double_truth_chunks": actual_double_truth_chunks,
    }


def uraian_id(code: str) -> str:
    digest = hashlib.md5(f"kbli_2025_oss::{code}::uraian".encode()).hexdigest()
    return str(uuid.UUID(digest))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-baseline",
        type=int,
        help="pre-build live point count; enables an exact untouched assertion",
    )
    args = parser.parse_args()

    results.clear()
    records = load_canonical_records()
    canonical = {str(record["kode_kbli_2025"]): record for record in records}
    expected_total = sum(expected_chunk_count(record) for record in records)

    qurl = os.environ["QDRANT_URL"].rstrip("/")
    qkey = os.environ.get("QDRANT_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if qkey:
        headers["api-key"] = qkey

    from openai import AsyncOpenAI

    openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async with httpx.AsyncClient(timeout=60) as http:
        twin_response = await http.get(f"{qurl}/collections/{TWIN}", headers=headers)
        twin_response.raise_for_status()
        twin_count = twin_response.json()["result"]["points_count"]
        check(
            "1. twin chunk count matches canonical",
            twin_count == expected_total,
            f"{twin_count} actual / {expected_total} expected",
        )

        live_response = await http.get(f"{qurl}/collections/{LIVE}", headers=headers)
        live_response.raise_for_status()
        live_count = live_response.json()["result"]["points_count"]
        if args.live_baseline is None:
            check(
                "2. live collection readable",
                live_count > 0,
                f"{live_count} points; untouched not claimed without --live-baseline",
            )
        else:
            check(
                "2. live point count untouched",
                live_count == args.live_baseline,
                f"{live_count} actual / {args.live_baseline} observed baseline",
            )

        async def find_uraian(code: str) -> Mapping[str, Any] | None:
            response = await http.post(
                f"{qurl}/collections/{TWIN}/points",
                json={"ids": [uraian_id(code)], "with_payload": True},
                headers=headers,
            )
            response.raise_for_status()
            points = response.json().get("result", [])
            return points[0].get("payload") if points else None

        for code in ("02102", "01111", "55203", "73100"):
            payload = await find_uraian(code)
            if payload is None:
                check(f"3.{code} representative disclosure", False, "uraian point missing")
                continue
            problems = metadata_contract_problems(payload, canonical)
            check(
                f"3.{code} representative disclosure",
                not problems,
                "; ".join(problems[:3]) if problems else "matches canonical contract",
            )

        async def top(collection: str, embedding: list[float]) -> tuple[list[str], float]:
            response = await http.post(
                f"{qurl}/collections/{collection}/points/query",
                json={
                    "query": embedding,
                    "using": "dense",
                    "limit": 5,
                    "with_payload": True,
                },
                headers=headers,
            )
            response.raise_for_status()
            points = response.json().get("result", {}).get("points", [])
            codes = [
                str(pv(point["payload"], "kode_kbli", "kode", "kode_kbli_2025", default="?"))
                for point in points
            ]
            score = points[0].get("score", 0) if points else 0
            return codes, score

        cases = (
            ("villa rental for tourists in Bali", "55203"),
            ("software development company", "62192"),
            ("restaurant food service in a building", "56101"),
            ("import export trading wholesale", "46799"),
        )
        for query, wanted_code in cases:
            embedding = (
                (await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[query]))
                .data[0]
                .embedding
            )
            live_codes, live_score = await top(LIVE, embedding)
            twin_codes, twin_score = await top(TWIN, embedding)
            ok = twin_score >= 0.20 and wanted_code in twin_codes
            check(
                f"4. no-abstain + code found {query[:22]!r}",
                ok,
                "twin_top="
                f"{twin_score:.3f} live_top={live_score:.3f} "
                f"wanted_in_twin={wanted_code in twin_codes} live_codes={live_codes[:3]}",
            )

        all_points: list[Mapping[str, Any]] = []
        offset: Any = None
        while True:
            body: dict[str, Any] = {
                "limit": 1000,
                "with_payload": True,
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            response = await http.post(
                f"{qurl}/collections/{TWIN}/points/scroll",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()["result"]
            all_points.extend(result["points"])
            offset = result.get("next_page_offset")
            if offset is None:
                break

        problems, metrics = audit_twin_points(all_points, records)
        check(
            "5. every point matches canonical public metadata/text",
            not problems,
            (
                f"{metrics['actual_points']} points / {metrics['expected_codes']} codes; "
                + ("; ".join(problems[:5]) if problems else "zero contract mismatches")
            ),
        )
        check(
            "6. located and double-truth coverage derived from canonical",
            metrics["actual_located_uraian"] == metrics["expected_located_codes"]
            and metrics["actual_double_truth_chunks"] == metrics["expected_double_truth_chunks"],
            f"located={metrics['actual_located_uraian']}/{metrics['expected_located_codes']} "
            f"double_truth={metrics['actual_double_truth_chunks']}/"
            f"{metrics['expected_double_truth_chunks']}",
        )

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    logger.info("\n=== %d/%d checks PASS ===", passed, total)
    if passed < total:
        logger.info("VERDICT: TWIN NOT READY — do NOT swap alias")
        sys.exit(1)
    logger.info("VERDICT: TWIN CONTRACT VERIFIED. Alias swap remains a separate operator action.")


if __name__ == "__main__":
    asyncio.run(main())
