"""Immutable MetricProfile contract from frozen CONTRACTS.md section 19.

Purpose (verbatim): "prevent thresholds and dashboards from becoming
post-hoc narratives." A MetricProfile is preregistered evaluation
methodology, frozen before any measurement is inspected; it carries no
terminal result -- that is MetricResult's job (section 20).

Judgment calls (spec silent or ambiguous, flagged for ratification in the
P04-D1 handoff report; the code sites below carry matching INTERPRETATION
comments):

- ``numerator``/``denominator``: ``"exact definition or null"`` has no shape
  at all in the prose -- not even a hint of what a "definition" looks like.
  Typed ``Any``, but kept a REQUIRED key (no ``?`` on either field in the
  spec text) so a producer must say ``null`` explicitly rather than omitting
  the key -- mirrors ``OutcomeEvent.value: Any`` (also no ``?``, also typed
  ``Any``, also required) rather than inventing a tagged union.
- ``window`` (``{type, duration, timezone, late_arrival_policy}``): every
  sub-field is a bare noun with zero type hint. All four typed as
  non-empty ``str`` -- the least-restrictive reading that cannot reject a
  document the spec permits (a closed enum here would be invention; a
  numeric/duration format here would be invention).
- ``baseline.window`` is given ZERO field names (unlike the top-level
  ``window``, which at least names its four sub-fields) -- this is the "too
  few words to determine a shape" case per the P04-D1 mandate: rather than
  reusing the top-level window-policy shape (a real but unstated guess) or
  inventing a ``{started_at, ended_at}`` interval (an equally real but
  unstated guess), it is typed ``Any``. Do not read this as spec-derived.
- ``baseline.source`` typed as a non-empty descriptive string, not an
  ``ExactObjectRef`` -- the prose says "source", not "source_ref", and gives
  none of the ``{object_kind, object_id, object_hash}`` triple that marks an
  exact-ref field everywhere else in this contract family.
- ``evaluation_data.dataset_ref.version`` typed ``str`` rather than ``int``:
  the prose gives no format, and a plain string is the strictly more
  permissive choice (accepts both "3" and "2026-08-01-snapshot" and
  "3.2.1"); forcing ``int`` would reject documents the spec's silence does
  not forbid.
- ``evaluation_data.split.assignment_hash`` and
  ``evaluation_data.exclusion_rules[].definition_hash`` typed ``Sha256Hex``
  by the repo-wide ``*_hash`` naming convention (every other ``*_hash``
  field in this package, e.g. ``input_revision_hash``, ``arguments_hash``,
  is a canonical SHA-256), not because section 19 states the format.
- ``minimum_sample.power_target``: numeric, ``?``-optional, NO bound applied
  even though a statistical power target conventionally lives in [0, 1] --
  the spec states no range for it, and the P04-D1 mandate explicitly warns
  against bounding a ``*score``-shaped field the spec leaves open. Applying
  the domain convention anyway would be exactly that mistake.
- ``estimator.method``/``estimator.version`` typed as plain non-empty
  strings, NOT ``RegisteredName``: a single-word method name such as
  "bootstrap" would fail ``RegisteredName``'s mandatory-separator pattern,
  so applying that type here would silently reject a plausible real value.
- ``estimator.confidence_interval_or_bootstrap`` has a name that all but
  invites a discriminated union ("confidence interval OR bootstrap") but
  the prose gives no field names for either arm. Per the P04-D1 mandate's
  explicit warning against inventing a union from bare prose, this is typed
  ``Any`` and left alone -- inventing the two arms here would be exactly the
  mistake a sibling kind was caught making elsewhere in this packet.
- ``subgroups[].definition`` and ``decision_rule``: both "no shape given at
  all" fields, both typed ``Any``, both required (no ``?``).
- ``guardrails[].direction``: no closed set given (plausible values include
  "increase"/"decrease" but also "no_worse_than", "within_tolerance", ...).
  Typed as a non-empty open string rather than a closed ``Literal`` --
  inventing the closed set here is the OVER-match failure mode the P04-D1
  mandate calls out (guard/type must enumerate what the spec actually
  states as PERMITTED, never a guessed-closed vocabulary).
- ``guardrails[].threshold``: numeric, no unit or bound stated -- left
  unconstrained for the same reason as ``power_target`` above.
- ``missing_data_policy``: the closed pipe-list
  ``exclude | impute_registered | insufficient_evidence`` has no matching
  row in section 3's registry table (checked: no ``missing_data_policy``
  entry there). Encoded as a local closed ``Literal`` anyway, same as
  ``OutcomeEvent.source_system`` did for an equally pipe-closed-but-
  unregistered field -- flagged for the same registry-completeness
  ratification question, not silently promoted to an open string.
- ``validity: {valid_from, expires_at}``: distinct field names from the
  ``ValidTime`` primitive's ``{valid_from, valid_to}`` (and from
  ``Retention``'s ``retain_until``), so the primitive is not reused
  verbatim; a local submodel is defined instead. Neither field carries
  ``?`` in the spec text, so both are required (unlike ``ValidTime.valid_to``,
  which explicitly allows an open-ended null). The "expires_at strictly
  after valid_from" ordering check mirrors the ``ValidTime`` primitive's own
  ordering rule for the same class of field pair (also true of
  ``OutcomeEvent.window`` and ``WorkflowRun``'s start/end pairs elsewhere in
  this packet) but is NOT itself verbatim-stated for section 19.

Deliberately NOT enforced (repository/service-layer invariants, not
single-object shape constraints -- narrowing here would reject documents
section 19's own text permits):

- "No improvement claim is valid if a guardrail fails, a subgroup is
  silently dropped, or the sample floor is unmet." This is about how a
  *consumer* uses a ``MetricResult`` against this profile, not a constraint
  a lone ``MetricProfile`` document can fail on its own.
- "An expired profile cannot govern a new measurement or release decision."
  Same shape of problem: ``validity.expires_at`` alone cannot say whether
  *this* document is currently governing anything; that comparison needs
  wall-clock "now", which a frozen canonical object does not carry.
- ``numerator``/``denominator`` joint presence-or-absence: unlike
  ``OutcomeEvent``'s ``metric_profile_ref``/``metric_result_ref`` pairing
  (which section 16's invariants state explicitly), section 19 states no
  such pairing rule for numerator/denominator. A ratio metric plausibly
  needs both; a raw-count metric plausibly needs neither -- but inventing a
  joint-presence rule here without textual support is the same narrowing
  mistake the mandate warns against, just self-inflicted instead of
  inherited from a sibling.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
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

# INTERPRETATION: closed pipe-list from the spec prose, no matching row in
# section 3's registry table -- same treatment as OutcomeEvent.source_system.
MissingDataPolicy = Literal["exclude", "impute_registered", "insufficient_evidence"]


class MetricWindowPolicy(FrozenCoreModel):
    # INTERPRETATION: all four sub-fields are bare nouns with no type hint
    # anywhere in the prose; typed as non-empty open strings (see module
    # docstring) rather than inventing enums or a duration format.
    type: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    late_arrival_policy: str = Field(min_length=1)


class MetricBaseline(FrozenCoreModel):
    # INTERPRETATION: "source" has no ref-triple given, typed as descriptive
    # text (see module docstring).
    source: str = Field(min_length=1)
    # INTERPRETATION: no field names given at all -- too few words to
    # determine a shape; left as Any rather than guessed. Required (no `?`).
    window: Any
    frozen_at: UtcDateTime


class DatasetRef(FrozenCoreModel):
    dataset_id: str = Field(min_length=1)
    # INTERPRETATION: str, not int -- see module docstring.
    version: str = Field(min_length=1)
    object_hash: Sha256Hex


class EvaluationSplit(FrozenCoreModel):
    strategy: str = Field(min_length=1)
    # INTERPRETATION: *_hash naming convention -> Sha256Hex.
    assignment_hash: Sha256Hex


class ExclusionRule(FrozenCoreModel):
    rule_id: str = Field(min_length=1)
    # INTERPRETATION: *_hash naming convention -> Sha256Hex.
    definition_hash: Sha256Hex


class EvaluationData(FrozenCoreModel):
    dataset_ref: DatasetRef
    split: EvaluationSplit
    exclusion_rules: tuple[ExclusionRule, ...]


class MinimumSample(FrozenCoreModel):
    overall: int = Field(ge=0)
    per_subgroup: int | None = Field(default=None, ge=0)
    # INTERPRETATION: no bound applied -- see module docstring
    # ("do not bound a *score field the spec leaves open").
    power_target: float | None = None


class Estimator(FrozenCoreModel):
    # INTERPRETATION: plain str, not RegisteredName -- see module docstring.
    method: str = Field(min_length=1)
    version: str = Field(min_length=1)
    # INTERPRETATION: no invented discriminated union -- see module
    # docstring. Required (no `?`).
    confidence_interval_or_bootstrap: Any


class MetricSubgroup(FrozenCoreModel):
    name: str = Field(min_length=1)
    # INTERPRETATION: no shape given at all; Any, required (no `?`).
    definition: Any


class Guardrail(FrozenCoreModel):
    metric_name: RegisteredName
    # INTERPRETATION: open string, not a closed Literal -- see module
    # docstring (avoid guessing a closed vocabulary the spec never states).
    direction: str = Field(min_length=1)
    # INTERPRETATION: no bound applied -- see module docstring.
    threshold: float


class MetricProfileValidity(FrozenCoreModel):
    valid_from: UtcDateTime
    expires_at: UtcDateTime

    @model_validator(mode="after")
    def validate_ordering(self) -> MetricProfileValidity:
        # INTERPRETATION: mirrors the ValidTime primitive's own ordering
        # check for the same class of field pair; not verbatim-stated here.
        if self.expires_at <= self.valid_from:
            raise PydanticCustomError(
                "expires_at_not_later",
                "validity.expires_at must be strictly later than validity.valid_from",
            )
        return self


class MetricProfile(FrozenCoreModel):
    metric_profile_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    metric_name: RegisteredName
    question: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    # INTERPRETATION: required (no `?`), type Any -- see module docstring.
    numerator: Any
    denominator: Any
    window: MetricWindowPolicy
    baseline: MetricBaseline
    evaluation_data: EvaluationData
    minimum_sample: MinimumSample
    estimator: Estimator
    subgroups: tuple[MetricSubgroup, ...]
    guardrails: tuple[Guardrail, ...]
    # INTERPRETATION: no shape given at all; Any, required (no `?`).
    decision_rule: Any
    missing_data_policy: MissingDataPolicy
    owner_ref: ActorRef
    validity: MetricProfileValidity
    classification: Classification
    created_at: UtcDateTime
    producer: Producer
    lineage: Lineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> MetricProfile:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
