"""Safety mechanisms — kill switches + DNA integrity + budget validation."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from cell_core.types import DNAConfig, DNARule, Proposal, SafetyCheckResult

logger = logging.getLogger("cell_core.safety")


class DNAIntegrityError(Exception):
    """Raised when DNA file has been tampered with."""


class SafetyGate:
    """Kill switch + maintenance mode. Organ-agnostic."""

    def __init__(self, disable_file: str = "/tmp/cell.disabled", redis: Any = None, cell_name: str = "cell") -> None:
        self._disable_file = Path(disable_file)
        self._redis = redis
        self._cell_name = cell_name

    async def check(self) -> SafetyCheckResult:
        if self._disable_file.exists():
            return SafetyCheckResult(can_proceed=False, reason="disabled", detail=f"Disable file exists: {self._disable_file}")
        if self._redis is not None:
            try:
                disabled = await self._redis.get(f"cell:{self._cell_name}:disabled")
                if disabled is not None:
                    return SafetyCheckResult(can_proceed=False, reason="disabled", detail="Redis kill switch active")
                maintenance = await self._redis.get(f"cell:{self._cell_name}:maintenance")
                if maintenance is not None:
                    return SafetyCheckResult(can_proceed=False, reason="maintenance", detail="Maintenance mode via Redis")
            except Exception as e:
                logger.debug(f"Redis unavailable for safety check: {e}")
        return SafetyCheckResult(can_proceed=True)


class DNALoader:
    """Loads and verifies the immutable DNA file."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def raw_bytes(self) -> bytes:
        return self._path.read_bytes()

    def load(self) -> DNAConfig:
        data = json.loads(self.raw_bytes())
        rules = [DNARule(text=r["text"], priority=r.get("priority", i + 1)) for i, r in enumerate(data.get("rules", []))]
        return DNAConfig(rules=rules, constraints=data.get("constraints", {}))

    def compute_hash(self) -> str:
        return hashlib.sha256(self.raw_bytes()).hexdigest()

    def verify_integrity(self, expected_hash: str) -> bool:
        return self.compute_hash() == expected_hash

    def verify_or_raise(self, expected_hash: str) -> DNAConfig:
        if not self.verify_integrity(expected_hash):
            raise DNAIntegrityError(f"DNA tampered! Expected {expected_hash[:16]}..., got {self.compute_hash()[:16]}...")
        return self.load()


class DNAInterpreter:
    """Validates proposed actions against DNA rules + constraints."""

    def __init__(self, dna: DNAConfig) -> None:
        self._dna = dna

    def validate(self, proposal: Proposal, budget_spent: float) -> SafetyCheckResult:
        if proposal.action == "none":
            return SafetyCheckResult(can_proceed=True)
        max_budget = self._dna.constraints.get("max_daily_budget_usd", 10.0)
        max_investigation = self._dna.constraints.get("max_cost_per_investigation_usd", 0.5)
        if budget_spent + proposal.cost_usd > max_budget * 0.9:
            return SafetyCheckResult(can_proceed=False, reason="Budget exceeded", detail=f"Spent {budget_spent:.2f} + cost {proposal.cost_usd:.2f} > {max_budget * 0.9:.2f}")
        if proposal.cost_usd > max_investigation:
            return SafetyCheckResult(can_proceed=False, reason="Investigation cost too high", detail=f"Cost {proposal.cost_usd:.2f} > max {max_investigation:.2f}")
        return SafetyCheckResult(can_proceed=True)
