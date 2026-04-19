"""Tests for the pre_natal gate logic."""
from datetime import datetime, timedelta, timezone

import pytest

from cell_core.types import Phase
from apps.evaluator.seo_cell.phase import SEOPhase, is_pre_natal


_NOW = datetime(2026, 5, 20, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "gsc,leads,age_days,expected_pre_natal",
    [
        # All three thresholds met → graduate (pre_natal = False)
        (80, 3, 28, False),
        # Fails GSC → still pre_natal
        (79, 3, 28, True),
        # Fails leads → still pre_natal
        (80, 2, 28, True),
        # Fails age → still pre_natal
        (80, 3, 27, True),
        # All zero → pre_natal
        (0, 0, 0, True),
        # Over-thresh everywhere → graduate
        (500, 10, 120, False),
    ],
)
def test_pre_natal_gate_and_logic(gsc, leads, age_days, expected_pre_natal):
    birth = _NOW - timedelta(days=age_days)
    assert (
        is_pre_natal(
            gsc_query_count=gsc,
            website_organic_lead_count=leads,
            birth_date=birth,
            min_gsc_queries=80,
            min_leads=3,
            min_age_days=28,
            now=_NOW,
        )
        is expected_pre_natal
    )


def test_seo_phase_capabilities_during_pre_natal():
    phase = SEOPhase(native=Phase.NEONATO, pre_natal=True)
    assert phase.can_learn is False
    assert phase.can_act is False
    assert phase.label == "pre_natal[neonato]"


def test_seo_phase_capabilities_after_graduation():
    phase = SEOPhase(native=Phase.GIOVANE, pre_natal=False)
    assert phase.can_learn is True
    assert phase.can_act is True
    assert phase.label == "giovane"
