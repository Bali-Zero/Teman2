"""Egress boundary for optional cloud OCR reinforcement (uncertain-ocr.feature, scenario 2).

The journey requires: redaction completes BEFORE any cloud connection opens; the outbound
material contains no raw image, personal data, document number, contact value, or opaque
result identifier; and when redaction cannot prove the outbound material safe, cloud
reinforcement is skipped entirely — the customer stays on the local manual-confirmation or
re-upload path.

For `PASSPORT_BIODATA` — the only document kind the frozen contract defines — every field
this pipeline extracts (name, passport number, nationality, expiry date) IS personal data,
and the image itself is the identity document. There is no representation of "this passport
photo, redacted" that both (a) is provably free of personal data and (b) still helps a
cloud model reinforce the reading. `can_reinforce_safely` therefore returns False
unconditionally for this document kind: this is not a placeholder pending future work, it
is the honest answer for an identity document, and it is the reason G-OCR-LOCAL's cloud
reinforcement path is designed but never exercised in this lane. A future document kind
that is NOT itself personal data (none exists in the contract today) could return True here
without changing any caller.
"""

from __future__ import annotations

from backend.services.garuda_documents.models import DocumentKind


def can_reinforce_safely(document_kind: DocumentKind) -> bool:
    if document_kind is DocumentKind.PASSPORT_BIODATA:
        return False
    # No other document kind exists in the frozen contract; treat anything else as
    # unrecognised and therefore unsafe by the same fail-closed default.
    return False
