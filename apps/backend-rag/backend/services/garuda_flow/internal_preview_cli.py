"""Stateless GARUDA VOA internal preview CLI.

Protocol: read one bounded JSON object from stdin and write one JSON object to
stdout.  This adapter deliberately performs no persistence and emits no input
in logs or errors.  It is the narrow process boundary used by the loopback-only
admin dashboard (with operator-controlled SSH access); it is not a client-facing
API.

Run from ``apps/backend-rag``::

    .venv/bin/python -m backend.services.garuda_flow.internal_preview_cli
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from typing import BinaryIO, Literal, TextIO

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.services.garuda_flow.constants import (
    FINAL_CHECK_DAYS,
    INTERNAL_ESCALATION_DAYS,
    PILOT_INTAKE_THRESHOLD_DAYS,
    b1_max_total_stay_exceeded,
)
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    build_verdict,
)
from backend.services.garuda_flow.operating_calendar import COVERAGE_END, COVERAGE_START
from backend.services.garuda_flow.pricing import price_for_case
from backend.services.visa_check.catalogue import VISA_META, VisaType

MAX_REQUEST_BYTES: int = 4096

_INTERNAL_LABELS: tuple[str, ...] = (
    f"D-{PILOT_INTAKE_THRESHOLD_DAYS}",
    f"D-{INTERNAL_ESCALATION_DAYS}",
    f"D-{FINAL_CHECK_DAYS}",
)

_BASE_WARNINGS: tuple[str, ...] = (
    "Internal preliminary pre-screen only; it is not an immigration decision or an approval guarantee.",
    "Nationality and entry-point eligibility are not yet checked against an authoritative dataset and require manual verification.",
    "Passport type, document authenticity, and prior overstay, refusal, or blacklist history require human review.",
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InternalPreviewRequest(_StrictModel):
    """The complete bounded input contract; no free-text or identity fields."""

    case_type: CaseType
    nationality: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    entry_date: date
    passport_expiry_date: date
    purpose: Purpose
    travellers: int = Field(ge=1, le=10)
    self_pay: bool
    voa_expiry_date: date | None = None
    extension_already_used: bool = False

    @field_validator("nationality")
    @classmethod
    def _normalise_iso(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _require_printed_extension_expiry(self) -> InternalPreviewRequest:
        if self.case_type is CaseType.EXTENSION and self.voa_expiry_date is None:
            raise ValueError("extension expiry is required")
        return self


class InternalCheckpoint(_StrictModel):
    label: Literal["D-10", "D-3", "D-1"]
    at: date
    kind: Literal["internal"]
    note: str | None = None


class InternalPreviewResponse(_StrictModel):
    decision: Literal["ACCEPT", "DECLINE"]
    reason_codes: list[str]
    case_type: CaseType
    entry_date: date
    expiry_date: date
    computed_stay_end: date
    expiry_is_estimated: bool
    published_filing_deadline: date | None
    submit_by_date: date | None
    internal_checkpoints: list[InternalCheckpoint]
    price_idr: int | None
    price_source: str | None
    generated_at: datetime
    calendar_coverage_start: date
    calendar_coverage_end: date
    calendar_status: Literal["confirmed", "uncovered", "not_applicable"]
    calendar_warning: str | None
    warnings: list[str]


class PreviewInputError(ValueError):
    """A sanitized request-validation failure safe to map to exit code 2."""


def _validate_entry_window(request: InternalPreviewRequest, *, today: date) -> None:
    if (today - request.entry_date).days > 365 * 3:
        raise PreviewInputError("entry date outside supported range")
    if request.case_type is CaseType.ISSUANCE and (request.entry_date - today).days > 365:
        raise PreviewInputError("entry date outside supported range")
    if request.case_type is not CaseType.EXTENSION:
        return
    if request.entry_date > today:
        raise PreviewInputError("extension entry date cannot be in the future")

    printed_expiry = request.voa_expiry_date
    if printed_expiry is None:
        # Pydantic enforces this too. Keep the process-boundary validator
        # defensive in case the request model is ever constructed unsafely.
        raise PreviewInputError("extension expiry is required")
    if printed_expiry < request.entry_date:
        raise PreviewInputError("extension expiry precedes entry date")

    meta = VISA_META[VisaType.B1]
    extension_count, extension_days = meta.extensions
    max_total_stay_days = meta.duration_days + extension_count * extension_days
    if b1_max_total_stay_exceeded(
        (printed_expiry - request.entry_date).days, max_total_stay_days
    ):
        raise PreviewInputError("extension expiry exceeds B1 maximum stay")


def build_internal_preview(
    request: InternalPreviewRequest,
    *,
    today: date,
    generated_at: datetime,
) -> InternalPreviewResponse:
    """Build one real, non-persisted preview from the GARUDA engine."""

    _validate_entry_window(request, today=today)
    intake = VoaIntakeRequest(
        case_type=request.case_type,
        nationality=request.nationality,
        entry_date=request.entry_date,
        passport_expiry_date=request.passport_expiry_date,
        purpose=request.purpose,
        travellers=request.travellers,
        self_pay=request.self_pay,
        voa_expiry_date=request.voa_expiry_date,
        extension_already_used=request.extension_already_used,
    )
    verdict = build_verdict(intake, today=today)
    price_idr, price_source = price_for_case(request.case_type)

    checkpoints: list[InternalCheckpoint] = []
    if request.case_type is CaseType.EXTENSION:
        checkpoints_by_label = {
            checkpoint.label: checkpoint for checkpoint in verdict.stay_window.checkpoints
        }
        checkpoints = [
            InternalCheckpoint(
                label=label,
                at=checkpoints_by_label[label].at,
                kind="internal",
                note=None,
            )
            for label in _INTERNAL_LABELS
        ]

    if request.case_type is CaseType.EXTENSION:
        calendar_status: Literal["confirmed", "uncovered", "not_applicable"] = (
            "not_applicable"
        )
    elif verdict.submit_by_date is not None:
        calendar_status = "confirmed"
    else:
        calendar_status = "uncovered"

    calendar_warning: str | None = None
    submit_by_date = verdict.submit_by_date
    if calendar_status == "uncovered":
        submit_by_date = None
        calendar_warning = (
            "The operating calendar does not cover this entry date. "
            "No issuance deadline is shown; staff must verify the applicable decree manually."
        )

    warnings = list(_BASE_WARNINGS)
    if verdict.stay_window.expiry_is_estimated:
        warnings.append(
            "The expiry is an estimate; the printed immigration expiry is authoritative and must be verified before action."
        )
    if request.case_type is CaseType.EXTENSION:
        warnings.append(
            "Extension processing requires office-specific verification and an in-person photo/interview step."
        )

    return InternalPreviewResponse(
        decision=verdict.decision.value,
        reason_codes=list(dict.fromkeys(verdict.decline_codes)),
        case_type=request.case_type,
        entry_date=request.entry_date,
        expiry_date=verdict.stay_window.expiry_date,
        computed_stay_end=verdict.stay_window.expiry_date,
        expiry_is_estimated=verdict.stay_window.expiry_is_estimated,
        published_filing_deadline=verdict.published_filing_deadline,
        submit_by_date=submit_by_date,
        internal_checkpoints=checkpoints,
        price_idr=price_idr,
        price_source=price_source,
        generated_at=generated_at,
        calendar_coverage_start=COVERAGE_START,
        calendar_coverage_end=COVERAGE_END,
        calendar_status=calendar_status,
        calendar_warning=calendar_warning,
        warnings=warnings,
    )


def _write_json(stdout: TextIO, payload: str) -> None:
    stdout.write(payload)
    stdout.write("\n")


def _write_error(stdout: TextIO, code: str) -> None:
    _write_json(stdout, json.dumps({"ok": False, "error": code}, separators=(",", ":")))


def run_cli(stdin: BinaryIO, stdout: TextIO) -> int:
    """Run the bounded one-request protocol.  Validation failures exit 2."""

    raw = stdin.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        _write_error(stdout, "request_too_large")
        return 2
    if not raw.strip():
        _write_error(stdout, "invalid_request")
        return 2

    try:
        request = InternalPreviewRequest.model_validate_json(raw)
        generated_at = datetime.now(timezone.utc)
        response = build_internal_preview(
            request,
            today=date.today(),
            generated_at=generated_at,
        )
    except (ValidationError, PreviewInputError):
        _write_error(stdout, "invalid_request")
        return 2
    except Exception:
        _write_error(stdout, "runtime_error")
        return 3

    _write_json(stdout, response.model_dump_json())
    return 0


def main() -> int:
    return run_cli(sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MAX_REQUEST_BYTES",
    "InternalCheckpoint",
    "InternalPreviewRequest",
    "InternalPreviewResponse",
    "build_internal_preview",
    "main",
    "run_cli",
]
