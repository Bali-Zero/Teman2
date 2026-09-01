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

TWO NARROW MODES, for the rows the gate protects (2026-09-01). `--pma-only`
and `--licensing-only` each sync ONE tuple inside `metadata` — the PMA
evidence tuple (`PMA_METADATA_KEYS`) or the licensing tuple
(`LICENSING_METADATA_KEYS`) — through a server-side jsonb merge that binds
only those keys; `judul`, `content` and every other key stay byte-identical.
Both require `--only`, refuse every `--all-*` selector and refuse each other
(two tuples, two cure runs). `--licensing-only` is one-directional: a code
whose canonical `per_skala` is empty is REFUSED, never emptied — that is the
quarantine class. These modes exist because since v34 the channel reads the
structured metadata and never the prose, so on a hand-written row the tuple
is the only thing a client can still be told wrong.

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
        --only 50113,68112,49213 --apply --cure-run kbli_cure:2026-08-08

    # every quarantined code (73 as of 2026-07-19), dry-run against prod
    # GitHub raw main:
    PYTHONPATH=. python backend/scripts/kbli_documents_cure.py --all-quarantined

    # apply (writes DB):
    fly ssh console -a nuzantara-rag -C \\
        "python backend/scripts/kbli_documents_cure.py --all-quarantined --apply \\
            --cure-run kbli_cure:2026-08-08"
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

from backend.scripts._kbli_archive import archive_row, ensure_archive_schema
from backend.services.kbli_pma_disclosure import disclose_pma, pma_claims_verified

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
#
# THE CURE COULD NOT RE-CURE ITS OWN OUTPUT (measured 2026-08-05).
#
# This set held the three sections of the 2026-02-18 SEED. But `build_content`
# also writes `## Perizinan` (always) and `## Catatan Verifikasi` (when there is
# a data note) — sections the seed never had. So every row this tool wrote
# failed its own `is_machine_template` and was refused on the next run as
# hand-written prose that must not be destroyed: prose the machine itself wrote.
# Measured on the live table: of the 55 rows cured on 2026-08-03, **0** were
# still recognised — all 55 were frozen against any future licensing update.
#
# The listed constant is now the seed's three PLUS everything the builder emits,
# and `test_the_builders_own_output_is_recognised_by_the_recogniser` regenerates
# real content and asserts the round trip — so adding a section to
# `build_content` without declaring it here fails CI instead of silently
# freezing the rows it writes.
MACHINE_TEMPLATE_SECTIONS = frozenset(
    {
        # the 2026-02-18 seed
        "Informasi Umum",
        "Deskripsi Kegiatan Usaha",
        "Investasi Asing (PMA)",
        # emitted by build_content — see the round-trip test
        "Perizinan",
        "Kewajiban",
        "Catatan Verifikasi",
    }
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

# The cure-run identifier comes from the INVOCATION (--cure-run), never a
# script constant. A constant makes every pass of this script share one
# cure_run: a later pass (different selection, different date) hits
# ON CONFLICT (kode_kbli, cure_run) DO NOTHING and its pre-cure snapshot is
# silently skipped — the one-shot disease resurrected across passes (round-2
# fix, 2026-08-08). The shared DDL + versioned INSERT live in _kbli_archive
# (single source of truth — the duplicated DDL that was here and in
# kbli_documents_phantom_cure is how schemas drift).


@dataclass
class DocumentCurePlan:
    code: str
    found_in_canonical: bool
    found_in_table: bool
    is_gap: (
        bool | None
    )  # per_skala == [] -> True (honest-gap); non-empty -> False (restored); None if canonical/table missing
    new_judul: str | None
    new_content: str | None
    new_metadata: dict | None
    update_row: bool
    skip_reason: str | None
    # True when the plan touches ONLY the PMA evidence tuple inside `metadata`:
    # `judul` and `content` are left byte-identical by construction (see
    # `plan_pma_only`), so the apply path must not rewrite them either.
    pma_only: bool = False
    # Same contract for the licensing tuple (`plan_licensing_only`). The two
    # flags are exclusive by construction: `validate_args` refuses both.
    licensing_only: bool = False

    @property
    def partial_keys(self) -> tuple[str, ...] | None:
        """The metadata keys a NARROW plan binds to its server-side merge —
        or None when the plan is a full rebuild (judul + content + whole
        metadata). Single dispatch point for the apply path: a mode that is
        not listed here rewrites the row wholesale, loudly, never by accident."""
        if self.pma_only:
            return PMA_METADATA_KEYS
        if self.licensing_only:
            return LICENSING_METADATA_KEYS
        return None


# The PMA evidence tuple `build_cured_metadata` writes — and the ONLY keys a
# `--pma-only` plan may touch. Read by the channel as one atomic disclosure
# (`_pma_disclosure_fields`): a partial sync (status without basis/vintage)
# reads as NOT_VERIFIED at the surface, so the tuple moves together or not at
# all.
PMA_METADATA_KEYS: tuple[str, ...] = (
    "pma_status",
    "pma_max_asing",
    "pma_verification_status",
    "pma_official_basis",
    "pma_source_vintage",
    "pma_cap_special",
    "pma_cap_verified",
)

# The licensing tuple `build_cured_metadata` writes — and the ONLY keys a
# `--licensing-only` plan may touch. `per_skala` is the PP 28/2025 per-scale
# row-set the conformance detector measures (`jsonb_array_length(metadata->
# 'per_skala')` vs the canonical rows); `pp28_sources` is its provenance and
# moves with it; `licensing_status` follows the SAME rule the full rebuild
# applies (gap marker on an empty set, otherwise carried over — this script
# makes no independent claim about it).
LICENSING_METADATA_KEYS: tuple[str, ...] = (
    "per_skala",
    "pp28_sources",
    "licensing_status",
)

_ABSENT = object()  # a key that is not there is not the same as a key holding null


def _json_differs(a: object, b: object) -> bool:
    """Type-strict inequality for JSON-shaped values.

    Python's `==` says `False == 0` and `1 == True`; jsonb does not, and
    neither does the channel (`_public_pma_cap` demands a real bool before it
    publishes a cap). Comparing the serialised forms makes `false`/`0` and
    `80`/`80.0` differ exactly the way the store and the reader see them, so
    a bool-coerced tuple is reported stale instead of "already cured".
    """
    return json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(
        b, sort_keys=True, ensure_ascii=False
    )


def metadata_patch(new_metadata: dict, keys: tuple[str, ...]) -> dict:
    """Pure. The ONLY keys a narrow apply binds to its UPDATE.

    The write is a server-side merge (`metadata || $2::jsonb`), never a
    replacement of the whole column: the row's other keys are not
    round-tripped through Python (no float re-encoding of a value we did not
    plan to touch) and a write landing on some other key between our SELECT
    and our UPDATE is not clobbered.
    """
    return {key: new_metadata[key] for key in keys}


def pma_metadata_patch(new_metadata: dict) -> dict:
    """Pure. The seven PMA keys a `--pma-only` apply binds — see `metadata_patch`."""
    return metadata_patch(new_metadata, PMA_METADATA_KEYS)


def licensing_metadata_patch(new_metadata: dict) -> dict:
    """Pure. The three licensing keys a `--licensing-only` apply binds — see `metadata_patch`."""
    return metadata_patch(new_metadata, LICENSING_METADATA_KEYS)


def licensing_metadata_from_canonical(record: dict, old_metadata: dict | None) -> dict:
    """Pure. The licensing tuple exactly as `build_cured_metadata` writes it —
    ONE derivation shared by the full rebuild and the narrow sync, so the two
    paths cannot disagree about the same three keys (W105).

    `per_skala` is the CURRENT canonical row-set (`[]` for an honest gap);
    `pp28_sources` is whatever canonical records as its provenance;
    `licensing_status` gets the KG cure's `PENDING_REGULATION` marker on an
    empty set and is otherwise carried over unchanged (`N/A` when the row
    never had one) — the rebuild has always declined to assert it, and the
    narrow mode inherits that restraint rather than inventing a value."""
    old = old_metadata or {}
    per_skala = record.get("per_skala") or []
    return {
        "per_skala": per_skala,
        "pp28_sources": record.get("pp28_sources"),
        "licensing_status": "PENDING_REGULATION"
        if per_skala == []
        else old.get("licensing_status", "N/A"),
    }


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


def selector_conflict(
    *, quarantined: bool, licensing_absent: bool, machine_template: bool
) -> str | None:
    """Pure. The refusal message when more than one scope selector is on, or None.

    The three selectors choose populations three different WAYS — a canonical
    marker, a detector's verdict about live state, and the stored text itself —
    so a union has no single sentence that describes what acted, and the run
    report is the only record of a write to a client-facing table. They also
    carry OPPOSITE duties: the quarantine scope deliberately destroys stored
    content (it is fabricated by definition) while the table scope refuses to.
    Silently letting one win is how a run destroys prose under a flag the
    operator thought meant something narrower.

    Pure and out here because the refusal lives in `main`, which no test can
    execute (it opens a real connection) — inline, a mutation disabling the
    check survived the whole suite.
    """
    chosen = [
        name
        for name, on in (
            ("--all-quarantined", quarantined),
            ("--all-licensing-absent", licensing_absent),
            ("--all-machine-template", machine_template),
        )
        if on
    ]
    if len(chosen) < 2:
        return None
    return (
        f"{' and '.join(chosen)} select DIFFERENT populations DIFFERENT ways (marker vs detector "
        "state vs stored text) — refusing to union them, because the run report could no longer "
        "say which scope acted. Run them separately."
    )


def select_machine_template_rows(
    codes: list[str], table_rows: dict[str, dict]
) -> tuple[list[str], int]:
    """Pure. The `--all-machine-template` population: of the codes queried, the
    rows the table actually holds, narrowed to the ones whose STORED TEXT is a
    machine seed. Returns (kept, how many were present) so the caller can print
    N of M rather than a bare N (W97).

    It lives out here, and `main` does nothing but call it, on purpose: while it
    was three lines inlined in `main` a mutation that replaced the predicate with
    `True` — rebuild every row present, including 316 pieces of hand-written
    editorial prose — SURVIVED the whole suite, because the test re-implemented
    the filter instead of calling it. A decision that only exists inside an
    un-runnable function is a decision nothing tests.
    """
    present = [c for c in codes if c in table_rows]
    return [c for c in present if is_machine_template(c, table_rows[c]["content"])], len(present)


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
        raise RuntimeError(
            f"--snapshot-captured-at is not ISO8601: {captured_at!r} ({exc})"
        ) from exc
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


# The extraction carries markup on ~1.8% of obligation strings (1,524 of 86,241
# requirement+obligation entries, measured 2026-08-05). Stripped, never
# rendered: this text is read by an LLM and spoken to a client, and `<strong>`
# is not a fact.
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")

# Beyond this, the obligation block would dominate the document it is part of.
# Measured on canonical: 1,490 of 1,559 records (95.6%) fit whole; 69 do not,
# and those say so IN THE TEXT rather than being quietly cut (W97 — a silent
# truncation reads downstream as "this is everything").
KEWAJIBAN_BLOCK_MAX_CHARS = 8000


def _scale_label(entry: dict) -> str:
    label = _join(entry.get("skala_usaha"))
    scope = entry.get("scope_uraian")
    return f"{label} ({scope})" if scope else label


def build_kewajiban_section(record: dict) -> list[str]:
    """The statutory obligations, grouped by the scales that share them.

    WHY THIS EXISTS (measured on canonical 2026-08-05, 9,095 per-scale rows):

        perizinan    non-empty in     17 rows  (0.19%)
        persyaratan  non-empty in  5,369 rows  (59%)
        kewajiban    non-empty in  8,951 rows  (98%)

    `## Perizinan` renders `perizinan` and nothing else — the ONE field that is
    empty 99.8% of the time — so the channel's answer about what a business must
    actually do was `Perizinan: N/A` for practically the whole catalogue, while
    the field carrying the real obligations was dropped. On `96230` (a day spa)
    canonical holds "Memiliki Sertifikat Standar Usaha Pariwisata" and "Memiliki
    Sertifikat Laik Sehat (SLS)" — the SLHS itself — and the channel was telling
    clients the requirements were "still pending". The WEBSITE already renders
    them (`balizero.com/kbli/96230` prints "Laik Sehat"), so this is the same
    shape as the rest of this lane: the page tells the truth, the channel does not.

    GROUPED, not per-scale-repeated, because the same obligation is usually
    carried by every scale: rendering it once per row costs 3.5M characters
    catalogue-wide against 1.1M grouped, and a client does not need "Sertifikat
    Laik Sehat" four times. The scales are NAMED on each group, because 912 of
    1,341 records genuinely differ by scale — collapsing them to one block would
    lose which scale an obligation belongs to.

    `persyaratan` is deliberately NOT rendered here: 6% of its entries are
    multi-line OSS document checklists (max 6,622 chars) whose bounded shape is
    a separate design question, ledgered rather than guessed at. Stating that is
    the point — an omission nobody wrote down reads as "there was nothing".
    """
    groups: dict[tuple[str, ...], list[str]] = {}
    for entry in record.get("per_skala") or []:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("kewajiban") or []
        if not isinstance(raw, list):
            raw = [raw]
        cleaned = tuple(
            text for text in (_HTML_TAG_RE.sub("", str(v)).strip() for v in raw if v) if text
        )
        if not cleaned:
            continue
        groups.setdefault(cleaned, []).append(_scale_label(entry))

    if not groups:
        return []

    lines: list[str] = []
    budget = KEWAJIBAN_BLOCK_MAX_CHARS
    dropped = 0
    for obligations, scales in groups.items():
        bullet = f"- **{', '.join(scales)}**: " + "; ".join(obligations)
        if len(bullet) > budget and lines:
            dropped += 1
            continue
        budget -= len(bullet)
        lines.append(bullet)
    if dropped:
        lines.append(
            f"- _({dropped} ulteriori kelompok kewajiban tidak ditampilkan di sini "
            f"karena panjang — tanyakan skala usaha tertentu untuk rinciannya.)_"
        )
    return ["", "## Kewajiban", *lines]


def build_perizinan_section(record: dict) -> str:
    """The licensing section — the ONLY place licensing/risk facts can enter
    the cured content. Two branches, both provenance-bound:
      - per_skala non-empty (a restored code, e.g. 49213): render the REAL
        canonical per_skala rows as structured bullets — nothing invented.
      - per_skala == [] (the honest-gap class): use `intel_2026.whatYouNeed`
        only when the PMA evidence tuple is located; otherwise use the neutral
        licensing fallback so editorial cannot bypass the PMA gate."""
    per_skala = record.get("per_skala") or []
    if per_skala:
        return "\n".join(_render_per_skala_entry(e) for e in per_skala)
    if not pma_claims_verified(record):
        return GAP_FALLBACK_TEXT
    what_you_need = ((record.get("intel_2026") or {}).get("whatYouNeed") or "").strip()
    return what_you_need or GAP_FALLBACK_TEXT


def build_cured_content(code: str, record: dict) -> str:
    """Pure — deterministic markdown built ONLY from canonical fields.
    Keeps the healthy factual-identity part (title/what-it-means from
    `uraian`) and routes every licensing/risk/capital fact through
    `build_perizinan_section` (the sole provenance-bound entry point)."""
    judul = (record.get("judul") or "").strip() or f"KBLI {code}"
    uraian = (record.get("uraian") or "").strip() or "(deskripsi belum tersedia)"
    pma = disclose_pma(record)
    pma_status = pma["pma_status"]
    pma_max_asing = pma["pma_max_asing"]
    pma_kondisi = pma["pma_kondisi"]
    pma_nota = pma["pma_nota"]
    data_note = (record.get("_data_note") or "").strip() if pma_claims_verified(record) else ""

    lines: list[str] = [
        f"# KBLI {code} — {judul}",
        "",
        "## Deskripsi Kegiatan Usaha",
        uraian,
        "",
        "## Investasi Asing (PMA)",
        f"- Status PMA: {pma_status}",
    ]
    if pma["pma_cap_verified"]:
        if pma_max_asing == "special":
            lines.append("- Kepemilikan Asing: kondisi khusus non-persentase")
        elif pma_max_asing is not None:
            lines.append(f"- Maksimum Kepemilikan Asing: {pma_max_asing}%")
    else:
        lines.append("- Maksimum Kepemilikan Asing: belum terverifikasi")
    if pma_kondisi:
        lines.append(f"- Kondisi: {pma_kondisi}")
    if pma_nota:
        lines.append(f"- Catatan PMA: {pma_nota}")
    lines += ["", "## Perizinan", build_perizinan_section(record)]
    lines += build_kewajiban_section(record)
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
    licensing = licensing_metadata_from_canonical(record, old)
    pma = disclose_pma(record)
    new_meta: dict = {
        "judul": record.get("judul"),
        "per_skala": licensing["per_skala"],
        "sektor_id": record.get("sektor_id"),
        "pma_status": pma["pma_status"],
        "pma_max_asing": pma["pma_max_asing"],
        "pma_verification_status": pma["pma_verification_status"],
        "pma_official_basis": pma["pma_official_basis"],
        "pma_source_vintage": pma["pma_source_vintage"],
        "pma_cap_special": pma["pma_cap_special"],
        "pma_cap_verified": pma["pma_cap_verified"],
        "pp28_sources": licensing["pp28_sources"],
        "kode_kbli_2025": code,
        "status_mapping": record.get("status_mapping"),
        "licensing_status": licensing["licensing_status"],
    }
    data_note = record.get("_data_note") if pma_claims_verified(record) else None
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

    update_row = (
        (new_content != old_content) or (new_metadata != old_metadata) or (new_judul != old_judul)
    )

    return DocumentCurePlan(
        code=code,
        found_in_canonical=True,
        found_in_table=True,
        is_gap=is_gap,
        new_judul=new_judul if update_row else None,
        new_content=new_content if update_row else None,
        new_metadata=new_metadata if update_row else None,
        update_row=update_row,
        skip_reason=None
        if update_row
        else "already cured (content/metadata/judul match canonical)",
    )


def plan_pma_only(code: str, record: dict | None, current_row: dict | None) -> DocumentCurePlan:
    """Pure decision function for `--pma-only` — no I/O.

    Syncs the PMA evidence tuple in `metadata` from canonical and NOTHING else:
    `judul`, `content` and every other metadata key (`per_skala`,
    `licensing_status`, `pp28_sources`, ...) are carried over unchanged. This is
    the cure for a row whose hand-written prose must survive: the full rebuild
    (`plan_cure`) replaces `content` wholesale, which is exactly what the
    content-preservation gate refuses on such rows — and since v34 the channel
    never injects `content` anyway, so the structured tuple is the only thing
    the client can still be told wrong.

    The tuple comes from `disclose_pma(record)` — the same fail-closed reader
    the channel uses — so a canonical record without a located basis+vintage
    syncs as NOT_VERIFIED rather than as a bare status.
    """
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
            pma_only=True,
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
            pma_only=True,
        )

    old_metadata = dict(current_row.get("metadata") or {})
    pma = disclose_pma(record)
    new_metadata = dict(old_metadata)
    for key in PMA_METADATA_KEYS:
        new_metadata[key] = pma[key]
    # Type-strict on purpose: a row holding `pma_cap_verified: 1` or
    # `pma_max_asing: false` reads as unverified at the surface, so it is
    # stale even though Python's `==` would call it equal to `True` / `0`.
    update_row = _json_differs(new_metadata, old_metadata)
    return DocumentCurePlan(
        code=code,
        found_in_canonical=True,
        found_in_table=True,
        is_gap=(record.get("per_skala") == []),
        new_judul=None,
        new_content=None,
        new_metadata=new_metadata if update_row else None,
        update_row=update_row,
        skip_reason=None if update_row else "already cured (metadata PMA tuple matches canonical)",
        pma_only=True,
    )


def plan_licensing_only(
    code: str, record: dict | None, current_row: dict | None
) -> DocumentCurePlan:
    """Pure decision function for `--licensing-only` — no I/O.

    Syncs the licensing tuple in `metadata` from canonical and NOTHING else:
    `judul`, `content` and every other metadata key (the PMA tuple included)
    are carried over unchanged. Same reason `--pma-only` exists: the rows the
    detector reports as "canonical holds PP 28/2025 rows, the table serves
    none" are hand-written prose the content-preservation gate refuses to
    rebuild, and since v34 the structured metadata is the only thing the
    channel still reads from them.

    ONE DIRECTION, like `licensing_absent_codes`: this mode only ever REPLACES
    an empty or stale row-set with canonical's non-empty one. A code whose
    canonical `per_skala` is `[]` is refused, not emptied — a table row-set
    that canonical has since detached is the QUARANTINE class
    (`--all-quarantined`, which archives and rebuilds because that prose is
    fabricated by definition). Emptying it from here would destroy a row-set
    while reporting a cure.
    """
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
            licensing_only=True,
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
            licensing_only=True,
        )
    if not (record.get("per_skala") or []):
        return DocumentCurePlan(
            code=code,
            found_in_canonical=True,
            found_in_table=True,
            is_gap=True,
            new_judul=None,
            new_content=None,
            new_metadata=None,
            update_row=False,
            skip_reason=(
                "canonical holds no licensing rows for this code — refusing to empty the "
                "stored row-set under --licensing-only (a detached row-set is the "
                "--all-quarantined class)"
            ),
            licensing_only=True,
        )

    old_metadata = dict(current_row.get("metadata") or {})
    new_metadata = dict(old_metadata)
    new_metadata.update(licensing_metadata_from_canonical(record, old_metadata))
    # Type-strict for the same reason as `plan_pma_only`: `[]` vs `null` vs a
    # JSON string holding "[]" are three different things to jsonb and to
    # `jsonb_array_length`, and Python's `==` would call some of them equal.
    update_row = _json_differs(new_metadata, old_metadata)
    return DocumentCurePlan(
        code=code,
        found_in_canonical=True,
        found_in_table=True,
        is_gap=False,
        new_judul=None,
        new_content=None,
        new_metadata=new_metadata if update_row else None,
        update_row=update_row,
        skip_reason=None
        if update_row
        else "already cured (metadata licensing tuple matches canonical)",
        licensing_only=True,
    )


def _tuple_delta(
    old_metadata: dict | None, new_metadata: dict | None, keys: tuple[str, ...]
) -> str:
    """Pure. `key: old -> new` for every key of the tuple that moves — the run
    report must say WHAT moved, not just that a row was touched. A list value
    is shown by its length (a 60-row `per_skala` is a measurement, not a log
    line); every other value by its repr."""
    old = old_metadata or {}
    new = new_metadata or {}

    def _moved(o: object, n: object) -> bool:
        if (o is _ABSENT) or (n is _ABSENT):
            return o is not n  # absent -> null IS a move; absent -> absent is not
        return _json_differs(o, n)

    def _show(v: object) -> str:
        if v is _ABSENT:
            return "<absent>"
        if isinstance(v, list):
            return f"<{len(v)} rows>"
        return repr(v)

    return ", ".join(
        f"{key}: {_show(old.get(key, _ABSENT))} -> {_show(new.get(key, _ABSENT))}"
        for key in keys
        if _moved(old.get(key, _ABSENT), new.get(key, _ABSENT))
    )


def pma_tuple_delta(old_metadata: dict | None, new_metadata: dict | None) -> str:
    """Pure. The PMA tuple's moves — see `_tuple_delta`."""
    return _tuple_delta(old_metadata, new_metadata, PMA_METADATA_KEYS)


def licensing_tuple_delta(old_metadata: dict | None, new_metadata: dict | None) -> str:
    """Pure. The licensing tuple's moves — see `_tuple_delta`."""
    return _tuple_delta(old_metadata, new_metadata, LICENSING_METADATA_KEYS)


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


def build_parser() -> argparse.ArgumentParser:
    """Module-level argparse construction so tests exercise the REAL parser,
    not a copy that stays green if production validation is deleted."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument(
        "--cure-run",
        default=None,
        help=(
            "Stable identifier of THIS cure pass, e.g. "
            "'<script>:<scope-or-spec-date>' — each pass declares its own; "
            "re-running the same pass with the same id stays idempotent, "
            "a new pass MUST use a new id or its snapshots are silently skipped. "
            "REQUIRED when --apply is passed."
        ),
    )
    ap.add_argument(
        "--only",
        default=None,
        help="comma-separated list of 5-digit codes to process "
        "(mandatory unless --all-quarantined or --all-licensing-absent)",
    )
    ap.add_argument(
        "--pma-only",
        action="store_true",
        help="with --only: sync ONLY the PMA evidence tuple inside `metadata` from canonical "
        "(pma_status, cap, verification status, official basis, source vintage). `judul`, "
        "`content` and every other metadata key are left byte-identical — the cure for rows "
        "whose hand-written prose the full rebuild would destroy. Refuses to combine with any "
        "--all-* selector.",
    )
    ap.add_argument(
        "--licensing-only",
        action="store_true",
        help="with --only: sync ONLY the licensing tuple inside `metadata` from canonical "
        "(per_skala, pp28_sources, licensing_status). `judul`, `content` and every other "
        "metadata key are left byte-identical. One direction only: a code whose canonical "
        "per_skala is empty is refused, never emptied (that is --all-quarantined's class). "
        "Refuses to combine with any --all-* selector or with --pma-only.",
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
        "--all-machine-template",
        action="store_true",
        help="rebuild every row the table itself shows to be a machine-seed document, i.e. every "
        "row `is_machine_template` accepts (299 of 1,563 measured 2026-08-05). TABLE-selected: "
        "the population is a property of the stored text, not of a marker or a detector, so this "
        "is the only selector that can DELIVER a change to the builder — the other three each "
        "answer a narrower question and together they reach a few dozen rows. Lossless by "
        "construction: a machine-seed row is regenerated from the same canonical fields it was "
        "built from. The other 1,264 rows keep their hand-written prose and are named, not "
        "silently skipped.",
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
    return ap


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> str:
    """Module-level validation of parsed args, returning the resolved cure_run.

    Lives outside ``main`` so tests exercise the REAL production validation
    rather than a re-implementation that stays green if this check is deleted.
    """
    # --cure-run: REQUIRED on apply; defaults to "dry-run" otherwise. A constant
    # would make every pass of this script share one cure_run, and a later pass's
    # pre-cure snapshot would be silently skipped by ON CONFLICT DO NOTHING — the
    # one-shot disease resurrected across passes.
    if args.apply and not args.cure_run:
        parser.error(
            "--cure-run is REQUIRED when --apply is passed — each cure pass declares its own stable id"
        )
    # --pma-only / --licensing-only are NARROWER writes on an operator-named
    # scope, never a sweep: the --all-* selectors each justify a WHOLESALE
    # rebuild (marker / detector / stored text), and none of them says anything
    # about one tuple alone.
    narrow = [
        name
        for name, on in (
            ("--pma-only", getattr(args, "pma_only", False)),
            ("--licensing-only", getattr(args, "licensing_only", False)),
        )
        if on
    ]
    if len(narrow) > 1:
        parser.error(
            "--pma-only and --licensing-only are two tuples and two cure runs — run them separately"
        )
    if narrow:
        (mode,) = narrow
        sweep = [
            name
            for name, on in (
                ("--all-quarantined", getattr(args, "all_quarantined", False)),
                ("--all-licensing-absent", getattr(args, "all_licensing_absent", False)),
                ("--all-machine-template", getattr(args, "all_machine_template", False)),
            )
            if on
        ]
        if sweep:
            parser.error(
                f"{mode} cannot be combined with {' or '.join(sweep)} — name the codes with --only"
            )
        if not args.only:
            parser.error(f"{mode} requires --only <codes> — it never guesses scope")
    if not args.cure_run:
        return "dry-run"
    cure_run = args.cure_run.strip()
    if not cure_run:
        parser.error("--cure-run must not be empty")
    if any(c.isspace() for c in cure_run):
        parser.error(f"--cure-run must not contain whitespace (got {cure_run!r})")
    return cure_run


async def main() -> int | None:
    ap = build_parser()
    args = ap.parse_args()
    cure_run = validate_args(ap, args)

    dataset = await load_dataset(args.dataset)

    canonical_rows_by_code: dict[str, int] = {}
    conflict = selector_conflict(
        quarantined=args.all_quarantined,
        licensing_absent=args.all_licensing_absent,
        machine_template=args.all_machine_template,
    )
    if conflict:
        logger.error("%s", conflict)
        return

    if args.all_machine_template:
        # Every code the canonical carries. The table-shaped narrowing happens
        # below, after the rows are read — the predicate is a property of the
        # STORED TEXT, so it cannot be evaluated before the fetch, and it is the
        # SAME `rebuild_reason` the other gate calls rather than a second copy
        # of it (two predicates for one decision is how they start disagreeing).
        codes = [str(r.get("kode_kbli_2025")) for r in dataset if r.get("kode_kbli_2025")]
        if args.only:
            logger.warning("--only ignored: --all-machine-template takes precedence")
    elif args.all_quarantined:
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
            await ensure_archive_schema(conn)

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
        if args.all_machine_template:
            # Table-selected: keep ONLY rows whose stored text is a machine seed.
            # `contradicted-licensing-claim` is deliberately NOT admitted here —
            # that reason needs the detector's per-code `canonical_rows`, which
            # this path does not have, and inventing a second count for it is
            # exactly the drift W105 describes. A broad rebuild must be the
            # lossless case and nothing else.
            keep, n_present = select_machine_template_rows(codes, table_rows)
            logger.info(
                "table-selected scope: %d machine-seed row(s) of %d present in the table "
                "(%d canonical codes queried); the other %d keep hand-written prose and are NOT "
                "rebuilt — closing them needs prose re-authored around the new rows, not a script",
                len(keep),
                n_present,
                len(codes),
                n_present - len(keep),
            )
            codes = keep
            if not codes:
                logger.warning("no machine-seed row in the table — nothing to do")
                return
        elif args.all_licensing_absent:
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
        elif not args.all_quarantined and not (args.pma_only or args.licensing_only):
            # (the narrow modes are exempt: they rewrite no prose, so the warning
            # below would be a false alarm about an overwrite that cannot happen.)
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
                    json.loads(row["metadata"])
                    if isinstance(row["metadata"], str)
                    else row["metadata"]
                )
                current_row = {
                    "judul": row["judul"],
                    "content": row["content"],
                    "metadata": metadata or {},
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            if args.pma_only:
                plan = plan_pma_only(code, by_code.get(code), current_row)
            elif args.licensing_only:
                plan = plan_licensing_only(code, by_code.get(code), current_row)
            else:
                plan = plan_cure(code, by_code.get(code), current_row)
            plans.append(plan)

            if not plan.update_row:
                logger.info("SKIP %s: %s", code, plan.skip_reason)
                continue

            if plan.partial_keys is not None:
                assert current_row is not None
                logger.info(
                    "  %s: %s metadata %s tuple only (judul/content byte-identical): %s",
                    code,
                    "syncing" if args.apply else "would sync",
                    "PMA" if plan.pma_only else "licensing",
                    _tuple_delta(current_row.get("metadata"), plan.new_metadata, plan.partial_keys),
                )
            else:
                logger.info(
                    "  %s: %s kbli_documents (%d chars)%s",
                    code,
                    "updating" if args.apply else "would update",
                    len(plan.new_content or ""),
                    " [GAP]" if plan.is_gap else " [RESTORED]",
                )
            if args.apply:
                assert current_row is not None  # update_row=True implies found_in_table=True
                params = archive_params(code, current_row)
                await archive_row(conn, code, params, cure_run)
                # W89 jsonb double-encoding class-guard (kg_kbli_license_fix.py
                # precedent): bind the pre-serialized json.dumps() string to a
                # $N::text::jsonb placeholder so the server casts text->jsonb
                # exactly once.
                if plan.partial_keys is not None:
                    # Server-side merge of the tuple ONLY: `||` overwrites the
                    # bound keys (a JSON null value still overwrites, it does not
                    # delete) and leaves every other key exactly as stored.
                    # The CASE guards the LEFT operand: `NULL || x` is NULL (a
                    # silent no-op on an empty column), and a JSON scalar or
                    # array on the left — `'null'::jsonb || {..}` — does not
                    # merge, it BUILDS AN ARRAY, so the next run would not be
                    # idempotent. `coalesce` alone only covers the SQL NULL.
                    assert plan.new_metadata is not None
                    await conn.execute(
                        "UPDATE kbli_documents "
                        "SET metadata = (CASE WHEN jsonb_typeof(metadata) = 'object' "
                        "THEN metadata ELSE '{}'::jsonb END) || $2::text::jsonb, "
                        "updated_at = now() WHERE kode_kbli = $1",
                        code,
                        json.dumps(
                            metadata_patch(plan.new_metadata, plan.partial_keys),
                            ensure_ascii=False,
                        ),
                    )
                else:
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
