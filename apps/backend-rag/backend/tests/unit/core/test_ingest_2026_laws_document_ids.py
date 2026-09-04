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
