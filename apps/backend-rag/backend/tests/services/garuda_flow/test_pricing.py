"""Exact-key pricing boundary tests for the GARUDA preview/archive."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from backend.services.garuda_flow import freshness, pricing
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.pricing import (
    catalogue_last_updated_stamp,
    price_for_case,
    price_freshness_for_case,
)

# A fixed, fresh-relative pair used by every test below that isn't
# specifically exercising the freshness gate itself (that's
# `TestPriceCatalogueFreshnessGate`) — chosen well inside the 90-day
# `price_catalogue` window so those tests stay about key-matching, not dates.
_FRESH_LAST_UPDATED = "2026-01-01"
_TODAY_WITHIN_WINDOW = date(2026, 1, 15)


class _PricingStub:
    def __init__(self, row: object, *, last_updated: str | None = _FRESH_LAST_UPDATED) -> None:
        self.row = row
        self.keys: list[str] = []
        self.prices: dict[str, Any] = (
            {"metadata": {"last_updated": last_updated}} if last_updated is not None else {}
        )

    def get_service_by_key(self, key: str) -> Any:
        self.keys.append(key)
        return self.row

    def search_service(self, query: str) -> None:
        raise AssertionError(f"fuzzy search must never run: {query}")


@pytest.mark.parametrize(
    ("case_type", "key", "price", "expected"),
    [
        (CaseType.ISSUANCE, "B1 Visa on Arrival (VOA)", "790.000 IDR", 790_000),
        (
            CaseType.EXTENSION,
            "B1 Visa on Arrival Extension",
            "850.000 IDR",
            850_000,
        ),
    ],
)
def test_price_for_case_uses_only_the_exact_official_key(
    case_type: CaseType,
    key: str,
    price: str,
    expected: int,
) -> None:
    pricing = _PricingStub({"key": key, "price": price})

    assert price_for_case(case_type, pricing=pricing, today=_TODAY_WITHIN_WINDOW) == (  # type: ignore[arg-type]
        expected,
        key,
    )
    assert pricing.keys == [key]


@pytest.mark.parametrize(
    "row",
    [
        None,
        {},
        {"key": "B1 Visa on Arrival Extension", "price": "850.000 IDR"},
        {"key": "B1 Visa on Arrival (VOA)"},
        {"key": "B1 Visa on Arrival (VOA)", "price": "Contact"},
        {"key": "B1 Visa on Arrival (VOA)", "price": "790000"},
        {"key": "B1 Visa on Arrival (VOA)", "price": 0},
        {"key": "B1 Visa on Arrival (VOA)", "price": -1},
        {"key": "B1 Visa on Arrival (VOA)", "price": True},
        {"key": "B1 Visa on Arrival (VOA)", "price": 790_000.0},
        {"key": "B1 Visa on Arrival (VOA)", "price": 1},
        {"key": "B1 Visa on Arrival (VOA)", "price": 999_999_999_999},
    ],
)
def test_price_for_case_fails_closed_on_missing_drifted_or_malformed_rows(
    row: object,
) -> None:
    pricing = _PricingStub(row)

    assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW) == (  # type: ignore[arg-type]
        None,
        None,
    )


class TestCatalogueLastUpdatedStamp:
    def test_reads_the_metadata_last_updated_field(self) -> None:
        pricing = _PricingStub({"key": "x"}, last_updated="2026-05-06")
        assert catalogue_last_updated_stamp(pricing) == "2026-05-06"  # type: ignore[arg-type]

    def test_missing_prices_attribute_reads_as_no_stamp(self) -> None:
        class _NoPricesAttr:
            pass

        assert catalogue_last_updated_stamp(_NoPricesAttr()) is None  # type: ignore[arg-type]

    def test_prices_without_metadata_reads_as_no_stamp(self) -> None:
        class _NoMetadata:
            prices: dict[str, Any] = {"services": {}}

        assert catalogue_last_updated_stamp(_NoMetadata()) is None  # type: ignore[arg-type]

    def test_metadata_without_last_updated_reads_as_no_stamp(self) -> None:
        pricing = _PricingStub({"key": "x"}, last_updated=None)
        assert catalogue_last_updated_stamp(pricing) is None  # type: ignore[arg-type]


class TestPriceCatalogueFreshnessGate:
    """Proven to bite both ways: a fresh catalogue prices the case, a stale
    one declines to quote via the EXISTING `(None, None)` shape — never a
    new one — exactly like a missing/malformed row already does.

    `conftest.py`'s autouse fixture pins `pricing.price_catalogue_freshness`
    to a canned FRESH report for every OTHER test in this package (so real
    dates/the real catalogue can't flip an unrelated assertion) — these
    tests exist specifically to test THAT function, so each starts with
    `monkeypatch.undo()` to reach the real, unpatched wiring.
    """

    _KEY = "B1 Visa on Arrival (VOA)"
    _ROW = {"key": _KEY, "price": "790.000 IDR"}

    def test_catalogue_exactly_at_the_90_day_window_still_prices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="2026-01-01")
        today = date(2026, 4, 1)  # exactly 90 days after 2026-01-01
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            790_000,
            self._KEY,
        )

    def test_catalogue_one_day_past_the_window_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="2026-01-01")
        today = date(2026, 4, 2)  # 91 days after 2026-01-01
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            None,
            None,
        )
        # the row IS looked up (needed to check for a per-row `verified_on`
        # override — see TestPerRowVerifiedOnAttestation) — but since this row
        # carries none, the catalogue-wide stamp governs and it is stale.
        assert pricing.keys == [self._KEY]

    def test_catalogue_with_no_stamp_at_all_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated=None)
        assert price_for_case(  # type: ignore[arg-type]
            CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW
        ) == (None, None)

    def test_catalogue_with_a_malformed_stamp_declines_to_quote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        pricing = _PricingStub(self._ROW, last_updated="not-a-date")
        assert price_for_case(  # type: ignore[arg-type]
            CaseType.ISSUANCE, pricing=pricing, today=_TODAY_WITHIN_WINDOW
        ) == (None, None)


class TestPerRowVerifiedOnAttestation:
    """A per-row ``verified_on`` stamp is a NARROWING of the catalogue-wide
    freshness gate, never an exemption from it: it only ever governs the ONE
    row that carries it, using the exact same fail-closed window/parsing
    rules as `metadata.last_updated` (`freshness.check_freshness`).

    Every test here starts with `monkeypatch.undo()` — same reason as
    `TestPriceCatalogueFreshnessGate` — because the point of these tests IS
    the freshness wiring the autouse fixture would otherwise mask.
    """

    _KEY = "B1 Visa on Arrival (VOA)"
    _STALE_CATALOGUE = "2026-01-01"  # >90d before every `today` used below

    def test_a_fresh_row_stamp_quotes_despite_a_stale_catalogue_stamp(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        row = {"key": self._KEY, "price": "790.000 IDR", "verified_on": "2026-08-01"}
        pricing = _PricingStub(row, last_updated=self._STALE_CATALOGUE)
        today = date(2026, 8, 25)  # 111d past the catalogue stamp, 24d past the row stamp
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            790_000,
            self._KEY,
        )

    def test_a_row_stamp_itself_past_the_window_still_declines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        row = {"key": self._KEY, "price": "790.000 IDR", "verified_on": "2026-01-01"}
        # The catalogue stamp is fresh here — proves the row stamp is a
        # NARROWING (it can make a fresh catalogue decline), not just a
        # one-directional escape hatch.
        pricing = _PricingStub(row, last_updated="2026-08-01")
        today = date(2026, 8, 25)  # 91d past the row stamp, only 24d past the catalogue stamp
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            None,
            None,
        )

    def test_a_row_without_verified_on_still_falls_back_to_the_catalogue_stamp_and_goes_stale(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        row = {"key": self._KEY, "price": "790.000 IDR"}  # no verified_on at all
        pricing = _PricingStub(row, last_updated=self._STALE_CATALOGUE)
        today = date(2026, 8, 25)  # 111d past the (only) catalogue stamp
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            None,
            None,
        )

    @pytest.mark.parametrize(
        "malformed_verified_on",
        [
            "",
            "not-a-date",
            "2026/08/25",
            "2026-13-40",
            123,
            123.0,
            True,
            [],
            {},
        ],
    )
    def test_a_malformed_row_stamp_fails_closed_never_falling_back_to_the_catalogue(
        self, monkeypatch: pytest.MonkeyPatch, malformed_verified_on: object
    ) -> None:
        monkeypatch.undo()
        row = {
            "key": self._KEY,
            "price": "790.000 IDR",
            "verified_on": malformed_verified_on,
        }
        # Catalogue stamp is FRESH — if a malformed row stamp ever fell back
        # to it, this would wrongly quote. It must not.
        pricing = _PricingStub(row, last_updated="2026-08-01")
        today = date(2026, 8, 25)
        assert price_for_case(CaseType.ISSUANCE, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            None,
            None,
        )

    def test_row_verified_on_is_never_consulted_for_the_extension_case_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity: the per-row lookup is keyed off the row actually returned
        for THIS case_type, not a global toggle — an EXTENSION lookup with
        its own fresh verified_on quotes on its own key/amount."""
        monkeypatch.undo()
        ext_key = "B1 Visa on Arrival Extension"
        row = {"key": ext_key, "price": "850.000 IDR", "verified_on": "2026-08-01"}
        pricing = _PricingStub(row, last_updated=self._STALE_CATALOGUE)
        today = date(2026, 8, 25)
        assert price_for_case(CaseType.EXTENSION, pricing=pricing, today=today) == (  # type: ignore[arg-type]
            850_000,
            ext_key,
        )


class TestFreshnessDecisionAlwaysPassesThroughThePatchableSeam:
    """Tripwire against a specific regression class: `price_for_case`'s
    freshness decision must ALWAYS be reachable by monkeypatching
    `pricing.price_catalogue_freshness` by that exact name — the one seam
    every existing consumer patches (`conftest.py` in this package AND in
    `tests/app/routers/`, the router's own stale/fresh tests,
    `freshness_report.collect_real_reports`).

    A prior version of the per-row attestation feature routed row-scoped
    freshness through a SEPARATE function (`price_freshness_for_row`) that
    `price_catalogue_freshness` was never consulted for, once a row carried
    its own `verified_on` — silently disconnecting every one of those
    consumers from the two rows the funnel actually sells. This test proves
    that class of bug cannot recur: it patches `price_catalogue_freshness` to
    a spy, deliberately gives the row a FRESH `verified_on` (the exact shape
    that broke the seam before), and requires BOTH that the spy was actually
    called AND that its verdict — not the row's own attestation — is what
    `price_for_case` obeys.
    """

    _KEY = "B1 Visa on Arrival (VOA)"

    def test_patching_price_catalogue_freshness_overrides_even_a_fresh_row_attestation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        calls: list[dict[str, object]] = []

        def _spy(**kwargs: object) -> freshness.FreshnessReport:
            calls.append(kwargs)
            return freshness.FreshnessReport(
                source="price_catalogue",
                verdict=freshness.FreshnessVerdict.STALE,
                stamp="2020-01-01",
                age_days=9_999,
                max_age_days=freshness.MAX_AGE_DAYS["price_catalogue"],
                detail="tripwire: forced stale via the one patchable seam",
            )

        monkeypatch.setattr(pricing, "price_catalogue_freshness", _spy)

        # The row carries its OWN fresh verified_on — the exact condition
        # under which the seam was previously bypassed entirely.
        row = {"key": self._KEY, "price": "790.000 IDR", "verified_on": "2026-08-01"}
        stub = _PricingStub(row, last_updated="2026-08-01")
        today = date(2026, 8, 25)

        result = price_for_case(CaseType.ISSUANCE, pricing=stub, today=today)

        assert calls, (
            "price_for_case never called pricing.price_catalogue_freshness — its "
            "freshness decision bypassed the one seam every test/report patches"
        )
        assert result == (None, None), (
            "pricing.price_catalogue_freshness was patched to STALE but price_for_case "
            "quoted anyway — the row's own attestation overrode the patched seam "
            "instead of the seam being authoritative"
        )


class TestPriceFreshnessForCase:
    """`price_freshness_for_case` is the reporting-only twin of the freshness
    decision `price_for_case` makes internally — used by
    `freshness_report.collect_real_reports` so the operator can see "the row
    we actually sell" separately from the catalogue-wide stamp. It must agree
    with `price_for_case` on every row shape, since both go through the same
    `price_catalogue_freshness(key=..., row=...)` seam.
    """

    def test_reports_the_rows_own_verified_on_when_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        row = {
            "key": "B1 Visa on Arrival (VOA)",
            "price": "790.000 IDR",
            "verified_on": "2026-08-01",
        }
        stub = _PricingStub(row, last_updated="2026-01-01")  # catalogue-wide stale
        report = price_freshness_for_case(
            CaseType.ISSUANCE, today=date(2026, 8, 25), service=stub
        )
        assert report.source == "price_catalogue.row[B1 Visa on Arrival (VOA)]"
        assert not report.stale

    def test_falls_back_to_the_catalogue_wide_stamp_when_the_row_has_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()
        row = {"key": "B1 Visa on Arrival (VOA)", "price": "790.000 IDR"}
        stub = _PricingStub(row, last_updated="2026-01-01")
        report = price_freshness_for_case(
            CaseType.ISSUANCE, today=date(2026, 8, 25), service=stub
        )
        assert report.source == "price_catalogue"
        assert report.stale

    def test_a_lookup_failure_reads_as_no_row_and_still_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.undo()

        class _BrokenStub:
            prices = {"metadata": {"last_updated": "2026-01-01"}}

            def get_service_by_key(self, key: str) -> object:
                raise RuntimeError("boom")

        report = price_freshness_for_case(
            CaseType.ISSUANCE, today=date(2026, 8, 25), service=_BrokenStub()  # type: ignore[arg-type]
        )
        assert report.source == "price_catalogue"
        assert report.stale


def test_collect_real_reports_distinguishes_catalogue_wide_from_the_two_sellable_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structural regression test for the operator-facing report: it must
    carry the catalogue-wide stamp AND the two individually-attested rows as
    SEPARATE entries with distinguishable sources — not collapse them back
    into one number, which is the exact defect this shape was added to fix.
    Deliberately does not assert FRESH/STALE verdicts (that would couple the
    test to the real file's current date, the anti-pattern this session was
    asked to avoid elsewhere) — only that the five expected sources are all
    present and distinct.

    `monkeypatch.undo()` because `price_freshness_for_case`'s internal call to
    `price_catalogue_freshness` resolves dynamically through `pricing`'s
    module namespace and IS affected by this package's autouse
    fresh-everything fixture — this test is specifically about the real,
    unpatched wiring's SHAPE.
    """
    monkeypatch.undo()
    from backend.services.garuda_flow.freshness_report import collect_real_reports

    reports = collect_real_reports()
    sources = [r.source for r in reports]
    assert sources == [
        "nationality_eligibility",
        "rule_constants",
        "price_catalogue",
        "price_catalogue.row[B1 Visa on Arrival (VOA)]",
        "price_catalogue.row[B1 Visa on Arrival Extension]",
    ]
    assert len(set(sources)) == len(sources), "duplicate source labels collapse distinct facts"
