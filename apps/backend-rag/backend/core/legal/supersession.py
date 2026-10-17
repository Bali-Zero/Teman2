"""
Pasal-level supersession metadata — the minimal arm of PENDING-ARMS 2026-08-25.

THE HOLE THIS CLOSES. ``retrieval_scope`` (current/historical_only) is a
WHOLE-DOCUMENT field and the current-law guard
(``SearchService._requires_current_law_guard``) filters per document. That is
right for a REPEALED act (the whole document leaves ``current``), wrong for an
AMENDED one: UU 6/2011 (amended by UU 63/2024) and Permenkumham 22/2023
(amended by Permenkumham 11/2024) are both still in force and must stay
``current`` — which left their PRE-AMENDMENT pasal wording live in the store,
retrievable with a real citation, readable as current law.

WHAT THIS MODULE IS. The metadata WRITER half of the fix. It parses an
amending instrument's OWN "Pasal X diubah/dicabut/ditambah" clauses and
annotates the affected chunks of the BASE document with flat payload keys:

    superseded_by_document   "UU_63_2024"      (document_id of the amendment)
    superseded_pasal_number  "12"              (which base pasal was rewritten)
    superseded_action        "diubah"          (diubah | dicabut | ditambah)
    superseded_by_label      "UU 63/2024"      (human-readable amendment cite)

The retrieval-side rule lives in
``backend/services/search/supersession_guard.py`` and no-ops when these keys
are absent, so nothing here is load-bearing until both halves and a backfill
are in force.

SCOPE, STATED. Wired and tested for the two known amended pairs (UU 6/2011 x
UU 63/2024, Permenkumham 22/2023 x Permenkumham 11/2024). This is NOT a
corpus-wide retro-parse of every amendment ever; the backfill for the rest of
the corpus is a separate, scripted, dry-run-first operation
(scripts/backfill_pasal_supersession.py).

WHY FLAT KEYS. Legal payloads are flat on this collection (see
test_qdrant_flat_payload.py and the ``identity_source`` write in
legal_ingestion_service.py), and the retrieval guard reads these fields
in Python after retrieval — no server-side filter depends on them, so no new
payload index is required.

WHY THE ANNOTATOR FILTERS PASAL CLIENT-SIDE. The only payload index every
legal ingest guarantees exists is ``document_id`` (plus ``identity_source`` /
``retrieval_scope``). Filtering a scroll on ``pasal_number`` on a collection
without that index is an ERROR on this Qdrant deployment ("Index required but
not found"), not a slow query — so the annotator scrolls by ``document_id``
(indexed), matches ``pasal_number`` on the returned payloads, and writes back
by explicit point ids via ``set_payload``.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from backend.core.legal.constants import LEGAL_TYPE_ABBREV

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns — bounded, no nested quantifiers over overlapping classes
# (the constants.py ReDoS scar applies to every pattern added here too).
# ---------------------------------------------------------------------------

# An AMENDMENT DIRECTIVE: "Pasal 12 diubah ...", "Ketentuan Pasal 5 ayat (2)
# dicabut", "Pasal 1 angka 3 diubah ...", and the re-citing form "Ketentuan
# Pasal 128 Undang-Undang Nomor 6 Tahun 2011 dicabut". Up to two
# ayat/angka/huruf qualifiers may sit between the pasal number and the verb;
# one full instrument citation may too. The verb itself is required —
# "Pasal 3 diberlakukan" or a bare cross-reference "Pasal 3" must NOT match.
# Pasal numbers can be Roman (PASAL_PATTERN accepts [IVXLC]+) or alphanumeric
# ("12A"). Every gap is single-run horizontal space: no `\s*`, per the
# constants.py ReDoS scar.
_TYPE_ALT = (
    "PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG"
    "|UNDANG-UNDANG DASAR"
    "|UNDANG-UNDANG"
    "|PERATURAN PEMERINTAH"
    "|PERATURAN PRESIDEN"
    "|KEPUTUSAN PRESIDEN"
    "|INSTRUKSI PRESIDEN"
    "|PERATURAN MENTERI"
    "|KEPUTUSAN MENTERI"
    "|INSTRUKSI MENTERI"
    "|PERATURAN GUBERNUR"
    "|KEPUTUSAN GUBERNUR"
    "|PERATURAN BUPATI"
    "|PERATURAN WALIKOTA"
    "|PERATURAN WALI KOTA"
    "|PERATURAN DAERAH"
    "|PERATURAN BADAN"
    "|PERATURAN KEPALA"
    "|SURAT EDARAN"
    "|QANUN"
)
_CITATION_INLINE = (
    rf"(?:{_TYPE_ALT})"
    r"[^\S\n]+NOMOR[^\S\n]+[A-Za-z0-9][A-Za-z0-9./-]{0,40}"
    r"[^\S\n]+TAHUN[^\S\n]+(?:19|20)\d{2}"
)
_AMEND_DIRECTIVE = re.compile(
    r"Pasal[^\S\n]+(?P<pasal>[IVXLC]+|\d+[A-Z]?)"
    r"(?:[^\S\n]+(?:ayat|angka|huruf)[^\S\n]*\(?[0-9A-Za-z]+\)?){0,2}"
    rf"(?:[^\S\n]+{_CITATION_INLINE})?"
    r"(?:[^\S\n]+TENTANG(?:[^\S\n]+[A-Za-z0-9][A-Za-z0-9.,'()-]*){0,12})?"
    r"(?:\n[^\S\n]*|[^\S\n]+)"
    r"(?P<action>diubah|dicabut|dihapus|ditambah)",
    re.IGNORECASE,
)

# A TARGET-INSTRUMENT mention: "Undang-Undang Nomor 6 Tahun 2011" /
# "Peraturan Menteri Nomor 22 Tahun 2023". Shares its citation body with
# _AMEND_DIRECTIVE's inline re-citation so the two cannot drift apart.
_TARGET_INSTRUMENT = re.compile(
    rf"(?P<type>{_TYPE_ALT})"
    r"[^\S\n]+NOMOR[^\S\n]+(?P<number>[A-Za-z0-9][A-Za-z0-9./-]{0,40})"
    r"[^\S\n]+TAHUN[^\S\n]+(?P<year>(?:19|20)\d{2})",
    re.IGNORECASE,
)

# A directive binds to the most recent target-instrument mention whose end is
# at most this many characters before the directive. Amendment articles are
# compact ("Beberapa ketentuan dalam UU Nomor 6 Tahun 2011 diubah: 1. ... 2. ..."),
# so a generous window absorbs lettered sub-clauses without reaching across
# into the NEXT instrument's citation.
_TARGET_WINDOW_CHARS = 1200


@dataclass(frozen=True)
class PasalSupersession:
    """One base-document pasal rewritten/repealed/added by an amendment."""

    base_type_abbrev: str
    base_number: str
    base_year: str
    pasal_number: str  # as written in the amendment ("12", "7A", "XII")
    action: str  # diubah | dicabut | ditambah


def _normalize_number(raw: str) -> str:
    """Reduce a cited number token to the plain instrument number.

    "6" and "M.IP-19.GR.01.01" pass through; a compound like "12/2024" keeps
    its head. Only the head is needed: document_id is built from the bare
    number and year.
    """
    head = re.split(r"[/\-]", raw.strip(), maxsplit=1)[0]
    return head


def parse_amendment_clauses(text: str) -> list[PasalSupersession]:
    """Parse an amending instrument's own text into pasal supersessions.

    Finds "Pasal X diubah/dicabut/ditambah" directives and binds each to the
    most recent target-instrument citation ("Undang-Undang Nomor 6 Tahun
    2011") before it. Directives with no target in the window are skipped —
    that is the honest no-op, not a guess: an unattributed "Pasal 3 diubah"
    cannot be tied to a base document safely.

    The amendment's OWN identity is taken by the caller (from the ingested
    document's metadata / doc_id), never from this text: an instrument's
    citation list names many laws, and scavenge-first identity is exactly the
    bug class the title-block pattern in constants.py exists to stop.
    """
    if not text:
        return []

    targets = [
        (
            m.end(),
            str(m.group("type")).upper(),
            _normalize_number(str(m.group("number"))),
            str(m.group("year")),
        )
        for m in _TARGET_INSTRUMENT.finditer(text)
    ]
    if not targets:
        return []

    seen: set[tuple[str, str, str, str, str]] = set()
    supersessions: list[PasalSupersession] = []

    for match in _AMEND_DIRECTIVE.finditer(text):
        window_start = max(0, match.start() - _TARGET_WINDOW_CHARS)
        candidates = [t for t in targets if window_start <= t[0] <= match.start()]
        if not candidates:
            logger.debug(
                "Amendment directive without target in window: Pasal %s %s at %d",
                match.group("pasal"),
                match.group("action"),
                match.start(),
            )
            continue
        _end, type_name, number, year = candidates[-1]
        type_abbrev = LEGAL_TYPE_ABBREV.get(type_name, type_name.title().replace(" ", ""))
        pasal = str(match.group("pasal"))
        action = str(match.group("action")).lower()
        key = (type_abbrev, number, year, pasal, action)
        if key in seen:
            continue
        seen.add(key)
        supersessions.append(
            PasalSupersession(
                base_type_abbrev=type_abbrev,
                base_number=number,
                base_year=year,
                pasal_number=pasal,
                action=action,
            )
        )

    return supersessions


def identity_triple_to_document_id(
    type_abbrev: str | None,
    number: str | None,
    year: str | None,
) -> str | None:
    """Map a parsed (type_abbrev, number, year) triple to its stored doc id.

    Returns None when the triple is incomplete: those documents were ingested
    with a hash-bound id (see build_content_bound_legal_doc_id) that cannot be
    reconstructed without the source bytes, so annotating them would require a
    lookup we cannot do honestly. The annotator records these as "unresolved"
    rather than guessing.
    """
    parts = [
        str(type_abbrev or "DOC"),
        str(number or "UNKNOWN"),
        str(year or "UNKNOWN"),
    ]
    normalized = [p.replace(" ", "_").replace("/", "_") for p in parts]
    if any(p.upper() in {"DOC", "UNKNOWN", "0", "NONE"} for p in normalized):
        return None
    return "_".join(normalized)


def build_supersession_payload(
    supersession: PasalSupersession,
    *,
    amendment_doc_id: str,
    amendment_label: str,
) -> dict[str, Any]:
    """Flat payload keys written onto the superseded chunk."""
    return {
        "superseded_by_document": amendment_doc_id,
        "superseded_pasal_number": supersession.pasal_number,
        "superseded_action": supersession.action,
        "superseded_by_label": amendment_label,
    }


async def annotate_superseded_pasals(
    vector_db: Any,
    supersessions: list[PasalSupersession],
    *,
    amendment_doc_id: str,
    amendment_label: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Annotate the base documents' chunks with supersession metadata.

    For each supersession: scroll the base document's points by ``document_id``
    (the one index every legal ingest guarantees), match ``pasal_number`` on
    the returned payloads client-side (an unindexed scroll filter is an ERROR
    on this Qdrant deployment, not a slow query), and write the supersession
    keys by explicit point ids.

    Idempotent: the payload keys are deterministic, so re-running after a
    partial failure converges. No-ops per-pasal when the base document or the
    pasal chunk is absent — recorded in ``unresolved``, never guessed.
    """
    annotated_points = 0
    annotated_pasals: list[str] = []
    unresolved: list[str] = []

    for sup in supersessions:
        base_doc_id = identity_triple_to_document_id(
            sup.base_type_abbrev,
            sup.base_number,
            sup.base_year,
        )
        label = (
            f"{sup.base_type_abbrev} {sup.base_number}/{sup.base_year} "
            f"Pasal {sup.pasal_number}"
        )
        if base_doc_id is None:
            unresolved.append(f"{label} (incomplete identity triple)")
            continue

        points = await vector_db.scroll_strict(metadata_filter={"document_id": base_doc_id})
        matching = [
            point
            for point in points
            if str((point.get("payload") or {}).get("pasal_number") or "")
            == sup.pasal_number
        ]
        if not matching:
            unresolved.append(f"{label} (no chunk under document_id={base_doc_id!r})")
            continue

        payload = build_supersession_payload(
            sup,
            amendment_doc_id=amendment_doc_id,
            amendment_label=amendment_label,
        )
        if dry_run:
            annotated_points += len(matching)
            annotated_pasals.append(label)
            continue
        await vector_db.set_payload(
            ids=[str(point["id"]) for point in matching],
            payload=payload,
        )
        annotated_points += len(matching)
        annotated_pasals.append(label)

    summary = {
        "amendment_doc_id": amendment_doc_id,
        "amendment_label": amendment_label,
        "dry_run": dry_run,
        "clauses_parsed": len(supersessions),
        "annotated_points": annotated_points,
        "annotated_pasals": annotated_pasals,
        "unresolved": unresolved,
    }
    if unresolved:
        logger.warning(
            "Supersession annotation left %d clause(s) unresolved for %s: %s",
            len(unresolved),
            amendment_label,
            unresolved,
        )
    return summary
