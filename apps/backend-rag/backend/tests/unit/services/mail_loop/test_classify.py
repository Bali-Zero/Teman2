"""Corpus for the mail-loop router: guilt AND innocence, per lane, per language.

Structure follows the superscar #3 antidote. A guard merged with only guilt
rows is half a guard, so every lane carries:

    guilt      — a real message that MUST route to the lane
    innocence  — a message containing the lane's marker as a SUBSTRING of an
                 ordinary word, or in a negative context, that must NOT route

The innocence half is GENERATED, not hand-picked, and that decision has a
history worth keeping. The first version of this file carried five hand-written
substring traps ("please" contains "lease", "quota" contains "ota", "different"
contains "rent", ...). A mutation check — disable the word-boundary matcher and
demand the corpus go red — showed that only two of the five actually depended
on the defence. The other three passed for a reason that had nothing to do with
the matcher: the marker list never contained a bare `lease`, `ota` or `rent`, so
the trap was not present to be sprung. A corpus written to detect superscar #3
had superscar #3.

So the innocence rows are now derived by CROSSING the real marker table with a
list of ordinary words, and keeping every pair where a marker genuinely hides
inside an ordinary word. That corpus grows by itself the day someone adds a
short bare marker, which is exactly when it is needed — and it cannot go
vacuous, because `test_landmine_corpus_is_not_empty` fails if the crossing
yields nothing (a blind sweep that traverses zero cases is not "clean").
"""

from __future__ import annotations

import pytest

from backend.services.mail_loop.classify import (
    _DECISIVE,
    _MARKERS,
    _NEEDS_CORROBORATION,
    _WEAK,
    Intent,
    classify,
    detect_language,
    is_bulk,
    normalize,
)

# --------------------------------------------------------------------------- #
# GUILT: these must route.                                                    #
# --------------------------------------------------------------------------- #

GUILT: list[tuple[str, str, str, Intent]] = [
    # id, subject, body, expected
    (
        "visa-en-kitas",
        "KITAS renewal",
        "My KITAS expires next month, what do you need from me to extend it?",
        Intent.VISA,
    ),
    (
        "visa-it-visto",
        "Rinnovo visto",
        "Buongiorno, vorrei rinnovare il mio permesso di soggiorno, cosa serve?",
        Intent.VISA,
    ),
    (
        "visa-id-izin",
        "Perpanjangan izin tinggal",
        "Mohon informasi untuk perpanjangan izin tinggal saya, terima kasih.",
        Intent.VISA,
    ),
    (
        "visa-ru",
        "Виза",
        "Здравствуйте, мне нужна помощь с визой и разрешением на работу.",
        Intent.VISA,
    ),
    (
        "ptpma-kbli",
        "KBLI for my new company",
        "Which KBLI covers frozen food distribution for a PT PMA?",
        Intent.PT_PMA,
    ),
    (
        "ptpma-it",
        "Costituzione societa",
        "Vorrei aprire una societa in Indonesia, quali sono i soci necessari?",
        Intent.PT_PMA,
    ),
    (
        "tax-coretax",
        "Coretax access",
        "I cannot log into Coretax to file my SPT, can you check my NPWP?",
        Intent.TAX,
    ),
    (
        "tax-it",
        "Tasse annuali",
        "Buongiorno, come funziona la dichiarazione dei redditi qui? Grazie.",
        Intent.TAX,
    ),
    (
        "property-hakpakai",
        "Hak pakai question",
        "Can a foreigner hold hak pakai on a plot in Canggu?",
        Intent.PROPERTY,
    ),
    (
        "property-leasehold",
        "Villa leasehold duration",
        "How long is a typical villa leasehold in Bali? Looking at a title deed.",
        Intent.PROPERTY,
    ),
    (
        "admin-invoice",
        "Invoice for last month",
        "Please send the invoice, I will do the bank transfer tomorrow.",
        Intent.ADMIN,
    ),
]


@pytest.mark.parametrize(
    ("case_id", "subject", "body", "expected"),
    GUILT,
    ids=[row[0] for row in GUILT],
)
def test_guilt_routes_to_lane(
    case_id: str, subject: str, body: str, expected: Intent
) -> None:
    result = classify(subject, body)
    assert result.intent is expected, (
        f"{case_id}: expected {expected.value}, got {result.intent.value} "
        f"(markers={result.markers})"
    )
    assert result.folder is not None
    assert result.routable is True


# --------------------------------------------------------------------------- #
# INNOCENCE: the lane's marker appears, but the message is NOT that lane.      #
# --------------------------------------------------------------------------- #

# Ordinary words a client plausibly writes, chosen because each one swallows a
# short token. Extend this list freely: every addition that hides a marker
# becomes a new innocence case for free.
ORDINARY_WORDS: tuple[str, ...] = (
    "please", "boss", "taxi", "quota", "different", "current", "across",
    "biota", "message", "status", "context", "estate", "translate", "syntax",
    "relax", "maximum", "possible", "available", "invitation", "situation",
    "vitality", "advisable", "reliable", "revisable", "supervisa",
    "приватный", "визажист", "societario", "assistenza", "kualitas",
    "fasilitas", "aktivitas", "prioritas", "universitas",
)


def _landmines() -> list[tuple[Intent, str, str]]:
    """Marker x ordinary-word pairs where the marker hides inside the word.

    Multi-token markers are skipped: a phrase cannot be swallowed by a single
    word, so they carry no substring risk.
    """
    found: list[tuple[Intent, str, str]] = []
    for intent, markers in _MARKERS.items():
        for marker in markers:
            if " " in marker or "-" in marker:
                continue
            for word in ORDINARY_WORDS:
                low = word.lower()
                if marker != low and marker in low:
                    found.append((intent, marker, word))
    return found


LANDMINES = _landmines()


def test_landmine_corpus_is_not_empty() -> None:
    """Blind-sweep guard: zero cases traversed is not the same as clean.

    If a refactor empties the marker table or the word list, the generated
    innocence suite below would silently become a no-op and report green. This
    fails loudly instead.
    """
    assert len(LANDMINES) >= 5, (
        "the marker x ordinary-word crossing produced almost nothing; "
        "the generated innocence suite is not actually testing anything"
    )


@pytest.mark.parametrize(
    ("intent", "marker", "word"),
    LANDMINES,
    ids=[f"{i.value}-{m}-in-{w}" for i, m, w in LANDMINES],
)
def test_generated_innocence_ordinary_word_does_not_route(
    intent: Intent, marker: str, word: str
) -> None:
    """An ordinary word that merely CONTAINS a marker must not route to its lane.

    This is the whole of superscar #3 in one assertion, and it is generated, so
    it covers the markers that exist today rather than the five a human happened
    to think of.
    """
    body = f"Hello, {word} — {word} again, thanks."
    result = classify("Quick question", body)
    assert result.intent is not intent, (
        f"'{word}' over-matched into {intent.value} via the buried marker "
        f"'{marker}' (markers={result.markers})"
    )


# Negative-context rows. Each asserts its PREMISE too: without the suppression
# the lane would genuinely have won. A row that passes because two lanes tied is
# proving nothing about suppression (W105: check the premise, or the green is an
# accident).

NEGATIVE_CONTEXT: list[tuple[str, str, str, Intent]] = [
    (
        "visa-card-is-not-immigration",
        "Payment method",
        "Can I pay by Visa card, or is that not possible?",
        Intent.VISA,
    ),
    (
        "akta-kelahiran-is-not-company-deed",
        "Documents for my dependent",
        "I have the akta kelahiran of my daughter, is that enough?",
        Intent.PT_PMA,
    ),
]

# `villa` is deliberately NOT in the list above, and the reason is worth keeping
# because it looks like an omission.
#
# The rows above are VERDICT-level: they assert the lane loses, and the premise
# check below proves the lane would otherwise have won — which is what stops a
# row from passing for an unrelated reason. That construction needs the marker
# to be strong enough to carry the lane on its own.
#
# `villa` is a WEAK marker (see `_WEAK`), so it can never carry a lane by
# itself, suppressed or not. A verdict-level row for it would read UNKNOWN on
# both sides: green forever, and green for a reason that has nothing to do with
# suppression — the exact vacuity the premise check exists to catch. It caught
# it, the day `villa` became weak.
#
# What the suppression still does for `villa` is remove it from the marker
# list, which is what breaks ties and what a strong marker in the same lane is
# added to. So it is tested THERE, at the level where it still bites.


def test_villa_suppression_bites_at_the_marker_level() -> None:
    """GUILT: housekeeping context strips `villa` out of the property lane."""
    result = classify(
        "Wifi",
        "The villa wifi password does not work, can someone send the new one?",
    )
    assert "villa" not in result.markers.get("property", [])
    assert result.intent is not Intent.PROPERTY


def test_villa_survives_without_housekeeping_context() -> None:
    """INNOCENCE: the same word, no housekeeping nearby, is still a marker.

    Without this half, deleting the `villa` entry from `_MARKERS` altogether
    would make the guilt test above pass, which is not what it claims to prove.
    """
    result = classify(
        "Purchase",
        "We are considering a villa and would like to understand the options.",
    )
    assert "villa" in result.markers.get("property", [])


@pytest.mark.parametrize(
    ("case_id", "subject", "body", "forbidden"),
    NEGATIVE_CONTEXT,
    ids=[row[0] for row in NEGATIVE_CONTEXT],
)
def test_negative_context_suppresses_lane(
    case_id: str, subject: str, body: str, forbidden: Intent
) -> None:
    result = classify(subject, body)
    assert result.intent is not forbidden, (
        f"{case_id}: negative context did not suppress {forbidden.value} "
        f"(markers={result.markers})"
    )


@pytest.mark.parametrize(
    ("case_id", "subject", "body", "forbidden"),
    NEGATIVE_CONTEXT,
    ids=[f"premise-{row[0]}" for row in NEGATIVE_CONTEXT],
)
def test_negative_context_premise_holds(
    case_id: str, subject: str, body: str, forbidden: Intent
) -> None:
    """Premise check: with suppression disabled, the lane WOULD have won.

    Without this, a suppression row can pass because some other lane tied for
    first place, and the test would keep reporting green after the suppression
    itself was deleted.
    """
    from backend.services.mail_loop import classify as module

    original = module._suppressed
    module._suppressed = lambda haystack, marker, at: False  # type: ignore[assignment]
    try:
        unsuppressed = classify(subject, body)
    finally:
        module._suppressed = original  # type: ignore[assignment]

    assert unsuppressed.intent is forbidden, (
        f"{case_id}: premise broken — with suppression OFF the verdict was "
        f"{unsuppressed.intent.value}, not {forbidden.value}, so the row above "
        f"is not actually testing suppression (markers={unsuppressed.markers})"
    )


# --------------------------------------------------------------------------- #
# Decisive instruments beat soft-marker volume.                                #
# --------------------------------------------------------------------------- #


def test_decisive_instrument_wins_over_soft_marker_volume() -> None:
    """One KITAS beats three admin words.

    A client writing about their permit while also mentioning the invoice and
    the meeting must land in the visa lane: the instrument is an entity, the
    admin words are context.
    """
    result = classify(
        "KITAS + invoice",
        "About my KITAS extension. Also send the invoice and let us set a meeting.",
    )
    assert result.intent is Intent.VISA
    assert result.decisive is True


def test_ambiguous_soft_markers_refuse_to_guess() -> None:
    """A soft tie is UNKNOWN, and UNKNOWN is left in the inbox.

    Routing a message we do not understand is worse than leaving it visible.

    Both lanes must be tied on NON-weak markers for this to be the property it
    claims. The original example paired `immigration` against `taxes`, and once
    weak-only lanes began stepping aside it stopped being a tie at all — the tax
    lane withdrew and `immigration` decided, correctly. The property survived;
    only the example had quietly stopped exercising it.
    """
    result = classify("Hello", "A question about immigration and about a leasehold.")
    assert result.markers == {"visa": ["immigration"], "property": ["leasehold"]}, (
        "premise: this must be a 1-1 tie between two lanes that both carry a "
        "non-weak marker, or the test is measuring something else"
    )
    assert result.intent is Intent.UNKNOWN
    assert result.folder is None
    assert result.routable is False


def test_empty_message_is_unknown_not_noise() -> None:
    """Silence is not a newsletter."""
    result = classify("", "")
    assert result.intent is Intent.UNKNOWN
    assert result.routable is False


# --------------------------------------------------------------------------- #
# Bulk detection is structural.                                                #
# --------------------------------------------------------------------------- #


def test_bulk_header_wins_over_business_markers() -> None:
    """A newsletter that mentions KITAS is still a newsletter."""
    result = classify(
        "Immigration news: new KITAS rules",
        "Read our roundup on KITAS and NPWP changes this month.",
        headers={"List-Unsubscribe": "<https://x.example/u>"},
    )
    assert result.intent is Intent.NOISE
    assert result.bulk is True


@pytest.mark.parametrize(
    "headers",
    [
        {"List-Unsubscribe": "<mailto:u@x.example>"},
        {"Precedence": "bulk"},
        {"Auto-Submitted": "auto-generated"},
        {"From": "no-reply@notifications.example.com"},
        {"From": "NoReply@Example.com"},
    ],
)
def test_bulk_positive(headers: dict[str, str]) -> None:
    assert is_bulk(headers) is True


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {},
        {"From": "sofia@client.example.com"},
        {"Auto-Submitted": "no"},
        {"Precedence": "normal"},
        # "reply" is a substring of "no-reply" but this is a real human address:
        # the boundary matters in the header check too.
        {"From": "replies.team@client.example.com"},
    ],
)
def test_bulk_negative(headers: dict[str, str] | None) -> None:
    assert is_bulk(headers) is False


# --------------------------------------------------------------------------- #
# Language.                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Buongiorno, vorrei sapere come funziona per la mia societa. Grazie.", "it"),
        ("Mohon informasi untuk saya dan keluarga saya, terima kasih.", "id"),
        ("Dear team, could you please confirm the timeline? Thanks and regards.", "en"),
        ("Здравствуйте, мне нужна помощь с документами и визой.", "ru"),
        ("", "en"),
        ("ok", "en"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_normalize_keeps_accents_and_folds_quotes() -> None:
    """Accents survive normalisation; curly quotes do not.

    Folding accents here would make the marker list lie: "societa" and
    "societa'" are listed separately on purpose (W105/W77).
    """
    out = normalize("  Società   ’Rinnovo’  ")
    assert "società" in out
    assert "'rinnovo'" in out
    assert "  " not in out


# --------------------------------------------------------------------------- #
# A lane that won on WEAK markers only does not route.                        #
#                                                                             #
# Measured, not imagined: before this rule, one live run routed 7 messages    #
# and SIX of them rested on a single soft marker — five on `tax`, one on      #
# `meeting` — with no decisive instrument anywhere. `tax` is the word every   #
# invoice footer already contains, so "mentions tax" was filing a client's    #
# mail on the strength of a vendor's small print.                             #
#                                                                             #
# Guilt AND innocence, per the superscar #3 antidote: a rule that only ever   #
# refuses is not a router, and the innocence half is what stops the next      #
# person from "fixing" a quiet lane by widening the weak set.                 #
# --------------------------------------------------------------------------- #


def test_weak_marker_alone_does_not_route() -> None:
    """A vendor invoice mentioning tax is not a tax enquiry.

    This is the exact live shape: `tax` hits, every other lane scores zero, and
    the old count path routed on a landslide of one.
    """
    result = classify(
        "Your monthly statement",
        "Total due: 100 EUR, tax included. Thank you for your business.",
    )
    assert result.intent is Intent.UNKNOWN
    assert result.folder is None
    assert result.routable is False
    # The evidence is still reported — refusing to act on a marker is not the
    # same as pretending it was not there.
    assert "tax" in result.markers.get("tax", [])


def test_scheduling_language_alone_does_not_route() -> None:
    """"Can we set a meeting?" inside a substantive email is not admin.

    The sentence appears at the end of visa, tax and company questions alike.
    Routing on it moves the real question out of sight.
    """
    result = classify("Quick question", "Could we set a meeting next week?")
    assert result.intent is Intent.UNKNOWN
    assert result.routable is False


def test_weak_plus_strong_in_the_same_lane_still_routes() -> None:
    """INNOCENCE: the rule refuses weak-ONLY, never weak-as-well."""
    result = classify(
        "Filing",
        "Please prepare the annual return; the tax due is not yet clear to me.",
    )
    assert result.intent is Intent.TAX
    assert result.routable is True
    assert result.decisive is False


def test_strong_marker_alone_still_routes() -> None:
    """INNOCENCE: one non-weak marker is enough, as it always was.

    Nobody writes "work permit" by accident, which is the whole distinction
    this rule turns on.
    """
    result = classify("Question", "I need help with a work permit for my staff.")
    assert result.intent is Intent.VISA
    assert result.routable is True


def test_decisive_instrument_is_never_blocked_by_the_weak_rule() -> None:
    """INNOCENCE: the decisive path runs first and is untouched.

    A message carrying NPWP and nothing else routes, even though `tax` — the
    weak word — is absent. The rule must not have become a second gate in
    front of the instruments.
    """
    result = classify("Registration", "Attached is the NPWP for the company.")
    assert result.intent is Intent.TAX
    assert result.decisive is True
    assert result.routable is True


def test_weak_markers_still_score() -> None:
    """A weak marker is demoted, not deleted.

    Two markers in one lane — one weak, one strong — must beat a single strong
    marker in another. If weak hits stopped counting, this would tie and the
    tie-breaker would refuse.
    """
    result = classify(
        "Mixed",
        "About the tax return, and separately please send the invoice.",
    )
    assert result.intent is Intent.TAX
    assert result.routable is True


def test_weak_set_contains_no_phantom_markers() -> None:
    """Every weak token must be a marker that actually exists (W65).

    A weak entry naming a token no lane carries is dead text: it looks like a
    defence, defends nothing, and quietly survives a rename of the real marker.
    """
    known = {marker for markers in _MARKERS.values() for marker in markers}
    phantom = sorted(_WEAK - known)
    assert phantom == [], f"weak markers absent from _MARKERS: {phantom}"


def test_no_marker_is_both_decisive_and_weak() -> None:
    """The two sets make opposite claims about the same token.

    `_DECISIVE` says "one hit settles it"; `_WEAK` says "one hit settles
    nothing". A token in both would be a contradiction the decisive path wins
    by accident of ordering, which is not a decision anybody made.
    """
    decisive = {token for tokens in _DECISIVE.values() for token in tokens}
    both = sorted(decisive & _WEAK)
    assert both == [], f"markers claimed as decisive AND weak: {both}"


# --------------------------------------------------------------------------- #
# A weak-only lane steps ASIDE. It does not poison the message.               #
#                                                                             #
# All of the following were found by adversarial review of the first version  #
# of this rule, each with a measured case. The defect was placement: the check #
# ran AFTER the winner was chosen, so a lane made entirely of coincidence      #
# could win the count and then collapse the whole verdict to UNKNOWN — taking  #
# a strong marker in a losing lane down with it.                              #
# --------------------------------------------------------------------------- #


def test_a_weak_lane_does_not_drag_down_a_strong_one() -> None:
    """The case the first version got wrong, verbatim.

    ADMIN wins the raw count 2-1 on `appointment` + `meeting`, both weak. VISA
    holds `work permit`, which is not. Withdrawing ADMIN must leave VISA, not
    UNKNOWN — anything else discards the one marker that was actually right.
    """
    result = classify(
        "Question",
        "I need help with a work permit for my staff. Could we set a meeting "
        "or an appointment next week?",
    )
    assert result.markers["admin"] == ["appointment", "meeting"], "premise: admin wins the count"
    assert result.intent is Intent.VISA
    assert result.routable is True


def test_two_weak_lanes_and_one_strong_still_resolves() -> None:
    """Withdrawal is not a tie-breaker of last resort — it applies per lane."""
    result = classify(
        "Mixed",
        "About the leasehold on the land. Also the tax, and let us set a meeting.",
    )
    assert result.intent is Intent.PROPERTY
    assert result.routable is True


def test_everything_weak_is_still_unknown() -> None:
    """GUILT survives the reorder: nothing non-weak anywhere means UNKNOWN."""
    result = classify(
        "Statement",
        "Total due: 100 EUR, tax included. Shall we set a meeting to discuss?",
    )
    assert result.intent is Intent.UNKNOWN
    assert result.routable is False


# --------------------------------------------------------------------------- #
# Short decisive codes need a second opinion.                                 #
# --------------------------------------------------------------------------- #


def test_a_permit_index_inside_an_address_does_not_decide_a_lane() -> None:
    """GUILT: `C2` is a visa index AND how this island writes an address.

    The decisive path returns before every other check, so an uncorroborated
    two-character hit moved mail with nothing to appeal to.
    """
    result = classify(
        "Delivery",
        "Please deliver the documents to Villa C2, Jalan Raya, before Friday.",
    )
    assert result.intent is not Intent.VISA
    assert result.decisive is False


def test_a_corroborated_permit_index_still_decides() -> None:
    """INNOCENCE, and the reason this costs nothing.

    Measured over 106 live messages: `c1` fired 15 times and never once alone.
    Real visa mail names the index beside something else, so corroboration
    removes the address case without losing a routing.
    """
    result = classify(
        "Application",
        "We are applying for a C1 visa and need the sponsor letter.",
    )
    assert result.intent is Intent.VISA
    assert result.decisive is True


def test_long_instruments_never_need_corroboration() -> None:
    """INNOCENCE: nobody writes `kitas` or `npwp` by accident.

    Without this, widening `_NEEDS_CORROBORATION` to the whole decisive set
    would pass the guilt case above while gutting the lane.
    """
    assert classify("X", "About my KITAS.").decisive is True
    assert classify("X", "Attached is the NPWP.").decisive is True


def test_corroboration_set_is_a_subset_of_decisive() -> None:
    """A corroboration rule naming a non-decisive token guards nothing (W65)."""
    decisive = {token for tokens in _DECISIVE.values() for token in tokens}
    phantom = sorted(_NEEDS_CORROBORATION - decisive)
    assert phantom == [], f"corroboration named for non-decisive tokens: {phantom}"


# --------------------------------------------------------------------------- #
# Homographs: the marker IS the ordinary word, not a substring of it.         #
#                                                                             #
# The generated landmine corpus at the top of this file cannot reach these.   #
# `_landmines()` keeps pairs where `marker in low and marker != low`, a STRICT #
# substring — so a marker that equals a whole ordinary word is structurally    #
# outside the sweep. That is exactly the class `_WEAK` exists for, which is    #
# why these are written by hand.                                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("case_id", "body", "forbidden"),
    [
        ("ho-visto-means-i-saw", "Buongiorno, ho visto il vostro sito e vorrei informazioni.", Intent.VISA),
        ("ci-siamo-visti-means-we-met", "Ci siamo visti la settimana scorsa in ufficio.", Intent.VISA),
        ("tanah-lot-is-a-landmark", "Company outing to Tanah Lot next month, who is coming?", Intent.PROPERTY),
        ("direktur-is-a-signature", "Salam,\nBudi Santoso\nDirektur Utama", Intent.PT_PMA),
        ("imposte-are-also-shutters", "Le imposte delle finestre sono rotte, chi le ripara?", Intent.TAX),
        ("fiscal-year-is-boilerplate", "Summary for the fiscal year ending 31 December.", Intent.TAX),
        ("a-call-link-is-furniture", "Here is my zoom link for later, talk soon.", Intent.ADMIN),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_homograph_does_not_route(case_id: str, body: str, forbidden: Intent) -> None:
    result = classify("", body)
    assert result.intent is not forbidden, (
        f"{case_id}: routed to {forbidden.value} on a homograph "
        f"(markers={result.markers})"
    )


def test_the_recall_cost_of_the_weak_set_is_visible() -> None:
    """The bill for all of the above, written down where it cannot be ignored.

    These are real enquiries that USED to route and now sit in the inbox. That
    is the deliberate trade — a message left visible costs a human one glance,
    a message filed wrongly costs them the message. Anyone widening `_WEAK`
    further should have to update this list and see what they are buying.
    """
    stays_in_inbox = [
        "We are looking to buy a villa in Ubud, what are the options?",
        "Vorrei informazioni su come ottenere un visto.",
        "Domanda sul soggiorno a Bali.",
        "Question about the OSS system.",
    ]
    for body in stays_in_inbox:
        assert classify("", body).routable is False, body
