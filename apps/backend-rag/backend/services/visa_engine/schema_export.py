"""Export JSON Schema 2020-12 documents from the PR1 Pydantic models.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``schema_export.py``: ``def
export_schemas(output_dir: Path) -> None``) and §2 (the JSON Schema contract
these exports approximate).

Honest scope note (see ``test_schema_contracts.py`` for the enforcement):
Pydantic v2's ``model_json_schema()`` emits Draft 2020-12-*compatible* output
(``$defs``, ``oneOf``/discriminated unions, patterns, enums) but it is not a
byte-for-byte reproduction of spec §2's hand-authored ``contract.schema.json``
— in particular, Pydantic does not encode the ``allOf``/``if``/``then``
cross-field conditionals (e.g. Rule's stage<->effect pairing) as schema
constructs; those live in code (``models.py``'s ``model_validator``s and
``compiler.py``) instead of the exported document, which is normal for a
Pydantic-schema-export approach. What this module's test *does* assert,
per the PR1 task brief ("a pytest asserts the exported schema matches the
spec §2 contract for the key invariants"): the 5 ``DecisionState`` values,
the 16 ``ConditionOperator`` values, and the 5 ``UnknownReason`` values are
present, verbatim, in the exported schema set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from backend.services.visa_engine.ast import Condition
from backend.services.visa_engine.models import Rule, RulePack, SourceRecord

#: One entrypoint schema per spec §2 §"Equivalent entrypoints" table, scoped
#: to what PR1 actually models (``VisaProductVersion``/``ApplicantFacts``/
#: ``Decision``/``PriceQuote`` are PR2+ — see ``models.py``'s docstring).
_ENTRYPOINTS: dict[str, Any] = {
    "rule-pack.schema.json": RulePack,
    "rule.schema.json": Rule,
    "source-record.schema.json": SourceRecord,
    "condition.schema.json": TypeAdapter(Condition),
}


def build_schemas() -> dict[str, dict[str, Any]]:
    """Return ``{filename: schema_dict}`` for every PR1 entrypoint, without
    touching the filesystem — the pure function ``export_schemas`` and the
    test suite both build on this.
    """
    schemas: dict[str, dict[str, Any]] = {}
    for filename, model in _ENTRYPOINTS.items():
        if isinstance(model, TypeAdapter):
            schema = model.json_schema()
        else:
            schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://schemas.balizero.com/visa-engine/{filename}"
        schemas[filename] = schema
    return schemas


def export_schemas(output_dir: Path) -> None:
    """Write every PR1 entrypoint schema as pretty-printed JSON under
    ``output_dir`` (spec §1 ``schema_export.py`` signature, verbatim).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, schema in build_schemas().items():
        (output_dir / filename).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
