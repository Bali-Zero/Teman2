"""The abstain gate must not be decided by the language the question is in.

Spec: research/operations/2026-09-01-wa-evidence-relevance-cross-language-spec.md

Measured before the cure, on the live scorer: the SAME question against the SAME
catalogue entry scored **0.08 with English context and 0.80 with Indonesian
context**, and symmetrically the other way. A factor of ten decided by language
alone, against a 0.15 threshold. And 0.08 is not a low relevance score — it is
the "no semantic relevance" branch.

WHAT SHIPS HERE, AND WHAT DOES NOT
-----------------------------------
The spec asks for two things. This file tests the one that shipped and pins the
one that did not as a MEASURED, DECLARED residual — not as a silent gap.

SHIPPED (criterion 2): the keyword filter is vocabulary-aware, so `PT`, `PMA`,
`NIB` and `OSS` survive extraction. This is more than a token-count fix: a
business identifier is spelled the same in every language, so it is the natural
bridge between an Indonesian question and an English chunk.

NOT SHIPPED (the retrieval-primary inversion): built on this branch, then
withdrawn. It regressed eleven standing abstain tripwires — nine let an
off-topic query clear the gate on cosine alone, and one newly discarded a
perfect lexical match. Those nine are pinned to cosines a real embedding does
not produce (measured on `text-embedding-3-small`, 2026-09-03: "quantum physics
theory" vs KBLI text = **0.038**, fixture 0.90; an Indonesian KBLI question vs
D12-visa text = **0.155**, fixture 0.91), so the DESIGN is sound and the
FIXTURES are the fiction — but correcting nine safety tripwires is its own
reviewable change, and criterion 3 says in terms that they are the floor and may
not be weakened to let a new metric pass.
"""

from __future__ import annotations

import pytest

from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic.reasoning_utils import (
    _SHORT_IDENTIFIERS,
    calculate_evidence_score,
)

RETRIEVAL = [{"score": 0.72}]
POOR_RETRIEVAL = [{"score": 0.18}]

EN_CONTEXT = [
    "PT PMA company setup — foreign-owned limited liability company "
    "registration, including deed, ministry approval, NPWP tax number and NIB "
    "business identification number via OSS. Price: IDR 20,000,000 all inclusive."
]
ID_CONTEXT = [
    "Pendirian PT PMA — pendaftaran perusahaan penanaman modal asing, termasuk "
    "akta notaris, pengesahan kementerian, NPWP dan NIB melalui OSS. "
    "Harga: IDR 20.000.000 sudah termasuk semuanya."
]
# A poor retrieval must be paired with the text it actually returned. Pairing a
# low cosine with rich on-topic context is a shape production cannot produce —
# the context IS the retrieved chunks — and an early draft of this file did
# exactly that, then read the resulting score as a hole in the cure. The fixture
# was the defect.
UNRELATED_CONTEXT = [
    "Scooter and motorbike rental in Canggu: daily and monthly rates, helmet "
    "included, delivery to your villa."
]


class TestTheEntityIsNoLongerThrownAway:
    """Criterion 2. A rule keyed on token LENGTH cannot express "keep the
    entity"; this one is keyed on vocabulary."""

    @pytest.mark.parametrize("identifier", ["pt", "pma", "nib", "oss", "spt", "hgb"])
    def test_a_short_business_identifier_is_kept(self, identifier: str) -> None:
        assert identifier in _SHORT_IDENTIFIERS

    @pytest.mark.parametrize("already_safe", ["npwp", "kitas", "e28a", "kbli"])
    def test_a_four_character_identifier_never_needed_the_allowlist(
        self, already_safe: str
    ) -> None:
        """These survived the old filter by an accident of length. Recording it
        so nobody reads the allowlist as "the identifiers that matter"."""
        assert len(already_safe) > 3

    def test_naming_the_entity_now_beats_a_bare_price_question(self) -> None:
        """"Harga PT PMA berapa all in?" used to reduce to `harga` and `berapa`
        — the two most generic words in it, the subject gone."""
        entity = calculate_evidence_score(RETRIEVAL, EN_CONTEXT, "Harga PT PMA berapa?")
        generic = calculate_evidence_score(RETRIEVAL, EN_CONTEXT, "Harga berapa?")
        assert entity > generic, (
            "naming PT PMA against an ENGLISH chunk must count for more than a "
            "bare price question — the identifier is the cross-language bridge"
        )


class TestTheCrossLanguageCasesThatCarryAnIdentifier:
    """The measured defect, on the cases the shipped half cures."""

    CASES = [
        ("Harga PT PMA berapa all in?", "an Indonesian question"),
        ("How much is a PT PMA company, all in?", "an English question"),
        ("Berapa biaya pendirian perusahaan PT PMA?", "an Indonesian question"),
        ("Apa saja syarat NIB dan OSS?", "an Indonesian question"),
        ("What are the NIB and OSS requirements?", "an English question"),
    ]

    @pytest.mark.parametrize(("query", "shape"), CASES)
    @pytest.mark.parametrize("context_lang", ["en", "id"])
    def test_it_clears_the_gate_in_either_context_language(
        self, query: str, shape: str, context_lang: str
    ) -> None:
        context = EN_CONTEXT if context_lang == "en" else ID_CONTEXT
        score = calculate_evidence_score(RETRIEVAL, context, query)
        assert score >= 0.15, (
            f"{shape} {query!r} against {context_lang} context scored {score} — "
            "the question and the corpus happening to share a language is not "
            "evidence, and its absence is not the lack of it"
        )

    def test_no_crossed_case_lands_in_the_no_relevance_branch(self) -> None:
        """The defect was not "a lower score" — it was landing in the **"no
        semantic relevance"** branch, `min(source_quality * 0.2, 0.1)`, which
        caps at 0.1 and cannot be argued out of. Measured headline row, this
        change: "Harga PT PMA berapa all in?" against ENGLISH context goes
        **0.08 -> 0.60** (origin/main vs this branch, same inputs).

        The claim is that branch is now unreachable for a question that names
        its subject — not that every phrasing scores identically. Banding makes
        an equality assertion here a fixture, not a finding."""
        scores = [
            calculate_evidence_score(RETRIEVAL, ctx, q)
            for q, _ in self.CASES
            for ctx in (EN_CONTEXT, ID_CONTEXT)
        ]
        assert min(scores) > 0.1, f"a crossed case is still scored as no-relevance: {sorted(scores)}"


class TestInnocenceIsTheFloorNotTheCeiling:
    """Criterion 3. These may not be weakened to let a new metric pass, and the
    withdrawn half of the cure was withdrawn precisely because it did."""

    def test_a_nonsense_query_still_scores_nothing(self) -> None:
        assert calculate_evidence_score(POOR_RETRIEVAL, UNRELATED_CONTEXT, "xyzabc123") < 0.15

    def test_no_sources_and_no_context_is_zero(self) -> None:
        assert calculate_evidence_score(None, [], "What is a PT PMA?") == 0.0

    def test_a_kitas_query_answered_with_kbli_documents_still_abstains(self) -> None:
        kbli_context = [
            "KBLI 56101 restaurant business classification code, risk category "
            "and licensing requirements under OSS."
        ]
        score = calculate_evidence_score(
            [{"score": 0.75}], kbli_context, "What are the KITAS extension requirements?"
        )
        assert score < 0.15, f"a topic mismatch must not clear the gate (got {score})"

    def test_the_new_vocabulary_did_not_widen_the_entity_mismatch_hole(self) -> None:
        """`pt`/`pma` are now extractable, so a company question against visa
        context has MORE keywords than before. The mismatch check must still
        catch it — a richer keyword set must not become a richer way to pass."""
        score = calculate_evidence_score(
            [{"score": 0.6}],
            ["visa immigration permit stay kitas renewal"],
            "PT PMA company setup registration",
        )
        assert score < 0.15, score


# ── the golden set, reported per language subset ──────────────────────────

GOLDEN: list[tuple[str, str, bool]] = [
    ("Harga PT PMA berapa all in?", "id", True),
    ("Berapa biaya pendirian PT PMA?", "id", True),
    ("Apa saja syarat NIB dan OSS?", "id", True),
    ("Berapa modal disetor minimum PT PMA?", "id", True),
    ("How much is a PT PMA company, all in?", "en", True),
    ("What are the NIB and OSS requirements?", "en", True),
    ("What is the minimum paid-up capital for a PT PMA?", "en", True),
    ("How long does PT PMA registration take?", "en", True),
    ("Where can I surf in Bali next weekend?", "en", False),
    ("Ada apa saja di Ubud akhir pekan ini?", "id", False),
    ("asdkjhasd", "id", False),
    ("xyzabc123", "en", False),
]


def test_the_golden_set_abstain_rate_is_reported_per_language() -> None:
    """Criterion 4. A single blended abstain rate hides exactly this defect — an
    over-cautious gate and a healthy one post the same number — so the two
    subsets are asserted SEPARATELY.

    Every question is run against the OPPOSITE language's context on purpose:
    the claim under test is not "the scorer is right", it is "the scorer does
    not decide by language".
    """
    policy = build_abstain_policy("default")
    by_lang: dict[str, list[bool]] = {}

    for query, lang, answerable in GOLDEN:
        if answerable:
            # deliberately crossed: Indonesian question -> English chunk
            sources, context = RETRIEVAL, (ID_CONTEXT if lang == "en" else EN_CONTEXT)
        else:
            sources, context = POOR_RETRIEVAL, UNRELATED_CONTEXT
        score = calculate_evidence_score(sources, context, query)
        abstained = policy.label_abstains(score)
        by_lang.setdefault(lang, []).append(abstained)
        assert abstained is not answerable, (
            f"{lang} {query!r}: answerable={answerable} but abstain={abstained} "
            f"(score {score})"
        )

    rates = {lang: sum(v) / len(v) for lang, v in by_lang.items()}
    assert rates["id"] == rates["en"], (
        f"Indonesian and English abstain at different rates on crossed-language "
        f"evidence: {rates}"
    )


@pytest.mark.xfail(
    reason=(
        "DECLARED RESIDUAL, measured not guessed: a question that names NO "
        "identifier has nothing to bridge the languages with, so the lexical "
        "ratio still reads 0. 'What is the price of new company setup?' against "
        "Indonesian context scores 0.08. Its real embedding cosine against that "
        "same chunk is 0.373 (measured 2026-09-03), comfortably above a 0.32 "
        "band — so the retrieval signal WOULD cure it. That half of the spec is "
        "withdrawn until the nine tripwires pinned to impossible cosines are "
        "corrected in their own PR. This xfail is the marker that it is open."
    ),
    strict=True,
)
def test_a_question_naming_no_identifier_is_still_language_blind() -> None:
    score = calculate_evidence_score(RETRIEVAL, ID_CONTEXT, "What is the price of new company setup?")
    assert score >= 0.15


@pytest.mark.xfail(
    reason=(
        "PRE-EXISTING, and measured as such rather than assumed: "
        "'Berapa harga sewa motor di Canggu?' shares exactly ONE generic word "
        "('harga') with a company-setup chunk. One hit out of four keywords is "
        "a 0.25 ratio, which the bands read as 0.2 'weak relevance', landing at "
        "0.16 against a 0.15 threshold. Measured on BOTH trees with identical "
        "inputs, 2026-09-03: origin/main = 0.160, this branch = 0.160 — the "
        "vocabulary change neither caused it nor cures it, and claiming a fix "
        "here would be claiming someone else's bug. It is the partial-overlap "
        "bypass the spec's withdrawn-attempt section already names."
    ),
    strict=True,
)
def test_one_generic_word_should_not_be_evidence() -> None:
    score = calculate_evidence_score(
        POOR_RETRIEVAL, ID_CONTEXT, "Berapa harga sewa motor di Canggu?"
    )
    assert score < 0.15


# ---------------------------------------------------------------------------
# The two-character identifiers, and why they need a boundary
#
# Found on this branch by its own author before merge, and it is the reason the
# first version of this change under-delivered in silence: the extractor keeps
# the vocabulary, and then a SECOND filter eight lines later — `len(w) > 2` in
# the de-duplication loop — threw ten of them straight back out. `PT`, the
# identifier the spec names first, never reached the matcher at all.
#
# Letting them through re-opens the risk that motivated the length rule in the
# first place, so the two changes are a pair and neither is safe alone:
# measured on the off-topic chunk below, substring matching scores **0.475**
# (`pt` inside `receipt`/`script`/`empty`/`accept`, `rp` inside `corporate`)
# against a 0.15 gate; word-boundary matching scores **0.060**.
# ---------------------------------------------------------------------------

COLLIDING_CONTEXT = [
    "Our corporate risk policy: keep every receipt, the script is empty "
    "until you accept the task."
]


@pytest.mark.parametrize(
    "identifier",
    ["pt", "rp", "sk", "cv", "b1", "c1", "c2", "c7", "d1", "d2"],
)
def test_two_character_identifiers_reach_the_matcher(identifier: str) -> None:
    """Guilt: each of the ten survives BOTH filters and is counted as a hit."""
    score = calculate_evidence_score(
        RETRIEVAL, [f"The {identifier.upper()} document is issued by the agency."], identifier
    )
    assert score >= 0.15, f"{identifier!r} was dropped before matching"


def test_short_identifiers_do_not_match_inside_ordinary_words() -> None:
    """Innocence: the same tokens must not be found inside longer words."""
    score = calculate_evidence_score(
        RETRIEVAL, COLLIDING_CONTEXT, "Berapa harga PT PMA dan RP modal?"
    )
    assert score < 0.15, (
        "an off-topic chunk cleared the gate on accidental substring hits "
        f"(score {score})"
    )


def test_visa_codes_do_not_match_inside_ordinary_words() -> None:
    score = calculate_evidence_score(
        RETRIEVAL, COLLIDING_CONTEXT, "Berapa lama proses B1 dan C1?"
    )
    assert score < 0.15


def test_longer_keywords_still_match_as_substrings() -> None:
    """The asymmetry is deliberate: Indonesian morphology depends on it."""
    score = calculate_evidence_score(
        RETRIEVAL, ["Proses pendiriannya memakan waktu 30 hari kerja."], "pendirian PT PMA"
    )
    assert score >= 0.15


# ---------------------------------------------------------------------------
# Adversarial review, 2026-09-03 (spalla-review, not the author): BLOCK, four
# findings. All four are pinned here, with the numbers that were measured.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "context", "collision"),
    [
        ("Apa itu OSS?", "Quarterly earnings show a net loss this quarter.", "oss/loss"),
        ("Apa itu OSS", "The cross-border boss said it was possible.", "oss/cross"),
        ("Apa itu hak milik?", "Please shake the bottle well before use.", "hak/shake"),
        ("Apakah IMB sudah keluar?", "The instructor asked everyone to climb.", "imb/climb"),
        ("Berapa tarif PKP?", "Please pick up the parcel at reception.", "pkp/pick-up"),
    ],
)
def test_three_character_identifiers_do_not_match_inside_words(
    query: str, context: str, collision: str
) -> None:
    """Finding 1 (BLOCKER): the collision is by VOCABULARY, not by length.

    Drawing the word-boundary line at two characters was wrong and measured
    wrong: with no sources at all, 'Apa itu OSS?' scored 0.600 against a
    quarterly-earnings chunk. Note the punctuated forms score 0.600 on
    origin/main too — the old length rule ran on the RAW token, so 'OSS?' is
    four characters and passed it.
    """
    score = calculate_evidence_score(None, [context], query)
    assert score < 0.15, f"{collision}: off-topic chunk scored {score}"


@pytest.mark.parametrize(
    ("query", "context"),
    [
        ("Apa itu OSS?", "OSS adalah sistem perizinan berusaha terintegrasi elektronik."),
        ("Apakah IMB sudah keluar?", "IMB sudah diganti PBG sejak UU Cipta Kerja."),
        ("Berapa tarif PKP?", "PKP wajib memungut PPN atas penyerahan barang kena pajak."),
    ],
)
def test_three_character_identifiers_still_match_their_own_subject(
    query: str, context: str
) -> None:
    """Innocence's other half: the guard must not cost the real hits."""
    assert calculate_evidence_score(None, [context], query) >= 0.15


RELEVANT_KITAS = ["The KITAS visa process typically takes 14 business days after submission."]


@pytest.mark.parametrize(
    "extra",
    ["", " NIB OSS", " NIB OSS SPT PKP IMB HAK AJB", " NIB OSS SPT PKP IMB HAK AJB SHM HGB PBG SLF"],
)
def test_naming_more_identifiers_never_lowers_the_score(extra: str) -> None:
    """Finding 3 (MEDIUM): dilution — and it crossed the gate.

    The ratio is hits/keywords, so each token the vocabulary newly keeps also
    enlarges the denominator. Before the clamp, on this same relevant chunk:
    three keywords scored 0.600, five scored 0.400, and twelve scored **0.000
    — below the gate, where the old rule scored 0.600**. Naming more of the
    right things made the bot abstain.
    """
    score = calculate_evidence_score(None, RELEVANT_KITAS, "syarat visa KITAS" + extra)
    assert score >= 0.15, f"appending {extra!r} pushed a relevant chunk to {score}"


def test_a_three_letter_word_followed_by_punctuation_survives() -> None:
    """Finding 4 (LOW): the walrus rewrite moved the length test onto the
    STRIPPED token, so 'sim?' — kept by the old raw-token test at four
    characters — was silently dropped. Measured: 0.600 on origin/main, 0.000
    on this branch before the clamp restored the old token set.
    """
    score = calculate_evidence_score(
        None, ["Biaya sim baru adalah Rp 100.000 di Polres."], "sim?"
    )
    assert score >= 0.15
