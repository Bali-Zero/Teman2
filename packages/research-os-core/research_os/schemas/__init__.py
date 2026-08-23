"""Deterministic Draft 2020-12 JSON Schema artifact generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel

from research_os.models.content_object import ContentObject
from research_os.models.media_manifest import MediaManifest
from research_os.models.revocation_receipt import RevocationReceipt
from research_os.models.successor_edge import ObjectSuccessorEdge

SCHEMA_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "content_object": ContentObject,
    "media_manifest": MediaManifest,
    "object_successor_edge": ObjectSuccessorEdge,
    "revocation_receipt": RevocationReceipt,
}


def _prettier_json(value: Any, *, indent: int = 0, starting_column: int = 0) -> str:
    """Render generated schemas with Prettier's stable JSON layout."""

    if isinstance(value, dict):
        if not value:
            return "{}"
        child_indent = indent + 2
        lines = []
        for key in sorted(value):
            key_text = json.dumps(key, ensure_ascii=False)
            prefix = f"{' ' * child_indent}{key_text}: "
            child = _prettier_json(
                value[key],
                indent=child_indent,
                starting_column=len(prefix),
            )
            lines.append(f"{prefix}{child}")
        return "{\n" + ",\n".join(lines) + f"\n{' ' * indent}}}"

    if isinstance(value, list):
        if not value:
            return "[]"
        compact = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        # "+ 1" reserves a column for the trailing "," this join adds when the
        # value is not the parent's last key (`",\n".join(lines)` above) --
        # without it, a compacted array landing at EXACTLY column 80 passes
        # this check but renders an 81-column line, which real Prettier
        # (this function's own documented contract: "Prettier's stable JSON
        # layout") would have kept expanded. Caught by
        # `PlatformSpec.required` (research_os/models/media_manifest.py,
        # section 10) landing at exactly column 80 before this fix; verified
        # byte-identical regeneration of every OTHER checked-in schema
        # (object_successor_edge, revocation_receipt) after this change --
        # more conservative can only expand a boundary case, never
        # re-compact one.
        if all(not isinstance(item, (dict, list)) for item in value) and (
            starting_column + len(compact) + 1 <= 80
        ):
            return compact
        child_indent = indent + 2
        children = [
            f"{' ' * child_indent}{_prettier_json(item, indent=child_indent)}" for item in value
        ]
        return "[\n" + ",\n".join(children) + f"\n{' ' * indent}]"

    return json.dumps(value, ensure_ascii=False)


def schema_bytes(model: type[BaseModel]) -> bytes:
    schema: dict[str, Any] = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return (_prettier_json(schema) + "\n").encode("utf-8")


def write_schema_artifacts() -> tuple[Path, ...]:
    written: list[Path] = []
    for contract_kind, model in SCHEMA_MODELS.items():
        path = SCHEMA_DIRECTORY / f"{contract_kind}.schema.json"
        path.write_bytes(schema_bytes(model))
        written.append(path)
    return tuple(written)


def checked_in_schemas_match() -> tuple[str, ...]:
    mismatches: list[str] = []
    for contract_kind, model in SCHEMA_MODELS.items():
        path = SCHEMA_DIRECTORY / f"{contract_kind}.schema.json"
        if not path.is_file() or path.read_bytes() != schema_bytes(model):
            mismatches.append(contract_kind)
    return tuple(mismatches)


def validate_schema_artifacts() -> tuple[str, ...]:
    invalid: list[str] = []
    for contract_kind in SCHEMA_MODELS:
        path = SCHEMA_DIRECTORY / f"{contract_kind}.schema.json"
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (OSError, ValueError, TypeError):
            invalid.append(contract_kind)
    return tuple(invalid)
