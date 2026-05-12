from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_build_evidence_dossiers_reads_db_and_kg_rows() -> None:
    from backend.services.crm.evidence_dossier import build_evidence_dossiers

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "client_id": 42,
                    "client_name": "Natan Kleimonov",
                    "client_folder_id": "client_drive_42",
                    "assigned_to": "setup@balizero.com",
                    "tax_consultant": "dea@balizero.com",
                    "company_id": 7,
                    "company_name": "OCEAN CLOTHES AND SHOES PT",
                    "company_type": "PT PMA",
                    "nib": "1234567890123",
                    "npwp_company": "01.234.567.8-901.000",
                    "kbli_code": "47711",
                    "company_status": "active",
                    "link_role": "Director",
                    "is_primary": True,
                },
            ],
            [
                {
                    "client_id": 42,
                    "file_name": "SPT 2025.pdf",
                    "document_type": "SPT company",
                    "document_category": "tax",
                    "file_id": "drive_file_spt",
                    "google_drive_file_url": "https://drive.google.com/file/d/drive_file_spt/view",
                    "file_url": None,
                    "status": "uploaded",
                    "client_visible": False,
                    "ocr_status": "completed",
                    "expiry_date": None,
                },
                {
                    "client_id": 42,
                    "file_name": "Profil Perseroan.pdf",
                    "document_type": "company_profile",
                    "document_category": "company",
                    "file_id": "drive_file_profile",
                    "google_drive_file_url": "https://drive.google.com/file/d/drive_file_profile/view",
                    "file_url": None,
                    "status": "uploaded",
                    "client_visible": False,
                    "ocr_status": "completed",
                    "expiry_date": None,
                },
            ],
            [
                {
                    "client_id": 42,
                    "document_file_id": "drive_file_profile",
                    "document_name": "Profil Perseroan.pdf",
                    "target_type": "crm_company",
                    "target_name": "OCEAN CLOTHES AND SHOES PT",
                    "relationship_type": "DESCRIBES",
                    "edge_tier": "direct",
                    "confidence": 1.0,
                },
            ],
        ],
    )
    pool = _pool(conn)

    result = await build_evidence_dossiers(pool, companies=["ocean"], limit=5)

    assert len(result) == 1
    dossier = result[0]
    assert dossier.key == "dynamic-7"
    assert dossier.company.name == "OCEAN CLOTHES AND SHOES PT"
    assert dossier.tax_member.name == "dea@balizero.com"
    assert dossier.persons[0].name == "Natan Kleimonov"
    assert dossier.persons[0].role == "Director"
    assert {document.group for document in dossier.documents} == {"company", "tax"}
    assert dossier.evidence_stories[0].relationship_path == [
        "Natan Kleimonov",
        "OCEAN CLOTHES AND SHOES PT",
        "Tax: dea@balizero.com",
    ]
    assert dossier.evidence_stories[0].portal_rule == (
        "Client portal: download approved documents only."
    )
    assert any("KG direct" in item.detail for item in dossier.evidence_stories[0].evidence_items)
    assert conn.fetch.await_count == 3
    assert "client_company_links" in conn.fetch.await_args_list[0].args[0]
    assert "documents" in conn.fetch.await_args_list[1].args[0]
    assert "crm_kg_nodes" in conn.fetch.await_args_list[2].args[0]


@pytest.mark.asyncio
async def test_build_evidence_dossiers_falls_back_to_pilot_when_dynamic_empty() -> None:
    from backend.services.crm.evidence_dossier import build_evidence_dossiers

    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    pool = _pool(conn)

    result = await build_evidence_dossiers(pool, companies=["ocean"], limit=5)

    assert len(result) == 1
    assert result[0].key == "ocean"
    assert result[0].company.name == "OCEAN CLOTHES AND SHOES PT"
    assert result[0].read_only is True
    assert result[0].evidence_stories


@pytest.mark.asyncio
async def test_build_evidence_dossiers_flags_operational_next_actions() -> None:
    from backend.services.crm.evidence_dossier import build_evidence_dossiers

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "client_id": 77,
                    "client_name": "Unassigned Founder",
                    "client_folder_id": None,
                    "assigned_to": None,
                    "tax_consultant": None,
                    "company_id": 12,
                    "company_name": "QUIET HOLDING PT",
                    "company_type": "PT PMA",
                    "nib": None,
                    "npwp_company": None,
                    "kbli_code": None,
                    "company_status": "active",
                    "link_role": None,
                    "is_primary": True,
                },
            ],
            [
                {
                    "client_id": 77,
                    "file_name": "Passport.pdf",
                    "document_type": "passport",
                    "document_category": "personal",
                    "file_id": "passport_file",
                    "google_drive_file_url": "https://drive.google.com/file/d/passport_file/view",
                    "file_url": None,
                    "status": "uploaded",
                    "client_visible": False,
                    "ocr_status": "pending",
                    "expiry_date": None,
                },
            ],
            [],
        ],
    )
    pool = _pool(conn)

    result = await build_evidence_dossiers(pool, companies=["quiet"], limit=5)

    assert len(result) == 1
    dossier = result[0]
    gap_codes = {gap.code for gap in dossier.gaps}
    assert {
        "missing_tax_owner",
        "missing_person_folder",
        "missing_company_registry",
        "missing_tax_trail",
        "missing_kg_edges",
    }.issubset(gap_codes)
    assert [
        action.label for action in dossier.next_best_actions[:2]
    ] == [
        "Assign tax owner before using this story operationally.",
        "Connect the canonical person Drive folder.",
    ]
    assert dossier.evidence_stories[0].next_action == (
        "Assign tax owner before using this story operationally."
    )


def _pool(conn: AsyncMock) -> MagicMock:
    pool = MagicMock()

    class _Acquire:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *exc: object) -> bool:
            return False

    pool.acquire = lambda: _Acquire()
    return pool
