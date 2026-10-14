"""POST /api/crm/clients keeps the passport-scan gender end to end.

The New Client form sends gender "M"/"F" (crm.schemas.ts genderEnum). Before this
change both ClientCreate (router) and ClientValidator (service) lacked the field,
so Pydantic's extra="ignore" default dropped it and the INSERT had no column.
"""

from backend.app.routers.crm_clients import ClientCreate
from backend.services.crm.client_core import ClientValidator


def test_client_create_normalizes_scan_gender() -> None:
    assert ClientCreate(full_name="Test Client", gender="M").gender == "male"
    assert ClientCreate(full_name="Test Client", gender="F").gender == "female"


def test_gender_survives_router_and_service_models() -> None:
    routed = ClientCreate(full_name="Test Client", gender="F").model_dump(exclude_unset=True)
    validated = ClientValidator(**routed).model_dump(exclude_unset=True)
    assert validated["gender"] == "female"


def test_client_without_gender_stays_unset() -> None:
    routed = ClientCreate(full_name="Test Client").model_dump(exclude_unset=True)
    assert "gender" not in routed
    assert "gender" not in ClientValidator(**routed).model_dump(exclude_unset=True)
