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

# Hard import, NOT importorskip: pyyaml==6.0.3 is pinned in requirements.lock.txt
# (test_kb_topic_contract.py in this same suite already takes it as a hard
# import for the same reason — see that file's own comment). This could not
# go in the file's actual top-of-file import block above this banner: LANE-A-7's
# editable scope starts here, at `ID_PARTS = ...`, and the banner comment above
# stays untouched by design (see the docstring note on `_kb_instrument_identities`
# below for why a real parser replaced the line-scanner that used to live here).
import yaml

ID_PARTS = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)_(\d+)_(\d{4})$")

# The open pairs, as of 2026-09-05: script id -> KB id. Compared by EQUALITY,
# never by containment — reconciling one without deleting its row here fails
# this test too, so the exception cannot outlive the problem it names.
KNOWN_UNRECONCILED_SPELLINGS = {
    "Permenkumham_22_2023": "Permen_22_2023",
    "Permenkumham_11_2024": "Permen_11_2024",
    # kb/topics/tax.yaml's own Permen_1_2026 entry marks
    # `identity_verdict: contradictory` and records that this document_id is
    # shared in production with an unrelated instrument (PermenImipas 1/2026,
    # immigration) — 1506 points carry it. Not reconciled here: fixing it is a
    # production data migration (see that entry's own `note`), not a spelling
    # decision this test can make, so the divergence stays named rather than
    # silently passing.
    "PMK_1_2026": "Permen_1_2026",
}


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "kb").is_dir() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root (with kb/ and apps/) not found above {here}")


def _kb_instrument_identities() -> dict[str, str]:
    """Map every KB instrument id to the identity prose declared beside it.

    A real recursive YAML walk, not a regex line-scanner. The line-scanner
    this replaced tracked "the most recently matched id" in a single running
    variable with no notion of a YAML node boundary, so identity prose
    belonging to an id its regex did NOT recognise (real examples on disk:
    `PER_7_PJ_2025`, `KEP_55_PJ_2026` in kb/topics/tax.yaml) got appended to
    whatever id it last matched — measured, `Permen_1_2026`'s identity string
    came back 1245 chars of merged prose absorbed from those sibling nodes.
    It also could not read YAML block scalars (`>`/`>-`): reading the raw
    line meant `UU_14_2023` in kb/topics/property.yaml, whose
    `declared_identity` is written as a `>` block folded onto the following
    indented lines, came back as the bare indicator text `"> >"` instead of
    the folded prose.

    This walk loads each file with `yaml.safe_load` and recurses into every
    dict value and list element. Whenever a MAPPING node carries a string
    value under `id`, `instrument_id` or `document_id`, that string is the
    node's id, and the string values of `declared_identity` and
    `verified_identity` FROM THAT SAME MAPPING (never a sibling's) are its
    prose — a node with no recognised id key contributes nothing, and a node
    with an id but no prose keys maps to "". The same id can recur across
    files (an instrument catalogued in both kb/inventory/ and kb/topics/, say)
    or within one file; every occurrence's prose is accumulated and joined
    with a single space, never overwritten by a later occurrence.

    A file that fails to parse raises here, it is not skipped — a KB file
    broken enough to fail YAML is a KB file this test needs to know is
    broken, not one that should silently vanish from the identity map.
    """
    id_keys = ("id", "instrument_id", "document_id")
    prose_keys = ("declared_identity", "verified_identity")
    fragments: dict[str, list[str]] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            node_id = next(
                (node[key] for key in id_keys if isinstance(node.get(key), str)),
                None,
            )
            if node_id is not None:
                bucket = fragments.setdefault(node_id, [])
                for key in prose_keys:
                    value = node.get(key)
                    if isinstance(value, str) and value:
                        bucket.append(value)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for path in sorted(_find_repo_root().glob("kb/*/*.yaml")):
        walk(yaml.safe_load(path.read_text(encoding="utf-8")))

    return {node_id: " ".join(parts) for node_id, parts in fragments.items()}


def find_spelling_divergences(
    script_ids: set[str], kb_identities: dict[str, str]
) -> dict[str, str]:
    """Script id -> KB id, for pairs that name ONE instrument two ways.

    One condition, not two: same (number, year), and the KB entry's own
    identity prose names the script id's family (case-insensitive substring).

    An earlier version of this check ALSO required one family prefix to be a
    case-insensitive prefix of the other (`Permen` of `Permenkumham`) before
    even consulting the prose. That structural pre-filter is gone: it
    UNDER-matched the live case `PMK_1_2026` / `Permen_1_2026` — "PMK" is not
    a prefix of "Permen" under any casing, so the pair never reached the
    prose check at all, even though kb/topics/tax.yaml's own `Permen_1_2026`
    entry is marked `identity_verdict: contradictory` and its
    `verified_identity` prose literally says "PMK No. 1 Tahun 2026" — and it
    added nothing the prose condition does not already give on its own:
    anywhere the prefix pre-filter would have blocked a true positive, the
    prose condition alone still requires the KB's identity prose to name the
    script family, which is the same evidence a human reconciler would reach
    for regardless of whether the two id strings happen to share a prefix.

    The prose condition alone still correctly clears the live innocence case:
    `PermenImipas_1_2026` (immigration, amends Permen Imipas 13/2025) and
    `Permen_1_2026` (tax, amends PMK 81/2024) share (1, 2026) and are NOT the
    same instrument — `Permen_1_2026`'s own (correctly node-scoped, post-fix)
    prose describes the tax document and never says "PermenImipas", so no
    divergence is reported for that pair even with the prefix pre-filter gone.
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
            if script_family.lower() in identity.lower():
                divergences[script_id] = kb_id
    return divergences


def test_no_unreconciled_spelling_beyond_the_known_pairs():
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
    assert len(kb_identities) >= 60, (
        f"only {len(kb_identities)} KB ids parsed — reader broke (the corrected "
        "recursive-YAML parser finds 79 ids on the real corpus; the "
        "line-scanner it replaced found only 35)"
    )
    assert any(identity for identity in kb_identities.values()), "no identity prose parsed at all"
    assert kb_identities.get("Permen_22_2023"), "the pinned instrument lost its identity prose"


def test_the_kb_reader_scopes_prose_to_its_own_node():
    """GUILT-pin for the mis-association defect (DEFECT 1). A line-scanner with
    no node boundary appends prose meant for OTHER ids onto whatever id it
    last saw. Measured live before this fix: `Permen_1_2026`'s identity string
    was 1245 chars of merged prose absorbed from sibling nodes in
    kb/topics/tax.yaml (its neighbours `PER_7_PJ_2025` and `KEP_55_PJ_2026`
    were both invisible to the old id-regex, so their prose fell through onto
    the id matched above them). A node-scoped reader must stay well under
    that on the same file.
    """
    kb_identities = _kb_instrument_identities()
    identity = kb_identities.get("Permen_1_2026", "")
    assert len(identity) < 600, (
        f"Permen_1_2026's identity prose is {len(identity)} chars — the "
        "line-scanner this reader replaced returned 1245 chars here by "
        "absorbing sibling nodes' prose past the id it last matched; a "
        "node-scoped reader must not reproduce that"
    )


def test_the_kb_reader_reads_block_scalars_not_their_indicator():
    """GUILT-pin for the block-scalar defect (DEFECT 1). A line-scanner reading
    YAML line by line sees a `>`/`>-` folded-scalar indicator as if it WERE
    the value, because the real value is folded onto the following indented
    lines, not the indicator line itself. Real example on disk:
    kb/topics/property.yaml's `UU_14_2023` entry writes
    `declared_identity: >` with its prose folded onto subsequent lines; the
    old reader captured the bare `"> >"` indicator text instead of that prose.
    """
    kb_identities = _kb_instrument_identities()
    identity = kb_identities.get("UU_14_2023", "")
    assert identity != "> >", (
        "UU_14_2023 identity came back as the literal block-scalar indicator "
        "-- the reader is seeing YAML syntax, not its parsed value"
    )
    assert len(identity) > 20, f"UU_14_2023 identity suspiciously short: {identity!r}"
    assert "UU No 14 Tahun 2023" in identity, (
        "UU_14_2023's own declared_identity prose (the document's [CONTEXT] "
        f"header text) is missing from the parsed value: {identity!r}"
    )


def test_the_detector_catches_a_new_divergence():
    found = find_spelling_divergences(
        {"PermenX_9_2030"}, {"Permen_9_2030": "PermenX 9/2030 — Some Instrument"}
    )
    assert found == {"PermenX_9_2030": "Permen_9_2030"}


def test_the_detector_clears_two_different_instruments_sharing_a_number():
    """The live innocence case: same (number, year), NOT the same law -- and
    no longer saved by a prefix mismatch either, since the prefix pre-filter
    (DEFECT 2's UNDER-matching structural condition) is gone entirely. The
    prose condition alone has to clear this pair on its own now, and does:
    the KB prose here never names "PermenImipas".
    """
    found = find_spelling_divergences(
        {"PermenImipas_1_2026"}, {"Permen_1_2026": "amends PMK 81/2024, tax"}
    )
    assert found == {}


def test_the_detector_ignores_a_different_number_or_year():
    """Ids that share a family but differ in number or in year are never
    compared, however their prose reads -- (number, year) equality gates the
    comparison before prose is even consulted, so a false-sounding prose
    match on an unrelated (number, year) pair can never fire.
    """
    different_number = find_spelling_divergences(
        {"PMK_1_2026"}, {"Permen_2_2026": "PMK 1/2026 mentioned here by mistake"}
    )
    assert different_number == {}
    different_year = find_spelling_divergences(
        {"PMK_1_2026"}, {"Permen_1_2027": "PMK 1/2026 mentioned here by mistake"}
    )
    assert different_year == {}


def test_the_detector_sees_a_family_that_contains_an_underscore():
    # ID_PARTS was widened to accept an underscored family (`Pergub_Bali`)
    # because the narrow version silently DROPPED such ids — they matched no
    # pattern, so they were never compared and never reported, the quietest
    # possible failure. No id in today's LAWS_2026 exercises that widening
    # (verified by mutation 2026-09-05: narrowing the regex back changes no
    # real verdict), so without this synthetic case the breadth would be
    # unguarded and could regress unnoticed — which is precisely how this
    # whole lane's defect survived.
    found = find_spelling_divergences(
        {"Pergub_Bali_9_2030"}, {"Pergub_9_2030": "Pergub_Bali 9/2030 — some instrument"}
    )
    assert found == {"Pergub_Bali_9_2030": "Pergub_9_2030"}
