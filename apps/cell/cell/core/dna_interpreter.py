"""DNA Interpreter — compiled rule checker.

This is NOT an LLM. This is deterministic Python code that validates
proposed actions against DNA rules. CELL cannot modify this file.

Every action must pass ALL checks before execution.
"""
import logging
import time
from dataclasses import dataclass

from cell.effectors.allowlist import ActionRegistry, ActionNotAllowed

logger = logging.getLogger("cell.dna_interpreter")


@dataclass
class ValidationResult:
    approved: bool
    rule_violated: int | None = None  # DNA rule ID that was violated
    reason: str = ""


# Actions that are NEVER subject to cost elimination (DNA Rule 3 exclusions)
COST_IMMUNE_ACTIONS = frozenset({
    "check_health",
    "alert_human",
    "alert_silent",
})

# Maximum concurrent requests before restart is blocked
LOAD_THRESHOLD_NO_RESTART = 100


class DNAInterpreter:
    """Validates proposed actions against DNA rules.

    This is compiled code. CELL cannot modify it.
    No LLM interpretation. No natural language ambiguity.
    """

    def __init__(self) -> None:
        self._registry = ActionRegistry()
        self._action_history: list[dict] = []  # {action, timestamp}
        self._daily_action_counts: dict[str, int] = {}
        self._last_reset_day: int = 0

    def _reset_daily_if_needed(self) -> None:
        today = time.gmtime().tm_yday
        if today != self._last_reset_day:
            self._daily_action_counts.clear()
            self._last_reset_day = today

    def _check_cooldown(self, action_name: str) -> ValidationResult | None:
        """Check if action is still in cooldown."""
        try:
            action = self._registry.get(action_name)
        except ActionNotAllowed:
            return ValidationResult(
                approved=False, rule_violated=1,
                reason=f"Action '{action_name}' not in allowlist",
            )

        if action.cooldown_seconds == 0:
            return None  # No cooldown

        now = time.time()
        for entry in reversed(self._action_history):
            if entry["action"] == action_name:
                elapsed = now - entry["timestamp"]
                if elapsed < action.cooldown_seconds:
                    remaining = int(action.cooldown_seconds - elapsed)
                    return ValidationResult(
                        approved=False, rule_violated=2,
                        reason=f"Action '{action_name}' in cooldown ({remaining}s remaining)",
                    )
                break  # Only check most recent

        return None  # Not in cooldown

    def _check_daily_limit(self, action_name: str) -> ValidationResult | None:
        """Check if action has exceeded daily limit."""
        self._reset_daily_if_needed()

        try:
            action = self._registry.get(action_name)
        except ActionNotAllowed:
            return ValidationResult(
                approved=False, rule_violated=1,
                reason=f"Action '{action_name}' not in allowlist",
            )

        count = self._daily_action_counts.get(action_name, 0)
        if count >= action.max_per_day:
            return ValidationResult(
                approved=False, rule_violated=3,
                reason=f"Action '{action_name}' hit daily limit ({count}/{action.max_per_day})",
            )

        return None  # Under limit

    def validate(
        self,
        action_name: str,
        budget_spent: float,
        budget_limit: float,
        confidence: float = 0.0,
    ) -> ValidationResult:
        """Validate a proposed action against ALL DNA rules.

        Returns ValidationResult with approved=True only if ALL checks pass.
        """
        # "none" action is always approved (doing nothing is always safe)
        if action_name == "none":
            return ValidationResult(approved=True)

        # Rule 1: Is the action in the allowlist?
        try:
            self._registry.get(action_name)
        except ActionNotAllowed:
            return ValidationResult(
                approved=False, rule_violated=1,
                reason=f"Action '{action_name}' not in allowlist (Rule 1: immutability)",
            )

        # Rule 3: Cost check — don't execute expensive actions when budget is tight
        budget_percent = (budget_spent / budget_limit * 100) if budget_limit > 0 else 100
        if budget_percent > 90 and action_name not in COST_IMMUNE_ACTIONS:
            return ValidationResult(
                approved=False, rule_violated=3,
                reason=f"Budget at {budget_percent:.1f}% — only observation and alerts allowed (Rule 3: cost)",
            )

        # Cooldown check
        cooldown_result = self._check_cooldown(action_name)
        if cooldown_result:
            return cooldown_result

        # Daily limit check
        daily_result = self._check_daily_limit(action_name)
        if daily_result:
            return daily_result

        # Confidence gate: actions with real impact need confidence > 0.6
        impactful_actions = {"restart_service", "scale_up", "scale_down"}
        if action_name in impactful_actions and confidence < 0.6:
            return ValidationResult(
                approved=False, rule_violated=2,
                reason=f"Action '{action_name}' requires confidence > 0.6 (got {confidence:.2f})",
            )

        return ValidationResult(approved=True)

    def record_action(self, action_name: str) -> None:
        """Record that an action was executed (for cooldown/daily limit tracking)."""
        self._action_history.append({
            "action": action_name,
            "timestamp": time.time(),
        })
        self._reset_daily_if_needed()
        self._daily_action_counts[action_name] = self._daily_action_counts.get(action_name, 0) + 1

        # Trim history to last 100 entries
        if len(self._action_history) > 100:
            self._action_history = self._action_history[-100:]
