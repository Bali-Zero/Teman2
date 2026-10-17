"""PricingService.search_service matches WORDS and keyword PHRASES, not substrings.

Spec: docs/specs/2026-10-17-pricing-search-token-matching-spec.md. The corpus in
``data/search_corpus_1017.json`` runs against the real 2026 catalogue in both directions
(rows that must be found, rows that must not).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data" / "search_corpus_1017.json"
CORPUS = json.loads(DATA.read_text(encoding="utf-8"))
GROUPS = CORPUS["groups"]


def _expand(names: list[str]) -> set[str]:
    out: set[str] = set()
    for name in names:
        out.update(GROUPS.get(name, [name]))
    return out


@pytest.fixture(scope="module")
def pricing_service():
    # search_service appends the client-facing contact trailer, which imports app settings.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("JWT_SECRET_KEY", "x" * 40)
        mp.setenv("API_KEYS", "test-key-for-pricing-search")
        from backend.services.pricing.pricing_service import PricingService

        service = PricingService()
        assert service.loaded
        yield service


def _row_keys(service) -> set[str]:
    keys: set[str] = set()
    for category, rows in service.prices["services"].items():
        blocks = rows.values() if category == "tax_accounting" else [rows]
        for block in blocks:
            if isinstance(block, dict):
                keys.update(k for k, v in block.items() if isinstance(v, dict))
    return keys


def _hit_keys(result: dict) -> set[str]:
    hits: set[str] = set()
    for rows in result.get("results", {}).values():
        hits.update(rows)
    return hits


def test_corpus_is_wide_and_names_only_real_rows(pricing_service):
    queries = CORPUS["queries"]
    assert len(queries) >= 60
    real = _row_keys(pricing_service)
    named = set()
    for entry in queries:
        named |= _expand(entry.get("must_find", []) + entry.get("must_not_find", []))
    assert named <= real, sorted(named - real)


@pytest.mark.parametrize("entry", CORPUS["queries"], ids=lambda e: e["query"])
def test_corpus_query(pricing_service, entry):
    hits = _hit_keys(pricing_service.search_service(entry["query"]))
    missing = _expand(entry.get("must_find", [])) - hits
    forbidden = _expand(entry.get("must_not_find", [])) & hits
    assert not missing, f"rows lost: {sorted(missing)}"
    assert not forbidden, f"rows that must not match: {sorted(forbidden)}"
    if entry.get("expect_no_hits"):
        assert not hits, sorted(hits)


# --- matcher units: guilt AND innocence --------------------------------------------------


@pytest.fixture(scope="module")
def m():
    from backend.services.pricing import pricing_service as mod

    return mod


def _count(m, query: str, text: list, keywords=None) -> int:
    tokens = m._words(query)
    terms = [t for t in tokens if t not in m._SEARCH_NOISE_WORDS and len(t) > 1]
    return m._count_search_matches(terms, tokens, text, keywords or [])


@pytest.mark.parametrize(
    ("token", "text"),
    [
        ("kitas", "Working KITAS (Offshore)"),  # exact word
        ("visa", "Tourist visas"),  # >= 4 chars: prefix
        ("e33", "E33G Remote Worker"),  # digit: prefix of a code
        ("c1", "C10 Speaker Visa"),
        ("pt", "New Company (PT PMA)"),  # short but equal to a word
        ("c7a", "C7A,B,C — Music/Art"),  # punctuation separates words
    ],
)
def test_token_matches_a_word(m, token, text):
    assert _count(m, token, [text]) == 1


@pytest.mark.parametrize(
    ("token", "text"),
    [
        ("ke", "keras"),  # 2-char token is not a prefix
        ("mi", "miras"),
        ("man", "minuman"),  # 3 chars, no digit: exact only
        ("ber", "beralkohol"),
        ("tax", "Coretax Activation"),  # never a substring
        ("erp", "Investor KITAP + MERP"),
        ("kerja", "ketenagakerjaan"),
    ],
)
def test_token_does_not_match_inside_a_word(m, token, text):
    assert _count(m, token, [text]) == 0


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("izin minuman beralkohol", 1),
        ("harga izin minuman beralkohol", 1),
        ("harga miras", 1),
        ("minuman ringan", 0),  # shares one word with the phrase: not a match
        ("izin usaha minuman ringan", 0),
        ("izin", 0),
        ("beralkohol", 0),  # a fragment of the phrase is not the phrase
    ],
)
def test_keyword_phrase_must_be_contained_in_the_query(m, query, expected):
    keywords = ["minuman beralkohol", "miras"]
    assert (_count(m, query, ["Alcohol License"], keywords) > 0) == bool(expected)


def test_keyword_words_do_not_leak_into_descriptive_matching(m):
    # "ringan" appears only inside a keyword phrase: not descriptive text.
    assert _count(m, "ringan", ["Other"], ["minuman ringan"]) == 0


def test_keyword_phrase_credits_its_terms_once(m):
    assert _count(m, "minuman keras", ["Alcohol License"], ["minuman keras"]) == 2


def test_all_noise_query_is_matched_as_a_whole_phrase(m):
    tokens = m._words("how much")
    assert m._count_search_matches(tokens, tokens, ["how much"], [], True) == 1
    assert m._count_search_matches(tokens, tokens, ["how long, so much"], [], True) == 0
    assert m._count_search_matches(["bali"], ["bali"], ["Bali tour"], [], True) == 1


def test_legacy_list_shape_uses_the_same_matcher(pricing_service):
    legacy = type(pricing_service).__new__(type(pricing_service))
    legacy.loaded = True
    legacy.prices = {
        "services": {
            "visa": [
                {"code": "C1", "name": "Tourist", "keywords": ["minuman beralkohol"]},
                {"code": "KE9", "name": "Keras thing"},
            ]
        }
    }
    res = legacy.search_service("izin minuman ringan")
    assert "results" not in res
    res = legacy.search_service("izin minuman beralkohol")
    assert [r["code"] for r in res["results"]["visa"]] == ["C1"]
    assert "results" not in legacy.search_service("ke")
