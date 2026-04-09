"""Tests for the Google Sheets router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.sheets as sheets_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(sheets_module.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert sheets_module.router.prefix == "/api/sheets"
        assert sheets_module.router.tags == ["sheets"]


class TestSheetsEndpoints:
    @pytest.mark.integration
    def test_post_read_returns_rows(self, client: TestClient) -> None:
        service = MagicMock()
        service.read_range = AsyncMock(return_value=[["name"], ["alice"]])

        with patch("backend.app.routers.sheets._get_sheets_service", return_value=service):
            response = client.post(
                "/api/sheets/read",
                json={"spreadsheet_id": "sheet-1", "range": "Sheet1!A1:A2"},
            )

        assert response.status_code == 200
        assert response.json()["count"] == 2

    @pytest.mark.integration
    def test_write_range_returns_updated_cells(self, client: TestClient) -> None:
        service = MagicMock()
        service.write_range = AsyncMock(return_value={"updatedCells": 4})

        with patch("backend.app.routers.sheets._get_sheets_service", return_value=service):
            response = client.post(
                "/api/sheets/write",
                json={"spreadsheet_id": "sheet-1", "range": "Sheet1!A1:B2", "values": [["a", "b"], ["c", "d"]]},
            )

        assert response.status_code == 200
        assert response.json()["updated_cells"] == 4

    @pytest.mark.integration
    def test_update_row_builds_expected_range(self, client: TestClient) -> None:
        service = MagicMock()
        service.write_range = AsyncMock(return_value={"updatedCells": 3})

        with patch("backend.app.routers.sheets._get_sheets_service", return_value=service):
            response = client.post(
                "/api/sheets/update-row",
                json={
                    "spreadsheet_id": "sheet-1",
                    "sheet_name": "Company",
                    "row_number": 5,
                    "column_start": "D",
                    "values": ["addr", "nib", "npwp"],
                },
            )

        assert response.status_code == 200
        assert response.json()["range"] == "Company!D5:F5"
        service.write_range.assert_awaited_once_with("sheet-1", "Company!D5:F5", [["addr", "nib", "npwp"]])

    @pytest.mark.integration
    def test_read_range_surfaces_service_errors(self, client: TestClient) -> None:
        service = MagicMock()
        service.read_range = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("backend.app.routers.sheets._get_sheets_service", return_value=service):
            response = client.post(
                "/api/sheets/read",
                json={"spreadsheet_id": "sheet-1", "range": "Sheet1!A1:A2"},
            )

        assert response.status_code == 500

