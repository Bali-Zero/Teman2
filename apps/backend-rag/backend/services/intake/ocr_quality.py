"""Offline OCR-provider quality scoring for intake samples.

This module does not call vision providers. It scores OCR text that a provider
already produced by running the normal classify/extract path and comparing the
result with known expected fields.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from backend.services.intake import classify, extract

GenerateFn = Callable[[str, str], Awaitable[str]]


def _field_value(fields: Mapping[str, Any], name: str) -> Any:
    raw = fields.get(name)
    if isinstance(raw, Mapping):
        return raw.get("value")
    return raw


def _normalize_for_match(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().casefold()
    return re.sub(r"\s+", " ", text)


def score_expected_fields(
    expected_fields: Mapping[str, Any],
    extracted_fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Score extracted field values against expected values.

    The comparison is intentionally simple and auditable: case-insensitive,
    whitespace-normalized exact equality. Missing values and wrong values are
    tracked separately so provider runs show whether OCR failed to read a field
    or read a conflicting value.
    """
    matched: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    details: dict[str, dict[str, Any]] = {}

    for name, expected in expected_fields.items():
        actual = _field_value(extracted_fields, name)
        expected_norm = _normalize_for_match(expected)
        actual_norm = _normalize_for_match(actual)
        if not actual_norm:
            missing.append(name)
            status = "missing"
        elif actual_norm == expected_norm:
            matched.append(name)
            status = "matched"
        else:
            mismatched.append(name)
            status = "mismatched"
        details[name] = {"expected": expected, "actual": actual, "status": status}

    total = len(expected_fields)
    score = round(len(matched) / total, 4) if total else 1.0
    return {
        "score": score,
        "total_fields": total,
        "matched_count": len(matched),
        "missing_count": len(missing),
        "mismatched_count": len(mismatched),
        "matched_fields": matched,
        "missing_fields": missing,
        "mismatched_fields": mismatched,
        "details": details,
    }


async def evaluate_ocr_text(
    *,
    provider: str,
    ocr_text: str,
    expected_doc_type: str,
    expected_fields: Mapping[str, Any],
    generate_fn: GenerateFn | None = None,
) -> dict[str, Any]:
    """Run current intake interpretation over one provider's OCR text."""
    classification = await classify.classify_document(ocr_text)
    expected_canonical = extract.canonical_doc_type(expected_doc_type) or expected_doc_type
    if classification["type"] == "unknown":
        return {
            "provider": provider,
            "classification": classification,
            "extracted_doc_type": "unknown",
            "expected_doc_type": expected_canonical,
            "doc_type_match": False,
            "field_score": score_expected_fields(expected_fields, {}),
            "fields": {},
        }

    extraction = await extract.extract_fields(
        classification["type"],
        [ocr_text],
        generate_fn=generate_fn,
    )
    extracted_doc_type = extraction["doc_type"]
    return {
        "provider": provider,
        "classification": classification,
        "extracted_doc_type": extracted_doc_type,
        "expected_doc_type": expected_canonical,
        "doc_type_match": extracted_doc_type == expected_canonical,
        "field_score": score_expected_fields(expected_fields, extraction["fields"]),
        "fields": extraction["fields"],
    }
