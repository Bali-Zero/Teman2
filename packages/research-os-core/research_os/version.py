"""Contract identity and schema compatibility rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

CONTRACT_FAMILY = "research-os"
CONTRACT_VERSION = "research-os/v1.0.0"
_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """A strict three-component semantic version."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> SemanticVersion:
        match = _SEMVER_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError(f"invalid semantic version: {value!r}")
        return cls(*(int(component) for component in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_contract_version(value: str) -> SemanticVersion:
    """Parse the semantic component of a Research OS contract version."""

    prefix = f"{CONTRACT_FAMILY}/v"
    if not value.startswith(prefix):
        raise ValueError(f"contract version must start with {prefix!r}")
    return SemanticVersion.parse(value.removeprefix(prefix))


def compare_semantic_versions(left: str | SemanticVersion, right: str | SemanticVersion) -> int:
    """Return -1, 0, or 1 after comparing two strict semantic versions."""

    left_version = SemanticVersion.parse(left) if isinstance(left, str) else left
    right_version = SemanticVersion.parse(right) if isinstance(right, str) else right
    return (left_version > right_version) - (left_version < right_version)


class CompatibilityLevel(StrEnum):
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


@dataclass(frozen=True)
class CompatibilityReport:
    """Compatibility decision with deterministic, explicit breaking reasons."""

    compatible: bool
    level: CompatibilityLevel
    breaking_reasons: tuple[str, ...]
    additive_optional_fields: tuple[str, ...]


def _json_literal(value: Any) -> str:
    if isinstance(value, str):
        return value
    return repr(value)


def _compare_schema_node(
    old: Any,
    new: Any,
    path: str,
    breaking: list[str],
    additive: list[str],
) -> None:
    if not isinstance(old, Mapping) or not isinstance(new, Mapping):
        if old != new:
            breaking.append(f"meaning change at {path}")
        return

    old_enum = old.get("enum")
    new_enum = new.get("enum")
    if isinstance(old_enum, list) and isinstance(new_enum, list):
        for value in new_enum:
            if value not in old_enum:
                breaking.append(f"enum addition at {path}: {_json_literal(value)}")
        for value in old_enum:
            if value not in new_enum:
                breaking.append(f"enum removal at {path}: {_json_literal(value)}")

    old_properties = old.get("properties", {})
    new_properties = new.get("properties", {})
    if isinstance(old_properties, Mapping) and isinstance(new_properties, Mapping):
        old_required = set(old.get("required", []))
        new_required = set(new.get("required", []))
        for name in sorted(old_required - new_required):
            breaking.append(f"required-field change at {path}: removed {name}")
        for name in sorted(new_required - old_required):
            breaking.append(f"required-field change at {path}: added {name}")
        for name in sorted(old_properties.keys() - new_properties.keys()):
            breaking.append(f"field removal at {path}.{name}")
        for name in sorted(new_properties.keys() - old_properties.keys()):
            field_path = f"{path}.{name}"
            if name in new_required:
                breaking.append(f"required field addition at {field_path}")
            else:
                additive.append(field_path)
        for name in sorted(old_properties.keys() & new_properties.keys()):
            _compare_schema_node(
                old_properties[name],
                new_properties[name],
                f"{path}.{name}",
                breaking,
                additive,
            )

    old_definitions = old.get("$defs", {})
    new_definitions = new.get("$defs", {})
    if isinstance(old_definitions, Mapping) and isinstance(new_definitions, Mapping):
        for name in sorted(old_definitions.keys() - new_definitions.keys()):
            breaking.append(f"definition removal at {path}.$defs.{name}")
        for name in sorted(old_definitions.keys() & new_definitions.keys()):
            _compare_schema_node(
                old_definitions[name],
                new_definitions[name],
                f"{path}.$defs.{name}",
                breaking,
                additive,
            )
        # A definition introduced only to type a new optional field is part
        # of that additive minor change. Any use by an existing field is
        # still observed as a change to that field's $ref/constraint.
    elif old_definitions != new_definitions:
        breaking.append(f"meaning change at {path}: schema keyword $defs changed")

    structural_keys = (set(old) | set(new)) - {
        "$id",
        "$schema",
        "$defs",
        "enum",
        "properties",
        "required",
    }
    for key in sorted(structural_keys):
        if key not in old or key not in new:
            breaking.append(f"meaning change at {path}: schema keyword {key} changed")
        elif old[key] != new[key]:
            if isinstance(old[key], Mapping) and isinstance(new[key], Mapping):
                _compare_schema_node(old[key], new[key], f"{path}.{key}", breaking, additive)
            else:
                breaking.append(f"meaning change at {path}: schema keyword {key} changed")


def check_compatibility(
    old_schema: Mapping[str, Any],
    new_schema: Mapping[str, Any],
) -> CompatibilityReport:
    """Apply frozen rule 1.10 to two JSON Schema documents.

    Additive optional fields require a minor version. Removals, enum changes,
    required-field changes, and all other semantic constraint changes require
    a major version.
    """

    breaking: list[str] = []
    additive: list[str] = []
    _compare_schema_node(old_schema, new_schema, "$", breaking, additive)
    unique_breaking = tuple(dict.fromkeys(breaking))
    unique_additive = tuple(dict.fromkeys(additive))
    if unique_breaking:
        level = CompatibilityLevel.MAJOR
    elif unique_additive:
        level = CompatibilityLevel.MINOR
    else:
        level = CompatibilityLevel.PATCH
    return CompatibilityReport(
        compatible=not unique_breaking,
        level=level,
        breaking_reasons=unique_breaking,
        additive_optional_fields=unique_additive,
    )
