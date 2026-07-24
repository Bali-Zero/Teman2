"""
kbli_documents_phantom_cure.py — neutralise PHANTOM rows in the Postgres
`kbli_documents` table: rows keyed on a code that is NOT in the canonical
KBLI 2025 catalogue we serve, yet still carries a full KBLI-2020 licensing
payload that `chat_kbli` injects VERBATIM into the LLM context.

WHY (2026-07-24 — 4th-surface follow-up). `kbli_documents` was seeded once on
2026-02-18 from an older dataset and has no builder script. Its code set is a
strict SUPERSET of the canonical: 1,563 rows vs 1,559 canonical codes, and the
4 extras are KBLI **2020** codes that the 2025 catalogue renumbered or dropped:

    26120  INDUSTRI PAPAN RANGKAIAN TERINTEGRASI (CHIPS)
    60111  SIARAN RADIO PEMERINTAH
    82920  AKTIVITAS PENGEMASAN
    85598  JASA PENDIDIKAN SWASTA LAINNYA YTDL

The router's direct-code path (`kbli_notebook_chat.py:715`) resolves ANY
5-digit code found in the user's question straight against this table, so a
phantom row wins on an exact-match lookup and the model answers with confident
2020-vintage licensing for a code that no longer exists. Live proof
(2026-07-24, prod, before this cure):
  - 82920 → "Yes, a PT PMA can absolutely run this business", risk tiers per
    scale, Gubernur authority, 7-day processing, ISO 9001 obligation, staffing
    minima. The 2025 catalogue split 82920 into 82921-82929 (+39002); the code
    the client would type into OSS does not exist.
  - 60111 → "TERBUKA (Open to 100% foreign ownership)" plus a full ISR/Kominfo
    permit path and "register your business and obtain your NIB under KBLI
    60111" — for a *government* radio-broadcasting code retired in 2025.

This is the 50113 disease with a different aetiology: not a disputed licensing
payload on a live code, but a licensing payload on a code that isn't in the
catalogue at all. `kbli_documents_cure.py` cannot treat it — that script is
scoped to codes whose CANONICAL record carries a `per_skala_disputed_*` marker,
and a phantom code has no canonical record to carry one. Hence this sibling.

WHAT IT DOES per `--only` code:
  1. Verify the code is genuinely phantom: present in `kbli_documents` AND
     absent from the canonical dataset. A code that IS canonical is REFUSED
     (that is `kbli_documents_cure.py`'s jurisdiction, not this script's).
  2. Derive the 2025 successors PURELY from the canonical crosswalk fields —
     a canonical record's `kbli_2020_source` or `pp28_sources` naming this
     code. Nothing is inferred, nothing is invented (rule #9,
     `.claude/skills/kbli-navigator/SKILL.md` §4). A code with no crosswalk
     entry gets NO successors — the content says so plainly rather than
     guessing one.
  3. Rewrite `content` to a superseded-code notice: what the code was, that it
     is not in the 2025 catalogue we serve, the certified successors (if any),
     and a directive to verify at oss.go.id. Every licensing/risk/authority
     fact from the 2020 payload is REMOVED, not restated.
  4. Rewrite `metadata`: `per_skala` -> [], the pre-cure value preserved under
     `per_skala_superseded_kbli2020`; `pma_status` -> "Verify at OSS" (the
     router's own honest fallback string, so the search card degrades to it
     instead of rendering a stale "TERBUKA"), pre-cure value preserved under
     `pma_status_superseded_kbli2020`; plus `kbli_2025_status`,
     `kbli_2025_successors`, `licensing_status` and a `_data_note`.
  5. Archive the pre-cure row verbatim into `kbli_documents_archive` before
     any UPDATE (shared with `kbli_documents_cure.py`; `ON CONFLICT
     (kode_kbli) DO NOTHING` keeps it a one-shot forensic snapshot).
  6. Idempotent: a re-run whose computed judul/content/metadata already match
     the live row is a declared no-op.

WORDING DISCIPLINE (corner rule F12). This script never asserts that a code was
abolished by regulation, nor that it is "not published". It states only what we
verified: the code is not present in the KBLI 2025 catalogue we serve, whose
provenance is BPS KBLI 2025 + OSS RBA 2025. Absence from our catalogue is our
finding about our data, not a regulatory ruling.

The same-3-digit-group listing is emitted ONLY when the crosswalk yields zero
certified successors, and is fenced as an explicitly NON-certified navigation
aid. It is there because the alternative — telling the model nothing — invites
it to supply successors from its own training data, which is strictly worse.

SCOPE DISCIPLINE: `--only` is MANDATORY for any cure. There is no sweep flag.
`--census` reports the phantom set (canonical-vs-table difference) and writes
nothing, so the scope is always something a human read before it was typed.

USAGE (dry-run is the default; nothing is written without --apply):
    # what is phantom right now?
    PYTHONPATH=. python backend/scripts/kbli_documents_phantom_cure.py --census \\
        --dataset data/source_documents/KBLI_2025_FINAL_CLEAN.json

    # dry-run the cure:
    PYTHONPATH=. python backend/scripts/kbli_documents_phantom_cure.py \\
        --only 26120,60111,82920,85598

    # apply (writes DB) — canonical dataset is NOT in the Fly image, so pin a
    # commit SHA rather than a moving branch:
    fly ssh console -a nuzantara-rag -C \\
        "python backend/scripts/kbli_documents_phantom_cure.py --only 26120,60111,82920,85598 --dataset https://raw.githubusercontent.com/Balizero1987/Teman2/<sha>/data/source_documents/KBLI_2025_FINAL_CLEAN.json --apply"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("kbli_documents_phantom_cure")

RAW_BASE = "https://raw.githubusercontent.com/Balizero1987/Teman2/main"
DATASET_URL = f"{RAW_BASE}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"

CATALOGUE_PROVENANCE = "BPS KBLI 2025 + OSS RBA 2025"
KBLI_2025_STATUS = "ABSENT_FROM_KBLI_2025_CATALOGUE"
LICENSING_STATUS = "NOT_IN_KBLI_2025"
ROUTER_PMA_FALLBACK = "Verify at OSS"  # kbli_notebook_chat.py:734 default
VINTAGE_SUFFIX = " [KBLI 2020 — tidak ada dalam KBLI 2025]"
ARCHIVE_REASON = (
    "kbli_documents_phantom_cure: pre-cure KBLI-2020 phantom-row snapshot (2026-07-24)"
)

# FAIL-CLOSED SHAPE GUARD. This cure neutralises specific metadata keys; a key
# it has never seen might carry licensing facts it would silently leave behind
# (adversarial-review finding, 2026-07-24: "the neutralisation is a
# whitelist-of-two — any other licensing-bearing key survives"). Rather than
# guess which unknown keys are dangerous with a substring heuristic — the
# over-match trap of superscar #3 — the script REFUSES any row whose metadata
# shape it has not been verified against. The set below is the shape actually
# observed on all 4 phantom rows in prod on 2026-07-24, plus the keys this cure
# itself writes (so a re-run is not refused by its own output).
RECOGNISED_METADATA_KEYS = frozenset(
    {
        # observed pre-cure shape
        "judul",
        "kode_kbli_2025",
        "licensing_status",
        "per_skala",
        "pma_status",
        "pp28_sources",
        "sektor_id",
        "status_mapping",
        # written by this cure
        "kode_kbli_2020",
        "per_skala_superseded_kbli2020",
        "pma_status_superseded_kbli2020",
        "kbli_2025_status",
        "kbli_2025_successors",
        "_data_note",
    }
)

# Shared with kbli_documents_cure.py — created lazily (IF NOT EXISTS) so either
# script can be the first to run. UNIQUE(kode_kbli) backs ON CONFLICT DO NOTHING.
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
class Successor:
    code: str
    judul: str
    via: str  # "kbli_2020_source" | "pp28_sources" — which canonical field carried the link
    mapping_note: str = ""  # canonical `mapping_note` verbatim — the link's own provenance


@dataclass
class PhantomCurePlan:
    code: str
    in_canonical: bool
    in_table: bool
    successors: list[Successor] = field(default_factory=list)
    new_judul: str | None = None
    new_content: str | None = None
    new_metadata: dict | None = None
    update_row: bool = False
    skip_reason: str | None = None


def canonical_codes(dataset: list[dict]) -> set[str]:
    return {str(r["kode_kbli_2025"]) for r in dataset}


def phantom_codes(dataset: list[dict], table_codes: list[str]) -> list[str]:
    """Codes present in `kbli_documents` but absent from the canonical
    catalogue. Computed from BOTH live sets — never a hardcoded list, so the
    census tracks the table as it actually is today."""
    canon = canonical_codes(dataset)
    return sorted(c for c in set(table_codes) if c not in canon)


def find_successors(dataset: list[dict], code: str) -> list[Successor]:
    """The 2025 codes whose canonical record declares THIS code as its KBLI
    2020 ancestor. Provenance-bound: reads only `kbli_2020_source` (the
    crosswalk field) and `pp28_sources` (the PP28 lineage field). A code
    named by neither yields an empty list — this function never falls back to
    prefix matching or any other inference.

    Every hit carries its `mapping_note` VERBATIM, and NOTHING is filtered on
    confidence. The crosswalk contains weak auto-matches — 39002 "Aktivitas
    Penyimpanan Karbon" (carbon storage) is linked to 82920 (packaging) with
    "Auto-matched ... score=71%" — and both silent inclusion (a weak link read
    as certified succession) and silent exclusion (a display cap, W97) would
    misinform. Disclosing the note lets the reader weigh the link, which is
    the only honest option available to a script that must not adjudicate
    mapping quality on its own authority.

    An adversarial review (2026-07-24) proposed splitting weak auto-matches
    into a separate fenced sub-list. Declined DELIBERATELY: doing so requires
    classifying confidence by parsing `mapping_note` prose ("[high]",
    "Match: 93%", "score=71%"), i.e. inventing a substring classifier over a
    field whose full range of formats has not been validated across the whole
    corpus — the over-match trap of superscar #3, introduced into the one place
    that is supposed to be pure disclosure. The risk it targets (a model
    flattening the list into "the successors are X, Y, Z") is instead addressed
    in the rendered lead-in, which states the order is by code number and not
    by relevance, and that presence is not a recommendation."""
    out: dict[str, Successor] = {}
    for record in dataset:
        src = record.get("kbli_2020_source")
        # The field is a bare string in practice, but a list (or an int, if a
        # future build drops the zero-padding) must not crash the census.
        ancestors_2020 = [src] if isinstance(src, (str, int)) else list(src or [])
        pp28 = [str(s) for s in (record.get("pp28_sources") or [])]

        via: str | None = None
        if code in [str(a) for a in ancestors_2020]:
            via = "kbli_2020_source"
        elif code in pp28:
            via = "pp28_sources"
        if via is None:
            continue

        succ_code = str(record["kode_kbli_2025"])
        if succ_code not in out or via == "kbli_2020_source":
            # kbli_2020_source is the stronger claim — let it win the label.
            out[succ_code] = Successor(
                code=succ_code,
                judul=(record.get("judul") or "").strip(),
                via=via,
                mapping_note=(record.get("mapping_note") or "").strip(),
            )
    return [out[k] for k in sorted(out)]


def same_group_codes(dataset: list[dict], code: str) -> list[Successor]:
    """Codes sharing this code's first 3 digits in the 2025 catalogue. NOT a
    crosswalk and never presented as one — see the module docstring for why it
    is emitted at all. `via` is deliberately labelled so no caller can mistake
    these for certified successors."""
    prefix = code[:3]
    return [
        Successor(code=str(r["kode_kbli_2025"]), judul=(r.get("judul") or "").strip(), via="same_group_not_certified")
        for r in sorted(dataset, key=lambda r: str(r["kode_kbli_2025"]))
        if str(r["kode_kbli_2025"]).startswith(prefix)
    ]


def build_phantom_content(
    code: str,
    old_judul: str,
    successors: list[Successor],
    group: list[Successor],
) -> str:
    """Pure — deterministic markdown. States facts only; carries no imperative
    addressed to the assistant, so a verbatim-injected row stays a document
    rather than a command channel."""
    title = (old_judul or "").strip() or f"KBLI {code}"
    lines: list[str] = [
        f"# KBLI {code} — {title} (kode KBLI 2020)",
        "",
        "## Status Kode",
        f"Kode **{code}** TIDAK terdapat dalam katalog KBLI 2025 yang kami layani "
        f"(sumber katalog: {CATALOGUE_PROVENANCE}). Kode ini berasal dari KBLI 2020.",
        "",
        "Tidak tersedia data perizinan, kategori risiko, kewenangan, jangka waktu, "
        "maupun status PMA KBLI 2025 untuk kode ini — bukan karena datanya kosong, "
        "melainkan karena kodenya tidak ada dalam katalog 2025. Data KBLI 2020 yang "
        "sebelumnya tersimpan pada baris ini telah dihapus dari konteks dan "
        "diarsipkan, karena tidak dapat dipakai untuk pendaftaran OSS hari ini.",
    ]

    if successors:
        lines += [
            "",
            "## Kode KBLI 2025 yang Tertaut pada Crosswalk Dataset Kami",
            f"Dataset kanonik kami mencatat kode 2025 berikut sebagai tertaut ke kode "
            f"2020 {code}. Daftar ini diurutkan menurut NOMOR KODE, BUKAN menurut "
            "relevansi, dan kehadiran sebuah kode di sini BUKAN rekomendasi. Tautan "
            "berasal dari proses pemetaan dataset dengan tingkat keyakinan yang "
            "BERBEDA-BEDA — sebagian dihasilkan pencocokan otomatis dan bisa jadi "
            "TIDAK relevan dengan kegiatan usaha nyata. Catatan pemetaan setiap kode "
            "disertakan apa adanya; baca catatan itu sebelum memakai kodenya:",
        ]
        for s in successors:
            note = f" — _catatan pemetaan: {s.mapping_note}_" if s.mapping_note else ""
            lines.append(f"- **{s.code}** — {s.judul}{note}")
        lines += [
            "",
            "Perizinan, kategori risiko, dan status PMA harus dibaca dari kode 2025 "
            "yang benar-benar sesuai dengan kegiatan usaha nyata, bukan dari kode "
            f"2020 {code} ini. Kesesuaian kegiatan wajib dipastikan di oss.go.id.",
        ]
    else:
        lines += [
            "",
            "## Kode KBLI 2025 yang Tertaut pada Crosswalk Dataset Kami",
            "Dataset kanonik kami TIDAK mencatat satu pun kode KBLI 2025 sebagai "
            f"tertaut ke kode {code}. Kami tidak menyimpulkan penggantinya.",
        ]
        if group:
            lines += [
                "",
                f"Sebagai bahan pengecekan saja — BUKAN crosswalk resmi dan BUKAN "
                f"pernyataan bahwa salah satunya setara dengan {code} — kelompok "
                f"{code[:3]} dalam katalog KBLI 2025 berisi:",
            ]
            lines += [f"- {s.code} — {s.judul}" for s in group]
            lines += [
                "",
                "Kesetaraan kegiatan usaha harus dipastikan sendiri di oss.go.id atau "
                "bersama konsultan; daftar di atas tidak membuktikan kesetaraan.",
            ]

    lines += [
        "",
        "## Verifikasi",
        "Status terkini setiap kode wajib dipastikan langsung di **oss.go.id**. "
        "Tim Bali Zero dapat membantu memetakan kegiatan usaha Anda ke kode KBLI "
        "2025 yang tepat.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_phantom_metadata(
    code: str,
    old_metadata: dict | None,
    successors: list[Successor],
    qualified_judul: str | None = None,
    dataset_provenance: str | None = None,
) -> dict:
    """Pure — preserves the pre-cure licensing/PMA values under explicit
    `*_superseded_kbli2020` keys (audit trail lives in the row, not only in the
    archive table) while removing them from every key a consumer reads.

    FIRST CURE WINS on the superseded keys. A re-run reads a row whose
    `pma_status` is already the cured sentinel and whose `per_skala` is already
    [] — capturing those would overwrite the genuine 2020 values with the
    cure's own output and silently destroy the audit trail. So a superseded key
    that already exists is never rewritten."""
    old = dict(old_metadata or {})
    new_meta = {
        k: v
        for k, v in old.items()
        if k not in ("per_skala", "pma_status", "kode_kbli_2025")
    }

    # `kode_kbli_2025` on a phantom row is the false claim this cure exists to
    # remove: the seed wrote the 2020 code into a field whose NAME asserts it is
    # a 2025 code. Re-key it honestly instead of carrying the lie forward.
    if "kode_kbli_2025" in old or "kode_kbli_2020" not in old:
        new_meta["kode_kbli_2020"] = code

    old_per_skala = old.get("per_skala")
    if old_per_skala and "per_skala_superseded_kbli2020" not in old:
        new_meta["per_skala_superseded_kbli2020"] = old_per_skala
    old_pma = old.get("pma_status")
    if old_pma and old_pma != ROUTER_PMA_FALLBACK and "pma_status_superseded_kbli2020" not in old:
        new_meta["pma_status_superseded_kbli2020"] = old_pma

    # `metadata.judul` must carry the SAME vintage qualifier as the row's judul
    # (adversarial-review finding, 2026-07-24): a consumer reading the metadata
    # copy instead of the column would otherwise render the bare 2020 title and
    # lose the whole warning.
    if qualified_judul:
        new_meta["judul"] = qualified_judul

    new_meta["per_skala"] = []
    new_meta["pma_status"] = ROUTER_PMA_FALLBACK
    new_meta["kbli_2025_status"] = KBLI_2025_STATUS
    new_meta["kbli_2025_successors"] = [
        {
            "kode_kbli_2025": s.code,
            "judul": s.judul,
            "via": s.via,
            "mapping_note": s.mapping_note,
        }
        for s in successors
    ]
    new_meta["licensing_status"] = LICENSING_STATUS
    new_meta["_data_note"] = (
        f"2026-07-24 phantom-row cure: {code} is a KBLI 2020 code absent from the "
        f"KBLI 2025 catalogue we serve ({CATALOGUE_PROVENANCE}). Its KBLI 2020 "
        "licensing/PMA payload was removed from the chat context (preserved here "
        "under *_superseded_kbli2020 and verbatim in kbli_documents_archive) "
        "because chat_kbli's direct-code lookup was serving it as current 2025 "
        "guidance. Successors, when listed, come from the canonical crosswalk "
        "fields only. This records our catalogue's contents, not a regulatory "
        "determination about the code's status."
        + (f" Catalogue used: {dataset_provenance}." if dataset_provenance else "")
    )
    return new_meta


def plan_phantom_cure(
    code: str,
    dataset: list[dict],
    canon: set[str],
    current_row: dict | None,
    dataset_provenance: str | None = None,
) -> PhantomCurePlan:
    """Pure decision function — no I/O. Guard order matters: the canonical
    membership check runs BEFORE anything is built, so a live code can never
    reach the content builder even if it is somehow also in the table."""
    if code in canon:
        return PhantomCurePlan(
            code=code,
            in_canonical=True,
            in_table=current_row is not None,
            skip_reason="code IS in the canonical KBLI 2025 catalogue — not phantom; "
            "use kbli_documents_cure.py for canonical codes",
        )
    if current_row is None:
        return PhantomCurePlan(
            code=code,
            in_canonical=False,
            in_table=False,
            skip_reason="not in kbli_documents table",
        )

    unknown = sorted(set(current_row.get("metadata") or {}) - RECOGNISED_METADATA_KEYS)
    if unknown:
        return PhantomCurePlan(
            code=code,
            in_canonical=False,
            in_table=True,
            skip_reason=(
                f"unrecognised metadata key(s) {unknown} — refusing to cure a row whose "
                "shape this script has not been verified against; it could be carrying "
                "licensing facts the cure would leave behind"
            ),
        )

    successors = find_successors(dataset, code)
    group = same_group_codes(dataset, code) if not successors else []
    old_judul = current_row.get("judul") or ""

    # Strip a previously-applied qualifier before re-applying it, so a re-run
    # cannot stack suffixes ("X [..] [..]") nor leak the qualifier into the
    # rendered title inside the content body.
    base_judul = old_judul.removesuffix(VINTAGE_SUFFIX).strip()
    new_judul = f"{base_judul}{VINTAGE_SUFFIX}".strip()
    new_content = build_phantom_content(code, base_judul, successors, group)
    new_metadata = build_phantom_metadata(
        code,
        current_row.get("metadata"),
        successors,
        qualified_judul=new_judul,
        dataset_provenance=dataset_provenance,
    )

    update_row = (
        new_content != current_row.get("content")
        or new_metadata != (current_row.get("metadata") or {})
        or new_judul != old_judul
    )

    return PhantomCurePlan(
        code=code,
        in_canonical=False,
        in_table=True,
        successors=successors,
        new_judul=new_judul if update_row else None,
        new_content=new_content if update_row else None,
        new_metadata=new_metadata if update_row else None,
        update_row=update_row,
        skip_reason=None if update_row else "already cured (judul/content/metadata match)",
    )


def archive_params(code: str, current_row: dict) -> tuple:
    """Pure — the exact, byte-unaltered params for the archive INSERT, kept
    standalone so the "archive is byte-exact" invariant is unit-testable
    without a DB connection."""
    return (
        code,
        current_row.get("judul"),
        current_row.get("content"),
        json.dumps(current_row.get("metadata") or {}, ensure_ascii=False),
        current_row.get("created_at"),
        current_row.get("updated_at"),
        ARCHIVE_REASON,
    )


def _looks_like_local_path(source: str) -> bool:
    return not source.startswith(("http://", "https://")) and Path(source).exists()


# The canonical KBLI 2025 catalogue has 1,559 codes. A dataset outside this band
# is not the catalogue this cure was designed against, and must not be used to
# decide what "phantom" means.
EXPECTED_CODE_COUNT_MIN = 1500
EXPECTED_CODE_COUNT_MAX = 1600


def validate_dataset(dataset: list[dict]) -> None:
    """Fail-closed integrity gate on the canonical catalogue.

    The catalogue is the ONLY thing standing between this cure and a live 2025
    code: "phantom" is defined as "absent from the catalogue". A truncated or
    wrong-vintage file that still parses would silently reclassify legitimate
    codes as phantom, and the innocence guard — which trusts the catalogue —
    would wave them through (adversarial-review finding, 2026-07-24). So the
    catalogue is validated before anything is computed from it."""
    n = len(dataset)
    if not (EXPECTED_CODE_COUNT_MIN <= n <= EXPECTED_CODE_COUNT_MAX):
        raise SystemExit(
            f"dataset integrity: {n} records is outside the expected "
            f"[{EXPECTED_CODE_COUNT_MIN}, {EXPECTED_CODE_COUNT_MAX}] band for the KBLI 2025 "
            "catalogue — refusing to derive 'phantom' from a catalogue this may not be"
        )
    missing = [i for i, r in enumerate(dataset) if not r.get("kode_kbli_2025") or not r.get("judul")]
    if missing:
        raise SystemExit(
            f"dataset integrity: {len(missing)} record(s) lack kode_kbli_2025/judul "
            f"(first at index {missing[0]}) — refusing to use a malformed catalogue"
        )
    codes = [str(r["kode_kbli_2025"]) for r in dataset]
    if len(set(codes)) != len(codes):
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        raise SystemExit(
            f"dataset integrity: duplicate kode_kbli_2025 {dupes[:10]} — a duplicated code "
            "makes successor resolution order-dependent; refusing"
        )


async def load_dataset(source: str) -> tuple[list[dict], str]:
    """Returns (records, provenance) where provenance is the source plus a
    sha256 of the exact bytes used, so the audit trail on every cured row
    records WHICH catalogue justified the cure."""
    if _looks_like_local_path(source):
        logger.info("dataset: reading local file %s", source)
        raw = Path(source).read_bytes()
    else:
        logger.info("dataset: fetching %s", source)
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.get(source)
            r.raise_for_status()
            raw = r.content
    digest = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))["data"]
    validate_dataset(data)
    logger.info("dataset: %d codes, sha256=%s", len(data), digest[:16])
    return data, f"{source} (sha256:{digest[:16]})"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--only",
        default=None,
        help="comma-separated 5-digit codes to cure (MANDATORY — there is no sweep flag)",
    )
    ap.add_argument(
        "--census",
        action="store_true",
        help="report the phantom set (kbli_documents codes absent from the canonical "
        "catalogue) and exit; writes nothing",
    )
    ap.add_argument(
        "--dataset",
        default=DATASET_URL,
        help="canonical dataset: local file path (read directly) or URL (httpx fetch). "
        "Default: GitHub raw main. Prefer a pinned commit SHA when applying.",
    )
    args = ap.parse_args()

    if not args.census and not args.only:
        logger.error("--only is MANDATORY (or pass --census to see the phantom set) — "
                     "refusing to guess scope")
        raise SystemExit(2)

    if args.apply and args.dataset == DATASET_URL:
        # `main` is a moving target: the catalogue that defines "phantom" could
        # change between the dry-run an operator read and the apply they then
        # ran. Writes require a catalogue that cannot move under them.
        logger.error(
            "--apply with the unpinned default dataset (%s) is refused — pass --dataset "
            "pinned to a commit SHA or a local file, so the catalogue that justified the "
            "cure is the one recorded in the audit trail",
            DATASET_URL,
        )
        raise SystemExit(2)

    dataset, dataset_provenance = await load_dataset(args.dataset)
    canon = canonical_codes(dataset)
    logger.info("canonical catalogue: %d codes", len(canon))

    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        if args.census:
            table_codes = [r["kode_kbli"] for r in await conn.fetch("SELECT kode_kbli FROM kbli_documents")]
            phantoms = phantom_codes(dataset, table_codes)
            missing = sorted(canon - set(table_codes))
            logger.info("kbli_documents: %d rows", len(table_codes))
            logger.info("PHANTOM (in table, not in canonical): %d", len(phantoms))
            for c in phantoms:
                row = await conn.fetchrow(
                    "SELECT judul, jsonb_array_length(COALESCE(metadata->'per_skala','[]'::jsonb)) AS n "
                    "FROM kbli_documents WHERE kode_kbli = $1",
                    c,
                )
                succ = find_successors(dataset, c)
                logger.info(
                    "  %s  %-50s per_skala=%s  successors=%s",
                    c,
                    (row["judul"] or "")[:50] if row else "?",
                    row["n"] if row else "?",
                    ",".join(s.code for s in succ) or "NONE",
                )
            logger.info("CANONICAL codes missing from table: %d", len(missing))
            if missing:
                logger.info("  %s", ", ".join(missing))
            return

        codes = [c.strip() for c in args.only.split(",") if c.strip()]
        if not codes:
            logger.error("--only produced an empty code list, nothing to do")
            raise SystemExit(2)

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

        plans: list[PhantomCurePlan] = []
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
            plan = plan_phantom_cure(code, dataset, canon, current_row, dataset_provenance)
            plans.append(plan)

            if not plan.update_row:
                logger.info("SKIP %s: %s", code, plan.skip_reason)
                continue

            logger.info(
                "  %s: would update kbli_documents (%d chars) successors=%s",
                code,
                len(plan.new_content or ""),
                ",".join(s.code for s in plan.successors) or "NONE",
            )
            if args.apply:
                assert current_row is not None  # update_row=True implies in_table=True
                # ATOMIC per code (adversarial-review finding, 2026-07-24): the
                # archive INSERT is the ONLY forensic copy of the pre-cure row,
                # and the UPDATE destroys the original. Outside a transaction, a
                # failure between them either loses the evidence (update landed,
                # archive did not) or leaves a half-cured surface. One
                # transaction per code keeps a mid-run abort at a clean
                # code-boundary rather than inside one.
                async with conn.transaction():
                    await conn.execute(
                        "INSERT INTO kbli_documents_archive "
                        "(kode_kbli, judul, content, metadata, original_created_at, "
                        "original_updated_at, archived_reason) "
                        "VALUES ($1, $2, $3, $4::text::jsonb, $5, $6, $7) "
                        "ON CONFLICT (kode_kbli) DO NOTHING",
                        *archive_params(code, current_row),
                    )
                    # W89 jsonb double-encoding class-guard: bind the pre-serialized
                    # json.dumps() string to a $N::text::jsonb placeholder so the
                    # server casts text->jsonb exactly once.
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
