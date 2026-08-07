"""HMAC authentication for trace-bound final public decisions."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import cast

from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.crypto import FactsFingerprintKey
from backend.services.visa_engine.models import Decision, Fingerprint
from backend.services.visa_engine.trace import EvaluationTrace


def _canonical(payload: Mapping[str, object]) -> bytes:
    """Serialize an already JSON-safe decision mapping with RFC 8785 JCS."""

    return canonicalize_json(cast(Mapping[str, JsonValue], payload))


def _integrity_digest(
    core: Mapping[str, object],
    *,
    trace_sha256: str,
    key: FactsFingerprintKey,
) -> str:
    sealed_payload = {
        **core,
        "trace_sha256": trace_sha256,
        "decision_integrity": None,
    }
    return hmac.new(
        key.secret,
        b"visa-oracle-decision-integrity-v1\x00" + _canonical(sealed_payload),
        hashlib.sha256,
    ).hexdigest()


def seal_decision(
    decision: Decision,
    *,
    key: FactsFingerprintKey,
    trace: EvaluationTrace | None = None,
) -> Decision:
    """Authenticate the exact final envelope and its evaluator trace hash.

    Call only after every monotone adapter (source hold, disclosures, pricing)
    has finished. ``trace_sha256`` must already come from the evaluator's
    same-pass ``EvaluationTrace``; this function never reconstructs or
    replaces it from the public decision. When the internal trace is
    available, pass it so a mismatch fails closed before minting the HMAC.
    """

    trace_sha256 = decision.trace_sha256
    if trace_sha256 is None:
        raise ValueError("cannot seal a decision without an evaluation trace")
    if trace is not None and not trace.matches(trace_sha256):
        raise ValueError("decision trace_sha256 does not match the evaluation trace")
    core = decision.model_dump(
        mode="json",
        exclude={"trace_sha256", "decision_integrity"},
    )
    sealed_payload = {
        **core,
        "trace_sha256": trace_sha256,
        "decision_integrity": None,
    }
    integrity_digest = _integrity_digest(core, trace_sha256=trace_sha256, key=key)
    sealed_payload["decision_integrity"] = Fingerprint(
        algorithm="HMAC-SHA256",
        key_id=key.kid,
        digest=integrity_digest,
    ).model_dump(mode="json")
    return Decision.model_validate(sealed_payload)


def verify_decision_seal(
    decision: Decision,
    *,
    key: FactsFingerprintKey,
    trace: EvaluationTrace | None = None,
) -> bool:
    """Fail closed unless HMAC authenticates the envelope and trace digest."""

    integrity = decision.decision_integrity
    trace_sha256 = decision.trace_sha256
    if integrity is None or trace_sha256 is None or integrity.key_id != key.kid:
        return False
    if trace is not None and not trace.matches(trace_sha256):
        return False
    core = decision.model_dump(
        mode="json",
        exclude={"trace_sha256", "decision_integrity"},
    )
    expected_integrity = _integrity_digest(
        core,
        trace_sha256=trace_sha256,
        key=key,
    )
    return hmac.compare_digest(integrity.digest, expected_integrity)


__all__ = ["seal_decision", "verify_decision_seal"]
