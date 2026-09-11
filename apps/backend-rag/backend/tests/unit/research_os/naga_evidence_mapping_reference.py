"""§2 of the P06 bundle, EXECUTED — the NAGA → canonical `Evidence` mapping as code.

WHY THIS MODULE EXISTS. `02-p04-adapter-mapping.md` §2 is a table: NAGA column on the left,
canonical `Evidence` path on the right, a mapping or a named gap in the middle. Until now
nothing in this repository ever RAN it. The guard module beside this one could prove that four
fields were load-bearing and that the document mentioned a name, and it could measure the width
of the gap — but a document can name all thirty-two required paths and still describe a mapping
that produces a schema-invalid object, and no test would have noticed. That is the hole this
module fills: it is the mapping, written out, so a test can execute it and validate the result
against the published schema.

WHAT IT IS NOT. It is not the production adapter. R2 implements
`services/research_os/naga_*` against this, and R1 may not write under `services/**` or
`packages/research-os-core/**`; this module is therefore the executable form of the
specification, living in the test tree on purpose. If R2's adapter and this module disagree,
one of them is wrong and the disagreement is the finding.

WHAT IT REFUSES TO DO — the same refusal as `research_os_admission_reference`. It never
defaults and never invents. Every value it produces comes from a NAGA column §2 names, from a
fixed constant §2 declares fixed, or from a minting rule §2 states explicitly (uuid5 over the
legacy serial, `naga.evidence.<slug>`, `object_hash` computed with RFC 8785). If an input the
mapping needs is absent, this module RAISES `UnmappableRecord` naming the path — it does not
fill the hole with a plausible value. Admission (`research_os_admission_reference.admit`) is
what decides whether a record should reach this mapping at all; a record that admission
EXCLUDES must never be mapped, and a record admission ADMITS must map without a raise. Those
two statements are the contract between the two modules, and a test asserts the second one.

THE THREE CONSTANTS AND THE ONE COMPUTATION, from §2's own rows:
- `contract_version` and `tenant` are `const` in the schema — fixed, no NAGA dependency;
- `object_hash` is computed over the canonical payload via `research_os.hashing.object_hash`
  (RFC 8785 + sha256), never sourced from NAGA and never hand-typed;
- `source_event_ref.object_hash` is computed the same way over the placeholder `IntelEvent`
  payload, which G6 says the adapter mints until P05's real adapter exists.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from research_os.hashing import object_hash

__all__ = [
    "NAGA_EVIDENCE_UUID_NAMESPACE",
    "UnmappableRecord",
    "map_to_evidence",
    "source_tier_for",
]

#: A fixed namespace so `evidence_id` minting is DETERMINISTIC and replay is idempotent —
#: §2's `naga_claim_evidence.id` row ("uuid5 over a fixed namespace plus the legacy serial, so
#: replay is idempotent — mirrors D5's admission-manifest idempotency requirement"). The value
#: is arbitrary but frozen: changing it re-mints every evidence id and breaks replay.
NAGA_EVIDENCE_UUID_NAMESPACE = uuid.UUID("6f2a4c1e-0000-4000-8000-000000000006")

_CONTRACT_VERSION = "research-os/v1.0.0"
_TENANT = "bali-zero"

#: §2's `credibility_score` row: "a discrete tiering function bucketing `credibility_score`
#: into tiers … not a direct copy; P04 deliberately does not carry a raw float credibility
#: score on `Evidence`." The thresholds are this module's choice and are declared here rather
#: than buried in an `if`, so a reviewer can disagree with a number instead of with code.
_TIER_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.8, "naga.tier.high"),
    (0.5, "naga.tier.medium"),
    (0.0, "naga.tier.low"),
)


class UnmappableRecord(ValueError):
    """A NAGA row lacks an input §2's mapping needs, named by its canonical path.

    Raised instead of defaulting. The mandate forbids "silent approval or classification
    defaults", and a mapping that quietly supplies `sensitivity: internal` for a record that
    never had one is exactly that failure wearing a helpful face.
    """


def source_tier_for(credibility_score: float) -> str:
    """Bucket NAGA's float credibility into a `RegisteredName` tier (§2, `credibility_score`)."""

    for threshold, tier in _TIER_THRESHOLDS:
        if credibility_score >= threshold:
            return tier
    raise UnmappableRecord(f"source_tier: credibility_score {credibility_score!r} is below 0.0")


def _require(record: Mapping[str, Any], key: str, canonical_path: str) -> Any:
    value = record.get(key)
    if value in (None, "", {}):
        raise UnmappableRecord(
            f"{canonical_path}: NAGA column {key!r} is absent or empty, and §2 names it as the "
            "only source for that path. A mapping may not default it."
        )
    return value


def _placeholder_intel_event(record: Mapping[str, Any]) -> dict[str, Any]:
    """G6's placeholder `IntelEvent` reference: a minted id plus a hash over its own payload.

    §2: "the adapter mints a placeholder `IntelEvent`-shaped wrapper per NAGA source *only if*
    P05's real adapter is not yet available, clearly tagged so it can be swapped for a real
    `IntelEvent` reference without a second migration." The tag is the payload's
    `placeholder_for` field; the hash is computed, never typed.
    """

    ref = record.get("source_event_ref") or {}
    event_id = ref.get("event_id")
    if not event_id:
        raise UnmappableRecord(
            "source_event_ref.event_id: no IntelEvent identity on this record (§2 G6). A legacy "
            "row has none, which is why admission rule 5 excludes it with "
            "intel_event_identity_missing rather than inventing one here."
        )
    stored_hash = ref.get("object_hash")
    if stored_hash:
        return {"event_id": str(event_id), "object_hash": str(stored_hash)}
    payload = {
        "contract_version": _CONTRACT_VERSION,
        "tenant": _TENANT,
        "event_id": str(event_id),
        "placeholder_for": "p05.intel_event",
        "document_id": str(_require(record, "document_id", "document_id")),
    }
    return {"event_id": str(event_id), "object_hash": object_hash(payload)}


def map_to_evidence(
    record: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    recorded_at: str,
    extractor: str = "com.balizero.naga_adapter",
    extractor_version: str = "1.0.0",
) -> dict[str, Any]:
    """Execute §2's documented mapping over one NAGA-shaped row.

    `record` and `source` are the SAME pair `research_os_admission_reference.admit` consumes —
    one legacy shape, two consumers, so a record cannot be admissible under one shape and
    mappable under another.

    `recorded_at` is passed in rather than read from a clock: §2's `times.recorded_at` row says
    it is "the wall-clock instant the *adapter* writes the canonical Evidence object — **never**
    copied from `naga_claim_evidence.created_at`". A test needs it deterministic, and a real
    adapter supplies its own now; both are served by making it an argument with no default.
    """

    document_id = str(_require(record, "document_id", "document_id"))
    span = record.get("source_span") or {}
    locator = span.get("locator")
    quote_hash = span.get("quote_hash")
    if not locator or not quote_hash:
        raise UnmappableRecord(
            "source_span.locator/source_span.quote_hash: §2 G2 — a `source_span_hint` string is "
            "not a locator plus a quote hash, and a hash cannot be synthesized from a hint."
        )

    content_hash = str(_require(record, "document_content_hash", "document_content_hash"))
    serial = _require(record, "legacy_evidence_serial_id", "evidence_id")
    evidence_id = uuid.uuid5(NAGA_EVIDENCE_UUID_NAMESPACE, f"naga_claim_evidence:{serial}")

    family_id = record.get("evidence_family_id") or f"naga.evidence.{str(serial).lower()}"

    classification = record.get("classification") or {}
    retention = record.get("retention") or {}
    review = record.get("review") or {}
    legal_hold = retention.get("legal_hold")
    if legal_hold is None:
        raise UnmappableRecord(
            "retention.legal_hold: required alongside retention_class, and no NAGA column "
            "carries it — an explicit policy value is required, not a default False."
        )

    payload: dict[str, Any] = {
        "evidence_id": str(evidence_id),
        "evidence_family_id": str(family_id),
        "contract_version": _CONTRACT_VERSION,
        "tenant": _TENANT,
        "source_event_ref": _placeholder_intel_event(record),
        "document_id": document_id,
        "document_version_id": str(
            _require(record, "document_version_id", "document_version_id")
        ),
        "document_content_hash": content_hash,
        "source_span": {"locator": str(locator), "quote_hash": str(quote_hash)},
        "source_tier": source_tier_for(
            float(_require(record, "credibility_score", "source_tier"))
        ),
        "stance": str(_require(record, "relation", "stance")),
        "times": {
            "observed_at": str(_require(record, "fetched_at", "times.observed_at")),
            "recorded_at": recorded_at,
        },
        "provenance": {
            "extractor": extractor,
            "extractor_version": extractor_version,
            "run_id": str(_require(record, "naga_session_id", "provenance.run_id")),
            "extraction_input_hash": object_hash(
                {
                    "contract_version": _CONTRACT_VERSION,
                    "document_id": document_id,
                    "document_content_hash": content_hash,
                    "body_length": len(str(source.get("body") or "")),
                }
            ),
        },
        "classification": {
            "risk_class": str(_require(classification, "risk_class", "classification.risk_class")),
            "sensitivity": str(
                _require(classification, "sensitivity", "classification.sensitivity")
            ),
            "rights": str(_require(classification, "rights", "classification.rights")),
        },
        "review_state": str(_require(review, "state", "review_state")),
        "retention": {
            "retention_class": str(
                _require(retention, "retention_class", "retention.retention_class")
            ),
            "legal_hold": bool(legal_hold),
        },
        "extensions": {
            "com.balizero.research-os.naga": {
                "extension_version": "1.0.0",
                "payload": {"legacy_evidence_serial_id": int(serial)},
            }
        },
    }
    payload["object_hash"] = object_hash(payload)
    return payload
