"""Export JSON Schema 2020-12 documents from the PR1 Pydantic models.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``schema_export.py``: ``def
export_schemas(output_dir: Path) -> None``) and §2 (the JSON Schema contract
this module exports), specifically the "Equivalent entrypoints" table plus
the ``rule-pack.schema.json`` example that precedes it (seven files total).

**The export IS the contract** (round 3, Codex round-2 re-review finding 2
residue — this replaces an earlier "approximate" disclaimer that was too
weak): Pydantic v2's ``model_json_schema()``/``models_json_schema()`` emit
JSON Schema Draft 2020-12 output (``$defs``, discriminated unions, patterns,
enums) faithfully for every *single-object* constraint, but do not
automatically encode a cross-field ``model_validator`` (e.g. ``Rule``'s
scope<->product_version_ids and stage<->effect pairings, ``RulePackPayload``'s
sequence<->previous_payload_sha256 chain, ``PriceQuote``'s status<->amount
conditional, ``Decision``'s five state-conditionals) as an ``allOf``/``if``/
``then`` schema construct on their own — so ``build_schemas`` below
hand-injects all four of spec §2's single-object ``allOf`` blocks
(``Rule``, ``RulePackPayload``, ``PriceQuote``, ``Decision`` — verified by
grepping the spec document for every ``"allOf"`` occurrence: exactly these
four, transcribed verbatim from spec §2 below, no more and no fewer) into
the generated ``$defs`` post-generation. ``test_schema_contracts.py`` proves
each injected block actually gates: a GLOBAL rule with a non-null
``product_version_ids``, or a HARD_FILTER rule with a SUPPORT effect, now
FAILS jsonschema validation against this export, matching what Pydantic
already enforces at construction time via ``models.py``'s own
``model_validator``s.

Round 4 correction (Codex round-3 verify HIGH residual): the ``Rule``
scope<->product_version_ids block's GLOBAL branch is NOT transcribed
verbatim from spec §2 — spec's literal text forbids the property's
PRESENCE (``"not": {"required": [...]}}``), but ``Rule.product_version_ids``
always serializes the *key* (with value ``null``) via
``model_dump(mode="json")`` (Pydantic dumps every declared field regardless
of whether it equals its default), so a model-valid GLOBAL rule's own
canonical serialization failed spec's literal ``allOf`` — the export
rejected its own valid instance. Fixed to require the property, if present,
to be ``null`` (present-and-null allowed, non-null forbidden — see the
inline comment at the injection site for the full reasoning). This is a
correction, not a relaxation: it still rejects the exact case the block
exists to catch (a non-null ``product_version_ids`` on a GLOBAL rule), it
just also accepts the shape Pydantic actually produces for the valid case.

One deliberate, documented exception: ``RulePack``'s own header/environment
consistency check ("protected.environment must equal payload.environment")
has **no ``allOf`` in spec §2 at all** — confirmed by reading the spec's
``RulePack`` ``$def`` directly (it has no ``allOf`` key whatsoever). Spec's
own "Compiler-only invariants, because JSON Schema cannot express them
safely" list (§2, the section right after the "Equivalent entrypoints"
table) places this exact check there instead: it is a same-payload
cross-*object* comparison (``protected.X == payload.Y``, two different
top-level properties compared to each other) that JSON Schema's ``if``/
``then`` machinery — which conditions on ONE property's value to constrain
OTHERS, not compare two arbitrary properties to each other — cannot express.
Pydantic enforces it anyway (``RulePack._check_header_environment``,
``models.py``) because ``model_validator`` is a general Python function, not
bound by JSON Schema's expressiveness; this export honestly leaves it
uninjected rather than force an artificial ``anyOf`` workaround spec itself
chose not to write.

PR1 hardening round 2 (Codex finding 1, part of the FX-1 contract-completeness
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

#: Inline primitive shapes used inside the ``allOf`` blocks below, in place
#: of spec §2's own ``{"$ref": "#/$defs/Uuid"}``/``{"$ref":
#: "#/$defs/Sha256Hex"}`` — spec's hand-authored ``contract.schema.json``
#: declares ``Uuid``/``Sha256Hex`` as named top-level ``$defs``, but
#: Pydantic's generator renders bare ``Annotated[str, Field(pattern=...)]``
#: type aliases (``models.Sha256Hex``) and well-known stdlib types
#: (``uuid.UUID``) INLINE at every usage site instead of emitting a shared
#: named ``$def`` for them (confirmed empirically: neither name appears in
#: ``models_json_schema``'s output ``$defs``) — a ``$ref`` to either would be
#: dangling in this export. Using the identical inline shape Pydantic already
#: renders elsewhere in the same document (e.g. ``Rule.product_version_ids``'
#: items) keeps these blocks self-consistent with the rest of the export.
_UUID_INLINE: dict[str, Any] = {"type": "string", "format": "uuid"}
_SHA256_HEX_INLINE: dict[str, Any] = {"type": "string", "pattern": r"^[0-9a-f]{64}$"}

#: Spec §2's four single-object ``allOf`` conditionals, transcribed verbatim
#: (research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
#: concretization.md §2 — Rule ~L1332, RulePackPayload ~L1790, PriceQuote
#: ~L1911, Decision ~L2136) with ONE deliberate, documented correction (round
#: 4: ``Rule``'s GLOBAL-scope branch — see the inline comment at that entry),
#: keyed by the ``$defs`` name each attaches to. The four-``$defs`` inventory
#: is complete — `grep -n '"allOf"'` over the whole spec document returns
#: exactly these four matches, no more. ``RulePack`` is
#: deliberately absent: see module docstring's "one deliberate, documented
#: exception" paragraph.
_ALLOF_INJECTIONS: dict[str, list[dict[str, Any]]] = {
    "Rule": [
        {
            # Round 4 (Codex round-3 verify HIGH residual): spec §2's own
            # literal text is `"then": {"not": {"required":
            # ["product_version_ids"]}}` — forbidding the property's
            # PRESENCE. But `Rule.product_version_ids: tuple[...] | None =
            # Field(default=None, ...)` always serializes the KEY (with
            # value `null`) via `model_dump(mode="json")`, since Pydantic
            # dumps every declared field regardless of whether it equals its
            # default — a GLOBAL rule's own canonical serialization then
            # fails "not required" (the key IS present, just null), i.e. a
            # model-valid instance fails its own exported contract. Fixed to
            # require the property, IF PRESENT, to be null — matching
            # model_dump's output exactly (present-and-null allowed,
            # non-null forbidden; ABSENT is also still fine, since
            # "properties" is a no-op when the key is missing).
            "if": {"properties": {"scope": {"const": "GLOBAL"}}},
            "then": {"properties": {"product_version_ids": {"type": "null"}}},
            "else": {"required": ["product_version_ids"]},
        },
        {
            "if": {"properties": {"stage": {"const": "HARD_FILTER"}}},
            "then": {"properties": {"effect": {"properties": {"type": {"const": "EXCLUDE"}}}}},
        },
        {
            "if": {"properties": {"stage": {"const": "ELIGIBILITY"}}},
            "then": {"properties": {"effect": {"properties": {"type": {"const": "SUPPORT"}}}}},
        },
        {
            "if": {"properties": {"stage": {"const": "HUMAN_REVIEW"}}},
            "then": {
                "properties": {"effect": {"properties": {"type": {"const": "REQUIRE_REVIEW"}}}}
            },
        },
        {
            "if": {"properties": {"stage": {"const": "RANKING"}}},
            "then": {"properties": {"effect": {"properties": {"type": {"const": "ADD_SCORE"}}}}},
        },
    ],
    "RulePackPayload": [
        {
            "if": {"properties": {"sequence": {"const": 1}}},
            "then": {"properties": {"previous_payload_sha256": {"type": "null"}}},
            "else": {"properties": {"previous_payload_sha256": _SHA256_HEX_INLINE}},
        },
    ],
    "PriceQuote": [
        {
            "if": {"properties": {"status": {"const": "AVAILABLE"}}},
            "then": {
                "properties": {
                    "amount": {"type": "integer", "minimum": 0},
                    "catalog_version": {"type": "string"},
                    "catalog_sha256": _SHA256_HEX_INLINE,
                    "row_sha256": _SHA256_HEX_INLINE,
                }
            },
            "else": {"properties": {"amount": {"type": "null"}}},
        },
    ],
    "Decision": [
        {
            "if": {"properties": {"state": {"const": "SUPPORTED_CANDIDATES"}}},
            "then": {
                "properties": {
                    "decision_id": _UUID_INLINE,
                    "public_id": {"type": "string", "pattern": "^[a-z0-9]{16,20}$"},
                    "rule_pack": {"$ref": "#/$defs/RulePackRef"},
                    "candidates": {"minItems": 1},
                    "missing_facts": {"maxItems": 0},
                    "review_reasons": {"maxItems": 0},
                    "no_path_reasons": {"maxItems": 0},
                    "outage": {"type": "null"},
                }
            },
            "else": {"properties": {"candidates": {"maxItems": 0}, "quotes": {"maxItems": 0}}},
        },
        {
            "if": {"properties": {"state": {"const": "NEEDS_INPUT"}}},
            "then": {
                "properties": {
                    "decision_id": _UUID_INLINE,
                    "public_id": {"type": "string", "pattern": "^[a-z0-9]{16,20}$"},
                    "rule_pack": {"$ref": "#/$defs/RulePackRef"},
                    "missing_facts": {"minItems": 1},
                    "review_reasons": {"maxItems": 0},
                    "no_path_reasons": {"maxItems": 0},
                    "outage": {"type": "null"},
                }
            },
        },
        {
            "if": {"properties": {"state": {"const": "HUMAN_REVIEW_REQUIRED"}}},
            "then": {
                "properties": {
                    "decision_id": _UUID_INLINE,
                    "public_id": {"type": "string", "pattern": "^[a-z0-9]{16,20}$"},
                    "rule_pack": {"$ref": "#/$defs/RulePackRef"},
                    "missing_facts": {"maxItems": 0},
                    "review_reasons": {"minItems": 1},
                    "no_path_reasons": {"maxItems": 0},
                    "outage": {"type": "null"},
                }
            },
        },
        {
            "if": {"properties": {"state": {"const": "NO_SUPPORTED_PATH"}}},
            "then": {
                "properties": {
                    "decision_id": _UUID_INLINE,
                    "public_id": {"type": "string", "pattern": "^[a-z0-9]{16,20}$"},
                    "rule_pack": {"$ref": "#/$defs/RulePackRef"},
                    "missing_facts": {"maxItems": 0},
                    "review_reasons": {"maxItems": 0},
                    "no_path_reasons": {"minItems": 1},
                    "outage": {"type": "null"},
                }
            },
        },
        {
            "if": {"properties": {"state": {"const": "TEMPORARILY_UNAVAILABLE"}}},
            "then": {
                "properties": {
                    "candidates": {"maxItems": 0},
                    "missing_facts": {"maxItems": 0},
                    "review_reasons": {"maxItems": 0},
                    "no_path_reasons": {"maxItems": 0},
                    "quotes": {"maxItems": 0},
                    "outage": {"type": "object"},
                }
            },
        },
    ],
}


def _inject_allof_conditionals(contract_defs: dict[str, Any]) -> None:
    """Mutate ``contract_defs`` in place, attaching each entry of
    ``_ALLOF_INJECTIONS`` to its named ``$def`` — see module docstring for
    why Pydantic's generator cannot produce these on its own and
    ``_UUID_INLINE``/``_SHA256_HEX_INLINE`` for why the spec's own ``$ref``
    forms had to be substituted with inline shapes.

    ``contract_defs`` is ``models_json_schema``'s raw return shape: a
    single-key dict ``{"$defs": {name: schema, ...}}`` — NOT the flat
    ``{name: schema, ...}`` mapping the name might suggest.
    """
    defs = contract_defs["$defs"]
    for def_name, allof_blocks in _ALLOF_INJECTIONS.items():
        if def_name not in defs:
            raise KeyError(
                f"expected $defs/{def_name} in the generated contract — "
                "a model rename/removal broke the allOf injection target"
            )
        defs[def_name]["allOf"] = allof_blocks


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
    contract_defs = dict(contract_defs)
    _inject_allof_conditionals(contract_defs)

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
