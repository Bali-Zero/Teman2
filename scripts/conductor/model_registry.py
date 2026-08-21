"""Validated, read-only loader for the Model Intelligence Registry (MIR).

The registry deliberately separates abstract ModelCards from concrete endpoint profiles.
Only the latter can become an ``EndpointCandidate``.  Loading a card never grants an
invocation path, and static registry evidence is never upgraded into live health or a
benchmarked task score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
from typing import Any, Mapping

from scripts.conductor.contracts import (
    AuthSurface,
    CapabilityEvidence,
    EndpointCandidate,
    EvidenceKind,
    HostObservation,
    Role,
    TaskProfile,
    TaskScore,
)
from scripts.conductor.calibration import (
    CalibrationError,
    CalibrationRecord,
    EndpointHostObservation,
    parse_timestamp,
)


logger = logging.getLogger(__name__)


_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "const",
        "enum",
        "pattern",
        "minLength",
        "minimum",
        "maximum",
        "minItems",
        "items",
    }
)

_CANONICAL_EVIDENCE_LEVELS = frozenset(kind.value for kind in EvidenceKind)
_CANONICAL_ROUTING_STATUSES = frozenset(
    {
        "eligible",
        "manual_only",
        "probation",
        "phantom",
        "denied",
        "investigation_required",
        "listed_unexploited",
        "deprecated",
        "known_unmeasured",
    }
)
_LOCAL_PII_CAPABILITIES = frozenset({"local_only", "pii_safe_local"})


class RegistryError(ValueError):
    """Base error for invalid or unavailable MIR data."""


class RegistryValidationError(RegistryError):
    """Raised when a checked-in MIR projection cannot be safely joined."""


class UnknownEndpointError(RegistryError):
    """Raised when an endpoint ID is not a known concrete endpoint."""


class AbstractModelCardError(RegistryError):
    """Raised when code attempts to invoke a model card instead of an endpoint."""


@dataclass(frozen=True)
class ModelIntelligenceRegistry:
    """Validated MIR records and safe concrete endpoint accessors."""

    root: Path
    model_cards: Mapping[str, Mapping[str, Any]]
    endpoint_profiles: Mapping[str, Mapping[str, Any]]
    task_profiles: Mapping[str, TaskProfile]
    capability_ids: frozenset[str]
    capability_index_hash: str
    calibrations: Mapping[str, tuple[CalibrationRecord, ...]]
    host_endpoint_observations: Mapping[str, tuple[EndpointHostObservation, ...]]
    overlay_diagnostics: tuple[str, ...]
    as_of: str | None

    def endpoint(self, endpoint_id: str) -> EndpointCandidate:
        """Return one concrete endpoint or reject direct ModelCard invocation."""
        if endpoint_id in self.model_cards:
            raise AbstractModelCardError(
                f"{endpoint_id!r} is an abstract ModelCard and cannot be invoked; select an EndpointProfile"
            )
        try:
            endpoint = self.endpoint_profiles[endpoint_id]
        except KeyError as error:
            raise UnknownEndpointError(
                f"unknown endpoint profile: {endpoint_id}"
            ) from error
        return _candidate_from_records(
            endpoint,
            self.model_cards[endpoint["model_card_id"]],
            self.calibrations.get(endpoint_id, ()),
            self.host_endpoint_observations.get(endpoint_id, ()),
            self.task_profiles,
        )

    def endpoints(
        self, *, automated_only: bool = True
    ) -> tuple[EndpointCandidate, ...]:
        """Return concrete endpoint candidates in stable endpoint-ID order.

        ``automated_only`` is true by default because manual, probation, and abstract
        records are inventory data rather than router inputs.  Runtime health remains a
        separate injected fact, so static records load as unhealthy by default.
        """
        candidates: list[EndpointCandidate] = []
        for endpoint_id in sorted(self.endpoint_profiles):
            candidate = self.endpoint(endpoint_id)
            if automated_only and not (
                candidate.automated_routing and candidate.routing_status == "eligible"
            ):
                continue
            candidates.append(candidate)
        return tuple(candidates)

    @property
    def operational(self) -> bool:
        """Whether any measured, healthy concrete endpoint is currently eligible."""
        return bool(self.endpoints())

    def host_availability_observations(self) -> tuple[HostObservation, ...]:
        """Project exact endpoint observations into the router's host placement view."""
        by_host: dict[str, list[EndpointHostObservation]] = {}
        for observations in self.host_endpoint_observations.values():
            for observation in observations:
                by_host.setdefault(observation.host, []).append(observation)
        projected: list[HostObservation] = []
        for host in sorted(by_host):
            observations = by_host[host]
            projected.append(
                HostObservation(
                    host=host,
                    available=any(
                        item.available and item.healthy for item in observations
                    ),
                    observed_at=min(item.observed_at for item in observations),
                )
            )
        return tuple(projected)

    def profile(self, profile_id: str) -> TaskProfile:
        """Return a validated task profile by canonical identifier."""
        try:
            return self.task_profiles[profile_id]
        except KeyError as error:
            raise RegistryValidationError(
                f"unknown task profile: {profile_id}"
            ) from error


def load_registry(
    root: Path,
    *,
    as_of: str | None = None,
    calibration_path: Path | None = None,
    host_observation_paths: tuple[Path, ...] | None = None,
) -> ModelIntelligenceRegistry:
    """Load, validate, and join MIR files rooted at a repository directory.

    This function performs filesystem reads only.  It does not run a capability probe,
    execute a CLI, inspect credentials, or perform an LLM/API call.
    """
    repository_root = root.resolve()
    mir = repository_root / "infra" / "conductor"
    if not mir.is_dir():
        raise RegistryValidationError(f"MIR directory does not exist: {mir}")

    cards = _load_record_directory(mir / "model_cards", "ModelCard")
    endpoints = _load_record_directory(mir / "endpoint_profiles", "EndpointProfile")
    model_card_schema = _load_json(mir / "model_card.schema.json")
    endpoint_profile_schema = _load_json(mir / "endpoint_profile.schema.json")
    ontology = _load_json(mir / "capability_ontology.v1.json")
    profiles_document = _load_json(mir / "task_profiles.v1.json")
    index = _load_json(mir / "model_capability_index.v1.json")
    task_profile_schema = _load_json(mir / "task_profile.schema.json")
    calibration_schema = _load_json(mir / "calibration_overlay.schema.json")
    host_observation_schema = _load_json(mir / "host_observation_overlay.schema.json")
    calibration_document = _load_json(calibration_path or mir / "calibrations.v1.json")
    observation_paths = host_observation_paths or (mir / "host_observations.v1.json",)
    observation_documents = tuple(_load_json(path) for path in observation_paths)

    capability_ids = _validate_ontology(ontology)
    _validate_document_against_schema(
        profiles_document, task_profile_schema, "task profiles"
    )
    profiles = _validate_task_profiles(profiles_document, capability_ids)
    _validate_records_against_schema(cards, model_card_schema, "ModelCard")
    _validate_records_against_schema(
        endpoints, endpoint_profile_schema, "EndpointProfile"
    )
    _validate_cards(cards, capability_ids, set(profiles))
    _validate_endpoints(endpoints, cards, capability_ids)
    _validate_index(index, cards, endpoints)
    _validate_document_against_schema(
        calibration_document, calibration_schema, "calibration overlay"
    )
    for index_number, observation_document in enumerate(observation_documents):
        _validate_document_against_schema(
            observation_document,
            host_observation_schema,
            f"host observation overlay {index_number}",
        )
    calibrations, observations, diagnostics = _validated_overlays(
        calibration_document=calibration_document,
        observation_documents=observation_documents,
        endpoints=endpoints,
        profiles=profiles,
        as_of=as_of,
    )

    index_hash = _content_hash(index)
    logger.debug(
        "loaded validated MIR: cards=%d endpoints=%d", len(cards), len(endpoints)
    )
    return ModelIntelligenceRegistry(
        root=repository_root,
        model_cards=cards,
        endpoint_profiles=endpoints,
        task_profiles=profiles,
        capability_ids=frozenset(capability_ids),
        capability_index_hash=index_hash,
        calibrations=calibrations,
        host_endpoint_observations=observations,
        overlay_diagnostics=diagnostics,
        as_of=as_of,
    )


def _load_record_directory(
    directory: Path, record_name: str
) -> dict[str, Mapping[str, Any]]:
    if not directory.is_dir():
        raise RegistryValidationError(
            f"{record_name} directory does not exist: {directory}"
        )
    records: dict[str, Mapping[str, Any]] = {}
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise RegistryValidationError(f"{record_name} directory is empty: {directory}")
    for path in paths:
        record = _load_json(path)
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise RegistryValidationError(
                f"{path}: record id must be a non-empty string"
            )
        if identifier in records:
            raise RegistryValidationError(f"duplicate {record_name} id: {identifier}")
        records[identifier] = record
    return records


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RegistryValidationError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise RegistryValidationError(f"invalid JSON in {path}: {error.msg}") from error
    if not isinstance(value, dict):
        raise RegistryValidationError(f"{path}: top-level JSON must be an object")
    return value


def _validate_records_against_schema(
    records: Mapping[str, Mapping[str, Any]],
    schema: Mapping[str, Any],
    record_type: str,
) -> None:
    """Validate every MIR record against its checked-in JSON Schema subset.

    The registry has a deliberately small fixed schema vocabulary, so a
    standard-library validator keeps bootstrap/CI dependency-free.  Unsupported
    schema constructs are errors rather than silently weakening validation.
    """
    _validate_schema_contract(schema, f"{record_type} schema")
    for identifier, record in records.items():
        _validate_schema_value(record, schema, schema, f"{record_type} {identifier}")


def _validate_document_against_schema(
    document: Mapping[str, Any], schema: Mapping[str, Any], document_type: str
) -> None:
    """Validate one strict top-level MIR document with the local schema subset."""
    _validate_schema_contract(schema, f"{document_type} schema")
    _validate_schema_value(document, schema, schema, document_type)


def _validate_schema_contract(schema: Mapping[str, Any], location: str) -> None:
    """Reject malformed or unsupported local schema vocabulary before record checks."""
    if not isinstance(schema, Mapping):
        raise RegistryValidationError(f"{location}: schema node must be an object")
    unexpected = sorted(set(schema) - _SUPPORTED_SCHEMA_KEYS)
    if unexpected:
        raise RegistryValidationError(
            f"{location}: unsupported JSON Schema keyword {unexpected[0]}"
        )
    for label in ("$schema", "$id", "title"):
        if label in schema and not isinstance(schema[label], str):
            raise RegistryValidationError(
                f"{location}: schema {label} must be a string"
            )
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise RegistryValidationError(f"{location}: unsupported schema reference")
    if "type" in schema:
        raw_types = schema["type"]
        types = (
            (raw_types,)
            if isinstance(raw_types, str)
            else tuple(raw_types)
            if isinstance(raw_types, list)
            else ()
        )
        if not types or not all(isinstance(item, str) for item in types):
            raise RegistryValidationError(
                f"{location}: schema type must be a string or string array"
            )
        for expected_type in types:
            _json_type_matches(None, expected_type)
    if "additionalProperties" in schema and schema["additionalProperties"] is not False:
        raise RegistryValidationError(
            f"{location}: MIR schemas must forbid additional properties"
        )
    if "required" in schema and (
        not isinstance(schema["required"], list)
        or not all(isinstance(item, str) for item in schema["required"])
    ):
        raise RegistryValidationError(
            f"{location}: schema required must be a string array"
        )
    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, Mapping) or not all(
            isinstance(key, str) and isinstance(value, Mapping)
            for key, value in properties.items()
        ):
            raise RegistryValidationError(
                f"{location}: schema properties must map strings to objects"
            )
        for key, child in properties.items():
            _validate_schema_contract(child, f"{location}.properties.{key}")
    if "items" in schema:
        items = schema["items"]
        if not isinstance(items, Mapping):
            raise RegistryValidationError(f"{location}: schema items must be an object")
        _validate_schema_contract(items, f"{location}.items")
    if "$defs" in schema:
        definitions = schema["$defs"]
        if not isinstance(definitions, Mapping) or not all(
            isinstance(key, str) and isinstance(value, Mapping)
            for key, value in definitions.items()
        ):
            raise RegistryValidationError(
                f"{location}: schema definitions must map strings to objects"
            )
        for key, child in definitions.items():
            _validate_schema_contract(child, f"{location}.$defs.{key}")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise RegistryValidationError(f"{location}: schema enum must be an array")
    for key in ("minLength", "minItems"):
        if key in schema and (
            not isinstance(schema[key], int)
            or isinstance(schema[key], bool)
            or schema[key] < 0
        ):
            raise RegistryValidationError(
                f"{location}: schema {key} must be a non-negative integer"
            )
    if "minimum" in schema and (
        not isinstance(schema["minimum"], (int, float))
        or isinstance(schema["minimum"], bool)
    ):
        raise RegistryValidationError(f"{location}: schema minimum must be a number")
    if "maximum" in schema and (
        not isinstance(schema["maximum"], (int, float))
        or isinstance(schema["maximum"], bool)
    ):
        raise RegistryValidationError(f"{location}: schema maximum must be a number")
    if "pattern" in schema:
        if not isinstance(schema["pattern"], str):
            raise RegistryValidationError(
                f"{location}: schema pattern must be a string"
            )
        try:
            re.compile(schema["pattern"])
        except re.error as error:
            raise RegistryValidationError(
                f"{location}: invalid schema pattern"
            ) from error


def _validate_schema_value(
    value: Any, schema: Mapping[str, Any], root_schema: Mapping[str, Any], location: str
) -> None:
    if not isinstance(schema, Mapping):
        raise RegistryValidationError(f"{location}: schema node must be an object")
    reference = schema.get("$ref")
    if reference is not None:
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise RegistryValidationError(f"{location}: unsupported schema reference")
        definitions = root_schema.get("$defs")
        key = reference.removeprefix("#/$defs/")
        if not isinstance(definitions, Mapping) or not isinstance(
            definitions.get(key), Mapping
        ):
            raise RegistryValidationError(
                f"{location}: unresolved schema reference {reference}"
            )
        _validate_schema_value(value, definitions[key], root_schema, location)
        return

    raw_types = schema.get("type")
    if raw_types is not None:
        expected_types = (
            (raw_types,)
            if isinstance(raw_types, str)
            else tuple(raw_types)
            if isinstance(raw_types, list)
            else ()
        )
        if not expected_types or not all(
            isinstance(item, str) for item in expected_types
        ):
            raise RegistryValidationError(
                f"{location}: schema type must be a string or string array"
            )
        if not any(_json_type_matches(value, item) for item in expected_types):
            raise RegistryValidationError(
                f"{location}: expected JSON type {list(expected_types)}"
            )

    if "const" in schema and value != schema["const"]:
        raise RegistryValidationError(f"{location}: value must equal schema const")
    if "enum" in schema:
        allowed = schema["enum"]
        if not isinstance(allowed, list) or not any(
            value == option for option in allowed
        ):
            raise RegistryValidationError(
                f"{location}: value is not permitted by schema enum"
            )
    if "pattern" in schema:
        pattern = schema["pattern"]
        if (
            not isinstance(pattern, str)
            or not isinstance(value, str)
            or re.search(pattern, value) is None
        ):
            raise RegistryValidationError(
                f"{location}: value does not match schema pattern"
            )
    if "minLength" in schema:
        minimum_length = schema["minLength"]
        if not isinstance(minimum_length, int) or isinstance(minimum_length, bool):
            raise RegistryValidationError(
                f"{location}: schema minimum string length must be an integer"
            )
        if isinstance(value, str) and len(value) < minimum_length:
            raise RegistryValidationError(
                f"{location}: string is shorter than schema minimum"
            )
    if "minimum" in schema:
        minimum = schema["minimum"]
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
            raise RegistryValidationError(
                f"{location}: schema numeric minimum must be a number"
            )
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value < minimum
        ):
            raise RegistryValidationError(f"{location}: number is below schema minimum")
    if "maximum" in schema:
        maximum = schema["maximum"]
        if not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
            raise RegistryValidationError(
                f"{location}: schema numeric maximum must be a number"
            )
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > maximum
        ):
            raise RegistryValidationError(f"{location}: number is above schema maximum")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (
            not isinstance(properties, Mapping)
            or not isinstance(required, list)
            or not all(isinstance(item, str) for item in required)
        ):
            raise RegistryValidationError(f"{location}: malformed object schema")
        for field in required:
            if field not in value:
                raise RegistryValidationError(
                    f"{location}: missing required property {field}"
                )
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise RegistryValidationError(
                    f"{location}: unexpected property {unexpected[0]}"
                )
        for field, field_value in value.items():
            field_schema = properties.get(field)
            if field_schema is not None:
                if not isinstance(field_schema, Mapping):
                    raise RegistryValidationError(
                        f"{location}.{field}: malformed property schema"
                    )
                _validate_schema_value(
                    field_value, field_schema, root_schema, f"{location}.{field}"
                )

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None:
            if (
                not isinstance(minimum_items, int)
                or isinstance(minimum_items, bool)
                or len(value) < minimum_items
            ):
                raise RegistryValidationError(
                    f"{location}: array is shorter than schema minimum"
                )
        item_schema = schema.get("items")
        if item_schema is not None:
            if not isinstance(item_schema, Mapping):
                raise RegistryValidationError(f"{location}: malformed item schema")
            for index, item in enumerate(value):
                _validate_schema_value(
                    item, item_schema, root_schema, f"{location}[{index}]"
                )


def _json_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise RegistryValidationError(
        f"unsupported JSON Schema type in MIR schema: {expected_type}"
    )


def _validate_cards(
    cards: Mapping[str, Mapping[str, Any]],
    capability_ids: set[str],
    task_profile_ids: set[str],
) -> None:
    aliases: set[str] = set()
    for identifier, card in cards.items():
        _require_equal(
            card, "schema_version", "model-card.v1", f"ModelCard {identifier}"
        )
        identity = _require_mapping(card, "identity", f"ModelCard {identifier}")
        routing = _require_mapping(card, "routing", f"ModelCard {identifier}")
        if routing.get("automated_routing") is not False:
            raise RegistryValidationError(
                f"ModelCard {identifier} must remain abstract and non-invocable"
            )
        for field in ("family", "kind"):
            _require_string(identity, field, f"ModelCard {identifier}.identity")
        for alias in _require_list(
            identity, "aliases", f"ModelCard {identifier}.identity"
        ):
            if not isinstance(alias, str) or not alias:
                raise RegistryValidationError(
                    f"ModelCard {identifier}: alias must be a non-empty string"
                )
            if alias in aliases:
                raise RegistryValidationError(
                    f"model alias belongs to more than one ModelCard: {alias}"
                )
            aliases.add(alias)
        _validate_capability_records(
            card,
            "modalities",
            capability_ids,
            f"ModelCard {identifier}",
        )
        _validate_task_scores(card, identifier, task_profile_ids)


def _validate_capability_records(
    record: Mapping[str, Any],
    key: str,
    capability_ids: set[str],
    location: str,
) -> dict[str, bool | None]:
    """Validate capability IDs and return their asserted values by identifier."""
    asserted: dict[str, bool | None] = {}
    for capability in _require_list(record, key, location):
        if not isinstance(capability, dict):
            raise RegistryValidationError(f"{location}: capability must be an object")
        capability_id = capability.get("id")
        if capability_id not in capability_ids:
            raise RegistryValidationError(
                f"{location}: capability not declared by ontology: {capability_id}"
            )
        if capability_id in asserted:
            raise RegistryValidationError(
                f"{location}: capability is declared more than once: {capability_id}"
            )
        value = capability.get("value")
        if value not in {True, False, None}:
            raise RegistryValidationError(
                f"{location}: capability value must be true, false, or null"
            )
        asserted[capability_id] = value
    return asserted


def _validate_task_scores(
    card: Mapping[str, Any], card_id: str, task_profile_ids: set[str]
) -> None:
    """Reject unjoinable or sampleless static scores before routing can read them."""
    for score in _require_list(card, "task_scores", f"ModelCard {card_id}"):
        if not isinstance(score, dict):
            raise RegistryValidationError(
                f"ModelCard {card_id}: task score must be an object"
            )
        profile_id = score.get("task_profile_id")
        if profile_id not in task_profile_ids:
            raise RegistryValidationError(
                f"ModelCard {card_id}: task score references unknown task profile: {profile_id}"
            )
        sample_count = score.get("sample_count")
        if (
            not isinstance(sample_count, int)
            or isinstance(sample_count, bool)
            or sample_count < 0
        ):
            raise RegistryValidationError(
                f"ModelCard {card_id}: task score sample_count must be a non-negative integer"
            )
        numeric_score = score.get("score")
        if sample_count == 0:
            if numeric_score is not None:
                raise RegistryValidationError(
                    f"ModelCard {card_id}: task score with zero samples must be unavailable"
                )
            if (
                score.get("benchmark_id") is not None
                or score.get("benchmark_version") is not None
            ):
                raise RegistryValidationError(
                    f"ModelCard {card_id}: unavailable task score cannot declare a benchmark"
                )
            continue
        if (
            not isinstance(numeric_score, (int, float))
            or isinstance(numeric_score, bool)
            or not 0 <= numeric_score <= 1
        ):
            raise RegistryValidationError(
                f"ModelCard {card_id}: sampled task score must be between 0 and 1"
            )
        benchmark_id = score.get("benchmark_id")
        benchmark_version = score.get("benchmark_version")
        if not isinstance(benchmark_id, str) or not benchmark_id:
            raise RegistryValidationError(
                f"ModelCard {card_id}: sampled task score requires benchmark_id"
            )
        if not isinstance(benchmark_version, str) or not benchmark_version:
            raise RegistryValidationError(
                f"ModelCard {card_id}: sampled task score requires benchmark_version"
            )


def _validate_endpoints(
    endpoints: Mapping[str, Mapping[str, Any]],
    cards: Mapping[str, Mapping[str, Any]],
    capability_ids: set[str],
) -> None:
    invocation_keys: set[tuple[str, str]] = set()
    for identifier, endpoint in endpoints.items():
        _require_equal(
            endpoint,
            "schema_version",
            "endpoint-profile.v1",
            f"EndpointProfile {identifier}",
        )
        card_id = endpoint.get("model_card_id")
        if card_id not in cards:
            raise RegistryValidationError(
                f"EndpointProfile {identifier} references unknown ModelCard: {card_id}"
            )
        invocation = _require_mapping(
            endpoint, "invocation", f"EndpointProfile {identifier}"
        )
        engine = _require_string(
            invocation, "engine", f"EndpointProfile {identifier}.invocation"
        )
        model_identifier = _require_string(
            invocation, "model_identifier", f"EndpointProfile {identifier}.invocation"
        )
        invocation_key = (engine, model_identifier)
        if invocation_key in invocation_keys:
            raise RegistryValidationError(
                f"duplicate endpoint invocation: {engine}/{model_identifier}"
            )
        invocation_keys.add(invocation_key)
        auth_surface = _require_auth_surface(endpoint, f"EndpointProfile {identifier}")

        routing = _require_mapping(endpoint, "routing", f"EndpointProfile {identifier}")
        automated = routing.get("automated_routing")
        status = routing.get("status")
        if not isinstance(automated, bool):
            raise RegistryValidationError(
                f"EndpointProfile {identifier}: automated_routing must be boolean"
            )
        if automated and status != "eligible":
            raise RegistryValidationError(
                f"EndpointProfile {identifier}: automated routing requires eligible status"
            )
        if auth_surface is AuthSurface.ANTHROPIC_PAID_API and (
            status == "eligible" or automated
        ):
            raise RegistryValidationError(
                f"EndpointProfile {identifier}: paid Anthropic API endpoints cannot be eligible or auto-routed"
            )

        machine_constraints = _require_mapping(
            endpoint, "machine_constraints", f"EndpointProfile {identifier}"
        )
        allowlist = _require_list(
            machine_constraints,
            "allowlist",
            f"EndpointProfile {identifier}.machine_constraints",
        )
        if not allowlist or not all(
            isinstance(host, str) and host for host in allowlist
        ):
            raise RegistryValidationError(
                f"EndpointProfile {identifier}: machine allowlist must be non-empty strings"
            )

        enforcement = _require_mapping(
            endpoint, "enforcement", f"EndpointProfile {identifier}"
        )
        _require_string(
            enforcement, "mode", f"EndpointProfile {identifier}.enforcement"
        )
        exposed_capabilities = _validate_capability_records(
            endpoint,
            "exposed_capabilities",
            capability_ids,
            f"EndpointProfile {identifier}",
        )
        claimed_local_pii_capabilities = {
            capability_id
            for capability_id, value in exposed_capabilities.items()
            if capability_id in _LOCAL_PII_CAPABILITIES and value is True
        }
        if (
            claimed_local_pii_capabilities
            and auth_surface is not AuthSurface.LOCAL_RUNTIME
        ):
            raise RegistryValidationError(
                f"EndpointProfile {identifier}: local PII capabilities require local_runtime auth_surface"
            )


def _validate_ontology(ontology: Mapping[str, Any]) -> set[str]:
    _require_equal(
        ontology, "schema_version", "capability-ontology.v1", "capability ontology"
    )
    capability_ids: set[str] = set()
    for key in ("modalities", "techniques"):
        for entry in _require_list(ontology, key, "capability ontology"):
            if not isinstance(entry, dict):
                raise RegistryValidationError(
                    f"capability ontology {key}: entry must be an object"
                )
            identifier = entry.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise RegistryValidationError(
                    f"capability ontology {key}: id must be a non-empty string"
                )
            if identifier in capability_ids:
                raise RegistryValidationError(
                    f"duplicate capability ontology id: {identifier}"
                )
            capability_ids.add(identifier)
    _require_exact_ontology_ids(
        ontology,
        "evidence_levels",
        _CANONICAL_EVIDENCE_LEVELS,
    )
    _require_exact_ontology_ids(
        ontology,
        "routing_statuses",
        _CANONICAL_ROUTING_STATUSES,
    )
    return capability_ids


def _require_exact_ontology_ids(
    ontology: Mapping[str, Any], key: str, expected_ids: frozenset[str]
) -> None:
    """Keep schema-visible vocabulary aligned with the typed routing contracts."""
    identifiers: set[str] = set()
    for entry in _require_list(ontology, key, "capability ontology"):
        if not isinstance(entry, dict):
            raise RegistryValidationError(
                f"capability ontology {key}: entry must be an object"
            )
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise RegistryValidationError(
                f"capability ontology {key}: id must be a non-empty string"
            )
        if identifier in identifiers:
            raise RegistryValidationError(
                f"duplicate capability ontology {key} id: {identifier}"
            )
        identifiers.add(identifier)
    if identifiers != expected_ids:
        raise RegistryValidationError(
            f"capability ontology {key} must exactly match canonical contract"
        )


def _validate_task_profiles(
    document: Mapping[str, Any], capability_ids: set[str]
) -> dict[str, TaskProfile]:
    _require_equal(document, "schema_version", "task-profiles.v1", "task profiles")
    profiles: dict[str, TaskProfile] = {}
    for raw in _require_list(document, "profiles", "task profiles"):
        if not isinstance(raw, dict):
            raise RegistryValidationError("task profile must be an object")
        identifier = raw.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise RegistryValidationError("task profile id must be a non-empty string")
        if identifier in profiles:
            raise RegistryValidationError(f"duplicate task profile id: {identifier}")
        required = _string_set(
            raw.get("required_capabilities"),
            f"task profile {identifier}.required_capabilities",
        )
        modalities = _string_set(
            raw.get("allowed_modalities"),
            f"task profile {identifier}.allowed_modalities",
        )
        unknown = (required | modalities) - capability_ids
        if unknown:
            raise RegistryValidationError(
                f"task profile {identifier} has unknown capabilities: {sorted(unknown)}"
            )
        pii_policy = str(raw.get("pii_policy", "context_dependent"))
        if pii_policy == "local_only" and not _LOCAL_PII_CAPABILITIES <= required:
            raise RegistryValidationError(
                f"task profile {identifier}: local_only policy requires local_only and pii_safe_local capabilities"
            )
        minimum_tier = raw.get("minimum_quality_tier")
        if (
            not isinstance(minimum_tier, int)
            or isinstance(minimum_tier, bool)
            or minimum_tier < 0
        ):
            raise RegistryValidationError(
                f"task profile {identifier}: minimum_quality_tier must be a non-negative integer"
            )
        minimum_score = raw.get("minimum_task_score")
        if minimum_score is not None and (
            not isinstance(minimum_score, (int, float))
            or isinstance(minimum_score, bool)
            or not 0 <= minimum_score <= 1
        ):
            raise RegistryValidationError(
                f"task profile {identifier}: minimum_task_score must be null or between 0 and 1"
            )
        profiles[identifier] = TaskProfile(
            id=identifier,
            mutation=bool(raw.get("mutation")),
            minimum_quality_tier=minimum_tier,
            minimum_task_score=float(minimum_score)
            if minimum_score is not None
            else None,
            required_capabilities=frozenset(required),
            allowed_modalities=frozenset(modalities),
            pii_policy=pii_policy,
            benchmark_id=_optional_string(
                raw.get("benchmark_id"),
                f"task profile {identifier}.benchmark_id",
            ),
            benchmark_version=_optional_string(
                raw.get("benchmark_version"),
                f"task profile {identifier}.benchmark_version",
            ),
            minimum_sample_count=_positive_integer(
                raw.get("minimum_sample_count", 1),
                f"task profile {identifier}.minimum_sample_count",
            ),
            maximum_dispersion=_bounded_optional_number(
                raw.get("maximum_dispersion"),
                f"task profile {identifier}.maximum_dispersion",
                upper=0.25,
            ),
            minimum_context_tokens=_optional_positive_integer(
                raw.get("minimum_context_tokens"),
                f"task profile {identifier}.minimum_context_tokens",
            ),
            minimum_output_tokens=_optional_positive_integer(
                raw.get("minimum_output_tokens"),
                f"task profile {identifier}.minimum_output_tokens",
            ),
        )
        profile = profiles[identifier]
        benchmark_fields = (profile.benchmark_id, profile.benchmark_version)
        if (benchmark_fields[0] is None) != (benchmark_fields[1] is None):
            raise RegistryValidationError(
                f"task profile {identifier}: benchmark id and version must both be set or null"
            )
        if profile.minimum_task_score is not None and profile.benchmark_id is None:
            raise RegistryValidationError(
                f"task profile {identifier}: a score floor requires a benchmark contract"
            )
    if not profiles:
        raise RegistryValidationError("task profiles cannot be empty")
    return profiles


def _validate_index(
    index: Mapping[str, Any],
    cards: Mapping[str, Mapping[str, Any]],
    endpoints: Mapping[str, Mapping[str, Any]],
) -> None:
    _require_equal(
        index, "schema_version", "model-capability-index.v1", "capability index"
    )
    from scripts.conductor.build_model_capability_index import build_index

    expected = build_index(list(cards.values()), list(endpoints.values()))
    if index != expected:
        raise RegistryValidationError(
            "capability index is not the exact deterministic projection of MIR records"
        )


def _validated_overlays(
    *,
    calibration_document: Mapping[str, Any],
    observation_documents: tuple[Mapping[str, Any], ...],
    endpoints: Mapping[str, Mapping[str, Any]],
    profiles: Mapping[str, TaskProfile],
    as_of: str | None,
) -> tuple[
    Mapping[str, tuple[CalibrationRecord, ...]],
    Mapping[str, tuple[EndpointHostObservation, ...]],
    tuple[str, ...],
]:
    """Validate and retain only fresh exact-join overlay facts."""
    clock = parse_timestamp(as_of)
    if as_of is not None and clock is None:
        raise RegistryValidationError(
            "overlay as_of must be a timezone-aware ISO-8601 timestamp"
        )
    calibrations: dict[str, list[CalibrationRecord]] = {}
    observations: dict[str, list[EndpointHostObservation]] = {}
    diagnostics: list[str] = []
    calibration_keys: set[tuple[str, str, str, str]] = set()
    for raw in calibration_document["records"]:
        try:
            record = CalibrationRecord.from_mapping(raw)
        except CalibrationError as error:
            raise RegistryValidationError(f"calibration overlay: {error}") from error
        if record.endpoint_id not in endpoints:
            raise RegistryValidationError(
                f"calibration overlay references unknown endpoint: {record.endpoint_id}"
            )
        if record.task_profile_id not in profiles:
            raise RegistryValidationError(
                f"calibration overlay references unknown task profile: {record.task_profile_id}"
            )
        key = (
            record.endpoint_id,
            record.task_profile_id,
            record.benchmark_id,
            record.benchmark_version,
        )
        if key in calibration_keys:
            raise RegistryValidationError(
                "calibration overlay contains a duplicate endpoint/task/benchmark record"
            )
        calibration_keys.add(key)
        endpoint = endpoints[record.endpoint_id]
        reason = record.rejection(
            endpoint_profile_hash=_content_hash(endpoint),
            profile=profiles[record.task_profile_id],
            as_of=clock,
        )
        if reason is not None:
            diagnostics.append(
                f"calibration:{record.endpoint_id}:{record.task_profile_id}:{reason}"
            )
            continue
        calibrations.setdefault(record.endpoint_id, []).append(record)

    observation_keys: set[tuple[str, str]] = set()
    for document in observation_documents:
        for raw in document["observations"]:
            try:
                observation = EndpointHostObservation.from_mapping(raw)
            except CalibrationError as error:
                raise RegistryValidationError(
                    f"host observation overlay: {error}"
                ) from error
            if observation.endpoint_id not in endpoints:
                raise RegistryValidationError(
                    "host observation overlay references unknown endpoint: "
                    f"{observation.endpoint_id}"
                )
            key = (observation.endpoint_id, observation.host)
            if key in observation_keys:
                raise RegistryValidationError(
                    "host observation overlay contains duplicate endpoint/host evidence"
                )
            observation_keys.add(key)
            endpoint = endpoints[observation.endpoint_id]
            reason = observation.rejection(
                endpoint_profile_hash=_content_hash(endpoint),
                model_identifier=str(endpoint["invocation"]["model_identifier"]),
                machine_allowlist=tuple(
                    str(host) for host in endpoint["machine_constraints"]["allowlist"]
                ),
                as_of=clock,
            )
            if reason is not None:
                diagnostics.append(
                    f"observation:{observation.endpoint_id}:{observation.host}:{reason}"
                )
                continue
            observations.setdefault(observation.endpoint_id, []).append(observation)

    return (
        {
            endpoint_id: tuple(
                sorted(
                    records,
                    key=lambda item: (
                        item.task_profile_id,
                        item.benchmark_id,
                        item.benchmark_version,
                    ),
                )
            )
            for endpoint_id, records in sorted(calibrations.items())
        },
        {
            endpoint_id: tuple(sorted(items, key=lambda item: item.host))
            for endpoint_id, items in sorted(observations.items())
        },
        tuple(sorted(diagnostics)),
    )


def _candidate_from_records(
    endpoint: Mapping[str, Any],
    card: Mapping[str, Any],
    calibrations: tuple[CalibrationRecord, ...],
    observations: tuple[EndpointHostObservation, ...],
    profiles: Mapping[str, TaskProfile],
) -> EndpointCandidate:
    endpoint_features = _evidence_by_capability(
        endpoint.get("exposed_capabilities", [])
    )
    card_features = _evidence_by_capability(card.get("modalities", []))
    combined: dict[str, CapabilityEvidence] = dict(card_features)
    combined.update(endpoint_features)
    auth_surface = _require_auth_surface(
        endpoint, f"EndpointProfile {endpoint.get('id', 'unknown')}"
    )
    if auth_surface is not AuthSurface.LOCAL_RUNTIME:
        for capability_id in _LOCAL_PII_CAPABILITIES:
            combined.pop(capability_id, None)
    usable_observations = tuple(
        observation
        for observation in observations
        if observation.available
        and observation.healthy
        and observation.identity_verified
    )
    if usable_observations:
        observed_at = min(item.observed_at for item in usable_observations)
        expires_at = min(item.expires_at for item in usable_observations)
        combined["context_tokens"] = CapabilityEvidence(
            capability="context_tokens",
            value=min(item.context_tokens for item in usable_observations),
            kind=EvidenceKind.PROBED,
            evidence_ref="host-observation-overlay:context_tokens",
            observed_at=observed_at,
            expires_at=expires_at,
            confidence=1.0,
        )
        combined["output_tokens"] = CapabilityEvidence(
            capability="output_tokens",
            value=min(item.output_tokens for item in usable_observations),
            kind=EvidenceKind.PROBED,
            evidence_ref="host-observation-overlay:output_tokens",
            observed_at=observed_at,
            expires_at=expires_at,
            confidence=1.0,
        )
    health_date = (
        min(item.observed_at for item in usable_observations)
        if usable_observations
        else _first_observed_at(endpoint.get("evidence", []))
    )
    overlay_scores = tuple(_task_score_from_calibration(item) for item in calibrations)
    quality_tier = max(
        (profiles[item.task_profile_id].minimum_quality_tier for item in calibrations),
        default=0,
    )
    evidence_ready = any(
        _observation_supports_profile(
            observation,
            profiles[calibration.task_profile_id],
        )
        for calibration in calibrations
        for observation in usable_observations
    )
    static_routing = endpoint["routing"]
    status = str(static_routing["status"])
    statically_authorized = (
        status == "eligible" and static_routing["automated_routing"] is True
    )
    automated_routing = bool(
        evidence_ready
        and statically_authorized
        and auth_surface is not AuthSurface.UNKNOWN
        and auth_surface is not AuthSurface.ANTHROPIC_PAID_API
    )
    enforcement_mode = _conservative_enforcement_mode(usable_observations)
    return EndpointCandidate(
        endpoint_id=str(endpoint["id"]),
        engine=str(endpoint["invocation"]["engine"]),
        model_card_id=str(card["id"]),
        model=str(endpoint["invocation"]["model_identifier"]),
        family=str(card["identity"]["family"]),
        role=Role.BUILDER,
        features=tuple(combined[key] for key in sorted(combined)),
        task_scores=tuple(
            sorted(
                (*_task_scores(card.get("task_scores", [])), *overlay_scores),
                key=lambda item: (
                    item.task_profile_id,
                    item.benchmark_id or "",
                    item.benchmark_version or "",
                ),
            )
        ),
        healthy=bool(usable_observations),
        health_observed_at=health_date,
        machine_allowlist=(
            tuple(sorted(item.host for item in usable_observations))
            if usable_observations
            else tuple(
                sorted(
                    str(host) for host in endpoint["machine_constraints"]["allowlist"]
                )
            )
        ),
        cost_rank=_unknown_rank(),
        latency_rank=max(
            (item.latency_ms for item in usable_observations),
            default=_unknown_rank(),
        ),
        quota_pressure_rank=_unknown_rank(),
        quality_tier=quality_tier,
        enforcement_mode=enforcement_mode,
        identity_confidence=1.0 if usable_observations else 0.0,
        model_card_hash=_content_hash(card),
        endpoint_profile_hash=_content_hash(endpoint),
        capability_snapshot_hash=_content_hash(
            {
                "endpoint": endpoint["id"],
                "calibrations": [item.as_mapping() for item in calibrations],
                "observations": [
                    {
                        "host": item.host,
                        "model_identifier": item.model_identifier,
                        "observed_at": item.observed_at,
                        "expires_at": item.expires_at,
                        "probe_id": item.probe_id,
                        "probe_version": item.probe_version,
                    }
                    for item in observations
                ],
            }
        ),
        automated_routing=automated_routing,
        routing_status=status,
        uses_paid_anthropic_api=auth_surface is AuthSurface.ANTHROPIC_PAID_API,
        auth_surface=auth_surface,
    )


def _task_score_from_calibration(record: CalibrationRecord) -> TaskScore:
    return TaskScore(
        task_profile_id=record.task_profile_id,
        score=record.score,
        benchmark_id=record.benchmark_id,
        benchmark_version=record.benchmark_version,
        sample_count=record.sample_count,
        observed_at=record.measured_at,
        evidence_kind=EvidenceKind.BENCHMARKED,
        conservative_score=record.conservative_score,
        sample_hashes=record.sample_hashes,
        scorer_id=record.scorer_id,
        scorer_version=record.scorer_version,
        expires_at=record.expires_at,
        dispersion=record.dispersion,
    )


def _observation_supports_profile(
    observation: EndpointHostObservation, profile: TaskProfile
) -> bool:
    if (
        profile.minimum_context_tokens is not None
        and observation.context_tokens < profile.minimum_context_tokens
    ):
        return False
    if (
        profile.minimum_output_tokens is not None
        and observation.output_tokens < profile.minimum_output_tokens
    ):
        return False
    return not profile.mutation or observation.enforcement_mode == "enforced"


def _conservative_enforcement_mode(
    observations: tuple[EndpointHostObservation, ...],
) -> str:
    if not observations:
        return "unmeasured"
    strength = {
        "unmeasured": 0,
        "manual_only": 1,
        "advisory_only": 2,
        "advisory": 2,
        "shadow": 3,
        "enforced": 4,
    }
    return min(
        (item.enforcement_mode for item in observations),
        key=lambda mode: (strength.get(mode, 0), mode),
    )


def _evidence_by_capability(raw_capabilities: Any) -> dict[str, CapabilityEvidence]:
    if not isinstance(raw_capabilities, list):
        return {}
    result: dict[str, CapabilityEvidence] = {}
    for raw in raw_capabilities:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            continue
        evidence = raw.get("evidence", [])
        result[raw["id"]] = CapabilityEvidence(
            capability=raw["id"],
            value=raw.get("value"),
            kind=_evidence_kind(evidence),
            evidence_ref=_first_evidence_ref(evidence),
            observed_at=_first_observed_at(evidence),
            expires_at=None,
            confidence=1.0
            if _evidence_kind(evidence) is not EvidenceKind.UNMEASURED
            else 0.0,
        )
    return result


def _task_scores(raw_scores: Any) -> tuple[TaskScore, ...]:
    if not isinstance(raw_scores, list):
        return ()
    scores: list[TaskScore] = []
    for raw in raw_scores:
        if not isinstance(raw, dict) or not isinstance(raw.get("task_profile_id"), str):
            continue
        evidence = raw.get("evidence", [])
        benchmark_id = raw.get("benchmark_id")
        benchmark_version = raw.get("benchmark_version")
        scores.append(
            TaskScore(
                task_profile_id=raw["task_profile_id"],
                score=raw.get("score")
                if isinstance(raw.get("score"), (int, float))
                else None,
                benchmark_id=benchmark_id if isinstance(benchmark_id, str) else None,
                benchmark_version=benchmark_version
                if isinstance(benchmark_version, str)
                else None,
                sample_count=raw.get("sample_count")
                if isinstance(raw.get("sample_count"), int)
                else 0,
                observed_at=_first_observed_at(evidence),
                evidence_kind=_evidence_kind(evidence),
            )
        )
    return tuple(
        sorted(scores, key=lambda item: (item.task_profile_id, item.benchmark_id or ""))
    )


def _is_automated_eligible(endpoint: Mapping[str, Any]) -> bool:
    routing = endpoint.get("routing")
    return (
        isinstance(routing, dict)
        and routing.get("status") == "eligible"
        and routing.get("automated_routing") is True
    )


def _require_auth_surface(endpoint: Mapping[str, Any], location: str) -> AuthSurface:
    """Return explicit endpoint authority; never infer it from names or harnesses."""
    raw = endpoint.get("auth_surface")
    try:
        return AuthSurface(raw)
    except (TypeError, ValueError) as error:
        raise RegistryValidationError(
            f"{location}.auth_surface is unknown or missing"
        ) from error


def _evidence_kind(raw_evidence: Any) -> EvidenceKind:
    if not isinstance(raw_evidence, list):
        return EvidenceKind.UNMEASURED
    levels = {item.get("level") for item in raw_evidence if isinstance(item, dict)}
    if "benchmarked" in levels:
        return EvidenceKind.BENCHMARKED
    if "production" in levels:
        return EvidenceKind.PRODUCTION
    if "probed" in levels:
        return EvidenceKind.PROBED
    if "declared" in levels:
        return EvidenceKind.DECLARED
    return EvidenceKind.UNMEASURED


def _first_evidence_ref(raw_evidence: Any) -> str:
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            if isinstance(item, dict) and isinstance(item.get("ref"), str):
                return item["ref"]
    return "unmeasured"


def _first_observed_at(raw_evidence: Any) -> str:
    if isinstance(raw_evidence, list):
        dates = sorted(
            item["observed_at"]
            for item in raw_evidence
            if isinstance(item, dict)
            and isinstance(item.get("observed_at"), str)
            and _is_iso_date(item["observed_at"])
        )
        if dates:
            return dates[-1]
    return "1970-01-01"


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value[:10])
    except ValueError:
        return False
    return True


def _content_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _unknown_rank() -> int:
    return 2_147_483_647


def _require_mapping(
    value: Mapping[str, Any], key: str, location: str
) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise RegistryValidationError(f"{location}.{key} must be an object")
    return item


def _require_list(value: Mapping[str, Any], key: str, location: str) -> list[Any]:
    item = value.get(key)
    if not isinstance(item, list):
        raise RegistryValidationError(f"{location}.{key} must be an array")
    return item


def _require_string(value: Mapping[str, Any], key: str, location: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise RegistryValidationError(f"{location}.{key} must be a non-empty string")
    return item


def _require_equal(
    value: Mapping[str, Any], key: str, expected: str, location: str
) -> None:
    if value.get(key) != expected:
        raise RegistryValidationError(f"{location}.{key} must equal {expected!r}")


def _string_set(value: Any, location: str) -> set[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise RegistryValidationError(
            f"{location} must be an array of non-empty strings"
        )
    return set(value)


def _optional_string(value: Any, location: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RegistryValidationError(f"{location} must be null or a non-empty string")
    return value


def _positive_integer(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RegistryValidationError(f"{location} must be a positive integer")
    return value


def _optional_positive_integer(value: Any, location: str) -> int | None:
    if value is None:
        return None
    return _positive_integer(value, location)


def _bounded_optional_number(
    value: Any, location: str, *, upper: float
) -> float | None:
    if value is None:
        return None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 <= value <= upper
    ):
        raise RegistryValidationError(
            f"{location} must be null or between 0 and {upper}"
        )
    return float(value)


def _index_ids(value: Any, key: str, location: str) -> set[str]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{location} must be an array")
    identifiers: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise RegistryValidationError(f"{location} entries must contain {key}")
        identifiers.add(item[key])
    if len(identifiers) != len(value):
        raise RegistryValidationError(f"{location} contains duplicate identifiers")
    return identifiers
