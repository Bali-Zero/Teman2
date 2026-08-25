"""get_required_documents' own args/result models + call() coroutine."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from team_bot.executor.http_client import BackendClient, BackendClientConfig
from team_bot.executor.tools.get_required_documents import (
    GetRequiredDocumentsArgs,
    GetRequiredDocumentsResult,
    call,
)

from ._fakes import fake_transport


def test_innocence_valid_args_parse() -> None:
    args = GetRequiredDocumentsArgs.model_validate({"practice_type": "limited_stay_kitas"})
    assert args.practice_type.value == "limited_stay_kitas"


def test_guilt_unknown_practice_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GetRequiredDocumentsArgs.model_validate({"practice_type": "not_a_real_practice_type"})


def test_guilt_extra_property_is_rejected_matching_registry_additionalproperties_false() -> None:
    with pytest.raises(ValidationError):
        GetRequiredDocumentsArgs.model_validate(
            {"practice_type": "limited_stay_kitas", "practice_id": "PR-1234"}
        )


def test_innocence_valid_result_with_disjoint_required_and_optional() -> None:
    result = GetRequiredDocumentsResult.model_validate(
        {
            "practice_type": "limited_stay_kitas",
            "required_docs": ["passport", "passport_photo", "sponsor_letter"],
            "optional_docs": ["ktp", "npwp", "domicile_letter"],
        }
    )
    assert result.required_docs == ("passport", "passport_photo", "sponsor_letter")
    assert result.optional_docs == ("ktp", "npwp", "domicile_letter")


def test_guilt_overlapping_required_and_optional_is_rejected() -> None:
    with pytest.raises(ValidationError, match="both required and optional"):
        GetRequiredDocumentsResult.model_validate(
            {
                "practice_type": "limited_stay_kitas",
                "required_docs": ["passport"],
                "optional_docs": ["passport"],
            }
        )


def test_extra_backend_field_is_ignored_not_rejected() -> None:
    # Deliberate departure from house extra="forbid" — see the module's
    # own docstring for why an untrusted backend response is tolerant of
    # fields it does not know about yet.
    result = GetRequiredDocumentsResult.model_validate(
        {
            "practice_type": "work_permit",
            "required_docs": [],
            "optional_docs": [],
            "a_field_this_module_has_never_heard_of": "some future backend addition",
        }
    )
    assert result.practice_type.value == "work_permit"


@pytest.mark.asyncio
async def test_call_hits_the_practice_type_scoped_path() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(
            200,
            json={
                "practice_type": "compliance_change",
                "required_docs": [],
                "optional_docs": [],
            },
        )

    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(handler)
    )
    args = GetRequiredDocumentsArgs.model_validate({"practice_type": "compliance_change"})
    result = await call(client, headers={"Authorization": "Bearer t"}, args=args)
    await client.aclose()

    assert seen["path"] == "/api/crm/practice-types/compliance_change/required-documents"
    assert seen["auth"] == "Bearer t"
    assert result.status_code == 200
    assert result.json_body == {
        "practice_type": "compliance_change",
        "required_docs": [],
        "optional_docs": [],
    }
