from __future__ import annotations

from backend.services.garuda_documents.models import DocumentKind
from backend.services.garuda_documents.redaction import can_reinforce_safely


def test_passport_biodata_can_never_be_safely_reinforced_via_cloud():
    """uncertain-ocr.feature scenario 2: when redaction cannot prove the outbound
    material safe, cloud reinforcement must be skipped. For an identity document every
    extracted field IS personal data, so this must be unconditionally False — not a flag
    someone could flip on without re-deriving the argument in the module docstring.
    """
    assert can_reinforce_safely(DocumentKind.PASSPORT_BIODATA) is False
