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

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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
        # Iterate explicitly over Legge enum members. CodeQL Python's
        # py/non-iterable-in-for-loop heuristic doesn't recognize Enum
        # iteration via metaclass — using `list(Legge)` is functionally
        # identical and bypasses the false positive.
        for legge in list(Legge):
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


# Delivery-class allowlist — operational integrations that push client
# data OUTBOUND or embed structured client data without pulling raw
# untrusted intel back IN. Cells that legitimately combine
# `client_data_access=true` with `external_sources=[…]` MUST list only
# providers from this allowlist; anything else is treated as
# (potentially) OSINT-class and blocks admission.
#
# This is a DEFAULT-DENY posture: a new external_source name added to
# a cell.yaml that's NOT in this allowlist will FAIL admission with a
# clear error pointing the author at this constant. To register a new
# delivery integration: add the provider name here in a separate code
# review PR (the Law 2 perimeter is security-critical, not yaml
# configuration).
#
# v2.5 review V2-B2 fix (multi-LLM 2026-05-04): the v2 design used a
# blocklist (`_OSINT_CLASS_PROVIDERS`) which silently passed any new
# scraper not in the hardcoded set — a security regression vs the v1
# design's "any external_sources + client_data → BLOCK". The allowlist
# restores conservative posture while still allowing legitimate cells
# (crm-cell uses Drive/Brevo/WhatsApp/Telegram, all in this list).
_DELIVERY_CLASS_ALLOWLIST: frozenset[str] = frozenset({
    # CRM client-comms delivery channels
    "google_drive_api",       # service account, folder/file CRUD on client folders
    "brevo_api",              # transactional email
    "whatsapp_business_api",  # client messaging
    "telegram_bot_api",       # team alerts
    # Common embedding-only / structured-output APIs (push, no inbound intel)
    "openai_embedding_api",   # text-embedding-3-small (FROZEN per CLAUDE.md)
})


@AdmissionTest.register(Legge.OSINT_BLINDATO)
def _check_osint_blindato(cd: dict[str, Any]) -> Violation | None:
    """Law 2: OSINT data must NOT leave Pro. No mixing OSINT + client data.

    Conservative posture: the cell must declare client_data_access=true
    AND have all `external_sources` in the `_DELIVERY_CLASS_ALLOWLIST`
    to pass admission. Any provider NOT in the allowlist is treated as
    OSINT-class and blocks the combination — including unknown
    providers (default-deny).

    Cells with `client_data_access=false` may declare any
    external_sources (no contamination risk on the client perimeter).

    Cell definition fields used:
        external_sources: list[str] — names of upstream feeds + delivery
            integrations
        client_data_access: bool — does the cell read client PII?
    """
    declared_sources: set[str] = set(cd.get("external_sources", []) or [])
    has_client = bool(cd.get("client_data_access", False))
    if not has_client:
        # No client PII access → no OSINT contamination risk. Cells
        # like intel-scraper-cell legitimately declare arbitrary
        # external_sources here (visa/tax government domains, etc.).
        return None
    untrusted = declared_sources - _DELIVERY_CLASS_ALLOWLIST
    if untrusted:
        return Violation(
            legge=Legge.OSINT_BLINDATO,
            message=(
                f"cell mixes external_sources with client_data_access — "
                f"the following providers are NOT in the delivery allowlist "
                f"and are treated as OSINT-class: {sorted(untrusted)}. "
                f"Either (a) add to _DELIVERY_CLASS_ALLOWLIST in "
                f"packages/cell-core/cell_core/admission_test.py via a "
                f"dedicated code review (the Law 2 perimeter is security-"
                f"critical), or (b) remove client_data_access if this cell "
                f"doesn't actually read client PII. Current allowlist: "
                f"{sorted(_DELIVERY_CLASS_ALLOWLIST)}"
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
                              substrate-only organelles (pg-proxy etc.) AND
                              requires cell_class == 'organelle' to PASS.
        cell_class: str — 'cell' (default) or 'organelle' (allows publishes_via='none')

    Round-2 review fix (Claude/GPT-5.5/DeepSeek):
    1. Unknown values now BLOCK (was warning) — silent registration of a
       new transport name is not an admission concern; it should fail loudly.
    2. publishes_via='none' is gated on cell_class == 'organelle'. Without
       that pairing, a cell could opt-out of Law 3 entirely just by setting
       publishes_via='none'. Now flagged as blocker.
    """
    publishes = cd.get("publishes_via")
    cell_class = cd.get("cell_class", "cell")

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
    if publishes == "none" and cell_class != "organelle":
        return Violation(
            legge=Legge.EVENT_DRIVEN,
            message=(
                "publishes_via='none' is reserved for substrate-only organelles "
                "(set cell_class='organelle' if this is a substrate). "
                "Cells must use pg_notify | pg_trigger | consumer_only."
            ),
            severity="blocker",
        )
    if publishes not in {"pg_notify", "pg_trigger", "consumer_only", "none"}:
        return Violation(
            legge=Legge.EVENT_DRIVEN,
            message=(
                f"publishes_via='{publishes}' is not in the allowlist "
                "{pg_notify, pg_trigger, consumer_only, none}"
            ),
            severity="blocker",
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


# === Cell-definition loader =================================================
#
# Sprint 1 W1: cells declare their 7 Leggi profile in a sidecar YAML
# (e.g. ``apps/bali-intel-scraper/cell.yaml``). ``load_cell_definition``
# parses the file into the same plain dict that
# ``AdmissionTest.run_all()`` consumes — no schema layer.
#
# PyYAML is the canonical loader. When unavailable (e.g. cell-core
# installed in a minimal env), JSON files are still readable.


class CellDefinitionLoadError(ValueError):
    """Raised when a cell definition file cannot be loaded or parsed."""


def load_cell_definition(path: str | Path) -> dict[str, Any]:
    """Load a cell definition from a YAML or JSON file.

    Returns a plain dict suitable for ``AdmissionTest().run_all(cd)``.

    Raises:
        FileNotFoundError: when *path* does not exist.
        CellDefinitionLoadError: when the file cannot be parsed, the
            root is not a mapping, or PyYAML is not installed for a
            ``.yaml`` / ``.yml`` file.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"cell definition not found: {p}")

    text = p.read_text(encoding="utf-8")

    if p.suffix.lower() == ".json":
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CellDefinitionLoadError(
                f"cell definition {p} is not valid JSON: {exc}"
            ) from exc
    else:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover  (env-specific)
            raise CellDefinitionLoadError(
                f"cell definition {p} is YAML but PyYAML is not installed; "
                f"install with `pip install pyyaml` or convert to JSON"
            ) from exc
        try:
            loaded = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise CellDefinitionLoadError(
                f"cell definition {p} is not valid YAML: {exc}"
            ) from exc

    if not isinstance(loaded, dict):
        raise CellDefinitionLoadError(
            f"cell definition {p} root must be a mapping, got "
            f"{type(loaded).__name__}"
        )
    return loaded
