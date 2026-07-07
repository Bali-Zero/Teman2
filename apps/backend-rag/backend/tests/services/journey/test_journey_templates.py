from backend.services.journey.journey_templates import JourneyTemplatesService


def test_get_template_returns_known_template_and_none_for_unknown() -> None:
    service = JourneyTemplatesService()

    template = service.get_template("pt_pma_setup")

    assert template is not None
    assert template["title"] == "PT PMA Company Setup"
    assert template["steps"][0]["step_id"] == "name_approval"
    assert service.get_template("missing") is None


def test_list_templates_returns_all_template_keys() -> None:
    service = JourneyTemplatesService()

    keys = service.list_templates()

    assert keys == list(service.JOURNEY_TEMPLATES.keys())
    assert {"pt_pma_setup", "kitas_application", "property_purchase"}.issubset(keys)


def test_validate_template_checks_template_presence() -> None:
    service = JourneyTemplatesService()

    assert service.validate_template("kitas_application") is True
    assert service.validate_template("unknown_template") is False
