"""Olympus DB Guardian — Rules Engine for loading, applying, and evolving rules."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.services.olympus.models import OlympusRule

logger = logging.getLogger("olympus.rules")


class RulesEngine:
    """Load, query, apply, and evolve operational rules from olympus_rules."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool
        self.rules: dict[str, OlympusRule] = {}

    async def load_rules(self) -> None:
        """Load all active (non-superseded) rules from the database."""
        query = """
            SELECT id, rule_name, category, config, source,
                   confidence, applied_count, last_applied, superseded_by
            FROM olympus_rules
            WHERE superseded_by IS NULL
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        loaded: dict[str, OlympusRule] = {}
        for row in rows:
            rule = OlympusRule(
                id=row["id"],
                rule_name=row["rule_name"],
                category=row["category"],
                config=row["config"],
                source=row["source"],
                confidence=float(row["confidence"]),
                applied_count=row["applied_count"],
                last_applied=row["last_applied"],
                superseded_by=row["superseded_by"],
            )
            loaded[rule.rule_name] = rule

        self.rules = loaded
        logger.info("Loaded %d active rules", len(self.rules))

    def get_threshold(self, rule_name: str, default: Any = None) -> Any:
        """Return the 'value' from a rule's config, or *default* if missing."""
        rule = self.rules.get(rule_name)
        if rule is None:
            return default
        return rule.get_value()

    def get_rule(self, rule_name: str) -> OlympusRule | None:
        """Return the full rule object by name, or None."""
        return self.rules.get(rule_name)

    async def record_applied(self, rule_name: str) -> None:
        """Increment applied_count and touch last_applied / updated_at."""
        now = datetime.now(timezone.utc)
        query = """
            UPDATE olympus_rules
            SET applied_count = applied_count + 1,
                last_applied  = $1,
                updated_at    = $1
            WHERE rule_name = $2
        """
        async with self._pool.acquire() as conn:
            await conn.execute(query, now, rule_name)

        rule = self.rules.get(rule_name)
        if rule is not None:
            rule.applied_count += 1
            rule.last_applied = now

        logger.debug("Rule '%s' applied (count=%d)", rule_name,
                      rule.applied_count if rule else 0)

    async def lower_confidence(
        self, rule_name: str, delta: float = -0.1
    ) -> None:
        """Decrease a rule's confidence (clamped to 0.0). Persists to DB."""
        rule = self.rules.get(rule_name)
        if rule is None:
            logger.warning("Cannot lower confidence: rule '%s' not loaded", rule_name)
            return

        new_confidence = max(0.0, rule.confidence + delta)
        now = datetime.now(timezone.utc)

        query = """
            UPDATE olympus_rules
            SET confidence = $1,
                updated_at = $2
            WHERE rule_name = $3
        """
        async with self._pool.acquire() as conn:
            await conn.execute(query, new_confidence, now, rule_name)

        old_confidence = rule.confidence
        rule.confidence = new_confidence
        logger.warning(
            "Rule '%s' confidence lowered: %.2f -> %.2f",
            rule_name, old_confidence, new_confidence,
        )
