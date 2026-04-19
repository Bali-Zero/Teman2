"""Unit tests for funnel email templates.

We assert on subject + presence of required substitutions; full HTML
rendering is brittle to assert line-by-line, so we only check that the
key dynamic fields appear in the rendered body.
"""

from __future__ import annotations

import pytest

from backend.services.notifications.funnel_email.templates import (
    render_clock,
    render_match_prearrival,
)


class TestClockTemplates:
    @pytest.mark.parametrize(
        "trigger_type",
        [
            "visa_clock_d60",
            "visa_clock_d30",
            "visa_clock_d14",
            "visa_clock_d7",
            "visa_clock_d1",
        ],
    )
    def test_all_triggers_render(self, trigger_type: str):
        r = render_clock(
            trigger_type=trigger_type,
            visa_type="E33G",
            expiry_date="1 Dec 2026",
            whatsapp_url="https://wa.me/628213107363?text=hi",
            unsubscribe_url="https://balizero.com/unsub/tok",
        )
        assert "E33G" in r.subject
        assert "E33G" in r.html or "expires" in r.html
        assert "wa.me" in r.html
        assert "unsub" in r.html

    def test_unknown_trigger_raises(self):
        with pytest.raises(ValueError):
            render_clock(
                trigger_type="visa_clock_unknown",
                visa_type="E33G",
                expiry_date="1 Dec 2026",
                whatsapp_url="",
                unsubscribe_url="",
            )


class TestMatchPreArrival:
    def test_renders_with_steps(self):
        r = render_match_prearrival(
            recommended_visa="E33G",
            arrival_date="1 Dec 2026",
            whatsapp_url="https://wa.me/628213107363",
            pre_arrival_steps=["Passport valid", "Bank statement", "Health insurance"],
            unsubscribe_url="https://balizero.com/unsub/tok",
        )
        assert "E33G" in r.subject
        assert "Passport valid" in r.html
        assert "Bank statement" in r.html
        assert "Health insurance" in r.html
        assert "wa.me" in r.html
