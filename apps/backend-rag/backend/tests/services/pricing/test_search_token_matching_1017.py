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
        ("kitas", "Working KITAS (Offshore)"),  # equal to a word
        ("visa", "Tourist visas"),  # prefix, 4+ chars
        ("kit", "Working KITAS"),  # prefix, 3 chars
        ("ext", "Visa on Arrival Extension"),
        ("e33", "E33G Remote Worker"),  # digit: prefix of a code
        ("c1", "C10 Speaker Visa"),  # 2 chars but a digit
        ("pt", "New Company (PT PMA)"),  # short but equal to a word
        ("c7a", "C7A,B,C — Music/Art"),  # punctuation separates words
        ("kitasnya", "Working KITAS"),  # light suffix: word (4+) prefixes the token
        ("visas", "Tourist visa"),
        ("alcoholic", "Alcohol License"),
        ("polisi", "Surat Keterangan Catatan Kepolisian"),  # 5+ chars inside a word
        ("sehat", "BPJS Kesehatan"),
        ("igiene", "Sertifikat Laik Higiene Sanitasi"),
        ("kerja", "Cancel Ketenagakerjaan"),
    ],
)
def test_token_matches_a_word(m, token, text):
    assert _count(m, token, [text]) == 1


@pytest.mark.parametrize(
    ("token", "text"),
    [
        ("ke", "keras"),  # 2-char token: whole words only
        ("mi", "miras"),
        ("as", "alas"),
        ("ma", "minuman"),
        ("tax", "Coretax Activation"),  # 3 chars: prefix, never inside
        ("erp", "Investor KITAP + MERP"),
        ("ber", "ibu"),
        ("ika", "Kepolisian"),  # 3 chars inside a word
        ("kit", "Akit"),
        ("sip", "Ketentuan"),
        ("visa", "visit"),
        ("kesehatan", "Sehat"),  # a SHORTER row word 'sehat' is not a prefix of it
    ],
)
def test_token_does_not_match_where_no_clause_applies(m, token, text):
    assert _count(m, token, [text]) == 0


@pytest.mark.parametrize(
    ("token", "text", "expected"),
    [
        ("kitasnya", "KITAS", 1),
        ("visas", "visa", 1),
        ("alcoholic", "Alcohol", 1),
        ("pensionati", "pension", 1),
        ("working", "work", 1),  # ing is a light suffix; 'work' as a word is legitimate
        ("freelance", "Visa-Free", 0),  # 'lance' is not a light suffix
        ("coretax", "core", 0),
        ("internship", "intern", 0),
        ("kitasxyz", "KITAS", 0),
        ("kitaszz", "KITAS", 0),
    ],
)
def test_word_prefix_of_token_needs_a_light_suffix(m, token, text, expected):
    assert _count(m, token, [text]) == expected


def test_light_suffixes_are_a_small_closed_set(m):
    assert {"nya", "an", "s", "ing", "ati"} <= m._LIGHT_SUFFIXES
    assert "" not in m._LIGHT_SUFFIXES
    assert len(m._LIGHT_SUFFIXES) <= 20


def test_inside_word_needs_five_characters(m):
    assert _count(m, "olis", ["Kepolisian"]) == 0  # 4 chars inside
    assert _count(m, "polis", ["Kepolisian"]) == 1  # 5 chars inside


def test_word_prefix_of_token_needs_a_four_character_word(m):
    assert _count(m, "kitasnya", ["Working KITAS"]) == 1
    assert _count(m, "ptnya", ["PT PMA"]) == 0  # 'pt' is too short to stem a token


@pytest.mark.parametrize(
    ("query", "keywords", "expected"),
    [
        ("izin minuman beralkohol", ["minuman beralkohol"], True),
        ("harga izin minuman beralkohol", ["minuman beralkohol"], True),
        ("minuman yang beralkohol", ["minuman beralkohol"], True),  # noise word between
        ("minuman untuk di beralkohol", ["minuman beralkohol"], True),
        ("harga miras", ["miras"], True),
        ("minuman ringan", ["minuman beralkohol"], False),  # shares one word only
        ("izin usaha minuman ringan", ["minuman beralkohol"], False),
        ("izin", ["izin minuman"], False),
        ("beralkohol minuman", ["minuman beralkohol"], False),  # order matters
        ("minuman izin beralkohol", ["minuman beralkohol"], False),  # not contiguous
        ("mi", ["miras"], False),  # 2-char token, keyword prefix
        ("mira", ["miras"], True),  # 4-char token prefixes the keyword
        ("mir", ["miras"], False),  # 3 chars do not
        ("miras", ["miras"], True),
        ("mirasan", ["miras"], True),  # keyword (4+) prefixes the token + light suffix
        ("mirasxyz", ["miras"], False),  # ... but not with any remainder
        ("beralkoholnya", ["beralkohol"], True),
        ("ber", ["beralkohol"], False),
        ("bera", ["beralkohol"], True),  # 4+ chars is enough ("ber" is not)
        ("beralk", ["beralkohol"], True),
        ("pensi", ["pensiun"], True),
        ("pensiunan", ["pensiun"], True),
        ("pen", ["pensiun"], False),
        ("kerja", ["tenagakerja"], False),  # never inside a keyword
        ("kolhol", ["alkohol"], False),
        ("alkohol", ["alkohol", "beralkohol"], True),
        ("alk", ["alkohol"], False),
    ],
)
def test_keyword_matching(m, query, keywords, expected):
    assert (_count(m, query, ["Alcohol License"], keywords) > 0) == expected


def test_a_keyword_with_a_noise_word_still_matches_the_raw_query(m):
    # No catalogue phrase has one today; if one appears it must keep working.
    tokens = m._words("minuman di beralkohol")
    keywords = ["minuman di beralkohol"]
    assert m._count_search_matches(["minuman", "beralkohol"], tokens, ["x"], keywords) > 0


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


# --- v4: aliases, hyphen phrases, negators, empty query ---------------------------------


@pytest.mark.parametrize(
    ("query", "text", "expected"),
    [
        ("itas", "Working KITAS", 1),
        ("itap", "Investor KITAP + MERP", 1),
        ("tka", "Cancel RPTKA", 1),
        ("itas", "Investor KITAP", 0),  # alias is not a wildcard
        ("tka", "Cancel Wajib Lapor", 0),
    ],
)
def test_domain_alias_expands_the_token(m, query, text, expected):
    terms = m._query_terms(query)[1]
    assert m._count_search_matches(terms, terms, [text], []) == expected


def test_alias_map_is_small_and_names_real_targets(m):
    assert set(m._TOKEN_ALIASES) == {"itas", "itap", "tka"}
    assert len(m._TOKEN_ALIASES) <= 6


@pytest.mark.parametrize(
    ("query", "text", "expected"),
    [
        ("re-entry", "ERP (Exit Re-entry Permit)", 1),
        ("re-entry", "B1 Single entry visa", 0),  # one part ("entry") is not the compound
        ("re-entry", "entry re", 0),  # order matters
        ("pt-pma", "New Company (PT PMA)", 1),
        ("pt-pma", "PT only", 0),
        ("re-visas", "Re-Visa fee", 1),  # last part may take a light suffix
    ],
)
def test_hyphen_compound_matches_as_a_phrase(m, query, text, expected):
    tokens, terms = m._query_terms(query)
    assert terms == [" ".join(m._words(query))]
    assert m._count_search_matches(terms, tokens, [text], []) == expected


@pytest.mark.parametrize(
    ("query", "terms"),
    [
        ("non alcoholic drinks", ["drinks"]),
        ("non-alcoholic drinks", ["drinks"]),
        ("minuman tanpa alkohol", ["minuman"]),
        ("bevande senza alcol", ["bevande"]),
        ("coffee without sugar", ["coffee"]),
        ("izin minuman beralkohol", ["izin", "minuman", "beralkohol"]),
        ("nonna kitas", ["nonna", "kitas"]),  # 'nonna' is not the negator 'non'
    ],
)
def test_negator_drops_the_next_word(m, query, terms):
    assert m._query_terms(query)[1] == terms


def test_negated_query_does_not_hit_the_negated_row(pricing_service):
    for query in ("non-alcoholic drinks", "minuman tanpa alkohol", "bevande senza alcol"):
        assert not _hit_keys(pricing_service.search_service(query)) & _expand(["@alcohol"])


@pytest.mark.parametrize("query", ["", "   ", "\t"])
def test_empty_query_returns_no_rows(pricing_service, query):
    # Pinned: the pre-2026-10-17 substring code returned every row for "";
    # no caller relies on that (/api/pricing/search needs min_length=1, the tools and the
    # WhatsApp builder only search a non-empty client message; get_all_prices lists all rows).
    assert _hit_keys(pricing_service.search_service(query)) == set()
