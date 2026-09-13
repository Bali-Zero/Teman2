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

from backend.app.core.constants import EvidenceScoreConstants
from backend.core import score_provenance
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic._support_signal import SupportVerdict
from backend.services.rag.agentic.reasoning_utils import (
    _SHORT_IDENTIFIERS,
    calculate_evidence_score,
)

RETRIEVAL = [{"score": 0.72}]
POOR_RETRIEVAL = [{"score": 0.18}]

# V1 (RULED I31) — a DECLARED dense source for the one measured cosine on
# disk for this (query, chunk) pair: 0.373 on `text-embedding-3-small`.
# What is ATTESTED, and nothing more (aligned to the manifest's own wording
# under gate condition C3 of #6338): 0.373 appears in #5618 (commit
# 2cd3cf84b8, 2026-09-09), whose message records its OTHER cosines as
# `measured live 2026-09-01` with their text pairs but states this one with
# NO measurement date of its own; the `2026-09-03` this comment used to
# attach to it is that commit's ADVERSARIAL REVIEW date, not a measurement
# receipt. No probe artifact for this cosine exists anywhere on disk, and
# none is invented here. `score` is the REAL
# transform of that cosine through the live `format_search_results`
# (`backend/services/misc/result_formatter.py`), not hand arithmetic:
#   PYTHONPATH=. .venv/bin/python -c "
#   from backend.services.misc.result_formatter import format_search_results
#   from backend.core import score_provenance
#   raw = {'ids': ['v1'], 'documents': ['x'], 'distances': [1 - 0.373], 'metadatas': [{}]}
#   print(format_search_results(raw, 'kbli_2025_final_hybrid',
#       score_kind=score_provenance.DENSE_FORMATTED)[0]['score'])"
# -> 0.6146. RETRIEVAL and POOR_RETRIEVAL above stay byte-identical (D3/D5,
# see `pipeline_score_fixtures.py`'s own docstring for the pattern this
# mirrors) — this is an ADDITIONAL literal, read only by the test below that
# names it.
RETRIEVAL_DECLARED_DENSE = [
    {
        "score": 0.6146,
        "score_kind": score_provenance.DENSE_FORMATTED,
        "score_raw": 0.373,
    }
]

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

    @pytest.mark.parametrize("identifier", ["pma", "nib", "oss", "spt", "hgb"])
    def test_a_short_business_identifier_is_kept(self, identifier: str) -> None:
        assert identifier in _SHORT_IDENTIFIERS

    def test_pt_was_removed_as_non_discriminating_not_forgotten(self) -> None:
        """`pt` is the identifier this whole spec names first — and it was
        removed in the 2026-09-10 fix-of-a-fix, not overlooked: it is a free
        hit on almost every Indonesian company name.
        See ``test_pt_pma_over_match_on_an_unrelated_company_chunk_now_abstains``
        for the measured before/after."""
        assert "pt" not in _SHORT_IDENTIFIERS

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


# D5 exception (build spec §8; staff-room RULING 2026-09-12 02:05 WITA,
# decision I13; extended 3→5 by reviewer agreement). These five GOLDEN
# queries carry `activates_in: "B2.1"` in `manifest_mandatory.json`
# (case_ids bs-30ca5e5a, bs-6cd7df49, bs-3d3b5229, bs-a3a7f1ca, bs-dd6ff12d,
# origin `test_evidence_cross_language.py:182/183/185/186/187` — exactly the
# five rows below). B1.3's two reviewers (Gemini 3.1 Pro + Codex gpt-5.6-sol)
# RATIFIED them `relevant_insufficient`, not `sufficient`: the crossed
# context lists company-setup COMPONENTS (deed, ministry approval, NPWP, NIB
# via OSS) but never explicitly states the specific requested fact — the
# NIB/OSS requirements themselves, the paid-up-capital figure, or the
# registration duration. They were CONTESTABLE `sufficient` at freeze; this
# is B1.3's correction, activated together with the B2.1 scorer change.
#
# GOLDEN's own `answerable=True` for these five is therefore STALE. It is
# kept in the tuple literal below (every OTHER row's shape is frozen) and
# overridden here rather than edited in place, because flipping `answerable`
# to `False` in the tuple would ALSO flip which fixture the crossing logic
# selects (RETRIEVAL, score 0.72 -> POOR_RETRIEVAL, score 0.18) — exactly the
# label-selected defect this override exists to remove: the fixture the
# manifest actually records (RETRIEVAL) must stay FIXED while only the
# expectation corrects.
#
# MEASURED, not assumed: on the frozen legacy path (this fixture declares no
# score_kind), all five share "PMA" with their crossed context, which alone
# clears every abstain gate through the ordinary keyword/source-quality path
# (0.3-0.8 measured per case) — provenance/lexical signals cannot make any of
# these five abstain, which is exactly build spec §0's own point: "provenance
# ... CANNOT separate a counterfactual pair, by construction ... the SUPPORT
# SIGNAL is what decides sufficiency." So each of these five calls supplies
# `support=SupportVerdict.NOT_SUPPORTED` — the verdict a real judge would
# return given each case's own `missing_fact_explanation` (the context lists
# setup components but never states the specific requested fact) — which
# fail-closed-zeroes relevance (build spec §2.5) regardless of the band or
# the keyword ratio. This also removes what looked like a collision with
# `TestTheCrossLanguageCasesThatCarryAnIdentifier.CASES` above (two of these
# five queries — "Apa saja syarat NIB dan OSS?", "What are the NIB and OSS
# requirements?" — are also members of that frozen, untouched test): CASES's
# own call never passes `support`, so it is a DIFFERENT call to the same pure
# function with a different keyword argument, not the same call asserted on
# twice. `calculate_evidence_score` is pure but `support` is part of its
# input, so the two assertions do not contradict each other.
_D5_CORRECTED_INSUFFICIENT: frozenset[str] = frozenset(
    {
        "Apa saja syarat NIB dan OSS?",
        "Berapa modal disetor minimum PT PMA?",
        "What are the NIB and OSS requirements?",
        "What is the minimum paid-up capital for a PT PMA?",
        "How long does PT PMA registration take?",
    }
)


def test_the_golden_set_abstain_rate_is_reported_per_language() -> None:
    """Criterion 4, with the D5 exception (build spec §8) folded in. A single
    blended abstain rate hides exactly this defect — an over-cautious gate
    and a healthy one post the same number — so the two subsets are still
    computed and reported SEPARATELY, per case, against the CORRECTED ground
    truth.

    Every question is still run against the OPPOSITE language's context on
    purpose (still deliberately crossed) for every row — the D5 five are the
    only ones whose (sources, context) are pinned directly to the manifest's
    fixture rather than re-derived, the only ones that pass a `support`
    verdict, and the only ones whose expectation flips to ABSTAIN. The claim
    under test is still "the scorer does not decide by language" — checked
    per case, since after the correction the five D5 flips land
    2-on-Indonesian/3-on-English (bs-30ca5e5a, bs-6cd7df49 vs bs-3d3b5229,
    bs-a3a7f1ca, bs-dd6ff12d), so the two languages' TRUE rates now
    legitimately differ and a same-rate-across-languages assertion would be
    asserting something false about the corrected data rather than testing
    the scorer.
    """
    policy = build_abstain_policy("default")
    by_lang: dict[str, list[bool]] = {}
    expected_by_lang: dict[str, list[bool]] = {}

    for query, lang, answerable in GOLDEN:
        expect_abstain = not answerable
        support: SupportVerdict | None = None
        if query in _D5_CORRECTED_INSUFFICIENT:
            # Fixed input, pinned to the manifest's own provenance_fixture
            # (RETRIEVAL, score 0.72, declares no score_kind) — never
            # derived from the (corrected) expectation below.
            sources, context = RETRIEVAL, (ID_CONTEXT if lang == "en" else EN_CONTEXT)
            support = SupportVerdict.NOT_SUPPORTED
            expect_abstain = True
        elif answerable:
            # deliberately crossed: Indonesian question -> English chunk
            sources, context = RETRIEVAL, (ID_CONTEXT if lang == "en" else EN_CONTEXT)
        else:
            sources, context = POOR_RETRIEVAL, UNRELATED_CONTEXT
        score = calculate_evidence_score(sources, context, query, support=support)
        abstained = policy.label_abstains(score)
        by_lang.setdefault(lang, []).append(abstained)
        expected_by_lang.setdefault(lang, []).append(expect_abstain)
        assert abstained is expect_abstain, (
            f"{lang} {query!r}: expected abstain={expect_abstain} but got "
            f"abstain={abstained} (score {score})"
        )

    rates = {lang: sum(v) / len(v) for lang, v in by_lang.items()}
    expected_rates = {lang: sum(v) / len(v) for lang, v in expected_by_lang.items()}
    assert rates == expected_rates, (
        f"per-language abstain rates diverge from the corrected ground truth "
        f"the per-case loop above already checked: measured {rates}, "
        f"expected {expected_rates}"
    )


def test_a_question_naming_no_identifier_is_still_language_blind() -> None:
    """CURED (RULED I31, this PR): a question that names NO identifier still
    has nothing to bridge the languages LEXICALLY — the legacy literal
    (`RETRIEVAL`, score_kind unknown) still scores 0.08 here, unchanged. What
    cures it is declaring the provenance this source actually has: its real
    embedding cosine against this chunk is 0.373 (attested in #5618, no
    measurement date of its own), which
    lands in B2.1's dense MODERATE band (>=0.32,
    `reasoning_utils.py::_dense_band_index`) and no longer needs a lexical
    bridge at all. `RETRIEVAL_DECLARED_DENSE` (declared above) scores 0.55.
    This was the nine-tripwires-pinned-to-impossible-cosines blocker the
    former xfail named as open — those nine were corrected in B1.2/B2.1
    ahead of this PR, so only this one declaration was left."""
    query = "What is the price of new company setup?"

    # The first half of the sentence in this test's name, ASSERTED and not
    # merely asserted in prose: the legacy literal is still language-blind.
    legacy = calculate_evidence_score(RETRIEVAL, ID_CONTEXT, query)
    assert legacy < 0.15, (
        "the lexical bridge must still be absent — if this rises, the cure "
        f"below is measuring something other than provenance (got {legacy})"
    )

    # The second half: declaring the provenance the source actually has is
    # what carries it over the gate.
    score = calculate_evidence_score(RETRIEVAL_DECLARED_DENSE, ID_CONTEXT, query)
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
#
# UPDATE, 2026-09-10 fix-of-a-fix: `pt`, `rp` and `cv` were removed from
# `_SHORT_IDENTIFIERS` entirely (whole-token over-match, not the substring
# case this section is about) — see the block below and
# ``test_pt_pma_over_match_on_an_unrelated_company_chunk_now_abstains``. They
# stay in the historical narrative above because that IS what was measured at
# the time; the guilt parametrize below now only lists members still in the
# vocabulary.
# ---------------------------------------------------------------------------

COLLIDING_CONTEXT = [
    "Our corporate risk policy: keep every receipt, the script is empty "
    "until you accept the task."
]


@pytest.mark.parametrize(
    "identifier",
    ["sk", "b1", "c1", "c2", "c7", "d1", "d2"],
)
def test_two_character_identifiers_reach_the_matcher(identifier: str) -> None:
    """Guilt: each of these seven survives BOTH filters and is counted as a
    hit. (`pt`/`rp`/`cv` were dropped from this list 2026-09-10 — they no
    longer reach the matcher on purpose, see the test below.)"""
    score = calculate_evidence_score(
        RETRIEVAL, [f"The {identifier.upper()} document is issued by the agency."], identifier
    )
    assert score >= 0.15, f"{identifier!r} was dropped before matching"


@pytest.mark.parametrize("removed", ["pt", "rp", "cv"])
def test_non_discriminating_two_character_tokens_were_removed_from_the_vocabulary(
    removed: str,
) -> None:
    """Innocence, the mirror of the guilt test above: `pt`/`rp`/`cv` used to
    reach the matcher too, and that was the defect — each is common enough to
    be a free hit on an UNRELATED chunk. Measured with `pt` still in the
    vocabulary: 0.800 on an unrelated-company chunk; removed, 0.080. See
    ``test_pt_pma_over_match_on_an_unrelated_company_chunk_now_abstains``."""
    assert removed not in _SHORT_IDENTIFIERS
    score = calculate_evidence_score(
        RETRIEVAL, [f"The {removed.upper()} document is issued by the agency."], removed
    )
    assert score < EvidenceScoreConstants.ABSTAIN_THRESHOLD, (
        f"{removed!r} still reaches the matcher (score {score})"
    )


# ---------------------------------------------------------------------------
# Whole-token over-match on an off-topic chunk (2026-09-10 fix-of-a-fix)
#
# Distinct from the substring case above (`receipt`/`corporate` etc.): here
# the chunk contains the identifier as a genuine standalone word, on a topic
# that has nothing to do with the query. `pt`/`rp`/`idr`/`usd`/`cv` used to
# be a free hit on this shape because they are common enough to appear on
# almost ANY chunk regardless of subject.
# ---------------------------------------------------------------------------

MONEY_UNRELATED_CONTEXT = [
    "Sewa motor per hari Rp 150.000, atau IDR 900.000 per minggu, USD 60 untuk turis."
]


def test_pt_pma_over_match_on_an_unrelated_company_chunk_now_abstains() -> None:
    """Measured: with `pt` in the vocabulary this scored 0.800 (an unrelated
    chunk answered a company question); with it removed, 0.080."""
    score = calculate_evidence_score(
        RETRIEVAL, ["PT Warung Bali menjual nasi goreng dan es teh"], "Apa itu PT PMA?"
    )
    assert score < EvidenceScoreConstants.ABSTAIN_THRESHOLD, (
        f"an unrelated company chunk cleared the gate on a bare 'PT' hit (score {score})"
    )


def test_a_price_chunk_with_currency_units_but_no_visa_word_still_abstains() -> None:
    """Measured 0.080 both before and after this fix: the query names no
    currency, so `rp`/`idr`/`usd` never drove this score either way — pinned
    so a future vocabulary change cannot reintroduce the free hit silently."""
    score = calculate_evidence_score(RETRIEVAL, MONEY_UNRELATED_CONTEXT, "Berapa harga KITAS?")
    assert score < EvidenceScoreConstants.ABSTAIN_THRESHOLD, (
        f"a price chunk with no visa word cleared the gate (score {score})"
    )


def test_the_pt_pma_guilt_twin_still_clears_the_gate_after_the_over_match_fix() -> None:
    """Guilt twin: removing `pt` must not cost the PR's cross-language win.
    Measured 0.800 before this fix, 0.600 after — both comfortably above the
    existing >= 0.15 expectation this reuses from
    ``TestTheCrossLanguageCasesThatCarryAnIdentifier.test_it_clears_the_gate_in_either_context_language``."""
    score = calculate_evidence_score(RETRIEVAL, EN_CONTEXT, "Harga PT PMA berapa all in?")
    assert score >= EvidenceScoreConstants.ABSTAIN_THRESHOLD, score


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


# ---------------------------------------------------------------------------
# The guard, swept over the WHOLE vocabulary rather than over hand-picked words
#
# The independent grader (backend-verifier, 2026-09-03) refused to sign off the
# hand-built collision list, and was right to: it found a collision for only 7
# of the 38 entries, failed to construct one for 19, and never attempted the
# remaining 12 (`imk`, `b1`, `c1`, `c2`, `c7`, `d1`, `d2`, `e23`, `e28`, `e31`,
# `e32`, `e33`) — zero data, which is not the same as safe. It also showed that
# three of my own cases (`pt`, `rp`, `sk`) proved nothing about the guard: with
# a query of `"PT?"` origin/main never extracts a two-letter identifier at all,
# so that comparison could not exercise the substring path it was meant to test.
#
# Enumeration was the wrong instrument. The guard is structural — word
# boundaries apply to every vocabulary entry — so it is swept structurally: for
# each of the 38, present as a whole token must COUNT, and the same characters
# buried inside a longer token must NOT. No entry can be forgotten, and a
# future addition to the vocabulary is covered the day it is added.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("identifier", sorted(_SHORT_IDENTIFIERS))
def test_every_identifier_counts_as_a_whole_token(identifier: str) -> None:
    score = calculate_evidence_score(
        None, [f"Dokumen {identifier} sudah diterbitkan kemarin."], identifier
    )
    assert score >= 0.15, f"{identifier!r} was not counted when present"


@pytest.mark.parametrize("identifier", sorted(_SHORT_IDENTIFIERS))
def test_no_identifier_counts_when_buried_in_a_longer_token(identifier: str) -> None:
    score = calculate_evidence_score(
        None, [f"Zxq{identifier}vkw plus some entirely unrelated filler prose."], identifier
    )
    assert score < 0.15, f"{identifier!r} matched inside a longer token"
