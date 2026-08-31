"""Parity guard for the dashboard's hand-maintained GARUDA vocabulary."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.services.garuda_flow.constants import (
    FINAL_CHECK_DAYS,
    INTERNAL_ESCALATION_DAYS,
    PILOT_INTAKE_THRESHOLD_DAYS,
)
from backend.services.garuda_flow.eligibility import DeclineCode
from backend.services.garuda_flow.internal_preview_cli import (
    _BASE_WARNINGS,
    InternalPreviewRequest,
    InternalPreviewResponse,
    build_internal_preview,
)
from backend.services.garuda_flow.pricing import (
    _EXTENSION_PRICE_KEY,
    _ISSUANCE_PRICE_KEY,
)

_NOW = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)
_TODAY = _NOW.date()
_STRING_LITERAL = r'"(?:[^"\\]|\\.)*"'


def _repo_root() -> Path:
    """Find the worktree root without depending on pytest's current directory."""

    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    raise AssertionError("repository root: no parent containing .git")


def _adapter_source() -> str:
    path = _repo_root() / "apps/admin-dashboard-local/lib/garuda-preview-adapter.ts"
    assert path.is_file(), f"GARUDA adapter file is missing: {path}"
    return path.read_text(encoding="utf-8")


def _decode_literal(literal: str, constant: str) -> str:
    try:
        value = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{constant}: invalid string literal") from exc
    assert isinstance(value, str), f"{constant}: parsed literal is not a string"
    return value


def _extract_collection(source: str, constant: str, *, is_set: bool) -> list[str]:
    opener = r"new\s+Set\s*\(\s*" if is_set else ""
    closer = r"\s*\)" if is_set else r"\s*(?:as\s+const)?"
    match = re.search(
        rf"\bconst\s+{re.escape(constant)}\s*=\s*{opener}"
        rf"\[(?P<body>.*?)\]{closer}\s*;",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"{constant}: declaration or literal block not found"

    body = match.group("body")
    literals = list(re.finditer(_STRING_LITERAL, body))
    residue = re.sub(_STRING_LITERAL, "", body)
    assert re.fullmatch(r"[\s,]*", residue), f"{constant}: literal block could not be parsed"
    values = [_decode_literal(item.group(), constant) for item in literals]
    assert values, f"{constant}: extracted collection is empty"
    return values


def _extract_string(source: str, constant: str) -> str:
    match = re.search(
        rf"\bconst\s+{re.escape(constant)}\s*=\s*(?P<value>{_STRING_LITERAL})\s*;",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"{constant}: declaration or string literal not found"
    value = _decode_literal(match.group("value"), constant)
    assert value, f"{constant}: extracted string is empty"
    return value


def _request(**overrides: object) -> InternalPreviewRequest:
    payload: dict[str, object] = {
        "case_type": "issuance",
        "nationality": "USA",
        "entry_date": "2026-08-24",
        "passport_expiry_date": "2027-08-24",
        "purpose": "tourism",
        "travellers": 1,
        "self_pay": True,
    }
    payload.update(overrides)
    return InternalPreviewRequest.model_validate_json(json.dumps(payload))


def _engine_warning_literals() -> dict[str, str]:
    issuance = build_internal_preview(_request(), today=_TODAY, generated_at=_NOW)
    assert issuance.warnings[: len(_BASE_WARNINGS)] == list(_BASE_WARNINGS)
    assert len(issuance.warnings) == len(_BASE_WARNINGS) + 1

    extension = build_internal_preview(
        _request(case_type="extension", entry_date="2026-07-25", voa_expiry_date="2026-09-05"),
        today=_TODAY,
        generated_at=_NOW,
    )
    assert extension.warnings[: len(_BASE_WARNINGS)] == list(_BASE_WARNINGS)
    assert len(extension.warnings) == len(_BASE_WARNINGS) + 1

    uncovered = build_internal_preview(
        _request(entry_date="2027-01-05", passport_expiry_date="2028-01-05"),
        today=date(2026, 12, 20),
        generated_at=datetime(2026, 12, 20, 1, 0, tzinfo=timezone.utc),
    )
    assert uncovered.calendar_warning is not None

    warnings = {
        "ESTIMATED_EXPIRY_WARNING": issuance.warnings[-1],
        "EXTENSION_WARNING": extension.warnings[-1],
        "CALENDAR_WARNING": uncovered.calendar_warning,
    }
    if "price_warning" in InternalPreviewResponse.model_fields:
        with patch(
            "backend.services.garuda_flow.internal_preview_cli.price_for_case",
            return_value=(None, None),
        ):
            unavailable = build_internal_preview(_request(), today=_TODAY, generated_at=_NOW)
        price_warning = unavailable.price_warning  # type: ignore[attr-defined]
        assert isinstance(price_warning, str) and price_warning
        warnings["PRICE_WARNING"] = price_warning
    return warnings


def test_decline_codes_match_engine_enum() -> None:
    actual = set(_extract_collection(_adapter_source(), "DECLINE_CODES", is_set=True))
    assert actual == {code.value for code in DeclineCode}


def test_success_keys_match_response_model_in_order() -> None:
    actual = _extract_collection(_adapter_source(), "SUCCESS_KEYS", is_set=False)
    assert actual == list(InternalPreviewResponse.model_fields)


def test_base_warnings_match_engine_in_order() -> None:
    actual = _extract_collection(_adapter_source(), "BASE_WARNINGS", is_set=False)
    assert actual == list(_BASE_WARNINGS)


def test_single_warning_literals_match_exercised_engine_outputs() -> None:
    source = _adapter_source()
    for constant, expected in _engine_warning_literals().items():
        assert _extract_string(source, constant) == expected


def test_official_price_keys_match_pricing_module() -> None:
    actual = set(_extract_collection(_adapter_source(), "OFFICIAL_PRICE_KEYS", is_set=True))
    assert actual == {_ISSUANCE_PRICE_KEY, _EXTENSION_PRICE_KEY}


def test_checkpoint_labels_match_engine_constants() -> None:
    actual = set(_extract_collection(_adapter_source(), "CHECKPOINT_LABELS", is_set=True))
    expected = {
        f"D-{PILOT_INTAKE_THRESHOLD_DAYS}",
        f"D-{INTERNAL_ESCALATION_DAYS}",
        f"D-{FINAL_CHECK_DAYS}",
    }
    assert actual == expected
