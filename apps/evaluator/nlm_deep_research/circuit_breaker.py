"""Circuit Breaker FSM for the NLM Deep Research Pipeline.

Implements three circuit breakers (CB_NLM, CB_SOURCE, CB_INTEGRATION)
with automatic and manual recovery, cascade rules, and state persistence
via pipeline_state.json.

States:
    CLOSED  — healthy, requests flow through
    OPEN    — tripped after threshold failures, requests blocked
    HALF_OPEN — testing after timeout, single request allowed

Cascade rules:
    CB_NLM open > 5 days  → CB_SOURCE opens
    CB_SOURCE open > 7 days → CB_INTEGRATION opens
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CB_NLM_FAILURE_THRESHOLD: int = 3
CB_NLM_TIMEOUT_HOURS: int = 4

CB_SOURCE_FAILURE_THRESHOLD: int = 5
CB_SOURCE_TIMEOUT_HOURS: int = -1  # manual close only

CB_INTEGRATION_FAILURE_THRESHOLD: int = 3
CB_INTEGRATION_TIMEOUT_HOURS: int = 12

CASCADE_NLM_TO_SOURCE_DAYS: int = 5
CASCADE_SOURCE_TO_INTEGRATION_DAYS: int = 7

# Default state file location (sibling to this module's package)
_DEFAULT_STATE_PATH: Path = (
    Path(__file__).resolve().parent.parent / "nlm_nb2_pipeline_state.json"
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CBState(Enum):
    """Possible states for a circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CBName(Enum):
    """Canonical names for the three circuit breakers."""

    CB_NLM = "CB_NLM"
    CB_SOURCE = "CB_SOURCE"
    CB_INTEGRATION = "CB_INTEGRATION"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string into a timezone-aware datetime, or None."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# CircuitBreaker dataclass
# ---------------------------------------------------------------------------


@dataclass
class CircuitBreaker:
    """A single circuit breaker with threshold, timeout, and state tracking.

    Attributes:
        name: Canonical name (CB_NLM, CB_SOURCE, CB_INTEGRATION).
        failure_threshold: Number of consecutive failures before tripping.
        timeout_hours: Hours before an OPEN breaker transitions to HALF_OPEN.
            Use -1 for manual-close-only breakers.
        state: Current FSM state.
        failure_count: Running count of consecutive failures.
        last_failure: ISO 8601 timestamp of the most recent failure.
        opened_at: ISO 8601 timestamp when the breaker last moved to OPEN.
    """

    name: CBName
    failure_threshold: int
    timeout_hours: int
    state: CBState = CBState.CLOSED
    failure_count: int = 0
    last_failure: Optional[str] = None
    opened_at: Optional[str] = None

    # -- State queries -------------------------------------------------------

    def get_state(self) -> CBState:
        """Return the current state after evaluating any pending timeout.

        If the breaker is OPEN and the auto-close timeout has elapsed,
        the state transitions to HALF_OPEN before being returned.
        """
        self._evaluate_timeout()
        return self.state

    @property
    def is_open(self) -> bool:
        """Return True if the breaker is currently blocking requests.

        A breaker in OPEN state that has passed its timeout will first
        transition to HALF_OPEN and then report as *not* open.
        """
        return self.get_state() == CBState.OPEN

    def should_allow_request(self) -> bool:
        """Return True if a request should be allowed through.

        Allowed in CLOSED (normal) and HALF_OPEN (probe) states.
        """
        current = self.get_state()
        return current in (CBState.CLOSED, CBState.HALF_OPEN)

    # -- Transition actions --------------------------------------------------

    def record_failure(self) -> None:
        """Record a failure and transition if the threshold is reached.

        In CLOSED state, increments failure_count.  When the count reaches
        the threshold, transitions to OPEN.

        In HALF_OPEN state (probe failed), transitions back to OPEN and
        resets the timeout window.
        """
        now = _now_iso()
        self.failure_count += 1
        self.last_failure = now

        if self.state == CBState.HALF_OPEN:
            # Probe failed — re-open and reset timeout
            self.state = CBState.OPEN
            self.opened_at = now
            logger.warning(
                "Circuit breaker %s: HALF_OPEN -> OPEN (probe failed, "
                "timeout reset)",
                self.name.value,
            )
            return

        if self.state == CBState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CBState.OPEN
                self.opened_at = now
                logger.warning(
                    "Circuit breaker %s: CLOSED -> OPEN "
                    "(failure_count=%d >= threshold=%d)",
                    self.name.value,
                    self.failure_count,
                    self.failure_threshold,
                )
            else:
                logger.info(
                    "Circuit breaker %s: failure recorded "
                    "(failure_count=%d/%d)",
                    self.name.value,
                    self.failure_count,
                    self.failure_threshold,
                )

    def record_success(self) -> None:
        """Record a success.

        In HALF_OPEN state, transitions back to CLOSED and resets counters.
        In CLOSED state, resets the failure count.
        """
        if self.state == CBState.HALF_OPEN:
            self.state = CBState.CLOSED
            self.failure_count = 0
            self.opened_at = None
            logger.info(
                "Circuit breaker %s: HALF_OPEN -> CLOSED (probe succeeded)",
                self.name.value,
            )
        elif self.state == CBState.CLOSED:
            # Reset rolling failure count on success
            self.failure_count = 0

    def force_open(self, reason: str = "") -> None:
        """Force the breaker into OPEN state (e.g. via cascade rule).

        Args:
            reason: Human-readable reason logged with the transition.
        """
        if self.state == CBState.OPEN:
            return
        previous = self.state
        self.state = CBState.OPEN
        self.opened_at = _now_iso()
        logger.warning(
            "Circuit breaker %s: %s -> OPEN (forced: %s)",
            self.name.value,
            previous.value,
            reason or "no reason given",
        )

    def force_close(self) -> None:
        """Manually reset the breaker to CLOSED (used for manual-close breakers)."""
        previous = self.state
        self.state = CBState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        logger.info(
            "Circuit breaker %s: %s -> CLOSED (manual close)",
            self.name.value,
            previous.value,
        )

    # -- Internal ------------------------------------------------------------

    def _evaluate_timeout(self) -> None:
        """Transition from OPEN to HALF_OPEN if the timeout has elapsed.

        Manual-close breakers (timeout_hours == -1) are never auto-promoted.
        """
        if self.state != CBState.OPEN:
            return
        if self.timeout_hours < 0:
            # Manual close only — no automatic transition
            return
        if self.opened_at is None:
            return

        opened_dt = _parse_iso(self.opened_at)
        if opened_dt is None:
            return

        deadline = opened_dt + timedelta(hours=self.timeout_hours)
        if datetime.now(tz=timezone.utc) >= deadline:
            self.state = CBState.HALF_OPEN
            logger.info(
                "Circuit breaker %s: OPEN -> HALF_OPEN "
                "(timeout %dh elapsed)",
                self.name.value,
                self.timeout_hours,
            )

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict matching pipeline_state.json schema."""
        d: dict[str, Any] = {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure,
            "opened_at": self.opened_at,
        }
        if self.timeout_hours < 0:
            d["manual_close_only"] = True
        else:
            d["auto_close_after_hours"] = self.timeout_hours
        return d

    @classmethod
    def from_dict(
        cls,
        name: CBName,
        data: dict[str, Any],
        failure_threshold: int,
        timeout_hours: int,
    ) -> CircuitBreaker:
        """Deserialize from a pipeline_state.json circuit_breakers entry.

        Args:
            name: The canonical breaker name.
            data: The dict stored under ``circuit_breakers.<name>`` in
                pipeline_state.json.
            failure_threshold: Threshold constant for this breaker.
            timeout_hours: Timeout constant for this breaker (-1 = manual).
        """
        return cls(
            name=name,
            failure_threshold=failure_threshold,
            timeout_hours=timeout_hours,
            state=CBState(data.get("state", "CLOSED")),
            failure_count=int(data.get("failure_count", 0)),
            last_failure=data.get("last_failure"),
            opened_at=data.get("opened_at"),
        )


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------


@dataclass
class CircuitBreakerRegistry:
    """Holds all three circuit breakers and enforces cascade rules.

    Usage::

        registry = CircuitBreakerRegistry.load()
        if registry.nlm.should_allow_request():
            try:
                result = call_nlm_api()
                registry.nlm.record_success()
            except Exception:
                registry.nlm.record_failure()
        registry.evaluate_cascades()
        registry.save()

    Attributes:
        nlm: Circuit breaker for NLM API failures.
        source: Circuit breaker for source import failures.
        integration: Circuit breaker for scraper integration failures.
        state_path: Path to the pipeline_state.json file.
    """

    nlm: CircuitBreaker = field(
        default_factory=lambda: CircuitBreaker(
            name=CBName.CB_NLM,
            failure_threshold=CB_NLM_FAILURE_THRESHOLD,
            timeout_hours=CB_NLM_TIMEOUT_HOURS,
        )
    )
    source: CircuitBreaker = field(
        default_factory=lambda: CircuitBreaker(
            name=CBName.CB_SOURCE,
            failure_threshold=CB_SOURCE_FAILURE_THRESHOLD,
            timeout_hours=CB_SOURCE_TIMEOUT_HOURS,
        )
    )
    integration: CircuitBreaker = field(
        default_factory=lambda: CircuitBreaker(
            name=CBName.CB_INTEGRATION,
            failure_threshold=CB_INTEGRATION_FAILURE_THRESHOLD,
            timeout_hours=CB_INTEGRATION_TIMEOUT_HOURS,
        )
    )
    state_path: Path = field(default_factory=lambda: _DEFAULT_STATE_PATH)

    # -- Convenience accessors -----------------------------------------------

    def get(self, name: CBName) -> CircuitBreaker:
        """Return the breaker instance by its canonical name.

        Args:
            name: One of CBName.CB_NLM, CB_SOURCE, CB_INTEGRATION.

        Raises:
            KeyError: If the name does not match a known breaker.
        """
        mapping = {
            CBName.CB_NLM: self.nlm,
            CBName.CB_SOURCE: self.source,
            CBName.CB_INTEGRATION: self.integration,
        }
        if name not in mapping:
            raise KeyError(f"Unknown circuit breaker: {name}")
        return mapping[name]

    # -- Cascade evaluation --------------------------------------------------

    def evaluate_cascades(self) -> None:
        """Apply cascade rules between breakers.

        - If CB_NLM has been OPEN for more than CASCADE_NLM_TO_SOURCE_DAYS,
          CB_SOURCE is forced open.
        - If CB_SOURCE has been OPEN for more than
          CASCADE_SOURCE_TO_INTEGRATION_DAYS, CB_INTEGRATION is forced open.
        """
        self._cascade(
            upstream=self.nlm,
            downstream=self.source,
            cascade_days=CASCADE_NLM_TO_SOURCE_DAYS,
        )
        self._cascade(
            upstream=self.source,
            downstream=self.integration,
            cascade_days=CASCADE_SOURCE_TO_INTEGRATION_DAYS,
        )

    @staticmethod
    def _cascade(
        upstream: CircuitBreaker,
        downstream: CircuitBreaker,
        cascade_days: int,
    ) -> None:
        """Force *downstream* open if *upstream* has been open too long."""
        if upstream.state != CBState.OPEN:
            return
        if upstream.opened_at is None:
            return

        opened_dt = _parse_iso(upstream.opened_at)
        if opened_dt is None:
            return

        deadline = opened_dt + timedelta(days=cascade_days)
        if datetime.now(tz=timezone.utc) >= deadline:
            downstream.force_open(
                reason=(
                    f"cascade from {upstream.name.value} "
                    f"(open > {cascade_days} days)"
                ),
            )

    # -- Persistence ---------------------------------------------------------

    def save(self) -> None:
        """Persist all breaker states into pipeline_state.json.

        Reads the existing file, updates the ``circuit_breakers`` section,
        bumps the ``updated`` timestamp, and writes atomically.
        """
        state = self._read_state_file()

        state["circuit_breakers"] = {
            CBName.CB_NLM.value: self.nlm.to_dict(),
            CBName.CB_SOURCE.value: self.source.to_dict(),
            CBName.CB_INTEGRATION.value: self.integration.to_dict(),
        }
        state["updated"] = _now_iso()

        self._write_state_file(state)
        logger.info("Circuit breaker state saved to %s", self.state_path)

    @classmethod
    def load(cls, state_path: Optional[Path] = None) -> CircuitBreakerRegistry:
        """Load breaker states from pipeline_state.json.

        If the file does not exist or has no ``circuit_breakers`` key,
        returns a registry with all breakers in CLOSED state.

        Args:
            state_path: Override the default state file location.
        """
        path = state_path or _DEFAULT_STATE_PATH
        registry = cls(state_path=path)

        if not path.exists():
            logger.info(
                "State file %s not found — initializing fresh registry",
                path,
            )
            return registry

        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read state file %s: %s — using defaults",
                path,
                exc,
            )
            return registry

        cb_data: dict[str, Any] = state.get("circuit_breakers", {})

        if CBName.CB_NLM.value in cb_data:
            registry.nlm = CircuitBreaker.from_dict(
                name=CBName.CB_NLM,
                data=cb_data[CBName.CB_NLM.value],
                failure_threshold=CB_NLM_FAILURE_THRESHOLD,
                timeout_hours=CB_NLM_TIMEOUT_HOURS,
            )

        if CBName.CB_SOURCE.value in cb_data:
            registry.source = CircuitBreaker.from_dict(
                name=CBName.CB_SOURCE,
                data=cb_data[CBName.CB_SOURCE.value],
                failure_threshold=CB_SOURCE_FAILURE_THRESHOLD,
                timeout_hours=CB_SOURCE_TIMEOUT_HOURS,
            )

        if CBName.CB_INTEGRATION.value in cb_data:
            registry.integration = CircuitBreaker.from_dict(
                name=CBName.CB_INTEGRATION,
                data=cb_data[CBName.CB_INTEGRATION.value],
                failure_threshold=CB_INTEGRATION_FAILURE_THRESHOLD,
                timeout_hours=CB_INTEGRATION_TIMEOUT_HOURS,
            )

        logger.info(
            "Circuit breakers loaded: NLM=%s SOURCE=%s INTEGRATION=%s",
            registry.nlm.state.value,
            registry.source.state.value,
            registry.integration.state.value,
        )
        return registry

    # -- File I/O helpers ----------------------------------------------------

    def _read_state_file(self) -> dict[str, Any]:
        """Read and parse the pipeline state JSON file.

        Returns an empty dict if the file is missing or malformed.
        """
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read %s: %s", self.state_path, exc)
            return {}

    def _write_state_file(self, state: dict[str, Any]) -> None:
        """Write the state dict to disk as formatted JSON.

        Creates parent directories if needed.
        """
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp_path.replace(self.state_path)
        except OSError:
            # Clean up temp file on failure
            tmp_path.unlink(missing_ok=True)
            raise
