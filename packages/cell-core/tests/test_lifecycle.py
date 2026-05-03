"""Tests for cell_core.lifecycle — maturation phases and confidence gates."""
from datetime import datetime, timedelta, timezone

import pytest


class TestMaturation:
    def _make(self, age_days: int):
        from cell_core.lifecycle import Maturation
        birth = datetime.now(timezone.utc) - timedelta(days=age_days)
        return Maturation(birth_date=birth)

    def test_embrione_phase(self):
        from cell_core.types import Phase
        m = self._make(0)
        assert m.phase == Phase.EMBRIONE
        m2 = self._make(3)
        assert m2.phase == Phase.EMBRIONE

    def test_neonato_phase(self):
        from cell_core.types import Phase
        m = self._make(4)
        assert m.phase == Phase.NEONATO
        m2 = self._make(14)
        assert m2.phase == Phase.NEONATO

    def test_giovane_phase(self):
        from cell_core.types import Phase
        m = self._make(15)
        assert m.phase == Phase.GIOVANE
        m2 = self._make(30)
        assert m2.phase == Phase.GIOVANE

    def test_adulto_phase(self):
        from cell_core.types import Phase
        m = self._make(31)
        assert m.phase == Phase.ADULTO
        m2 = self._make(179)
        assert m2.phase == Phase.ADULTO

    def test_anziano_phase(self):
        from cell_core.types import Phase
        m = self._make(180)
        assert m.phase == Phase.ANZIANO
        m2 = self._make(365)
        assert m2.phase == Phase.ANZIANO

    def test_can_act(self):
        assert not self._make(0).can_act()
        assert self._make(5).can_act()
        assert self._make(20).can_act()
        assert self._make(50).can_act()

    def test_can_dream(self):
        assert not self._make(0).can_dream()
        assert not self._make(5).can_dream()
        assert self._make(20).can_dream()
        assert self._make(50).can_dream()
        assert self._make(200).can_dream()

    def test_can_reason_deep(self):
        assert not self._make(0).can_reason_deep()
        assert not self._make(5).can_reason_deep()
        assert self._make(20).can_reason_deep()

    def test_confidence_thresholds(self):
        assert self._make(0).action_confidence_threshold() == 1.1
        assert self._make(5).action_confidence_threshold() == 0.8
        assert self._make(20).action_confidence_threshold() == 0.5
        assert self._make(50).action_confidence_threshold() == 0.0
        assert self._make(200).action_confidence_threshold() == 0.0

    def test_tick_increments_total_pulses(self):
        m = self._make(10)
        assert m.total_pulses == 0
        m.tick(1)
        assert m.total_pulses == 1
        m.tick(2)
        assert m.total_pulses == 2

    def test_age_days_property(self):
        m = self._make(42)
        assert m.age_days == 42

    def test_to_prompt_context(self):
        m = self._make(50)
        ctx = m.to_prompt_context()
        assert "adulto" in ctx.lower()
        assert "50" in ctx
