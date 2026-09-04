"""Every entry in ingest_2026_laws.py's LAWS_2026 must declare its own document_id.

DEFECT measured live on production 2026-09-04: only 2 of 21 entries (PMK_1_2026,
PermenImipas_1_2026) declared an explicit `document_id`. Every other entry let
`LegalIngestionService` derive `{type}_{number}_{year}` from the pattern
metadata extractor -- which does not always name the document itself, it can
name a law CITED in the document's own preamble. Confirmed wrong-identity
points landed in Qdrant `legal_unified` from exactly this gap:
PP_9_2026_THR_Gaji_13.pdf -> `UUD_17_2003` (105 pts) / `UU_17_2026` (58 pts,
earlier run, not a real law); SE_Gubernur_Bali_09_2025 -> `SE_18_2008` /
`PP_18_2025`; Pergub_Bali_14_2023 -> also `UU_14_2023` (953 pts, marked
dicabut); Perpres_157_2024 -> also `Perpres_39_2024`; Kepmen_MIP_19 -> also
`UU_28_2025`. Prove-live at the time: `ask_legal` on PP 9/2026 answered
"Sumber: UU No. 17 Tahun 2026", a law that does not exist.

The cure is this file's companion change to ingest_2026_laws.py: every
LAWS_2026 entry now declares `document_id`, in the `{type_abbrev}_{number}_
{year}` convention this KB already uses (`kb/inventory/immigration.yaml`,
e.g. `UU_6_2011`, `Permen_22_2023`), ministry-qualified for Permen-family
instruments (`PMK_`, `PermenImipas_`, `Permenkumham_`) because 8 ministries
independently number their regulations from 1 each year -- a bare
`Permen_1_2026` does not identify an instrument. This makes
`classify_identity_source()` (legal_ingestion_service.py) record "declared"
for every write this script makes, never "extracted" (the class of id that
let the wrong citation through).

`LAWS_2026` is parsed with `ast.literal_eval`, never imported. The script's
top-level code opens a `logging.FileHandler` against a hardcoded
`/Users/nuzantara/nuzantara` path and calls `load_dotenv` against another
hardcoded absolute path -- both raise on any machine/CI runner where that
path does not exist (this repo's #1 HOME-fork scar family; M5's home is
`/Users/balizero`). The script's own comment on the Permenkumham-34/2021 entry
already states the requirement this test leans on: "LAWS_2026 is a
module-level data literal that must stay `ast.literal_eval`-able."
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

DOC_ID_PATTERN = re.compile(r"^[A-Za-z_]+_[0-9]+_[0-9]{4}$")


def _find_script() -> Path:
    """Locate the script from THIS file's path, never from cwd.

    CI shards run pytest from `apps/backend-rag`; a cwd-relative lookup would
    report the module absent on precisely the machine that matters.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        script = candidate / "apps" / "backend-rag" / "scripts" / "ingest_2026_laws.py"
        if script.is_file():
            return script
    raise AssertionError(
        f"apps/backend-rag/scripts/ingest_2026_laws.py not found above {here} "
        "-- has the script moved?"
    )


def extract_laws_2026(source: str) -> list[dict]:
    """Parse the LAWS_2026 literal out of `source` without executing the module.

    Deliberately AST-based, not `exec`/`import`: the real script's top-level
    code has side effects (see module docstring) that fail off the one machine
    the script's hardcoded paths were written for.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "LAWS_2026" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(
        "LAWS_2026 assignment not found in ingest_2026_laws.py -- has it been "
        "renamed or restructured?"
    )


SCRIPT_PATH = _find_script()
LAWS_2026 = extract_laws_2026(SCRIPT_PATH.read_text(encoding="utf-8"))


def test_every_law_declares_a_document_id():
    missing = [law["filename"] for law in LAWS_2026 if not law.get("document_id")]
    assert missing == [], (
        "these LAWS_2026 entries have no declared document_id -- "
        "LegalIngestionService falls back to the extracted (type, number, "
        "year) triple, which can name a law CITED in the preamble instead of "
        f"the document itself (see module docstring): {missing}"
    )


def test_document_ids_are_unique():
    # .get(), not indexing: a missing document_id must fail as a clean
    # assertion here too, not mask this test behind a KeyError raised by
    # test_every_law_declares_a_document_id running first.
    ids = [law.get("document_id") for law in LAWS_2026]
    duplicates = sorted({i for i in ids if i is not None and ids.count(i) > 1})
    assert duplicates == [], f"duplicate document_id(s) in LAWS_2026: {duplicates}"


def test_document_ids_match_type_number_year_convention():
    bad = [
        law.get("document_id")
        for law in LAWS_2026
        if law.get("document_id") and not DOC_ID_PATTERN.match(law["document_id"])
    ]
    assert bad == [], (
        "document_id must match this KB's identity convention "
        "'{type_abbrev}_{number}_{year}' (e.g. UU_6_2011, Permenkumham_22_2023): "
        f"{bad}"
    )


def test_the_real_script_still_parses_as_a_literal_with_all_entries_present():
    """Anti-vacuity: if LAWS_2026 stopped being ast.literal_eval-able, every
    assertion above would never run at all -- `extract_laws_2026` raises at
    module-import time, not inside a test function, so a broken parse would
    silently look like a collection error rather than a red assertion. Pin a
    non-trivial count so a scanner that started returning [] is caught too.
    """
    assert len(LAWS_2026) >= 20, (
        f"expected at least 20 LAWS_2026 entries, found {len(LAWS_2026)} -- "
        "either entries were removed or the AST extraction silently broke"
    )


# ---- guilt / innocence on the extraction+assertion logic itself ----


def test_the_checker_actually_catches_a_missing_document_id():
    """GUILT. A synthetic LAWS_2026 with one entry missing document_id."""
    source = (
        "LAWS_2026 = [\n"
        '    {"document_id": "UU_1_2023", "filename": "a.pdf"},\n'
        '    {"filename": "b.pdf"},\n'
        "]\n"
    )
    laws = extract_laws_2026(source)
    missing = [law["filename"] for law in laws if not law.get("document_id")]
    assert missing == ["b.pdf"]


def test_the_checker_actually_catches_a_duplicate_document_id():
    """GUILT. Two entries sharing the same declared identity."""
    source = (
        "LAWS_2026 = [\n"
        '    {"document_id": "Permen_1_2026", "filename": "a.pdf"},\n'
        '    {"document_id": "Permen_1_2026", "filename": "b.pdf"},\n'
        "]\n"
    )
    laws = extract_laws_2026(source)
    ids = [law["document_id"] for law in laws]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert duplicates == ["Permen_1_2026"]


def test_the_checker_actually_catches_a_malformed_document_id():
    """GUILT. An id that does not fit {type_abbrev}_{number}_{year}."""
    source = 'LAWS_2026 = [{"document_id": "PMK-1-2026", "filename": "a.pdf"}]\n'
    laws = extract_laws_2026(source)
    bad = [law["document_id"] for law in laws if not DOC_ID_PATTERN.match(law["document_id"])]
    assert bad == ["PMK-1-2026"]


def test_the_checker_passes_a_fully_declared_synthetic_list():
    """INNOCENCE. All ids present, unique, well-formed -> no violation."""
    source = (
        "LAWS_2026 = [\n"
        '    {"document_id": "UU_1_2023", "filename": "a.pdf"},\n'
        '    {"document_id": "PP_9_2026", "filename": "b.pdf"},\n'
        "]\n"
    )
    laws = extract_laws_2026(source)
    ids = [law["document_id"] for law in laws]
    assert all(law.get("document_id") for law in laws)
    assert len(ids) == len(set(ids))
    assert all(DOC_ID_PATTERN.match(i) for i in ids)


# ---------------------------------------------------------------------------
# LANE-A-7: the ingest script and the KB must not spell the same instrument
# two different ways.
#
# `ingest_2026_laws.py` declares `Permenkumham_22_2023` / `Permenkumham_11_2024`
# (ministry-qualified, deliberately — see the script's own comment: 8 ministries
# number their regulations from 1 each year, so a bare `Permen_N_YYYY` does not
# identify an instrument). The KB — `kb/inventory/`, `kb/topics/`,
# `kb/journeys/` — and every point in production Qdrant use the SHORT form
# `Permen_22_2023` / `Permen_11_2024`. They are the SAME regulation: this
# module's own docstring above cites `Permen_22_2023` as the KB convention
# while the script beside it writes the qualified form, and
# `kb/topics/immigration.yaml` settles it — the entry whose `id` is
# `Permen_22_2023` carries
# `verified_identity: "Permenkumham 22/2023 — Visa dan Izin Tinggal"`,
# fetched from peraturan.go.id.
#
# NOTHING RECONCILES THEM, and nothing FAILS either: no test compares the
# script's ids against the KB's, so the divergence is invisible. It is not a
# live defect today only because production Qdrant holds zero points under the
# qualified spelling — the 2026-09-04 batch never re-ingested these two PDFs.
# The moment anyone runs this script over them, the instrument acquires a
# SECOND document_id and the two live probes that hardcode the short form
# (`scripts/kb/probe_legal_status_marking.py`, `propose_legal_status_repair.py`)
# start silently missing half the corpus.
#
# This test does not pick the winning spelling — that is a convention decision
# with a production data migration attached, and it is open. It makes the
# divergence LOUD and BOUNDED: the two known pairs are named below, and any
# THIRD divergence fails immediately.
# ---------------------------------------------------------------------------

ID_PARTS = re.compile(r"^([A-Za-z][A-Za-z0-9]*)_(\d+)_(\d{4})$")

# The open pairs, as of 2026-09-05: script id -> KB id. Compared by EQUALITY,
# never by containment — reconciling one without deleting its row here fails
# this test too, so the exception cannot outlive the problem it names.
KNOWN_UNRECONCILED_SPELLINGS = {
    "Permenkumham_22_2023": "Permen_22_2023",
    "Permenkumham_11_2024": "Permen_11_2024",
}


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "kb").is_dir() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root (with kb/ and apps/) not found above {here}")


def _kb_instrument_identities() -> dict[str, str]:
    """Map every KB instrument id to the identity prose declared beside it.

    Line-scanned, not YAML-parsed, on purpose: this test lives in the backend
    suite and must not acquire a parser dependency to read five data files.
    An id with no identity prose maps to "" — which is the INNOCENT case
    below, since nothing then proves the two spellings name one instrument.
    """
    identities: dict[str, str] = {}
    current: str | None = None
    for path in sorted(_find_repo_root().glob("kb/*/*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            id_match = re.match(
                r"\s*-?\s*(?:id|instrument_id|document_id):\s*"
                r"([A-Za-z][A-Za-z0-9_]*_\d+_\d{4})\s*$",
                line,
            )
            if id_match:
                current = id_match.group(1)
                identities.setdefault(current, "")
                continue
            if current is None:
                continue
            identity = re.match(
                r"\s*(?:declared_identity|verified_identity):\s*\"?(.+?)\"?\s*$", line
            )
            if identity:
                identities[current] = (identities[current] + " " + identity.group(1)).strip()
    return identities


def find_spelling_divergences(
    script_ids: set[str], kb_identities: dict[str, str]
) -> dict[str, str]:
    """Script id -> KB id, for pairs that name ONE instrument two ways.

    Two conditions, and BOTH are required — the first alone over-matches:

    1. structural: same (number, year), and one family prefix is a
       case-insensitive prefix of the other (`Permen` of `Permenkumham`);
    2. evidential: the KB entry's own identity prose names the SCRIPT's
       qualified family, which is what proves it is the same instrument.

    Condition 1 alone is a false positive with a real example on disk:
    `PermenImipas_1_2026` (immigration, amends Permen Imipas 13/2025) and
    `Permen_1_2026` (tax, amends PMK 81/2024) share (1, 2026) and are
    prefix-related, and `kb/inventory/company.yaml` already records that this
    pair is NOT a two-way ministry collision. Condition 2 clears it: the tax
    entry declares no identity prose naming "PermenImipas".
    """
    divergences: dict[str, str] = {}
    for script_id in sorted(script_ids):
        script_parts = ID_PARTS.match(script_id)
        if not script_parts:
            continue
        script_family = script_parts.group(1)
        for kb_id, identity in sorted(kb_identities.items()):
            kb_parts = ID_PARTS.match(kb_id)
            if not kb_parts or kb_id == script_id:
                continue
            if kb_parts.group(2, 3) != script_parts.group(2, 3):
                continue
            kb_family = script_family.lower(), kb_parts.group(1).lower()
            shorter, longer = sorted(kb_family, key=len)
            if not longer.startswith(shorter):
                continue
            if script_family.lower() in identity.lower():
                divergences[script_id] = kb_id
    return divergences


def test_no_unreconciled_spelling_beyond_the_two_known_pairs():
    kb_identities = _kb_instrument_identities()
    script_ids = {entry["document_id"] for entry in LAWS_2026 if "document_id" in entry}
    assert find_spelling_divergences(script_ids, kb_identities) == KNOWN_UNRECONCILED_SPELLINGS, (
        "the set of instruments spelled one way by ingest_2026_laws.py and another "
        "way by the KB has MOVED. A new pair means a re-ingest would write a second "
        "document_id for an instrument that already has one — reconcile the spelling "
        "before ingesting. A pair that disappeared means it was reconciled: delete "
        "its row from KNOWN_UNRECONCILED_SPELLINGS in this file."
    )


def test_the_kb_side_actually_loaded():
    """Anti-vacuity: an empty KB map would make the test above pass forever."""
    kb_identities = _kb_instrument_identities()
    assert len(kb_identities) >= 20, f"only {len(kb_identities)} KB ids parsed — reader broke"
    assert any(identity for identity in kb_identities.values()), "no identity prose parsed at all"
    assert kb_identities.get("Permen_22_2023"), "the pinned instrument lost its identity prose"


def test_the_detector_catches_a_new_divergence():
    found = find_spelling_divergences(
        {"PermenX_9_2030"}, {"Permen_9_2030": "PermenX 9/2030 — Some Instrument"}
    )
    assert found == {"PermenX_9_2030": "Permen_9_2030"}


def test_the_detector_clears_two_different_instruments_sharing_a_number():
    """The live innocence case: prefix-related, same (number, year), NOT the same law."""
    found = find_spelling_divergences(
        {"PermenImipas_1_2026"}, {"Permen_1_2026": "amends PMK 81/2024, tax"}
    )
    assert found == {}


def test_the_detector_ignores_an_unrelated_family():
    found = find_spelling_divergences(
        {"PMK_55_2026"}, {"Perpres_55_2026": "PMK 55/2026 mentioned in prose"}
    )
    assert found == {}
