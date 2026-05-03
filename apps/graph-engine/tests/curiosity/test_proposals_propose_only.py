"""SACRED TEST: Propose-only enforcement for KG Curiosity Loop.

This test file verifies the INVIOLABLE safety gate:
  - CuriosityOrchestrator NEVER writes directly to kg_nodes or kg_edges
  - All KG mutations go through kg_proposals table
  - apply_approved() is the ONLY path to kg_nodes/kg_edges
  - apply_approved() REQUIRES status='approved' (not 'pending')

SYMBIOSIS Legge 5: Zero come ultima istanza.
The organism proposes, it does NOT decide.

DO NOT MODIFY THESE TESTS without Zero's explicit approval.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from nuzantara_graph.curiosity.models import (
    GapTopic,
    KGProposal,
    ProposalType,
    ResearchEvidence,
    Tier,
)
from nuzantara_graph.curiosity.orchestrator import CuriosityOrchestrator
from nuzantara_graph.curiosity.proposals import KGProposalStore


class TestProposeOnlyInvariant:
    """SACRED: Verify the propose-only safety gate is never violated."""

    def test_orchestrator_never_imports_kg_store_write(self) -> None:
        """Orchestrator must NEVER import KGStore directly."""
        source_path = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity" / "orchestrator.py"
        source = source_path.read_text()

        # Parse AST to check imports
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "kg_store" not in module.lower(), (
                    f"SAFETY VIOLATION: orchestrator.py imports from '{module}' "
                    f"which appears to reference kg_store. "
                    f"The orchestrator must NEVER access kg_nodes/kg_edges directly."
                )

    def test_orchestrator_never_mentions_kg_nodes_insert(self) -> None:
        """Orchestrator source must NEVER contain INSERT INTO kg_nodes."""
        source_path = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity" / "orchestrator.py"
        source = source_path.read_text().lower()

        forbidden_patterns = [
            "insert into kg_nodes",
            "insert into kg_edges",
            "update kg_nodes",
            "update kg_edges",
            "delete from kg_nodes",
            "delete from kg_edges",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"SAFETY VIOLATION: orchestrator.py contains '{pattern}'. "
                f"The orchestrator must NEVER write to kg_nodes/kg_edges directly."
            )

    def test_dispatchers_never_write_to_kg(self) -> None:
        """No dispatcher must write to kg_nodes or kg_edges."""
        dispatchers_dir = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity" / "dispatchers"

        forbidden_patterns = [
            "insert into kg_nodes",
            "insert into kg_edges",
            "kg_store",
        ]

        for py_file in dispatchers_dir.glob("*.py"):
            source = py_file.read_text().lower()
            for pattern in forbidden_patterns:
                assert pattern not in source, (
                    f"SAFETY VIOLATION: {py_file.name} contains '{pattern}'. "
                    f"Dispatchers must NEVER access KG tables directly."
                )

    def test_grader_never_writes_to_kg(self) -> None:
        """Grader must be read-only — NEVER write to kg_nodes or kg_edges."""
        source_path = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity" / "grader.py"
        source = source_path.read_text().lower()

        forbidden_patterns = [
            "insert into",
            "update ",
            "delete from",
            "kg_store",
            "asyncpg",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"SAFETY VIOLATION: grader.py contains '{pattern}'. "
                f"The grader must be pure computation — no DB access."
            )

    def test_only_proposals_py_has_kg_write_path(self) -> None:
        """Only proposals.py should contain the path to write to kg_nodes/kg_edges."""
        curiosity_dir = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity"

        for py_file in curiosity_dir.rglob("*.py"):
            if py_file.name == "proposals.py" or py_file.name == "__init__.py":
                continue

            source = py_file.read_text().lower()
            # Only proposals.py should contain INSERT INTO kg_nodes
            if "insert into kg_nodes" in source or "insert into kg_edges" in source:
                assert False, (
                    f"SAFETY VIOLATION: {py_file.relative_to(curiosity_dir)} contains "
                    f"direct KG write SQL. Only proposals.py may write to KG tables "
                    f"(via apply_approved after Zero approval)."
                )

    def test_apply_approved_requires_approved_status(self) -> None:
        """apply_approved() must check for 'approved' status before writing."""
        source_path = Path(__file__).parents[2] / "src" / "nuzantara_graph" / "curiosity" / "proposals.py"
        source = source_path.read_text()

        # Verify the SQL query checks for status='approved'
        assert "status = 'approved'" in source, (
            "SAFETY VIOLATION: apply_approved() must SELECT only status='approved' proposals."
        )

    @pytest.mark.asyncio
    async def test_orchestrator_cycle_only_calls_store_save(
        self, sample_coverage_matrix: str,
    ) -> None:
        """During a cycle, orchestrator must ONLY call store.save() — never apply_approved()."""
        store = AsyncMock()
        store.save = AsyncMock(return_value="id")
        store.is_duplicate = AsyncMock(return_value=False)
        store.is_blacklisted = AsyncMock(return_value=False)
        store.expire_stale = AsyncMock(return_value=0)
        store.apply_approved = AsyncMock()

        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        # Mock dispatcher to return good evidence
        with patch.object(
            orch.simple, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="PP 48/2021 regulates KITAS. " * 10,
                    source_type="ollama",
                    citations=["PP 48/2021"],
                    confidence=0.8,
                ),
            ],
        ), patch.object(
            orch.medium, "dispatch",
            new_callable=AsyncMock,
            return_value=[
                ResearchEvidence(
                    content="HyDE expanded content about topic. " * 10,
                    source_type="hyde_synthesis",
                    citations=["Source A"],
                    confidence=0.7,
                ),
            ],
        ):
            result = await orch.run_cycle(max_gaps=5)

        # save() should have been called for created proposals
        if result.proposals_created > 0:
            assert store.save.called

        # apply_approved MUST NEVER be called by the orchestrator
        store.apply_approved.assert_not_called()

    @pytest.mark.asyncio
    async def test_back_to_back_scan_produces_single_proposal(
        self, sample_coverage_matrix: str,
    ) -> None:
        """Two consecutive scans of the same gap should produce 1 proposal (dedup)."""
        store = AsyncMock()
        store.save = AsyncMock(return_value="id")
        store.is_duplicate = AsyncMock(side_effect=[False, True, True, True, True, True, True, True, True, True])
        store.is_blacklisted = AsyncMock(return_value=False)
        store.expire_stale = AsyncMock(return_value=0)

        orch = CuriosityOrchestrator(
            proposal_store=store,
            coverage_matrix_path=sample_coverage_matrix,
        )

        good_evidence = [
            ResearchEvidence(
                content="Detailed regulatory content " * 10,
                source_type="ollama",
                citations=["PP 1"],
                confidence=0.8,
            ),
        ]

        with patch.object(orch.simple, "dispatch", new_callable=AsyncMock, return_value=good_evidence), \
             patch.object(orch.medium, "dispatch", new_callable=AsyncMock, return_value=good_evidence):
            # First scan
            r1 = await orch.run_cycle(max_gaps=5)
            # Second scan — should all be deduplicated
            r2 = await orch.run_cycle(max_gaps=5)

        # First scan creates proposals, second should skip all (dedup)
        assert r2.proposals_created == 0 or r2.skipped_dedup > 0
