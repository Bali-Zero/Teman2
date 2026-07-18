"""Visa Engine v2 — the sole recommendation authority for Bali Zero visa
decisions (product-design.md §5.2; round-2 spec §0 binding decision #1).

PR1 ships the engine's *contracts*: closed enums, frozen Pydantic wire
models mirroring the JSON Schema 2020-12 contract, the fact registry, the
16-operator three-valued condition AST, the compiler, and the packaged
schema files. No bundle signing, no evaluator, no persistence, no HTTP
wiring — those land in later PRs (see the module's own docstrings for what
is explicitly out of scope).

This module re-exports the public API named in the spec (section 1) plus
the closed fact-path vocabulary from ``fact_registry``. Wire-format helper
models internal to ``models.py`` (``UnknownFact`` and the per-path
``Known*`` shapes used inside ``ApplicantFacts``) are deliberately NOT
re-exported here — they share a name with ``fact_registry``'s runtime
``UnknownFact``/``KnownFact`` and are reachable via
``backend.services.visa_engine.models`` directly if ever needed.
"""

from __future__ import annotations

from backend.services.visa_engine.ast import (
    AllCondition,
    AnyCondition,
    BetweenCondition,
    Condition,
    ConditionResult,
    ContainsAllCondition,
    EqCondition,
    GtCondition,
    GteCondition,
    InCondition,
    IntersectsCondition,
    KnownCondition,
    LtCondition,
    LteCondition,
    NeqCondition,
    NotCondition,
    NotInCondition,
    Scalar,
    UnknownCondition,
    collect_fact_paths,
    evaluate_condition,
)
from backend.services.visa_engine.compiler import (
    CompiledProduct,
    CompiledRule,
    CompiledRulePack,
    compile_rule_pack,
)
from backend.services.visa_engine.enums import (
    DecisionState,
    EngineMode,
    EngineSurface,
    RuleStage,
    TruthValue,
)
from backend.services.visa_engine.errors import (
    FactValidationError,
    PersistenceRequiredError,
    RulePackCompilationError,
    RulePackUnavailableError,
    RulePackVerificationError,
    VisaEngineError,
)
from backend.services.visa_engine.fact_registry import (
    DEFAULT_FACT_SPECS,
    ApplicantFactPath,
    DerivedFactPath,
    FactPath,
    FactRegistry,
    FactSnapshot,
    FactSpec,
    KnownFact,
    UnknownFact,
    UnknownReason,
    canonical_fact_payload,
)
from backend.services.visa_engine.models import (
    ApplicantFacts,
    CandidateDecision,
    ConsentEvent,
    Decision,
    EvaluationContext,
    PriceQuote,
    Rule,
    RulePack,
    SourceRecord,
    VisaProductVersion,
)
from backend.services.visa_engine.schema_export import export_schemas

__all__ = [  # noqa: RUF022 — grouped by source module, not alphabetical
    # enums.py
    "TruthValue",
    "DecisionState",
    "RuleStage",
    "EngineMode",
    "EngineSurface",
    # models.py
    "RulePack",
    "Rule",
    "VisaProductVersion",
    "ApplicantFacts",
    "Decision",
    "PriceQuote",
    "SourceRecord",
    "CandidateDecision",
    "ConsentEvent",
    "EvaluationContext",
    # fact_registry.py
    "FactSpec",
    "FactSnapshot",
    "FactRegistry",
    "KnownFact",
    "UnknownFact",
    "UnknownReason",
    "ApplicantFactPath",
    "DerivedFactPath",
    "FactPath",
    "DEFAULT_FACT_SPECS",
    "canonical_fact_payload",
    # ast.py
    "AllCondition",
    "AnyCondition",
    "NotCondition",
    "KnownCondition",
    "UnknownCondition",
    "EqCondition",
    "NeqCondition",
    "LtCondition",
    "LteCondition",
    "GtCondition",
    "GteCondition",
    "InCondition",
    "NotInCondition",
    "BetweenCondition",
    "IntersectsCondition",
    "ContainsAllCondition",
    "Condition",
    "ConditionResult",
    "Scalar",
    "evaluate_condition",
    "collect_fact_paths",
    # compiler.py
    "CompiledRule",
    "CompiledProduct",
    "CompiledRulePack",
    "compile_rule_pack",
    # schema_export.py
    "export_schemas",
    # errors.py
    "VisaEngineError",
    "RulePackUnavailableError",
    "RulePackVerificationError",
    "RulePackCompilationError",
    "FactValidationError",
    "PersistenceRequiredError",
]
