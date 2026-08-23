from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest
from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    ValidationError,
)
from research_os.schemas import (
    SCHEMA_DIRECTORY,
    SCHEMA_MODELS,
    checked_in_schemas_match,
    validate_schema_artifacts,
)


def test_checked_in_schemas_are_byte_identical_to_fresh_regeneration() -> None:
    assert checked_in_schemas_match() == ()


def test_generated_schemas_are_valid_draft_2020_12() -> None:
    assert validate_schema_artifacts() == ()


def _collect_pattern_values(node: Any, out: list[str]) -> None:
    """Recursively collect every JSON Schema "pattern" keyword value."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "pattern" and isinstance(value, str):
                out.append(value)
            else:
                _collect_pattern_values(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_pattern_values(item, out)


def _schema_pattern_values() -> list[tuple[str, str]]:
    """(schema filename, pattern) pairs for every checked-in schema.json."""
    pairs: list[tuple[str, str]] = []
    for contract_kind in SCHEMA_MODELS:
        path = SCHEMA_DIRECTORY / f"{contract_kind}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        patterns: list[str] = []
        _collect_pattern_values(schema, patterns)
        pairs.extend((path.name, pattern) for pattern in patterns)
    return pairs


def _ecma_regexes_that_fail_to_compile(patterns: list[str]) -> list[tuple[str, str]]:
    """Ask Node's V8 (the engine JSON Schema's "pattern" keyword is specified
    against -- ECMA-262) to compile each pattern with `new RegExp(...)`.
    Returns (pattern, error_message) for every one that fails.

    This deliberately does NOT use Python's `re` module: `re` (and
    pydantic-core, and the `jsonschema` package used elsewhere in this file)
    accepts a strictly larger dialect than ECMA-262 -- possessive quantifiers
    (`*+`, `++`), atomic groups, etc. A pattern can be perfectly valid Python
    and still be uncompilable by every non-Python consumer (Go, TypeScript,
    Java) of this schema file, which is the cross-language wire contract.
    """
    script = (
        "const patterns = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "const failures = [];"
        "for (const p of patterns) {"
        "  try { new RegExp(p); }"
        "  catch (e) { failures.push([p, String(e.message)]); }"
        "}"
        "process.stdout.write(JSON.stringify(failures));"
    )
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(patterns),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    failures: list[list[str]] = json.loads(result.stdout)
    return [(pattern, message) for pattern, message in failures]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_every_schema_pattern_compiles_under_ecma_262() -> None:
    """Guard against a defect this suite cannot otherwise see.

    `test_checked_in_schemas_are_byte_identical_to_fresh_regeneration` and
    `test_generated_schemas_are_valid_draft_2020_12` both validate these
    files with Python's `jsonschema` package, which compiles the "pattern"
    keyword with Python's `re` -- a strictly larger dialect than the
    ECMA-262 regex grammar the JSON Schema spec actually names. That means a
    pattern that is valid Python (e.g. a possessive quantifier `*+`/`++`)
    but invalid ECMA-262 passes every other test in this file while being
    uncompilable by every non-Python consumer of the schema (Go, TypeScript,
    Java): the schema is the cross-language wire contract, and "no consumer
    has been written against it yet" is not the same claim as "the contract
    is valid". This test asks Node's V8 -- a real ECMA-262 engine -- to
    compile every "pattern" value in both checked-in schema.json files.

    Proven to fail loudly against the disease this guards: pointed at the
    possessive-quantifier `Identifier`/`RegisteredName` patterns that were
    briefly on this branch (`^[a-z][a-z0-9_-]*+(?:[.-][a-z0-9_-]++)*$` /
    `^[a-z][a-z0-9]*+(?:[._-][a-z0-9][a-z0-9_-]*+)+$`), this exact check
    fails with "SyntaxError: Invalid regular expression: ... Nothing to
    repeat" -- see the primitives.py history / PR discussion for the
    transcript. Never weaken this to "compiles under Python `re`".
    """
    pairs = _schema_pattern_values()
    assert pairs, "expected at least one 'pattern' keyword in the checked-in schemas"

    patterns = [pattern for _, pattern in pairs]
    failures = _ecma_regexes_that_fail_to_compile(patterns)

    if failures:
        failed_patterns = {pattern for pattern, _ in failures}
        offending_fields = [
            f"{filename}: {pattern!r}" for filename, pattern in pairs if pattern in failed_patterns
        ]
        raise AssertionError(
            "the following schema 'pattern' values are not valid ECMA-262 "
            f"regexes (uncompilable by node -- Go/TS/Java consumers would "
            f"also reject them): {failures!r}\nOffending fields: {offending_fields!r}"
        )


@pytest.mark.parametrize(
    "invalid_timestamp",
    ("2026-02-01T08:01:00+08:00", "2026-02-01T00:01:00"),
    ids=("non_utc", "naive"),
)
def test_shipped_schema_asserts_utc_timestamp_offset(invalid_timestamp: str) -> None:
    schema_path = SCHEMA_DIRECTORY / "revocation_receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    fixture_path = (
        SCHEMA_DIRECTORY.parents[1] / "fixtures" / "revocation_receipt" / "valid_minimal.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["issued_at"] = invalid_timestamp

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)
