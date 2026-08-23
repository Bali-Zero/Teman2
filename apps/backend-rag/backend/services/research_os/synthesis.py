"""Deterministic helpers shared by every adapter: hash-object construction,
timestamp parsing, and clearly-marked SYNTHESIZED_UNBACKED reference
generation.

Two mandatory canonical refs (`ActionItem.decision_packet_ref`,
`ActionItem`/`ActionIntent.requested_action_spec_ref`) have no legacy source
in Magazine's `ops_intents` -- confirmed by reading `decision_packet.py` and
`requested_action_spec.py` this session: both are non-optional fields with
no default, and `RequestedActionSpec` itself requires a real
`DecisionPacketRef` (which in turn requires a real `WorkflowRunRef`).
Building a genuinely valid, independently-materialized `DecisionPacket` (and
the `WorkflowRun` under it) purely to backfill a pointer would fabricate an
upstream decision-gate provenance Magazine's ops-action pipeline never had --
Magazine's own POST body is consumed directly into `ops_intents`, with no
decision-packet gate at any point (matrix §1.0/§1.1). That is a materially
worse kind of adapter lie than an honestly-disclosed dangling pointer, so
this module does the latter: it synthesizes a deterministic, reproducible
`{id, object_hash}` pair and every adapter that uses one records a
SYNTHESIZED_UNBACKED loss entry making clear the reference does not resolve
to any materialized object. This is a deliberate, disclosed judgment call,
not a silent workaround -- flagged to the conductor as a ruling this
packet's matrix under-scoped (it recorded these refs as merely "no legacy
source," not as constructor-blocking).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from research_os.hashing import object_hash
from research_os.primitives import ExtensionValue

from backend.services.research_os import _core_path  # noqa: F401  (sys.path bootstrap)

# Adapter-owned namespace -- NOT part of the research-os/v1.0.0 wire contract,
# and never shared with any real object-minting path anywhere else in the
# repo (a cross-family adversarial review flagged that a shared namespace
# would make a synthetic id semantically indistinguishable from a future
# real one minted the same way -- this string exists ONLY here).
_ADAPTER_NAMESPACE = uuid5(NAMESPACE_URL, "https://balizero.com/research-os/adapters/v1")

# Reverse-DNS extension namespace (required shape, primitives.py's
# `_REVERSE_DNS_RE`) carrying a MACHINE-CHECKABLE flag for which ref fields
# on a canonical object are SYNTHESIZED_UNBACKED. A loss report is prose a
# human reads; this is the same fact a downstream consumer can branch on
# without reading docs first -- the fix a cross-family adversarial review
# (Kimi K3) asked for when it argued disclosure-in-prose alone is not enough.
UNBACKED_REFS_EXTENSION_NAMESPACE = "com.balizero.research-os-adapters"


def unbacked_refs_extension(*field_names: str) -> dict[str, ExtensionValue]:
    """Build the `extensions` payload naming which of this object's own ref
    fields are synthesized/unbacked (see module docstring). Safe against the
    frozen core vocabulary jail (`validate_extensions`): `unbacked_refs` is
    not in `V1_RESERVED_EXTENSION_FIELD_NAMES`, verified this session.
    """

    return {
        UNBACKED_REFS_EXTENSION_NAMESPACE: ExtensionValue(
            extension_version="1.0.0", payload={"unbacked_refs": list(field_names)}
        )
    }


def synthetic_uuid(*parts: str) -> UUID:
    """A deterministic UUID for one adapter-owned synthetic identity. Same
    `parts` always yields the same UUID -- required so re-running an
    adapter on the same legacy row is idempotent.
    """

    return uuid5(_ADAPTER_NAMESPACE, ":".join(parts))


def unbacked_object_hash(*parts: str) -> str:
    """A deterministic, syntactically-valid sha256-hex placeholder for a
    reference that does not resolve to any independently materialized
    canonical object. Never pass this to `research_os.hashing.object_hash`'s
    result path -- it is a plain content hash of the adapter's own
    disclosure string, not a canonical object_hash.
    """

    return hashlib.sha256(f"unbacked:{':'.join(parts)}".encode()).hexdigest()


def legacy_content_hash(*parts: str) -> str:
    """A reproducible sha256-hex reference to exact legacy row content (e.g.
    a `params_json` blob) -- distinct from `unbacked_object_hash` only in
    intent: this DOES point at something real (the legacy row's own
    content), it just isn't a canonical-object hash.
    """

    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def parse_legacy_timestamp(value: str) -> datetime:
    """Magazine's D1 columns are ISO-8601 text. Canonical `UtcDateTime`
    requires a tz-aware UTC value -- naive legacy strings are assumed UTC
    (Magazine has no other timezone convention anywhere in its schema).
    """

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_with_object_hash(model_cls: type[BaseModel], **fields: object) -> BaseModel:
    """Construct a canonical `FrozenCoreModel` instance whose `object_hash`
    is computed from its own content, in two passes:

    1. `model_cls.model_construct(...)` builds a draft WITHOUT running any
       validator (so a placeholder `object_hash` value cannot fail the
       self-consistency check that a real constructor call would raise).
    2. `research_os.hashing.object_hash(draft)` computes the real hash --
       safe even though the placeholder is nonsense, because that function
       drops the `object_hash` key from the hashable payload before hashing
       (`HASH_OMISSION_FIELDS`), so the placeholder's value never enters the
       computation.

    The real constructor is then called with every field plus the computed
    hash, so the returned instance is fully validated like any other.
    """

    draft = model_cls.model_construct(object_hash="0" * 64, **fields)
    computed_hash = object_hash(draft)
    return model_cls(object_hash=computed_hash, **fields)
