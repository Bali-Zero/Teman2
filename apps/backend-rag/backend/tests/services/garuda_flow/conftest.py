"""Shared fixtures for the `garuda_flow` test package.

`freshness.py` (G-FRESHNESS-FAIL-CLOSED, DECISIONS.md Q9) makes
`intake.build_verdict` DECLINE, and `pricing.price_for_case` decline to
quote, whenever a real stamp — `nationality_eligibility.RETRIEVED_ON`,
`constants.RULES_VERIFIED_ON`, or the real price catalogue's
``metadata.last_updated`` — is older than its window relative to the
``today`` a test passes in. Most tests in this package fix a historical
``today`` (or, for pricing, use the real wall clock at `civil_clock.
garuda_today()` at time of writing) to exercise engine behaviour that has
nothing to do with freshness — calendar cutoffs, passport validity,
extension limits, real-catalogue price-key wiring. Several of those dates
already fall outside one or more real windows (December 2026 is >90 days
past the nationality list's 2026-08-23 retrieval; the real price catalogue's
2026-05-06 stamp is well past its own 90-day window as of this writing), and
every one of them will eventually fall outside the rest as this repository's
calendar advances. Left unpinned, that would flip an unrelated ACCEPT to
DECLINE (or a confirmed price to "unavailable") out from under a test that
was never about freshness in the first place.

This autouse fixture pins all three checks to FRESH for every test in this
package by default, so freshness is tested ONLY where it is the point of the
test:

- `test_freshness.py` for the `check_freshness`/registry mechanism,
- `TestTruthFreshnessGate` in `test_intake.py` for the `build_verdict`
  integration (nationality/rule-constants),
- `TestPriceCatalogueFreshnessGate` in `test_pricing.py` for the
  `price_for_case` integration (price catalogue).

A test that needs the STALE path, or the REAL unpatched function, calls
`monkeypatch.setattr` (or `monkeypatch.undo()`) again on top of this fixture
within its own body — the same `monkeypatch` fixture instance restores the
TRUE original at teardown regardless of how many times it was re-patched
inside one test.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_flow import freshness, pricing


def _fresh_report(source: str) -> freshness.FreshnessReport:
    return freshness.FreshnessReport(
        source=source,
        verdict=freshness.FreshnessVerdict.FRESH,
        stamp="2026-01-01",
        age_days=0,
        max_age_days=freshness.MAX_AGE_DAYS[source],
        detail="conftest fixture: forced fresh for a test unrelated to freshness",
    )


@pytest.fixture(autouse=True)
def _assume_truth_sheets_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        freshness,
        "nationality_eligibility_freshness",
        lambda *, today: _fresh_report("nationality_eligibility"),
    )
    monkeypatch.setattr(
        freshness,
        "rule_constants_freshness",
        lambda *, today: _fresh_report("rule_constants"),
    )
    monkeypatch.setattr(
        pricing,
        "price_catalogue_freshness",
        lambda *, today, service=None: _fresh_report("price_catalogue"),
    )
