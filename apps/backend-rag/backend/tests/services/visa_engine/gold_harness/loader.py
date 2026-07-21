"""Loaders for the gold-harness fixtures: the designed RulePack (source JSON,
compiled via the REAL compiler) and the 20 gold personas (source JSON,
validated against the closed FactPath vocabulary and parsed into real
``models.ApplicantFacts`` Pydantic objects -- never a hand-rolled shape).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.visa_engine.ast import FactSnapshot
from backend.services.visa_engine.compiler import (
    CompilationReport,
    CompiledRulePack,
    build_compiled_pack,
    compile_rule_pack,
)
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import ApplicantFacts, RulePack

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RULE_PACK_PATH = FIXTURES_DIR / "gold_rule_pack.json"
PERSONAS_DIR = FIXTURES_DIR / "personas"

#: The exact GOLD_EFFECTIVE_AT the pack + every persona are authored against
#: (matches the sibling suite's own ``conftest.py::GOLD_EFFECTIVE_AT`` value
#: -- redeclared here rather than imported to keep this package free of a
#: back-reference into the DB-fixture-heavy sibling conftest module).
GOLD_EFFECTIVE_AT = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)

#: The full closed 35-key wire vocabulary (``ApplicantFactsData``'s aliases),
#: used to fail loudly if a persona fixture is missing a key or carries an
#: extra one -- Pydantic's own ``extra="forbid"``/required-field validation
#: already enforces this at ``ApplicantFacts.model_validate()`` time; this
#: constant exists so a malformed persona fails with a persona-scoped,
#: readable message before that generic Pydantic error.
APPLICANT_FACT_WIRE_KEYS: frozenset[str] = frozenset(
    path.value for path in FactPath if not path.value.startswith("derived.")
)


def load_rule_pack_raw() -> dict[str, Any]:
    with RULE_PACK_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_and_compile_rule_pack() -> CompiledRulePack:
    """Parse the source-JSON envelope into a real ``RulePack``, run it
    through the REAL compiler (``compile_rule_pack``), assert zero defects,
    then build the evaluator-ready ``CompiledRulePack`` (``build_compiled_pack``).

    Raises ``RulePackCompilationError`` with every collected defect if the
    fixture does not compile clean -- this is the harness's own fixed
    fixture; a defect here is a bug in the harness, not in an applicant's
    facts, so failing loudly (not per-test) is correct.
    """

    raw = load_rule_pack_raw()
    pack = RulePack.model_validate(raw)
    report: CompilationReport = compile_rule_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)
    if not report.ok:
        details = "; ".join(f"{e.code}: {e.message} (rule={e.rule_id})" for e in report.errors)
        raise RulePackCompilationError(f"gold_rule_pack.json fails compile_rule_pack: {details}")
    return build_compiled_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)


@dataclass(frozen=True, slots=True)
class Persona:
    persona_id: str
    narrative: str
    facts: ApplicantFacts
    expected: dict[str, Any]
    source_path: Path

    def derive_snapshot(self, *, effective_at: datetime = GOLD_EFFECTIVE_AT) -> FactSnapshot:
        return DEFAULT_FACT_REGISTRY.derive(self.facts, effective_at=effective_at)


def _validate_wire_keys(persona_id: str, raw_facts: dict[str, Any]) -> None:
    got = frozenset(raw_facts)
    missing = APPLICANT_FACT_WIRE_KEYS - got
    extra = got - APPLICANT_FACT_WIRE_KEYS
    if missing or extra:
        raise ValueError(
            f"persona {persona_id!r}: facts do not match the closed 35-path "
            f"FactPath vocabulary -- missing={sorted(missing)} extra={sorted(extra)}"
        )


def load_persona(path: Path) -> Persona:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    persona_id = raw["persona_id"]
    raw_facts = raw["facts"]
    _validate_wire_keys(persona_id, raw_facts)

    facts = ApplicantFacts.model_validate(
        {
            "schema_version": "1.0.0",
            "assessment_id": raw.get("assessment_id", "00000000-0000-0000-0000-000000000000"),
            "collected_at": GOLD_EFFECTIVE_AT,
            "facts": raw_facts,
        }
    )
    return Persona(
        persona_id=persona_id,
        narrative=raw["narrative"],
        facts=facts,
        expected=raw["expected"],
        source_path=path,
    )


def load_all_personas() -> list[Persona]:
    paths = sorted(PERSONAS_DIR.glob("*.json"))
    if not paths:
        raise RuntimeError(f"no persona fixtures found under {PERSONAS_DIR}")
    return [load_persona(p) for p in paths]
