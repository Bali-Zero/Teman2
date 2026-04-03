# apps/cell/tests/test_maturation.py
"""Tests for Maturation lifecycle phases."""
import pytest
from cell.lifecycle.maturation import Maturation, LifecyclePhase


class TestMaturationPhases:
    def test_embrione_day0(self):
        m = Maturation(age_days=0)
        assert m.phase == LifecyclePhase.EMBRIONE

    def test_embrione_day3(self):
        m = Maturation(age_days=3)
        assert m.phase == LifecyclePhase.EMBRIONE

    def test_neonato_day4(self):
        m = Maturation(age_days=4)
        assert m.phase == LifecyclePhase.NEONATO

    def test_neonato_day14(self):
        m = Maturation(age_days=14)
        assert m.phase == LifecyclePhase.NEONATO

    def test_giovane_day15(self):
        m = Maturation(age_days=15)
        assert m.phase == LifecyclePhase.GIOVANE

    def test_giovane_day30(self):
        m = Maturation(age_days=30)
        assert m.phase == LifecyclePhase.GIOVANE

    def test_adulto_day31(self):
        m = Maturation(age_days=31)
        assert m.phase == LifecyclePhase.ADULTO

    def test_anziano_day180(self):
        m = Maturation(age_days=180)
        assert m.phase == LifecyclePhase.ANZIANO


class TestMaturationCapabilities:
    def test_embrione_no_actions(self):
        m = Maturation(age_days=1)
        assert m.can_act() is False
        assert m.can_dream() is False
        assert m.can_reason_deep() is False

    def test_neonato_can_reason_not_act_autonomously(self):
        m = Maturation(age_days=5)
        assert m.can_reason_deep() is False  # neonato cannot use Qwen 27B
        assert m.can_dream() is False
        assert m.can_act() is True

    def test_giovane_can_dream(self):
        m = Maturation(age_days=20)
        assert m.can_dream() is True
        assert m.can_act() is True

    def test_adulto_full_autonomy(self):
        m = Maturation(age_days=50)
        assert m.can_act() is True
        assert m.can_dream() is True
        assert m.can_reason_deep() is True

    def test_confidence_threshold_embrione(self):
        m = Maturation(age_days=2)
        assert m.action_confidence_threshold() == 1.1

    def test_confidence_threshold_neonato(self):
        m = Maturation(age_days=7)
        assert m.action_confidence_threshold() == 0.8

    def test_confidence_threshold_adulto(self):
        m = Maturation(age_days=40)
        assert m.action_confidence_threshold() == 0.0

    def test_confidence_threshold_giovane(self):
        m = Maturation(age_days=20)
        assert m.action_confidence_threshold() == 0.5


class TestMaturationPromptContext:
    def test_to_prompt_context_includes_phase(self):
        m = Maturation(age_days=20)
        ctx = m.to_prompt_context()
        assert "giovane" in ctx
        assert "age=20d" in ctx
