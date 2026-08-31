"""GARUDA VOA — the truth-freshness authority (pure; the registry wraps I/O).

`products/garuda-voa/product.yaml` declares a guardrail, ``G-FRESHNESS-FAIL-
CLOSED``, that has never had a reader. `DECISIONS.md` Q9 decided the windows
in prose; the contract freeze put them into `contracts/openapi.yaml` as
``x-truth-freshness-max-age-days``; and `GROUND.md` §2 confirmed that nothing
in `garuda_flow` compares ``today`` against any of the three dated sources
that exist (``nationality_eligibility.RETRIEVED_ON`` was read by nothing;
the rule constants had no single stamp at all; the price catalogue's
``metadata.last_updated`` was read by a different service entirely). This
module is that reader — the ONE place age-vs-window is computed, so a
freshness check implemented per-lane cannot let one surface decline while
another sells the same stale price.

This module is orchestrator-owned, cross-cutting, and deliberately narrow:
it does not decide what a caller does with a stale verdict (that is
`intake.build_verdict` for the nationality/rule-constants sources, and
`pricing.price_for_case` for the price catalogue — see those modules).

Design decisions, made explicit because each has a defensible alternative
that was NOT chosen, and an untested alternative left in a guardrail is
exactly the defect this module exists to close:

- **The boundary.** Staleness is ``today - stamp > max_age_days`` — strict
  greater-than. A source re-verified on day 0 stays FRESH through the whole
  of day ``max_age_days`` and only goes STALE the day after. The window
  itself IS the safety margin `DECISIONS.md` Q9 chose ("the longest we could
  defend having not looked"); reading it as an inclusive ``<=`` cutoff would
  quietly shave a day off a number the owner already picked deliberately.
- **Fail-closed on absence and on garbage.** A missing stamp, a stamp that
  is not a string, a string that is not a parseable ISO date, or a stamp
  accessor that raises are ALL treated as STALE — never as fresh. "I could
  not tell" must never read as "fine"; that is the entire point of a
  freshness guard, and a guard that treats an unreadable signal as a green
  light is worse than no guard (it actively hides the failure it exists to
  catch).
- **A stamp dated after `today` is not special-cased.** In real production
  traffic this cannot happen — `today` is always
  `civil_clock.garuda_today()`, a wall clock that only advances, and a
  ``RETRIEVED_ON``/``RULES_VERIFIED_ON`` stamp is always in the past at the
  moment it is committed. It DOES happen routinely in this engine's own test
  suite, where fixed historical ``today`` values predate a truth source that
  was verified (or re-verified) later in this repository's real history.
  Rather than invent a third state for an impossible-in-production but
  common-in-fixtures shape, the plain arithmetic comparison is used as-is:
  a negative age is never ``> max_age_days``, so it reads as FRESH. This is
  a considered choice, not an oversight — see
  ``test_a_future_stamp_reads_as_fresh_not_as_an_error`` in
  ``test_freshness.py``.
- **The windows live here, in Python, as the single source of truth**
  (``MAX_AGE_DAYS``). Runtime code never parses the frozen OpenAPI contract;
  instead ``test_freshness_windows_match_the_frozen_contract`` (in
  ``test_freshness.py``) reads `contracts/openapi.yaml`'s
  ``x-truth-freshness-max-age-days`` block and asserts the two agree, so the
  contract and the code can never drift silently in either direction.
- **The operating calendar is deliberately NOT a member of this registry.**
  It already enforces its own bound (`operating_calendar.COVERAGE_START` /
  `COVERAGE_END`) and is the pattern the other three sources copy (Q9);
  adding it here would just be a second, redundant clock on the same fact.

PURE in the narrow sense the rest of this engine uses the word: no network
call, and every comparison takes ``today`` as an explicit parameter (never
reads a clock itself — see `civil_clock.py`). It is NOT free of I/O in the
broader sense: the two convenience readers below import
`nationality_eligibility` / `constants` to read their string constants, and
a stamp accessor a caller supplies (e.g. `pricing.py`'s catalogue reader) may
do real file I/O. ``check_freshness`` treats any such access uniformly and
never assumes it is cheap or side-effect-free.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum

__all__ = [
    "MAX_AGE_DAYS",
    "FreshnessReport",
    "FreshnessVerdict",
    "check_freshness",
    "nationality_eligibility_freshness",
    "render_report",
    "rule_constants_freshness",
]


class FreshnessVerdict(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    """The outcome for ONE truth source, plus enough to explain it to staff.

    ``detail`` is a human-readable diagnostic for the reporter script and
    logs — never serialized to a visitor (this engine's house rule: only a
    closed, neutral machine vocabulary crosses the wire, same as
    `eligibility.DeclineCode`).
    """

    source: str
    verdict: FreshnessVerdict
    stamp: str | None
    age_days: int | None  # None only when the stamp could not be parsed at all
    max_age_days: int
    detail: str

    @property
    def stale(self) -> bool:
        return self.verdict is FreshnessVerdict.STALE


# DECISIONS.md Q9 / contracts/openapi.yaml `x-truth-freshness-max-age-days`.
# SINGLE SOURCE OF TRUTH for the three numbers — the contract mirrors this,
# not the other way around. `test_freshness_windows_match_the_frozen_contract`
# pins the two together so they cannot silently drift.
MAX_AGE_DAYS: dict[str, int] = {
    "nationality_eligibility": 90,
    "rule_constants": 180,
    "price_catalogue": 90,
}


def _parse_iso_date(raw: object) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def check_freshness(
    *,
    source: str,
    stamp_accessor: Callable[[], object],
    max_age_days: int,
    today: date,
) -> FreshnessReport:
    """Evaluate ONE truth source against ``today``. Never raises.

    ``stamp_accessor`` is called exactly once. Any exception it raises is
    itself treated as STALE (fail-closed on "I could not tell" — see the
    module docstring) rather than propagated: a truth-freshness check must
    never be the reason an unrelated request 500s.
    """
    try:
        raw_stamp = stamp_accessor()
    except Exception as exc:  # deliberate broad catch: any failure => STALE, never propagated
        return FreshnessReport(
            source=source,
            verdict=FreshnessVerdict.STALE,
            stamp=None,
            age_days=None,
            max_age_days=max_age_days,
            detail=f"stamp accessor raised {exc.__class__.__name__}: {exc}",
        )

    stamp_str = raw_stamp if isinstance(raw_stamp, str) else None
    parsed = _parse_iso_date(raw_stamp)
    if parsed is None:
        detail = (
            "stamp is missing"
            if raw_stamp is None
            else f"stamp {raw_stamp!r} is not a parseable ISO date (YYYY-MM-DD)"
        )
        return FreshnessReport(
            source=source,
            verdict=FreshnessVerdict.STALE,
            stamp=stamp_str,
            age_days=None,
            max_age_days=max_age_days,
            detail=detail,
        )

    age_days = (today - parsed).days
    verdict = FreshnessVerdict.STALE if age_days > max_age_days else FreshnessVerdict.FRESH
    return FreshnessReport(
        source=source,
        verdict=verdict,
        stamp=stamp_str,
        age_days=age_days,
        max_age_days=max_age_days,
        detail=f"age {age_days}d vs max {max_age_days}d -> {verdict.value}",
    )


def _nationality_eligibility_stamp() -> object:
    from backend.services.garuda_flow.nationality_eligibility import RETRIEVED_ON

    return RETRIEVED_ON


def nationality_eligibility_freshness(*, today: date) -> FreshnessReport:
    """Freshness of the decree-sourced VOA-eligible-nationality list."""
    return check_freshness(
        source="nationality_eligibility",
        stamp_accessor=_nationality_eligibility_stamp,
        max_age_days=MAX_AGE_DAYS["nationality_eligibility"],
        today=today,
    )


def _rule_constants_stamp() -> object:
    from backend.services.garuda_flow.constants import RULES_VERIFIED_ON

    return RULES_VERIFIED_ON


def rule_constants_freshness(*, today: date) -> FreshnessReport:
    """Freshness of the D-7/D-14/eVOA-window/passport-validity rule bundle."""
    return check_freshness(
        source="rule_constants",
        stamp_accessor=_rule_constants_stamp,
        max_age_days=MAX_AGE_DAYS["rule_constants"],
        today=today,
    )


def render_report(reports: list[FreshnessReport]) -> str:
    """One human-readable line per source — the shape the diagnostic script
    and any future ops dashboard print. Never used to drive a decision;
    ``FreshnessReport.stale`` is the only thing callers should branch on.
    """
    lines = []
    for report in reports:
        stamp = report.stamp if report.stamp is not None else "(missing)"
        age = f"{report.age_days}d" if report.age_days is not None else "n/a"
        lines.append(
            f"{report.source:<24} stamp={stamp:<12} age={age:<6} "
            f"max={report.max_age_days}d -> {report.verdict.value}  ({report.detail})"
        )
    return "\n".join(lines)
