"""Tests for CRM Drive autowatcher orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_autowatcher_dry_run_previews_story_drafts_without_writes() -> None:
    from backend.services.crm.drive_autowatcher_service import (
        CompanyDriveEvidence,
        DriveEvidenceDocument,
        run_crm_drive_autowatch,
    )

    evidence = [
        CompanyDriveEvidence(
            company_id=7,
            company_name="PT OCEAN CLOTHES AND SHOES",
            client_ids=[42],
            people=["Ihor Osmanov"],
            tax_owner="DEA",
            documents=[
                DriveEvidenceDocument(
                    file_id="drive-profile",
                    file_name="Profil Perseroan.pdf",
                    document_type="profile_perseroan",
                    document_category="company",
                    ocr_status="completed",
                    has_kg_node=True,
                )
            ],
            kg_edge_count=2,
        )
    ]

    with patch(
        "backend.services.crm.drive_autowatcher_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
        return_value={"processed": 1, "ocr_dispatched": 0, "kg_linked": 1},
    ), patch(
        "backend.services.crm.drive_autowatcher_service.fetch_drive_evidence_for_story_drafts",
        new_callable=AsyncMock,
        return_value=evidence,
    ), patch(
        "backend.services.crm.drive_autowatcher_service.create_workspace_ai_snapshot",
        new_callable=AsyncMock,
    ) as create_snapshot:
        result = await run_crm_drive_autowatch(
            object(),
            limit=5,
            dry_run=True,
            allow_ocr=False,
            created_by="autowatcher",
        )

    assert result["dry_run"] is True
    assert result["backfill"]["processed"] == 1
    assert result["snapshot_candidates"] == 1
    assert result["snapshots_created"] == 0
    assert result["snapshot_previews"][0]["company_name"] == "PT OCEAN CLOTHES AND SHOES"
    create_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_autowatcher_creates_only_new_draft_snapshots() -> None:
    from backend.services.crm.drive_autowatcher_service import (
        CompanyDriveEvidence,
        DriveEvidenceDocument,
        run_crm_drive_autowatch,
    )

    evidence = [
        CompanyDriveEvidence(
            company_id=7,
            company_name="PT OCEAN CLOTHES AND SHOES",
            client_ids=[42],
            people=["Ihor Osmanov", "Natan Kleimonov"],
            tax_owner="DEA",
            documents=[
                DriveEvidenceDocument(
                    file_id="drive-profile",
                    file_name="Profil Perseroan.pdf",
                    document_type="profile_perseroan",
                    document_category="company",
                    ocr_status="completed",
                    has_kg_node=True,
                ),
                DriveEvidenceDocument(
                    file_id="drive-npwp",
                    file_name="NPWP PT Ocean.pdf",
                    document_type="npwp",
                    document_category="tax",
                    ocr_status="completed",
                    has_kg_node=True,
                ),
            ],
            kg_edge_count=3,
        )
    ]

    with patch(
        "backend.services.crm.drive_autowatcher_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
        return_value={"processed": 2, "ocr_dispatched": 1, "kg_linked": 2},
    ), patch(
        "backend.services.crm.drive_autowatcher_service.fetch_drive_evidence_for_story_drafts",
        new_callable=AsyncMock,
        return_value=evidence,
    ), patch(
        "backend.services.crm.drive_autowatcher_service.workspace_ai_snapshot_exists",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "backend.services.crm.drive_autowatcher_service.create_workspace_ai_snapshot",
        new_callable=AsyncMock,
        return_value=object(),
    ) as create_snapshot:
        result = await run_crm_drive_autowatch(
            object(),
            limit=5,
            dry_run=False,
            allow_ocr=True,
            created_by="autowatcher",
        )

    assert result["dry_run"] is False
    assert result["snapshots_created"] == 1
    assert result["snapshots_skipped_existing"] == 0
    create_snapshot.assert_awaited_once()
    payload = create_snapshot.await_args.args[1]
    assert payload.company_id == 7
    assert payload.provider == "gemini"
    assert payload.note_id.startswith("crm-drive-autowatcher:v1:7:")
    assert payload.source_file_ids == ["drive-profile", "drive-npwp"]
    assert [fact.category for fact in payload.facts] == [
        "identity",
        "person",
        "compliance",
        "gap",
        "next_action",
    ]


@pytest.mark.asyncio
async def test_autowatcher_skips_existing_snapshot_fingerprint() -> None:
    from backend.services.crm.drive_autowatcher_service import (
        CompanyDriveEvidence,
        DriveEvidenceDocument,
        run_crm_drive_autowatch,
    )

    evidence = [
        CompanyDriveEvidence(
            company_id=8,
            company_name="PT BIMALA INVESTMENTS BALI",
            client_ids=[51],
            people=["Gianluca Morelli"],
            tax_owner="Dewa Ayu",
            documents=[
                DriveEvidenceDocument(
                    file_id="drive-tax",
                    file_name="SPT 2025.pdf",
                    document_type="spt",
                    document_category="tax",
                    ocr_status="completed",
                    has_kg_node=True,
                )
            ],
            kg_edge_count=1,
        )
    ]

    with patch(
        "backend.services.crm.drive_autowatcher_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
        return_value={"processed": 0},
    ), patch(
        "backend.services.crm.drive_autowatcher_service.fetch_drive_evidence_for_story_drafts",
        new_callable=AsyncMock,
        return_value=evidence,
    ), patch(
        "backend.services.crm.drive_autowatcher_service.workspace_ai_snapshot_exists",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "backend.services.crm.drive_autowatcher_service.create_workspace_ai_snapshot",
        new_callable=AsyncMock,
    ) as create_snapshot:
        result = await run_crm_drive_autowatch(
            object(),
            dry_run=False,
            created_by="autowatcher",
        )

    assert result["snapshots_created"] == 0
    assert result["snapshots_skipped_existing"] == 1
    create_snapshot.assert_not_called()


def test_story_draft_payload_uses_human_language_and_no_drive_links() -> None:
    from backend.services.crm.drive_autowatcher_service import (
        CompanyDriveEvidence,
        DriveEvidenceDocument,
        build_workspace_ai_snapshot_payload,
    )

    payload = build_workspace_ai_snapshot_payload(
        CompanyDriveEvidence(
            company_id=9,
            company_name="PT HUMAN BUSINESS",
            client_ids=[70],
            people=["Maria Rossi"],
            tax_owner="Adit",
            documents=[
                DriveEvidenceDocument(
                    file_id="drive-company",
                    file_name="AKTA.pdf",
                    document_type="akta",
                    document_category="company",
                    ocr_status="completed",
                    has_kg_node=True,
                )
            ],
            kg_edge_count=1,
        )
    )

    details = " ".join(fact.detail for fact in payload.facts)
    assert "KG" not in details
    assert "OCR" not in details
    assert "drive.google.com" not in details
    assert "Maria Rossi" in details
    assert payload.facts[-1].detail.startswith("Review this draft")


def test_evidence_query_prioritizes_companies_without_autowatcher_drafts() -> None:
    from backend.services.crm import drive_autowatcher_service

    sql = drive_autowatcher_service._EVIDENCE_SQL

    assert "crm_workspace_ai_snapshots" in sql
    assert "snap.note_id LIKE $3::text" in sql
    assert "ORDER BY has_autowatcher_snapshot ASC" in sql
    assert "company_documents" in sql
    assert "google_drive_file_id" in sql


def test_evidence_rows_dedupe_company_documents_across_linked_people() -> None:
    from backend.services.crm.drive_autowatcher_service import _evidence_from_rows

    evidence = _evidence_from_rows(
        [
            {
                "company_id": 1762,
                "company_name": "PT FRA Real Estate Consulting",
                "client_id": 146,
                "client_name": "Michele Porinelli",
                "tax_owner": "sahira@balizero.com",
                "file_id": "company-drive-file",
                "file_name": "Profil Perseroan April 2025.pdf",
                "document_type": "company_profile",
                "document_category": "company",
                "ocr_status": None,
                "has_kg_node": False,
                "kg_edge_count": 0,
            },
            {
                "company_id": 1762,
                "company_name": "PT FRA Real Estate Consulting",
                "client_id": 176,
                "client_name": "Francesca rizzo",
                "tax_owner": "krisna@balizero.com",
                "file_id": "company-drive-file",
                "file_name": "Profil Perseroan April 2025.pdf",
                "document_type": "company_profile",
                "document_category": "company",
                "ocr_status": None,
                "has_kg_node": False,
                "kg_edge_count": 0,
            },
        ]
    )

    assert len(evidence) == 1
    assert evidence[0].client_ids == [146, 176]
    assert evidence[0].people == ["Michele Porinelli", "Francesca rizzo"]
    assert [document.file_id for document in evidence[0].documents] == ["company-drive-file"]
