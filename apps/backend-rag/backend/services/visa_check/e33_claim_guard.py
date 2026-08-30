"""E33 Second Home — runtime forbidden-claim guard.

Single source of pattern truth for claims that MUST NOT appear in generated
answers about the E33 Second Home visa vertical. Patterns are derived from
the E33 fact registry (``research/secondhome/e33-fact-registry.json`` v1.0.0,
branch ``backend-rag-e33-fact-registry`` pending merge): facts whose notes
say FORBIDDEN (BSI sharia equivalence, split deposits, ITAP-after-3-years)
plus the legacy error list (``USD 1,500/month`` superseded figure, ``IDR
2,000,000`` 1000x fee error, "LPS fully covers the deposit", "approval
guaranteed", "automatic KITAP", "E33 permits local work", any-bank
placement, ``5-10 years`` first-grant phrasing).

Wiring: ``guard_e33_answer_detailed`` (and the legacy ``guard_e33_answer``
text-only wrapper) is called once in
``backend/services/rag/agentic/orchestrator_core.py`` (``process_query_core``,
right before the final ``return result``) — the single finalization point of
the ReAct-generated answer path. The fallback-note append is unconditional
and non-blocking (never rewrites or removes the model's text). Whether a
violation ALSO routes the answer into the abstain/HUMAN_REVIEW path is an
enforcement decision made by the caller, gated by the
``E33_CLAIM_GUARD_ENFORCE`` env kill-switch (default off) — see
``orchestrator_core.py`` for the wiring, since a ``CoreResult`` mutation
belongs there, not in this stdlib-only module. Cached answers (FAQ/semantic)
are pre-vetted and intentionally not re-checked; KG fast-path answers are
covered by the static surface tests in
``backend/tests/services/visa_check/test_e33_forbidden_claims.py``.

The module is stdlib-only on purpose: importing it can never create import
cycles or I/O, so it is safe to call on the hot path. ``GuardOutcome`` is a
plain frozen dataclass of ``str``/``tuple`` — no pydantic/CoreResult import
here, to keep that guarantee.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Registry fact ids live in research/secondhome/e33-fact-registry.json.
# Legacy errors are not registry facts; they use this sentinel ref.
LEGACY_ERROR_REF = "legacy_error_list"

# Context gate: patterns flagged ``requires_e33_context`` only fire when the
# text is actually about the E33 / Second Home vertical, so unrelated answers
# mentioning e.g. "USD 1,500" are not flagged.
_E33_CONTEXT_RE = re.compile(
    r"\bE33[A-Z]?\b|second[- ]home|rumah\s+kedua|silver\s+hair",
    re.IGNORECASE,
)

E33_SAFE_FALLBACK_NOTE = (
    "Note: some details of the E33 Second Home visa are still pending written "
    "confirmation from the Indonesian immigration authority (Ditjen Imigrasi) "
    "and the state-owned banks. Please verify specific figures and conditions "
    "with the Bali Zero team before making any decision."
)


@dataclass(frozen=True)
class ForbiddenPattern:
    """A claim that must never be stated about the E33 vertical."""

    pattern_id: str
    regex: re.Pattern[str]
    description: str
    registry_ref: str
    requires_e33_context: bool = True


@dataclass(frozen=True)
class ClaimViolation:
    """One forbidden-claim match inside a generated answer."""

    pattern_id: str
    description: str
    matched_text: str
    start: int
    end: int
    registry_ref: str = field(default=LEGACY_ERROR_REF)


# Negation guard: fixed-width lookbehinds so that CORRECT cautionary phrasing
# ("does NOT authorize employment", "approval is not guaranteed", "LPS does not
# fully cover") is not flagged. Heuristic by design — the guard is log-only.
# Negation guard. Python's re requires FIXED-WIDTH lookbehind, so each
# negator is its own assertion rather than one alternation.
#
# Italian and Indonesian negators are here because the guard scans answers in
# whichever language the client wrote in: `wrap_query_with_language_instruction`
# (query_helpers.py) detects the query language and instructs the model to
# reply in the same one, with an explicit Indonesian branch. A guard that only
# knows English negation would fire on a correct Italian sentence that says a
# thing is NOT allowed.
_NEG = (
    r"(?<!not\s)(?<!never\s)(?<!cannot\s)(?<!can't\s)(?<!doesn't\s)"
    r"(?<!non\s)(?<!mai\s)(?<!senza\s)"
    r"(?<!tidak\s)(?<!bukan\s)(?<!jangan\s)(?<!tanpa\s)"
)


def _p(
    pattern_id: str, raw: str, description: str, registry_ref: str, *, ctx: bool = True
) -> ForbiddenPattern:
    return ForbiddenPattern(
        pattern_id=pattern_id,
        regex=re.compile(raw, re.IGNORECASE),
        description=description,
        registry_ref=registry_ref,
        requires_e33_context=ctx,
    )


E33_FORBIDDEN_PATTERNS: tuple[ForbiddenPattern, ...] = (
    _p(
        "e33f_superseded_income_usd1500",
        r"\bUSD\s*1[.,]?500\b",
        "USD 1,500/month is the SUPERSEDED pre-2024 E33F figure; current is USD 3,000/month",
        "e33f_requirements",
    ),
    _p(
        "second_home_any_bank",
        # IT: "qualsiasi/qualunque banca", "banca qualsiasi"
        # ID: "bank mana saja / apa saja", "sembarang bank"
        r"\bany\s+(?:Indonesian\s+)?bank\b"
        r"|\b(?:qualsiasi|qualunque)\s+banca\b"
        r"|\bbanca\s+(?:indonesiana\s+)?(?:qualsiasi|qualunque)\b"
        r"|\bbank\s+(?:\w+\s+){0,2}?(?:mana|apa)\s+saja\b"
        r"|\bsembarang\s+bank\b",
        "Deposit must be at a state-owned (BUMN) Indonesian bank, not 'any bank'",
        "e33_base_deposit_amount",
    ),
    _p(
        "e33_itap_kitap_automatic_promise",
        r"\bautomatic(?:ally)?\b(?!\s+included)[^.\n]{0,25}\b(?:KITAP|ITAP)\b"
        r"|\b(?:KITAP|ITAP)\b[^.\n]{0,40}\bautomatic(?:ally)?\b(?!\s+included)"
        r"|\bafter\s+3\s+years\b[^.\n]{0,50}\b(?:eligible|convert\w*|automatic\w*)\b[^.\n]{0,30}\b(?:KITAP|ITAP)\b"
        # IT: "automatico/automatica/automaticamente"
        r"|\bautomatic(?:o|a|amente)\b[^.\n]{0,30}\b(?:KITAP|ITAP)\b"
        r"|\b(?:KITAP|ITAP)\b[^.\n]{0,40}\bautomatic(?:o|a|amente)\b"
        r"|\bdopo\s+3\s+anni\b[^.\n]{0,50}\b(?:KITAP|ITAP)\b"
        # ID: "otomatis", "setelah 3 tahun"
        r"|\botomatis\b[^.\n]{0,30}\b(?:KITAP|ITAP)\b"
        r"|\b(?:KITAP|ITAP)\b[^.\n]{0,40}\botomatis\b"
        r"|\bsetelah\s+3\s+tahun\b[^.\n]{0,50}\b(?:KITAP|ITAP)\b",
        "ITAP/KITAP conversion after 3 years is pending confirmation — never promise it",
        "itap_after_3y_criteria",
    ),
    _p(
        "e33_permits_local_work",
        rf"\bE33[A-Z]?\b[^.\n]{{0,60}}\b{_NEG}(?<!residence\s)(?<!stay\s)(?:allows?|permits?|authoriz\w*|entitle\w*)\b[^.\n]{{0,40}}\b(?:work|employment)\b"
        rf"|\b{_NEG}work(?:ing)?\s+(?:legally\s+)?(?:in\s+Indonesia\s+)?on\s+(?:the\s+|an\s+)?E33"
        # IT: "l'E33 permette/consente/autorizza ... lavorare/lavoro"
        rf"|\bE33[A-Z]?\b[^.\n]{{0,60}}\b{_NEG}(?:permett\w+|consent\w+|autorizz\w+|abilit\w+)\b[^.\n]{{0,40}}\b(?:lavor\w+|impiego|occupazione)\b"
        # ID: "E33 memungkinkan/mengizinkan/membolehkan ... bekerja/kerja"
        rf"|\bE33[A-Z]?\b[^.\n]{{0,60}}\b{_NEG}(?:memungkinkan|mengizinkan|membolehkan|memperbolehkan)\b[^.\n]{{0,40}}\b(?:bekerja|kerja|pekerjaan)\b",
        "Base E33 is a pure residence permit — it does NOT authorize local employment",
        "e33_not_work_visa",
        ctx=False,
    ),
    _p(
        "bsi_sharia_equivalence",
        r"\b(?:BSI|Bank\s+Syariah\s+Indonesia)\b[^.\n]{0,80}"
        r"\b(?:qualif\w*|accept\w*|state[- ]owned|BUMN|equivalent|counts?\s+as"
        # IT: equivalente / accettata / statale / vale come
        r"|equivalen\w+|accettat\w+|statale|vale\s+come|conta\s+come"
        # ID: setara / diterima / memenuhi syarat / milik negara
        r"|setara|diterima|memenuhi\s+syarat|milik\s+negara)\b",
        "BSI (sharia) placement as qualifying state-bank deposit is unconfirmed — forbidden to claim",
        "bsi_sharia_accepted",
    ),
    _p(
        "split_deposit_accepted",
        r"\bsplit\b[^.\n]{0,40}\bdeposit\b|\bdeposit\b(?:(?!not|never|cannot|can't)[^.\n]){0,40}\bsplit\b"
        r"|\bmultiple\s+(?:BUMN\s+|state[- ]owned\s+)?banks\b[^.\n]{0,50}\bdeposit\b"
        # IT: dividere/suddividere/frazionare/ripartire il deposito; piu' banche
        r"|\b(?:divid\w+|suddivid\w+|frazion\w+|ripart\w+)\b[^.\n]{0,40}\bdeposit\w*\b"
        r"|\bdeposit\w*\b(?:(?!non|mai)[^.\n]){0,40}\b(?:divis\w+|suddivis\w+|frazionat\w+)\b"
        r"|\bpi[uù]\s+banche\b[^.\n]{0,50}\bdeposit\w*\b"
        # ID: membagi/memecah deposito; beberapa bank
        r"|\b(?:membagi|memecah|memisahkan|dibagi|dipecah)\b[^.\n]{0,40}\bdeposit\w*\b"
        r"|\bbeberapa\s+bank\b[^.\n]{0,50}\bdeposit\w*\b",
        "Splitting the USD 130,000 deposit across multiple banks is unconfirmed — forbidden to claim",
        "split_deposit_accepted",
    ),
    _p(
        "lps_full_coverage",
        rf"\bLPS\b[^.\n]{{0,60}}\b{_NEG}(?:full(?:y)?|100\s*%|entire(?:ly)?|whole)\b"
        rf"|\b{_NEG}(?:full(?:y)?|100\s*%|entire(?:ly)?)\b[^.\n]{{0,40}}\b(?:covered|guaranteed|insured)\b[^.\n]{{0,30}}\b(?:by\s+)?LPS\b"
        # IT: interamente/totalmente/completamente/integralmente
        rf"|\bLPS\b[^.\n]{{0,60}}\b{_NEG}(?:interament\w+|totalment\w+|completament\w+|integralment\w+)\b"
        rf"|\b{_NEG}(?:interament\w+|totalment\w+|completament\w+|integralment\w+)\b[^.\n]{{0,40}}\b(?:copert\w+|garantit\w+|assicurat\w+)\b[^.\n]{{0,30}}\bLPS\b"
        # ID: sepenuhnya/seluruhnya/penuh
        rf"|\bLPS\b[^.\n]{{0,60}}\b{_NEG}(?:sepenuhnya|seluruhnya|penuh)\b"
        rf"|\b{_NEG}(?:sepenuhnya|seluruhnya|penuh)\b[^.\n]{{0,40}}\b(?:dijamin|ditanggung|diasuransikan)\b[^.\n]{{0,30}}\bLPS\b"
        # Indonesian puts the adverb AFTER the verb ("dijamin sepenuhnya"),
        # the reverse of the English and Italian word order above.
        rf"|\b(?:dijamin|ditanggung|diasuransikan)\s+{_NEG}(?:sepenuhnya|seluruhnya|penuh)\b[^.\n]{{0,30}}\bLPS\b",
        "LPS deposit insurance has a cap — never claim it fully covers the E33 deposit",
        "usd_deposit_rates_and_lps_cap_confirmation",
    ),
    _p(
        "approval_guaranteed",
        rf"\b(?:approval|approved|application|visa)\b[^.\n]{{0,30}}\b(?:is\s+|are\s+)?{_NEG}guaranteed\b"
        rf"|\b{_NEG}guaranteed\s+(?:approval|visa)\b"
        # IT: "l'approvazione e' garantita", "visto garantito"
        rf"|\b(?:approvazione|domanda|visto|esito)\b[^.\n]{{0,30}}\b(?:[eè]\s+|sono\s+)?{_NEG}garantit[oaie]\b"
        rf"|\b{_NEG}garantit[oa]\s+(?:l[ea']\s*)?(?:approvazione|visto)\b"
        # ID: "persetujuan dijamin", "visa terjamin"
        rf"|\b(?:persetujuan|permohonan|visa|hasil)\b[^.\n]{{0,30}}\b{_NEG}(?:dijamin|terjamin|pasti\s+disetujui)\b"
        rf"|\b{_NEG}(?:dijamin|terjamin)\s+(?:persetujuan|visa)\b",
        "Visa approval is never guaranteed",
        LEGACY_ERROR_REF,
    ),
    _p(
        "idr_2m_fee_error",
        r"\bIDR\s*2[.,]?000[.,]?000\b",
        "IDR 2,000,000 is the 1000x legacy fee error for the E33 vertical",
        LEGACY_ERROR_REF,
    ),
    _p(
        "second_home_first_grant_5_10_years",
        r"\b5\s*[-–]\s*10\s*years?\b",
        "Base E33 first grant is up to 5 years; '5-10 years' mixes in other first-grant categories",
        "e33_first_grant_duration",
    ),
)


#: Sentence terminators. A negation only shields a claim inside its OWN
#: sentence — "Approval is not guaranteed. You may split the deposit." must
#: still flag the second clause.
#: A sentence boundary. A period BETWEEN DIGITS is a thousands separator, not
#: the end of a sentence: Italian and Indonesian write the very figures this
#: guard exists to police as "USD 130.000" / "USD 1.500". Reading those dots as
#: full stops moved the search window past the negator and made the verdict
#: depend on which locale's separator the sentence happened to use.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<!\d)\.(?!\d)|[!?;:\n]")

#: Negators in the three languages this guard actually sees. The bot answers in
#: whichever language the client wrote in (`wrap_query_with_language_instruction`),
#: so an English-only negation guard fires on correct Italian and Indonesian
#: sentences that say a thing is NOT allowed.
#:
#: PREPOSITIONAL negators are deliberately ABSENT — no "without", no "senza",
#: no "tanpa". They open a phrase, they do not negate the claim that follows:
#: "E33 allows you, without a separate permit, to work in Indonesia" asserts
#: the forbidden claim while carrying a negator. Their removal costs a few
#: false positives and closes a whole class of false negatives.
_NEGATOR_RE = re.compile(
    r"\b(?:not|never|cannot|can\'t|don\'t|doesn\'t|isn\'t|aren\'t|neither"
    r"|non|mai|nessun\w*"
    r"|tidak|bukan|jangan|belum)\b",
    re.IGNORECASE,
)

#: "not X **but** Y" — the negator governs X, and Y is asserted. A contrast
#: marker between a negator and the claim therefore PROVES the negator does not
#: reach it. This is the construction that broke the previous heuristic on 27
#: adversarial sentences, among them "the required income is not USD 3,000 but
#: USD 1,500 per month" — the superseded figure, stated as fact, silently
#: suppressed because a "not" appeared earlier in the clause.
_CONTRAST_RE = re.compile(
    r"\b(?:but|rather|instead"
    r"|ma|bensì|bensi|invece|anzi|piuttosto"
    r"|melainkan|tetapi|namun|justru)\b",
    re.IGNORECASE,
)

#: "not ONLY X" scopes the negation to the quantifier, never to the predicate:
#: "E33 does not only allow residence, it also allows you to work" asserts the
#: forbidden claim. Same for "approval is not merely likely; it is guaranteed".
_SCOPE_LIMITER_RE = re.compile(
    r"\W*\b(?:only|just|merely|simply"
    r"|solo|soltanto|solamente|semplicemente"
    r"|hanya|sekadar|sekedar|semata)\b",
    re.IGNORECASE,
)

#: A negator fenced inside a comma-delimited aside governs the aside, not the
#: predicate: "BSI, not Mandiri, qualifies as a state-owned bank" ASSERTS that
#: BSI qualifies. The closing comma must fall before the claim ends, which is
#: what separates the aside from an ordinary "not X, only Y" correction.
_PARENTHETICAL_OPEN_RE = re.compile(r",\s*$")

#: How far back a negator may sit and still be read as negating this claim.
#: Deliberately short. A wider window suppresses more false positives but buys
#: it with FALSE NEGATIVES, and the two are not symmetric here: a false
#: positive parks a correct answer for a human to glance at, while a false
#: negative sends a forbidden claim to a client. When in doubt, flag.
_NEGATION_WINDOW = 40


def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """True if a negator GOVERNS the claim spanning ``match_start:match_end``.

    Presence is not government. The previous version answered "is there a
    negator nearby", which a contrast clause turns into a silencer: an
    adversarial matrix of 29 sentences that each state a forbidden claim after
    negating something else was suppressed 27 times. Three tests now stand
    between a negator and a suppression:

    1. it must lie in the same sentence (``_SENTENCE_BOUNDARY_RE``, which knows
       a thousands separator from a full stop) and within ``_NEGATION_WINDOW``;
    2. no contrast marker may sit between it and the claim — "not X **but** Y"
       asserts Y;
    3. it must not be a scope limiter — "not **only** X" asserts X.

    The span searched runs to ``match_end``, not ``match_start``: several
    patterns swallow the negator themselves ("KITAP is not automatic after 3
    years" matches from "KITAP"), and those ARE correct cautionary sentences.
    Rules 2 and 3 are what keep that span from becoming a loophole — they are
    applied to the text between the negator and the end of the claim, so a
    contrast inside the match disqualifies the negator exactly as one before it
    does.
    """
    window_start = max(0, match_start - _NEGATION_WINDOW)
    sentence_start = window_start
    for boundary in _SENTENCE_BOUNDARY_RE.finditer(text, window_start, match_start):
        sentence_start = boundary.end()

    for negator in _NEGATOR_RE.finditer(text, sentence_start, match_end):
        tail_start = negator.end()
        if _SCOPE_LIMITER_RE.match(text, tail_start):
            continue  # "not only" — the predicate is asserted, not denied
        if _CONTRAST_RE.search(text, tail_start, match_end):
            continue  # "not X but Y" — this negator governs X, not the claim
        if (
            _PARENTHETICAL_OPEN_RE.search(text, sentence_start, negator.start())
            and text.find(",", tail_start, match_end) != -1
        ):
            continue  # ", not X," — an aside; the predicate is still asserted
        if _SENTENCE_BOUNDARY_RE.search(text, tail_start, match_end):
            # The negator sits INSIDE a match that swallowed a sentence break:
            # "LPS does not cover a fraction; it fully covers the deposit."
            # Government stops at the break, so it does not reach the claim.
            continue
        return True
    return False


def check_e33_claims(text: str) -> list[ClaimViolation]:
    """Flag registry-forbidden E33 claims in ``text``.

    Deterministic regex scan, no I/O. Patterns that require E33 context are
    skipped when the text does not mention the E33 / Second Home vertical.
    """
    if not text:
        return []
    has_context = bool(_E33_CONTEXT_RE.search(text))
    violations: list[ClaimViolation] = []
    for pattern in E33_FORBIDDEN_PATTERNS:
        if pattern.requires_e33_context and not has_context:
            continue
        for match in pattern.regex.finditer(text):
            if _is_negated(text, match.start(), match.end()):
                continue
            violations.append(
                ClaimViolation(
                    pattern_id=pattern.pattern_id,
                    description=pattern.description,
                    matched_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    registry_ref=pattern.registry_ref,
                )
            )
    return violations


@dataclass(frozen=True)
class GuardOutcome:
    """Result of a guard pass: the (possibly note-appended) text plus the raw
    violations, so a caller can decide on enforcement beyond the note-append
    (e.g. routing to abstain). Plain dataclass of stdlib types only — see
    module docstring on why ``CoreResult`` is never imported here.
    """

    answer: str
    violations: tuple[ClaimViolation, ...]

    @property
    def has_violation(self) -> bool:
        return bool(self.violations)


def guard_e33_answer_detailed(answer: str) -> GuardOutcome:
    """Scan, log, and append the fallback note — same contract as
    ``guard_e33_answer`` — but also return the violations found, so the
    caller can additionally enforce (e.g. set ``CoreResult.abstain``).

    Non-blocking by contract: never raises, never rewrites or removes any of
    the model's original text (only appends). Returns the original answer
    unchanged (and an empty violations tuple) when nothing is flagged.
    """
    try:
        violations = check_e33_claims(answer)
    except Exception:  # pragma: no cover - defensive; guard must never break the hot path
        logger.exception("[E33Guard] check failed — returning answer unguarded")
        return GuardOutcome(answer=answer, violations=())
    if not violations:
        return GuardOutcome(answer=answer, violations=())
    logger.warning(
        "[E33Guard] %d forbidden E33 claim(s) in generated answer: %s",
        len(violations),
        [(v.pattern_id, v.matched_text[:80]) for v in violations],
    )
    guarded = answer.rstrip() + "\n\n" + E33_SAFE_FALLBACK_NOTE
    return GuardOutcome(answer=guarded, violations=tuple(violations))


def guard_e33_answer(answer: str) -> str:
    """Log E33 forbidden-claim violations and append a safe fallback note.

    Non-blocking by contract: never raises, never rewrites or suppresses the
    answer. Returns the original answer unchanged when no violation is found.

    Text-only backward-compat wrapper around ``guard_e33_answer_detailed`` —
    kept because it is the smallest possible surface for a caller that only
    cares about the guarded text, not the violation enforcement decision.
    """
    return guard_e33_answer_detailed(answer).answer


#: Reason code written to ``CoreResult.abstain_reason`` when the enforcement
#: kill-switch is armed and a violation fires. Kept alongside the pattern
#: registry (single source of truth) rather than in orchestrator_core.py.
E33_ABSTAIN_REASON = "e33_forbidden_claim"


def apply_guard_enforcement(
    *,
    has_violation: bool,
    enforce: bool,
    existing_abstain_reason: str | None,
) -> str | None:
    """Pure enforcement decision — no I/O, no CoreResult import.

    Returns the ``abstain_reason`` string the caller should write (combined
    with any pre-existing reason, e.g. a low evidence-score abstain that
    already fired upstream) when the answer should ALSO be routed to
    abstain/HUMAN_REVIEW, or ``None`` when nothing should change.

    Kept separate from ``guard_e33_answer_detailed`` so the decision itself
    is trivially unit-testable without constructing a ``CoreResult`` or an
    ``AgentState`` — see ``test_e33_claim_guard.py::TestApplyGuardEnforcement``.
    """
    if not (has_violation and enforce):
        return None
    if existing_abstain_reason:
        return f"{existing_abstain_reason}+{E33_ABSTAIN_REASON}"
    return E33_ABSTAIN_REASON
