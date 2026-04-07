"""Tests for LHKPN graph loader — Neo4j mocked.

Validates that load_lhkpn_report calls the correct upsert methods and
creates the right OWNS relationships.
"""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from osint_nexus.parsers.lhkpn_parser import (
    LhkpnReport,
    PropertyItem,
    VehicleItem,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_report(
    *,
    properties: list[PropertyItem] | None = None,
    vehicles: list[VehicleItem] | None = None,
    kas: int = 0,
) -> LhkpnReport:
    """Build a minimal LhkpnReport for testing."""
    return LhkpnReport(
        nama="RAJA ULUL AZMI SYAHWAL",
        jabatan="PPNS",
        nhk="496999",
        tahun=2022,
        lembaga="KEMENKUMHAM",
        unit_kerja="SUMSEL",
        tanah_bangunan=properties or [],
        kendaraan=vehicles or [],
        kas=kas,
        hutang=0,
        total_harta=0,
        source_file="test.pdf",
    )


def _make_property() -> PropertyItem:
    return PropertyItem(
        lokasi="DELI SERDANG",
        luas_tanah_m2=340,
        luas_bangunan_m2=250,
        tipe="tanah_bangunan",
        nilai=900_000_000,
        sumber="HASIL SENDIRI",
    )


def _make_vehicle() -> VehicleItem:
    return VehicleItem(
        jenis="MOBIL",
        merk_model="TOYOTA VIOS",
        tahun_perolehan=2012,
        nilai=100_000_000,
        sumber="HASIL SENDIRI",
    )


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_driver() -> MagicMock:
    """Create a mock Neo4j driver with async session."""
    driver = MagicMock()
    session = AsyncMock()
    session.run = AsyncMock()

    # Make session work as async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = ctx

    return driver, session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadLhkpnReport:
    """Tests for GraphLoader.load_lhkpn_report."""

    @pytest.mark.asyncio
    async def test_creates_property_nodes(self) -> None:
        """load_lhkpn_report creates official + property + OWNS relationships.

        With 1 property + 1 vehicle, expect at least 4 session.run calls:
        - 1 for upsert_official
        - 1 for upsert_property
        - 1 for OWNS relationship (property)
        - 1 for upsert_vehicle
        - 1 for OWNS relationship (vehicle)
        = 5 total
        """
        driver, session = _mock_driver()

        with patch("osint_nexus.graph.loader.AsyncGraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = driver

            from osint_nexus.graph.loader import GraphLoader

            loader = GraphLoader.__new__(GraphLoader)
            loader._driver = driver
            loader._db = "neo4j"

            report = _make_report(
                properties=[_make_property()],
                vehicles=[_make_vehicle()],
            )

            count = await loader.load_lhkpn_report(report)

            assert count == 2  # 1 property + 1 vehicle
            # At least 5 calls: official + property + OWNS + vehicle + OWNS
            assert session.run.call_count >= 5

    @pytest.mark.asyncio
    async def test_skips_empty_kas(self) -> None:
        """When kas=0, no BankAccount node should be created."""
        driver, session = _mock_driver()

        with patch("osint_nexus.graph.loader.AsyncGraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = driver

            from osint_nexus.graph.loader import GraphLoader

            loader = GraphLoader.__new__(GraphLoader)
            loader._driver = driver
            loader._db = "neo4j"

            report = _make_report(kas=0)

            count = await loader.load_lhkpn_report(report)

            assert count == 0  # no assets

            # Check no BankAccount query was issued
            for call in session.run.call_args_list:
                query = call[0][0] if call[0] else call[1].get("query", "")
                assert "BankAccount" not in query, \
                    "BankAccount query should not be issued when kas=0"

    @pytest.mark.asyncio
    async def test_creates_bank_account_when_kas_positive(self) -> None:
        """When kas>0, a BankAccount node and OWNS relationship are created."""
        driver, session = _mock_driver()

        with patch("osint_nexus.graph.loader.AsyncGraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = driver

            from osint_nexus.graph.loader import GraphLoader

            loader = GraphLoader.__new__(GraphLoader)
            loader._driver = driver
            loader._db = "neo4j"

            report = _make_report(kas=15_000_000)

            count = await loader.load_lhkpn_report(report)

            assert count == 1  # just the bank account

            # Verify BankAccount query was issued
            bank_queries = [
                call for call in session.run.call_args_list
                if "BankAccount" in (call[0][0] if call[0] else "")
            ]
            assert len(bank_queries) >= 1, "Expected at least one BankAccount query"

    @pytest.mark.asyncio
    async def test_asset_count_matches(self) -> None:
        """Return count should equal total asset nodes."""
        driver, session = _mock_driver()

        with patch("osint_nexus.graph.loader.AsyncGraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = driver

            from osint_nexus.graph.loader import GraphLoader

            loader = GraphLoader.__new__(GraphLoader)
            loader._driver = driver
            loader._db = "neo4j"

            props = [_make_property(), _make_property()]
            vehs = [_make_vehicle()]
            report = _make_report(properties=props, vehicles=vehs, kas=500_000)

            count = await loader.load_lhkpn_report(report)

            # 2 properties + 1 vehicle + 1 bank account = 4
            assert count == 4
