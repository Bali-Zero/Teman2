"""Tests for cell_core.safety — kill switches, DNA loader, DNA interpreter."""
import json
import pytest
from cell_core.types import DNAConfig, DNARule, Proposal, SafetyCheckResult


class TestSafetyGate:
    @pytest.mark.asyncio
    async def test_proceeds_when_no_disable_file(self, tmp_path):
        from cell_core.safety import SafetyGate
        gate = SafetyGate(disable_file=str(tmp_path / "nonexistent"))
        result = await gate.check()
        assert result.can_proceed is True

    @pytest.mark.asyncio
    async def test_halts_when_disable_file_exists(self, tmp_path):
        from cell_core.safety import SafetyGate
        disable = tmp_path / "cell.disabled"
        disable.write_text("disabled by operator")
        gate = SafetyGate(disable_file=str(disable))
        result = await gate.check()
        assert result.can_proceed is False
        assert "disabled" in result.reason


class TestDNALoader:
    def test_load_valid_dna(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text(json.dumps({"rules": [{"text": "Never modify DNA", "priority": 1}, {"text": "If broken, repair it", "priority": 2}], "constraints": {"max_daily_budget_usd": 10.0}}))
        loader = DNALoader(str(dna_file))
        config = loader.load()
        assert len(config.rules) == 2
        assert config.rules[0].text == "Never modify DNA"
        assert config.constraints["max_daily_budget_usd"] == 10.0

    def test_verify_hash_matches(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        h = loader.compute_hash()
        assert loader.verify_integrity(h) is True

    def test_verify_hash_mismatch(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        assert loader.verify_integrity("badhash") is False

    def test_verify_or_raise(self, tmp_path):
        from cell_core.safety import DNALoader, DNAIntegrityError
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        with pytest.raises(DNAIntegrityError):
            loader.verify_or_raise("badhash")

    def test_load_missing_file_raises(self):
        from cell_core.safety import DNALoader
        loader = DNALoader("/nonexistent/dna.json")
        with pytest.raises(FileNotFoundError):
            loader.load()


class TestDNAInterpreter:
    def _make_dna(self):
        return DNAConfig(rules=[DNARule(text="Never modify DNA", priority=1)], constraints={"max_daily_budget_usd": 10.0, "max_cost_per_investigation_usd": 0.5})

    def test_approve_within_budget(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="restart_service", reason="test", confidence=0.9, tier_used=0, cost_usd=0.1)
        result = interp.validate(proposal, budget_spent=5.0)
        assert result.can_proceed is True

    def test_reject_over_budget(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="restart_service", reason="test", confidence=0.9, tier_used=0, cost_usd=0.1)
        result = interp.validate(proposal, budget_spent=9.5)
        assert result.can_proceed is False
        assert "budget" in result.reason.lower()

    def test_reject_expensive_investigation(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="investigate", reason="test", confidence=0.9, tier_used=1, cost_usd=0.8)
        result = interp.validate(proposal, budget_spent=0.0)
        assert result.can_proceed is False

    def test_approve_no_action(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="none", reason="stable", confidence=1.0, tier_used=-1)
        result = interp.validate(proposal, budget_spent=0.0)
        assert result.can_proceed is True
