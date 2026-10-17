"""Official Pricing Service
Loads official prices from JSON (NO AI GENERATION).

Source of truth: ``backend/data/bali_zero_official_prices_2026.json``.

The 2026 schema differs from the legacy 2025 one in three ways the
service has to handle internally:

* The ``urgent_services`` category was renamed ``urgent_processing``.
* The ``visa_extensions`` category was dropped — ``C1 Tourism Extension``
  now lives inside ``single_entry_visas``.
* New categories ``tax_accounting`` (which has one extra nesting level
  for the four tier sub-blocks ``monthly_tax_basic`` / ``monthly_tax_bundled``
  / ``annual_basic_packages`` / ``annual_standalone``) and
  ``consultant_services`` (flat, like the others).
* Each entry now exposes ``name`` / ``description_en`` / ``icon_id``
  / ``tier_range`` (a list ``[low, high]`` or ``None``) on top of the
  legacy ``price`` / ``duration`` / ``validity`` / ``notes`` fields.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Authoritative pricing JSON, 2026 edition.
_PRICING_FILENAME = "bali_zero_official_prices_2026.json"

# Categories whose value is a flat ``{service_name: entry}`` mapping.
_FLAT_CATEGORIES = (
    "single_entry_visas",
    "multiple_entry_visas",
    "kitas_permits",
    "kitap_permits",
    "company_services",
    "consultant_services",
    "other_process",
    "urgent_processing",
)

# Categories whose value is ``{sub_block: {service_name: entry}}``.
_NESTED_CATEGORIES = ("tax_accounting",)

# Words that carry no service identity in a price question (EN/ID/IT function and
# "how much" words, plus the short ones that would still match whole words in
# descriptions). Dropped from the query before matching.
_SEARCH_NOISE_WORDS = frozenset(
    {
        "berapa", "harga", "biaya", "price", "cost", "how", "much", "is", "the",
        "quanto", "costa", "what", "untuk", "for", "di", "in", "bali", "un", "una",
        "il", "la", "anno", "anni", "year", "years", "prezzo", "a", "of", "per",
        "del", "della", "dei", "delle", "con", "and", "e", "or", "o",
        "ke", "dan", "yang", "dari", "to", "as", "on", "at", "mi", "ma", "si",
        "ci", "lo", "che",
        "license", "licence", "licensing", "sell",
    }
)  # fmt: skip

_WORD_RE = re.compile(r"\w+")

# The only remainders that let a row word (or curated keyword) of 4+ characters stand for a
# longer query token: plural/inflection/derivation endings (EN, ID, IT). "kitasnya" ~ "kitas",
# "pensionati" ~ "pension"; "freelance" !~ "free", "coretax" !~ "core".
_LIGHT_SUFFIXES = frozenset(
    {
        "s",
        "es",
        "ing",
        "ed",
        "er",
        "ers",
        "ic",
        "nya",
        "an",
        "kan",
        "i",
        "ku",
        "mu",
        "lah",
        "e",
        "ati",
    }
)


def _is_noise(token: str) -> bool:
    """A noise word, or a noise word of 4+ characters plus a light suffix.

    "prices" = "price" + "s", "biayanya" = "biaya" + "nya", "selling" = "sell" + "ing".
    """
    if token in _SEARCH_NOISE_WORDS:
        return True
    return any(
        len(w) >= 4 and token.startswith(w) and token[len(w) :] in _LIGHT_SUFFIXES
        for w in _SEARCH_NOISE_WORDS
    )


# Domain acronyms a client types that are not a prefix/infix of the catalogue word any more
# (the old substring match found "itas" inside "kitas"): query token -> extra target words.
_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "itas": ("kitas",),
    "itap": ("kitap",),
    "tka": ("rptka",),
}

# A negator drops the single word after it ("non alcoholic", "minuman tanpa alkohol").
_NEGATORS = frozenset({"non", "tanpa", "senza", "without"})

_QUERY_WORD_RE = re.compile(r"\w+(?:-\w+)*")


def _query_terms(query: str) -> tuple[list[str], list[str]]:
    """Split a query into (flat word tokens, match terms).

    Terms drop noise words, one-character words and negated words. A hyphenated word
    ("re-entry", "pt-pma") stays ONE term whose parts are joined by a space; it matches
    only as a contiguous phrase of its parts. A hyphenated word that starts with a
    negator ("non-alcoholic") is dropped whole. With nothing left, the raw words are
    used (whole-query phrase match).
    """
    flat: list[str] = []
    items: list[str] = []
    for match in _QUERY_WORD_RE.findall(query.lower()):
        parts = _words(match)
        flat.extend(parts)
        items.append(" ".join(parts))
    tokens: list[str] = []
    terms: list[str] = []
    skip = False
    for item in items:
        first = item.split(" ", 1)[0]
        if skip:
            skip = False
            continue
        if item in _NEGATORS:
            skip = True
            continue
        if first in _NEGATORS:
            continue
        tokens.extend(item.split(" "))
        if not _is_noise(item) and len(item) > 1:
            terms.append(item)
    return (tokens, terms) if terms else (flat, [])


def _words(text: Any) -> list[str]:
    """Lower-cased Unicode word tokens; punctuation and symbols separate words."""
    return _WORD_RE.findall(str(text).lower())


def _term_matches_row(term: str, row_list: list[str], row_words: set[str]) -> bool:
    """A term (single word, alias-expanded, or space-joined hyphen compound) against a row."""
    if " " in term:
        parts = term.split(" ")
        n = len(parts)
        return any(
            row_list[i : i + n - 1] == parts[:-1]
            and _token_matches_words(parts[-1], {row_list[i + n - 1]})
            for i in range(len(row_list) - n + 1)
        )
    return any(_token_matches_words(t, row_words) for t in (term, *_TOKEN_ALIASES.get(term, ())))


def _token_matches_words(token: str, words: set[str]) -> bool:
    """A query token matches a row's descriptive text by WORD.

    True when the token equals a row word; is a prefix of one (at least 3 characters
    or containing a digit: "ext" ~ "extension", "e33" ~ "e33g"); has a row word of at
    least 4 characters as its prefix plus a light suffix ("kitasnya" ~ "kitas"); or is at
    least 5 characters and occurs inside a word (Indonesian circumfixes and roots:
    "polisi" ~ "kepolisian", "igiene" ~ "higiene"). 1-2 character tokens match whole
    words only ("ke" !~ "keras").
    """
    if token in words:
        return True
    long_enough_for_prefix = len(token) >= 3 or any(ch.isdigit() for ch in token)
    for w in words:
        if long_enough_for_prefix and w.startswith(token):
            return True
        if len(w) >= 4 and token.startswith(w) and token[len(w) :] in _LIGHT_SUFFIXES:
            return True
        if len(token) >= 5 and token in w:
            return True
    return False


def _token_matches_keyword(token: str, keyword: str) -> bool:
    """A query token against a curated SINGLE-word keyword: never inside the word."""
    if token == keyword:
        return True
    if len(keyword) >= 4 and token.startswith(keyword) and token[len(keyword) :] in _LIGHT_SUFFIXES:
        return True
    return len(token) >= 4 and keyword.startswith(token)


def _contains_phrase(sequence: list[str], phrase: list[str]) -> bool:
    n = len(phrase)
    return bool(n) and any(sequence[i : i + n] == phrase for i in range(len(sequence) - n + 1))


def _count_search_matches(
    terms: list[str],
    query_tokens: list[str],
    descriptive_text: list[Any],
    keywords: Any,
    whole_query: bool = False,
) -> int:
    """How many query terms a catalogue row answers (0 = not a hit).

    ``descriptive_text`` (key, name, notes, description, legacy names) matches
    by word (``_token_matches_words``). ``keywords`` are curated terms that never
    match by a word they merely share with the query: a multi-word keyword counts
    only when the whole phrase appears, contiguous, in the query (also once noise
    words are removed from it: "minuman yang beralkohol"); a single-word keyword
    counts for a query term it equals or prefixes (``_token_matches_keyword``).
    ``whole_query`` (every word was noise) requires the raw query as one
    contiguous word sequence.
    """
    row_list = [w for part in descriptive_text for w in _words(part)]
    row_words = set(row_list)
    if whole_query:
        if len(terms) == 1:
            return int(_token_matches_words(terms[0], row_words))
        return int(_contains_phrase(row_list, terms))
    matched = {t for t in terms if _term_matches_row(t, row_list, row_words)}
    if isinstance(keywords, list):
        stripped = [t for t in query_tokens if not _is_noise(t)]
        for keyword in keywords:
            phrase = _words(keyword)
            if len(phrase) == 1:
                matched.update(
                    t
                    for t in terms
                    if " " not in t
                    and any(
                        _token_matches_keyword(x, phrase[0])
                        for x in (t, *_TOKEN_ALIASES.get(t, ()))
                    )
                )
            elif _contains_phrase(query_tokens, phrase) or _contains_phrase(stripped, phrase):
                credited = [t for t in terms if t in phrase]
                matched.update(credited or [" ".join(phrase)])
    return len(matched)


def _client_facing_contacts() -> tuple[str, str]:
    """Load application settings only for contact fallbacks that need them.

    Exact catalogue lookups are pure file reads and intentionally do not
    initialize the application's environment-backed settings object. This
    keeps narrow stateless consumers, including GARUDA's child process, free
    of unrelated database/JWT/API-key requirements.

    The WhatsApp half is ``CLIENT_CONTACT_WHATSAPP``, NOT ``SUPPORT_WHATSAPP``.
    Every caller below puts this number in front of a client — a
    ``fallback_contact`` block returned when the catalogue fails to load, or
    the ``Contact:`` line of the LLM pricing context. ``SUPPORT_WHATSAPP`` is
    the bot's INBOUND identity: the line Meta delivers webhooks to, which no
    human answers. This function used to return it, and the old name is why —
    "support contacts" reads like the number a client contacts for support,
    and it is the one number that is not. Renamed so the next reader cannot
    make the same substitution; pinned by
    ``test_only_the_meta_webhook_router_reads_the_bots_inbound_number``.
    """

    from backend.app.core.config import settings

    return settings.SUPPORT_EMAIL, settings.CLIENT_CONTACT_WHATSAPP


def _format_tier_range(tier_range: list[str] | tuple[str, str] | None) -> str | None:
    """Render a ``tier_range`` (e.g. ``["1.800.000 IDR", "2.000.000 IDR"]``)
    as ``"Rp 1.800.000 – 2.000.000"`` for human-facing surfaces."""
    if not tier_range or len(tier_range) != 2:
        return None
    low_raw, high_raw = tier_range
    low = (low_raw or "").replace("IDR", "").strip()
    high = (high_raw or "").replace("IDR", "").strip()
    if not low or not high:
        return None
    return f"Rp {low} – {high}"


def _entry_display_price(entry: dict[str, Any]) -> str:
    """Return the best human price string for a 2026 entry.

    Falls back to ``tier_range`` when ``price`` is empty (typical for
    ``tax_accounting`` rows) and to ``"Contact"`` if both are missing.
    """
    price = (entry.get("price") or "").strip()
    if price:
        return price
    rendered = _format_tier_range(entry.get("tier_range"))
    if rendered:
        return rendered
    return "Contact"


def _is_internal_service(svc: Any, key: str, entry: dict[str, Any]) -> bool:
    """True when the catalogue row carries ``"internal": true``.

    ``PricingService.get_service_by_key`` returns a projected dict and must keep
    resolving internal rows for backend callers, so check both the returned dict
    and the raw catalogue entry in ``svc.prices``.
    """
    if not isinstance(entry, dict):
        return False
    if entry.get("internal") is True:
        return True
    services = getattr(svc, "prices", {}).get("services", {})
    if not isinstance(services, dict):
        return False
    category_data = services.get(entry.get("category", ""), {})
    if not isinstance(category_data, dict):
        return False
    qualifier, sep, bare_name = key.partition("::")
    if not sep:
        bare_name = key
        qualifier = ""
    raw = category_data.get(bare_name)
    if isinstance(raw, dict) and ("price" in raw or "tier_range" in raw):
        return raw.get("internal") is True
    for sub_name, sub_block in category_data.items():
        if qualifier and sub_name != qualifier:
            continue
        if isinstance(sub_block, dict):
            sub_raw = sub_block.get(bare_name)
            if isinstance(sub_raw, dict) and sub_raw.get("internal") is True:
                return True
    return False


def _omit_internal_rows(node: Any, svc: Any = None) -> Any:
    """Return a deep copy of ``node`` omitting dict entries marked ``"internal": true``."""
    if isinstance(node, dict):
        cleaned: dict[str, Any] = {}
        for key, value in node.items():
            if isinstance(value, dict) and _is_internal_service(svc, str(key), value):
                continue
            cleaned[key] = _omit_internal_rows(value, svc)
        return cleaned
    if isinstance(node, list):
        return [
            _omit_internal_rows(item, svc)
            for item in node
            if not (
                isinstance(item, dict)
                and _is_internal_service(svc, str(item.get("name", "")), item)
            )
        ]
    return node


# Namespace separator for a QUALIFIED ``get_service_by_key`` argument
# (``"<sub_block or category>::<service_name>"``). Chosen over "/" because
# several real catalogue display names already contain a bare "/" (e.g.
# "Working KITAS (Altus/Onshore)") — "/" would not visibly distinguish a
# qualifier from an ordinary display name that happens to contain one. No
# catalogue name contains "::". Kept in sync by convention (not by import —
# this module owns the catalogue walk, the client-bot snapshot builder does
# not) with the identical scheme in
# ``backend/services/client_bot/grounding.py``'s ``_KEY_QUALIFIER_SEP``.
_KEY_QUALIFIER_SEP = "::"


def _iter_service_entries_with_subblock(
    services: dict[str, Any],
) -> list[tuple[str, str | None, str, dict[str, Any]]]:
    """Yield ``(category, sub_block, service_name, entry)`` quadruples across
    the whole ``services`` mapping. ``sub_block`` is ``None`` for the flat
    ``_FLAT_CATEGORIES`` and the nested sub-block name (e.g.
    ``"monthly_tax_basic"``) for ``_NESTED_CATEGORIES`` — the one extra
    piece of context :func:`_iter_service_entries` intentionally drops, and
    that :meth:`PricingService.get_service_by_key` needs to tell apart two
    entries that share the same ``service_name`` across different
    sub-blocks of the same category."""
    quads: list[tuple[str, str | None, str, dict[str, Any]]] = []
    for category_name, category_payload in services.items():
        if not isinstance(category_payload, dict):
            continue
        if category_name in _NESTED_CATEGORIES:
            for sub_block_name, sub_block in category_payload.items():
                if not isinstance(sub_block, dict):
                    continue
                for service_name, entry in sub_block.items():
                    if isinstance(entry, dict):
                        quads.append((category_name, sub_block_name, service_name, entry))
        else:
            for service_name, entry in category_payload.items():
                if isinstance(entry, dict):
                    quads.append((category_name, None, service_name, entry))
    return quads


def _iter_service_entries(
    services: dict[str, Any],
) -> list[tuple[str, str, dict[str, Any]]]:
    """Yield ``(category, service_name, entry)`` triples across the whole
    ``services`` mapping, descending one extra level for nested categories
    such as ``tax_accounting`` so callers see a flat stream.

    A thin projection of :func:`_iter_service_entries_with_subblock` that
    drops the sub-block column — kept as its own function because it is the
    load-time service-count helper's public shape and nothing outside this
    module needs the sub-block detail."""
    return [
        (category, service_name, entry)
        for category, _sub_block, service_name, entry in _iter_service_entries_with_subblock(
            services
        )
    ]


class PricingService:
    """Official Service Pricing - NO AI GENERATION ALLOWED"""

    def __init__(self) -> None:
        self.prices: dict[str, Any] = {}
        self.loaded = False
        self._load_prices()

    def _load_prices(self) -> None:
        """Load official prices from the 2026 JSON file."""
        try:
            json_path = Path(__file__).parent.parent.parent / "data" / _PRICING_FILENAME

            if not json_path.exists():
                logger.warning("Official prices file not found at %s", json_path)
                self.prices = {}
                self.loaded = False
                return

            with open(json_path, encoding="utf-8") as f:
                self.prices = json.load(f)

            self.loaded = True
            logger.info("Loaded official prices from %s", json_path)

            # Count services across the full 9-category 2026 schema, descending
            # into ``tax_accounting`` sub-blocks so the log line reflects the
            # real number of priced rows.
            service_count = len(_iter_service_entries(self.prices.get("services", {})))
            categories_present = [
                cat
                for cat in (*_FLAT_CATEGORIES, *_NESTED_CATEGORIES)
                if cat in self.prices.get("services", {})
            ]
            logger.info(
                f"{service_count} services loaded across {len(categories_present)} categories"
            )

        except Exception as e:
            logger.error("Error loading official prices: %s", e)
            self.prices = {}
            self.loaded = False

    def get_pricing(self, service_type: str = "all") -> dict[str, Any]:
        """
        Get pricing for specific service type

        Args:
            service_type: Type of service (visa, kitas, business_setup, tax_consulting, legal, all)

        Returns:
            Pricing data for the requested service type
        """
        if not self.loaded:
            support_email, client_whatsapp = _client_facing_contacts()
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {
                    "email": support_email,
                    "whatsapp": client_whatsapp,
                },
            }

        # Map service types to specific methods
        if service_type == "visa":
            return self.get_visa_prices()
        if service_type == "kitas" or service_type == "long_stay_permit":
            return self.get_kitas_prices()  # Generic long-stay permit prices
        if service_type == "business_setup":
            return self.get_business_prices()
        if service_type == "tax_consulting":
            return self.get_tax_prices()
        if service_type == "legal":
            return self.get_business_prices()  # Legal services are in business
        if service_type == "all":
            return self.get_all_prices()
        # Try to search for the service
        return self.search_service(service_type)

    def get_pricing_for_clients(self, service_type: str = "all") -> dict[str, Any]:
        """Get pricing for client-facing and LLM callers, omitting internal rows."""
        return _omit_internal_rows(self.get_pricing(service_type), self)

    def get_service_by_key(self, key: str) -> dict[str, Any] | None:
        """Look up ONE service by its exact catalogue key.

        This is the deterministic counterpart to :meth:`search_service`: no
        scoring, no fuzzy matching, no "best guess". A caller that renders a
        price on a client-facing surface must get either the exact row it asked
        for or nothing — a near-miss silently rendered as the real price is the
        failure mode this method exists to make impossible.

        Returns ``None`` when the key is unknown OR when the catalogue failed to
        load, so the caller cannot mistake "not loaded" for "no such service".
        The two are distinguished by :attr:`loaded`.

        ``key`` can also be AMBIGUOUS: the live 2026 catalogue has four
        ``service_name`` collisions — "Tier 0-50", "Tier 50-100",
        "Tier 100-200", "Tier 200+" — each shared between
        ``tax_accounting``'s ``monthly_tax_basic`` (a tier-range price, LKPM
        and Annual Tax NOT included) and ``monthly_tax_bundled`` (a single
        price, LKPM + Annual Tax included) sub-blocks, with a genuinely
        different amount behind the identical dict key. A bare colliding key
        now returns ``None`` rather than silently resolving to whichever
        sub-block the catalogue walk happens to reach first — the near-miss-
        as-real-price failure this method exists to prevent, just triggered
        by the catalogue's own shape instead of a caller's typo. To ask for
        ONE of the colliding rows unambiguously, qualify the key as
        ``"<sub_block or category>::<service_name>"`` (e.g.
        ``"monthly_tax_bundled::Tier 0-50"``) — see :data:`_KEY_QUALIFIER_SEP`.
        Every other key (105 of the catalogue's 109) is unaffected and keeps
        resolving on its bare, human-readable name exactly as before; the
        returned ``"key"`` always echoes back ``key`` verbatim, qualified or
        not, so a caller's own ``row["key"] == key`` round-trip check holds
        either way.
        """
        if not self.loaded:
            return None

        quads = _iter_service_entries_with_subblock(self.prices.get("services", {}))

        if _KEY_QUALIFIER_SEP in key:
            qualifier, _sep, bare_name = key.partition(_KEY_QUALIFIER_SEP)
            matches = [
                (category, sub_block, entry)
                for category, sub_block, service_name, entry in quads
                if service_name == bare_name and (sub_block or category) == qualifier
            ]
        else:
            bare_name = key
            matches = [
                (category, sub_block, entry)
                for category, sub_block, service_name, entry in quads
                if service_name == key
            ]

        if len(matches) != 1:
            if len(matches) > 1:
                qualifiers = sorted((sub_block or cat) for cat, sub_block, _e in matches)
                logger.warning(
                    "get_service_by_key(%r): %d entries share this key — refusing "
                    "to guess. Ask for one unambiguously via '<qualifier>::%s' "
                    "where <qualifier> in %s.",
                    key,
                    len(matches),
                    bare_name,
                    qualifiers,
                )
            return None

        category, _sub_block, entry = matches[0]
        return {
            "key": key,
            "name": entry.get("name") or bare_name,
            "price": _entry_display_price(entry),
            "category": category,
            "validity": entry.get("validity") or None,
            "notes": entry.get("notes") or None,
            # Per-row attestation stamp (narrower than `metadata.last_updated`)
            # — see `garuda_flow.pricing.price_catalogue_freshness`'s `row=`
            # argument. Absent on every row except the ones an owner has
            # explicitly re-verified; passed through verbatim, unvalidated
            # (the freshness module owns "is this a good stamp").
            "verified_on": entry.get("verified_on"),
        }

    def get_all_prices(self) -> dict[str, Any]:
        """Get all official prices"""
        if not self.loaded:
            support_email, client_whatsapp = _client_facing_contacts()
            return {
                "error": "Official prices not loaded",
                "fallback_contact": {
                    "email": support_email,
                    "whatsapp": client_whatsapp,
                },
            }
        return self.prices

    def search_service(self, query: str) -> dict[str, Any]:
        """Search for a specific service by name or keyword.

        Supports both the legacy LIST shape (some unit tests still mount
        ``[{code, name, ...}]`` fixtures) and the 2026 DICT shape, plus
        the 2026-only nested ``tax_accounting`` sub-block layout.
        """
        if not self.loaded:
            return {
                "error": "Official prices not loaded",
                "contact": self.prices.get(
                    "contact_info", self.prices.get("metadata", {}).get("contact", {})
                ),
            }

        query_lower = query.lower().strip()
        results: dict[str, Any] = {}

        # Words of the query (punctuation-insensitive); noise words and one-character
        # tokens are dropped. If nothing is left, the raw query is matched as a phrase.
        query_tokens, clean_keywords = _query_terms(query_lower)
        whole_query = not clean_keywords
        if whole_query:
            clean_keywords = query_tokens

        services = self.prices.get("services", {})

        def _score_dict_entry(
            category_name: str,
            service_name: str,
            service_data: dict[str, Any],
            container: dict[str, Any] | None = None,
        ) -> None:
            if _is_internal_service(self, service_name, service_data):
                return
            legacy_names = service_data.get("legacy_names", [])
            match_count = _count_search_matches(
                clean_keywords,
                query_tokens,
                [
                    service_name,
                    service_data.get("name", ""),
                    service_data.get("notes", ""),
                    service_data.get("description_en", ""),
                    *(legacy_names if isinstance(legacy_names, list) else []),
                ],
                service_data.get("keywords", []),
                whole_query,
            )
            if match_count > 0:
                target = container if container is not None else results
                target.setdefault(category_name, {})[service_name] = service_data

        for category_name, category_services in services.items():
            # Handle LIST format (legacy fixtures only — no 2026 category uses this)
            if isinstance(category_services, list):
                for service_item in category_services:
                    if not isinstance(service_item, dict):
                        continue
                    if _is_internal_service(self, str(service_item.get("name", "")), service_item):
                        continue
                    legacy_names = service_item.get("legacy_names", [])
                    match_count = _count_search_matches(
                        clean_keywords,
                        query_tokens,
                        [
                            service_item.get("code", ""),
                            service_item.get("name", ""),
                            service_item.get("notes", ""),
                            service_item.get("description_en", ""),
                            *(legacy_names if isinstance(legacy_names, list) else []),
                        ],
                        service_item.get("keywords", []),
                        whole_query,
                    )
                    if match_count > 0:
                        results.setdefault(category_name, []).append(
                            (match_count, service_item),
                        )
                continue

            if not isinstance(category_services, dict):
                continue

            # 2026: ``tax_accounting`` is one level deeper.
            if category_name in _NESTED_CATEGORIES:
                for sub_block_name, sub_block in category_services.items():
                    if not isinstance(sub_block, dict):
                        continue
                    for service_name, service_data in sub_block.items():
                        if not isinstance(service_data, dict):
                            continue
                        # Annotate the entry with its sub-block so callers
                        # (UI, MCP, prompt builder) can preserve the
                        # tier hierarchy without us flattening it.
                        annotated = {**service_data, "_sub_block": sub_block_name}
                        _score_dict_entry(category_name, service_name, annotated)
                continue

            # Flat dict (single_entry_visas, kitas_permits, …, urgent_processing).
            for service_name, service_data in category_services.items():
                if not isinstance(service_data, dict):
                    continue
                _score_dict_entry(category_name, service_name, service_data)

        # For list results, sort by match_count descending, keep top results
        filtered_results: dict[str, Any] = {}
        for category_name, items in results.items():
            if isinstance(items, list):
                items.sort(key=lambda x: x[0], reverse=True)
                max_score = items[0][0] if items else 0
                if max_score <= 1:
                    best_items = [item for _score, item in items[:5]]
                else:
                    best_items = [item for score, item in items if score >= max_score]
                filtered_results[category_name] = best_items
            else:
                filtered_results[category_name] = items

        contact_info = self.prices.get(
            "contact_info",
            self.prices.get("metadata", {}).get("contact", {}),
        )

        if filtered_results:
            return {
                "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
                "search_query": query,
                "results": filtered_results,
                "contact_info": contact_info,
                "disclaimer": self.prices.get("disclaimer", {}),
            }
        support_email, _client_whatsapp = _client_facing_contacts()
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026",
            "search_query": query,
            "message": f"No service found for '{query}'",
            "suggestion": f"Contact {support_email} for custom quotes",
            "contact_info": contact_info,
        }

    def _contact_info(self) -> dict[str, Any]:
        """Single source for contact info — prefer 2026 ``metadata.contact``."""
        explicit = self.prices.get("contact_info")
        if explicit:
            return explicit
        return self.prices.get("metadata", {}).get("contact", {})

    def get_visa_prices(self) -> dict[str, Any]:
        """Get all visa prices.

        2026 dropped the ``visa_extensions`` category — ``C1 Tourism Extension``
        is now a row inside ``single_entry_visas``. We still publish the
        ``visa_extensions`` key in the response for backwards compatibility
        with the Mouth ``PricingTable.tsx`` renderer, but it is empty.
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - VISA",
            "single_entry_visas": services.get("single_entry_visas", {}),
            "multiple_entry_visas": services.get("multiple_entry_visas", {}),
            # Legacy key preserved for the Mouth chat renderer; 2026 has no
            # standalone extensions category, so this is intentionally empty.
            "visa_extensions": services.get("visa_extensions", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_kitas_prices(self) -> dict[str, Any]:
        """Get all KITAS / KITAP prices."""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - KITAS",
            "kitas_permits": services.get("kitas_permits", {}),
            "kitap_permits": services.get("kitap_permits", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_business_prices(self) -> dict[str, Any]:
        """Get business / company / consultant service prices.

        2026 added ``consultant_services`` (Close PMA, NPWPD, BPJS, NPWP
        Personal, Update Data, EFIN). Surfaced alongside the existing
        ``company_services`` and ``other_process`` so the prompt builder
        and the Mouth UI can render them together.
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - BUSINESS",
            "company_services": services.get("company_services", {}),
            "consultant_services": services.get("consultant_services", {}),
            "other_process": services.get("other_process", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
            "important_warnings": self.prices.get("important_warnings", {}),
        }

    def get_tax_prices(self) -> dict[str, Any]:
        """Get tax & accounting prices.

        2026 introduced the dedicated ``tax_accounting`` category with four
        nested sub-blocks (``monthly_tax_basic`` / ``monthly_tax_bundled``
        / ``annual_basic_packages`` / ``annual_standalone``). The nested
        structure is preserved in the response so callers can render the
        tier hierarchy. Urgent processing kept under its 2026 name
        (``urgent_processing``).
        """
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - TAX & URGENT",
            "tax_accounting": services.get("tax_accounting", {}),
            "urgent_processing": services.get("urgent_processing", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_quick_quotes(self) -> dict[str, Any]:
        """Get pre-calculated package quotes (deprecated — not in 2026 schema)."""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        services = self.prices.get("services", {})
        return {
            "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2026 - PACKAGES",
            "quick_quotes": services.get("quick_quotes", {}),
            "contact_info": self._contact_info(),
            "disclaimer": self.prices.get("disclaimer", {}),
        }

    def get_warnings(self) -> dict[str, Any]:
        """Get important warnings for clients"""
        if not self.loaded:
            return {"error": "Prices not loaded"}

        return {
            "important_warnings": self.prices.get("important_warnings", {}),
            "cost_optimization_tips": self.prices.get("cost_optimization_tips", {}),
            "contact_urgency_levels": self.prices.get("contact_urgency_levels", {}),
        }

    def _format_service_list(self, category_data: list | dict) -> list[str]:
        """Helper to format service data regardless of list/dict format.

        2026 dict entries can carry ``tier_range`` instead of ``price``;
        :func:`_entry_display_price` resolves both cases.
        """
        lines: list[str] = []
        if isinstance(category_data, list):
            for item in category_data:
                if isinstance(item, dict):
                    name = item.get("name", item.get("code", "Unknown"))
                    if _is_internal_service(self, str(name), item):
                        continue
                    price_idr = item.get("price_idr", item.get("price", "Contact"))
                    price_usd = item.get("price_usd_approx", "")
                    duration = item.get("duration", "")
                    suffix = f" ({duration})" if duration else ""
                    usd_str = f" (~${price_usd})" if price_usd else ""
                    lines.append(
                        f"- {name}: IDR {price_idr:,}{usd_str}{suffix}"
                        if isinstance(price_idr, (int, float))
                        else f"- {name}: {price_idr}{usd_str}{suffix}",
                    )
        elif isinstance(category_data, dict):
            for name, data in category_data.items():
                if isinstance(data, dict):
                    if _is_internal_service(self, name, data):
                        continue
                    # Detect tax_accounting-style sub-block: a dict whose
                    # values look like service entries themselves (have
                    # ``name`` and either ``price`` or ``tier_range``).
                    is_subblock = bool(data) and all(
                        isinstance(v, dict) and ("price" in v or "tier_range" in v)
                        for v in data.values()
                    )
                    # Distinguish a SINGLE entry (which also has those keys)
                    # from a sub-block by checking that ``data`` itself is
                    # NOT a service entry — service entries have ``name``.
                    if is_subblock and "name" not in data:
                        lines.append(f"### {name}")
                        lines.extend(self._format_service_list(data))
                        continue
                    display = _entry_display_price(data)
                    duration = data.get("duration", "")
                    duration_str = f" — {duration}" if duration else ""
                    lines.append(f"- {name}: {display}{duration_str}")
                else:
                    lines.append(f"- {name}: {data}")
        return lines

    def format_for_llm_context(self, service_type: str | None = None) -> str:
        """
        Format pricing data as context for LLM.

        Returns a concise string suitable for injection into LLM context.
        Sections track the 2026 schema: visa, KITAS/KITAP, company &
        consultant, tax & accounting, urgent processing.
        """
        if not self.loaded:
            support_email, _client_whatsapp = _client_facing_contacts()
            return f"⚠️ Official prices not available. Contact {support_email}"

        context_parts = [
            "🔒 BALI ZERO OFFICIAL PRICES 2026 (DO NOT GENERATE - USE THESE EXACT VALUES)",
            "",
        ]

        services = self.prices.get("services", {})

        if service_type == "visa" or service_type is None:
            context_parts.append("## VISA PRICES")
            context_parts.extend(self._format_service_list(services.get("single_entry_visas", {})))
            context_parts.extend(
                self._format_service_list(services.get("multiple_entry_visas", {})),
            )
            context_parts.append("")

        if service_type == "kitas" or service_type is None:
            context_parts.append("## KITAS/KITAP PERMITS")
            context_parts.extend(self._format_service_list(services.get("kitas_permits", {})))
            context_parts.extend(self._format_service_list(services.get("kitap_permits", {})))
            context_parts.append("")

        if service_type == "business" or service_type is None:
            context_parts.append("## COMPANY & CONSULTANT SERVICES")
            context_parts.extend(self._format_service_list(services.get("company_services", {})))
            context_parts.extend(self._format_service_list(services.get("consultant_services", {})))
            context_parts.append("")

        if service_type == "tax" or service_type is None:
            context_parts.append("## TAX & ACCOUNTING")
            context_parts.extend(self._format_service_list(services.get("tax_accounting", {})))
            context_parts.append("")

        if service_type == "other" or service_type is None:
            context_parts.append("## OTHER SERVICES")
            context_parts.extend(self._format_service_list(services.get("other_process", {})))
            context_parts.append("")

        if service_type == "urgent" or service_type is None:
            context_parts.append("## URGENT PROCESSING")
            context_parts.extend(self._format_service_list(services.get("urgent_processing", {})))
            context_parts.append("")

        # Always include warnings
        warnings = self.prices.get("important_warnings", {})
        if warnings and isinstance(warnings, dict):
            context_parts.append("## IMPORTANT WARNINGS")
            for _key, warning in list(warnings.items())[:3]:
                context_parts.append(f"⚠️ {warning}")
            context_parts.append("")

        # Contact info
        contact = self._contact_info()
        support_email, client_whatsapp = _client_facing_contacts()
        context_parts.append(
            f"Contact: {contact.get('email', support_email)} | WhatsApp: {contact.get('whatsapp', client_whatsapp)}",
        )

        return "\n".join(context_parts)


# Global singleton instance
_pricing_service: PricingService | None = None


def get_pricing_service() -> PricingService:
    """Get or create global pricing service instance"""
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService()
    return _pricing_service


# Convenience functions for easy import
def get_all_prices() -> dict[str, Any]:
    """Get all official prices"""
    return get_pricing_service().get_all_prices()


def search_service(query: str) -> dict[str, Any]:
    """Search for a service by name/keyword"""
    return get_pricing_service().search_service(query)


def get_visa_prices() -> dict[str, Any]:
    """Get visa prices"""
    return get_pricing_service().get_visa_prices()


def get_kitas_prices() -> dict[str, Any]:
    """Get KITAS prices"""
    return get_pricing_service().get_kitas_prices()


def get_business_prices() -> dict[str, Any]:
    """Get business service prices"""
    return get_pricing_service().get_business_prices()


def get_tax_prices() -> dict[str, Any]:
    """Get tax service prices"""
    return get_pricing_service().get_tax_prices()


def get_pricing_context_for_llm(service_type: str | None = None) -> str:
    """Get pricing data formatted for LLM context injection"""
    return get_pricing_service().format_for_llm_context(service_type)
