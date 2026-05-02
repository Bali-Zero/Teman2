"""7 Leggi Immutabili admission test for cell candidates — Sprint 0 Track C1.

Reference: brainstorm 2026-05-02 round 2 § "7 Leggi admission test obbligatorio".
Codex disagreed with the round-1 flat promotion of 12 cells; round 2 adds an
explicit admission test against the 7 immutable Symbiosis laws so promotion
decisions are grounded in a rubric, not vibes.

Usage::

    from cell_core.admission_test import AdmissionTest, Legge

    cell_definition = {
        "name": "system-doctor-cell",
        "level": "L1",
        "exposes_gui": False,
        "external_sources": ["ollama-local", "fly-api"],
        "publishes_via": "pg_notify",
        "fallback_modes": ["llm_provider_down", "redis_down"],
        "kill_switch": True,
        "depends_on_other_cell_decisions": False,
        "metrics": ["ttr", "error_rate", "throughput"],
    }
    result = AdmissionTest().run_all(cell_definition)
    if result.passed:
        ...
    else:
        print(result.summary())

The 7 checks are intentionally *narrow* — each maps to one Symbiosis Law.
A cell PASSES iff zero blocker violations. Warnings flag situations the
operator should be aware of but don't block promotion.

Cell definitions are plain dicts (loadable from YAML). The schema is
documented in ``docs/cell-core/admission-test-rubric.md`` with a YAML
template + one passing + one failing example per law.

Out of scope:
    - Runtime behaviour validation (this is a static contract check; PulseLoop
      tests cover runtime).
    - Pydantic model — kept as plain dicts for YAML interop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Legge(str, Enum):
    """7 Leggi Immutabili (DNA helix) — see SYMBIOSIS.md."""

    CLI_ONLY = "cli_only"                     # Law 1
    OSINT_BLINDATO = "osint_blindato"         # Law 2
    EVENT_DRIVEN = "event_driven"             # Law 3 (Symbiosis Law 4 in numbering)
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Law 4
    ZERO_FINAL_INSTANCE = "zero_final_instance"    # Law 5
    LOCAL_SOVEREIGNTY = "local_sovereignty"   # Law 6
    NUMBERS_FIRST = "numbers_first"           # Law 7


@dataclass(frozen=True)
class Violation:
    """A specific failure of one of the 7 Leggi."""

    legge: Legge
    message: str
    severity: str  # "blocker" | "warning"


@dataclass
class AdmissionResult:
    """Verdict on a cell candidate against the 7 Leggi."""

    cell_name: str
    passed: bool
    violations: list[Violation] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable single-paragraph summary suitable for review."""
        lines = [
            f"=== Admission test for cell '{self.cell_name}': "
            f"{'PASS' if self.passed else 'FAIL'} ==="
        ]
        if not self.violations:
            lines.append("  (no violations)")
        else:
            for v in self.violations:
                tag = "[BLOCKER]" if v.severity == "blocker" else "[WARNING]"
                lines.append(f"  {tag} {v.legge.value}: {v.message}")
        return "\n".join(lines)


# Type alias for check callables.
Check = Callable[[dict[str, Any]], Violation | None]


class AdmissionTest:
    """7 Leggi admission test runner.

    Each check is a function ``dict -> Violation | None`` registered via the
    ``@register(legge)`` decorator. Cells PASS iff zero blocker violations.
    Warnings populate ``result.violations`` with severity='warning' but do
    NOT flip ``passed`` to False.
    """

    CHECKS: dict[Legge, Check] = {}

    @classmethod
    def register(cls, legge: Legge) -> Callable[[Check], Check]:
        """Decorator to register a check for one of the 7 Leggi."""
        def decorator(fn: Check) -> Check:
            cls.CHECKS[legge] = fn
            return fn
        return decorator

    def run_all(self, cell_definition: dict[str, Any]) -> AdmissionResult:
        """Run every registered check against the cell definition."""
        cell_name = cell_definition.get("name", "<unnamed>")
        violations: list[Violation] = []
        for legge in Legge:
            check = self.CHECKS.get(legge)
            if check is None:
                violations.append(
                    Violation(
                        legge=legge,
                        message=f"no check registered for {legge.value}",
                        severity="warning",
                    )
                )
                continue
            v = check(cell_definition)
            if v is not None:
                violations.append(v)
        passed = not any(v.severity == "blocker" for v in violations)
        return AdmissionResult(
            cell_name=cell_name,
            passed=passed,
            violations=violations,
        )


# === The 7 checks ==========================================================
#
# Each check returns Violation(severity="blocker") for hard failures,
# Violation(severity="warning") for soft notes, and None for OK. They are
# intentionally simple (single-field reads) — sophistication belongs in the
# rubric doc, not in the runtime check.

@AdmissionTest.register(Legge.CLI_ONLY)
def _check_cli_only(cd: dict[str, Any]) -> Violation | None:
    """Law 1: CLI-only LLM access. No paid HTTP API calls.

    Cell definition fields used:
        exposes_gui: bool — must be False (cell is headless)
        llm_invocation: optional str — must be one of {cli, oauth_cli, ollama, deepseek_api}
                                       (DeepSeek API is the documented exception)
    """
    if cd.get("exposes_gui", False):
        return Violation(
            legge=Legge.CLI_ONLY,
            message="cell exposes a GUI — Law 1 requires headless CLI-only operation",
            severity="blocker",
        )
    invocation = cd.get("llm_invocation")
    if invocation is not None and invocation not in {
        "cli", "oauth_cli", "ollama", "deepseek_api", "none",
    }:
        return Violation(
            legge=Legge.CLI_ONLY,
            message=(
                f"llm_invocation='{invocation}' not in allowlist "
                f"{{cli, oauth_cli, ollama, deepseek_api, none}}; "
                f"global rule bans Anthropic paid API"
            ),
            severity="blocker",
        )
    return None


@AdmissionTest.register(Legge.OSINT_BLINDATO)
def _check_osint_blindato(cd: dict[str, Any]) -> Violation | None:
    """Law 2: OSINT data must NOT leave Pro. No mixing OSINT + client data.

    Cell definition fields used:
        external_sources: list[str] — names of upstream feeds
        client_data_access: bool — does the cell read client PII?
    """
    has_external = bool(cd.get("external_sources", []))
    has_client = bool(cd.get("client_data_access", False))
    if has_external and has_client:
        return Violation(
            legge=Legge.OSINT_BLINDATO,
            message=(
                "cell mixes external_sources with client_data_access — Law 2 "
                "forbids OSINT contamination of client facts"
            ),
            severity="blocker",
        )
    return None


@AdmissionTest.register(Legge.EVENT_DRIVEN)
def _check_event_driven(cd: dict[str, Any]) -> Violation | None:
    """Law 3 (Symbiosis Law 4): Event-driven via PG NOTIFY (today's substrate).

    Cell definition fields used:
        publishes_via: str — must be 'pg_notify' or 'pg_trigger' for cells
                              that produce events; 'consumer_only' for cells
                              that are pure consumers; 'none' is reserved for
                              substrate-only organelles (pg-proxy etc.)
    """
    publishes = cd.get("publishes_via")
    if publishes is None:
        return Violation(
            legge=Legge.EVENT_DRIVEN,
            message="publishes_via not declared — must be one of pg_notify | pg_trigger | consumer_only | none",
            severity="blocker",
        )
    if publishes in {"filesystem", "redis", "memory", "telegram_only"}:
        return Violation(
            legge=Legge.EVENT_DRIVEN,
            message=(
                f"publishes_via='{publishes}' violates Law 3; "
                f"use pg_notify or pg_trigger for IPC"
            ),
            severity="blocker",
        )
    if publishes not in {"pg_notify", "pg_trigger", "consumer_only", "none"}:
        return Violation(
            legge=Legge.EVENT_DRIVEN,
            message=f"publishes_via='{publishes}' is not in the allowlist",
            severity="warning",
        )
    return None


@AdmissionTest.register(Legge.GRACEFUL_DEGRADATION)
def _check_graceful_degradation(cd: dict[str, Any]) -> Violation | None:
    """Law 4: each cell must declare ≥1 fallback mode.

    Cell definition fields used:
        fallback_modes: list[str] — e.g. ['redis_down', 'llm_provider_down']
    """
    fallbacks = cd.get("fallback_modes", [])
    if not isinstance(fallbacks, list) or len(fallbacks) == 0:
        return Violation(
            legge=Legge.GRACEFUL_DEGRADATION,
            message="fallback_modes empty — Law 4 requires at least one declared degradation mode",
            severity="blocker",
        )
    return None


@AdmissionTest.register(Legge.ZERO_FINAL_INSTANCE)
def _check_zero_final_instance(cd: dict[str, Any]) -> Violation | None:
    """Law 5: structural decisions go through Zero. Cell needs a kill switch.

    Cell definition fields used:
        kill_switch: bool — operator-callable kill switch must exist
        auto_publishes: bool — does the cell auto-publish to externally-visible
                                channels without human approval?
    """
    if not cd.get("kill_switch", False):
        return Violation(
            legge=Legge.ZERO_FINAL_INSTANCE,
            message=(
                "kill_switch=False — Law 5 requires an operator-callable kill switch "
                "so Zero can stop the cell mid-flight"
            ),
            severity="blocker",
        )
    if cd.get("auto_publishes", False):
        return Violation(
            legge=Legge.ZERO_FINAL_INSTANCE,
            message=(
                "auto_publishes=True — Law 5 requires human review for any "
                "externally-visible publish (Telegram review gate, etc.)"
            ),
            severity="blocker",
        )
    return None


@AdmissionTest.register(Legge.LOCAL_SOVEREIGNTY)
def _check_local_sovereignty(cd: dict[str, Any]) -> Violation | None:
    """Law 6: cell decisions must NOT depend on another cell's decisions.

    Cell definition fields used:
        depends_on_other_cell_decisions: bool — explicit declaration that
                                                  the cell's outputs are
                                                  derived from another cell's
                                                  reasoning (vs raw substrate)
    """
    if cd.get("depends_on_other_cell_decisions", False):
        return Violation(
            legge=Legge.LOCAL_SOVEREIGNTY,
            message=(
                "depends_on_other_cell_decisions=True — Law 6 requires "
                "decisional autonomy. Reading another cell's data is fine; "
                "depending on its REASONING is not. Re-classify as organelle."
            ),
            severity="blocker",
        )
    return None


@AdmissionTest.register(Legge.NUMBERS_FIRST)
def _check_numbers_first(cd: dict[str, Any]) -> Violation | None:
    """Law 7: cells must declare ≥3 metrics for before/after evaluation.

    Cell definition fields used:
        metrics: list[str] — e.g. ['ttr', 'error_rate', 'throughput']
    """
    metrics = cd.get("metrics", [])
    if not isinstance(metrics, list) or len(metrics) < 3:
        return Violation(
            legge=Legge.NUMBERS_FIRST,
            message=(
                f"metrics has {len(metrics) if isinstance(metrics, list) else 0} "
                f"entries — Law 7 requires ≥3 measurable signals so promotion "
                f"can be evaluated quantitatively"
            ),
            severity="blocker",
        )
    return None
