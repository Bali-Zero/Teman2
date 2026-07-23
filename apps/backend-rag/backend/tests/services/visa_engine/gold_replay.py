"""Canonical gold-suite replay report — the machine-readable evidence
artifact for Visa Oracle v2 gate criterion **G-b(a)**: an INDEPENDENT replay
of the 20 canonical gold personas (``test_evaluator_gold.PERSONAS``, the
single source of truth — imported, never duplicated) against the REAL
``evaluator.evaluate()`` (never the sibling ``gold_harness`` adapter, which
is the self-authored Decision-agnostic stand-in this artifact replaces).

Not collected as tests (no ``test_`` prefix / no test functions) — same
convention as the sibling ``gold_harness/replay_report.py``. Two consumers:

- ``apps/backend-rag/scripts/visa_gold_replay.py`` — the CLI wrapper an
  independent grader runs on a fresh checkout (see that script's docstring
  for the exact acceptance flow).
- ``test_gold_replay_artifact.py`` — a thin pytest wiring layer that runs
  the same builder in-process and asserts zero divergences.

Determinism contract (the gate's "two runs diff clean" requirement): every
field in the report is a pure function of the checkout — the persona table,
the gold pack (deterministic UUIDv5 ids throughout ``_gold_fixtures``),
per-persona ``assessment_id``s pinned to deterministic UUIDv5 values (never
``uuid4``), and both evaluation instants pinned to ``GOLD_EFFECTIVE_AT``.
The ONLY run-varying field is ``generated_at``; pass a fixed
``generated_at`` (the CLI's ``--fixed-now`` flag) for a byte-identical
artifact across runs, or strip that one key when diffing two independent
runs. ``json.dumps(..., sort_keys=True)`` is applied by the caller (the
CLI), so key order never leaks run-to-run noise either.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.visa_engine import evaluator
from backend.services.visa_engine.models import Decision
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS

#: Fixed namespace for the per-persona deterministic ``assessment_id``s —
#: readable, stable across runs/checkouts, never a secret (mirrors
#: ``_gold_fixtures._NS``'s own posture). ``assessment_id`` is a load-bearing
#: identity input (it feeds ``decision_id``/``public_id``), so pinning it is
#: what makes the per-persona ``decision_id`` recorded below reproducible by
#: an independent grader.
_REPLAY_NS = uuid.UUID("77777777-7777-4777-8777-777777777777")

#: Report envelope version — bump when the report SHAPE changes (never for
#: ordinary re-runs; two runs on the same checkout with the same
#: ``generated_at`` must be byte-identical).
REPORT_SCHEMA_VERSION = "1.0.0"

#: The visa_engine modules whose source bytes determine what a Decision
#: comes out — the evaluator plus every sibling module its control flow
#: directly depends on (condition semantics, compiler/ordering, fact
#: derivation/fingerprinting, the Decision models themselves, the enums and
#: error types). Codex-grade P2 fix (2026-07-23): hashing ``evaluator.py``
#: alone let a semantic change in any of these ship without moving the
#: artifact's "engine version". Scope honesty: transitive dependencies
#: OUTSIDE this package (pydantic, the interpreter) are not hashed — the
#: digest identifies the engine's own source, not its full runtime closure.
_ENGINE_MODULES: tuple[str, ...] = (
    "ast",
    "compiler",
    "enums",
    "errors",
    "evaluator",
    "fact_registry",
    "models",
)


def _persona_assessment_id(persona_id: int) -> uuid.UUID:
    return uuid.uuid5(_REPLAY_NS, f"gold-replay-persona-{persona_id:02d}")


def _engine_modules_digest() -> dict[str, Any]:
    """Per-module SHA-256 over each ``_ENGINE_MODULES`` source file, plus a
    combined digest over the sorted ``module:hash`` lines — the "engine
    version" axis of the artifact: an independent grader re-running the CLI
    on a different checkout immediately sees whether the engine they
    replayed matches the one this artifact was produced against, at
    single-module granularity."""
    modules: list[dict[str, str]] = []
    for name in _ENGINE_MODULES:
        module = importlib.import_module(f"backend.services.visa_engine.{name}")
        if module.__file__ is None:  # pragma: no cover - namespace-package guard
            raise RuntimeError(f"engine module has no source file: {name}")
        digest = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        modules.append({"module": module.__name__, "sha256": digest})
    combined = hashlib.sha256(
        "\n".join(f"{entry['module']}:{entry['sha256']}" for entry in modules).encode("utf-8")
    ).hexdigest()
    return {"modules": modules, "combined_sha256": combined}


def _pack_payload_sha256(payload: Any) -> str:
    """SHA-256 over the canonical (sorted-key) JSON of the pack payload —
    computed, never read from the envelope (the fixture envelope's own
    ``payload_sha256`` is a documented placeholder, ``"b" * 64``)."""
    canonical = json.dumps(payload.model_dump(mode="json", by_alias=True), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decision_actual(decision: Decision) -> dict[str, Any]:
    """The actual-outcome view of one persona's ``Decision``, shaped exactly
    like the canonical suite's own assertions (``test_evaluator_gold.py``'s
    ``test_gold_persona``): candidate order is rank order; missing-fact and
    notice codes are sorted; review/no-path reason codes keep engine order.
    """
    return {
        "state": decision.state.value,
        "candidates": [candidate.product_code for candidate in decision.candidates],
        "missing_facts": sorted(missing.value for missing in decision.missing_facts),
        "review_reason_codes": [reason.code for reason in decision.review_reasons],
        "no_path_reason_codes": [reason.code for reason in decision.no_path_reasons],
        "notice_codes": sorted(notice.code for notice in decision.notices),
    }


def _persona_expected(persona: Any) -> dict[str, Any]:
    """The expected-outcome view, normalized from the canonical
    ``test_evaluator_gold.Persona`` table with the exact same ordering
    conventions ``_decision_actual`` uses, so the two sides compare
    field-by-field without any re-interpretation."""
    return {
        "state": persona.expected_state.value,
        "candidates": list(persona.expected_candidates),
        "missing_facts": sorted(persona.expected_missing),
        "review_reason_codes": list(persona.expected_review_codes),
        "no_path_reason_codes": list(persona.expected_no_path_codes),
        "notice_codes": sorted(persona.expected_notice_codes),
    }


def _persona_divergences(
    persona_id: int, expected: dict[str, Any], actual: dict[str, Any]
) -> list[dict[str, Any]]:
    """One entry per outcome field whose expected and actual values differ —
    empty when the persona replays clean. Field-scoped (never a bare
    pass/fail) so a divergence is actionable without re-running anything."""
    divergences: list[dict[str, Any]] = []
    for field_name in sorted(expected):
        if expected[field_name] != actual[field_name]:
            divergences.append(
                {
                    "persona_id": persona_id,
                    "field": field_name,
                    "expected": expected[field_name],
                    "actual": actual[field_name],
                }
            )
    return divergences


def build_report(*, generated_at: datetime | None = None) -> dict[str, Any]:
    """Replay all 20 canonical gold personas through the REAL
    ``evaluator.evaluate()`` against the canonical gold compiled pack and
    return the evidence report as a JSON-serializable dict.

    Pure apart from reading ``evaluator.py``'s own source bytes (for the
    engine-version digest): no DB, no network, no clock reads beyond the
    caller-supplied ``generated_at``. Two calls with the same
    ``generated_at`` on the same checkout return deeply-equal reports.
    """
    compiled_pack = gf.build_gold_compiled_pack()
    payload = compiled_pack.source_pack.payload

    persona_reports: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []

    for persona in PERSONAS:
        facts = gf.applicant_facts(
            assessment_id=_persona_assessment_id(persona.id),
            overrides=persona.overrides,
        )
        decision = evaluator.evaluate(
            facts,
            compiled_pack,
            effective_at=gf.GOLD_EFFECTIVE_AT,
            observed_at=gf.GOLD_EFFECTIVE_AT,
        )
        expected = _persona_expected(persona)
        actual = _decision_actual(decision)
        persona_divergences = _persona_divergences(persona.id, expected, actual)
        divergences.extend(persona_divergences)
        persona_reports.append(
            {
                "persona_id": persona.id,
                "label": persona.label,
                "assessment_id": str(facts.assessment_id),
                "decision_id": str(decision.decision_id),
                "facts_fingerprint": decision.facts_fingerprint.digest,
                "expected": expected,
                "actual": actual,
                "pass": not persona_divergences,
            }
        )

    engine_digest = _engine_modules_digest()

    return {
        "gate": "G-b",
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat() if generated_at is not None else None,
        "engine": {
            "modules": engine_digest["modules"],
            "combined_sha256": engine_digest["combined_sha256"],
            "engine_contract_version": payload.engine_contract_version,
        },
        "replay": {
            "effective_at": gf.GOLD_EFFECTIVE_AT.isoformat(),
            "observed_at": gf.GOLD_EFFECTIVE_AT.isoformat(),
            "assessment_ids": "deterministic uuid5 per persona (see gold_replay._REPLAY_NS)",
        },
        "pack": {
            "rule_pack_id": str(compiled_pack.rule_pack_id),
            "sequence": compiled_pack.sequence,
            "version": compiled_pack.version,
            "environment": compiled_pack.environment.value,
            "rule_count": len(compiled_pack.rules),
            "product_count": len(compiled_pack.products),
            "payload_computed_sha256": _pack_payload_sha256(payload),
        },
        "persona_count": len(persona_reports),
        "personas": persona_reports,
        "divergences": divergences,
        "summary": {
            "personas_total": len(persona_reports),
            "personas_pass": sum(1 for report in persona_reports if report["pass"]),
            "personas_with_divergence": sum(1 for report in persona_reports if not report["pass"]),
            "divergence_count": len(divergences),
        },
        "overall_pass": not divergences,
    }
