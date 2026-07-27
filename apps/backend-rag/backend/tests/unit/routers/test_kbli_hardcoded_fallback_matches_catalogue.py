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


def test_the_online_channel_answer_names_the_fork(catalogue: dict[str, dict]) -> None:
    """47901 is the marketplace OPERATOR; selling your own goods is the product code.

    Replacing one false certainty with another would be the same mistake wearing
    a correct code, so the description must carry the fork.
    """
    description = kbli_notebook_chat.KNOWN_KBLI_CODES["47901"]["description"]
    assert "47221" in description, "the restricted-category caveat must survive"
    assert "PRODUCT CATEGORY" in description.upper()
