"""Canonical, privacy-minimized evaluation traces for Visa Oracle v2.

The trace is produced by the evaluator while rules are evaluated.  It never
contains raw fact values: only fact paths, UNKNOWN reason codes, signed rule
metadata, tri-state outcomes, applied effects, and product-proof outcomes.

``trace_sha256`` follows the frozen engine contract exactly::

    SHA256(JCS({pack_sha256, effective_at, facts_hmac, ordered_nodes}))

Database timestamps, decision/public IDs, quote IDs, and encryption nonces do
not participate in this digest.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.enums import FactPath, RuleStage, TruthValue, UnknownReason
from backend.services.visa_engine.models import Sha256Hex


class TraceUnknownFact(BaseModel):
    """One UNKNOWN fact reference without its raw applicant value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact_path: FactPath
    reason: UnknownReason


class TraceNode(BaseModel):
    """One rule-condition evaluation from the decision-producing traversal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_scope: Literal["GLOBAL_PREPASS", "PRODUCT_PROOF", "RANKING"]
    stage: RuleStage
    stage_order: Annotated[int, Field(ge=0, le=3, strict=True)]
    priority: Annotated[int, Field(ge=0, le=100_000, strict=True)]
    rule_id: Annotated[str, Field(min_length=1, max_length=128)]
    product_version_id: uuid.UUID | None
    signed_child_index: Annotated[int, Field(ge=0, strict=True)]
    source_refs: tuple[uuid.UUID, ...]
    condition_result: TruthValue
    referenced_fact_paths: tuple[FactPath, ...]
    unknown_facts: tuple[TraceUnknownFact, ...]
    applied_effect: str | None
    product_proof_status: str | None

    @field_validator("source_refs", "referenced_fact_paths")
    @classmethod
    def _unique_tuple(cls, value: tuple) -> tuple:
        if len(value) != len(set(value)):
            raise ValueError("trace arrays must contain unique items")
        return value

    @model_validator(mode="after")
    def _stage_order_matches_stage(self) -> TraceNode:
        if self.stage_order != self.stage.order:
            raise ValueError("stage_order must match the RuleStage semantic order")
        unknown_paths = tuple(item.fact_path for item in self.unknown_facts)
        if len(unknown_paths) != len(set(unknown_paths)):
            raise ValueError("unknown_facts must contain unique fact paths")
        if set(unknown_paths) - set(self.referenced_fact_paths):
            raise ValueError("unknown facts must also be referenced facts")
        return self

    def ordering_key(self) -> tuple[int, int, str, str, int]:
        """The frozen canonical ordering from the product contract."""

        product_key = "" if self.product_version_id is None else str(self.product_version_id)
        return (
            self.stage_order,
            self.priority,
            self.rule_id,
            product_key,
            self.signed_child_index,
        )


class EvaluationTrace(BaseModel):
    """The complete internal trace whose digest is exposed on ``Decision``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    pack_sha256: Sha256Hex
    effective_at: datetime
    facts_hmac: Sha256Hex
    ordered_nodes: tuple[TraceNode, ...]

    @field_validator("effective_at")
    @classmethod
    def _effective_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must be timezone-aware")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("effective_at must be UTC")
        return value

    @model_validator(mode="after")
    def _nodes_are_canonically_ordered(self) -> EvaluationTrace:
        keys = tuple(node.ordering_key() for node in self.ordered_nodes)
        if keys != tuple(sorted(keys)):
            raise ValueError("ordered_nodes must use canonical trace ordering")
        return self

    def canonical_payload(self) -> Mapping[str, JsonValue]:
        """Return the exact frozen digest payload, excluding trace metadata."""

        payload = {
            "pack_sha256": self.pack_sha256,
            "effective_at": self.effective_at.isoformat().replace("+00:00", "Z"),
            "facts_hmac": self.facts_hmac,
            "ordered_nodes": [
                node.model_dump(mode="json", exclude_none=False) for node in self.ordered_nodes
            ],
        }
        return cast(Mapping[str, JsonValue], payload)

    def sha256(self) -> str:
        """Digest the RFC 8785/JCS canonical trace payload."""

        return hashlib.sha256(canonicalize_json(self.canonical_payload())).hexdigest()

    def matches(self, trace_sha256: str | None) -> bool:
        """Constant-time comparison against an exposed trace digest."""

        return trace_sha256 is not None and hmac.compare_digest(self.sha256(), trace_sha256)


__all__ = ["EvaluationTrace", "TraceNode", "TraceUnknownFact"]
