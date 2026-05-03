"""Fill deterministic summaries for small Louvain communities.

The LLM-based generator (`generate_community_summaries.py`) is rate-limited by
the local Ollama runtime (~12s/call). For the long tail of small communities
(member_count < 10) the deterministic fallback is acceptable: it still gives
downstream consumers a text field instead of NULL, which is what matters for
the GraphRAG summary-aware retrieval path.

This script writes the fallback summary for every community with
summary IS NULL AND member_count < min_members_llm.

Usage:
    PYTHONPATH=. python scripts/fill_small_community_fallbacks.py \
        --min-members-llm 10
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg

def _require_env(name: str) -> str:
    import os as _os
    val = _os.environ.get(name)
    if not val:
        raise SystemExit(f"{name} env var is required (no hardcoded fallback for security)")
    return val




DB_URL = _require_env("ENTITY_LINKER_DB_URL")


_DOMAIN_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("kbli", "klasifikasi", "usaha", "kegiatan"), "classificazione attività economiche (KBLI)"),
    (("kitas", "kitap", "vitas", "visa", "imigrasi", "izin_tinggal"), "permessi di soggiorno e immigrazione"),
    (("pph", "ppn", "pajak", "pbb", "bphtb", "spt", "tax"), "obblighi fiscali e tributari"),
    (("nib", "oss", "siup", "tdp", "izin_usaha", "perizinan"), "licenze e registrazioni d'impresa"),
    (("pt_pma", "pt_pmdn", "perusahaan", "modal"), "struttura societaria e capitale"),
    (("ketenagakerjaan", "karyawan", "pekerja", "rptka", "imta", "bpjs"), "lavoro e protezione sociale"),
    (("uu", "pp", "perpres", "permen", "perda", "pasal", "ayat"), "riferimenti normativi primari e secondari"),
    (("bkpm", "kemenkumham", "kemenaker", "djp", "bpn"), "enti governativi e ministeri"),
    (("sanksi", "pencabutan", "pidana"), "sanzioni e conseguenze amministrative"),
    (("lingkungan", "amdal", "limbah"), "ambiente e valutazione di impatto"),
    (("properti", "tanah", "bangunan", "imb", "hak_guna"), "diritti immobiliari e urbanistica"),
]


def _infer_domain(top_entities: list[str]) -> str:
    joined = " ".join(top_entities).lower() if top_entities else ""
    for keys, label in _DOMAIN_HINTS:
        if any(key in joined for key in keys):
            return label
    return "normative e entità eterogenee"


def _fallback(community_id: str, top_entities: list[str], member_count: int) -> str:
    domain = _infer_domain(top_entities)
    entities = ", ".join(top_entities[:6]) if top_entities else "voci senza etichetta"
    return (
        f"Cluster Louvain di {member_count} entità centrate su {domain}. "
        f"Voci rappresentative: {entities}. "
        f"Riepilogo deterministico (estratto da top_entities) — non generato da LLM."
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-members-llm", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(
            """
            SELECT community_id, member_count, top_entities
            FROM kg_communities
            WHERE (summary IS NULL OR summary = '')
              AND member_count < $1
            """,
            args.min_members_llm,
        )
        print(f"Pending small-community fallbacks: {len(rows)}")
        if args.dry_run or not rows:
            return 0

        batch = [
            (_fallback(r["community_id"], list(r["top_entities"] or []), int(r["member_count"])), r["community_id"])
            for r in rows
        ]
        async with pool.acquire() as conn:
            await conn.executemany(
                "UPDATE kg_communities SET summary = $1, updated_at = NOW() "
                "WHERE community_id = $2 AND (summary IS NULL OR summary = '')",
                batch,
            )
        print(f"Updated {len(batch)} rows with deterministic fallback summaries")
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
