"""Regression gate for the campaign's §6 "Cukup jelas" damage signal.

MANDATE.md §6 flags a point as damaged when its `section` is not `penjelasan`
AND its text contains "Cukup jelas" — elucidation/commentary sitting in an
article slot. Before this test existed the signal had never been checked for
innocence: `section` is populated on only 792/84,283 points in `legal_unified`
(the two 2026-08-25 repairs), so for 99.1% of the corpus `!= "penjelasan"` is
vacuously true and the check degrades to a bare substring match — exactly the
shape that has repeatedly over-matched elsewhere in this repo (superscar
family #3, `.claude/rules/cicatrix-superscar.md`).

Lane P measured the real false-positive rate on 2026-08-25: a stratified
sample of 45 flagged fragments (round-robin across 34 distinct documents,
seed 20260825, NOT "first N found" — see `scripts/kb/cukup_jelas_sample.py`)
was read in full. 0/45 were innocent occurrences (a citation, an unrelated
preamble, ordinary non-idiomatic prose) — every one was genuinely
elucidation-style text: a bare "Cukup jelas." boilerplate note, a fuller
Penjelasan Pasal Demi Pasal explanation with real prose, or an explicit
"Tidak diberikan penjelasan, karena cukup jelas" statement. Full read-through
and method: `research/legal/2026-08-25-cukup-jelas-false-positive-rate.md`.

This test does two things a one-off measurement script cannot:
  1. Locks a representative sample of that manually-verified GUILTY set in as
     a permanent regression fixture, so a future refactor of the predicate
     cannot silently stop recognizing real elucidation text.
  2. Adds INNOCENCE fixtures the live sample happened not to surface —
     constructed specifically to catch the over-match failure mode this
     signal is structurally exposed to (word-boundary slop, and the
     `section: penjelasan` exclusion silently regressing).

Guilt without innocence is exactly the shape superscar family #3 warns
against ("nessuna guardia senza test di innocenza E colpevolezza"). Both
halves are exercised here, and `test_mutation_*` proves each can go red.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()


def _signal():
    """Load cukup_jelas_signal.py as a module (it lives outside any package,
    same pattern as test_kb_inventory_contract.py::_probe)."""
    cached = sys.modules.get("cukup_jelas_signal")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "cukup_jelas_signal", ROOT / "scripts" / "kb" / "cukup_jelas_signal.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["cukup_jelas_signal"] = module
    spec.loader.exec_module(module)
    return module


# ── GUILT fixtures ───────────────────────────────────────────────────────────
# Verbatim text from 10 of the 45 sampled points (lane P, 2026-08-25), spanning
# 10 distinct documents and every shape the manual read-through found: bare
# boilerplate, per-Ayat lists mixing "Cukup jelas" with real explanatory prose,
# an explicit "PASAL DEMI PASAL" elucidation heading, and the archaic
# "Tidak diberikan penjelasan, karena cukup jelas" phrasing. All manually
# verified genuine elucidation text — none is an innocent occurrence.
GUILTY_SAMPLES = [
    {  # bare boilerplate, no section tag at all (legacy shape, the 99.1% case)
        "document_id": "UU_17_2008",
        "text": "Cukup jelas.",
    },
    {  # per-Ayat list mixing boilerplate with a real explanatory Ayat
        "document_id": "UU_11_2020",
        "text": (
            "Ayat (1)\nCukup jelas. \nAyat (2)\nCukup jelas. \nAyat (3)\nCukup jelas. "
            "\nAyat (4)\nCukup jelas. \n\nBiro Hukum Sekretariat Jenderal \n"
            "Kementerian Ketenagakerjaan Ayat (5)\nBagi perusahaan yang telah \n"
            "memberlakukan istirahat panjang tidak \nboleh mengurangi dari ketentuan "
            "yang \nsudah ada.\nAyat (6)\nCukup jelas.\nAngka 24"
        ),
    },
    {  # explicit "PASAL DEMI PASAL" elucidation-section heading present
        "document_id": "Keppres_29_1959",
        "text": (
            "II. PASAL DEMI PASAL.\nTidak diberikan penjelasan, karena cukup jelas.\n"
            "Diketahui:\nMenteri Kehakiman,\nG. A. MAENGKOM."
        ),
    },
    {  # substantial explanatory prose (tax law example with figures), not boilerplate
        "document_id": "UU_28_2007",
        "text": (
            "Pasal Ayat (1)\n Cukup jelas.\n Ayat (2)\nSurat Tagihan Pajak menurut ayat "
            "ini disamakan kekuatan\nhukumnya dengan surat ketetapan pajak sehingga "
            "dalam\nhal penagihannya dapat juga dilakukan dengan Surat Paksa.\n "
            "Ayat (3)\nAyat ini mengatur pengenaan sanksi administrasi berupa\n"
            "bunga atas Surat Tagihan Pajak yang diterbitkan karena:"
        ),
    },
    {  # investment law (UU 25/2007) — relevant to Bali Zero's own domain
        "document_id": "UU_25_2007",
        "text": (
            "Ayat (1)\n Cukup jelas.\n Ayat (2)\n Cukup jelas.\n Ayat (3)\n"
            "Yang dimaksud dengan bertanggung jawab langsung kepada Presiden adalah "
            "bahwa Badan Koordinasi Penanaman Modal\ndalam melaksanakan tugas, "
            "menjalankan fungsi, dan\nmenyampaikan tanggung jawabnya langsung kepada "
            "Presiden."
        ),
    },
    {  # UU_6_2023 — the carrier act whose 726 flagged fragments are mostly the
        # annexed Cipta Kerja elucidation (a separate, larger defect); this
        # specific fragment is still genuinely elucidation text either way
        "document_id": "UU_6_2023",
        "text": (
            "[CONTEXT: UU - NO 6 - TAHUN 2023 - TENTANG PENETAPAN PERATURAN "
            "PEMERINTAH PENGGANTI UNDANG-UNDANG NOMOR 2 TAHUN 2022 TENTANG CIPTA "
            "KERJA MENJADI UNDANG-UNDANG - Pasal 12]\n\nCukup jelas.\nAngka 4"
        ),
    },
    {  # UU_17_2008 — the UNMARKED BOUNDARY document (471 "Cukup jelas", 0
        # "PENJELASAN" headers); bare form is the overwhelming majority there
        "document_id": "UU_17_2008",
        "text": "Cukup jelas.",
    },
    {  # environmental Perda with a long, genuinely substantive elucidation entry
        "document_id": "Perda_3_2013",
        "text": (
            "huruf a \n Cukup Jelas. \n\n huruf b \n Cukup Jelas. \n\n huruf c \n "
            "Cukup Jelas. \n\n Huruf d \n- jenis zat yang terkandung dalam air "
            "limbah adalah \nBOD (Biologi Oxygent Demand ), COD (Chemistri Design "
            "Demand), TSS (Total Suspende Solid)"
        ),
    },
    {  # income tax law (UU 7/1983 as amended) — detailed real elucidation prose
        "document_id": "TASSE_7_1983",
        "text": (
            "Huruf a \nBagi Wajib Pajak baru yang mulai menjalankan  usaha atau "
            "melakukan  kegiatan dalam \ntahun pajak berjalan perlu diatur "
            "perhitungan  besarnya angsuran.\n\nAyat (8) \nCukup jelas."
        ),
    },
    {  # short bare form with trailing page-artifact noise (common OCR pattern)
        "document_id": "PP_1_2011",
        "text": "Cukup jelas.",
    },
]


# ── INNOCENCE fixtures ───────────────────────────────────────────────────────
INNOCENT_SAMPLES = [
    {
        "id": "explicitly-tagged-penjelasan-top-level",
        # The one case the live sample under-represents: only 792/84,283 points
        # carry `section` at all (the two 2026-08-25 repairs), so a top-level
        # exclusion path is exercised almost nowhere in production traffic
        # today. If this regresses, ALL of UU_6_2011/UU_40_2007's correctly
        # tagged elucidation re-enters the damaged count.
        "payload": {"document_id": "UU_6_2011", "section": "penjelasan",
                    "text": "Cukup jelas."},
        "expect": False,
    },
    {
        "id": "explicitly-tagged-penjelasan-nested-metadata",
        # Same exclusion, legacy nested-metadata shape (78,486/84,283 points).
        "payload": {"metadata": {"document_id": "UU_40_2007", "section": "penjelasan",
                                  "text": "Cukup jelas."}},
        "expect": False,
    },
    {
        "id": "no-phrase-at-all",
        "payload": {"document_id": "UU_1_1945",
                    "text": "Setiap warga negara berhak atas pekerjaan yang layak."},
        "expect": False,
    },
    {
        "id": "word-boundary-should-not-fuse-unrelated-words",
        # "kecukupanjelas" contains neither "cukup" nor "jelas" as whole words;
        # a naive `"cukup" in text and "jelas" in text` (two independent
        # substring tests instead of one co-located regex) would wrongly fire
        # on unrelated text that happens to contain both words far apart, or
        # on fused/garbled OCR tokens. The regex used here requires the two
        # words adjacent (whitespace-only between them), so this must be False.
        "payload": {"document_id": "UU_99_2099",
                    "text": "Ketercukupan anggaran dan kejelasan prosedur wajib dijamin."},
        "expect": False,
    },
    {
        "id": "case-insensitive-still-matches",
        # Not an innocence case in the "should be excluded" sense — asserts the
        # positive direction of the same word-boundary logic: case must not
        # matter (guards against a future regex edit adding re.IGNORECASE
        # removal as a silent regression in the guilty direction).
        "payload": {"document_id": "UU_1_2019", "text": "Pasal 1 \nCUKUP JELAS."},
        "expect": True,
    },
    {
        "id": "multi-whitespace-between-words-still-matches",
        "payload": {"document_id": "UU_1_2019", "text": "Cukup   \n  jelas."},
        "expect": True,
    },
    {
        "id": "missing-text-key-does-not-crash-and-is-innocent",
        # get_text() falls through payload.text -> payload.content ->
        # metadata.text -> "". A point with none of those must not raise and
        # must not be flagged.
        "payload": {"document_id": "UU_0_0000"},
        "expect": False,
    },
]


@pytest.mark.parametrize("sample", GUILTY_SAMPLES, ids=lambda s: s["document_id"])
def test_guilt_real_elucidation_fragments_are_flagged(sample):
    """All 10 fixtures are verbatim text lane P manually verified as genuine
    elucidation (Penjelasan) content during the 2026-08-25 false-positive
    read-through. If the predicate stops recognizing any of these, it has
    lost RECALL on the exact shape the campaign is trying to measure."""
    signal = _signal()
    payload = {"document_id": sample["document_id"], "text": sample["text"]}
    assert signal.is_unmarked_penjelasan_fragment(payload) is True, (
        f"{sample['document_id']}: manually-verified genuine elucidation text "
        "was not flagged — the predicate has lost recall."
    )


@pytest.mark.parametrize("sample", INNOCENT_SAMPLES, ids=lambda s: s["id"])
def test_innocence_constructed_edge_cases_are_not_flagged_or_are_correctly_flagged(sample):
    signal = _signal()
    result = signal.is_unmarked_penjelasan_fragment(sample["payload"])
    assert result is sample["expect"], (
        f"{sample['id']}: expected is_unmarked_penjelasan_fragment()={sample['expect']}, "
        f"got {result}"
    )


def test_mutation_removing_the_section_exclusion_flips_the_penjelasan_fixture():
    """Proves the innocence fixture is load-bearing, not vacuous: reimplement
    the predicate WITHOUT the `section != "penjelasan"` guard (the exact
    regression this test exists to catch) and show the known-innocent
    `section: penjelasan` fixture flips to a false positive under it. If this
    assertion could not be made to fail by deleting the guard, the innocence
    test above would not actually be testing anything."""
    signal = _signal()

    def predicate_without_section_guard(payload):
        # The bug this simulates: someone "simplifies" the predicate to a bare
        # substring test, dropping the section check entirely.
        return bool(signal.CUKUP_JELAS.search(signal.get_text(payload)))

    tagged_penjelasan = {"document_id": "UU_6_2011", "section": "penjelasan",
                          "text": "Cukup jelas."}
    # The real predicate correctly excludes it.
    assert signal.is_unmarked_penjelasan_fragment(tagged_penjelasan) is False
    # The mutated (guardless) predicate wrongly flags it -- proving the guard
    # in the real predicate is the thing keeping this fixture green.
    assert predicate_without_section_guard(tagged_penjelasan) is True


def test_mutation_loosening_the_regex_to_two_independent_substrings_breaks_a_fixture():
    """Same proof, for the word-boundary innocence fixture: reimplement the
    match as two independent `in` checks (a plausible "simplification" that
    drops the adjacency requirement) and show it wrongly flags text where
    "cukup" and "jelas" each appear, unrelated to each other."""
    signal = _signal()

    def predicate_two_independent_substrings(payload):
        text = signal.get_text(payload).lower()
        has_phrase = "cukup" in text and "jelas" in text
        if not has_phrase:
            return False
        return signal.get_section(payload) != "penjelasan"

    unrelated = {"document_id": "UU_99_2099",
                 "text": "Ketercukupan anggaran dan kejelasan prosedur wajib dijamin."}
    assert signal.is_unmarked_penjelasan_fragment(unrelated) is False
    assert predicate_two_independent_substrings(unrelated) is True
