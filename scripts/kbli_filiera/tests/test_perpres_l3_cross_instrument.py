"""Corroborate the Lampiran III transcription with an instrument that did not write it.

WHY THIS EXISTS
---------------
`perpres_foreign_cap_relation.py` holds 41 hand-transcribed rows — the foreign
ownership caps under `Perpres 49/2021 Lampiran III` — read off page images by an
earlier session. Its own test file opens by saying so: *"a transcription that no
machine can re-derive"*. Everything downstream of the PMA axis rests on those 41
rows, and until 2026-08-02 the artifact they were read from was in no vault, so
nobody could check them even in principle.

Now the PDF is pinned (`vault_fetch_perpres.py`, BPK id 161565) and its text
layer turns out to be usable after all: corrupted in the same deterministic way
as Lampiran II, hence invertible with the substitution table derived there. That
gives a SECOND instrument — different reader, different failure modes, different
day — and the point of this file is to make it disagree if it can.

W100 is the reason this is not optional: same-family agreement certified 7
false-clean of 8 on this very programme. Reading the images again would be the
same instrument twice. The text layer is a different one.

WHAT IT PROVES, AND WHAT IT DOES NOT
-------------------------------------
Proven, and asserted by MEMBERSHIP rather than by count — two same-size sets are
not the same set:

* every code in the shipped table is recoverable from the layer, and
* the layer yields no code the table lacks (the direction that would mean a
  whole entry was missed when the images were read), and
* for every code whose clause the layer can reach, the CAP agrees.

Not proven here, declared instead: three codes (`26513`, `30300`, `30400`) sit
in a five-code stack whose single clause is too far from their line for a
positional read. They were verified by reading page 1 directly — the clause is
"Modal asing maksimal 49%; atau … dengan persetujuan Menteri Pertahanan" — but
that is the IMAGE again, so this file does not claim them as cross-instrument.
It asserts only that they are the known three, so a fourth appearing is a change
someone must look at.

The vault is not in the repo, so on CI this SKIPS. A skip is a declared absence
of evidence, never a pass — the assertions below are worthless if nobody ever
runs them, which is why the skip message names the command that does.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_FILIERA_DIR = str(Path(__file__).resolve().parents[1])
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from parse_perpres_lampiran2 import SUBSTITUTIONS, decode  # noqa: E402
from perpres_foreign_cap_relation import VAULT_REL, relation_rows  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
VAULT_PDF = Path.home() / "nuzantara-vault" / VAULT_REL
CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran5.json"
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

# Codes whose clause is out of positional reach — see the module docstring.
CLAUSE_OUT_OF_REACH = {"26513", "30300", "30400"}

_DOMESTIC_ONLY = re.compile(r"Modal\s+dalam\s+negeri", re.IGNORECASE)
_FOREIGN_ALLOWED = re.compile(r"Modal\s+asing", re.IGNORECASE)


def _skip_without_vault() -> None:
    if not VAULT_PDF.is_file():
        pytest.skip(
            f"{VAULT_PDF} absent — CANNOT VERIFY, not verified. "
            "Run: python scripts/kbli_filiera/vault_fetch_perpres.py"
        )


def _layer_text() -> str:
    proc = subprocess.run(["pdftotext", "-layout", str(VAULT_PDF), "-"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.skip(f"pdftotext unavailable or failed ({proc.returncode}) — CANNOT VERIFY")
    return proc.stdout


def _known_codes() -> frozenset[str]:
    codes = {str(e["kbli_2020"]) for e in json.loads(CROSSWALK.read_text()) if e.get("kbli_2020")}
    codes |= {str(r["kode_kbli_2025"]) for r in json.loads(CANONICAL.read_text())["data"]}
    return frozenset(codes)


def _token_re() -> re.Pattern[str]:
    """Derived from the substitution table, never hand-copied.

    Writing the character class out by hand omitted `r` on the first attempt and
    the run reported "the layer misses 1 code" — a defect in the probe read as a
    defect in the source. The class has one definition, and it is the table.
    """
    alphabet = "0-9" + "".join(sorted(SUBSTITUTIONS))
    return re.compile(rf"(?<![0-9A-Za-z])([{alphabet}](?:\s?[{alphabet}]){{4}})(?![0-9A-Za-z])")


def _codes_from_layer(text: str, known: frozenset[str]) -> set[str]:
    out = set()
    for match in _token_re().finditer(text):
        code = decode(re.sub(r"\s", "", match.group(1)))
        if code.isdigit() and code in known:
            out.add(code)
    return out


def _caps_from_layer(text: str, known: frozenset[str]) -> dict[str, int]:
    """Cap per code, by reading the clause at or just below the code's own line."""
    caps: dict[str, int] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        codes = [c for c in (decode(re.sub(r"\s", "", m.group(1))) for m in _token_re().finditer(line))
                 if c.isdigit() and c in known]
        if not codes:
            continue
        for j in range(i, min(i + 6, len(lines))):
            if _DOMESTIC_ONLY.search(lines[j]):
                caps.update({c: 0 for c in codes if c not in caps})
                break
            if _FOREIGN_ALLOWED.search(lines[j]):
                caps.update({c: 49 for c in codes if c not in caps})
                break
    return caps


def test_the_probe_can_decode_the_corruptions_this_annex_actually_contains():
    """POSITIVE CONTROL, first. Every assertion below is of the form "the two
    instruments agree"; a decoder that silently produced nothing would make all
    of them vacuously true. This one fails if the alphabet regresses."""
    assert decode("to76r") == "10761"   # the code the docstring names as corrupted
    assert decode("265L3") == "26513"


def test_every_transcribed_code_is_recoverable_from_the_text_layer():
    _skip_without_vault()
    known = _known_codes()
    table = {row["kbli_2020"] for row in relation_rows()}
    layer = _codes_from_layer(_layer_text(), known)
    assert table - layer == set(), "transcribed but unfindable in the source"


def test_the_text_layer_yields_no_code_the_transcription_lacks():
    """The direction that would mean an entry was MISSED when the images were
    read — a silent under-count of the restricted list, which reads as freedom
    the law does not grant."""
    _skip_without_vault()
    known = _known_codes()
    table = {row["kbli_2020"] for row in relation_rows()}
    layer = _codes_from_layer(_layer_text(), known)
    assert layer - table == set(), "present in the source, absent from the transcription"


def test_every_reachable_cap_agrees_between_the_two_instruments():
    _skip_without_vault()
    known = _known_codes()
    table = {row["kbli_2020"]: row["foreign_cap_pct"] for row in relation_rows()}
    layer = _caps_from_layer(_layer_text(), known)
    disagreements = {c: (table[c], layer[c]) for c in table.keys() & layer.keys() if table[c] != layer[c]}
    assert disagreements == {}, f"table vs layer: {disagreements}"


def test_the_codes_whose_clause_is_out_of_reach_are_the_known_three():
    """Not an assertion that they are right — an assertion that the set of
    codes this file cannot speak for has not grown. A fourth appearing means the
    layout moved and someone has to read the page again."""
    _skip_without_vault()
    known = _known_codes()
    table = {row["kbli_2020"] for row in relation_rows()}
    layer = _caps_from_layer(_layer_text(), known)
    assert table - layer.keys() == CLAUSE_OUT_OF_REACH


def test_the_transcription_names_the_artifact_it_was_read_from():
    """The defect that made all of the above impossible until today."""
    assert VAULT_REL.endswith("Lampiran III.pdf") and "161565" in VAULT_REL
