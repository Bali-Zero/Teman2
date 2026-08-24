"""GARUDA VOA — read-only truth-freshness diagnostic.

This is NOT a test. A test that asserted the real catalogue's current
freshness state would pass today and go red the day someone re-stamps the
file — a time bomb that trains people to edit tests instead of data. This
script exists precisely so a human can ask "what is the real state right
now?" without that trap: it prints each of the three truth sources
`freshness.py` tracks, its stamp, its age, and its verdict, using the real
engine clock (`civil_clock.garuda_today()`) and the real, loaded price
catalogue. It is allowed to print STALE.

Run from ``apps/backend-rag``::

    .venv/bin/python -m backend.services.garuda_flow.freshness_report
"""

from __future__ import annotations

import sys

from backend.services.garuda_flow import freshness
from backend.services.garuda_flow.civil_clock import garuda_today
from backend.services.garuda_flow.pricing import price_catalogue_freshness


def collect_real_reports() -> list[freshness.FreshnessReport]:
    """The real, current freshness state of all three tracked truth sources."""
    today = garuda_today()
    return [
        freshness.nationality_eligibility_freshness(today=today),
        freshness.rule_constants_freshness(today=today),
        price_catalogue_freshness(today=today),
    ]


def main() -> int:
    reports = collect_real_reports()
    today = garuda_today()
    print(f"GARUDA VOA truth-freshness — as of {today.isoformat()} (Asia/Makassar)\n")
    print(freshness.render_report(reports))
    stale = [r for r in reports if r.stale]
    if stale:
        print(
            f"\n{len(stale)} of {len(reports)} truth source(s) STALE — "
            "build_verdict/price_for_case will decline to sell/quote on these."
        )
        return 1
    print(f"\nAll {len(reports)} truth sources FRESH.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
