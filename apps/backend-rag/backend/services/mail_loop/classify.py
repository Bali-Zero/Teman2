"""Intent + language routing for the daily Zoho mail loop.

Pure logic, zero I/O: every function here is a total function of its inputs, so
the whole module is unit-testable without a mailbox.

Cicatrix discipline (superscar #3 — guard-over-match / under-match):

    * Every marker matches on WORD BOUNDARIES, never as a bare substring.
      The live traps this module is built against, all of them real members of
      the #3 family: "please" contains "lease", "boss" contains "oss",
      "taxi" contains "tax", "quota" contains "ota", "different" contains
      "rent". A bare-substring router mis-files a food-import question as a
      villa question (W73, live-proven) — so `_WORD` is not optional polish,
      it is the whole difference between routing and lying.

    * Markers exist for EVERY language the channel actually speaks
      (en / id / it / ru). A router calibrated in English on a multilingual
      channel is W77 waiting to happen: 10 wrong-answer-passes were found in
      ID/IT precisely because the gates were English-only.

    * Accented AND unaccented spellings are both listed. Normalisation here
      lowercases and collapses whitespace but does NOT strip accents (W105/W77
      gotcha), so "società" and "societa" are two markers, not one.

    * NEGATIVE CONTEXT beats marker count. "Payment by Visa card" carries the
      token `visa` and is not a visa enquiry; suppression is expressed as an
      entity ("visa" adjacent to a card/payment word), not as a blocklist of
      phrasings, because a fixed phrase list is brittle (W73 gotcha c).

    * Bulk/noise detection prefers STRUCTURAL evidence (List-Unsubscribe,
      Precedence: bulk, an auto-submitted header) over word matching. A header
      is an entity; "sale" in prose is a coincidence.

    * The test corpus carries guilt AND innocence rows per lane. A guard
      merged with only guilt rows is half a guard (superscar #3 antidote).

This module ROUTES. It never decides regulatory content: no marker here
implies a legal conclusion, and nothing downstream may read an intent as a
verdict about a client's case.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    """Routing lanes. Values double as the Zoho folder suffix."""

    VISA = "visa"
    PT_PMA = "ptpma"
    TAX = "tax"
    PROPERTY = "property"
    ADMIN = "admin"
    NOISE = "noise"
    UNKNOWN = "unknown"


# Folder names in Zoho. Underscore prefix keeps them grouped at the top of the
# sidebar and distinguishable from folders a human made.
FOLDER_BY_INTENT: dict[Intent, str] = {
    Intent.VISA: "_Visa",
    Intent.PT_PMA: "_PTPMA",
    Intent.TAX: "_Tax",
    Intent.PROPERTY: "_Property",
    Intent.ADMIN: "_Admin",
    Intent.NOISE: "_Noise",
}

# ---------------------------------------------------------------------------
# Markers. Grouped per lane, per language. Bahasa terms stay verbatim (brand
# rule: KITAS / PT PMA / KBLI / hak pakai / NPWP are never translated).
# ---------------------------------------------------------------------------

_MARKERS: dict[Intent, tuple[str, ...]] = {
    Intent.VISA: (
        # Instruments — language-invariant, the strongest signal in the lane.
        "kitas", "kitap", "b211", "b211a", "c1", "c2", "c7", "c12", "c22",
        "d12", "e23", "e28a", "e31", "e33g", "voa", "evisa", "e-visa",
        "imta", "rptka", "mert", "epo", "sktt",
        # en
        "visa", "visas", "overstay", "work permit", "stay permit",
        "residence permit", "sponsor letter", "dependent visa", "immigration",
        # id
        "izin tinggal", "keimigrasian", "imigrasi", "paspor", "penjamin",
        "visa kunjungan", "visa tinggal",
        # it
        "visto", "visti", "permesso di soggiorno", "immigrazione", "soggiorno",
        # ru
        "виза", "визу", "визы", "китас", "внж", "разрешение на работу",
    ),
    Intent.PT_PMA: (
        "pt pma", "pma", "pt lokal", "kbli", "oss", "nib", "akta", "notaris",
        "ahu", "sk kemenkumham", "lkpm", "modal disetor", "paid up capital",
        "pendirian", "shareholder", "shareholders", "direktur", "komisaris",
        "company setup", "incorporation", "legal entity", "cv indonesia",
        # it
        "società", "societa", "costituzione", "socio", "soci", "quota sociale",
        # ru
        "ооо", "регистрация компании", "учредитель",
    ),
    Intent.TAX: (
        "npwp", "spt", "ppn", "pph", "pbb", "coretax", "efaktur", "e-faktur",
        "faktur pajak", "bukti potong", "djp", "e-billing", "ebupot",
        "pajak", "perpajakan",
        # en
        "tax", "taxes", "taxation", "vat", "withholding", "fiscal year",
        "annual return", "tax return", "audit fiscale",
        # it
        "tasse", "imposte", "fiscale", "dichiarazione dei redditi", "iva",
        # ru
        "налог", "налоги", "налоговая", "ндс",
    ),
    Intent.PROPERTY: (
        "hak milik", "hak pakai", "hak guna bangunan", "hgb", "shm", "ajb",
        "ppjb", "imb", "pbg", "sertifikat tanah", "girik", "zonasi",
        # en
        "leasehold", "freehold", "land certificate", "villa", "land plot",
        "title deed", "notary deed", "due diligence tanah",
        # id
        "tanah", "sewa tanah", "bangunan", "notaris tanah",
        # it
        "terreno", "immobile", "immobiliare", "usufrutto", "compravendita",
        # ru
        "недвижимость", "земля", "участок", "аренда земли",
    ),
    Intent.ADMIN: (
        "invoice", "receipt", "quotation", "proforma", "payment confirmation",
        "bank transfer", "appointment", "meeting", "reschedule", "calendar",
        "zoom link", "google meet", "onboarding", "engagement letter",
        # id
        "pembayaran", "tagihan", "kwitansi", "jadwal", "pertemuan",
        # it
        "fattura", "ricevuta", "preventivo", "bonifico", "appuntamento",
        # ru
        "счёт", "оплата", "встреча", "квитанция",
    ),
    Intent.NOISE: (
        "unsubscribe", "newsletter", "webinar", "promo code", "black friday",
        "limited offer", "you have won", "click here to claim",
        "no longer wish to receive", "berhenti berlangganan",
        "disiscriviti", "отписаться",
    ),
}

# Instruments that are strong enough to decide a lane on their own. These are
# entities (a permit code, a legal instrument) with no ordinary-language twin,
# so a single hit is not a coincidence.
_DECISIVE: dict[Intent, frozenset[str]] = {
    Intent.VISA: frozenset(
        {"kitas", "kitap", "b211", "b211a", "c1", "c2", "c7", "c12", "c22",
         "d12", "e23", "e28a", "e31", "e33g", "imta", "rptka", "sktt",
         "izin tinggal", "overstay", "китас"}
    ),
    Intent.PT_PMA: frozenset(
        {"pt pma", "kbli", "nib", "akta", "ahu", "lkpm", "sk kemenkumham"}
    ),
    Intent.TAX: frozenset(
        {"npwp", "spt", "ppn", "pph", "coretax", "efaktur", "e-faktur",
         "faktur pajak", "bukti potong", "ebupot"}
    ),
    Intent.PROPERTY: frozenset(
        {"hak milik", "hak pakai", "hak guna bangunan", "hgb", "shm", "ajb",
         "ppjb", "imb", "pbg", "sertifikat tanah"}
    ),
}

# Markers too common in ordinary business email to justify a route ON THEIR OWN.
#
# `_DECISIVE` above says an instrument is strong because it has "no
# ordinary-language twin, so a single hit is not a coincidence". The
# contrapositive was written in that comment and never enforced: a soft marker's
# single hit CAN be a coincidence, and until 2026-08-05 the count path routed on
# it anyway — one hit, runner-up zero, message moved out of the inbox.
#
# Measured on the live mailbox before this rule existed: of 7 routings in one
# run, SIX rested on a single soft marker (five on `tax`, one on `meeting`) and
# not one carried a decisive instrument. `tax` is boilerplate — it sits in the
# footer of every invoice, receipt and SaaS bill on earth — so "mentions tax"
# was filing a client's mail into _Tax on the strength of a vendor's small
# print.
#
# Each entry below is listed WITH the ordinary-language twin that makes it
# coincidence-grade. A weak marker still SCORES (it can win a lane, break a tie,
# and confirm a strong one); it simply may not be the sole reason to move
# somebody's mail. A lane whose every hit is weak yields UNKNOWN, which this
# module already treats as a first-class answer: the message stays in the inbox
# where a human sees it. That is the stated preference, now enforced.
#
# Deliberately NOT weak, and why: `visa` (the card-brand twin is already killed
# by negative context, and no other boilerplate carries it), `invoice`/`receipt`
# and their translations (these DO define their topic, and _Admin is the correct
# home for a vendor invoice), `pajak`/`налог` (domain words, not footer
# furniture). Extending this set is a measurement, not a hunch — add a token
# only after seeing it decide a route it should not have.
_WEAK: frozenset[str] = frozenset(
    {
        # TAX — every commercial email quotes a tax line.
        "tax", "taxes", "vat", "iva",
        # "codice fiscale" is an identity number; "anno fiscale" is a date range.
        "fiscale",
        # Pure accounting boilerplate, and no more specific than `vat`.
        "fiscal year",
        # Italian "imposte" is both taxes AND window shutters.
        "imposte",
        # ADMIN — scheduling language lives INSIDE substantive mail. A visa
        # question that ends "can we set a meeting?" is a visa question.
        "meeting", "appointment", "calendar", "reschedule",
        "jadwal", "pertemuan", "appuntamento", "встреча",
        # Signature-block furniture in the same sense: a call link pasted under
        # a name says nothing about what the mail is about.
        "zoom link", "google meet",
        # PROPERTY — in Bali everyone lives in a villa; `bangunan` shows up in
        # postal addresses. "villa" already has negative context for the
        # housekeeping sense, which is a different (narrower) filter.
        "villa", "bangunan",
        # "Tanah Lot" is one of Bali's best-known landmarks — the commonest
        # place-name component on the island, and a stronger coincidence than
        # `bangunan`, which was demoted for the weaker (postal) reason.
        "tanah",
        # VISA — Italian "soggiorno" is also a living room and a plain stay.
        # The instrument "permesso di soggiorno" is listed separately and stays
        # strong.
        "soggiorno",
        # "ho visto" = "I saw"; "ci siamo visti" = "we met". A top-20 Italian
        # past participle in the busiest lane, on a channel where Italian is a
        # first-class language — strictly worse than `soggiorno`, which was
        # already demoted. Declared cost: a bare "vorrei un visto" now stays in
        # the inbox instead of routing. That is the trade this whole rule
        # makes, and it is pinned by a test so nobody pays it unknowingly.
        "visto", "visti",
        # PT_PMA — three letters that also spell "open source software" and sit
        # inside plenty of unrelated acronym soup.
        "oss",
        # Signature-block furniture: "Budi Santoso / Direktur Utama" says who
        # wrote the mail, not what it is about.
        "direktur",
    }
)

# Decisive instruments SHORT enough to appear by accident. These keep their
# decisive status — one hit still settles the lane — but only when the lane
# carries at least one other marker.
#
# The rest of `_DECISIVE` needs no corroboration: nobody writes `kitas`,
# `b211a`, `npwp` or `hak guna bangunan` by chance. These do get written by
# chance, in exactly one shape: an address. "Villa C2, Jalan Raya" and "Blok
# D12" are how this island writes where you live.
_NEEDS_CORROBORATION: frozenset[str] = frozenset(
    {"c1", "c2", "c7", "c12", "c22", "d12", "e23", "e31", "ahu", "shm", "ajb"}
)

# Negative context: a marker is dropped when it sits next to one of these.
# Keyed by marker, each value is a set of words that must NOT appear within
# `_NEG_WINDOW` characters of the hit.
_NEG_WINDOW = 40
_NEGATIVE_CONTEXT: dict[str, frozenset[str]] = {
    # "Payment by Visa card" is not an immigration question.
    "visa": frozenset({"card", "mastercard", "amex", "debit", "credit",
                       "carta", "kartu", "карта"}),
    # "the villa's wifi password" is admin noise, not a property transaction;
    # but "villa" next to a title word stays in the property lane.
    "villa": frozenset({"wifi", "password", "checkin", "check-in", "towel",
                        "cleaning"}),
    # An "akta" in "akta kelahiran" (birth certificate) is a personal document,
    # not a company deed.
    "akta": frozenset({"kelahiran", "kematian", "nikah", "cerai"}),
}

_LANG_STOPWORDS: dict[str, tuple[str, ...]] = {
    "it": ("il", "lo", "la", "gli", "che", "per", "non", "sono", "della",
           "grazie", "buongiorno", "cordiali", "saluti", "vorrei", "come"),
    "id": ("dan", "yang", "untuk", "saya", "dengan", "tidak", "adalah",
           "terima", "kasih", "mohon", "bapak", "ibu", "bisa", "kami"),
    "en": ("the", "and", "for", "you", "with", "would", "please", "thanks",
           "regards", "dear", "could", "about", "have", "your"),
}

_WORD_CACHE: dict[str, re.Pattern[str]] = {}


def _word_pattern(marker: str) -> re.Pattern[str]:
    """Compile a word-boundary pattern for `marker`, cached.

    `\\b` alone is wrong at a non-word edge, and several markers contain
    hyphens or spaces ("e-visa", "hak milik"), so the boundary is expressed as
    "not flanked by a letter, digit or underscore". Interior whitespace is
    allowed to stretch, because a subject line wraps.
    """
    cached = _WORD_CACHE.get(marker)
    if cached is not None:
        return cached
    parts = [re.escape(p) for p in marker.split()]
    body = r"\s+".join(parts)
    pattern = re.compile(rf"(?<![\w]){body}(?![\w])", re.IGNORECASE)
    _WORD_CACHE[marker] = pattern
    return pattern


def normalize(text: str) -> str:
    """Lowercase, unify quote glyphs, collapse whitespace.

    Deliberately does NOT strip accents: markers carry both spellings, and
    silently folding "società" into "societa" would make the marker list lie
    about what it matches.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFC", text)
    out = out.replace("’", "'").replace("‘", "'")
    out = out.replace("“", '"').replace("”", '"')
    out = re.sub(r"\s+", " ", out)
    return out.strip().lower()


def _suppressed(haystack: str, marker: str, at: int) -> bool:
    """True when a negative-context word sits within the window of a hit."""
    forbidden = _NEGATIVE_CONTEXT.get(marker)
    if not forbidden:
        return False
    lo = max(0, at - _NEG_WINDOW)
    window = haystack[lo : at + len(marker) + _NEG_WINDOW]
    return any(_word_pattern(word).search(window) for word in forbidden)


def _lane_is_credible(hits: list[str]) -> bool:
    """Does this lane hold at least one marker worth acting on?

    Two ways to fail, and the second was learned by getting it wrong: denying
    an uncorroborated `C2` the DECISIVE path is not enough, because it then
    falls through to the count path and wins there instead — a lane of one
    two-character token beats a runner-up that has just stepped aside. Closing
    a hole in one path moves it to the other unless the same judgement is
    applied to both.

    So a marker counts here only when it is neither coincidence-grade prose
    (`_WEAK`) nor a short permit index standing on its own
    (`_NEEDS_CORROBORATION` with nothing else in the lane).
    """
    for marker in hits:
        if marker in _WEAK:
            continue
        if marker in _NEEDS_CORROBORATION and len(hits) == 1:
            continue
        return True
    return False


def _hits(haystack: str, intent: Intent) -> list[str]:
    """Distinct markers of `intent` present in `haystack`, minus suppressions."""
    found: list[str] = []
    for marker in _MARKERS[intent]:
        match = _word_pattern(marker).search(haystack)
        if match is None:
            continue
        if _suppressed(haystack, marker, match.start()):
            logger.debug("marker suppressed by negative context: %r", marker)
            continue
        found.append(marker)
    return found


def detect_language(text: str) -> str:
    """Best-effort language of the body: it | id | en | ru.

    Script first (Cyrillic is decisive), then stopword frequency. Returns "en"
    on a tie or on too little text — a wrong-but-declared default beats a
    confident guess, and the drafting step re-reads the client's own language
    from the thread anyway.
    """
    if not text:
        return "en"
    if len(re.findall(r"[Ѐ-ӿ]", text)) >= 4:
        return "ru"
    norm = normalize(text)
    scores = {
        lang: sum(1 for w in words if _word_pattern(w).search(norm))
        for lang, words in _LANG_STOPWORDS.items()
    }
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "en"
    # A tie between it/id and en resolves to the non-English candidate: the
    # English stopword list overlaps loan words in both, so en over-scores.
    ties = [lang for lang, sc in scores.items() if sc == scores[best]]
    if len(ties) > 1 and "en" in ties:
        non_en = [lang for lang in ties if lang != "en"]
        return non_en[0]
    return best


def is_bulk(headers: dict[str, str] | None) -> bool:
    """Structural bulk detection. Headers are entities; prose is not."""
    if not headers:
        return False
    lowered = {k.lower(): (v or "") for k, v in headers.items()}
    if lowered.get("list-unsubscribe"):
        return True
    if lowered.get("precedence", "").lower() in {"bulk", "list", "junk"}:
        return True
    if lowered.get("auto-submitted", "").lower() not in {"", "no"}:
        return True
    if lowered.get("x-mailer", "").lower().startswith("mailchimp"):
        return True
    sender = lowered.get("from", "").lower()
    return bool(re.search(r"(?<![\w])(no-?reply|donotreply|noreply)(?![\w])", sender))


@dataclass(frozen=True)
class Classification:
    """Routing verdict. `markers` is kept for auditability, not for display."""

    intent: Intent
    language: str
    folder: str | None
    bulk: bool
    decisive: bool
    markers: dict[str, list[str]] = field(default_factory=dict)

    @property
    def routable(self) -> bool:
        """Whether the loop may move this message without asking."""
        return self.intent is not Intent.UNKNOWN and self.folder is not None


def classify(
    subject: str,
    body: str,
    *,
    headers: dict[str, str] | None = None,
) -> Classification:
    """Route one message.

    Order matters and is deliberate:
      1. structural bulk -> NOISE (a newsletter mentioning "tax" is noise).
      2. a decisive instrument -> its lane, regardless of how many soft
         markers another lane collected.
      3. otherwise, the lane with the most distinct markers; a tie or a blank
         score is UNKNOWN, which the loop leaves in the inbox untouched.
      4. and a lane that won on WEAK markers only is UNKNOWN too, however
         lopsided the count: beating a runner-up of zero proves nothing when
         the winning token is the word every invoice already contains.

    UNKNOWN is a first-class answer, not a failure: routing a message we do
    not understand is worse than leaving it where a human will see it.
    """
    hay = normalize(f"{subject}\n{body}")
    language = detect_language(body or subject)

    if is_bulk(headers):
        return Classification(
            intent=Intent.NOISE,
            language=language,
            folder=FOLDER_BY_INTENT[Intent.NOISE],
            bulk=True,
            decisive=True,
            markers={},
        )

    per_lane = {intent: _hits(hay, intent) for intent in _MARKERS}
    per_lane = {k: v for k, v in per_lane.items() if v}

    for intent, decisive_set in _DECISIVE.items():
        hit = [m for m in per_lane.get(intent, []) if m in decisive_set]
        if not hit:
            continue
        # A short alphanumeric permit index needs a second opinion. `C2` and
        # `D12` decide a lane on one hit, and they are also how Bali writes an
        # address ("Villa C2, Jalan Raya"), a spreadsheet cell and an invoice
        # line reference. Corroboration costs nothing on real mail — measured
        # over 106 live messages, `c1` fired 15 times and NEVER alone, `pma`
        # 3 of 3 — so requiring another marker in the same lane closes the
        # address case without losing a single real routing.
        if all(marker in _NEEDS_CORROBORATION for marker in hit):
            others = [m for m in per_lane[intent] if m not in hit]
            if not others:
                logger.debug(
                    "decisive %s in lane %s stands alone — not corroborated",
                    hit,
                    intent.value,
                )
                continue
        return Classification(
            intent=intent,
            language=language,
            folder=FOLDER_BY_INTENT[intent],
            bulk=False,
            decisive=True,
            markers={k.value: v for k, v in per_lane.items()},
        )

    # Drop weak-only lanes BEFORE ranking, not after choosing a winner.
    #
    # Filtering afterwards was a real defect, caught by adversarial review with
    # a measured case: "I need help with a work permit... could we set a meeting
    # or an appointment next week?" gives {visa: [work permit], admin:
    # [appointment, meeting]}. ADMIN wins the count 2-1, its hits are all weak,
    # and a post-hoc check then collapsed the WHOLE verdict to UNKNOWN —
    # discarding `work permit`, a strong marker in the lane that was right.
    #
    # A weak-only lane must step ASIDE, not poison the message. UNKNOWN is then
    # what happens when nothing non-weak survives anywhere, which is what the
    # comment above `_WEAK` always claimed and what the code now does.
    considered = {
        intent: hits for intent, hits in per_lane.items() if _lane_is_credible(hits)
    }
    if len(considered) != len(per_lane):
        logger.debug(
            "weak-only lanes stepped aside: %s",
            sorted(lane.value for lane in per_lane.keys() - considered.keys()),
        )

    if not considered:
        return Classification(
            intent=Intent.UNKNOWN,
            language=language,
            folder=None,
            bulk=False,
            decisive=False,
            markers={k.value: v for k, v in per_lane.items()},
        )

    ranked = sorted(considered.items(), key=lambda kv: (-len(kv[1]), kv[0].value))
    top_intent, top_hits = ranked[0]
    if len(ranked) > 1 and len(ranked[1][1]) == len(top_hits):
        # Ambiguous on soft markers only: refuse to guess.
        return Classification(
            intent=Intent.UNKNOWN,
            language=language,
            folder=None,
            bulk=False,
            decisive=False,
            markers={k.value: v for k, v in per_lane.items()},
        )

    return Classification(
        intent=top_intent,
        language=language,
        folder=FOLDER_BY_INTENT[top_intent],
        bulk=False,
        decisive=False,
        markers={k.value: v for k, v in per_lane.items()},
    )
