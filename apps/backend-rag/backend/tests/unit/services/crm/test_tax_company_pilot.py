import pytest


def test_ocean_pilot_map_links_tax_member_people_and_drive_evidence() -> None:
    from backend.services.crm.tax_company_pilot import get_tax_company_pilot_map

    pilot_map = get_tax_company_pilot_map("ocean")

    assert pilot_map is not None
    assert pilot_map.company.name == "OCEAN CLOTHES AND SHOES PT"
    assert pilot_map.tax_member.name == "DEA"
    assert pilot_map.read_only is True
    assert pilot_map.primary_entry == "person"
    assert pilot_map.workspace_mode == "team_read_only"
    assert pilot_map.drive_folders["operational"].endswith("1qJwTPkKFbm5Re1mKMeEEBFTfw0bYAYnQ")
    assert pilot_map.drive_folders["tax"].endswith("1Mfwo4txaLarfoDucQzB4_QFgt1YKragA")
    assert {person.name for person in pilot_map.persons} == {
        "Natan Kleimonov",
        "Ihor Osmanov",
        "Yaroslav Voitenko",
    }
    assert any(document.group == "tax" and document.name == "SPT 2025" for document in pilot_map.documents)
    assert any(candidate.confidence == "medium" for candidate in pilot_map.duplicate_candidates)
    assert any(gap.code == "confirm_company_roles" for gap in pilot_map.gaps)
    assert {dossier.person_name for dossier in pilot_map.person_dossiers} == {
        "Natan Kleimonov",
        "Ihor Osmanov",
        "Yaroslav Voitenko",
    }
    assert all(dossier.company_name == pilot_map.company.name for dossier in pilot_map.person_dossiers)
    assert any("Company finance stays internal" in flag for dossier in pilot_map.person_dossiers for flag in dossier.risk_flags)
    assert pilot_map.next_best_actions[0].reason.endswith("person-first workspace.")
    assert pilot_map.business_story[-1] == (
        "Client portal access stays document-download only; Drive review remains a team workflow."
    )


def test_bimala_pilot_map_keeps_child_edges_unconfirmed() -> None:
    from backend.services.crm.tax_company_pilot import get_tax_company_pilot_map

    pilot_map = get_tax_company_pilot_map("bimala")

    assert pilot_map is not None
    assert pilot_map.company.name == "BIMALA / Bimala Investments Bali PT"
    assert pilot_map.tax_member.name == "Dewa Ayu"
    assert pilot_map.drive_folders["operational"].endswith("192muakUUFdYZVq67w10dy_75R63nor_L")
    assert {person.name for person in pilot_map.persons if person.relationship_confidence == "confirmed"} == {
        "Giulia Del Giudice",
        "Gianluca Morelli",
    }
    assert {person.name for person in pilot_map.persons if person.relationship_confidence == "unconfirmed"} == {
        "Giorgia Emidio",
        "Iuma Morelli",
        "Mailen Morelli",
    }
    assert any(document.group == "lkpm" for document in pilot_map.documents)
    assert any(gap.code == "confirm_family_relationships" for gap in pilot_map.gaps)
    unconfirmed_dossiers = [
        dossier for dossier in pilot_map.person_dossiers if dossier.relationship_confidence == "unconfirmed"
    ]
    assert {dossier.person_name for dossier in unconfirmed_dossiers} == {
        "Giorgia Emidio",
        "Iuma Morelli",
        "Mailen Morelli",
    }
    assert all(
        dossier.next_action == "Confirm the family or business relationship before nesting files."
        for dossier in unconfirmed_dossiers
    )
    assert any(action.owner == "tax" for action in pilot_map.next_best_actions)


@pytest.mark.parametrize("company_key", ["", "unknown", "ocean-clothes"])
def test_unknown_company_key_returns_none(company_key: str) -> None:
    from backend.services.crm.tax_company_pilot import get_tax_company_pilot_map

    assert get_tax_company_pilot_map(company_key) is None
