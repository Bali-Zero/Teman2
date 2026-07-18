"""Shared fixtures for visa_engine tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[4] / "backend" / "services" / "visa_engine" / "schemas"
)


def _load_schema_registry() -> Registry:
    resources = []
    for schema_file in _SCHEMAS_DIR.glob("*.schema.json"):
        doc = json.loads(schema_file.read_text())
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


@pytest.fixture(scope="session")
def schema_registry() -> Registry:
    return _load_schema_registry()


def _validator_for(entrypoint_filename: str, registry: Registry) -> Draft202012Validator:
    schema = json.loads((_SCHEMAS_DIR / entrypoint_filename).read_text())
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


@pytest.fixture(scope="session")
def rule_pack_validator(schema_registry: Registry) -> Draft202012Validator:
    return _validator_for("rule-pack.schema.json", schema_registry)


@pytest.fixture(scope="session")
def applicant_facts_validator(schema_registry: Registry) -> Draft202012Validator:
    return _validator_for("applicant-facts.schema.json", schema_registry)


@pytest.fixture(scope="session")
def decision_validator(schema_registry: Registry) -> Draft202012Validator:
    return _validator_for("decision.schema.json", schema_registry)


@pytest.fixture
def schemas_dir() -> Path:
    return _SCHEMAS_DIR


def validate_or_fail(validator: Draft202012Validator, instance: dict[str, Any]) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        messages = "\n".join(f"- {'/'.join(map(str, e.path))}: {e.message}" for e in errors)
        raise AssertionError(f"schema validation failed:\n{messages}")
