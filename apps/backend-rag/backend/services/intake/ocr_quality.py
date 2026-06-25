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

_EXPECTED_FIELD_ALIASES_BY_DOC_TYPE: dict[str, dict[str, tuple[str, ...]]] = {
    "nib": {
        "nib": ("nib_number",),
    },
    "payment_receipt": {
        "reference": ("receipt_no",),
        "payer": ("payer_name",),
        "date": ("payment_date",),
    },
    "travel_ticket": {
        "passenger": ("name",),
        "booking_ref": ("booking_reference",),
        "date": ("travel_date",),
    },
}


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


def _candidate_field_names(name: str, doc_type: str | None) -> tuple[str, ...]:
    aliases = _EXPECTED_FIELD_ALIASES_BY_DOC_TYPE.get(doc_type or "", {}).get(name, ())
    return (name, *aliases)


def _elapsed_seconds(result: Mapping[str, Any]) -> float | None:
    """Return provider runtime when benchmark rows include it."""
    raw = result.get("elapsed_s")
    if raw is None:
        raw = result.get("seconds")
    if not isinstance(raw, int | float):
        return None
    return float(raw)


def _score_one_field(
    *,
    expected: Any,
    extracted_fields: Mapping[str, Any],
    candidate_names: tuple[str, ...],
) -> tuple[str, Any, str | None]:
    expected_norm = _normalize_for_match(expected)
    first_actual: Any = None
    first_actual_name: str | None = None

    for candidate_name in candidate_names:
        actual = _field_value(extracted_fields, candidate_name)
        actual_norm = _normalize_for_match(actual)
        if not actual_norm:
            continue
        if first_actual_name is None:
            first_actual = actual
            first_actual_name = candidate_name
        if actual_norm == expected_norm:
            return "matched", actual, candidate_name

    if first_actual_name is None:
        return "missing", None, None
    return "mismatched", first_actual, first_actual_name


def score_expected_fields(
    expected_fields: Mapping[str, Any],
    extracted_fields: Mapping[str, Any],
    *,
    doc_type: str | None = None,
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
        candidate_names = _candidate_field_names(name, doc_type)
        status, actual, actual_field = _score_one_field(
            expected=expected,
            extracted_fields=extracted_fields,
            candidate_names=candidate_names,
        )
        if status == "missing":
            missing.append(name)
        elif status == "matched":
            matched.append(name)
        else:
            mismatched.append(name)
        details[name] = {
            "expected": expected,
            "actual": actual,
            "actual_field": actual_field,
            "status": status,
        }

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
            "field_score": score_expected_fields(expected_fields, {}, doc_type=expected_canonical),
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
        "field_score": score_expected_fields(
            expected_fields,
            extraction["fields"],
            doc_type=expected_canonical,
        ),
        "fields": extraction["fields"],
    }


def summarize_evaluations(evaluations: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate per-sample OCR quality results by provider."""
    grouped: dict[str, dict[str, Any]] = {}
    for result in evaluations:
        provider = str(result.get("provider") or "unknown")
        field_score = result.get("field_score") or {}
        bucket = grouped.setdefault(
            provider,
            {
                "samples": 0,
                "doc_type_matches": 0,
                "field_score_total": 0.0,
                "matched_fields": 0,
                "missing_fields": 0,
                "error_count": 0,
                "clean_samples": 0,
                "clean_doc_type_matches": 0,
                "clean_field_score_total": 0.0,
                "clean_matched_fields": 0,
                "clean_missing_fields": 0,
                "elapsed_values": [],
                "clean_elapsed_values": [],
            },
        )
        bucket["samples"] += 1
        if result.get("doc_type_match"):
            bucket["doc_type_matches"] += 1
        bucket["field_score_total"] += float(field_score.get("score") or 0.0)
        bucket["matched_fields"] += int(field_score.get("matched_count") or 0)
        bucket["missing_fields"] += int(field_score.get("missing_count") or 0)
        if result.get("error"):
            bucket["error_count"] += 1
        else:
            bucket["clean_samples"] += 1
            if result.get("doc_type_match"):
                bucket["clean_doc_type_matches"] += 1
            bucket["clean_field_score_total"] += float(field_score.get("score") or 0.0)
            bucket["clean_matched_fields"] += int(field_score.get("matched_count") or 0)
            bucket["clean_missing_fields"] += int(field_score.get("missing_count") or 0)
        if (elapsed_s := _elapsed_seconds(result)) is not None:
            bucket["elapsed_values"].append(elapsed_s)
            if not result.get("error"):
                bucket["clean_elapsed_values"].append(elapsed_s)

    provider_summary: dict[str, dict[str, Any]] = {}
    for provider, bucket in grouped.items():
        samples = bucket["samples"]
        clean_samples = bucket["clean_samples"]
        summary = {
            "samples": samples,
            "doc_type_matches": bucket["doc_type_matches"],
            "doc_type_match_rate": round(bucket["doc_type_matches"] / samples, 4),
            "avg_field_score": round(bucket["field_score_total"] / samples, 4),
            "matched_fields": bucket["matched_fields"],
            "missing_fields": bucket["missing_fields"],
            "error_count": bucket["error_count"],
            "clean_samples": clean_samples,
            "clean_doc_type_matches": bucket["clean_doc_type_matches"],
            "clean_doc_type_match_rate": (
                round(bucket["clean_doc_type_matches"] / clean_samples, 4)
                if clean_samples
                else 0.0
            ),
            "clean_avg_field_score": (
                round(bucket["clean_field_score_total"] / clean_samples, 4)
                if clean_samples
                else 0.0
            ),
            "clean_matched_fields": bucket["clean_matched_fields"],
            "clean_missing_fields": bucket["clean_missing_fields"],
        }
        elapsed_values = bucket["elapsed_values"]
        if elapsed_values:
            summary.update(
                {
                    "elapsed_total_s": round(sum(elapsed_values), 3),
                    "elapsed_avg_s": round(sum(elapsed_values) / len(elapsed_values), 3),
                    "elapsed_min_s": round(min(elapsed_values), 3),
                    "elapsed_max_s": round(max(elapsed_values), 3),
                }
            )
        clean_elapsed_values = bucket["clean_elapsed_values"]
        if clean_elapsed_values:
            summary.update(
                {
                    "clean_elapsed_total_s": round(sum(clean_elapsed_values), 3),
                    "clean_elapsed_avg_s": round(
                        sum(clean_elapsed_values) / len(clean_elapsed_values), 3
                    ),
                    "clean_elapsed_min_s": round(min(clean_elapsed_values), 3),
                    "clean_elapsed_max_s": round(max(clean_elapsed_values), 3),
                }
            )
        provider_summary[provider] = summary

    return {
        "sample_count": len(evaluations),
        "provider_summary": provider_summary,
        "results": list(evaluations),
    }
