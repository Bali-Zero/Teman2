"""Rule-based visa recommender for the Visa Match wizard.

Input: nationality (ISO-3), purpose, duration_months, budget_band.
Output: MatchResult with a `ranking` list (best → worst) and backwards-compat
        properties (`recommended_visa`, `reason`, `alternatives`,
        `pre_arrival_steps`, `referral_mode`) read by the router.

Design:
- No hardcoded `VisaType.X` in branch logic. Each branch filters VISA_META
  by purpose tag, scores candidates, returns top-N.
- Scoring is deterministic and visible so users see *why* a rank was chosen.
- Catch-all referral terminates the tree.

Scoring rubric (all additive, clamped to [0.0, 1.0]):
  base:                +0.50
  budget_fit:          +0.25  (visa min-budget ≤ user's band ceiling)
  duration_fit:        +0.20  (visa max-stay ≥ requested months)
  overshoot:           −0.10  (visa covers > 4× requested stay — overkill)
  budget_near_floor:   −0.05  (ceiling < 1.5× visa min — thin headroom)
  high_budget_bonus:   +0.05  (ceiling ≥ 3× visa min — visa is right-sized)
  anti_tourism:        −0.15  (tourism-tagged visa used for non-tourism purpose)
  niche_tag:           −0.15  (E23-FREELANCE niche tag for generic WORK_REMOTE)
  multi_entry:         −0.30  (multiple-entry visa unsuitable for continuous stay)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.services.visa_check.catalogue import FitTag, VisaMeta, VisaType


# VISA_META is imported lazily inside _rank_for_purpose() to break the
# circular import: catalogue._build_meta() imports Purpose from this module,
# so importing VISA_META here at module-load time would create a cycle.
# The lazy import is safe because _rank_for_purpose() is only called after
# both modules have fully initialised.
def _get_visa_meta() -> dict[VisaType, VisaMeta]:
    from backend.services.visa_check.catalogue import VISA_META

    return VISA_META


class Purpose(str, Enum):
    WORK_REMOTE = "work_remote"
    INVESTOR = "investor"
    WORK_EMPLOYEE = "work_employee"
    FAMILY = "family"
    LONG_TOURISM = "long_tourism"
    RETIREMENT = "retirement"
    STUDENT = "student"
    OTHER = "other"


class BudgetBand(str, Enum):
    UNDER_50M = "under_50m"
    MID_50_500M = "50m_500m"
    OVER_500M = "over_500m"


_BUDGET_CEILING: dict[BudgetBand, int] = {
    BudgetBand.UNDER_50M: 50_000_000,
    BudgetBand.MID_50_500M: 500_000_000,
    BudgetBand.OVER_500M: 10_000_000_000,
}


@dataclass(frozen=True)
class RankedVisa:
    visa: VisaType
    score: float  # 0.0 – 1.0
    reason: str  # 1–2 sentences, user-facing
    fit_tags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class MatchResult:
    ranking: list[RankedVisa]
    pre_arrival_steps: list[str]
    referral_mode: bool
    referral_reason: str = ""  # used when ranking is empty

    # ── Backwards-compat properties (router + existing tests) ────

    @property
    def recommended_visa(self) -> VisaType | None:
        return self.ranking[0].visa if self.ranking else None

    @property
    def reason(self) -> str:
        if self.ranking:
            return self.ranking[0].reason
        return self.referral_reason

    @property
    def alternatives(self) -> list[VisaType]:
        return [rv.visa for rv in self.ranking[1:]]


# ── Pre-arrival step libraries ───────────────────────────────────

_STEPS_TOURISM: list[str] = [
    "Passport valid ≥ 6 months from entry date",
    "Confirmed accommodation for first 7 nights",
    "Return or onward flight ticket",
    "Travel insurance covering Indonesia",
]

_STEPS_DIGITAL_NOMAD: list[str] = [
    "Proof of remote employment with a foreign company",
    "Bank statement showing ≥ USD 60,000 balance (12 months)",
    "Passport valid ≥ 18 months",
    "Health insurance with Indonesia coverage",
    "CV + LinkedIn URL for immigration review",
]

_STEPS_FREELANCE: list[str] = [
    "Sample invoices to Indonesian clients (past 6 months)",
    "NPWP application plan (Indonesian tax ID)",
    "Passport valid ≥ 18 months",
    "Proof of accommodation in Indonesia",
]

_STEPS_INVESTOR: list[str] = [
    "PT PMA incorporated (or plan ready to incorporate on arrival)",
    "Investment plan document (IDR equivalent ≥ 10bn for E28A)",
    "Share capital confirmation",
    "Proposed business address in Indonesia",
    "Passport valid ≥ 24 months",
]

_STEPS_EMPLOYEE: list[str] = [
    "RPTKA from sponsoring Indonesian employer",
    "Signed employment contract",
    "Education certificate (notarised + translated)",
    "Curriculum vitae",
    "Passport valid ≥ 18 months",
]

# Shared by both retirement routes. The route-specific money line is
# prepended per product by `_steps_for` — see `_STEPS_BY_VISA` below.
_STEPS_RETIREMENT: list[str] = [
    "Passport valid ≥ 18 months",
    "Proof of accommodation (rental or property in Indonesia)",
    "Domestic helper hire letter (optional but recommended)",
    "Health insurance valid in Indonesia",
]

_STEPS_FAMILY: list[str] = [
    "Sponsor's KITAS/KITAP + passport copies",
    "Marriage or birth certificate (notarised + translated)",
    "Passport valid ≥ 18 months",
    "Proof of joint household (photos + rental/ownership docs)",
]

_STEPS_STUDENT: list[str] = [
    "Acceptance letter from an accredited Indonesian university",
    "Sponsor letter (university or direct bursary)",
    "Passport valid ≥ the full study programme",
    "Health insurance valid in Indonesia",
]


_STEPS_BY_PURPOSE: dict[Purpose, list[str]] = {
    Purpose.LONG_TOURISM: _STEPS_TOURISM,
    Purpose.WORK_REMOTE: _STEPS_DIGITAL_NOMAD,
    Purpose.INVESTOR: _STEPS_INVESTOR,
    Purpose.WORK_EMPLOYEE: _STEPS_EMPLOYEE,
    Purpose.RETIREMENT: _STEPS_RETIREMENT,
    Purpose.FAMILY: _STEPS_FAMILY,
    Purpose.STUDENT: _STEPS_STUDENT,
}


#: Financial requirements that belong to ONE product, prepended to the
#: purpose-level list for the visa actually recommended.
#:
#: These cannot live in `_STEPS_BY_PURPOSE`. The result is rendered as an
#: ordered "Pre-arrival checklist" in the frontend and introduced in the funnel
#: email as "make sure you have the <visa> essentials" — i.e. as ONE visa's
#: mandatory list. Putting both routes' money lines in it would tell an E33F
#: client to place a USD 50,000 deposit they do not need, and would show an
#: E33E client "no deposit required" immediately above a deposit.
#:
#: The two senior routes (the official catalogue names them "Retirement KITAS
#: (55+)" and "Retirement KITAS (Variant)") DO share the USD 3,000/month income
#: requirement; only E33E adds a deposit on top. Both figures map to
#: `confirmed` entries in research/secondhome/e33-fact-registry.json
#: (e33e_requirements, e33f_requirements) and to the official catalogue's own
#: wording ("Proof of USD 50,000 deposit in state bank (within 90 days)").
_STEPS_BY_VISA: dict[VisaType, list[str]] = {
    VisaType.E33E: [
        "USD 50,000 deposit at a state-owned (BUMN) Indonesian bank, placed "
        "within 90 days of arrival",
        "Proof of pension or passive income \u2265 USD 3,000/month",
    ],
    VisaType.E33F: [
        "Proof of pension or passive income \u2265 USD 3,000/month "
        "\u2014 this route requires no deposit",
    ],
}


def _steps_for(visa: VisaType | None, purpose: Purpose) -> list[str]:
    """Pre-arrival steps for the recommended VISA, not merely its purpose.

    One purpose can rank several products with different money requirements,
    and every caller presents this list as a single visa's mandatory
    checklist — so a purpose-level list cannot carry a product-level figure.
    """
    shared = _STEPS_BY_PURPOSE.get(purpose, [])
    if visa is None:
        return shared
    return _STEPS_BY_VISA.get(visa, []) + shared


# ── Scoring ──────────────────────────────────────────────────────


def _budget_fits(meta: VisaMeta, band: BudgetBand) -> bool:
    """True if the user's budget band ceiling strictly exceeds the visa's min_budget_idr.

    Strict `>` so that a visa with min_budget_idr == 50,000,000 (e.g. E33G)
    is NOT considered affordable at the under-50M band (ceiling 50M). This
    keeps the band semantics consistent with their labels:
    - UNDER_50M  = budget strictly less than 50M
    - MID_50_500M = budget in [50M, 500M)
    - OVER_500M  = budget > 500M (ceiling effectively unbounded)
    """
    if meta.min_budget_idr is None:
        return True
    return _BUDGET_CEILING[band] > meta.min_budget_idr


def _duration_fits(meta: VisaMeta, months: int) -> bool:
    """True if the visa's base + extensions cover the requested months."""
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    return total_days >= months * 30


def _score(meta: VisaMeta, purpose: Purpose, months: int, band: BudgetBand) -> float:
    """Deterministic score in [0.0, 1.0]. See module docstring for rubric."""
    score = 0.5
    budget_ceiling = _BUDGET_CEILING[band]

    # Budget fit bonus
    if _budget_fits(meta, band):
        score += 0.25

    # Duration fit bonus
    if _duration_fits(meta, months):
        score += 0.2

    # Duration overshoot penalty: visa covers > 4× requested stay (overkill)
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    if total_days > months * 30 * 4:
        score -= 0.1

    # Budget near-floor penalty: thin headroom between ceiling and min
    if meta.min_budget_idr is not None and budget_ceiling < meta.min_budget_idr * 1.5:
        score -= 0.05

    # High-budget preference bonus: visa is right-sized for this budget band
    if meta.min_budget_idr is not None and budget_ceiling >= meta.min_budget_idr * 3:
        score += 0.05

    # Anti-tourism penalty: tourism-tagged visa used for a non-tourism purpose.
    # C1/C2/C6 are valid short-term fallbacks but are semantically off-target
    # for users who identify as remote workers, investors, etc.
    if purpose != Purpose.LONG_TOURISM and Purpose.LONG_TOURISM in meta.purposes:
        score -= 0.15

    # Niche tag penalty: E23_FREELANCE is specifically for users billing
    # Indonesian clients, not for the generic "work remotely for a foreign
    # employer" use-case that WORK_REMOTE implies by default.
    if FitTag.INVOICES_INDONESIAN_CLIENTS in meta.fit_tags and purpose == Purpose.WORK_REMOTE:
        score -= 0.15

    # Multi-entry penalty: D2 / multi-entry visas assume frequent short trips
    # and are semantically unsuitable for users planning continuous residence.
    if FitTag.MULTI_ENTRY in meta.fit_tags:
        score -= 0.30

    return max(0.0, min(1.0, round(score, 3)))


def _reason(meta: VisaMeta, purpose: Purpose, months: int, band: BudgetBand) -> str:
    """Short user-facing sentence explaining why this visa is ranked here."""
    del purpose, band  # reserved for future per-branch phrasing
    budget_note = ""
    if meta.min_budget_idr is not None:
        budget_note = f" (requires ≥ IDR {meta.min_budget_idr // 1_000_000}M)"
    total_days = meta.duration_days + meta.extensions[0] * meta.extensions[1]
    if _duration_fits(meta, months):
        duration_note = f" Covers {total_days} days total."
    else:
        duration_note = f" Max stay {total_days} days — less than your {months}-month plan."
    return f"{meta.name_en} — {meta.notes}{budget_note}.{duration_note}".strip()


# ── Branch dispatch ──────────────────────────────────────────────


def _rank_for_purpose(
    purpose: Purpose,
    months: int,
    band: BudgetBand,
    max_results: int,
) -> list[RankedVisa]:
    candidates: list[RankedVisa] = []
    for visa_type, meta in _get_visa_meta().items():
        if purpose not in meta.purposes:
            continue
        if meta.min_budget_idr is not None and not _budget_fits(meta, band):
            # Hard-exclude visas whose minimum budget the user cannot meet.
            continue
        score = _score(meta, purpose, months, band)
        candidates.append(
            RankedVisa(
                visa=visa_type,
                score=score,
                reason=_reason(meta, purpose, months, band),
                fit_tags=meta.fit_tags,
            )
        )
    # Sort by score desc, then by code for deterministic tie-break.
    candidates.sort(key=lambda rv: (-rv.score, rv.visa.value))
    return candidates[:max_results]


_MAX_RESULTS: dict[Purpose, int] = {
    Purpose.WORK_EMPLOYEE: 3,  # E23 + short-term (C18/C22A) alternatives
    Purpose.STUDENT: 2,
    Purpose.FAMILY: 2,
    Purpose.RETIREMENT: 2,
    Purpose.INVESTOR: 3,
    Purpose.WORK_REMOTE: 3,
    Purpose.LONG_TOURISM: 3,
}


#: Human-readable purpose names used inside referral explanations.
#: Every `Purpose` must appear here — `test_every_purpose_has_a_label` enforces
#: it, so a new purpose cannot ship with an explanation that names it `None`.
_PURPOSE_LABEL: dict[Purpose, str] = {
    Purpose.WORK_REMOTE: "remote work",
    Purpose.INVESTOR: "investment",
    Purpose.WORK_EMPLOYEE: "local employment",
    Purpose.FAMILY: "family",
    Purpose.LONG_TOURISM: "tourism",
    Purpose.RETIREMENT: "retirement",
    Purpose.STUDENT: "study",
    Purpose.OTHER: "the purpose you chose",
}


def _covered_purposes_sentence() -> str:
    """List the purposes this form can actually rank, as prose.

    Derived from `Purpose` rather than hardcoded, so adding a purpose updates
    the visitor-facing sentence instead of silently turning it into a lie.
    """
    labels = [_PURPOSE_LABEL[p] for p in Purpose if p is not Purpose.OTHER]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def _explain_empty_ranking(purpose: Purpose, months: int, band: BudgetBand) -> str:
    """Name the specific constraint that eliminated every candidate.

    `_rank_for_purpose` can come back empty for two reasons that mean opposite
    things to the visitor: the catalogue carries no visa for this purpose at
    all, or it carries several but the budget filter excluded every one. A
    single "no visa matches cleanly" for both hides the one fact the visitor
    could act on, so each cause gets its own sentence and its own number.
    """
    tagged = [meta for meta in _get_visa_meta().values() if purpose in meta.purposes]

    if not tagged:
        return (
            f"Our catalogue carries no visa tagged for {_PURPOSE_LABEL[purpose]}, so "
            "there is nothing for us to rank — we would rather tell you that than hand "
            "you a poor match. Indonesia's visa index is wider than this form: tell us "
            "on WhatsApp what you will actually be doing here and we will name the route."
        )

    if not any(_budget_fits(meta, band) for meta in tagged):
        # `_budget_fits` returns True whenever `min_budget_idr is None`, so if
        # nothing fit then every tagged visa carries a minimum — `min()` below
        # can never run over an empty sequence.
        cheapest = min(meta.min_budget_idr for meta in tagged if meta.min_budget_idr is not None)
        return (
            f"Every {_PURPOSE_LABEL[purpose]} visa we rank carries a minimum-budget "
            "requirement above the band you selected — the cheapest one starts at "
            f"IDR {cheapest:,}. On WhatsApp we can work out whether a staged approach "
            "gets you there, or whether a different route fits what you have today."
        )

    return (
        f"We hold {len(tagged)} {_PURPOSE_LABEL[purpose]} route(s), and none of them "
        f"came through our ranking for a {months}-month stay at your budget band. That "
        "combination is unusual enough that it deserves a person rather than a form — "
        "15 minutes on WhatsApp."
    )


def recommend_visa(
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    budget_band: BudgetBand,
) -> MatchResult:
    """Return a ranked list of visas + pre-arrival steps.

    Rules:
    1. `OTHER` always refers to WhatsApp.
    2. Under-budget investors refer (E28A, D12, E33G all require budget).
    3. Tourism > 6 months refers (Indonesian tourism visas cap at ~180d).
    4. Everything else: filter VISA_META by purpose tag, score, top-N.

    Invariant on every referral (ruled by Zero, 2026-08-28): the reason must
    name the specific constraint that blocked us — quoting the stay length,
    the purpose, or a real IDR figure — and must tell the visitor where to go
    next. A generic "your case needs a conversation" is not an explanation.
    Enforced across the whole input space by
    `tests/services/visa_check/test_match_tree_referral_reasons.py`.
    """
    del nationality  # reserved for future visa-waiver rules
    months = max(1, min(60, int(duration_months)))

    if purpose == Purpose.OTHER:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                f"This form ranks visas for {_covered_purposes_sentence()} — you told "
                "us none of those is your reason for coming. The visa follows the "
                "activity, so we will not reverse-engineer one from a duration and a "
                f"budget. We do have your {months}-month horizon and your budget band; "
                "what is missing is what you will actually be doing in Indonesia. "
                "That is one question on WhatsApp, and the official index names far "
                "more categories than a four-step form can ask about."
            ),
        )

    if purpose == Purpose.LONG_TOURISM and months > 6:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                f"Indonesia's tourism visas max out at ~180 days. For a "
                f"{months}-month stay, we need a non-tourism route (investor, "
                "digital nomad, retirement) that matches what you actually "
                "plan to do here. Tell us on WhatsApp which of those fits and "
                "we will name the visa."
            ),
        )

    if purpose == Purpose.INVESTOR and budget_band == BudgetBand.UNDER_50M:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=(
                "Investor routes (E28A, D12, E33G) all have minimum-capital or "
                "savings requirements that a sub-IDR 50M budget does not meet. "
                "Let's talk through what kind of business you want to open on "
                "WhatsApp — there may be a staged approach."
            ),
        )

    ranking = _rank_for_purpose(
        purpose,
        months,
        budget_band,
        max_results=_MAX_RESULTS.get(purpose, 3),
    )

    if not ranking:
        return MatchResult(
            ranking=[],
            pre_arrival_steps=[],
            referral_mode=True,
            referral_reason=_explain_empty_ranking(purpose, months, budget_band),
        )

    return MatchResult(
        ranking=ranking,
        pre_arrival_steps=_steps_for(ranking[0].visa, purpose),
        referral_mode=False,
    )
