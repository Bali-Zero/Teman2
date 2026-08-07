"""The hardcoded KBLI fallback may not contradict the catalogue.

`kbli_notebook_chat.KNOWN_KBLI_CODES` is a hand-written dict used when a code
lookup misses BOTH PostgreSQL and Qdrant, and it is also injected by an
activity-keyword map. Whatever it says goes straight into the LLM context that
answers on WhatsApp and web chat — so it is a second, unversioned source of
truth sitting in front of the cured one.

It had drifted, in the two ways this shape always drifts:

1. **A code the catalogue does not have.** `47911` is a KBLI *2020* code,
   retired in 2025. Being absent from the catalogue, it misses both stores by
   construction — so the hardcoded dict was its ONLY possible answer, with no
   retrieval able to correct it. It was reached by the e-commerce keyword row
   ("online shop", "toko online", "jual online", ...), i.e. one of the most
   common questions a client asks, and it asserted `TERBATAS` where the 2025
   successor `47901` is `TERBUKA`. A restriction invented out of nothing, in
   the direction that refuses a lawful investment.
2. **A value that disagrees with the record.** `56290` said `TERBATAS`; the
   catalogue says `TERBUKA`, max foreign 100%.

These tests are the structural guard, not a spot fix: any future entry that
names an unknown code, or that states a PMA status the catalogue contradicts,
fails here before it can reach a client.
"""

import json
import re
from pathlib import Path

import pytest

from backend.app.routers import kbli_notebook_chat

# backend/tests/unit/routers/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[6]
DATASET = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
ROUTER_SOURCE = Path(kbli_notebook_chat.__file__)


@pytest.fixture(scope="module")
def catalogue() -> dict[str, dict]:
    assert DATASET.exists(), f"canonical KBLI dataset missing at {DATASET}"
    raw = json.loads(DATASET.read_text())
    records = raw["data"] if isinstance(raw, dict) else raw
    assert records, "catalogue loaded empty"
    return {r["kode_kbli_2025"]: r for r in records}


def test_every_hardcoded_code_exists_in_the_catalogue(catalogue: dict[str, dict]) -> None:
    """A code the catalogue lacks can never be corrected by retrieval."""
    unknown = sorted(c for c in kbli_notebook_chat.KNOWN_KBLI_CODES if c not in catalogue)
    assert unknown == [], (
        f"hardcoded fallback names code(s) absent from KBLI 2025: {unknown}. "
        "Such a code misses PostgreSQL and Qdrant by construction, so this dict "
        "becomes its only answer — check the crosswalk for the real successor."
    )


def test_no_hardcoded_pma_status_contradicts_the_catalogue(catalogue: dict[str, dict]) -> None:
    conflicts = [
        (code, entry["pma_status"], catalogue[code].get("pma_status"))
        for code, entry in kbli_notebook_chat.KNOWN_KBLI_CODES.items()
        if code in catalogue and entry["pma_status"] != catalogue[code].get("pma_status")
    ]
    assert conflicts == [], f"hardcoded PMA status disagrees with the catalogue: {conflicts}"


def test_the_retired_2020_ecommerce_code_is_gone(catalogue: dict[str, dict]) -> None:
    """Pin the specific defect: 47911 must not come back."""
    assert "47911" not in catalogue, "premise: 47911 is a 2020 code, absent from 2025"
    assert "47911" not in kbli_notebook_chat.KNOWN_KBLI_CODES
    assert "47901" in kbli_notebook_chat.KNOWN_KBLI_CODES, "the real successor must be present"
    assert kbli_notebook_chat.KNOWN_KBLI_CODES["47901"]["pma_status"] == "TERBUKA"


def test_ecommerce_keywords_still_resolve(catalogue: dict[str, dict]) -> None:
    """INNOCENCE: the row must be repointed, not silently deleted.

    Dropping it would leave the most common question with no injected code at
    all — a different failure, not a fix.
    """
    source = ROUTER_SOURCE.read_text()
    block = re.search(
        r'"online shop".*?\]\s*,\s*\n\s*"(\d{5})"',
        source,
        re.DOTALL,
    )
    assert block, "the e-commerce keyword row disappeared"
    target = block.group(1)
    assert target in catalogue, f"e-commerce keywords point at {target}, absent from the catalogue"
    assert target in kbli_notebook_chat.KNOWN_KBLI_CODES, (
        f"{target} is not in KNOWN_KBLI_CODES, so the injection guard skips it silently"
    )


def test_every_keyword_target_is_a_real_code(catalogue: dict[str, dict]) -> None:
    """Whole-map sweep: no row may aim at a code the catalogue lacks."""
    source = ROUTER_SOURCE.read_text()
    body = source.split("_activity_keyword_map", 1)[1]
    body = body.split("if not direct_kbli_match", 1)[0]
    targets = sorted(set(re.findall(r'^\s*"(\d{5})",\s*$', body, re.MULTILINE)))
    assert targets, "no keyword targets parsed — the map's shape changed, fix this test"
    unknown = [t for t in targets if t not in catalogue]
    assert unknown == [], f"keyword map aims at code(s) absent from KBLI 2025: {unknown}"


def test_no_prompt_constant_teaches_a_code_the_catalogue_lacks(catalogue: dict[str, dict]) -> None:
    """The MASTER PROMPT is a third copy of these facts, and it is the one the LLM reads.

    The first version of this guard checked `KNOWN_KBLI_CODES` and the keyword
    map and declared the e-commerce defect cured. It was not: the module's
    prompt constants independently carried ``- 47911 = ... PMA: TERBATAS`` in
    the "KNOWN KBLI CODES" block and named 47911 again as the e-commerce
    mapping and as the pass-through example. Fixing the dict while the prompt
    still taught the retired code left the channel able to emit it — a cure
    closed on three surfaces that still lied on the fourth.

    A mention is GUILTY only when the line presents the code as real. A line
    that names a code in order to retire it ("does NOT exist in KBLI 2025") is
    innocent — that sentence is the cure, not the defect.
    """
    source = ROUTER_SOURCE.read_text()
    RETIREMENT_MARKERS = ("does NOT exist", "never cite it", "retired in 2025")

    offenders: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if any(marker in line for marker in RETIREMENT_MARKERS):
            continue  # INNOCENCE: the line exists to disown the code
        cited = set(re.findall(r"KBLI (\d{5})", line)) | set(
            re.findall(r'"-\s*(\d{5})\s*=', line)
        )
        for code in sorted(cited):
            if code not in catalogue:
                offenders.append((lineno, code, line.strip()[:90]))

    assert offenders == [], (
        "prompt text cites KBLI code(s) absent from the 2025 catalogue — the LLM "
        f"is being taught they exist: {offenders}"
    )


def test_the_online_channel_answer_names_the_fork(catalogue: dict[str, dict]) -> None:
    """47901 is the marketplace OPERATOR; selling your own goods is the product code.

    Replacing one false certainty with another would be the same mistake wearing
    a correct code, so the description must carry the fork.
    """
    description = kbli_notebook_chat.KNOWN_KBLI_CODES["47901"]["description"]
    assert "47221" in description, "the restricted-category caveat must survive"
    assert "PRODUCT CATEGORY" in description.upper()


# --------------------------------------------------------------------------
# The SIXTH surface: the prose beside the field
# --------------------------------------------------------------------------


def _openness_claims(description: str) -> list[str]:
    """Sentences of a hardcoded description that assert foreign openness.

    Sentence-scoped and affirmative-only, for the reason the sibling detector
    in `scripts/kbli_filiera/editorial_record_conformance.py` learned the hard
    way: a proximity match convicts "this is NOT open to foreign ownership",
    which is the correct sentence to write. A clause that RESERVES the activity
    is likewise innocent — "reserved for Koperasi and UMKM ... 0%" contains
    neither an openness claim nor a lie.
    """
    sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", description) if s.strip()]
    return [
        s
        for s in sentences
        if re.search(r"TERBUKA|100\s*%|open to foreign", s, re.I)
        and not re.search(r"\bnot\b|\bno\b|cannot|never|reserved", s, re.I)
    ]


def test_no_hardcoded_description_asserts_openness_the_catalogue_denies(
    catalogue: dict[str, dict],
) -> None:
    """The field and the prose are TWO assertions, and only one was guarded.

    `test_no_hardcoded_pma_status_contradicts_the_catalogue` compares
    `entry["pma_status"]` and stops there. But the whole entry — description
    included — is injected verbatim into the LLM context that answers on
    WhatsApp and web chat, so a description reading "PMA: TERBUKA (open to
    foreigners, 100%)" reaches a client exactly as the field would.

    Found live: the UMKM split-heir cure moved `96100` (laundry) to TERBATAS at
    a 0% ceiling, the field test went red and was fixed, and the description
    kept its own sentence promising 100%. Correcting the field alone would have
    left the guarded copy right and the unguarded copy wrong — the shape this
    file's fourth test already names, one surface further out.
    """
    offenders = [
        (code, claim)
        for code, entry in kbli_notebook_chat.KNOWN_KBLI_CODES.items()
        if code in catalogue
        and isinstance(catalogue[code].get("pma_max_asing"), int)
        and catalogue[code]["pma_max_asing"] < 100
        for claim in _openness_claims(str(entry.get("description") or ""))
    ]
    assert offenders == [], (
        "hardcoded description promises foreign openness on a code the catalogue "
        f"caps below 100%: {offenders}"
    )


def test_guilt_the_prose_guard_catches_the_defect_that_created_it() -> None:
    """The exact sentence `96100` carried before the UMKM cure."""
    assert _openness_claims(
        "Laundry and dry cleaning services. PMA: TERBUKA (open to foreigners, 100%). "
        "Risk level is SCALE-DEPENDENT."
    ) == ["PMA: TERBUKA (open to foreigners, 100%)."]


def test_innocence_a_reservation_sentence_is_not_an_openness_claim() -> None:
    """What replaced it. Naming the 0% ceiling must not read as promising 100%."""
    assert (
        _openness_claims(
            "Laundry and dry cleaning services. PMA: reserved for Koperasi and UMKM "
            "(Perpres 49/2021 Lampiran II) — maximum foreign ownership 0%, a PT PMA "
            "cannot take this bidang usaha."
        )
        == []
    )


def test_innocence_an_open_code_may_still_say_it_is_open(catalogue: dict[str, dict]) -> None:
    """A guard that forbade the words would force every honest page to lie by omission."""
    assert _openness_claims("Sale of goods. PMA: TERBUKA (open to foreigners, 100%).") != []
    open_codes = [
        c
        for c in kbli_notebook_chat.KNOWN_KBLI_CODES
        if c in catalogue and catalogue[c].get("pma_max_asing") == 100
    ]
    assert open_codes, "premise: some hardcoded codes are genuinely 100% open"
