"""Unit tests for the E33 runtime claim guard (task 1.3, armed task 2026-07-25).

Covers ``check_e33_claims`` (per-pattern positives, negation guards, E33
context gating), ``guard_e33_answer``/``guard_e33_answer_detailed`` (log +
fallback note, never raises), and ``apply_guard_enforcement`` (the pure
abstain/HUMAN_REVIEW routing decision gated by the ``E33_CLAIM_GUARD_ENFORCE``
kill-switch). Uses the trimmed registry fixture at
``fixtures/e33_fact_registry.json`` — tests never touch the sibling worktree
path.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

import pytest

from backend.services.visa_check.e33_claim_guard import (
    E33_ABSTAIN_REASON,
    E33_FORBIDDEN_PATTERNS,
    E33_SAFE_FALLBACK_NOTE,
    LEGACY_ERROR_REF,
    GuardOutcome,
    apply_guard_enforcement,
    check_e33_claims,
    guard_e33_answer,
    guard_e33_answer_detailed,
)

FIXTURE_REGISTRY = Path(__file__).parent / "fixtures" / "e33_fact_registry.json"

_E33 = "About the E33 Second Home visa: "

# (pattern_id, violating text). Every sample is E33-contextual unless the
# pattern is context-free by design.
POSITIVE_CASES: list[tuple[str, str]] = [
    (
        "e33f_superseded_income_usd1500",
        _E33 + "the E33F retirement route requires USD 1,500/month passive income.",
    ),
    (
        "second_home_any_bank",
        _E33 + "you can place the USD 130,000 deposit at any Indonesian bank.",
    ),
    (
        "second_home_any_bank",
        _E33 + "the deposit may sit at any bank of your choice.",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        _E33 + "after 3 years you are eligible for KITAP conversion.",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        _E33 + "KITAP is automatic after the first grant.",
    ),
    (
        "e33_permits_local_work",
        "The E33 permits you to work for a local employer.",
    ),
    (
        "e33_permits_local_work",
        "You can work legally in Indonesia on an E33 visa.",
    ),
    (
        "bsi_sharia_equivalence",
        _E33 + "a BSI deposit qualifies as the state-owned bank deposit.",
    ),
    (
        "split_deposit_accepted",
        _E33 + "you may split the deposit across two BUMN banks.",
    ),
    (
        "lps_full_coverage",
        _E33 + "the deposit is safe because LPS fully covers it.",
    ),
    (
        "approval_guaranteed",
        _E33 + "with our package, approval is guaranteed.",
    ),
    (
        "idr_2m_fee_error",
        _E33 + "the government fee is IDR 2,000,000.",
    ),
    (
        "second_home_first_grant_5_10_years",
        _E33 + "the first grant is 5-10 years depending on the case.",
    ),
]

# Correct cautionary phrasing must NOT be flagged (negation guards).
NEGATIVE_CASES: list[str] = [
    _E33 + "it is a pure residence permit — it does NOT authorize employment.",
    _E33 + "you cannot work in Indonesia on an E33; paid work needs a separate KITAS.",
    _E33 + "approval is not guaranteed; the decision rests with immigration.",
    _E33 + "LPS does not fully cover the deposit — a cap applies.",
    _E33 + "the deposit cannot be split across banks (unconfirmed).",
    _E33 + "the E33F route requires USD 3,000/month passive income.",
    _E33 + "a USD 130,000 deposit in your own name at a state-owned (BUMN) "
    "Indonesian bank, or USD 1,000,000 qualifying strata-title property.",
    _E33 + "first grant is up to 5 years, renewable per prevailing regulations.",
    # No E33 context at all -> context-gated patterns stay silent.
    "The consulting retainer is USD 1,500/month and approval is guaranteed.",
    "",
]


class TestCheckE33Claims:
    @pytest.mark.parametrize(("pattern_id", "text"), POSITIVE_CASES)
    def test_flags_forbidden_claim(self, pattern_id: str, text: str) -> None:
        violations = check_e33_claims(text)
        flagged = {v.pattern_id for v in violations}
        assert pattern_id in flagged, f"expected '{pattern_id}' in {flagged} for: {text!r}"

    @pytest.mark.parametrize("text", NEGATIVE_CASES)
    def test_clean_text_passes(self, text: str) -> None:
        assert check_e33_claims(text) == [], f"unexpected violations for: {text!r}"

    def test_violation_shape(self) -> None:
        text = _E33 + "deposit at any Indonesian bank is fine."
        (violation,) = check_e33_claims(text)
        assert violation.pattern_id == "second_home_any_bank"
        assert violation.matched_text.lower() == "any indonesian bank"
        assert 0 <= violation.start < violation.end <= len(text)
        assert violation.registry_ref == "e33_base_deposit_amount"

    def test_legacy_error_ref_sentinel(self) -> None:
        (violation,) = check_e33_claims(_E33 + "fee is IDR 2.000.000 flat.")
        assert violation.registry_ref == LEGACY_ERROR_REF


class TestGuardE33Answer:
    def test_clean_answer_returned_unchanged(self) -> None:
        answer = _E33 + "first grant is up to 5 years; it does not authorize employment."
        assert guard_e33_answer(answer) == answer

    def test_violation_appends_fallback_note(self, caplog: pytest.LogCaptureFixture) -> None:
        answer = _E33 + "deposit at any Indonesian bank."
        with caplog.at_level(logging.WARNING):
            guarded = guard_e33_answer(answer)
        assert guarded.startswith(answer)
        assert E33_SAFE_FALLBACK_NOTE in guarded
        assert "[E33Guard]" in caplog.text
        assert "second_home_any_bank" in caplog.text

    def test_empty_answer_passthrough(self) -> None:
        assert guard_e33_answer("") == ""


class TestGuardE33AnswerDetailed:
    """``guard_e33_answer_detailed`` must be byte-identical to
    ``guard_e33_answer`` on ``.answer`` and additionally expose the raw
    violations the enforcement decision needs.
    """

    def test_positive_corpus_covers_all_ten_patterns(self) -> None:
        """Sanity check on the corpus itself: every registered pattern_id
        has at least one GUILT case — the precondition the two corpus tests
        below rely on."""
        covered = {pid for pid, _ in POSITIVE_CASES}
        registered = {p.pattern_id for p in E33_FORBIDDEN_PATTERNS}
        assert covered == registered, (
            f"POSITIVE_CASES does not cover exactly the registered patterns: "
            f"missing={registered - covered} extra={covered - registered}"
        )

    @pytest.mark.parametrize(("pattern_id", "text"), POSITIVE_CASES)
    def test_guilt_case_reports_violation(self, pattern_id: str, text: str) -> None:
        """GUILT corpus (10/10 patterns): each forbidden claim must trip the
        detailed guard, append the note, and never touch the model's own text."""
        outcome = guard_e33_answer_detailed(text)
        assert outcome.has_violation
        assert pattern_id in {v.pattern_id for v in outcome.violations}
        assert outcome.answer.startswith(text.rstrip())
        assert E33_SAFE_FALLBACK_NOTE in outcome.answer

    @pytest.mark.parametrize("text", NEGATIVE_CASES)
    def test_innocence_case_reports_no_violation(self, text: str) -> None:
        """INNOCENCE corpus: adjacent legitimate phrasing (correct negations,
        no-E33-context mentions, empty string) must never trip the guard —
        answer passed through byte-for-byte, no note appended."""
        outcome = guard_e33_answer_detailed(text)
        assert not outcome.has_violation
        assert outcome.violations == ()
        assert outcome.answer == text

    def test_outcome_is_immutable_and_stdlib_only(self) -> None:
        outcome = guard_e33_answer_detailed(_E33 + "deposit at any Indonesian bank.")
        assert isinstance(outcome, GuardOutcome)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.answer = "tampered"  # type: ignore[misc]

    def test_guard_e33_answer_and_detailed_agree_on_text(self) -> None:
        for text in [*[t for _, t in POSITIVE_CASES], *NEGATIVE_CASES]:
            assert guard_e33_answer(text) == guard_e33_answer_detailed(text).answer


class TestApplyGuardEnforcement:
    """Pure decision function — no I/O, no CoreResult. GUILT = violation
    found AND kill-switch armed routes to abstain; INNOCENCE = every other
    combination (switch off, or no violation) leaves abstain untouched."""

    # --- GUILT: enforcement fires ---
    def test_violation_plus_enforce_sets_new_reason(self) -> None:
        reason = apply_guard_enforcement(
            has_violation=True, enforce=True, existing_abstain_reason=None
        )
        assert reason == E33_ABSTAIN_REASON

    def test_violation_plus_enforce_combines_with_existing_reason(self) -> None:
        """A query that already abstained on low evidence score must keep
        that reason visible, not have it silently clobbered."""
        reason = apply_guard_enforcement(
            has_violation=True, enforce=True, existing_abstain_reason="low_confidence"
        )
        assert reason == f"low_confidence+{E33_ABSTAIN_REASON}"

    # --- INNOCENCE: enforcement must NOT fire ---
    def test_violation_but_kill_switch_off_is_noop(self) -> None:
        """The default (dark-ship) shape: a real violation, switch OFF ->
        no abstain routing. This is the CURRENT behaviour the kill-switch
        must preserve by default."""
        reason = apply_guard_enforcement(
            has_violation=True, enforce=False, existing_abstain_reason=None
        )
        assert reason is None

    def test_no_violation_even_when_armed_is_noop(self) -> None:
        """A clean, legitimate answer must never be routed to abstain even
        when enforcement is armed — the guard only acts on real violations."""
        reason = apply_guard_enforcement(
            has_violation=False, enforce=True, existing_abstain_reason=None
        )
        assert reason is None

    def test_no_violation_and_switch_off_is_noop(self) -> None:
        reason = apply_guard_enforcement(
            has_violation=False, enforce=False, existing_abstain_reason="low_confidence"
        )
        assert reason is None


class TestApplyE33ClaimGuardCallSite:
    """Integration test against the real orchestrator_core.py wiring
    (``_apply_e33_claim_guard``), using a bare ``CoreResult`` — no
    ``OrchestratorCore``/``AgentState`` construction needed. Proves the
    kill-switch's default-OFF behaviour end-to-end, not just via the pure
    helper in isolation.
    """

    def test_default_kill_switch_is_off(self) -> None:
        """Module-level constant must default to False when
        E33_CLAIM_GUARD_ENFORCE is unset — 'ship dark' precondition."""
        from backend.services.rag.agentic import orchestrator_core as oc

        assert oc._E33_CLAIM_GUARD_ENFORCE is False

    def test_violation_default_off_appends_note_but_does_not_abstain(self) -> None:
        from backend.services.rag.agentic import orchestrator_core as oc
        from backend.services.rag.agentic.schema import CoreResult

        result = CoreResult(answer=_E33 + "deposit at any Indonesian bank.")
        oc._apply_e33_claim_guard(result)

        assert E33_SAFE_FALLBACK_NOTE in result.answer
        assert result.abstain is False
        assert result.abstain_reason is None

    def test_violation_armed_routes_to_abstain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.rag.agentic import orchestrator_core as oc
        from backend.services.rag.agentic.schema import CoreResult

        monkeypatch.setattr(oc, "_E33_CLAIM_GUARD_ENFORCE", True)
        result = CoreResult(answer=_E33 + "with our package, approval is guaranteed.")
        oc._apply_e33_claim_guard(result)

        assert result.abstain is True
        assert result.abstain_reason == E33_ABSTAIN_REASON
        assert E33_SAFE_FALLBACK_NOTE in result.answer  # note-append still happens

    def test_violation_armed_preserves_existing_abstain_reason(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.services.rag.agentic import orchestrator_core as oc
        from backend.services.rag.agentic.schema import CoreResult

        monkeypatch.setattr(oc, "_E33_CLAIM_GUARD_ENFORCE", True)
        result = CoreResult(
            answer=_E33 + "with our package, approval is guaranteed.",
            abstain=True,
            abstain_reason="low_confidence",
        )
        oc._apply_e33_claim_guard(result)

        assert result.abstain is True
        assert result.abstain_reason == f"low_confidence+{E33_ABSTAIN_REASON}"

    def test_clean_answer_armed_does_not_abstain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """INNOCENCE at the call site: even with enforcement armed, a
        legitimate answer must sail through untouched — the failure mode of
        a false positive here is 'parked for human review', not this path
        firing on correct text."""
        from backend.services.rag.agentic import orchestrator_core as oc
        from backend.services.rag.agentic.schema import CoreResult

        monkeypatch.setattr(oc, "_E33_CLAIM_GUARD_ENFORCE", True)
        clean = _E33 + "first grant is up to 5 years; it does not authorize employment."
        result = CoreResult(answer=clean)
        oc._apply_e33_claim_guard(result)

        assert result.answer == clean
        assert result.abstain is False
        assert result.abstain_reason is None


class TestRegistryFixture:
    def test_fixture_covers_guard_registry_refs(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        fact_ids = {f["id"] for f in fixture["facts"]}
        for pattern in E33_FORBIDDEN_PATTERNS:
            if pattern.registry_ref != LEGACY_ERROR_REF:
                assert pattern.registry_ref in fact_ids

    def test_fixture_marks_pending_facts_forbidden(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        forbidden_fact_ids = {
            f["id"] for f in fixture["facts"] if "FORBIDDEN" in f.get("notes", "")
        }
        # The three registry facts explicitly marked FORBIDDEN in their notes.
        assert {
            "bsi_sharia_accepted",
            "split_deposit_accepted",
            "itap_after_3y_criteria",
        } <= forbidden_fact_ids

    def test_fixture_documents_legacy_errors(self) -> None:
        fixture = json.loads(FIXTURE_REGISTRY.read_text())
        legacy = " ".join(fixture["forbidden_legacy_errors"]).lower()
        for keyword in ("1,500", "2,000,000", "lps", "guaranteed", "kitap", "work"):
            assert keyword in legacy


# ── Multilingual guilt + innocence (EN / IT / ID) ────────────────────
#
# The guard scans whatever the model answered, and the model answers in the
# language the client wrote in: `wrap_query_with_language_instruction`
# (query_helpers.py) detects the query language and instructs the model to
# reply in the same one, with an explicit Indonesian branch. Before this
# suite, every pattern body was English-only. Measured on the pre-change
# build, 7 of the 10 patterns caught nothing in Italian or Indonesian — only
# the three anchored to a NUMBER survived translation (USD 1,500, IDR
# 2,000,000, "5-10 years"), because a digit reads the same in every language.
#
# Arming E33_CLAIM_GUARD_ENFORCE on that build would have parked English
# answers for human review while letting the identical claim through in
# Italian and Indonesian — and the logs would have looked healthy.
# Cicatrix family #3, the UNDER-match twin (W82).

_EN = "About the E33 Second Home visa: "
_IT = "Riguardo al visto E33 Second Home: "
_ID = "Tentang visa E33 Second Home: "

#: (pattern_id, english, italian, indonesian) — each a REAL violation.
MULTILINGUAL_GUILT: list[tuple[str, str, str, str]] = [
    (
        "e33f_superseded_income_usd1500",
        _EN + "the E33F route requires USD 1,500/month passive income.",
        _IT + "la via E33F richiede USD 1.500 al mese di reddito passivo.",
        _ID + "jalur E33F membutuhkan pendapatan pasif USD 1.500 per bulan.",
    ),
    (
        "second_home_any_bank",
        _EN + "you can place the USD 130,000 deposit at any Indonesian bank.",
        _IT + "puoi depositare i USD 130.000 presso qualsiasi banca indonesiana.",
        _ID + "Anda dapat menempatkan deposito USD 130.000 di bank Indonesia mana saja.",
    ),
    (
        "e33_itap_kitap_automatic_promise",
        _EN + "after 3 years you are automatically eligible for KITAP.",
        _IT + "dopo 3 anni si ottiene automaticamente il KITAP.",
        _ID + "setelah 3 tahun Anda otomatis mendapatkan KITAP.",
    ),
    (
        "e33_permits_local_work",
        _EN + "the E33 allows you to work in Indonesia.",
        _IT + "l'E33 permette di lavorare in Indonesia.",
        _ID + "E33 memungkinkan Anda bekerja di Indonesia.",
    ),
    (
        "bsi_sharia_equivalence",
        _EN + "BSI qualifies as a state-owned bank for the deposit.",
        _IT + "BSI e' equivalente a una banca statale per il deposito.",
        _ID + "BSI setara dengan bank BUMN untuk deposito.",
    ),
    (
        "split_deposit_accepted",
        _EN + "you may split the deposit across multiple banks.",
        _IT + "puoi dividere il deposito su piu' banche.",
        _ID + "Anda bisa membagi deposito di beberapa bank.",
    ),
    (
        "lps_full_coverage",
        _EN + "the deposit is fully covered by LPS.",
        _IT + "il deposito e' interamente coperto da LPS.",
        _ID + "deposito dijamin sepenuhnya oleh LPS.",
    ),
    (
        "approval_guaranteed",
        _EN + "approval is guaranteed.",
        _IT + "l'approvazione e' garantita.",
        _ID + "persetujuan dijamin.",
    ),
    (
        "idr_2m_fee_error",
        _EN + "the government fee is IDR 2,000,000.",
        _IT + "la tassa governativa e' IDR 2.000.000.",
        _ID + "biaya pemerintah adalah IDR 2.000.000.",
    ),
    (
        "second_home_first_grant_5_10_years",
        _EN + "the first grant is 5-10 years.",
        _IT + "il primo rilascio e' di 5-10 years.",
        _ID + "izin pertama berlaku 5-10 years.",
    ),
]


@pytest.mark.parametrize(
    "pattern_id,text,language",
    [
        (pid, text, lang)
        for pid, en, it, idn in MULTILINGUAL_GUILT
        for lang, text in (("en", en), ("it", it), ("id", idn))
    ],
    ids=[f"{pid}-{lang}" for pid, _, _, _ in MULTILINGUAL_GUILT for lang in ("en", "it", "id")],
)
def test_every_pattern_fires_in_all_three_languages(
    pattern_id: str, text: str, language: str
) -> None:
    """Each forbidden claim must be caught however the answer was phrased."""
    fired = {v.pattern_id for v in check_e33_claims(text)}
    assert pattern_id in fired, (
        f"{pattern_id} is blind in {language}: {text!r} produced {sorted(fired)}"
    )


#: Sentences that are CORRECT and must produce ZERO violations. A guard that
#: flags these is worse than no guard once armed: it parks exactly the answers
#: that got the fact right, and it teaches whoever reads the queue to ignore it.
MULTILINGUAL_INNOCENCE: list[tuple[str, str]] = [
    # English negations — three of these were FALSE POSITIVES on the
    # pre-change build, measured. The fixed-width look-behind could only see
    # the single token before the match, so "you cannot split the deposit"
    # (negator three words back) and "KITAP is not automatic" (negator inside
    # the match) both fired.
    ("en-negated-approval", _EN + "approval is not guaranteed."),
    ("en-negated-split", _EN + "you cannot split the deposit across multiple banks."),
    ("en-negated-lps", _EN + "the deposit is not fully covered by LPS."),
    ("en-negated-automatic", _EN + "KITAP is not automatic after 3 years."),
    ("en-negated-any-bank", _EN + "the deposit cannot sit at any Indonesian bank."),
    ("en-negated-work", _EN + "the E33 does not allow you to work in Indonesia."),
    # Italian negations
    ("it-negated-approval", _IT + "l'approvazione non e' garantita."),
    ("it-negated-split", _IT + "non puoi dividere il deposito su piu' banche."),
    ("it-negated-lps", _IT + "il deposito non e' interamente coperto da LPS."),
    ("it-negated-automatic", _IT + "il KITAP non e' automatico dopo 3 anni."),
    ("it-negated-work", _IT + "l'E33 non permette di lavorare in Indonesia."),
    # Indonesian negations
    ("id-negated-approval", _ID + "persetujuan tidak dijamin."),
    ("id-negated-split", _ID + "Anda tidak bisa membagi deposito di beberapa bank."),
    ("id-negated-automatic", _ID + "KITAP tidak otomatis setelah 3 tahun."),
    ("id-negated-work", _ID + "E33 tidak memungkinkan Anda bekerja di Indonesia."),
    # Correct affirmative statements of the real requirements
    (
        "it-correct-deposit",
        _IT + "il deposito di USD 130.000 deve essere intestato a te presso "
        "una banca statale (BUMN) indonesiana.",
    ),
    ("it-correct-income", _IT + "E33F richiede USD 3.000 al mese di reddito passivo."),
    (
        "id-correct-deposit",
        _ID + "deposito USD 130.000 harus atas nama Anda di bank BUMN.",
    ),
    # Same vocabulary, no E33 context at all
    (
        "unrelated-bank-sentence",
        "Puoi aprire un conto presso qualsiasi banca indonesiana per le spese quotidiane.",
    ),
]


@pytest.mark.parametrize(
    "label,text",
    MULTILINGUAL_INNOCENCE,
    ids=[label for label, _ in MULTILINGUAL_INNOCENCE],
)
def test_correct_sentences_are_never_flagged(label: str, text: str) -> None:
    violations = check_e33_claims(text)
    assert not violations, (
        f"{label} is a correct sentence but fired "
        f"{[(v.pattern_id, v.matched_text) for v in violations]}"
    )


class TestNegationIsScopedToItsOwnSentence:
    """A negation must not shield a violation in the NEXT sentence.

    This is the failure mode a whole-text negation check would introduce: one
    honest "not guaranteed" anywhere in the answer would silence every other
    claim in it. A false negative here reaches a client, so the window is
    bounded twice — by sentence, and by characters.
    """

    def test_violation_after_a_negated_clause_still_fires(self):
        text = _EN + "Approval is not guaranteed. You may split the deposit across multiple banks."
        assert "split_deposit_accepted" in {v.pattern_id for v in check_e33_claims(text)}

    def test_distant_negator_does_not_reach_the_claim(self):
        """A negator far outside the window must not suppress the claim."""
        text = (
            _EN + "This is not the place to discuss unrelated topics at any "
            "length whatsoever, and separately you may split the deposit."
        )
        assert "split_deposit_accepted" in {v.pattern_id for v in check_e33_claims(text)}


#: Sentences that NEGATE SOMETHING ELSE and then state a forbidden claim.
#:
#: This corpus is the reason the negation check asks whether a negator GOVERNS
#: the claim rather than whether one is nearby. An earlier version asked only
#: for presence, and a cross-family adversarial review (Codex gpt-5.6-sol,
#: 2026-08-31) silenced it on 27 of these 29 sentences — including "the
#: required income is not USD 3,000 but USD 1,500 per month", which states the
#: superseded figure this guard exists to catch, in the phrasing a model
#: reaches for most naturally.
#:
#: Every entry here states a forbidden claim as fact. The guard MUST fire.
NEGATOR_GOVERNMENT_GUILT: list[tuple[str, str]] = [
    # "not X but Y" — the contrast marker proves the negator governs X
    (
        "en-income-contrast",
        "About E33F: The required income is not USD 3,000 but USD 1,500 per month.",
    ),
    ("it-income-contrast", "Per E33F, il reddito non è USD 3.000 ma USD 1.500 al mese."),
    (
        "id-income-contrast",
        "Untuk E33F, pendapatan bukan USD 3.000, melainkan USD 1.500 per bulan.",
    ),
    ("en-fee-contrast", "For E33, the fee is not IDR 13,000,000 but IDR 2,000,000."),
    ("en-duration-contrast", "For E33, the first grant is not 1 year but 5-10 years."),
    (
        "en-lps-but-fully",
        "For E33, LPS does not cover interest or bank fees, but fully covers the deposit.",
    ),
    (
        "it-lps-cross-comma",
        "Per E33, LPS non copre solo una parte, ma copre interamente il deposito.",
    ),
    # "not ONLY X" — the negation scopes to the quantifier, the predicate stands
    (
        "en-work-not-only",
        "E33 does not only allow residence, it also allows you to work in Indonesia.",
    ),
    (
        "it-work-non-solo",
        "L'E33 non consente solo il soggiorno, ma consente anche di lavorare in Indonesia.",
    ),
    (
        "id-work-tidak-hanya",
        "E33 tidak hanya memungkinkan tinggal, tetapi juga memungkinkan Anda bekerja di Indonesia.",
    ),
    (
        "en-kitap-contrast",
        "For E33, after 3 years you become eligible, not merely considered, for KITAP.",
    ),
    ("en-approval-cross-semicolon", "For E33, approval is not merely likely; it is guaranteed."),
    # a colon or semicolon introduces the assertion — government stops there
    (
        "en-any-bank-neg-restriction",
        "For E33, the deposit rule is not restrictive: any Indonesian bank is acceptable.",
    ),
    ("it-any-bank-neg-restriction", "Per E33, non ci sono vincoli: qualsiasi banca va bene."),
    (
        "id-any-bank-neg-restriction",
        "Untuk E33, tidak ada batasan: bank Indonesia mana saja bisa dipakai.",
    ),
    (
        "en-lps-cross-semicolon",
        "For E33, LPS does not cover a fraction; it fully covers the deposit.",
    ),
    # a comma-fenced aside negates the aside, not the predicate
    ("en-bsi-parenthetical", "For E33, BSI, not Mandiri, qualifies as a state-owned bank."),
    # prepositional "without/senza/tanpa" opens a phrase, it negates nothing
    ("en-work-without", "E33 allows you, without a separate permit, to work in Indonesia."),
    ("it-work-senza", "L'E33 consente, senza un permesso separato, di lavorare in Indonesia."),
    (
        "id-work-tanpa",
        "E33 mengizinkan Anda, tanpa izin kerja tambahan, untuk bekerja di Indonesia.",
    ),
    (
        "en-split-without",
        "For E33, even without another account, you may split the deposit across banks.",
    ),
    (
        "it-split-senza",
        "Per E33, anche senza un conto separato, puoi dividere il deposito fra più banche.",
    ),
    ("en-approval-without", "For E33, even without collateral, approval is guaranteed."),
    (
        "en-split-two-clauses",
        "For E33, you cannot apply without a deposit, but you may split the deposit across banks.",
    ),
]


@pytest.mark.parametrize(
    ("label", "text"),
    NEGATOR_GOVERNMENT_GUILT,
    ids=[label for label, _ in NEGATOR_GOVERNMENT_GUILT],
)
def test_a_negator_that_governs_something_else_does_not_shield_the_claim(
    label: str, text: str
) -> None:
    violations = check_e33_claims(text)
    assert violations, (
        f"{label} states a forbidden claim as fact and the guard stayed silent: {text!r}"
    )


class TestNegationGovernmentRules:
    """One named test per rule, so a regression names its own cause.

    Each pair is the same claim twice: once genuinely denied (must stay
    silent), once asserted behind a negator that governs something else (must
    fire). A rule that stops working takes exactly one of these red.
    """

    def test_contrast_marker_breaks_government(self):
        assert not check_e33_claims(_EN + "The required income is not USD 1,500 per month.")
        assert check_e33_claims(_EN + "The income is not USD 3,000 but USD 1,500 per month.")

    def test_scope_limiter_breaks_government(self):
        assert not check_e33_claims(_EN + "Approval is not guaranteed.")
        # No semicolon and no contrast marker: only the scope limiter stands
        # between "not only" and a suppression here.
        assert check_e33_claims(
            _EN + "E33 does not only allow residence, it also allows you to work in Indonesia."
        )

    def test_colon_breaks_government(self):
        assert not check_e33_claims(_EN + "The deposit cannot be placed at any bank.")
        assert check_e33_claims(
            _EN + "The deposit rule is not restrictive: any Indonesian bank is acceptable."
        )

    def test_comma_fenced_aside_breaks_government(self):
        assert not check_e33_claims(_EN + "BSI does not qualify as a state-owned bank.")
        assert check_e33_claims(_EN + "BSI, not Mandiri, qualifies as a state-owned bank.")

    def test_prepositional_negators_never_govern(self):
        # Not comma-fenced, so the aside rule cannot cover for this: the only
        # reason "without" fails to suppress is that it is not a negator.
        assert check_e33_claims(
            _EN + "Without any doubt you may split the deposit across several banks."
        )

    def test_a_thousands_separator_is_not_a_sentence_boundary(self):
        """`USD 130.000` must not end the sentence and expose the negator."""
        assert not check_e33_claims(
            "Per E33, il deposito non può essere di USD 130.000 presso qualsiasi banca."
        )


class TestTheWorkClaimKnowsTheProductsOwnName:
    """ "Second Home" must reach the work pattern exactly as "E33" does.

    This pattern was the only one of the ten with `requires_e33_context=False`:
    it hardcoded `\\bE33[A-Z]?\\b` in its own regex rather than using the shared
    context vocabulary, which already knew `second[- ]home`, `rumah kedua` and
    `silver hair`. So the guard was blind to the name clients, marketing pages
    and the bot itself normally use — on the one claim in this set that risks a
    client's immigration status rather than their money.

    A cross-family adversarial probe (2026-08-31) found it by inventing its own
    sentences rather than reusing the corpus above; the negation corpus could
    not have found it, because every sentence in it says "E33".
    """

    GUILTY = [
        ("en-e33", "The E33 allows you to work in Indonesia."),
        ("en-second-home", "The Second Home visa allows you to work in Indonesia."),
        ("en-hyphen", "The Second-Home permit entitles you to employment in Indonesia."),
        ("it-second-home", "Il visto Second Home ti permette di lavorare in Indonesia."),
        ("id-rumah-kedua", "Visa Rumah Kedua memungkinkan Anda bekerja di Indonesia."),
        ("id-second-home", "Visa Second Home mengizinkan Anda bekerja di Indonesia."),
    ]

    INNOCENT = [
        ("en-negated", "The Second Home visa does not allow you to work in Indonesia."),
        ("it-negated", "Il visto Second Home non ti permette di lavorare in Indonesia."),
        ("id-negated", "Visa Rumah Kedua tidak mengizinkan Anda bekerja di Indonesia."),
        (
            "en-residence-carveout",
            "The Second Home visa allows you to reside in Indonesia.",
        ),
    ]

    @pytest.mark.parametrize(("label", "text"), GUILTY, ids=[x for x, _ in GUILTY])
    def test_the_claim_fires_under_every_name_the_product_has(self, label, text):
        assert "e33_permits_local_work" in {v.pattern_id for v in check_e33_claims(text)}, (
            f"{label}: the work claim went unflagged — {text!r}"
        )

    @pytest.mark.parametrize(("label", "text"), INNOCENT, ids=[x for x, _ in INNOCENT])
    def test_correct_sentences_under_those_names_stay_silent(self, label, text):
        assert not check_e33_claims(text), f"{label} is correct but fired: {text!r}"

    def test_the_name_vocabulary_has_exactly_one_definition(self):
        """The context gate and the work pattern must not drift apart again."""
        from backend.services.visa_check import e33_claim_guard as g

        assert g._E33_CONTEXT_RE.pattern == g._E33_NAME
        work = next(p for p in g.E33_FORBIDDEN_PATTERNS if p.pattern_id == "e33_permits_local_work")
        assert "second[- ]home" in work.regex.pattern, (
            "the work pattern no longer carries the shared name vocabulary"
        )
