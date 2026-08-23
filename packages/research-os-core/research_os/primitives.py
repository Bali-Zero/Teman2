"""Shared strict primitives from frozen CONTRACTS.md section 3."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Annotated, Any, Literal, Mapping
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import SHA256_HEX_PATTERN
from research_os.version import SemanticVersion


_REVERSE_DNS_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z][a-z0-9-]*$"
)
_REGISTERED_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9][a-z0-9_-]*)+$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:[.-][a-z0-9_-]+)*$")


class FrozenCoreModel(BaseModel):
    """Base configuration for immutable, closed canonical objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PydanticCustomError("timestamp_timezone_missing", "timestamp must be timezone-aware UTC")
    if value.utcoffset() != timedelta(0):
        raise PydanticCustomError("timestamp_not_utc", "timestamp must be UTC")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_utc_datetime)]
Sha256Hex = Annotated[str, Field(pattern=SHA256_HEX_PATTERN)]
RegisteredName = Annotated[str, Field(pattern=_REGISTERED_NAME_RE.pattern)]
Identifier = Annotated[str, Field(pattern=_IDENTIFIER_RE.pattern)]


class ExactObjectRef(FrozenCoreModel):
    object_kind: Identifier
    object_id: str = Field(min_length=1)
    object_hash: Sha256Hex


class ActorRef(FrozenCoreModel):
    scheme: Literal["hmac-sha256"]
    key_version: str = Field(min_length=1)
    purpose: Literal["approval", "verification", "queue_decision", "assignment", "execution", "audit"]
    pseudonym: Sha256Hex


class Retention(FrozenCoreModel):
    retention_class: Literal["public_record", "operational", "audit", "restricted"]
    retain_until: UtcDateTime | None = None
    legal_hold: bool
    rights_expires_at: UtcDateTime | None = None


class Producer(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class WorkflowRunRef(FrozenCoreModel):
    workflow_run_id: UUID
    object_hash: Sha256Hex


class Lineage(FrozenCoreModel):
    workflow_run_ref: WorkflowRunRef | None = None
    input_hashes: tuple[Sha256Hex, ...]


class Classification(FrozenCoreModel):
    risk_class: RiskClass
    sensitivity: Sensitivity


class ValidTime(FrozenCoreModel):
    valid_from: UtcDateTime
    valid_to: UtcDateTime | None

    @model_validator(mode="after")
    def validate_half_open_interval(self) -> ValidTime:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise PydanticCustomError(
                "valid_time_not_increasing",
                "valid_to must be strictly later than valid_from",
            )
        return self


class ExtensionValue(FrozenCoreModel):
    extension_version: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_semantic_version(self) -> ExtensionValue:
        try:
            SemanticVersion.parse(self.extension_version)
        except ValueError as exc:
            raise PydanticCustomError(
                "extension_version_not_semver",
                "extension_version must be semantic version",
            ) from exc
        return self


Extensions = dict[str, ExtensionValue]


def validate_extensions(
    extensions: Mapping[str, ExtensionValue] | None,
    *,
    core_fields: set[str],
) -> Mapping[str, ExtensionValue] | None:
    """Enforce reverse-DNS namespaces and prevent core-field shadowing."""

    if extensions is None:
        return None
    for namespace, extension in extensions.items():
        if _REVERSE_DNS_RE.fullmatch(namespace) is None:
            raise ValueError(f"extension namespace must be reverse-DNS: {namespace!r}")
        shadowed = core_fields & extension.payload.keys()
        if shadowed:
            raise ValueError(f"extension payload cannot introduce a core field: {sorted(shadowed)}")
    return extensions
