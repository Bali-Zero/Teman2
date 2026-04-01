"""LongTermMemory — weekly condensation of pulse patterns into learned rules.

Reads the last 7 days of pulse_log from PostgreSQL, identifies
recurring patterns, and writes a compact summary ("learned rules")
to the cell_ltm table. The reasoner injects this summary into its
system prompt to improve future decisions.

Schema (auto-created):
  cell_ltm (id SERIAL, created_at TIMESTAMPTZ, week_start DATE,
            rule_text TEXT, support_count INT)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("cell.memory.ltm")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cell_ltm (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    week_start   DATE NOT NULL,
    rule_text    TEXT NOT NULL,
    support_count INT NOT NULL DEFAULT 1
);
"""

# Minimum occurrences for a pattern to become a rule
_MIN_SUPPORT = 3


@dataclass
class LearnedRule:
    rule_text: str
    support_count: int
    week_start: str


class LongTermMemory:
    """Condenses 7 days of pulse_log into actionable rules.

    Call condense_weekly() from cell_weekly_report.py or a Sunday cron.
    Call load_rules() to inject context into the reasoner.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def ensure_table(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE)

    async def condense_weekly(self) -> list[LearnedRule]:
        """Read last 7 days of pulse_log, extract patterns, persist rules."""
        await self.ensure_table()

        week_start = (datetime.now(timezone.utc) - timedelta(days=7)).date()

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT health_status, action_taken, response_time_ms, budget_spent
                FROM pulse_log
                WHERE created_at >= NOW() - INTERVAL '7 days'
                ORDER BY created_at
                """,
            )

        if not rows:
            logger.info("LTM: no pulse_log data for this week")
            return []

        rules = self._extract_rules(rows)

        async with self._pool.acquire() as conn:
            # Delete old rules for this week_start to avoid duplicates
            await conn.execute("DELETE FROM cell_ltm WHERE week_start = $1", week_start)
            for rule in rules:
                await conn.execute(
                    "INSERT INTO cell_ltm (week_start, rule_text, support_count) VALUES ($1, $2, $3)",
                    week_start,
                    rule.rule_text,
                    rule.support_count,
                )

        logger.info(f"LTM: condensed {len(rows)} pulses → {len(rules)} rules for week {week_start}")
        return rules

    async def load_rules(self, max_rules: int = 10) -> list[LearnedRule]:
        """Load the most recent learned rules for reasoner context injection."""
        try:
            await self.ensure_table()
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT rule_text, support_count, week_start::text
                    FROM cell_ltm
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    max_rules,
                )
            return [
                LearnedRule(
                    rule_text=r["rule_text"],
                    support_count=r["support_count"],
                    week_start=r["week_start"],
                )
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"LTM load_rules failed: {e}")
            return []

    def _extract_rules(self, rows: list[Any]) -> list[LearnedRule]:
        """Derive rules from pulse history using simple frequency analysis."""
        rules: list[LearnedRule] = []
        week_start = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()

        total = len(rows)
        if total == 0:
            return rules

        # Pattern 1: Dominant health status
        status_counts: dict[str, int] = {}
        for r in rows:
            s = r["health_status"] or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        for status, count in status_counts.items():
            pct = int(count / total * 100)
            if count >= _MIN_SUPPORT:
                rules.append(LearnedRule(
                    rule_text=f"Health was '{status}' in {pct}% of pulses this week ({count}/{total})",
                    support_count=count,
                    week_start=week_start,
                ))

        # Pattern 2: Most frequent action taken
        action_counts: dict[str, int] = {}
        for r in rows:
            a = r["action_taken"]
            if a:
                action_counts[a] = action_counts.get(a, 0) + 1

        for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
            if count >= _MIN_SUPPORT:
                rules.append(LearnedRule(
                    rule_text=f"Action '{action}' was taken {count} times this week — recurring issue",
                    support_count=count,
                    week_start=week_start,
                ))

        # Pattern 3: High response time episodes
        slow_count = sum(1 for r in rows if (r["response_time_ms"] or 0) > 3000)
        if slow_count >= _MIN_SUPPORT:
            rules.append(LearnedRule(
                rule_text=f"Response time exceeded 3000ms in {slow_count} pulses — backend latency issue recurring",
                support_count=slow_count,
                week_start=week_start,
            ))

        # Pattern 4: Budget burn rate
        budgets = [float(r["budget_spent"] or 0) for r in rows if r["budget_spent"]]
        if budgets:
            avg_budget = sum(budgets) / len(budgets)
            if avg_budget > 5.0:
                rules.append(LearnedRule(
                    rule_text=f"Average daily budget spend was ${avg_budget:.2f} — approaching limit",
                    support_count=len(budgets),
                    week_start=week_start,
                ))

        return rules

    def format_for_prompt(self, rules: list[LearnedRule]) -> str:
        """Format rules as a compact string for injection into LLM system prompt."""
        if not rules:
            return ""
        lines = ["LEARNED PATTERNS (last 7 days):"]
        for r in rules[:8]:  # Cap at 8 to avoid bloating prompt
            lines.append(f"  • {r.rule_text}")
        return "\n".join(lines)
