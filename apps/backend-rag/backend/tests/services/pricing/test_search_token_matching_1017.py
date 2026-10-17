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


# --- after #8655's gate: noise words stem like row words; generic licence/sale words ----------


@pytest.mark.parametrize(
    "token",
    ["price", "prices", "biayanya", "harganya", "years", "license", "licenses", "licences",
     "licensing", "sell", "sells", "selling", "seller"],
)  # fmt: skip
def test_inflected_noise_words_are_noise(m, token):
    assert m._is_noise(token)
    assert m._query_terms(f"{token} kitas")[1] == ["kitas"]


@pytest.mark.parametrize(
    "token",
    [
        "kitas",
        "alcohol",
        "visa",
        "pricey",
        "costume",
        "sellx",
        "yearly",
        "di5",
        "kitasnya",
        "alkohol",
    ],
)
def test_other_tokens_are_not_noise(m, token):
    assert not m._is_noise(token)


@pytest.mark.parametrize("word", ["license", "licence", "sell"])
def test_generic_licence_and_sale_words_are_noise_words(m, word):
    assert word in m._SEARCH_NOISE_WORDS


# --- speed shape (issue #8665 item 1): per-query work is done once, per-row text once ------


def _long_message(words: int) -> str:
    base = (
        "berapa harga kitas investor pt-pma for the selling prices of alcohol licence tax".split()
    )
    return " ".join(base[i % len(base)] + ("" if i % 7 else str(i)) for i in range(words))


def test_search_prepares_the_query_and_the_rows_once(pricing_service, m, monkeypatch):
    """Tokeniser and noise-check calls must not scale with rows x query tokens."""
    calls = {"row_profile": 0}
    real_profile = m._row_profile

    def counting_profile(texts):
        calls["row_profile"] += 1
        return real_profile(texts)

    monkeypatch.setattr(m, "_row_profile", counting_profile)
    short, long = "kitas", _long_message(250)
    per_search = {}
    for label, query in (("short", short), ("long", long)):
        calls["row_profile"] = 0
        m._is_noise.cache_clear()
        pricing_service.search_service(query)
        info = m._is_noise.cache_info()
        per_search[label] = (calls["row_profile"], info.hits + info.misses, len(m._words(query)))
    # One profile per row, whatever the query length.
    assert per_search["short"][0] == per_search["long"][0] > 50
    # Noise checks scale with the QUERY (a few per token), never with rows x tokens
    # (the 2026-10-17 regression made ~34,000 calls for a 1,500-character message).
    rows, noise_calls, tokens = per_search["long"]
    assert noise_calls <= 4 * tokens
    assert noise_calls < rows * tokens // 10


def test_row_profile_is_keyed_by_content_so_a_reload_is_never_stale(pricing_service, m):
    fresh = type(pricing_service).__new__(type(pricing_service))
    fresh.loaded = True
    fresh.prices = {"services": {"company_services": {"Row X": {"name": "Alpha gadget"}}}}
    assert "company_services" in fresh.search_service("alpha")["results"]
    assert "results" not in fresh.search_service("omega")
    # Same service object, same row key, edited text: the next search must see the edit.
    fresh.prices = {"services": {"company_services": {"Row X": {"name": "Omega gadget"}}}}
    assert "results" not in fresh.search_service("alpha")
    assert "company_services" in fresh.search_service("omega")["results"]


def test_vocabulary_lookup_equals_the_reference_word_rule(pricing_service, m):
    words: set[str] = set()
    for rows in pricing_service.prices["services"].values():
        blocks = rows.values() if isinstance(rows, dict) and "monthly_tax_basic" in rows else [rows]
        for block in blocks:
            for key, row in block.items():
                if isinstance(row, dict):
                    words.update(m._words(f"{key} {row.get('name', '')} {row.get('notes', '')}"))
    vocab = m._Vocabulary(words)
    tokens = {w[:n] for w in list(words)[:150] for n in (2, 3, 4, 6)} | {
        w + s for w in list(words)[:60] for s in ("s", "nya", "ing", "x", "an", "")
    }
    tokens |= {
        "kitasnya",
        "polisi",
        "igiene",
        "ke",
        "e3",
        "di5",
        "freelance",
        "free",
        "coretax",
        "core",
    }
    for token in tokens:
        expected = {w for w in words if m._token_matches_words(token, {w})}
        assert vocab.matching(token) == expected, token
