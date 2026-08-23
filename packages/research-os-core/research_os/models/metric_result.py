"""Immutable MetricResult contract from frozen CONTRACTS.md section 20.

Purpose (verbatim): "bind one observed measurement to the exact
preregistered profile that governed it, without putting terminal results
into the profile itself." The causal order is MetricProfile -> MetricResult
-> OutcomeEvent (section 20 invariants); this kind never references an
OutcomeEvent, avoiding a circular identity dependency.

## Cross-kind check against section 16 (OutcomeEvent, already on a sibling
branch): PASSES, no divergence found.

``OutcomeEvent.metric_profile_ref``/``metric_result_ref`` (git show
``ros-v1-p04-d1-outcome-event:packages/research-os-core/research_os/models/
outcome_event.py``) are:

    class MetricProfileRef(FrozenCoreModel):
        metric_profile_id: UUID
        object_hash: Sha256Hex

    class MetricResultRef(FrozenCoreModel):
        metric_result_id: UUID
        object_hash: Sha256Hex

both jointly-optional on OutcomeEvent, enforced there by a
``model_validator`` (not schema ``dependentRequired``) reading "present or
jointly absent" from section 16's own invariants text. The local ref shapes
defined below are byte-for-byte the same two-field shape (this kind owns its
own copies rather than importing OutcomeEvent's module, matching every
other sibling kind's convention of not cross-importing another kind's local
ref classes). No mismatch to report as a divergence.

## THE EXPENSIVE ONE, applied here: ``insufficient_evidence`` is a
first-class ``metric_result_state`` (section 3 registry), so a
``MetricResult`` with no measured value is a VALID document per contract
rule 9 ("Missing evidence is not negative evidence... insufficient_evidence
are valid outcomes"). Section 20's own prose gives ``measurement.value`` no
``?`` mark, which would normally read as required -- but making it required
would make an ``insufficient_evidence`` result UNREPRESENTABLE, directly
contradicting rule 9 and the ``metric_result_state`` registry it names.
Rule 9 is a contract-wide rule (section 1), and it overrides a section-local
missing-``?`` reading where the two conflict. ``measurement.value`` is
therefore typed ``Any = None`` (both an optional key and a nullable value)
-- the most permissive reading available, so this model can never reject a
document rule 9 explicitly protects. ``measurement.unit`` stays required as
literally specified: it describes what would be measured (a static
descriptor inherited conceptually from the profile), not "evidence" in
rule 9's sense, so nothing here forces it open too.

Considered and deliberately REJECTED (would narrow a document the spec does
not forbid):

- Requiring ``measurement.value`` to be non-null when ``result_state ==
  "measured"``: plausible domain logic, but section 20's invariants text
  never states this conditional. Enforcing it is inventing a rule, not
  reading one.
- Requiring ``reason_codes`` non-empty when ``result_state`` is
  ``"invalidated"`` or ``gate_disposition`` is ``"fail"``: same problem,
  not stated in section 20's invariants.
- Ordering ``window.data_cutoff_at`` against ``started_at``/``ended_at``:
  only ``ended_at`` strictly after ``started_at`` is enforced (mirrors the
  ``ValidTime``-class ordering precedent used throughout this packet);
  ``data_cutoff_at`` is plausibly ``>= ended_at`` in most real pipelines but
  that is a domain guess, not spec text, so it is left unconstrained.

Other judgment calls (spec silent, flagged for ratification; matching
INTERPRETATION comments sit at each code site below):

- ``metric_result_family_id: stable namespaced identifier`` -> RegisteredName
  (matches ``OutcomeEvent.outcome_event_family_id`` and
  ``ObjectSuccessorEdge.family_id``'s identical wording and typing).
- ``subject_refs``/``source_observation_refs``: ``[{object_kind, object_id,
  object_hash}]`` is a verbatim, field-for-field match of the existing
  ``ExactObjectRef`` primitive -- reused directly, not reinvented.
- ``sample.overall``/``sample.subgroups[].size``/``sample.exclusions[].
  count``: non-negative integers (a count cannot be negative) -- a
  definitional bound, not an invented business rule, mirroring
  ``OutcomeEvent.cohort.size``'s identical ``ge=0`` treatment.
- ``measurement.numerator``/``denominator``/``uncertainty``: all carry `?`
  in the spec, so ``Any | None = None``. ``uncertainty`` in particular has
  no shape given (could be a stderr scalar, a {lower, upper} CI, ...); left
  as ``Any`` rather than inventing a shape, same reasoning as
  ``MetricProfile.estimator.confidence_interval_or_bootstrap``.
- ``guardrail_results[].result`` and ``decision_rule_evaluation.result``:
  both use section 20's inline closed 3-value list ``pass | fail |
  insufficient_evidence``. This is DISTINCT from every existing section-3
  registry enum -- not ``verification_verdict`` (4 values, includes
  ``pass_with_limits``), not ``gate_disposition`` (4 values, includes
  ``not_applicable``). No section-3 row matches it. Encoded as one shared
  local closed ``Literal`` (used at both sites, not duplicated
  inconsistently) -- same "closed-but-unregistered" treatment as
  ``MetricProfile.missing_data_policy`` and ``OutcomeEvent.source_system``,
  flagged for the same registry-completeness ratification question.
- ``gate_disposition``: reuses the section-3 ``GateDisposition`` enum
  directly -- verbatim value-for-value match (``pass | fail |
  insufficient_evidence | not_applicable``).
- ``result_state``: reuses the section-3 ``MetricResultState`` enum
  directly per the P04-D1 mandate's explicit instruction -- do not
  re-declare it locally.
- Top-level ``reason_codes: [string]`` vs. ``decision_rule_evaluation.
  reason_codes: []``: the top-level field is explicitly typed "string" in
  the prose (not "registered namespaced string", unlike singular
  ``reason_code`` fields elsewhere in this contract family, e.g.
  ``RevocationReceipt.reason_code: RegisteredName``). This is read as a
  deliberate textual distinction, not an omission -- both are typed plain
  ``tuple[str, ...]``, NOT ``RegisteredName``, so a legitimate free-text
  reason (e.g. "sample too small") is not rejected for lacking a
  dot/dash/underscore separator ``RegisteredName`` would require.
  ``decision_rule_evaluation.reason_codes`` is given no element type at all
  (bare ``[]``); by proximity to the top-level field of the same name in
  the same document, it is read the same way, flagged as an
  interpretation rather than a certainty.
- ``classification``: unlike ``MetricProfile`` (which reuses the two-field
  ``Classification`` primitive verbatim), section 20 adds
  ``aggregation_level`` -- a local three-field submodel is defined instead,
  mirroring ``OutcomeEvent.classification``'s identical extension of the
  same primitive (``aggregation_level`` has no enum/format/example
  anywhere in the spec; typed as a free non-empty string there too).
- ``lineage``: section 20 writes the exact same shape as the ``Lineage``
  primitive (``workflow_run_ref?: {workflow_run_id, object_hash}``,
  ``input_hashes: []``, no extra fields) -- reused directly, unlike
  ``OutcomeEvent``'s lineage (which adds ``code_version``/``model_version``/
  ``prompt_version`` and therefore needed its own submodel).
- Idempotency-key construction ("covers profile hash, exact subject hashes,
  source-observation hashes, and measurement window") is NOT re-derived or
  checked here: section 20 gives no exact formula (no field-concatenation
  order, no hash algorithm binding), unlike ``object_hash`` (whose omission
  set is fully pinned in ``hashing.py``). This model validates only that
  ``idempotency_key`` is present and non-empty.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import GateDisposition, MetricResultState, RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Lineage,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)

# INTERPRETATION: closed 3-value list from the spec prose, distinct from
# every existing section-3 registry enum -- see module docstring.
GuardrailResultVerdict = Literal["pass", "fail", "insufficient_evidence"]


class MetricProfileRef(FrozenCoreModel):
    metric_profile_id: UUID
    object_hash: Sha256Hex


class MetricResultRef(FrozenCoreModel):
    metric_result_id: UUID
    object_hash: Sha256Hex


class MetricResultWindow(FrozenCoreModel):
    started_at: UtcDateTime
    ended_at: UtcDateTime
    data_cutoff_at: UtcDateTime

    @model_validator(mode="after")
    def validate_window(self) -> MetricResultWindow:
        if self.ended_at <= self.started_at:
            raise PydanticCustomError(
                "window_ended_at_not_later",
                "window.ended_at must be strictly later than window.started_at",
            )
        return self


class SampleSubgroup(FrozenCoreModel):
    name: str = Field(min_length=1)
    size: int = Field(ge=0)


class SampleExclusion(FrozenCoreModel):
    reason_code: RegisteredName
    count: int = Field(ge=0)


class MetricResultSample(FrozenCoreModel):
    overall: int = Field(ge=0)
    subgroups: tuple[SampleSubgroup, ...]
    exclusions: tuple[SampleExclusion, ...]


class Measurement(FrozenCoreModel):
    # INTERPRETATION: rule 9 override -- see module docstring "THE
    # EXPENSIVE ONE, applied here". Optional key AND nullable value.
    value: Any = None
    unit: str = Field(min_length=1)
    numerator: Any = None
    denominator: Any = None
    uncertainty: Any = None


class GuardrailResult(FrozenCoreModel):
    metric_name: RegisteredName
    result: GuardrailResultVerdict
    observed_value: Any = None


class DecisionRuleEvaluation(FrozenCoreModel):
    result: GuardrailResultVerdict
    # INTERPRETATION: plain str, not RegisteredName -- see module docstring.
    reason_codes: tuple[str, ...]


class MetricResultClassification(FrozenCoreModel):
    risk_class: RiskClass
    sensitivity: Sensitivity
    aggregation_level: str = Field(min_length=1)


class MetricResult(FrozenCoreModel):
    metric_result_id: UUID
    metric_result_family_id: RegisteredName
    supersedes_metric_result_ref: MetricResultRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    metric_profile_ref: MetricProfileRef
    subject_refs: tuple[ExactObjectRef, ...]
    source_observation_refs: tuple[ExactObjectRef, ...]
    window: MetricResultWindow
    sample: MetricResultSample
    measurement: Measurement
    guardrail_results: tuple[GuardrailResult, ...]
    decision_rule_evaluation: DecisionRuleEvaluation
    gate_disposition: GateDisposition
    result_state: MetricResultState
    # INTERPRETATION: plain str, not RegisteredName -- see module docstring.
    reason_codes: tuple[str, ...]
    classification: MetricResultClassification
    observed_at: UtcDateTime
    recorded_at: UtcDateTime
    idempotency_key: str = Field(min_length=1)
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_result(self) -> MetricResult:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
