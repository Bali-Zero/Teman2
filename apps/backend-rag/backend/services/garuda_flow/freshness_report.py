"""GARUDA VOA — read-only truth-freshness diagnostic.

This is NOT a test. A test that asserted the real catalogue's current
freshness state would pass today and go red the day someone re-stamps the
file — a time bomb that trains people to edit tests instead of data. This
script exists precisely so a human can ask "what is the real state right
now?" without that trap: it prints each truth source `freshness.py` tracks
(nationality eligibility, rule constants, the catalogue-wide price stamp, and
the two individually-attestable VOA rows — see `collect_real_reports`), its
stamp, its age, and its verdict, using the real engine clock
(`civil_clock.garuda_today()`) and the real, loaded price catalogue. It is
allowed to print STALE.

Run from ``apps/backend-rag``::

    .venv/bin/python -m backend.services.garuda_flow.freshness_report
"""

from __future__ import annotations

import sys

from backend.services.garuda_flow import freshness
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.intake import CaseType
from backend.services.garuda_flow.pricing import price_catalogue_freshness, price_freshness_for_case


def collect_real_reports() -> list[freshness.FreshnessReport]:
    """The real, current freshness state of every truth source, PLUS the two
    rows the funnel actually sells.

    The price catalogue has two independent freshness stories that used to
    collapse into one number: `metadata.last_updated` (one stamp over the
    whole ~100-row file) and each VOA row's own `verified_on` attestation
    (owner decision 7, `products/garuda-voa/product.yaml`) — which NARROWS
    the catalogue-wide stamp for exactly the two rows that carry it. Reporting
    only the catalogue-wide figure would have been actively misleading here:
    that stamp is 2026-05-06 and stays >90 days stale indefinitely (nobody is
    re-verifying the other ~98 rows), while the two sellable rows can be
    genuinely fresh on their own attestation — the operator needs to be able
    to tell "the catalogue as a whole is old" (expected, not urgent) apart
    from "the rows we sell are stale" (the funnel is about to stop selling),
    because those carry completely different consequences.

    So this reports FIVE lines, not three: the two engine truth sources,
    the catalogue-wide stamp (unscoped — what governs every unattested row),
    and the ISSUANCE/EXTENSION rows individually (via `price_freshness_for_case`,
    the exact precedence `price_for_case` applies for each).
    """
    today = garuda_today()
    return [
        freshness.nationality_eligibility_freshness(today=today),
        freshness.rule_constants_freshness(today=today),
        price_catalogue_freshness(today=today),
        price_freshness_for_case(CaseType.ISSUANCE, today=today),
        price_freshness_for_case(CaseType.EXTENSION, today=today),
    ]


def main() -> int:
    reports = collect_real_reports()
    today = garuda_today()
    print(f"GARUDA VOA truth-freshness — as of {today.isoformat()} (Asia/Makassar)\n")
    print(freshness.render_report(reports))
    stale = [r for r in reports if r.stale]
    if stale:
        stale_sources = ", ".join(r.source for r in stale)
        print(
            f"\n{len(stale)} of {len(reports)} truth source(s) STALE: {stale_sources}."
        )
        # The unscoped `price_catalogue` line is the catalogue-wide stamp — it
        # governs every row EXCEPT the two that carry their own `verified_on`
        # (owner decision 7). It can sit STALE indefinitely without blocking a
        # single sale, so its presence in `stale` above does NOT by itself mean
        # the funnel has stopped selling — read the `price_catalogue.row[...]`
        # lines (and nationality_eligibility/rule_constants) for that.
        if any(r.source == "price_catalogue" and r.stale for r in reports) and not any(
            r.source.startswith("price_catalogue.row[") and r.stale for r in reports
        ):
            print(
                "  (the catalogue-wide stamp is stale but both sellable rows carry "
                "their own fresh attestation — this is expected, not urgent)"
            )
        return 1
    print(f"\nAll {len(reports)} truth sources FRESH.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
