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
    _prettier_json,
    checked_in_schemas_match,
    validate_schema_artifacts,
)

# packages/research-os-core/research_os/schemas -> repo root is 4 levels up
# (schemas -> research_os -> research-os-core -> packages -> repo root).
_REPO_ROOT = SCHEMA_DIRECTORY.parents[3]
_PRETTIER_ESM_ENTRYPOINT = _REPO_ROOT / "node_modules" / "prettier" / "index.mjs"


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


# --- _prettier_json vs. real Prettier -----------------------------------
#
# `test_checked_in_schemas_are_byte_identical_to_fresh_regeneration` and
# `test_generated_schemas_are_valid_draft_2020_12` above both compare
# `_prettier_json`'s output against itself (the checked-in files were
# produced by the same function) -- a self-consistency check that can never
# catch a defect in `_prettier_json`'s own understanding of Prettier's
# layout rules, no matter how the function is wrong. Every test below
# instead asks a real `prettier` (Node, `parser: "json"`) to format the
# same value and asserts byte-identical output, so a divergence in the
# algorithm itself -- not just a divergence from what we last generated --
# fails the suite.
#
# Note on invocation: the `prettier` *CLI*, when given a file argument (not
# stdin) and invoked with a cwd inside this git repository, was observed
# during authoring to silently skip wrapping some over-width JSON arrays
# that it wraps correctly from any other cwd or via `--stdin-filepath`
# (confirmed cwd-dependent, not flaky -- 100% reproducible either way, same
# Prettier version, byte-identical `node_modules/prettier` package
# contents). That CLI quirk is orthogonal to this bug and not something
# this test is trying to characterize, so it is sidestepped entirely here:
# we call Prettier's own JS `format()` API directly (proven cwd-independent
# during authoring), never the CLI, so the oracle is Prettier's formatting
# engine itself with no CLI config-resolution layer in between.

_PRETTIER_BATCH_FORMAT_SCRIPT = """
const prettierPath = process.argv[1];
const prettier = (await import(prettierPath)).default;
const chunks = [];
process.stdin.on("data", (c) => chunks.push(c));
process.stdin.on("end", async () => {
  const values = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const results = [];
  for (const v of values) {
    results.push(await prettier.format(JSON.stringify(v), { parser: "json" }));
  }
  process.stdout.write(JSON.stringify(results));
});
"""


def _real_prettier_batch(values: list[Any]) -> list[str]:
    """Format each of `values` with real Prettier's JS API, in one Node process."""
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            _PRETTIER_BATCH_FORMAT_SCRIPT,
            _PRETTIER_ESM_ENTRYPOINT.as_uri(),
        ],
        input=json.dumps(values),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    formatted: list[str] = json.loads(result.stdout)
    return formatted


def _shape_table() -> list[tuple[str, Any]]:
    """(label, value) pairs sweeping the axes that reproduce the bug.

    Every shape here is an array-of-arrays (or array-of-objects /
    object-of-object-of-array): the ONLY place `_prettier_json`'s list
    branch recurses into a child whose own inline-vs-break decision depends
    on `starting_column`/`trailing_comma` -- a same-level array of bare
    strings never recurses that way (its compact form is measured directly
    against `budget`, without a per-item recursive call), which is exactly
    why the missing-parameter defect stayed invisible to every existing
    fixture. Each entry sweeps the varying string's length so the probe
    array's would-be single-line width crosses 78..83 -- the exact band the
    original defect (80 without a trailing comma vs. 81 with one) lives in
    -- inside a distinct container (array vs. object), sibling position
    (last vs. non-last), and nesting depth (2 through 4).
    """
    entries: list[tuple[str, Any]] = []

    # A: array container, probe is the LAST sibling, depth 2.
    #    starting_column=2 (outer array's child indent), trailing_comma=False
    #    (last item) => budget=80, width = 2 + (n+4) = n + 6.
    for n in range(72, 78):
        entries.append((f"array_last_sibling_n{n}", [["short"], ["x" * n]]))

    # B: array container, probe is the FIRST (non-last) sibling, depth 2.
    #    starting_column=2, trailing_comma=True => budget=79, same width
    #    formula n + 6 -- this is the original bug's own shape (a trailing
    #    comma shifts the wrap boundary down by one).
    for n in range(72, 78):
        entries.append((f"array_non_last_sibling_n{n}", [["x" * n], ["short"]]))

    # C: object container, single (=> last) key, depth 3 (object > array >
    #    array). starting_column=4 (grandchild indent), trailing_comma=False
    #    => budget=80, width = 4 + (n+4) = n + 8.
    for n in range(70, 76):
        entries.append((f"object_last_key_n{n}", {"only": [["short"], ["x" * n]]}))

    # D: object container, non-last key (sorted before its sibling), same
    #    depth/width formula as C -- the outer key's own trailing_comma
    #    doesn't reach the probe (the array's inline shortcut is already
    #    skipped because it contains list items), but the extra sibling
    #    exercises comma-joining across a genuinely different document.
    for n in range(70, 76):
        entries.append(
            (f"object_non_last_key_n{n}", {"a_probe": [["short"], ["x" * n]], "z_other": 1})
        )

    # E: object-of-object-of-array, depth 4. starting_column=6, width = n+10.
    for n in range(68, 74):
        entries.append((f"nested_object_depth4_n{n}", {"outer": {"inner": [["short"], ["x" * n]]}}))

    # F: array-of-objects-of-array, depth 4. Same width formula as E, but a
    #    structurally different container mix (list branch wrapping a dict
    #    item, whose own value is the probe array).
    for n in range(68, 74):
        entries.append((f"array_of_objects_depth4_n{n}", [{"k": [["short"], ["x" * n]]}]))

    # The bug report's own reproduction, verbatim.
    entries.append(("original_bug_repro", {"outer": [["short"], ["x" * 73]]}))

    return entries


@pytest.mark.skipif(
    shutil.which("node") is None or not _PRETTIER_ESM_ENTRYPOINT.is_file(),
    reason="node or the repo's node_modules/prettier install is not available",
)
def test_prettier_json_matches_real_prettier_across_shape_table() -> None:
    table = _shape_table()
    ours = [_prettier_json(value) + "\n" for _, value in table]
    real = _real_prettier_batch([value for _, value in table])

    mismatches = [
        (label, our, expected)
        for (label, _), our, expected in zip(table, ours, real, strict=True)
        if our != expected
    ]
    details = "\n".join(
        f"--- {label} ---\nours:  {our!r}\nreal:  {expected!r}"
        for label, our, expected in mismatches
    )
    assert not mismatches, (
        f"{len(mismatches)}/{len(table)} shapes disagree with real Prettier:\n{details}"
    )
