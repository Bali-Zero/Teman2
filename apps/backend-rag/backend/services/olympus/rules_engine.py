"""Olympus v2 — Rules Engine.

Loads rules from DB, provides threshold lookups, records usage,
and lowers confidence on failure. Every public method is called.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

from backend.services.olympus.models import OlympusRule

logger = logging.getLogger("olympus.rules")

SUPERSEDE_ELIGIBLE_SOURCES = frozenset({"learned", "reflexion", "dream"})
PROTECTED_RULE_SOURCES = frozenset({"base", "initial"})


class RulesEngine:
    """Load, query, and evolve operational rules from olympus_rules."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool
        self.rules: dict[str, OlympusRule] = {}

    async def load_rules(self) -> None:
        query = """
            SELECT id, rule_name, category, config, source,
                   confidence, applied_count, last_applied, superseded_by
            FROM olympus_rules
            WHERE superseded_by IS NULL
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        self.rules = {}
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
            self.rules[rule.rule_name] = rule

        logger.info("Loaded %d active rules", len(self.rules))

    def get_threshold(self, rule_name: str, default: Any = None) -> Any:
        rule = self.rules.get(rule_name)
        if rule is None:
            return default
        return rule.get_value()

    async def record_applied(self, rule_name: str) -> None:
        """Increment applied_count and touch last_applied. Called by guardian after each pulse action."""
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET applied_count = applied_count + 1, "
                "last_applied = $1, updated_at = $1 WHERE rule_name = $2",
                now,
                rule_name,
            )
        rule = self.rules.get(rule_name)
        if rule is not None:
            rule.applied_count += 1
            rule.last_applied = now
        logger.debug("Rule '%s' applied (count=%d)", rule_name, rule.applied_count if rule else 0)

    async def lower_confidence(self, rule_name: str, delta: float = -0.1) -> None:
        """Decrease confidence on failure. Called by guardian when a pulse action fails."""
        rule = self.rules.get(rule_name)
        if rule is None:
            return

        new_confidence = max(0.0, rule.confidence + delta)
        now = datetime.now(timezone.utc)

        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE olympus_rules SET confidence = $1, updated_at = $2 WHERE rule_name = $3",
                new_confidence,
                now,
                rule_name,
            )

        old = rule.confidence
        rule.confidence = new_confidence
        logger.warning("Rule '%s' confidence: %.2f -> %.2f", rule_name, old, new_confidence)

    async def supersede(self, old_rule_name: str, new_rule_id: int, reason: str) -> bool:
        """Retire an eligible learned rule in favor of a newer learned rule."""
        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            old_row = await conn.fetchrow(
                """
                SELECT id, rule_name, category, config, source,
                       confidence, superseded_by
                FROM olympus_rules
                WHERE rule_name = $1
                """,
                old_rule_name,
            )
            new_row = await conn.fetchrow(
                """
                SELECT id, rule_name, category, config, source,
                       confidence, superseded_by
                FROM olympus_rules
                WHERE id = $1
                """,
                new_rule_id,
            )

            if not _can_supersede(old_row, new_row):
                logger.info("Rule supersede rejected: old=%s new=%s", old_rule_name, new_rule_id)
                return False

            status = await conn.execute(
                """
                UPDATE olympus_rules
                SET superseded_by = $1, updated_at = $2
                WHERE id = $3
                  AND superseded_by IS NULL
                """,
                new_rule_id,
                now,
                old_row["id"],
            )
            if not _updated_one(status):
                return False

            detail = {
                "old_rule_id": old_row["id"],
                "old_rule_name": old_row["rule_name"],
                "new_rule_id": new_row["id"],
                "new_rule_name": new_row["rule_name"],
                "reason": reason,
                "old_confidence": float(old_row["confidence"]),
                "new_confidence": float(new_row["confidence"]),
            }
            await conn.execute(
                """
                INSERT INTO olympus_actions (
                    rhythm, action_type, target, detail, outcome,
                    rule_applied, reflection, executed_at
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8)
                """,
                "metacognition",
                "rule_superseded",
                old_row["rule_name"],
                json.dumps(detail),
                "success",
                old_row["rule_name"],
                reason,
                now,
            )

        self.rules.pop(old_rule_name, None)
        logger.info("Rule '%s' superseded by id=%s", old_rule_name, new_rule_id)
        return True

    async def propose_supersessions(self, confidence_floor: float = 0.2) -> list[dict[str, Any]]:
        """Find low-confidence learned rules and either propose or enforce supersession."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, rule_name, category, config, source,
                       confidence, created_at, superseded_by
                FROM olympus_rules
                WHERE superseded_by IS NULL
                ORDER BY category, created_at, id
                """
            )

        candidates = _find_supersession_candidates(rows, confidence_floor)
        if not candidates:
            return []

        mode = os.environ.get("OLYMPUS_RULE_SUPERSEDE_MODE", "shadow").strip().lower()
        if mode == "enforce":
            enforced: list[dict[str, Any]] = []
            for candidate in candidates:
                old_row = candidate["old"]
                new_row = candidate["new"]
                reason = candidate["reason"]
                if await self.supersede(old_row["rule_name"], int(new_row["id"]), reason):
                    enforced.append(_proposal_payload(candidate, mode="enforce"))
            return enforced

        now = datetime.now(timezone.utc)
        proposals: list[dict[str, Any]] = []
        async with self._pool.acquire() as conn:
            for candidate in candidates:
                payload = _proposal_payload(candidate, mode="shadow")
                await conn.execute(
                    """
                    INSERT INTO olympus_insights (
                        insight_type, title, content, evidence, source,
                        confidence, applicable_to
                    ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                    """,
                    "recommendation",
                    f"Supersede rule: {payload['old_rule_name']}",
                    (
                        f"Rule '{payload['old_rule_name']}' is below the confidence floor "
                        f"and can be superseded by '{payload['new_rule_name']}'."
                    ),
                    json.dumps(payload),
                    "rules_engine",
                    payload["new_confidence"],
                    [payload["old_rule_name"], payload["new_rule_name"]],
                )
                proposals.append({**payload, "created_at": now.isoformat()})
        return proposals


def _can_supersede(old_row: Any, new_row: Any) -> bool:
    if not old_row or not new_row:
        return False
    if old_row["id"] == new_row["id"]:
        return False
    if old_row["superseded_by"] is not None or new_row["superseded_by"] is not None:
        return False
    old_source = str(old_row["source"]).lower()
    new_source = str(new_row["source"]).lower()
    if old_source in PROTECTED_RULE_SOURCES or old_source not in SUPERSEDE_ELIGIBLE_SOURCES:
        return False
    if new_source not in SUPERSEDE_ELIGIBLE_SOURCES:
        return False
    return old_row["category"] == new_row["category"]


def _updated_one(status: str) -> bool:
    return status.split()[-1:] == ["1"]


def _find_supersession_candidates(rows: list[Any], confidence_floor: float) -> list[dict[str, Any]]:
    active = [row for row in rows if row["superseded_by"] is None]
    candidates: list[dict[str, Any]] = []
    for old_row in active:
        if str(old_row["source"]).lower() not in SUPERSEDE_ELIGIBLE_SOURCES:
            continue
        old_confidence = float(old_row["confidence"])
        if old_confidence > confidence_floor:
            continue
        replacements = [
            new_row for new_row in active
            if _candidate_replaces(old_row, new_row)
        ]
        if not replacements:
            continue
        replacements.sort(
            key=lambda row: (
                float(row["confidence"]),
                _row_get(row, "created_at") or datetime.min.replace(tzinfo=timezone.utc),
                int(row["id"]),
            ),
            reverse=True,
        )
        new_row = replacements[0]
        candidates.append({
            "old": old_row,
            "new": new_row,
            "reason": (
                f"confidence {old_confidence:.2f} <= {confidence_floor:.2f}; "
                f"replacement confidence {float(new_row['confidence']):.2f}"
            ),
        })
    return candidates


def _candidate_replaces(old_row: Any, new_row: Any) -> bool:
    if not _can_supersede(old_row, new_row):
        return False
    if float(new_row["confidence"]) <= float(old_row["confidence"]):
        return False
    return _rule_signature(old_row) == _rule_signature(new_row)


def _rule_signature(row: Any) -> tuple[str, str]:
    config = _parse_config(row["config"])
    for key in ("target", "metric", "key", "threshold_key", "name"):
        value = config.get(key)
        if value:
            return (row["category"], str(value))
    return (row["category"], _rule_family(row["rule_name"]))


def _rule_family(rule_name: str) -> str:
    lowered = rule_name.lower()
    for marker in ("_v", "-v", "_rev", "-rev"):
        idx = lowered.rfind(marker)
        if idx > 0 and lowered[idx + len(marker):].replace("_", "").replace("-", "").isdigit():
            return lowered[:idx]
    return lowered


def _parse_config(config: Any) -> dict[str, Any]:
    if isinstance(config, dict):
        return config
    if isinstance(config, str):
        try:
            parsed = json.loads(config)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError):
        return getattr(row, key, default)


def _proposal_payload(candidate: dict[str, Any], *, mode: str) -> dict[str, Any]:
    old_row = candidate["old"]
    new_row = candidate["new"]
    return {
        "mode": mode,
        "old_rule_id": old_row["id"],
        "old_rule_name": old_row["rule_name"],
        "new_rule_id": new_row["id"],
        "new_rule_name": new_row["rule_name"],
        "reason": candidate["reason"],
        "old_confidence": float(old_row["confidence"]),
        "new_confidence": float(new_row["confidence"]),
        "signature": list(_rule_signature(old_row)),
    }
