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
the full ~1,559-row table.

`--only` DOES NOT GET THE CONTENT-PRESERVATION GATE. That gate is scoped to
`--all-licensing-absent`, so passing the same population as a hand-written
`--only` list cures every code the gate would have REFUSED — on 2026-08-02
that was 25 of 80 rows of hand-written client-facing prose. `--only` is also
the only selector that runs inside the deployed image, which is what makes the
substitution tempting. It is not blocked (the Perpres-cap lane legitimately
replaces prose) but it is now REPORTED: a run logs which rows it is about to
overwrite. Read that line before `--apply`.

WHAT `--only` ACTUALLY GATES ON (corrected 2026-08-01 — this paragraph used
to claim the opposite, and a session relied on the path it denied). The
`per_skala_disputed_*` marker selects the `--all-quarantined` population and
NOTHING else: `main()` hands an `--only` list straight to `plan_cure`, which
skips a code only when it is missing from the canonical dataset or missing
from `kbli_documents`. An `--only` code without the marker IS cured. The
previous text asserted it would be "skipped with a logged reason, never
guessed at" — false in code, and dangerous in the direction that matters,
because it reads as a safety gate that does not exist.

That is deliberate and it is also load-bearing, so the real guarantee has to
be stated in place of the imaginary one: nothing here is ever guessed —
`build_cured_content`/`build_cured_metadata` are pure functions of the
canonical record, so the honesty of a cure equals the honesty of that record,
marker or no marker. The marker was only ever a proxy for "someone
adjudicated this code". When curing an unmarked code, establish the
equivalent DIRECTLY and say so: the caller is asserting that the canonical
record is sourced. `scripts/kbli_filiera/_coverage_basis.py` makes that
checkable — `classify_licensing(record) == "sourced_oss_2025"` and
`classify_pma(record) == "located"` mean the record names a per-code
government locator. A canonical record carrying `pma_cap_verified: False`
and no `pma_official_basis` does NOT, and curing it merely propagates an
unsourced verdict to a second surface (2026-08-01: `02101` and `03120` were
held back for exactly this reason, while six sibling divergences were cured).

SIZE IS PART OF SCOPE on this table, unlike the others: `chat_kbli` injects
`content` VERBATIM into the LLM context, so a code with a large `per_skala`
renders a document that competes for that context. Measured on the live table
2026-08-01: median 2,458 chars, p99 13,272, max 25,483. `03110` (69 canonical
rows) computes to 48,008 — ~2x the largest row that has ever existed there —
and was held back pending a channel-appropriate rendering. Read the dry-run's
char count before `--apply`; it is not decoration.

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
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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

# --- state-based scope (2026-08-02) -----------------------------------------
# The conformance detector is the SINGLE implementation of "does this code's
# licensing presence agree between canonical and the channel table". This
# script does not re-derive that predicate: it asks the detector and consumes
# its verdict. Two tools that must agree on the same fact do not get to invent
# two answers (W105) — and the detector is the one with the corpus that pins it.
CONFORMANCE_MARKER = Path("scripts") / "kbli_filiera" / "kbli_surface_conformance.py"


def find_conformance_script(start: Path | None = None) -> Path | None:
    """Locate the detector by WALKING UP for its marker, never by a fixed index.

    This file lives at two different depths: `apps/backend-rag/backend/scripts/`
    in the repo (4 levels under the root) and `/app/backend/scripts/` in the
    deployed image (2). A hardcoded `parents[4]` is therefore an IndexError in
    production — raised at MODULE level, so the script could not even be
    imported there, which killed `--only` too: the one path that can run inside
    the container, and the path the 2026-08-01 prod cure actually used.

    Returns None when no repo layout is found. That is the EXPECTED state inside
    the image, which ships neither `scripts/kbli_filiera/` nor `pg.sh`, and it
    must read as "no selector available here" — never as a crash, and never as
    an empty scope (W84: absence of a reading is not a clean bill).
    """
    here = (start or Path(__file__)).resolve()
    for ancestor in here.parents:
        candidate = ancestor / CONFORMANCE_MARKER
        if candidate.is_file():
            return candidate
    return None


CONFORMANCE_SCRIPT = find_conformance_script()

# A refusal must be legible to a CALLER, not only to a human reading stderr.
# The detector below is scrupulous about this ("judged by EXIT CODE, never by
# did it print something") and this script used to drop that discipline on the
# floor for its own caller: the refusal branch did a bare `return`, so
# `sys.exit(main())` exited 0 and "I refused to cure anything" was
# indistinguishable from "I cured everything" (the W104 shape).
# 3, not 2: argparse spends exit 2 on a usage error, and the caller this
# exists for — automation — would then read 'you passed bad flags' and
# 'I refused to cure anything' as the same event. 0/1/4 belong to the
# detector's own vocabulary and are left alone.
EXIT_REFUSED = 3
# Mirrors kbli_surface_conformance.py's own exit vocabulary. 4 is CANNOT-VERIFY
# and it is NOT a clean bill: a detector that could not read the table reports
# zero divergences, which is indistinguishable from a healthy fleet unless the
# code refuses on it (W84 — absence of a reading is not alignment).
CONFORMANCE_EXIT_OK = 0
CONFORMANCE_EXIT_DIVERGENCE = 1
CONFORMANCE_EXIT_CANNOT_VERIFY = 4

# The 2026-02-18 seed produced TWO different document shapes, and only one of
# them is safe to replace wholesale. The machine shape is derived from the same
# canonical fields this script rebuilds from, so replacing it loses nothing. The
# other shape carries HAND-WRITTEN client-facing prose (code disambiguation,
# local-market guidance) that canonical cannot regenerate.
#
# Recognition is POSITIVE and whole-document, never a keyword search for the
# prose: a search for known editorial headings judges the FORM, so prose under
# any other heading would be silently classified disposable and destroyed
# (superscar #3 — the guard that matches a string instead of an entity). Here
# the default is REFUSE, and only a document whose every section belongs to the
# machine template earns a rebuild. Measured 2026-08-02: all 50 machine-shaped
# rows in the live divergent set carry exactly these three sections and nothing
# else, so a row with a hand-added section is refused rather than overwritten.
MACHINE_TEMPLATE_SECTIONS = frozenset(
    {"Informasi Umum", "Deskripsi Kegiatan Usaha", "Investasi Asing (PMA)"}
)
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)

# A row whose prose asserts that no licensing data exists, on a code where
# canonical now HOLDS government rows. Preserving that sentence keeps a
# government-contradicted instruction in front of a client ("licensing is
# currently minimal — get your NIB early") on an activity that in fact carries
# a risk tier, which can drive a wrong filing decision. That harm outranks the
# loss of market prose, so these rows are rebuilt even though they are
# hand-written; the archive keeps the prose for a later editorial re-authoring.
#
# DECLARED LIMIT, deliberately not dressed up: this is a literal-phrase probe.
# It finds the phrasings the 2026-02-18 seed actually used — it does NOT decide
# in general whether prose contradicts data, which is a semantic judgment this
# script cannot make. A row contradicting canonical in words not listed here is
# NOT caught, and stays in the refused bucket.
CONTRADICTED_LICENSING_CLAIM_RE = re.compile(
    r"no PP28 data|licensing is currently minimal|no licensing data(?: yet)?"
    r"|belum ada data (?:PP28|perizinan)",
    re.I,
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


def licensing_absent_codes(report: dict) -> list[str]:
    """Pure. From a conformance report, the codes where **canonical HOLDS
    verified licensing rows and the channel table serves NONE**.

    ONE DIRECTION, deliberately. `licensing_divergent` is symmetric — it also
    contains the mirror case (the table still holds rows that canonical has
    since detached), which is the QUARANTINE class and belongs to
    `--all-quarantined`. Curing that case from here would rewrite a real
    row-set into a gap statement, i.e. destroy data while reporting a cure.
    The asymmetry is the whole point of this selector, so it is asserted here
    rather than left to the caller."""
    return sorted(
        str(d["code"])
        for d in report.get("licensing_divergent", [])
        if int(d.get("table_rows", 0)) == 0 and int(d.get("canonical_rows", 0)) > 0
    )


def is_machine_template(code: str, content: str | None) -> bool:
    """Pure. True only if the WHOLE document is the 2026-02-18 machine seed:
    the `# KBLI <code> - ` heading AND every `##` section drawn from
    MACHINE_TEMPLATE_SECTIONS. Checking only the head would pass a row that
    starts machine-shaped and has hand-written material appended lower down —
    the exact content this predicate exists to protect."""
    text = content or ""
    if not re.match(rf"^#\s*KBLI\s+{re.escape(str(code))}\s*[-–—]", text):
        return False
    sections = {m.strip() for m in _SECTION_RE.findall(text)}
    return bool(sections) and sections <= MACHINE_TEMPLATE_SECTIONS


def rebuild_reason(code: str, content: str | None, canonical_rows: int) -> str | None:
    """Pure. Why this row may be rebuilt wholesale — or None to refuse it.

    Two admissible reasons, and no third:
      - `machine-template`: nothing is lost, the text is derived from the same
        canonical fields the rebuild reads.
      - `contradicted-licensing-claim`: the prose tells a client there is no
        licensing regime while canonical holds government rows. Rebuilding
        costs hand-written prose (recoverable from the archive); NOT rebuilding
        keeps a false regulatory instruction live. The second harm is larger,
        so this case is rebuilt on purpose rather than parked in the safer-
        looking bucket.
    Anything else is REFUSED — the default is to keep human text."""
    if is_machine_template(code, content):
        return "machine-template"
    if canonical_rows > 0 and CONTRADICTED_LICENSING_CLAIM_RE.search(content or ""):
        return "contradicted-licensing-claim"
    return None


SNAPSHOT_MAX_AGE_MINUTES = 60


def _check_snapshot_freshness(captured_at: str | None) -> None:
    """A supplied snapshot is a MEASUREMENT OF THE WORLD, and a measurement
    frozen into a file goes stale silently (W106). The caller must say when it
    was taken; a value older than an hour is refused rather than trusted.

    Deliberately an assertion by the caller rather than the file's mtime: `scp`
    without `-p` restamps mtime, so an mtime check would read every shipped
    snapshot as fresh — a guard that cannot fail is worse than none."""
    if captured_at is None:
        raise RuntimeError(
            "--conformance-table-json requires --snapshot-captured-at <ISO8601>: a snapshot "
            "with no stated capture time cannot be distinguished from one taken last week"
        )
    try:
        taken = datetime.fromisoformat(captured_at)
    except ValueError as exc:
        raise RuntimeError(f"--snapshot-captured-at is not ISO8601: {captured_at!r} ({exc})") from exc
    if taken.tzinfo is None:
        taken = taken.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - taken).total_seconds() / 60
    if age > SNAPSHOT_MAX_AGE_MINUTES:
        raise RuntimeError(
            f"snapshot was captured {age:.0f} minutes ago (limit {SNAPSHOT_MAX_AGE_MINUTES}) — "
            "re-capture it. Curing against a stale reading of the table is how a cure writes "
            "over rows it never actually looked at."
        )
    if age < -5:
        raise RuntimeError(
            f"--snapshot-captured-at is {-age:.0f} minutes in the FUTURE — refusing rather than "
            "accepting a timestamp that cannot be true"
        )


def fetch_conformance_report(
    script: Path | None,
    table_json: Path | None = None,
    snapshot_captured_at: str | None = None,
) -> dict:
    """I/O. Runs the detector and returns its JSON report.

    Judged by EXIT CODE, never by "did it print something": exit 4 means the
    detector could not read one of the two sides, and its report then carries
    zero divergences — the exact shape of a healthy fleet. Consuming that as
    "nothing to cure" is how a cure silently becomes a no-op (W84). Anything
    outside {0, 1, 4} is also a refusal: an unknown exit is not a verdict.

    WHY `table_json` EXISTS. Reading the live table needs a Keychain password,
    and reading THAT needs an interactive session: over ssh the same lookup
    returns `errSecInteractionNotAllowed` (rc 36) — the entry is present and
    simply unreadable, which is not the same as absent. The write DSN lives on
    a different machine than the readable Keychain, so no single non-interactive
    run holds both halves. This lets the snapshot be captured where the table
    can be read and carried to where the write can happen.

    What it does NOT do: hand the cure a verdict. The detector still derives the
    divergence itself from canonical plus the snapshot, and still owns the
    predicate — passing a hand-written REPORT would let anything drive a write."""
    if table_json is not None:
        _check_snapshot_freshness(snapshot_captured_at)
        if not table_json.is_file():
            raise RuntimeError(f"--conformance-table-json not found at {table_json}")
    if script is None:
        raise RuntimeError(
            "conformance detector not found by walking up from this file — no repo layout "
            "here. That is the expected state inside the deployed image, which ships neither "
            "scripts/kbli_filiera/ nor pg.sh: --all-licensing-absent is a repo-side selector. "
            "Run it where the repo is, or pass --only <codes> (which needs no detector)"
        )
    if not script.is_file():
        raise RuntimeError(
            f"conformance detector not found at {script} — refusing to guess scope from a "
            "predicate this script does not own"
        )
    cmd = [sys.executable, str(script), "--json"]
    if table_json is not None:
        cmd += ["--table-json", str(table_json)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == CONFORMANCE_EXIT_CANNOT_VERIFY:
        raise RuntimeError(
            "conformance detector returned CANNOT-VERIFY (exit 4) — it could not read canonical "
            f"or the table, so an empty divergence list proves nothing: {proc.stdout.strip()[:300]}"
        )
    if proc.returncode not in (CONFORMANCE_EXIT_OK, CONFORMANCE_EXIT_DIVERGENCE):
        raise RuntimeError(
            f"conformance detector exited {proc.returncode} (expected 0/1/4): "
            f"{(proc.stderr or proc.stdout).strip()[:300]}"
        )
    body = proc.stdout.strip()
    if not body:
        raise RuntimeError("conformance detector exited cleanly but printed nothing")
    return json.loads(body)


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


async def main() -> int | None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--only",
        default=None,
        help="comma-separated list of 5-digit codes to process "
        "(mandatory unless --all-quarantined or --all-licensing-absent)",
    )
    ap.add_argument(
        "--all-quarantined",
        action="store_true",
        help="process every code with a per_skala_disputed_* marker in the canonical dataset "
        "(73 as of 2026-07-19) — a MARKER-selected sweep; never a bare table scan",
    )
    ap.add_argument(
        "--all-licensing-absent",
        action="store_true",
        help="process every code the conformance detector reports as: canonical holds verified "
        "licensing rows while the channel table serves NONE (80 codes / 687 rows as of "
        "2026-08-02). STATE-selected, not marker-selected — this is the scope that reaches the "
        "1,423 rows no --only list ever named. Refuses if the detector cannot verify.",
    )
    ap.add_argument(
        "--conformance-script",
        type=Path,
        default=CONFORMANCE_SCRIPT,
        help="path to kbli_surface_conformance.py (the sole owner of the divergence predicate)",
    )
    ap.add_argument(
        "--conformance-table-json",
        type=Path,
        default=None,
        help=(
            "table snapshot for the detector to read INSTEAD of querying the DB, for when the "
            "readable Keychain and the write DSN are on different machines. The detector still "
            "derives the verdict itself. Requires --snapshot-captured-at"
        ),
    )
    ap.add_argument(
        "--snapshot-captured-at",
        default=None,
        metavar="ISO8601",
        help=(
            f"when --conformance-table-json was captured; refused if older than "
            f"{SNAPSHOT_MAX_AGE_MINUTES} minutes"
        ),
    )
    ap.add_argument(
        "--dataset",
        default=DATASET_URL,
        help="canonical dataset: local file path (read directly) or URL (httpx fetch). "
        "Default: GitHub raw main.",
    )
    args = ap.parse_args()

    dataset = await load_dataset(args.dataset)

    canonical_rows_by_code: dict[str, int] = {}
    if args.all_quarantined and args.all_licensing_absent:
        logger.error(
            "--all-quarantined and --all-licensing-absent are two DIFFERENT populations selected "
            "two different ways (marker vs state) — refusing to union them, because the run "
            "report could no longer say which scope acted. Run them separately."
        )
        return

    if args.all_quarantined:
        codes = quarantined_codes(dataset)
        if args.only:
            logger.warning("--only ignored: --all-quarantined takes precedence")
    elif args.all_licensing_absent:
        try:
            report = fetch_conformance_report(
                args.conformance_script,
                table_json=args.conformance_table_json,
                snapshot_captured_at=args.snapshot_captured_at,
            )
        except (RuntimeError, OSError, json.JSONDecodeError) as exc:
            logger.error("refusing to cure: %s", exc)
            return EXIT_REFUSED
        codes = licensing_absent_codes(report)
        canonical_rows_by_code = {
            str(d["code"]): int(d.get("canonical_rows", 0))
            for d in report.get("licensing_divergent", [])
        }
        # Declare N of M — a scope printed without its denominator reads as
        # "covered everything" (W97). The denominator here is every divergence
        # the detector saw, including the mirror direction this selector skips.
        logger.info(
            "state-selected scope: %d code(s) with canonical rows and an empty channel row-set, "
            "out of %d licensing divergence(s) the detector reported",
            len(codes),
            len(report.get("licensing_divergent", [])),
        )
        if args.only:
            logger.warning("--only ignored: --all-licensing-absent takes precedence")
    else:
        if not args.only:
            logger.error(
                "--only is MANDATORY unless --all-quarantined or --all-licensing-absent is "
                "passed — refusing to guess scope"
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

        # Content-preservation gate — state-selected scope ONLY. The quarantine
        # population is deliberately exempt: there the stored content is
        # FABRICATED by definition (invented risk tiers, a capital figure from a
        # revoked regulation), so "preserve what a human wrote" would preserve
        # exactly what the cure exists to destroy. Same code, opposite duty,
        # decided by which selector chose the row.
        if args.all_licensing_absent:
            keep, refused = [], []
            for code in codes:
                row = table_rows.get(code)
                reason = rebuild_reason(
                    code,
                    row["content"] if row is not None else None,
                    canonical_rows_by_code.get(code, 0),
                )
                (keep if reason else refused).append((code, reason))
            logger.info(
                "content-preservation gate: %d of %d row(s) rebuildable "
                "(%d machine-template, %d contradicted-licensing-claim); %d REFUSED to protect "
                "hand-written prose canonical cannot regenerate",
                len(keep),
                len(codes),
                sum(1 for _, r in keep if r == "machine-template"),
                sum(1 for _, r in keep if r == "contradicted-licensing-claim"),
                len(refused),
            )
            for code, _ in refused:
                logger.info("  REFUSED %s: hand-written content, not a machine-seed row", code)
            codes = [c for c, _ in keep]
            if not codes:
                logger.warning("gate refused every selected row — nothing to do")
                return
        elif not args.all_quarantined:
            # `--only` BYPASSES the gate above, and that is the trap this block
            # exists to make loud. The gate cannot run here: a hand-written
            # scope means the operator, not a predicate, chose these codes, and
            # the legitimate `--only` lane (the Perpres-cap cures) exists
            # precisely to replace prose. So this REPORTS and never refuses.
            #
            # It matters because `--only` is also the ONLY selector that runs
            # inside the deployed image, which makes it the path most likely to
            # be handed a state-selected list by hand — exactly how the 25 rows
            # the gate protected on 2026-08-02 nearly went out anyway.
            #
            # canonical_rows is 0 on purpose: the detector's count does not
            # exist on this path, and deriving a second one for the same fact is
            # how two tools start disagreeing about it (W105). A
            # contradicted-licensing-claim row therefore reports as plain
            # hand-written — true, and the loud direction.
            overwritten = []
            for code in codes:
                row = table_rows.get(code)
                if row is None:
                    continue  # nothing stored to overwrite
                if rebuild_reason(code, row["content"], 0) is None:
                    overwritten.append(code)
            if overwritten:
                logger.warning(
                    "--only bypasses the content-preservation gate: %d of %d selected row(s) "
                    "carry hand-written prose this run will OVERWRITE (%s). The pre-cure text "
                    "goes to kbli_documents_archive, but ON CONFLICT DO NOTHING makes that "
                    "ONE-SHOT per code — a second cure of the same row preserves nothing.",
                    len(overwritten),
                    len(codes),
                    ", ".join(overwritten),
                )

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
