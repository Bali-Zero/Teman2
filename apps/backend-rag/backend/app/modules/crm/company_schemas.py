"""
Request bodies for the company router.

The router used to take `data: dict` and hand JSON values straight to asyncpg.
asyncpg binds a DATE parameter only from datetime.date, so an ISO string blew
up inside the driver ("'str' object has no attribute 'toordinal'") and surfaced
as a 500. These models validate and convert at the edge instead: bad input is a
422 that names the field, and it is rejected before any SQL runs.

Two behaviours are kept from the dict bodies on purpose:
- unknown keys are ignored, not rejected;
- a number sent for a text column (a kbli_code of 62019) is accepted as text.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def parse_iso_date(value: Any) -> date | None:
    """YYYY-MM-DD to datetime.date. A longer ISO timestamp is cut to its date.

    None and "" both mean "no date". Anything else that is not an ISO date
    raises ValueError, which FastAPI reports as a 422 on that field.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    raise ValueError("must be an ISO date (YYYY-MM-DD)")


def _not_blank(value: str | None) -> str:
    if value is None or not value.strip():
        raise ValueError("must not be empty")
    return value


class _RequestBody(BaseModel):
    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)


class CompanyCreate(_RequestBody):
    company_name: str
    company_type: str = "PT PMA"
    kbli_code: str | None = None
    nib: str | None = None
    npwp_company: str | None = None
    registered_address: str | None = None
    city: str | None = None
    province: str | None = None
    company_email: str | None = None
    company_phone: str | None = None

    @field_validator("company_name")
    @classmethod
    def _company_name_not_blank(cls, value: str) -> str:
        return _not_blank(value)

    @field_validator("company_type", mode="before")
    @classmethod
    def _company_type_defaults_on_null(cls, value: Any) -> Any:
        # companies.company_type is NOT NULL; the server default only applies
        # when the column is omitted, so an explicit null gets the same default.
        return "PT PMA" if value is None else value


class CompanyUpdate(_RequestBody):
    company_name: str | None = None
    company_type: str | None = None
    kbli_code: str | None = None
    nib: str | None = None
    npwp_company: str | None = None
    akta_pendirian_no: str | None = None
    akta_pendirian_date: date | None = None
    akta_perubahan_no: str | None = None
    akta_perubahan_date: date | None = None
    sk_menhumkam_no: str | None = None
    sk_menhumkam_date: date | None = None
    registered_address: str | None = None
    office_address: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    status: str | None = None

    @field_validator(
        "akta_pendirian_date", "akta_perubahan_date", "sk_menhumkam_date", mode="before"
    )
    @classmethod
    def _dates(cls, value: Any) -> date | None:
        return parse_iso_date(value)

    @field_validator("company_name")
    @classmethod
    def _company_name_not_blank(cls, value: str | None) -> str:
        return _not_blank(value)

    @field_validator("company_type", "status")
    @classmethod
    def _not_null_columns(cls, value: str | None) -> str:
        # NOT NULL columns: an explicit null would reach the driver as a
        # not-null violation and surface as a 500. Validators do not run on
        # fields the client left out, so omitting them is still fine.
        if value is None:
            raise ValueError("must not be null")
        return value


class ClientCompanyLinkCreate(_RequestBody):
    # Defaults match the old data.get(key, default): used only when the key is
    # absent; an explicit null is passed through as before.
    role: str | None = "shareholder"
    is_primary: bool | None = False
    ownership_percentage: int | float | None = None
    shares_count: int | None = None
    start_date: date | None = None

    @field_validator("start_date", mode="before")
    @classmethod
    def _dates(cls, value: Any) -> date | None:
        return parse_iso_date(value)


class CompanyDocumentCreate(_RequestBody):
    document_type: str | None = None
    document_subtype: str | None = None
    document_number: str | None = None
    document_title: str | None = None
    description: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    google_drive_file_id: str | None = None
    google_drive_file_url: str | None = None
    file_name: str | None = None
    file_size_kb: int | float | None = None
    mime_type: str | None = None

    @field_validator("issue_date", "expiry_date", mode="before")
    @classmethod
    def _dates(cls, value: Any) -> date | None:
        return parse_iso_date(value)
