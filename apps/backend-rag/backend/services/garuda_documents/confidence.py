"""Turns two independent OCR passes into the three customer-visible outcomes.

DECISIONS.md Q7 defers the numeric threshold to L5 and asks that it be MEASURED against a
corpus of genuine passport photographs (good, dim, glare, angle, partial crop). This lane
cannot do that measurement honestly: the PII boundary in this mandate forbids using real
client documents even for calibration, and no synthetic corpus stands in for the real
false-confident rate a genuine-document study would produce. `CONFIDENCE_THRESHOLD` below
is therefore a conservative PROPOSED default, not a measured one — flagged to the
orchestrator, not asserted as done. It is a single named constant specifically so a real
calibration pass can replace it without touching call sites.

The signal it is measured against is NOT bare LLM self-confidence (unreliable on its own):
a field only counts as confident when BOTH the two independent OCR passes agree on its
value AND the average self-rating clears the threshold. Disagreement between passes always
forces the field to uncertain, regardless of self-rating.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.garuda_documents.models import (
    PassportReviewFieldName,
    ReviewField,
    UncertainReviewField,
)
from backend.services.garuda_documents.ocr_client import OcrPassResult

# PROPOSED, not measured — see module docstring. Orchestrator/G1 must replace this with a
# real-corpus-derived number before this lane's confidence gate can be called "grounded".
CONFIDENCE_THRESHOLD = 0.80


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split()).upper()
    return normalized or None


@dataclass(frozen=True)
class FieldVerdict:
    field: PassportReviewFieldName
    value: str | None
    confident: bool


def classify_fields(pass_a: OcrPassResult, pass_b: OcrPassResult) -> list[FieldVerdict]:
    verdicts: list[FieldVerdict] = []
    for f in PassportReviewFieldName:
        val_a = _normalize(pass_a.values.get(f.value))
        val_b = _normalize(pass_b.values.get(f.value))
        agrees = val_a is not None and val_a == val_b
        avg_self_conf = (pass_a.self_confidence.get(f.value, 0.0) + pass_b.self_confidence.get(f.value, 0.0)) / 2
        confident = agrees and avg_self_conf >= CONFIDENCE_THRESHOLD
        # Prefer pass_a's original (non-normalized) casing for the value we surface.
        surfaced_value = pass_a.values.get(f.value) if agrees else None
        verdicts.append(FieldVerdict(field=f, value=surfaced_value, confident=confident))
    return verdicts


def to_review_fields(verdicts: list[FieldVerdict]) -> list[ReviewField]:
    """Only valid when every verdict is confident — caller (`service.py`) enforces this;
    raises if called on a mixed set so a future refactor cannot silently mis-route data.
    """
    if not all(v.confident and v.value is not None for v in verdicts):
        raise ValueError("to_review_fields requires every field confident with a value")
    return [ReviewField(field_path=v.field, value=v.value, confirmation_required=True) for v in verdicts]


def to_uncertain_fields(verdicts: list[FieldVerdict]) -> list[UncertainReviewField]:
    return [UncertainReviewField(field_path=v.field) for v in verdicts if not v.confident]


def all_confident(verdicts: list[FieldVerdict]) -> bool:
    return all(v.confident and v.value is not None for v in verdicts)
