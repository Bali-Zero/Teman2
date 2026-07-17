"""Export JSON Schema 2020-12 documents from the PR1 Pydantic models.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``schema_export.py``: ``def
export_schemas(output_dir: Path) -> None``) and §2 (the JSON Schema contract
these exports approximate), specifically the "Equivalent entrypoints" table
plus the ``rule-pack.schema.json`` example that precedes it (seven files
total).

Honest scope note (see ``test_schema_contracts.py`` for the enforcement):
Pydantic v2's ``model_json_schema()``/``models_json_schema()`` emit JSON
Schema Draft 2020-12-*compatible* output (``$defs``, discriminated unions as
``oneOf``, patterns, enums) but this is not a byte-for-byte reproduction of
spec §2's hand-authored ``contract.schema.json`` — in particular, Pydantic
does not encode a cross-field ``model_validator`` (e.g. ``Rule``'s
stage<->effect pairing, ``Decision``'s five state-conditionals) as an
``allOf``/``if``/``then`` schema construct; those live in code
(``models.py``'s ``model_validator``s and ``compiler.py``) instead of the
exported document, which is the normal, expected shape of a
Pydantic-schema-export approach (the same tradeoff spec §2 itself
acknowledges is unavoidable for cheap single-object conditionals).

PR1 hardening round (Codex finding 1, part of the FX-1 contract-completeness
fix): this module now exports **all seven** spec §2 entrypoints —
``rule-pack``, ``rule``, ``visa-product-version``, ``applicant-facts``,
``decision``, ``price-quote``, ``source-record`` — plus a ``contract``
document that holds every model's ``$defs`` in one place (each entrypoint
``$ref``s into it), mirroring spec §2's own two-tier
``contract.schema.json`` + per-entrypoint-``$ref`` structure. The previous
PR1 draft exported only four of these (missing three models entirely) and
additionally exported a non-spec ``condition.schema.json`` "bonus" entrypoint
— kept below (see ``_BONUS_CONDITION_FILENAME``) since it is still useful
for a standalone ``Condition`` consumer, but no longer conflated with the
seven official ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter
from pydantic.json_schema import models_json_schema

from backend.services.visa_engine.ast import Condition
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
    PriceQuote,
    Rule,
    RulePack,
    SourceRecord,
    VisaProductVersion,
)

#: The seven spec §2 "Equivalent entrypoints" models, keyed by their exported
#: filename (matching spec §2's table + its preceding ``rule-pack.schema.json``
#: example verbatim).
_ENTRYPOINT_MODELS: dict[str, type[BaseModel]] = {
    "rule-pack.schema.json": RulePack,
    "rule.schema.json": Rule,
    "visa-product-version.schema.json": VisaProductVersion,
    "applicant-facts.schema.json": ApplicantFacts,
    "decision.schema.json": Decision,
    "price-quote.schema.json": PriceQuote,
    "source-record.schema.json": SourceRecord,
}

#: Non-spec extra this package also finds useful to export standalone
#: (``Condition`` is a ``TypeAdapter`` target, not a ``BaseModel`` — it's a
#: bare discriminated-union type alias — handled separately in
#: ``build_schemas`` below since it cannot join ``models_json_schema``'s
#: shared-``$defs`` document the way a ``BaseModel`` can).
_BONUS_CONDITION_FILENAME = "condition.schema.json"

_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_ID_BASE = "https://schemas.balizero.com/visa-engine/"


def build_schemas() -> dict[str, dict[str, Any]]:
    """Return ``{filename: schema_dict}`` for the ``contract.schema.json``
    document plus every entrypoint (the seven spec-mandated ones and the one
    bonus ``Condition`` export), without touching the filesystem — the pure
    function ``export_schemas`` and the test suite both build on this.
    """
    key_map, contract_defs = models_json_schema(
        [(model, "validation") for model in _ENTRYPOINT_MODELS.values()],
        ref_template="#/$defs/{model}",
    )

    schemas: dict[str, dict[str, Any]] = {}
    schemas["contract.schema.json"] = _with_envelope(dict(contract_defs), "contract.schema.json")

    for filename, model in _ENTRYPOINT_MODELS.items():
        def_ref = key_map[(model, "validation")]
        ref_name = def_ref["$ref"].rsplit("/", 1)[-1]
        entrypoint_schema = {"$ref": f"contract.schema.json#/$defs/{ref_name}"}
        schemas[filename] = _with_envelope(entrypoint_schema, filename)

    condition_schema = TypeAdapter(Condition).json_schema()
    schemas[_BONUS_CONDITION_FILENAME] = _with_envelope(condition_schema, _BONUS_CONDITION_FILENAME)

    return schemas


def _with_envelope(schema: dict[str, Any], filename: str) -> dict[str, Any]:
    enveloped = dict(schema)
    enveloped["$schema"] = _SCHEMA_DIALECT
    enveloped["$id"] = f"{_ID_BASE}{filename}"
    return enveloped


def export_schemas(output_dir: Path) -> None:
    """Write every exported schema as pretty-printed JSON under
    ``output_dir`` (spec §1 ``schema_export.py`` signature, verbatim).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, schema in build_schemas().items():
        (output_dir / filename).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
