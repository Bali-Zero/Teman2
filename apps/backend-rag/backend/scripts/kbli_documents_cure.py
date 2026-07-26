"""
kbli_documents_cure.py — replace fabricated/stale licensing content in the
Postgres `kbli_documents` table with honest content derived from the
canonical KBLI dataset, for the codes whose canonical record has already
been detached/restored by the GARUDA-FILIERA collision cure (a
`per_skala_disputed_*` key present on the canonical record).

WHY (2026-07-19, PENDING-ARMS follow-up — 4th consumer surface): `kbli_documents`
is a Postgres table with every row seeded 2026-02-18 and NO builder script
anywhere in the repo — a datastore entirely outside the canonical dataset's
cure pathway (Fase 1 collision detach, `kg_kbli_license_fix.py`,
`kbli_qdrant_risk_clear.py`, the gold cure). `chat_kbli`
(`POST /api/v1/kbli-notebook/chat`, `backend/app/routers/kbli_notebook_chat.py`)
injects `kbli_documents.content` VERBATIM into the LLM context — via the
direct 5-digit-code lookup path (`kbli_notebook_chat.py:699`) and via
`_fetch_parent_documents_from_kbli_table()` (`kbli_notebook_chat.py:635`,
used for every result the search/explanation step returns). For a
quarantined code this means the LLM answers with STALE fabricated risk
tiers / license sequences / capital figures / ministry authorities that the
canonical dataset has already disowned. Live proof (2026-07-19): chat_kbli
for 50113 (a collision-detached code — canonical `per_skala == []`)
confidently asserted "Menengah Tinggi" risk, "NIB dan Sertifikat Standar",
NIB→Sertifikat Standar→Izin, KSOP/BKI/STCW authorities, and a "Rp 10 Billion
minimum capital" figure sourced from the REVOKED Permen BKPM 4/2021 (BKPM
5/2025 changed paid-up PMA capital to Rp 2.5bn — see memory
`fact_bkpm_5_2025_paidup_capital_2_5_mld_2026_07_16`) — none of it present
in the current canonical record.

SCOPE: codes whose canonical record carries a `per_skala_disputed_*` key —
computed DYNAMICALLY from the canonical dataset (never a hardcoded list), so
the scope always tracks whichever codes have actually been adjudicated. As
of 2026-07-19 this is 73 codes. 72 of the 73 are honest-gap (canonical
`per_skala == []`); ONE (49213) was RESTORED per-ancestor (canonical
`per_skala` is non-empty, real per-ancestor licensing data) — its cured
content must render that restored data FAITHFULLY, not a gap statement:
"detach > plausible-remap" cuts both ways — a genuinely-restored fact is not
a gap and must not be flattened into one.

WHAT IT DOES per `--only` code (or every quarantined code under
`--all-quarantined`):
  1. Load the canonical record (local file path or URL — same convention as
     `kg_kbli_license_fix.py`'s `--dataset`).
  2. Build the honest replacement `content` (markdown) and `metadata`
     (jsonb) PURELY from canonical fields: `judul`, `uraian`, the `pma_*`
     family, `_data_note`, and EITHER the real `per_skala` (if non-empty —
     the 49213-class restore, rendered as structured bullet rows) OR
     `intel_2026.whatYouNeed` (if `per_skala == []` — the honest-gap class,
     already Codex-gated client-facing prose, used VERBATIM, never
     re-authored). This script NEVER invents a licensing/risk/capital value
     that isn't already present in the canonical record (rule #9 —
     `.claude/skills/kbli-navigator/SKILL.md` §4).
  3. If the computed content/metadata/judul differs from what's currently in
     `kbli_documents` for that code: archive the CURRENT row verbatim into
     `kbli_documents_archive` (created if absent; `INSERT ... ON CONFLICT
     (kode_kbli) DO NOTHING` — a one-shot forensic snapshot of the
     fabricated row, taken once and never overwritten by a later re-run) —
     THEN `UPDATE` the live row.
  4. Idempotent: a re-run whose computed content/metadata/judul already
     match the live row is a declared no-op — no archive insert, no update.

SCOPE DISCIPLINE (mirrors `kg_kbli_license_fix.py`): `--only` is MANDATORY
unless `--all-quarantined` is passed explicitly — this script NEVER sweeps
the full ~1,559-row table; only codes whose canonical record already carries
a `per_skala_disputed_*` marker have a verified honest replacement to write.
A `--only` code without that marker (or missing from the canonical dataset,
or missing from `kbli_documents`) is skipped with a logged reason, never
guessed at.

WHOLE-TABLE REFRESH IS OUT OF SCOPE for this script — the other ~1,486 rows
in `kbli_documents` (never adjudicated) are unmanaged and untouched here; see
the PENDING-ARMS line opened alongside this script.

USAGE (dry-run is the default; nothing is written without --apply):
    # single code, dry-run against a LOCAL cured canonical file:
    PYTHONPATH=. python backend/scripts/kbli_documents_cure.py \\
        --only 50113 --dataset data/source_documents/KBLI_2025_FINAL_CLEAN.json

    # multiple codes:
    PYTHONPATH=. python backend/scripts/kbli_documents_cure.py \\
        --only 50113,68112,49213 --apply

    # every quarantined code (73 as of 2026-07-19), dry-run against prod
    # GitHub raw main:
    PYTHONPATH=. python backend/scripts/kbli_documents_cure.py --all-quarantined

    # apply (writes DB):
    fly ssh console -a nuzantara-rag -C \\
        "python backend/scripts/kbli_documents_cure.py --all-quarantined --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_documents_cure")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

GAP_FALLBACK_TEXT = (
    "Regime perizinan untuk kode ini belum dapat diverifikasi dari sumber resmi yang "
    "kami miliki saat ini. Mohon konfirmasi persyaratan terkini dengan tim Bali Zero."
)

# One-shot forensic archive of the pre-cure fabricated row — created lazily
# (IF NOT EXISTS) by this script itself, no formal migration needed for an
# admin-only audit sidecar. UNIQUE(kode_kbli) backs the ON CONFLICT DO
# NOTHING one-shot-capture semantics in main().
ARCHIVE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS kbli_documents_archive (
    id SERIAL PRIMARY KEY,
    kode_kbli VARCHAR NOT NULL UNIQUE,
    judul TEXT,
    content TEXT,
    metadata JSONB,
    original_created_at TIMESTAMP,
    original_updated_at TIMESTAMP,
    archived_at TIMESTAMP NOT NULL DEFAULT now(),
    archived_reason TEXT NOT NULL DEFAULT
        'kbli_documents_cure: pre-cure fabricated-content snapshot (2026-07-19)'
)
"""


@dataclass
class DocumentCurePlan:
    code: str
    found_in_canonical: bool
    found_in_table: bool
    is_gap: bool | None  # per_skala == [] -> True (honest-gap); non-empty -> False (restored); None if canonical/table missing
    new_judul: str | None
    new_content: str | None
    new_metadata: dict | None
    update_row: bool
    skip_reason: str | None


def quarantined_codes(dataset: list[dict]) -> list[str]:
    """Codes whose canonical record carries ANY `per_skala_disputed_*` key —
    the GARUDA-FILIERA collision-cure marker. Computed dynamically so this
    script's scope always matches whichever codes have actually been
    adjudicated (never a hardcoded snapshot that can drift stale)."""
    return sorted(
        str(r["kode_kbli_2025"])
        for r in dataset
        if any(k.startswith("per_skala_disputed_") for k in r)
    )


def _join(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "N/A"
    return str(value) if value else "N/A"


def _render_per_skala_entry(entry: dict) -> str:
    skala_txt = _join(entry.get("skala_usaha"))
    risiko = entry.get("kategori_risiko") or "N/A"
    perizinan_txt = _join(entry.get("perizinan"))
    kewenangan_txt = _join(entry.get("kewenangan"))
    jangka = entry.get("jangka_waktu") or "N/A"
    scope = entry.get("scope_uraian")
    scope_txt = f" ({scope})" if scope else ""
    return (
        f"- **[{skala_txt}]{scope_txt}** — Risiko: {risiko} | "
        f"Perizinan: {perizinan_txt} | Kewenangan: {kewenangan_txt} | "
        f"Jangka Waktu: {jangka}"
    )


def build_perizinan_section(record: dict) -> str:
    """The licensing section — the ONLY place licensing/risk facts can enter
    the cured content. Two branches, both provenance-bound:
      - per_skala non-empty (a restored code, e.g. 49213): render the REAL
        canonical per_skala rows as structured bullets — nothing invented.
      - per_skala == [] (the honest-gap class, 72 of the 73): use
        `intel_2026.whatYouNeed` VERBATIM — that text is already
        Codex-gated client-facing honest-gap prose (kbli-navigator corner
        §1/§4 rule 8/9); this function never re-authors it, never
        synthesizes a bullet row for a gap code."""
    per_skala = record.get("per_skala") or []
    if per_skala:
        return "\n".join(_render_per_skala_entry(e) for e in per_skala)
    what_you_need = ((record.get("intel_2026") or {}).get("whatYouNeed") or "").strip()
    return what_you_need or GAP_FALLBACK_TEXT


def build_cured_content(code: str, record: dict) -> str:
    """Pure — deterministic markdown built ONLY from canonical fields.
    Keeps the healthy factual-identity part (title/what-it-means from
    `uraian`) and routes every licensing/risk/capital fact through
    `build_perizinan_section` (the sole provenance-bound entry point)."""
    judul = (record.get("judul") or "").strip() or f"KBLI {code}"
    uraian = (record.get("uraian") or "").strip() or "(deskripsi belum tersedia)"
    pma_status = record.get("pma_status") or "Verify at OSS"
    pma_max_asing = record.get("pma_max_asing")
    pma_kondisi = record.get("pma_kondisi")
    pma_nota = record.get("pma_nota")
    data_note = (record.get("_data_note") or "").strip()

    lines: list[str] = [
        f"# KBLI {code} — {judul}",
        "",
        "## Deskripsi Kegiatan Usaha",
        uraian,
        "",
        "## Investasi Asing (PMA)",
        f"- Status PMA: {pma_status}",
    ]
    if pma_max_asing is not None:
        lines.append(f"- Maksimum Kepemilikan Asing: {pma_max_asing}%")
    if pma_kondisi:
        lines.append(f"- Kondisi: {pma_kondisi}")
    if pma_nota:
        lines.append(f"- Catatan PMA: {pma_nota}")
    lines += ["", "## Perizinan", build_perizinan_section(record)]
    if data_note:
        lines += ["", "## Catatan Verifikasi", data_note]
    return "\n".join(lines).strip() + "\n"


def build_cured_metadata(code: str, record: dict, old_metadata: dict | None) -> dict:
    """Pure — rebuilds the `metadata` jsonb column from canonical fields,
    same key shape as the original 2026-02-18 seed (defensive: no confirmed
    consumer reads beyond `pma_status`, but the shape is kept stable in case
    one exists). `per_skala` is replaced wholesale with the CURRENT
    canonical value (== [] for the 72 gap codes, the real restored rows for
    49213) — never left holding the fabricated pre-cure block. `_data_note`
    is added for audit-trail parity with the KG cure's own convention
    (`kg_kbli_license_fix.py`). `licensing_status`: honest-gap codes get the
    same `PENDING_REGULATION` marker the KG cure writes (class-parity, so a
    future reader of either datastore sees the same verdict); a
    non-gap/restored code's existing value is left untouched — this script
    makes no independent claim about it."""
    old = dict(old_metadata or {})
    per_skala = record.get("per_skala") or []
    new_meta: dict = {
        "judul": record.get("judul"),
        "per_skala": per_skala,
        "sektor_id": record.get("sektor_id"),
        "pma_status": record.get("pma_status"),
        "pp28_sources": record.get("pp28_sources"),
        "kode_kbli_2025": code,
        "status_mapping": record.get("status_mapping"),
        "licensing_status": "PENDING_REGULATION" if per_skala == [] else old.get("licensing_status", "N/A"),
    }
    data_note = record.get("_data_note")
    if data_note:
        new_meta["_data_note"] = data_note
    return new_meta


def plan_cure(code: str, record: dict | None, current_row: dict | None) -> DocumentCurePlan:
    """Pure decision function — no I/O. `current_row` is
    {"judul": str, "content": str, "metadata": dict} from `kbli_documents`
    (or None if the code isn't in the table at all)."""
    if record is None:
        return DocumentCurePlan(
            code=code,
            found_in_canonical=False,
            found_in_table=current_row is not None,
            is_gap=None,
            new_judul=None,
            new_content=None,
            new_metadata=None,
            update_row=False,
            skip_reason="not in canonical dataset",
        )
    if current_row is None:
        return DocumentCurePlan(
            code=code,
            found_in_canonical=True,
            found_in_table=False,
            is_gap=None,
            new_judul=None,
            new_content=None,
            new_metadata=None,
            update_row=False,
            skip_reason="not in kbli_documents table",
        )

    per_skala = record.get("per_skala")
    is_gap = per_skala == []
    new_content = build_cured_content(code, record)
    new_metadata = build_cured_metadata(code, record, current_row.get("metadata"))
    new_judul = (record.get("judul") or "").strip() or current_row.get("judul")

    old_content = current_row.get("content")
    old_metadata = current_row.get("metadata") or {}
    old_judul = current_row.get("judul")

    update_row = (new_content != old_content) or (new_metadata != old_metadata) or (new_judul != old_judul)

    return DocumentCurePlan(
        code=code,
        found_in_canonical=True,
        found_in_table=True,
        is_gap=is_gap,
        new_judul=new_judul if update_row else None,
        new_content=new_content if update_row else None,
        new_metadata=new_metadata if update_row else None,
        update_row=update_row,
        skip_reason=None if update_row else "already cured (content/metadata/judul match canonical)",
    )


def archive_params(code: str, current_row: dict) -> tuple:
    """Pure — the exact, byte-unaltered params for the archive INSERT.
    Kept as a standalone function so the "archive is byte-exact" invariant
    is unit-testable without a DB connection."""
    return (
        code,
        current_row.get("judul"),
        current_row.get("content"),
        json.dumps(current_row.get("metadata") or {}, ensure_ascii=False),
        current_row.get("created_at"),
        current_row.get("updated_at"),
    )


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


async def load_dataset(source: str) -> list[dict]:
    if _looks_like_local_path(source):
        logger.info("dataset: reading local file %s", source)
        text = Path(source).read_text(encoding="utf-8")
        return json.loads(text)["data"]
    logger.info("dataset: fetching %s", source)
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(source)
        r.raise_for_status()
        return r.json()["data"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--only",
        default=None,
        help="comma-separated list of 5-digit codes to process (mandatory unless --all-quarantined)",
    )
    ap.add_argument(
        "--all-quarantined",
        action="store_true",
        help="process every code with a per_skala_disputed_* marker in the canonical dataset "
        "(73 as of 2026-07-19) — the ONLY sanctioned full-set sweep; never a bare table scan",
    )
    ap.add_argument(
        "--dataset",
        default=DATASET_URL,
        help="canonical dataset: local file path (read directly) or URL (httpx fetch). "
        "Default: GitHub raw main.",
    )
    args = ap.parse_args()

    dataset = await load_dataset(args.dataset)

    if args.all_quarantined:
        codes = quarantined_codes(dataset)
        if args.only:
            logger.warning("--only ignored: --all-quarantined takes precedence")
    else:
        if not args.only:
            logger.error(
                "--only is MANDATORY unless --all-quarantined is passed — refusing to guess scope"
            )
            return
        codes = [c.strip() for c in args.only.split(",") if c.strip()]
    if not codes:
        logger.error("empty code list, nothing to do")
        return

    by_code = {str(r.get("kode_kbli_2025")): r for r in dataset}

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        if args.apply:
            await conn.execute(ARCHIVE_TABLE_DDL)

        table_rows = {
            r["kode_kbli"]: r
            for r in await conn.fetch(
                "SELECT kode_kbli, judul, content, metadata, created_at, updated_at "
                "FROM kbli_documents WHERE kode_kbli = ANY($1)",
                codes,
            )
        }

        plans: list[DocumentCurePlan] = []
        for code in codes:
            row = table_rows.get(code)
            current_row: dict | None = None
            if row is not None:
                metadata = (
                    json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                )
                current_row = {
                    "judul": row["judul"],
                    "content": row["content"],
                    "metadata": metadata or {},
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            plan = plan_cure(code, by_code.get(code), current_row)
            plans.append(plan)

            if not plan.update_row:
                logger.info("SKIP %s: %s", code, plan.skip_reason)
                continue

            logger.info(
                "  %s: would update kbli_documents (%d chars)%s",
                code,
                len(plan.new_content or ""),
                " [GAP]" if plan.is_gap else " [RESTORED]",
            )
            if args.apply:
                assert current_row is not None  # update_row=True implies found_in_table=True
                params = archive_params(code, current_row)
                await conn.execute(
                    "INSERT INTO kbli_documents_archive "
                    "(kode_kbli, judul, content, metadata, original_created_at, original_updated_at) "
                    "VALUES ($1, $2, $3, $4::text::jsonb, $5, $6) "
                    "ON CONFLICT (kode_kbli) DO NOTHING",
                    *params,
                )
                # W89 jsonb double-encoding class-guard (kg_kbli_license_fix.py
                # precedent): bind the pre-serialized json.dumps() string to a
                # $N::text::jsonb placeholder so the server casts text->jsonb
                # exactly once.
                await conn.execute(
                    "UPDATE kbli_documents SET judul = $2, content = $3, "
                    "metadata = $4::text::jsonb, updated_at = now() WHERE kode_kbli = $1",
                    code,
                    plan.new_judul,
                    plan.new_content,
                    json.dumps(plan.new_metadata, ensure_ascii=False),
                )
    finally:
        await conn.close()

    mode = "APPLIED" if args.apply else "DRY-RUN"
    acted = [p for p in plans if p.update_row]
    skipped = [p for p in plans if not p.update_row]
    logger.info("%s: %d code(s) cured | %d skipped", mode, len(acted), len(skipped))
    for p in skipped:
        logger.info("  skipped %s: %s", p.code, p.skip_reason)
    if not args.apply and acted:
        logger.info("dry-run complete — rerun with --apply to write")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
