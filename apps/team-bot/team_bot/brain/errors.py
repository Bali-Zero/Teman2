"""Closed error taxonomy for the TP1 (Alibaba Model Studio) brain adapter.

Read `docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md`
FIRST — it is binding here too (directive #1 §1, team-lead brief). That spec
diagnoses one defect in `codex_exec_client.py`'s stderr classifier: *"Distinct
vocabularies do not imply mutually exclusive payloads"* — free-text scanning
let one payload match two word classes at once, let matches bridge across
unrelated log lines, and let ordinary prose (both consultancy sentences and
missed vendor wording) fool a first-match-wins regex cascade.

This module does not inherit that defect, and the reason is structural, not
diligence: **HTTP status codes are a protocol-level partition, not prose**.
A response has exactly one status code, so there is no analogue of "one
payload matches two classes" (P1) or "matches span unrelated records" (P2) to
guard against here by construction — the classifier below never scans
free text for a word class at all. What it DOES need, and provides, is P3's
"prefer machine-readable evidence to prose" (classify on `(http_status,
error.type, error.code)` — the OpenAI-compatible JSON error envelope — never
on `error.message` prose), P4's confidence tagging, and P5's "unknown stays
unknown" (an unrecognised status/code falls to a generic bucket, never a
guessed specific one).

## Evidence ledger (P3/P4, made explicit per the team-lead's report requirement)

Live-probed against the real TP1 door 2026-08-25 (base URL below, key from
`~/.qwen/settings.json`, scrubbed before any log line) — three real shapes
observed and hard-coded as OBSERVED_TP1_LIVE regression fixtures in
`tests/brain/test_errors.py`:

    401  {"error":{"message":"Invalid API-key provided. ...",
                    "id":"...","type":"invalid_request_error","code":"invalid_api_key"}}
    404  {"error":{"message":"Model not exist.",
                    "id":"...","type":"invalid_request_error","code":"model_not_found"}}
    200  ordinary chat.completion + tool_calls (not an error; see tp1_client.py)

NOT observed against TP1 specifically, classified by HTTP/OpenAI-envelope
PROTOCOL semantics instead (every OpenAI-compatible vendor uses these
status codes for these purposes; this is the same class of inference the
`codex_exec_client.py` SPEC calls "protocol-inferred" and marks lower
confidence than a vendor-observed shape, never the same fact):

    429  rate limit / quota — no TP1 429 has been observed in this session
         (see `depletion_probe.py` docstring: a 25-request concurrent burst
         on 2026-08-25 did not trigger one — the RPM ceiling, if any, is
         above 25 concurrent). Directive #1 §4 (Kimi refuter) still warns
         "Default RPM caps are low" as a design input, so this class is
         wired and tested, just never marked OBSERVED_TP1_LIVE.
    5xx  upstream/gateway failure — the door sits behind `server: istio-envoy`
         (observed in response headers); an Envoy-shaped non-JSON gateway
         error page has never been seen either. A non-JSON body under any
         status degrades gracefully to a generic bucket (P5) rather than
         guessing Envoy's exact wording.

Never fabricated as a fixture: a TP1-specific 429/5xx JSON body. Per the
SPEC's "Arming condition", any caller-visible distinction that would depend
on a TP1 quota-body shape nobody has seen stays UNVERIFIED_GUESS and low
confidence until a real one is recorded here.

Author: Claude (lane B4-tp1 — team-bot TP1 brain adapter).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "BrainErrorClass",
    "BrainErrorVerdict",
    "EvidenceProvenance",
    "MatchConfidence",
    "classify_response",
    "verdict_for_network_error",
    "verdict_for_output_invalid",
    "verdict_for_timeout",
]

_MAX_DETAIL_CHARS = 300


class BrainErrorClass(StrEnum):
    """Closed vocabulary. Adding a member requires updating this module's
    evidence ledger, not just the enum (P6: every class needs guilt AND
    innocence tests in `test_errors.py`)."""

    AUTH_DEAD = "AUTH_DEAD"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_REQUEST = "INVALID_REQUEST"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    UNKNOWN = "UNKNOWN"


class MatchConfidence(StrEnum):
    """HIGH — driven by a numeric HTTP status code and/or a structured JSON
    `error.code`/`error.type` field: both are machine-readable by
    definition, so a bare, well-formed status code alone is already HIGH
    (unlike stderr text, an HTTP status line is never "prose"). LOW — the
    JSON envelope was missing/unparseable and classification fell back to
    the status code's coarse 4xx/5xx range with no corroborating field, or
    the status code itself was unrecognised."""

    HIGH = "HIGH"
    LOW = "LOW"


class EvidenceProvenance(StrEnum):
    """Whether the EXACT shape that fired has actually been seen coming
    back from TP1 (see the evidence ledger above), or is inferred from
    HTTP/OpenAI-envelope protocol convention, or is an unverified guess.
    Never conflate the second with the first — that conflation is exactly
    what the SPEC calls out as unsound in the codex client's precedent."""

    OBSERVED_TP1_LIVE = "observed_tp1_live_2026_08_25"
    PROTOCOL_INFERRED = "protocol_inferred"
    UNVERIFIED_GUESS = "unverified_guess"


@dataclass(frozen=True, slots=True)
class BrainErrorVerdict:
    """The result of classifying one non-2xx TP1 response (or a client-side
    transport failure that never got a response at all).

    `detail` is a short, log-safe string: the vendor's own `error.message`
    (Alibaba's generic account/request diagnostics, never user content —
    error responses are rejected BEFORE any chat content is generated) or a
    synthesized description for transport-level failures. Callers must
    never log `raw_body` itself alongside this verdict — team-lead brief:
    "Never log a token, a body, or a signature." `detail` is the sanctioned
    substitute.
    """

    error_class: BrainErrorClass
    confidence: MatchConfidence
    provenance: EvidenceProvenance
    http_status: int | None
    vendor_type: str | None
    vendor_code: str | None
    detail: str


def _truncate(text: str) -> str:
    text = text.strip()
    return text if len(text) <= _MAX_DETAIL_CHARS else text[:_MAX_DETAIL_CHARS] + "…"


def _parse_openai_error_envelope(
    body_text: str,
) -> tuple[str | None, str | None, str | None] | None:
    """Best-effort parse of the OpenAI-compatible `{"error": {...}}` shape.
    Returns `None` (never raises) when the body is empty, not JSON, not an
    object, or has no `error` object — every one of those degrades the
    caller to the generic/protocol-only branch (P5), never a guess."""
    if not body_text:
        return None
    try:
        parsed = json.loads(body_text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    error = parsed.get("error")
    if not isinstance(error, dict):
        return None
    vtype = error.get("type")
    vcode = error.get("code")
    vmsg = error.get("message")
    return (
        vtype if isinstance(vtype, str) else None,
        vcode if isinstance(vcode, str) else None,
        vmsg if isinstance(vmsg, str) else None,
    )


def classify_response(status: int, body_text: str) -> BrainErrorVerdict:
    """Classify one non-2xx HTTP response from the TP1 door.

    P7 (disjointness): status codes partition responses by construction —
    every branch below is a disjoint numeric range or an exact value, and
    the function returns on the first matching branch, so there is no
    "which class wins" question the way free-text scanning has. See
    `test_errors.py::test_every_status_maps_to_exactly_one_class` for the
    regression lock on this property (a future edit that overlaps two
    ranges — e.g. a typo'd `<=` — is exactly the "weaker test agrees with
    itself" failure mode the codex client's own history warns about, so
    that test iterates the FULL representative status range, not just each
    branch's own examples).
    """
    envelope = _parse_openai_error_envelope(body_text)
    vtype, vcode, vmsg = envelope if envelope is not None else (None, None, None)
    detail = _truncate(vmsg) if vmsg else f"HTTP {status}, no parseable error envelope"

    if status == 401:
        observed = vcode == "invalid_api_key"
        return BrainErrorVerdict(
            BrainErrorClass.AUTH_DEAD,
            MatchConfidence.HIGH,
            EvidenceProvenance.OBSERVED_TP1_LIVE
            if observed
            else EvidenceProvenance.PROTOCOL_INFERRED,
            status,
            vtype,
            vcode,
            detail,
        )

    if status == 404:
        if vcode == "model_not_found":
            return BrainErrorVerdict(
                BrainErrorClass.MODEL_NOT_FOUND,
                MatchConfidence.HIGH,
                EvidenceProvenance.OBSERVED_TP1_LIVE,
                status,
                vtype,
                vcode,
                detail,
            )
        return BrainErrorVerdict(
            BrainErrorClass.INVALID_REQUEST,
            MatchConfidence.HIGH if vtype else MatchConfidence.LOW,
            EvidenceProvenance.PROTOCOL_INFERRED,
            status,
            vtype,
            vcode,
            detail,
        )

    if status == 429:
        # Protocol-inferred, NOT vendor-observed — see evidence ledger.
        return BrainErrorVerdict(
            BrainErrorClass.RATE_LIMITED,
            MatchConfidence.HIGH,
            EvidenceProvenance.PROTOCOL_INFERRED,
            status,
            vtype,
            vcode,
            detail,
        )

    if 500 <= status < 600:
        return BrainErrorVerdict(
            BrainErrorClass.SERVER_ERROR,
            MatchConfidence.HIGH,
            EvidenceProvenance.PROTOCOL_INFERRED,
            status,
            vtype,
            vcode,
            detail,
        )

    if 400 <= status < 500:
        # Any other 4xx TP1 has never returned to this session (400/403/422/...).
        return BrainErrorVerdict(
            BrainErrorClass.INVALID_REQUEST,
            MatchConfidence.HIGH if vtype == "invalid_request_error" else MatchConfidence.LOW,
            EvidenceProvenance.PROTOCOL_INFERRED
            if vtype == "invalid_request_error"
            else EvidenceProvenance.UNVERIFIED_GUESS,
            status,
            vtype,
            vcode,
            detail,
        )

    # P5: unknown stays unknown — never guess a specific class for a status
    # this module has no basis (observed or protocol) to characterise.
    return BrainErrorVerdict(
        BrainErrorClass.UNKNOWN,
        MatchConfidence.LOW,
        EvidenceProvenance.UNVERIFIED_GUESS,
        status,
        vtype,
        vcode,
        detail,
    )


def verdict_for_timeout(detail: str) -> BrainErrorVerdict:
    """A client-side wall-clock deadline never produced an HTTP status at
    all — this is determined structurally (the caller's own timer fired),
    never by pattern-matching, so HIGH confidence is warranted despite no
    vendor evidence existing to observe."""
    return BrainErrorVerdict(
        BrainErrorClass.TIMEOUT,
        MatchConfidence.HIGH,
        EvidenceProvenance.PROTOCOL_INFERRED,
        None,
        None,
        None,
        detail,
    )


def verdict_for_network_error(detail: str) -> BrainErrorVerdict:
    """DNS/connect/TLS failure — no response ever arrived. Same structural
    certainty as timeout: the transport library's own exception type is the
    evidence, not a guess."""
    return BrainErrorVerdict(
        BrainErrorClass.NETWORK_ERROR,
        MatchConfidence.HIGH,
        EvidenceProvenance.PROTOCOL_INFERRED,
        None,
        None,
        None,
        detail,
    )


def verdict_for_output_invalid(detail: str, http_status: int = 200) -> BrainErrorVerdict:
    """A 2xx response whose body could not be parsed into the expected
    `choices[0].message` shape. LOW confidence + UNVERIFIED_GUESS: this
    session has never seen TP1 return a malformed 200, so the *cause* is
    unknown even though the *symptom* (unusable body) is certain."""
    return BrainErrorVerdict(
        BrainErrorClass.OUTPUT_INVALID,
        MatchConfidence.LOW,
        EvidenceProvenance.UNVERIFIED_GUESS,
        http_status,
        None,
        None,
        detail,
    )
